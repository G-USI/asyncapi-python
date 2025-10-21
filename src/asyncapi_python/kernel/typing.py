"""Unified type system for the AsyncAPI Python kernel

This module defines all TypeVars used across the kernel with clear relationships
between application data, encoded data, and wire messages.
"""

from types import CodeType
from typing import Any, Protocol, TypedDict, TypeVar

from typing_extensions import Required, TypeAlias


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
        return b""

    @property
    def headers(self) -> dict[str, Any]:
        """Message headers"""
        return {}

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


# Codec layer types - connect application data to wire data
T_DecodedPayload = TypeVar("T_DecodedPayload", bound=Serializable)
"""Application-level payload data (what codecs decode to/encode from)"""

T_EncodedPayload = TypeVar("T_EncodedPayload", bound=WireData)
"""Wire-level encoded data (what codecs encode to/decode from)"""

# Wire layer types - transport-specific message types
T_Send = TypeVar("T_Send", bound=Message)
"""Outgoing wire messages (bound to Message protocol)"""

T_Recv = TypeVar("T_Recv", covariant=True, bound=IncomingMessage)
"""Incoming wire messages (bound to IncomingMessage protocol)"""

# Channel parameter types
T_ChannelParams = TypeVar("T_ChannelParams", bound=dict[str, Any])
"""Channel parameters for parameterized channels (bound to dict)"""

# Handler-specific invariant TypeVars - prevent list[T]/T type splitting
T_Input = TypeVar("T_Input", bound=Serializable, contravariant=False, covariant=False)
"""Invariant input type for handlers - exact type matching prevents variance issues"""

T_Output = TypeVar("T_Output", bound=Serializable, contravariant=False, covariant=False)
"""Invariant output type for handlers - exact type matching prevents variance issues"""


# Type relationships (aliases for clarity)
ApplicationData: TypeAlias = T_DecodedPayload
"""Alias for application-level data types"""

WirePayload: TypeAlias = T_EncodedPayload
"""Alias for wire-level payload types"""

HandlerInput: TypeAlias = T_Input
"""Alias for handler input types"""

HandlerOutput: TypeAlias = T_Output
"""Alias for handler output types"""


# Batch configuration
class BatchConfig(TypedDict):
    """Configuration for batch processing"""

    max_size: Required[int]
    """Maximum number of messages in a batch"""

    timeout: Required[float]
    """Maximum wait time in seconds before processing batch"""


# Handler protocols for user callback functions - using invariant types
class Handler(Protocol[T_Input, T_Output]):  # type: ignore[misc]
    """A callback function, provided by user - uses invariant types for exact matching"""

    async def __call__(self, arg: T_Input, /) -> T_Output: ...

    @property
    def __name__(self) -> str: ...

    @property
    def __code__(self) -> CodeType: ...


class BatchHandler(Protocol[T_Input, T_Output]):
    """A batch callback function for RPC operations - processes list of inputs to list of outputs"""

    async def __call__(self, args: list[T_Input], /) -> list[T_Output]: ...

    @property
    def __name__(self) -> str: ...

    @property
    def __code__(self) -> CodeType: ...


class BatchConsumer(Protocol[T_Input]):
    """A batch callback function for consumer operations - processes list of inputs with no output"""

    async def __call__(self, args: list[T_Input], /) -> None: ...

    @property
    def __name__(self) -> str: ...

    @property
    def __code__(self) -> CodeType: ...
