"""Parameter TypedDict generation for parameterized channels."""

import json
import tempfile
from pathlib import Path
from typing import Any

from datamodel_code_generator.__main__ import main as datamodel_codegen


class ParameterGenerator:
    """Generates TypedDict classes for channel parameters."""

    def generate_parameter_models(self, operations: list[Any]) -> str:
        """Generate TypedDict models from operations' resolved channels."""
        from asyncapi_python.kernel.document import Operation

        parameter_schemas: dict[str, Any] = {}

        # Collect unique parameterized channels from all operations
        seen_addresses: set[str] = set()

        for op in operations:
            if not isinstance(op, Operation):
                continue

            channel = op.channel
            if not channel or not channel.address:
                continue

            # Check if channel has parameters in address
            if "{" not in channel.address or "}" not in channel.address:
                continue

            # Skip if we've already processed this channel address
            if channel.address in seen_addresses:
                continue
            seen_addresses.add(channel.address)

            # Skip if channel has no parameters defined
            if not channel.parameters:
                continue

            # Generate TypedDict name from channel address pattern
            dict_name = self._channel_to_dict_name(channel.address)

            # Build schema for this channel's parameters
            properties: dict[str, Any] = {}
            required: list[str] = []

            for param_name, param_obj in channel.parameters.items():
                # For parameters with 'location' field (used by publishers for extraction),
                # generate as 'str' type for subscriber wildcard support
                if hasattr(param_obj, "location") and param_obj.location:
                    properties[param_name] = {"type": "string"}
                else:
                    # Convert parameter definition to JSON Schema property
                    # For AddressParameter objects without location, use default schema
                    properties[param_name] = {"type": "string"}

                # All channel parameters are required
                required.append(param_name)

            # Only create TypedDict if there are properties
            if properties:
                parameter_schemas[dict_name] = {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                    "title": dict_name,
                }

        if not parameter_schemas:
            return self._generate_empty_parameters()

        # Create unified JSON Schema with all parameter TypedDicts
        unified_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$defs": parameter_schemas,
        }

        # Generate TypedDicts using datamodel-code-generator
        return self._generate_with_datamodel_codegen(unified_schema)

    def _channel_to_dict_name(self, channel_name: str) -> str:
        """Convert channel pattern to TypedDict name.

        Example: 'market.data.{exchange}.{symbol}' -> 'MarketDataExchangeSymbolParams'
        """
        import re

        # Extract parameter names and include them in the TypedDict name
        params = re.findall(r"\{([^}]+)\}", channel_name)

        # Remove all parameter placeholders to get the base name
        clean_name = re.sub(r"\{[^}]+\}", "", channel_name)

        # Remove trailing/leading dots and convert to PascalCase
        parts = [p for p in clean_name.strip(".").split(".") if p]
        base_name = "".join(
            part.title().replace("-", "").replace("_", "") for part in parts
        )

        # Add parameter names in PascalCase
        param_suffix = "".join(p.title().replace("_", "") for p in params)

        return f"{base_name}{param_suffix}Params"

    def _param_to_schema(self, param_def: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert AsyncAPI parameter definition to JSON Schema."""
        schema: dict[str, Any] = {"type": "string"}  # Default to string

        if isinstance(param_def, dict):
            # Extract description
            if "description" in param_def:
                schema["description"] = param_def["description"]

            # Extract schema if provided
            if "schema" in param_def:
                schema.update(param_def["schema"])  # type: ignore[arg-type]

            # Handle enum values
            if "enum" in param_def:
                schema["enum"] = param_def["enum"]

            # Handle pattern
            if "pattern" in param_def:
                schema["pattern"] = param_def["pattern"]

        return schema

    def _generate_with_datamodel_codegen(self, schema: dict[str, Any]) -> str:
        """Generate TypedDict models using datamodel-code-generator."""
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_path = Path(temp_dir) / "schema.json"
            models_path = Path(temp_dir) / "models.py"

            # Write schema to temp file
            with schema_path.open("w") as f:
                json.dump(schema, f, indent=2)

            # Configure datamodel-code-generator for TypedDict output
            args = [
                "--input",
                str(schema_path.absolute()),
                "--output",
                str(models_path.absolute()),
                "--output-model-type",
                "typing.TypedDict",
                "--input-file-type",
                "jsonschema",
                "--target-python-version",
                "3.10",
                "--use-title-as-name",
                "--snake-case-field",
            ]

            # Run datamodel-code-generator
            datamodel_codegen(args=args)

            # Read generated models
            with models_path.open() as f:
                generated_code = f.read()

            return self._add_exports(generated_code)

    def _add_exports(self, generated_code: str) -> str:
        """Add __all__ export list to generated code."""
        import re

        # Extract TypedDict class names
        dict_names = re.findall(
            r"^class (\w+Params)\(TypedDict\)", generated_code, re.MULTILINE
        )

        if not dict_names:
            return generated_code

        # Add __all__ list
        all_list = f"\n__all__ = {dict_names!r}\n"
        return generated_code + all_list

    def _generate_empty_parameters(self) -> str:
        """Generate empty parameters module when no parameterized channels found."""
        return '''"""Generated parameter TypedDict models for AsyncAPI channels."""

from typing import TypedDict

# No parameterized channels found in the specification

__all__ = []
'''
