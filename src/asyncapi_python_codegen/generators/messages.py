"""Message model generation using datamodel-code-generator."""

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml
from datamodel_code_generator.__main__ import main as datamodel_codegen

from asyncapi_python.kernel.document import Operation
from asyncapi_python_codegen.parser.types import ParseContext, navigate_json_pointer


class MessageGenerator:
    """Generates Pydantic message models using datamodel-code-generator."""

    def generate_message_models(
        self, operations: dict[str, Operation], spec_path: Path | None = None
    ) -> str:
        """Generate complete Pydantic models code using datamodel-code-generator."""
        # Collect all message schemas from operations
        message_schemas = self._collect_message_schemas(operations)

        if not message_schemas:
            return self._generate_empty_messages()

        # If we have a spec path, load component schemas for reference resolution
        component_schemas = {}
        if spec_path:
            component_schemas = self._load_component_schemas(spec_path)

        # Create unified JSON Schema with $defs including both message and component schemas
        all_schemas = {**message_schemas, **component_schemas}

        # Resolve references from #/components/schemas/... to #/$defs/...
        resolved_schemas = self._resolve_references(all_schemas)

        unified_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$defs": resolved_schemas,
        }

        # Use datamodel-code-generator to create Pydantic models
        return self._generate_with_datamodel_codegen(unified_schema)

    def _collect_message_schemas(
        self, operations: dict[str, Operation]
    ) -> dict[str, Any]:
        """Collect all message schemas from operations."""
        schemas = {}

        for operation in operations.values():
            # Extract messages from channel
            for msg_name, message in operation.channel.messages.items():
                schema_name = self._to_pascal_case(msg_name)
                if schema_name not in schemas:
                    schemas[schema_name] = self._extract_message_schema(message)

            # Extract reply messages
            if operation.reply:
                for msg_name, message in operation.reply.channel.messages.items():
                    schema_name = self._to_pascal_case(msg_name)
                    if schema_name not in schemas:
                        schemas[schema_name] = self._extract_message_schema(message)

        return schemas  # type: ignore[return-value]

    def _load_component_schemas(self, spec_path: Path) -> dict[str, Any]:
        """Load component schemas from the AsyncAPI specification file and all referenced files."""
        all_schemas: dict[str, Any] = {}
        visited_files: set[Path] = set()

        def load_schemas_from_file(file_path: Path) -> None:
            """Recursively load schemas from a file and its references."""
            abs_path = file_path.absolute()

            # Avoid infinite loops
            if abs_path in visited_files:
                return
            visited_files.add(abs_path)

            try:
                with abs_path.open("r") as f:
                    spec = yaml.safe_load(f)

                components = spec.get("components", {})
                schemas = components.get("schemas", {})
                messages = components.get("messages", {})

                # Add component schemas directly
                for schema_name, schema_def in schemas.items():
                    if schema_name not in all_schemas:
                        # Check if this schema is itself a reference
                        if isinstance(schema_def, dict) and "$ref" in schema_def:
                            ref_value: Any = schema_def["$ref"]  # type: ignore[misc]
                            # Resolve the reference using ParseContext utilities
                            if isinstance(ref_value, str):
                                try:
                                    context = ParseContext(abs_path)
                                    target_context = context.resolve_reference(
                                        ref_value
                                    )

                                    # Load and navigate to the referenced schema
                                    with target_context.filepath.open("r") as ref_file:
                                        ref_spec = yaml.safe_load(ref_file)

                                    if target_context.json_pointer:
                                        resolved_schema = navigate_json_pointer(
                                            ref_spec, target_context.json_pointer
                                        )
                                    else:
                                        resolved_schema = ref_spec

                                    all_schemas[schema_name] = resolved_schema
                                except Exception as e:
                                    print(
                                        f"Warning: Could not resolve reference {ref_value} in {abs_path}: {e}"
                                    )
                                    all_schemas[schema_name] = schema_def
                        else:
                            all_schemas[schema_name] = schema_def

                # Add message payloads from components
                for msg_name, msg_def in messages.items():
                    if isinstance(msg_def, dict) and "payload" in msg_def:
                        schema_name = self._to_pascal_case(msg_name)
                        if schema_name not in all_schemas:
                            all_schemas[schema_name] = msg_def["payload"]

                # Find and process all external file references
                self._find_and_process_refs(
                    spec, abs_path.parent, load_schemas_from_file
                )

            except Exception as e:
                print(f"Warning: Could not load component schemas from {abs_path}: {e}")

        # Start loading from the main spec file
        load_schemas_from_file(spec_path)

        return all_schemas  # type: ignore[return-value]

    def _find_and_process_refs(
        self, data: Any, base_dir: Path, process_file: Any
    ) -> None:
        """Recursively find all $ref entries pointing to external files."""
        if isinstance(data, dict):
            # Check if this is a reference
            if "$ref" in data:
                ref_value: Any = data["$ref"]  # type: ignore[misc]
                if isinstance(ref_value, str) and not ref_value.startswith("#"):
                    # External reference - extract file path
                    file_part: str
                    if "#" in ref_value:
                        file_part = ref_value.split("#")[0]
                    else:
                        file_part = ref_value

                    if file_part:
                        # Resolve relative path
                        ref_path = (base_dir / file_part).resolve()
                        process_file(ref_path)

            # Recurse into all dict values
            for value in data.values():  # type: ignore[misc]
                self._find_and_process_refs(value, base_dir, process_file)

        elif isinstance(data, list):
            # Recurse into all list items
            for item in data:  # type: ignore[misc]
                self._find_and_process_refs(item, base_dir, process_file)

    def _resolve_references(self, schemas: dict[str, Any]) -> dict[str, Any]:
        """Recursively resolve $ref references to use #/$defs/... instead of #/components/schemas/..."""

        def resolve_in_object(obj: Any) -> Any:
            if isinstance(obj, dict):
                resolved_obj: dict[str, Any] = {}
                for key, value in obj.items():  # type: ignore[misc]
                    if key == "$ref" and isinstance(value, str):
                        # Extract schema name from the reference
                        schema_name = value.split("/")[-1]

                        # Transform all component references to #/$defs/...
                        if "#/components/schemas/" in value:
                            # Internal or external schema reference
                            resolved_obj[key] = f"#/$defs/{schema_name}"
                        elif "#/components/messages/" in value:
                            # Handle message references - convert message name to PascalCase
                            schema_name = self._to_pascal_case(schema_name)
                            resolved_obj[key] = f"#/$defs/{schema_name}"
                        elif value.startswith("#"):
                            # Other internal references, keep as-is
                            resolved_obj[key] = value
                        else:
                            # External file reference (e.g., "./commons2.yaml#/components/schemas/Foo")
                            # Extract just the schema name and point to #/$defs
                            resolved_obj[key] = f"#/$defs/{schema_name}"
                    else:
                        resolved_obj[key] = resolve_in_object(value)
                return resolved_obj
            elif isinstance(obj, list):
                return [resolve_in_object(item) for item in obj]  # type: ignore[misc]
            else:
                return obj

        return {name: resolve_in_object(schema) for name, schema in schemas.items()}

    def _extract_message_schema(self, message: Any) -> dict[str, Any]:
        """Extract JSON Schema from a message object."""
        if hasattr(message, "payload") and isinstance(message.payload, dict):
            return message.payload  # type: ignore[return-value]
        else:
            # Fallback to a basic object schema
            return {"type": "object", "properties": {}}

    def _generate_with_datamodel_codegen(self, schema: dict[str, Any]) -> str:
        """Generate Pydantic models using datamodel-code-generator."""
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_path = Path(temp_dir) / "schema.json"
            models_path = Path(temp_dir) / "models.py"

            # Write the unified schema to a temporary file
            with schema_path.open("w") as schema_file:
                json.dump(schema, schema_file, indent=2)

            # Configure datamodel-code-generator arguments
            args = [
                "--input",
                str(schema_path.absolute()),
                "--output",
                str(models_path.absolute()),
                "--output-model-type",
                "pydantic_v2.BaseModel",
                "--input-file-type",
                "jsonschema",
                "--reuse-model",
                "--allow-extra-fields",
                "--collapse-root-models",
                "--target-python-version",
                "3.10",
                "--use-title-as-name",
                "--capitalize-enum-members",
                "--snake-case-field",
                "--allow-population-by-field-name",
            ]

            # Run datamodel-code-generator
            datamodel_codegen(args=args)

            # Read the generated models and add __all__ export
            with models_path.open() as models_file:
                generated_code = models_file.read()

            return self._add_all_export(generated_code)

    def _add_all_export(self, generated_code: str) -> str:
        """Add __all__ list to the generated code."""
        # Extract class names from the generated code
        model_names = re.findall(r"^class (\w+)", generated_code, re.MULTILINE)

        if not model_names:
            return generated_code + "\n__all__ = []\n"

        # Add the __all__ list at the end
        all_list = f"\n__all__ = {model_names!r}\n"
        return generated_code + all_list

    def _generate_empty_messages(self) -> str:
        """Generate empty message module when no schemas found."""
        return '''"""Generated message models from AsyncAPI specification."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

# No message schemas found in the specification
'''

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

    # Legacy method for backward compatibility - now returns empty dict since we generate complete code
    def extract_messages(self, operations: dict[str, Operation]) -> dict[str, Any]:
        """Extract message definitions from operations (legacy compatibility)."""
        return {}
