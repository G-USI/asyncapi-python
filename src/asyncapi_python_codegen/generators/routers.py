"""Router generation with nested path support."""

from dataclasses import dataclass
from typing import Any

from asyncapi_python.kernel.document import Channel, Operation
from asyncapi_python.utils import snake_case


@dataclass
class RouterInfo:
    """Information about a router for template generation."""

    class_name: str
    operation: Operation
    channel: Channel
    path: tuple[str, ...]
    input_type: str
    output_type: str
    description: str
    has_parameters: bool = False
    parameter_type_name: str = ""

    @property
    def channel_repr(self) -> str:
        """Get string representation of channel for template with spec prefix."""
        channel_str = repr(self.channel)

        # Replace all document struct references with spec. prefix
        document_classes = [
            "Channel",
            "Operation",
            "Message",
            "ChannelBindings",
            "OperationReply",
            "AddressParameter",
            "ExternalDocs",
            "Server",
            "Tag",
            "CorrelationId",
            "MessageBindings",
            "MessageExample",
            "MessageTrait",
            "OperationBindings",
            "OperationReplyAddress",
            "OperationTrait",
            "SecurityScheme",
        ]

        for class_name in document_classes:
            # Replace standalone class calls like Tag( with spec.Tag(
            channel_str = channel_str.replace(f"{class_name}(", f"spec.{class_name}(")

        return channel_str

    @property
    def operation_repr(self) -> str:
        """Get string representation of operation for template with spec prefix."""
        operation_str = repr(self.operation)

        # Replace all document struct references with spec. prefix
        document_classes = [
            "Channel",
            "Operation",
            "Message",
            "ChannelBindings",
            "OperationReply",
            "AddressParameter",
            "ExternalDocs",
            "Server",
            "Tag",
            "CorrelationId",
            "MessageBindings",
            "MessageExample",
            "MessageTrait",
            "OperationBindings",
            "OperationReplyAddress",
            "OperationTrait",
            "SecurityScheme",
        ]

        for class_name in document_classes:
            # Replace standalone class calls like Tag( with spec.Tag(
            operation_str = operation_str.replace(
                f"{class_name}(", f"spec.{class_name}("
            )

        return operation_str


