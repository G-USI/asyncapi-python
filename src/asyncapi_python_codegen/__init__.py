"""AsyncAPI Python Code Generator."""

from importlib.metadata import version

from .cli import app
from .generators import CodeGenerator
from .parser import extract_all_operations, load_document_info

try:
    __version__ = version("asyncapi-python")
except Exception:
    # Fallback for development/uninstalled packages
    __version__ = "unknown"
__all__ = ["CodeGenerator", "extract_all_operations", "load_document_info", "app"]
