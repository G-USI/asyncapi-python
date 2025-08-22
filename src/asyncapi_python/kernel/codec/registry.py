"""Codec registry and factory implementation"""

from typing import Type, Optional
from ..document import Message as AsyncAPIMessage
from .abc import AbstractCodec
from .exceptions import CodecNotFoundError


class CodecRegistry:
    """
    Registry for message codecs with factory pattern.
    
    Manages codec registration and selection based on content type.
    """
    
    def __init__(self):
        """Initialize empty codec registry"""
        self._codecs: dict[str, Type[AbstractCodec]] = {}
        self._instances: dict[str, AbstractCodec] = {}
    
    def register(self, content_type: str, codec_class: Type[AbstractCodec]) -> None:
        """
        Register a codec class for a specific content type.
        
        Args:
            content_type: MIME type (e.g., "application/json")
            codec_class: AbstractCodec subclass to register
        """
        self._codecs[content_type] = codec_class
        # Clear cached instance if exists
        self._instances.pop(content_type, None)
    
    def unregister(self, content_type: str) -> None:
        """
        Remove a codec from the registry.
        
        Args:
            content_type: MIME type to unregister
        """
        self._codecs.pop(content_type, None)
        self._instances.pop(content_type, None)
    
    def get_codec(self, message: AsyncAPIMessage) -> AbstractCodec:
        """
        Factory method - returns appropriate codec for message.
        
        Args:
            message: AsyncAPI message specification
            
        Returns:
            Codec instance for the message's content type
            
        Raises:
            CodecNotFoundError: If no codec registered for content type
        """
        content_type = message.content_type or "application/json"
        return self.get_codec_by_type(content_type)
    
    def get_codec_by_type(self, content_type: str) -> AbstractCodec:
        """
        Get codec by explicit content type.
        
        Args:
            content_type: MIME type
            
        Returns:
            Codec instance for the content type
            
        Raises:
            CodecNotFoundError: If no codec registered for content type
        """
        # Lazy instantiation with caching
        if content_type not in self._instances:
            if content_type not in self._codecs:
                raise CodecNotFoundError(
                    f"No codec registered for content type: {content_type}. "
                    f"Available types: {list(self._codecs.keys())}"
                )
            self._instances[content_type] = self._codecs[content_type]()
        
        return self._instances[content_type]
    
    def list_content_types(self) -> list[str]:
        """
        List all registered content types.
        
        Returns:
            List of MIME types with registered codecs
        """
        return list(self._codecs.keys())
    
    def clear(self) -> None:
        """Clear all registered codecs and cached instances"""
        self._codecs.clear()
        self._instances.clear()


# Global default registry instance
default_registry = CodecRegistry()