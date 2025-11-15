"""Protocol-specific validation rules."""

# Import all protocol modules to register their rules
from . import amqp  # noqa: F401

__all__ = ["amqp"]
