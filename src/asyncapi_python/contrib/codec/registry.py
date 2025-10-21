from types import ModuleType
from typing import Any, ClassVar

from asyncapi_python.kernel.codec import Codec, CodecFactory
from asyncapi_python.kernel.document.message import Message

from .json import JsonCodecFactory


class CodecRegistry(CodecFactory[Any, Any]):
    """A registry-based codec factory that routes messages to appropriate codecs by content type.

    This factory maintains a class-level registry of codec factories mapped to content types,
    and creates codec instances on demand. It supports fallback to a default codec when
    no specific codec is registered for a content type.

    Example:
        >>> # Register codec factories for different content types
        >>> CodecRegistry.register("application/json", JsonCodecFactory)
        >>> CodecRegistry.register("application/xml", XmlCodecFactory)
        >>>
        >>> # Create registry instance and use it
        >>> registry = CodecRegistry(my_module)
        >>> codec = registry.create(json_message)  # Returns JSON codec
        >>> codec = registry.create(xml_message)   # Returns XML codec
    """

    _registry: ClassVar[dict[str | None, type[CodecFactory[Any, Any]]]] = {}
    """Class-level registry mapping content types to codec factory classes."""

    def __init__(self, module: ModuleType) -> None:
        """Initialize the codec registry.

        Args:
            module: The root module containing generated message classes.
        """
        super().__init__(module)
        self._codecs: dict[str | None, CodecFactory[Any, Any]] = {}

    @classmethod
    def register(
        cls, content_type: str | None, codec_factory: type[CodecFactory[Any, Any]], /
    ) -> None:
        """Register a codec factory for a specific content type.

        Args:
            content_type: The MIME content type (e.g., "application/json") or None for default.
            codec_factory: The codec factory class to use for this content type.

        Example:
            >>> CodecRegistry.register("application/json", JsonCodecFactory)
            >>> CodecRegistry.register(None, JsonCodecFactory)  # Default fallback
        """
        cls._registry[content_type] = codec_factory

    def create(self, message: Message) -> Codec[Any, Any]:
        """Creates codec instance from the message specification.

        Looks up the appropriate codec factory based on the message's content type,
        creates and caches codec factory instances, then delegates codec creation
        to the specific factory.

        Args:
            message: The AsyncAPI message specification containing content type info.

        Returns:
            A codec instance capable of encoding/decoding the message.

        Raises:
            ValueError: If no codec is registered for the message's content type
                       and no default codec is available.

        Example:
            >>> message = Message(content_type="application/json", ...)
            >>> codec = registry.create(message)
            >>> encoded = codec.encode(my_data)
        """
        content_type = message.content_type

        # Get or create codec instance for this content type
        if content_type not in self._codecs:
            codec_factory_class = self._registry.get(content_type)
            if codec_factory_class is None:
                # Fallback to default (None) content type
                codec_factory_class = self._registry.get(None)
                if codec_factory_class is None:
                    raise ValueError(
                        f"No codec registered for content type: {content_type}"
                    )

            self._codecs[content_type] = codec_factory_class(self._module)

        return self._codecs[content_type].create(message)


CodecRegistry.register(None, JsonCodecFactory)
CodecRegistry.register("application/json", JsonCodecFactory)
