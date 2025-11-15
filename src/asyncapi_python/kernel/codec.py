from abc import ABC, abstractmethod
from types import ModuleType
from typing import Generic, Protocol

from asyncapi_python.kernel.document.message import Message

from .typing import T_DecodedPayload, T_EncodedPayload


class Codec(Protocol, Generic[T_DecodedPayload, T_EncodedPayload]):
    def encode(self, payload: T_DecodedPayload) -> T_EncodedPayload: ...

    def decode(self, payload: T_EncodedPayload) -> T_DecodedPayload: ...

    def extract_field(self, payload: T_DecodedPayload, location: str) -> str:
        """Extract field value from decoded payload using location expression.

        Args:
            payload: Decoded payload (Pydantic model, Protobuf object, etc.)
            location: Location expression like "$message.payload#/userId"

        Returns:
            str: Extracted value converted to string

        Raises:
            ValueError: If location path doesn't exist in payload
        """
        ...


class CodecFactory(ABC, Generic[T_DecodedPayload, T_EncodedPayload]):
    """A codec factory

    Args:
        module (ModuleType): a root module where the generated code of the application lies.

    Notes:
        This essentially couples codec factory with the corresponding compiler (options).
        All assumptions regarding message type positioning must be clearly documented.
    """

    def __init__(self, module: ModuleType):
        self._module = module

    @abstractmethod
    def create(self, message: Message) -> Codec[T_DecodedPayload, T_EncodedPayload]:
        """Creates codec instance from the message spec.
        The factory will dynamically import data model object based on the root module and the
        code generated, and will construct a codec implementation for this message.
        """
