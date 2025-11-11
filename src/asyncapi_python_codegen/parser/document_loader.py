"""Main document loader and operations extractor."""

from pathlib import Path

from asyncapi_python.kernel.document import Operation

from .context import parsing_context
from .extractors import extract_operation
from .references import load_yaml_file


def extract_all_operations(
    yaml_path: Path, validate: bool = True, fail_on_error: bool = True
) -> dict[str, Operation]:
    """Extract all operations from AsyncAPI document.

    Args:
        yaml_path: Path to AsyncAPI YAML file
        validate: Whether to run validation rules (default: True)
        fail_on_error: Whether to raise ValidationError on errors (default: True)

    Returns:
        Dictionary mapping operation IDs to Operation dataclasses

    Raises:
        RuntimeError: If file cannot be loaded or parsed
        ValueError: If document structure is invalid
        ValidationError: If validation fails and fail_on_error is True
    """
    # Load the main document
    with parsing_context(yaml_path):
        document = load_yaml_file(yaml_path)

        # Validate basic document structure - document is already known to be dict from load_yaml_file

        if "asyncapi" not in document:
            raise ValueError("Missing 'asyncapi' version field")

        if "operations" not in document:
            raise ValueError("Missing 'operations' section")

        operations_data = document["operations"]
        if not isinstance(operations_data, dict):
            raise ValueError("'operations' must be a dictionary")

        # Extract each operation
        operations: dict[str, Operation] = {}
        for operation_id, operation_data in operations_data.items():  # type: ignore[misc]
            try:
                # Extract operation with reference resolution
                operation = extract_operation(operation_data)  # type: ignore[arg-type]
                # Create new operation with key set from operation ID
                operation_with_key = Operation(
                    action=operation.action,
                    title=operation.title,
                    summary=operation.summary,
                    description=operation.description,
                    channel=operation.channel,
                    messages=operation.messages,
                    reply=operation.reply,
                    traits=operation.traits,
                    security=operation.security,
                    tags=operation.tags,
                    external_docs=operation.external_docs,
                    bindings=operation.bindings,
                    key=operation_id,  # type: ignore[arg-type]
                )
                operations[operation_id] = operation_with_key
            except Exception as e:
                raise RuntimeError(
                    f"Failed to extract operation '{operation_id}': {e}"
                ) from e

        # Run validation if enabled
        if validate:
            from ..validation import Severity, ValidationError, validate_spec

            try:
                issues = validate_spec(
                    spec=document,
                    operations=operations,
                    spec_path=yaml_path,
                    fail_on_error=fail_on_error,
                )

                # Print warnings and info even if not failing
                for issue in issues:
                    if issue.severity in (Severity.WARNING, Severity.INFO):
                        print(f"  {issue}")

            except ValidationError as e:
                # Print all issues before re-raising
                print("\n❌ Document validation failed:\n")
                for issue in e.issues:
                    print(f"  {issue}\n")
                raise

        return operations


def load_document_info(yaml_path: Path) -> dict[str, str]:
    """Load basic document info (asyncapi version, title, etc.).

    Args:
        yaml_path: Path to AsyncAPI YAML file

    Returns:
        Dictionary with document metadata
    """
    with parsing_context(yaml_path):
        document = load_yaml_file(yaml_path)

        info = document.get("info", {})
        return {
            "asyncapi_version": document.get("asyncapi", "unknown"),
            "title": info.get("title", "Untitled"),
            "version": info.get("version", "0.0.0"),
            "description": info.get("description", ""),
        }
