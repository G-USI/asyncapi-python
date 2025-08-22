from typing import Any, Protocol, TypeVar, Type
from ..document import Message as AsyncAPIMessage

T_Payload = TypeVar("T_Payload")
T_Headers = TypeVar("T_Headers")


class EncodedMessage(Protocol):
    """Protocol for encoded message representation"""

    @property
    def payload(self) -> bytes:
        """Raw message payload bytes"""

    @property
    def headers(self) -> dict[str, Any]:
        """Protocol-specific message headers"""

    @property
    def content_type(self) -> str | None:
        """MIME content type of the message payload"""


class Encoder(Protocol):
    """Callable protocol for encoding messages to wire format"""

    def __call__(
        self, 
        payload: T_Payload, 
        headers: T_Headers,
        asyncapi_message: AsyncAPIMessage
    ) -> EncodedMessage:
        """
        Encode typed payload and headers to wire format

        Args:
            payload: The typed payload object to encode
            headers: The typed headers object to encode
            asyncapi_message: AsyncAPI message specification for encoding hints

        Returns:
            EncodedMessage with serialized payload, headers, and content type
        """


class Decoder(Protocol):
    """Callable protocol for decoding messages from wire format"""

    def __call__(
        self, 
        encoded: EncodedMessage, 
        payload_type: Type[T_Payload],
        headers_type: Type[T_Headers]
    ) -> tuple[T_Payload, T_Headers]:
        """
        Decode wire format message to typed payload and headers

        Args:
            encoded: The encoded message from transport layer
            payload_type: Target payload type to decode into
            headers_type: Target headers type to decode into

        Returns:
            Tuple of (decoded_payload, decoded_headers)

        Raises:
            ValidationError: If message doesn't match expected schema
            DecodingError: If payload/headers cannot be decoded from wire format
        """


class Validator(Protocol):
    """Callable protocol for message validation"""

    def __call__(
        self, 
        payload: T_Payload, 
        headers: T_Headers,
        asyncapi_message: AsyncAPIMessage
    ) -> tuple[T_Payload, T_Headers]:
        """
        Validate payload and headers against AsyncAPI specification

        Args:
            payload: Payload to validate
            headers: Headers to validate
            asyncapi_message: AsyncAPI message specification

        Returns:
            Tuple of (validated_payload, validated_headers) - may be modified/normalized

        Raises:
            ValidationError: If payload/headers don't conform to specification
        """
