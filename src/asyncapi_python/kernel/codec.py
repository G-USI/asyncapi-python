from typing import Generic, Protocol
from typing_extensions import TypeVar


T_DecodedPayload = TypeVar("T_DecodedPayload", covariant=True)
T_EncodedPayload = TypeVar("T_EncodedPayload", covariant=True, default=bytes)


class Codec(Protocol, Generic[T_DecodedPayload, T_EncodedPayload]):
    def encode(payload: T_DecodedPayload) -> T_EncodedPayload: ...

    def decode(payload: T_EncodedPayload) -> T_DecodedPayload: ...
