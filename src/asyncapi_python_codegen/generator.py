"""Main code generator using parser and templates."""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader
from black import format_str, FileMode
import subprocess
import sys

from .parser import extract_all_operations, load_document_info
from asyncapi_python.kernel.document import Operation, Channel


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


class CodeGenerator:
    """Generate Python code from AsyncAPI specifications."""

    def __init__(self):
        """Initialize the code generator."""
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Add custom filters
        self.env.filters["repr"] = repr

    def generate(self, spec_path: Path, output_dir: Path, force: bool = False) -> None:
        """Generate code from AsyncAPI spec.

        Args:
            spec_path: Path to AsyncAPI YAML file
            output_dir: Output directory for generated code
            force: If True, overwrite existing directory. If False, fail if directory exists.
        """
        # Check if output directory exists and handle force flag
        if output_dir.exists() and not force:
            raise ValueError(
                f"Output directory {output_dir} already exists. Use --force to overwrite."
            )
        elif output_dir.exists() and force:
            print(f"Warning: Overwriting existing directory {output_dir}")

        # Parse the spec
        print(f"Parsing {spec_path}...")
        operations = extract_all_operations(spec_path)
        doc_info = load_document_info(spec_path)

        # Build router information
        routers = self._build_routers(operations)
        producer_routers, consumer_routers = self._split_routers(routers)

        # Extract and generate message models
        messages = self._extract_messages(operations)

        # Prepare template context
        context = {
            # Document info
            "app_title": doc_info["title"],
            "app_description": doc_info["description"],
            "app_version": doc_info["version"],
            "asyncapi_version": doc_info["asyncapi_version"],
            # Routers
            "routers": routers,
            "producer_routers": producer_routers,
            "consumer_routers": consumer_routers,
            # Messages
            "messages": messages,
        }

        # Generate files
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate router.py
        self._generate_file("router.py.j2", output_dir / "router.py", context)

        # Generate application.py
        self._generate_file("application.py.j2", output_dir / "application.py", context)

        # Generate messages/json/__init__.py (for JsonCodecFactory compatibility)
        messages_json_dir = output_dir / "messages" / "json"
        messages_json_dir.mkdir(parents=True, exist_ok=True)
        self._generate_file(
            "messages.py.j2", messages_json_dir / "__init__.py", context
        )

        # Generate __init__.py
        self._generate_file("__init__.py.j2", output_dir / "__init__.py", context)

        print(f"✅ Generated code in {output_dir}")

        # Run mypy for validation
        self._run_mypy(output_dir)

    def _build_routers(self, operations: Dict[str, Operation]) -> List[RouterInfo]:
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

    def _split_routers(
        self, routers: List[RouterInfo]
    ) -> Tuple[Dict[Tuple[str, ...], RouterInfo], Dict[Tuple[str, ...], RouterInfo]]:
        """Split routers into producer and consumer groups."""
        producer_routers = {}
        consumer_routers = {}

        for router in routers:
            if router.operation.action == "send":
                producer_routers[router.path] = router
            else:
                consumer_routers[router.path] = router

        return producer_routers, consumer_routers

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

    def _extract_messages(self, operations: Dict[str, Operation]) -> Dict[str, Any]:
        """Extract message definitions from operations."""
        messages = {}

        for op_id, operation in operations.items():
            # Extract messages from channel
            for msg_name, message in operation.channel.messages.items():
                class_name = self._to_pascal_case(msg_name)
                if class_name not in messages:
                    messages[class_name] = self._build_message_info(message)

            # Extract reply messages
            if operation.reply:
                for msg_name, message in operation.reply.channel.messages.items():
                    class_name = self._to_pascal_case(msg_name)
                    if class_name not in messages:
                        messages[class_name] = self._build_message_info(message)

        return messages

    def _build_message_info(self, message) -> Dict[str, Any]:
        """Build message information for template."""
        info = {
            "description": getattr(message, "description", None) or "",
            "fields": {},
        }

        # Extract fields from payload
        if hasattr(message, "payload") and isinstance(message.payload, dict):
            payload = message.payload
            if payload.get("type") == "object" and "properties" in payload:
                for prop_name, prop_schema in payload["properties"].items():
                    field_info = {
                        "type": self._json_type_to_python(
                            prop_schema.get("type", "Any")
                        ),
                        "default": None,
                    }

                    # Handle const/literal
                    if "const" in prop_schema:
                        const_val = prop_schema["const"]
                        field_info["type"] = f"Literal[{json.dumps(const_val)}]"
                        field_info["default"] = json.dumps(const_val)

                    # Handle enum
                    elif "enum" in prop_schema:
                        enum_vals = ", ".join(
                            json.dumps(v) for v in prop_schema["enum"]
                        )
                        field_info["type"] = f"Literal[{enum_vals}]"

                    # Handle format
                    elif "format" in prop_schema:
                        if prop_schema["format"] == "uuid":
                            field_info["type"] = "str"
                        elif prop_schema["format"] == "date-time":
                            field_info["type"] = "str"
                        elif prop_schema["format"] == "email":
                            field_info["type"] = "str"

                    info["fields"][prop_name] = field_info

        return info

    def _json_type_to_python(self, json_type: str) -> str:
        """Convert JSON type to Python type."""
        type_map = {
            "string": "str",
            "number": "float",
            "integer": "int",
            "boolean": "bool",
            "array": "List[Any]",
            "object": "Dict[str, Any]",
            "null": "None",
        }
        return type_map.get(json_type, "Any")

    def _generate_file(
        self, template_name: str, output_path: Path, context: Dict[str, Any]
    ) -> None:
        """Generate a file from template."""
        template = self.env.get_template(template_name)
        content = template.render(**context)

        # Always format with black - retry with different modes if needed
        formatted_content = self._format_with_black(content, template_name)

        output_path.write_text(formatted_content)
        print(f"  Generated: {output_path}")

    def _format_with_black(self, content: str, filename: str) -> str:
        """Format content with Black, with fallback strategies."""
        # Try standard formatting first
        try:
            return format_str(content, mode=FileMode())
        except Exception as e1:
            print(f"  Warning: Standard Black formatting failed for {filename}: {e1}")

            # Try with different line length
            try:
                mode = FileMode(line_length=120)
                return format_str(content, mode=mode)
            except Exception as e2:
                print(
                    f"  Warning: Extended line Black formatting failed for {filename}: {e2}"
                )

                # Try to fix common syntax issues and retry
                try:
                    fixed_content = self._fix_common_syntax_issues(content)
                    return format_str(fixed_content, mode=FileMode())
                except Exception as e3:
                    print(
                        f"  Error: All Black formatting attempts failed for {filename}: {e3}"
                    )
                    print(f"  Raw content preview: {content[:200]}...")
                    # Return unformatted content rather than crash
                    return content

    def _fix_common_syntax_issues(self, content: str) -> str:
        """Fix common syntax issues that prevent Black from formatting."""
        lines = content.split("\n")
        fixed_lines = []

        for line in lines:
            # Fix missing newlines between fields
            if (
                line.strip()
                and not line.startswith(" ")
                and not line.startswith('"""')
                and not line.startswith("class ")
                and not line.startswith("def ")
                and not line.startswith("from ")
                and not line.startswith("import ")
                and ":" in line
                and "=" not in line
                and len(fixed_lines) > 0
                and fixed_lines[-1].strip()
                and not fixed_lines[-1].strip().endswith(":")
            ):
                # This looks like a field without proper indentation/separation
                # Add proper indentation if missing
                if not line.startswith("    "):
                    line = "    " + line.strip()

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def _run_mypy(self, output_dir: Path) -> None:
        """Run mypy on generated code."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "mypy", str(output_dir)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("✅ Type checking passed")
            else:
                print(f"⚠️ Type checking warnings:\n{result.stdout}")
        except Exception as e:
            print(f"⚠️ Could not run mypy: {e}")
