"""AsyncAPI Python Code Generator."""

from .generators import CodeGenerator
from .parser import extract_all_operations, load_document_info
from .cli import app

from importlib.metadata import version

try:
    __version__ = version("asyncapi-python")
except Exception:
    # Fallback for development/uninstalled packages
    __version__ = "unknown"
__all__ = ["CodeGenerator", "extract_all_operations", "load_document_info", "app"]
