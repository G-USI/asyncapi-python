"""Validation context providing access to document data."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from asyncapi_python.kernel.document import Operation


@dataclass
class ValidationContext:
    """Context passed to validation rules containing document data."""

    spec: dict[str, Any]  # Raw AsyncAPI YAML as dict
    spec_path: Path  # Path to the YAML file
    operations: dict[str, Operation] | None = None  # Parsed operations (if available)

    def get_channels(self) -> dict[str, Any]:
        """Get all channels from the spec."""
        return self.spec.get("channels", {})

    def get_operations_spec(self) -> dict[str, Any]:
        """Get operations section from raw spec."""
        return self.spec.get("operations", {})

    def get_components(self) -> dict[str, Any]:
        """Get components section from spec."""
        return self.spec.get("components", {})

    def get_info(self) -> dict[str, Any]:
        """Get info section from spec."""
        return self.spec.get("info", {})

    def get_servers(self) -> dict[str, Any]:
        """Get servers section from spec."""
        return self.spec.get("servers", {})
