"""Type aliases and basic types for AsyncAPI parsing."""

from pathlib import Path
from typing import Any

# Type alias for raw YAML document data
YamlDocument = dict[str, Any]


# Context for tracking current parsing location
class ParseContext:
    """Represents current parsing context (file path + JSON pointer)."""

    def __init__(self, filepath: Path, json_pointer: str = ""):
        self.filepath = filepath.absolute()
        self.json_pointer = json_pointer

    def __str__(self) -> str:
        return f"{self.filepath}#{self.json_pointer}"

    def with_pointer(self, pointer: str) -> "ParseContext":
        """Create new context with different JSON pointer."""
        return ParseContext(self.filepath, pointer)

    def resolve_reference(self, ref: str) -> "ParseContext":
        """Resolve a $ref string to new context."""
        if "#" in ref:
            filepath_part, pointer_part = ref.split("#", 1)
            if filepath_part == "":
                # Internal reference - same file
                return ParseContext(self.filepath, pointer_part)
            else:
                # External reference - different file
                if Path(filepath_part).is_absolute():
                    target_path = Path(filepath_part)
                else:
                    # Relative to current file
                    target_path = (self.filepath.parent / filepath_part).resolve()
                return ParseContext(target_path, pointer_part)
        else:
            # Just a file reference with no pointer
            if Path(ref).is_absolute():
                target_path = Path(ref)
            else:
                target_path = (self.filepath.parent / ref).resolve()
            return ParseContext(target_path, "")


# JSON Pointer utilities
def unescape_json_pointer(pointer_segment: str) -> str:
    """Unescape JSON Pointer segment according to RFC 6901.

    ~0 becomes ~
    ~1 becomes /
    """
    return pointer_segment.replace("~1", "/").replace("~0", "~")


def parse_json_pointer(pointer: str) -> list[str]:
    """Parse JSON pointer into list of unescaped segments."""
    if not pointer.startswith("/"):
        return []

    segments = pointer[1:].split("/")  # Remove leading /
    return [unescape_json_pointer(seg) for seg in segments]


def navigate_json_pointer(data: YamlDocument, pointer: str) -> Any:
    """Navigate to data at JSON pointer location."""
    if not pointer:
        return data

    current = data
    segments = parse_json_pointer(pointer)

    for segment in segments:
        if isinstance(current, dict):
            if segment not in current:
                raise KeyError(f"JSON pointer segment '{segment}' not found")
            current = current[segment]  # type: ignore[assignment]
        elif isinstance(current, list):
            try:
                index = int(segment)
                current = current[index]  # type: ignore[assignment]
            except (ValueError, IndexError) as e:
                raise KeyError(
                    f"Invalid array index in JSON pointer: '{segment}'"
                ) from e
        else:
            raise KeyError(f"Cannot navigate into non-dict/list: {type(current)}")

    return current  # type: ignore[return-value]
