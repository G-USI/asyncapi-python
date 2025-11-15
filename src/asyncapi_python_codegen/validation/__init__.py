"""AsyncAPI document validation system.

This module provides a pluggable validation system for AsyncAPI 3.0 documents.
All validation is performed through rules that can be extended or disabled.

Example:
    from asyncapi_python_codegen.validation import validate_spec, ValidationError

    try:
        issues = validate_spec(spec, operations, spec_path)
    except ValidationError as e:
        for error in e.errors:
            print(f"{error.path}: {error.message}")
"""

from pathlib import Path
from typing import Any

from asyncapi_python.kernel.document import Operation

from .base import get_registry, rule
from .context import ValidationContext
from .errors import Severity, ValidationError, ValidationIssue

__all__ = [
    "validate_spec",
    "rule",
    "ValidationError",
    "ValidationIssue",
    "Severity",
    "ValidationContext",
]


def validate_spec(
    spec: dict[str, Any],
    operations: dict[str, Operation] | None,
    spec_path: Path,
    categories: list[str] | None = None,
    fail_on_error: bool = True,
) -> list[ValidationIssue]:
    """
    Validate an AsyncAPI spec using registered rules.

    Args:
        spec: Raw AsyncAPI YAML as dict
        operations: Parsed operations (None if parsing failed)
        spec_path: Path to the YAML file
        categories: List of rule categories to run (None = all)
        fail_on_error: If True, raise ValidationError on errors

    Returns:
        List of all validation issues (errors, warnings, info)

    Raises:
        ValidationError: If validation fails and fail_on_error is True
    """
    # Import core rules to ensure they're registered
    from . import core  # noqa: F401  # pyright: ignore[reportUnusedImport]

    # Import protocol-specific rules (AMQP, etc.)
    from . import protocol  # noqa: F401  # pyright: ignore[reportUnusedImport]

    # Create validation context
    context = ValidationContext(spec=spec, spec_path=spec_path, operations=operations)

    # Run validation
    registry = get_registry()
    issues = registry.validate(context, categories)

    # Raise on errors if requested
    if fail_on_error and any(issue.severity == Severity.ERROR for issue in issues):
        raise ValidationError(issues)

    return issues
