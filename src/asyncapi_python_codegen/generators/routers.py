"""Router generation with nested path support."""

from typing import Any, Dict, List, Tuple
from dataclasses import dataclass
from asyncapi_python.kernel.document import Channel, Operation


@dataclass
class RouterInfo:
    """Information about a router for template generation."""

    class_name: str
    operation: Operation
    channel: Channel
    path: Tuple[str, ...]
    input_type: str
    output_type: str
    description: str

    @property
    def channel_repr(self) -> str:
        """Get string representation of channel for template."""
        return repr(self.channel)

    @property
    def operation_repr(self) -> str:
        """Get string representation of operation for template."""
        return repr(self.operation)


class RouterGenerator:
    """Generates nested router structures from operations."""

    def build_routers(self, operations: Dict[str, Operation]) -> List[RouterInfo]:
        """Build router information from operations."""
        routers = []

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

            router = RouterInfo(
                class_name=class_name,
                operation=operation,
                channel=operation.channel,
                path=path,
                input_type=input_type,
                output_type=output_type or "None",
                description=desc,
            )
            routers.append(router)

        return routers

    def split_routers(
        self, routers: List[RouterInfo]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Split routers into producer and consumer groups with nested structure."""
        producer_routers = {}
        consumer_routers = {}

        for router in routers:
            target = producer_routers if router.operation.action == "send" else consumer_routers
            self._insert_nested_router(target, router.path, router)

        return producer_routers, consumer_routers

    def _insert_nested_router(self, tree: Dict[str, Any], path: Tuple[str, ...], router: RouterInfo) -> None:
        """Insert a router into a nested tree structure."""
        current = tree

        # Navigate to the parent level
        for segment in path[:-1]:
            segment_lower = segment.lower()
            if segment_lower not in current:
                current[segment_lower] = {}
            current = current[segment_lower]

        # Insert the router at the final level
        final_segment = path[-1].lower()
        current[final_segment] = router

    def generate_nested_routers_code(self, routers_dict: Dict[str, Any], indent: int = 2, router_type: str = "") -> str:
        """Generate nested router initialization code."""
        lines = []
        indent_str = " " * indent

        for key, value in routers_dict.items():
            if isinstance(value, RouterInfo):
                # This is a router endpoint
                lines.append(f"{indent_str}self.{key} = {value.class_name}(wire_factory, codec_factory)")
            else:
                # This is a nested router level - create a sub-router class
                subclass_name = f"{router_type}{key.title()}Router" if router_type else f"{key.title()}Router"
                lines.append(f"{indent_str}self.{key} = {subclass_name}(wire_factory, codec_factory)")

        return "\n".join(lines)

    def collect_nested_classes(self, routers_dict: Dict[str, Any], prefix: str = "", router_type: str = "") -> List[str]:
        """Collect all nested router class definitions."""
        classes = []

        for key, value in routers_dict.items():
            if not isinstance(value, RouterInfo):
                # This is a nested level - generate a sub-router class
                # Make class name unique by including router type prefix
                class_name = f"{router_type}{key.title()}Router" if router_type else f"{key.title()}Router"
                full_prefix = f"{prefix}.{key}" if prefix else key

                # Generate class definition
                class_def = self._generate_nested_class(class_name, value, router_type)
                classes.append(class_def)

                # Recursively collect nested classes
                classes.extend(self.collect_nested_classes(value, full_prefix, router_type))

        return classes

    def _generate_nested_class(self, class_name: str, routers_dict: Dict[str, Any], router_type: str = "") -> str:
        """Generate a nested router class definition."""
        lines = [
            f"class {class_name}:",
            f'    """Nested router for {class_name.lower().replace("router", "").replace(router_type.lower(), "")} operations."""',
            "",
            f"    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):",
        ]

        for key, value in routers_dict.items():
            if isinstance(value, RouterInfo):
                lines.append(f"        self.{key} = {value.class_name}(wire_factory, codec_factory)")
            else:
                subclass_name = f"{router_type}{key.title()}Router" if router_type else f"{key.title()}Router"
                lines.append(f"        self.{key} = {subclass_name}(wire_factory, codec_factory)")

        return "\n".join(lines)

    def _get_message_type(self, operation: Operation, is_input: bool) -> str:
        """Get message type name for operation."""
        if is_input:
            # Use first message from channel
            if operation.channel.messages:
                msg_name = next(iter(operation.channel.messages.keys()))
                return self._to_pascal_case(msg_name)
        else:
            # Use first message from reply channel
            if operation.reply and operation.reply.channel.messages:
                msg_name = next(iter(operation.reply.channel.messages.keys()))
                return self._to_pascal_case(msg_name)

        return "Any"

    def _to_pascal_case(self, name: str) -> str:
        """Convert name to PascalCase."""
        return "".join(
            word.capitalize()
            for word in name.replace("-", "_").replace(".", "_").split("_")
        )