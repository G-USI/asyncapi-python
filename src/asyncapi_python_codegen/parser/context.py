"""Global context stack management for reference resolution."""

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from .types import ParseContext

# Thread-local storage for context stack
_context_storage = threading.local()


def _get_context_stack() -> list[ParseContext]:
    """Get current thread's context stack."""
    if not hasattr(_context_storage, "stack"):
        _context_storage.stack = []  # type: ignore[misc]
    return _context_storage.stack  # type: ignore[return-value]


def get_current_context() -> Optional[ParseContext]:
    """Get current parsing context from stack."""
    stack = _get_context_stack()
    return stack[-1] if stack else None


def push_context(context: ParseContext) -> None:
    """Push new context onto stack."""
    stack = _get_context_stack()
    stack.append(context)


def pop_context() -> Optional[ParseContext]:
    """Pop context from stack."""
    stack = _get_context_stack()
    return stack.pop() if stack else None


@contextmanager
def parsing_context(
    filepath: Path, json_pointer: str = ""
) -> Generator[ParseContext, None, None]:
    """Context manager for parsing scope."""
    context = ParseContext(filepath, json_pointer)
    push_context(context)
    try:
        yield context
    finally:
        pop_context()


@contextmanager
def json_pointer_context(pointer: str) -> Generator[ParseContext, None, None]:
    """Context manager for navigating to JSON pointer within current file."""
    current = get_current_context()
    if not current:
        raise RuntimeError("No current parsing context")

    context = current.with_pointer(pointer)
    push_context(context)
    try:
        yield context
    finally:
        pop_context()
