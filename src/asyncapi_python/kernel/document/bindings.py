"""AsyncAPI binding classes for various protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Literal, Optional


class AmqpExchangeType(str, Enum):
    """AMQP exchange types."""

    TOPIC = "topic"
    DIRECT = "direct"
    FANOUT = "fanout"
    DEFAULT = "default"
    HEADERS = "headers"


@dataclass
class AmqpExchange:
    """AMQP exchange configuration."""

    name: Optional[str] = None
    type: AmqpExchangeType = AmqpExchangeType.DEFAULT
    durable: Optional[bool] = None
    auto_delete: Optional[bool] = None
    vhost: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None

    def __repr__(self) -> str:
        """Custom repr to handle enum properly for code generation."""
        from asyncapi_python.kernel.document.bindings import AmqpExchangeType

        _ = AmqpExchangeType  # Explicitly reference the import
        return f"spec.AmqpExchange(name={self.name!r}, type=spec.AmqpExchangeType.{self.type.name}, durable={self.durable!r}, auto_delete={self.auto_delete!r}, vhost={self.vhost!r}, arguments={self.arguments!r})"


@dataclass
class AmqpQueue:
    """AMQP queue configuration."""

    name: Optional[str] = None
    durable: Optional[bool] = None
    exclusive: Optional[bool] = None
    auto_delete: Optional[bool] = None
    vhost: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None

    def __repr__(self) -> str:
        """Custom repr for code generation."""
        return f"spec.AmqpQueue(name={self.name!r}, durable={self.durable!r}, exclusive={self.exclusive!r}, auto_delete={self.auto_delete!r}, vhost={self.vhost!r}, arguments={self.arguments!r})"


@dataclass
class AmqpChannelBinding:
    """AMQP channel binding following AsyncAPI specification v0.3.0."""

    # Discriminator field
    type: Literal["queue", "routingKey"]

    # Optional configurations based on type
    queue: Optional[AmqpQueue] = None
    exchange: Optional[AmqpExchange] = None

    # Version information
    binding_version: str = "0.3.0"

    # Extension fields
    extensions: Dict[str, Any] = field(default_factory=lambda: {})

    def __post_init__(self):
        """Validate binding configuration after initialization."""
        if self.type == "queue" and not self.queue:
            # Default queue configuration
            self.queue = AmqpQueue()
        elif self.type == "routingKey" and not self.exchange:
            # Default exchange configuration
            self.exchange = AmqpExchange()

    def __repr__(self) -> str:
        """Custom repr for code generation."""
        return f"spec.AmqpChannelBinding(type={self.type!r}, queue={self.queue!r}, exchange={self.exchange!r}, binding_version={self.binding_version!r}, extensions={self.extensions!r})"


@dataclass
class AmqpOperationBinding:
    """AMQP operation binding following AsyncAPI specification."""

    # Delivery mode and other operation-specific properties
    expiration: Optional[int] = None
    user_id: Optional[str] = None
    cc: Optional[list[str]] = None
    priority: Optional[int] = None
    delivery_mode: Optional[int] = None
    mandatory: Optional[bool] = None
    bcc: Optional[list[str]] = None
    timestamp: Optional[bool] = None
    ack: Optional[bool] = None

    # Version information
    binding_version: str = "0.3.0"

    # Extension fields
    extensions: Dict[str, Any] = field(default_factory=lambda: {})

    def __repr__(self) -> str:
        """Custom repr for code generation."""
        return f"spec.AmqpOperationBinding(expiration={self.expiration!r}, user_id={self.user_id!r}, cc={self.cc!r}, priority={self.priority!r}, delivery_mode={self.delivery_mode!r}, mandatory={self.mandatory!r}, bcc={self.bcc!r}, timestamp={self.timestamp!r}, ack={self.ack!r}, binding_version={self.binding_version!r}, extensions={self.extensions!r})"


@dataclass
class AmqpMessageBinding:
    """AMQP message binding following AsyncAPI specification."""

    # Message properties
    content_encoding: Optional[str] = None
    message_type: Optional[str] = None

    # Version information
    binding_version: str = "0.3.0"

    # Extension fields
    extensions: Dict[str, Any] = field(default_factory=lambda: {})


def create_amqp_binding_from_dict(binding_dict: Dict[str, Any]) -> AmqpChannelBinding:
    """Create an AmqpChannelBinding from a dictionary.

    This helper function converts the dictionary format used in generated code
    to the proper binding object structure expected by the resolver.
    """
    if not binding_dict:
        raise ValueError("Invalid AMQP binding: binding data is empty")

    # Derive binding type from presence of fields
    has_exchange = "exchange" in binding_dict
    has_routing_key = "routingKey" in binding_dict
    has_queue = "queue" in binding_dict

    if has_exchange and has_routing_key:
        raise ValueError(
            "Invalid AMQP binding: both exchange and routingKey are present"
        )
    elif has_queue:
        binding_type: Literal["queue", "routingKey"] = "queue"
    elif has_exchange or has_routing_key:
        binding_type = "routingKey"
    else:
        # Default fallback - assume it's a queue binding
        binding_type = "queue"

    # Create the binding based on type
    binding = AmqpChannelBinding(type=binding_type)

    if binding_type == "queue" and "queue" in binding_dict:
        queue_config = binding_dict["queue"]
        binding.queue = AmqpQueue(
            name=queue_config.get("name"),
            durable=queue_config.get("durable"),
            exclusive=queue_config.get("exclusive"),
            auto_delete=queue_config.get("auto_delete"),
            vhost=queue_config.get("vhost"),
            arguments=queue_config.get("arguments"),
        )
    elif binding_type == "routingKey" and "exchange" in binding_dict:
        exchange_config = binding_dict["exchange"]
        exchange_type = exchange_config.get("type", "default")

        # Convert string to enum
        try:
            enum_type = AmqpExchangeType(exchange_type)
        except ValueError:
            enum_type = AmqpExchangeType.DEFAULT

        binding.exchange = AmqpExchange(
            name=exchange_config.get("name"),
            type=enum_type,
            durable=exchange_config.get("durable"),
            auto_delete=exchange_config.get("auto_delete"),
            vhost=exchange_config.get("vhost"),
            arguments=exchange_config.get("arguments"),
        )

    return binding
