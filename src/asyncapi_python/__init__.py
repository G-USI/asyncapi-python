"""AsyncAPI Python - Generate type-safe async Python applications from AsyncAPI 3 specifications."""

from importlib.metadata import version

try:
    __version__ = version("asyncapi-python")
except Exception:
    # Fallback for development/uninstalled packages
    __version__ = "unknown"

__all__ = ["__version__"]
