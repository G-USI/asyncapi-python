"""Reference resolution decorator and utilities."""

from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

import yaml

from .context import get_current_context, pop_context, push_context
from .types import YamlDocument, navigate_json_pointer

T = TypeVar("T")

# Cache for loaded YAML files to avoid re-reading
_file_cache: dict[Path, YamlDocument] = {}


def load_yaml_file(filepath: Path) -> YamlDocument:
    """Load YAML file with caching."""
    abs_path = filepath.absolute()

    if abs_path in _file_cache:
        return _file_cache[abs_path]

    try:
        with abs_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ValueError(
                    f"Expected YAML document to be a dictionary, got {type(data)}"
                )
            _file_cache[abs_path] = data
            return data  # type: ignore[return-value]
    except Exception as e:
        raise RuntimeError(f"Failed to load YAML file {abs_path}: {e}") from e


def resolve_reference(ref_data: YamlDocument) -> YamlDocument:
    """Resolve $ref in data to actual content."""

    current_context = get_current_context()
    if not current_context:
        raise RuntimeError("No parsing context available for reference resolution")

    # Extract reference string
    ref_string = ref_data.get("$ref")
    if not ref_string:
        raise ValueError("Missing $ref in reference object")

    # Resolve reference to new context
    target_context = current_context.resolve_reference(ref_string)

    # Load target file
    target_data = load_yaml_file(target_context.filepath)

    # Navigate to JSON pointer location
    if target_context.json_pointer:
        resolved_data = navigate_json_pointer(target_data, target_context.json_pointer)
    else:
        resolved_data = target_data

    # Ensure resolved data is a dictionary
    if not isinstance(resolved_data, dict):
        raise ValueError(
            f"Reference {ref_string} resolved to non-dictionary: {type(resolved_data)}"
        )

    return resolved_data  # type: ignore[return-value]


def is_reference(data: Any) -> bool:
    """Check if data is a reference object (contains $ref)."""
    return isinstance(data, dict) and "$ref" in data


def maybe_ref(func: Callable[[YamlDocument], T]) -> Callable[[YamlDocument], T]:
    """Decorator that automatically resolves references before calling function.

    If the input data contains a $ref, resolve it first and update context.
    Otherwise, pass data through unchanged.
    """

    @wraps(func)
    def wrapper(data: YamlDocument) -> T:
        if is_reference(data):

            # Get current context and resolve reference
            current_context = get_current_context()
            if not current_context:
                raise RuntimeError(
                    "No parsing context available for reference resolution"
                )

            ref_string = data.get("$ref")
            if not ref_string or not isinstance(ref_string, str):
                raise ValueError("Invalid or missing $ref value")
            target_context = current_context.resolve_reference(ref_string)

            # Load target file and navigate to JSON pointer
            target_data = load_yaml_file(target_context.filepath)
            if target_context.json_pointer:
                resolved_data = navigate_json_pointer(
                    target_data, target_context.json_pointer
                )
            else:
                resolved_data = target_data

            # Check if this is an external reference (different file)
            if target_context.filepath != current_context.filepath:
                # External reference - push new context for processing resolved data
                push_context(
                    target_context.with_pointer("")
                )  # Start at root of new file
                try:
                    return func(resolved_data)
                finally:
                    pop_context()
            else:
                # Internal reference - process without changing context
                return func(resolved_data)
        else:
            # No reference, call function directly
            return func(data)

    return wrapper
