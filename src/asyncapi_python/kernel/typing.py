"""Unified type system for the AsyncAPI Python kernel

This module defines all TypeVars used across the kernel with clear relationships
between application data, encoded data, and wire messages.
"""

from typing import Any, Generic, Protocol, TypeVar
from typing_extensions import TypeAlias


# Base protocols for type bounds
class Serializable(Protocol):
    """Protocol for data that can be serialized"""
    pass


class WireData(Protocol):
    """Protocol for wire-level data"""
    pass


# Wire message protocols
class Message(Protocol):
    @property
    def payload(self) -> bytes:
        """Payload of the message"""

    @property
    def headers(self) -> dict[str, Any]:
        """Message headers"""

    @property
    def correlation_id(self) -> str | None:
        """AsyncAPI 3.0 correlation ID for RPC request/response matching"""

    @property
    def reply_to(self) -> str | None:
        """AsyncAPI 3.0 reply-to address for dynamic RPC responses"""


class IncomingMessage(Message, Protocol):
    async def ack(self) -> None:
        """Processing of the message successful"""

    async def nack(self) -> None:
        """Processing of the message failed due to app internal reason"""

    async def reject(self) -> None:
        """Processing of the message failed due to external reasons (e.g. protocol validation)"""


# Core application data types
T_Input = TypeVar("T_Input", contravariant=True, bound=Serializable)
"""Input to handler functions (user application code receives this)"""

T_Output = TypeVar("T_Output", covariant=True, bound=Serializable)
"""Output from handler functions (user application code returns this)"""

# Codec layer types - connect application data to wire data
T_DecodedPayload = TypeVar("T_DecodedPayload", bound=Serializable)
"""Application-level payload data (what codecs decode to/encode from)"""

T_EncodedPayload = TypeVar("T_EncodedPayload", bound=WireData, default=bytes)
"""Wire-level encoded data (what codecs encode to/decode from)"""

# Wire layer types - transport-specific message types
T_Send = TypeVar("T_Send", bound=Message)
"""Outgoing wire messages (bound to Message protocol)"""

T_Recv = TypeVar("T_Recv", covariant=True, bound=IncomingMessage) 
"""Incoming wire messages (bound to IncomingMessage protocol)"""


# Type relationships (aliases for clarity)
ApplicationData: TypeAlias = T_DecodedPayload
"""Alias for application-level data types"""

WirePayload: TypeAlias = T_EncodedPayload
"""Alias for wire-level payload types"""

HandlerInput: TypeAlias = T_Input
"""Alias for handler input types"""

HandlerOutput: TypeAlias = T_Output
"""Alias for handler output types"""


# Handler protocol for user callback functions
class Handler(Protocol, Generic[T_Input, T_Output]):
    """A callback function, provided by user"""

    async def __call__(self, m: T_Input) -> T_Output: ...