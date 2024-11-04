from pathlib import Path
from typing import Generator
from typing_extensions import Self
from contextlib import contextmanager

DOCUMENT_CONTEXT_STACK: list[Path] = []


@contextmanager
def set_current_doc_path(path: Path) -> Generator[None, None, None]:
    DOCUMENT_CONTEXT_STACK.append(path)
    yield
    DOCUMENT_CONTEXT_STACK.pop()


def current_doc_path():
    if not DOCUMENT_CONTEXT_STACK:
        raise AssertionError(
            "No Document path available. "
            + "Make sure you have used `with` statement on the "
            + "current DocumentPath during construction.\n"
        )
    return DOCUMENT_CONTEXT_STACK[-1]
