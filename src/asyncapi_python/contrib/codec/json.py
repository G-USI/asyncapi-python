"""JSON codec implementation for encoding/decoding BaseModel messages"""

from dataclasses import dataclass
from typing import Type, Any
from pydantic import BaseModel, ValidationError
from asyncapi_python.kernel.document import Message as AsyncAPIMessage
from asyncapi_python.kernel.codec import AbstractCodec
from asyncapi_python.kernel.codec.protocols import EncodedMessage as EncodedMessageProtocol


@dataclass
class JsonEncodedMessage:
    """Concrete implementation of EncodedMessage for JSON codec"""

    payload: bytes
    headers: dict[str, Any]
    content_type: str | None = "application/json"


class JsonCodec(AbstractCodec[BaseModel, BaseModel]):
    """
    JSON codec for encoding/decoding Pydantic BaseModel instances.

    This codec:
    - Encodes Pydantic models to JSON bytes
    - Decodes JSON bytes back to Pydantic models
    - Validates against model schemas
    - Preserves custom headers as JSON-serializable values
    """

    def encode(
        self, payload: BaseModel, headers: BaseModel, asyncapi_message: AsyncAPIMessage
    ) -> EncodedMessageProtocol:
        """
        Encode Pydantic models to JSON wire format

        Args:
            payload: Pydantic model instance for message body
            headers: Pydantic model instance for message headers
            asyncapi_message: AsyncAPI spec (used for content-type hints)

        Returns:
            JsonEncodedMessage with JSON-serialized payload and headers
        """
        # Validate models first
        validated_payload, validated_headers = self.validate(
            payload, headers, asyncapi_message
        )

        # Encode payload to JSON bytes
        payload_bytes = validated_payload.model_dump_json().encode("utf-8")

        # Convert headers to dict (JSON-serializable)
        headers_dict = validated_headers.model_dump(mode="json")

        # Determine content type from AsyncAPI spec or use default
        content_type = asyncapi_message.content_type or "application/json"

        return JsonEncodedMessage(
            payload=payload_bytes, headers=headers_dict, content_type=content_type
        )

    def decode(
        self,
        encoded: EncodedMessageProtocol,
        payload_type: Type[BaseModel],
        headers_type: Type[BaseModel],
    ) -> tuple[BaseModel, BaseModel]:
        """
        Decode JSON wire format to Pydantic models

        Args:
            encoded: Wire format message with JSON payload
            payload_type: Target Pydantic model class for payload
            headers_type: Target Pydantic model class for headers

        Returns:
            Tuple of (decoded_payload, decoded_headers) as Pydantic instances

        Raises:
            ValidationError: If JSON doesn't match model schemas
            ValueError: If payload is not valid JSON
        """
        # Decode payload from JSON bytes
        try:
            payload = payload_type.model_validate_json(encoded.payload)
        except ValidationError:
            raise  # Re-raise the original Pydantic ValidationError
        except Exception as e:
            raise ValueError(f"Failed to decode JSON payload: {e}")

        # Decode headers from dict
        try:
            headers = headers_type.model_validate(encoded.headers)
        except ValidationError:
            raise  # Re-raise the original Pydantic ValidationError

        return payload, headers

    def validate(
        self, payload: BaseModel, headers: BaseModel, asyncapi_message: AsyncAPIMessage
    ) -> tuple[BaseModel, BaseModel]:
        """
        Validate models against AsyncAPI specification

        Default implementation uses Pydantic's built-in validation.
        Override for custom AsyncAPI schema validation.

        Args:
            payload: Payload model to validate
            headers: Headers model to validate
            asyncapi_message: AsyncAPI message specification

        Returns:
            Validated models (may be normalized by Pydantic)
        """
        # Pydantic models self-validate on construction
        # Re-validate to ensure consistency
        payload_validated = payload.model_validate(payload.model_dump())
        headers_validated = headers.model_validate(headers.model_dump())

        return payload_validated, headers_validated