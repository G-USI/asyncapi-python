from abc import ABC, abstractmethod
from typing import Type, TypeVar, Generic
from ..document import Message as AsyncAPIMessage
from .protocols import EncodedMessage

T_Payload = TypeVar("T_Payload")
T_Headers = TypeVar("T_Headers")


class AbstractCodec(ABC, Generic[T_Payload, T_Headers]):
    """
    Abstract base class for message codecs.
    
    Combines encoding, decoding, and validation into a unified interface
    for handling message serialization according to AsyncAPI specifications.
    """
    
    @abstractmethod
    def encode(
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
            
        Raises:
            ValidationError: If payload/headers don't conform to AsyncAPI specification
            EncodingError: If payload/headers cannot be encoded to wire format
        """
    
    @abstractmethod 
    def decode(
        self, 
        encoded: EncodedMessage, 
        payload_type: Type[T_Payload],
        headers_type: Type[T_Headers]
    ) -> tuple[T_Payload, T_Headers]:
        """
        Decode wire format message to typed payload and headers
        
        Args:
            encoded: The encoded message from wire layer
            payload_type: Target payload type to decode into
            headers_type: Target headers type to decode into
            
        Returns:
            Tuple of (decoded_payload, decoded_headers)
            
        Raises:
            ValidationError: If message doesn't match expected schema
            DecodingError: If payload/headers cannot be decoded from wire format
        """
    
    def validate(
        self, 
        payload: T_Payload, 
        headers: T_Headers,
        asyncapi_message: AsyncAPIMessage
    ) -> tuple[T_Payload, T_Headers]:
        """
        Validate payload and headers against AsyncAPI specification
        
        Default implementation performs no validation.
        Override to add custom validation logic.
        
        Args:
            payload: Payload to validate
            headers: Headers to validate
            asyncapi_message: AsyncAPI message specification
            
        Returns:
            Tuple of (validated_payload, validated_headers) - may be modified/normalized
            
        Raises:
            ValidationError: If payload/headers don't conform to specification
        """
        return payload, headers