class RouterGenerator:
    """Generates nested router structures from operations."""

    def build_routers(self, operations: dict[str, Operation]) -> list[RouterInfo]:
        """Build router information from operations."""
        routers: list[RouterInfo] = []

        for op_id, operation in operations.items():
            # Parse operation path - clean up leading/trailing slashes and split on both . and /
            clean_op_id = op_id.strip("/")
            path = tuple(
                segment
                for segment in clean_op_id.replace("/", ".").split(".")
                if segment
            )

            # Generate router class name - clean up any invalid characters
            class_name = (
                "".join(
                    segment.title().replace("-", "").replace("_", "")
                    for segment in path
                )
                + "Router"
            )

            # Determine message types
            input_type = self._get_message_type(operation, is_input=True)
            output_type = self._get_message_type(operation, is_input=False)

            # Build description
            desc = f"{op_id} operation"
            if operation.title:
                desc = operation.title
            elif operation.description:
                desc = operation.description

            # Check if channel has parameters (indicated by {} in address)
            has_parameters = (
                operation.channel.address is not None
                and "{" in operation.channel.address
                and "}" in operation.channel.address
            )
            parameter_type_name = ""

            if has_parameters:
                # Generate parameter TypedDict name from channel address
                if operation.channel.address:
                    parameter_type_name = self._channel_to_param_type_name(
                        operation.channel.address
                    )
                else:
                    parameter_type_name = "DefaultParams"

            router = RouterInfo(
                class_name=class_name,
                operation=operation,
                channel=operation.channel,
                path=path,
                input_type=input_type,
                output_type=output_type or "None",
                description=desc,
                has_parameters=has_parameters,
                parameter_type_name=parameter_type_name,
            )
            routers.append(router)

        return routers

    def _channel_to_param_type_name(self, channel_address: str) -> str:
        """Convert channel address to parameter TypedDict name.

        Example: 'market.data.{exchange}.{symbol}' -> 'MarketDataExchangeSymbolParams'
        """
        import re

        # Extract parameter names and include them in the TypedDict name
        params = re.findall(r"\{([^}]+)\}", channel_address)

        # Remove all parameter placeholders to get the base name
        clean_name = re.sub(r"\{[^}]+\}", "", channel_address)

        # Remove trailing/leading dots and convert to PascalCase
        parts = [p for p in clean_name.strip(".").split(".") if p]
        base_name = "".join(
            part.title().replace("-", "").replace("_", "") for part in parts
        )

        # Add parameter names in PascalCase
        param_suffix = "".join(p.title().replace("_", "") for p in params)

        return f"{base_name}{param_suffix}Params"

    def split_routers(
        self, routers: list[RouterInfo]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Split routers into producer and consumer groups with nested structure."""
        producer_routers: dict[str, Any] = {}
        consumer_routers: dict[str, Any] = {}

        for router in routers:
            target = (
                producer_routers
                if router.operation.action == "send"
                else consumer_routers
            )
            self._insert_nested_router(target, router.path, router)

        return producer_routers, consumer_routers

    def _insert_nested_router(
        self, tree: dict[str, Any], path: tuple[str, ...], router: RouterInfo
    ) -> None:
        """Insert a router into a nested tree structure."""
        current = tree

        # Navigate to the parent level
        for segment in path[:-1]:
            segment_snake = snake_case(segment)
            if segment_snake not in current:
                current[segment_snake] = {}
            current = current[segment_snake]

        # Insert the router at the final level
        final_segment = snake_case(path[-1])
        current[final_segment] = router

    def generate_nested_routers_code(
        self,
        routers_dict: dict[str, Any],
        indent: int = 2,
        router_type: str = "",
        prefix: str = "",
    ) -> str:
        """Generate nested router initialization code."""
        lines: list[str] = []
        indent_str = " " * indent

        for key, value in routers_dict.items():
            if isinstance(value, RouterInfo):
                # This is a router endpoint
                lines.append(
                    f"{indent_str}self.{key} = {value.class_name}(wire_factory, codec_factory)"
                )
            else:
                # This is a nested router level - create a sub-router class
                full_prefix = f"{prefix}.{key}" if prefix else key
                path_parts = full_prefix.split(".")
                class_name_parts = (
                    [router_type] + [part.title() for part in path_parts] + ["Router"]
                )
                subclass_name = "__".join(class_name_parts)
                lines.append(
                    f"{indent_str}self.{key} = {subclass_name}(wire_factory, codec_factory)"
                )

        return "\n".join(lines)

    def collect_nested_classes(
        self, routers_dict: dict[str, Any], prefix: str = "", router_type: str = ""
    ) -> list[str]:
        """Collect all nested router class definitions."""
        classes: list[str] = []

        for key, value in routers_dict.items():
            if not isinstance(value, RouterInfo):
                # This is a nested level - generate a sub-router class
                full_prefix = f"{prefix}.{key}" if prefix else key
                # Make class name unique by including the full path to avoid conflicts
                path_parts = full_prefix.split(".")
                class_name_parts = (
                    [router_type] + [part.title() for part in path_parts] + ["Router"]
                )
                class_name = "__".join(class_name_parts)

                # Generate class definition
                class_def = self._generate_nested_class(
                    class_name, value, router_type, full_prefix
                )
                classes.append(class_def)

                # Recursively collect nested classes
                classes.extend(
                    self.collect_nested_classes(value, full_prefix, router_type)
                )

        return classes

    def _generate_nested_class(
        self,
        class_name: str,
        routers_dict: dict[str, Any],
        router_type: str = "",
        prefix: str = "",
    ) -> str:
        """Generate a nested router class definition."""
        lines: list[str] = [
            f"class {class_name}:",
            f'    """Nested router for {class_name.lower().replace("router", "").replace(router_type.lower(), "")} operations."""',
            "",
            f"    def __init__(self, wire_factory: AbstractWireFactory[Any, Any], codec_factory: CodecFactory[Any, Any]):",
        ]

        for key, value in routers_dict.items():
            if isinstance(value, RouterInfo):
                lines.append(
                    f"        self.{key} = {value.class_name}(wire_factory, codec_factory)"
                )
            else:
                full_prefix = f"{prefix}.{key}" if prefix else key
                path_parts = full_prefix.split(".")
                class_name_parts = (
                    [router_type] + [part.title() for part in path_parts] + ["Router"]
                )
                subclass_name = "__".join(class_name_parts)
                lines.append(
                    f"        self.{key} = {subclass_name}(wire_factory, codec_factory)"
                )

        return "\n".join(lines)

    def _get_message_type(self, operation: Operation, is_input: bool) -> str:
        """Get message type name for operation."""
        if is_input:
            # Handle multiple messages from channel with union types
            if operation.channel.messages:
                message_types = [
                    self._to_pascal_case(msg_name)
                    for msg_name in operation.channel.messages.keys()
                ]
                if len(message_types) == 1:
                    return message_types[0]
                else:
                    # For union types, use Python 3.10+ | syntax
                    return " | ".join(message_types)
        else:
            # Handle multiple messages from reply channel with union types
            if operation.reply and operation.reply.channel.messages:
                message_types = [
                    self._to_pascal_case(msg_name)
                    for msg_name in operation.reply.channel.messages.keys()
                ]
                if len(message_types) == 1:
                    return message_types[0]
                else:
                    # For union types, use Python 3.10+ | syntax
                    return " | ".join(message_types)

        return "Any"

    def _to_pascal_case(self, name: str) -> str:
        """Convert name to PascalCase."""
        # Handle camelCase input by detecting internal capitals
        if "_" not in name and "-" not in name and "." not in name:
            # Check if it's camelCase (has internal capital letters)
            if any(c.isupper() for c in name[1:]):
                # Split on capital letters for camelCase
                import re

                words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", name)
                return "".join(word.capitalize() for word in words)

        # Handle underscore/hyphen/dot separated names (existing logic)
        return "".join(
            word.capitalize()
            for word in name.replace("-", "_").replace(".", "_").split("_")
        )
