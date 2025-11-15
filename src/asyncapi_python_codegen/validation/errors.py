"""Validation error types and severity levels."""

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    """Severity level of a validation issue."""

    ERROR = "error"  # Blocks code generation
    WARNING = "warning"  # Continues with warning
    INFO = "info"  # Informational only


@dataclass
class ValidationIssue:
    """A single validation issue found in a document."""

    severity: Severity
    message: str
    path: str  # JSONPath to the error location (e.g., "$.channels.myChannel")
    rule: str  # Rule identifier (e.g., "channel-address-matches-parameters")
    suggestion: str | None = None  # Optional suggestion for fixing the issue

    def __str__(self) -> str:
        """Format issue for display."""
        level_emoji = {
            Severity.ERROR: "❌",
            Severity.WARNING: "⚠️ ",
            Severity.INFO: "ℹ️ ",
        }
        emoji = level_emoji.get(self.severity, "")
        suggestion_str = f"\n    💡 {self.suggestion}" if self.suggestion else ""
        return f"{emoji} {self.message}\n    at {self.path}{suggestion_str}"


class ValidationError(ValueError):
    """Raised when document validation fails with errors."""

    def __init__(self, issues: list[ValidationIssue]):
        """
        Initialize validation error with issues.

        Args:
            issues: List of all validation issues (errors, warnings, info)
        """
        self.issues = issues
        self.errors = [i for i in issues if i.severity == Severity.ERROR]
        self.warnings = [i for i in issues if i.severity == Severity.WARNING]
        self.info = [i for i in issues if i.severity == Severity.INFO]

        if self.errors:
            error_messages = "\n\n".join(str(e) for e in self.errors)
            message = f"Document validation failed with {len(self.errors)} error(s):\n\n{error_messages}"
        else:
            message = "Document validation completed (no errors)"

        super().__init__(message)

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0
