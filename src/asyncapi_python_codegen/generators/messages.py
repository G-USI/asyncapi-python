"""Message model generation from JSON Schema."""

import json
from typing import Any, Dict
from asyncapi_python.kernel.document import Operation


class MessageGenerator:
    """Generates Pydantic message models from AsyncAPI message schemas."""

    def extract_messages(self, operations: Dict[str, Operation]) -> Dict[str, Any]:
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

    def _to_pascal_case(self, name: str) -> str:
        """Convert name to PascalCase."""
        return "".join(
            word.capitalize()
            for word in name.replace("-", "_").replace(".", "_").split("_")
        )