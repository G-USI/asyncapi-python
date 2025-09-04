"""AsyncAPI binding classes for various protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, Union
from enum import Enum


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


@dataclass
class AmqpQueue:
    """AMQP queue configuration."""
    name: Optional[str] = None
    durable: Optional[bool] = None
    exclusive: Optional[bool] = None
    auto_delete: Optional[bool] = None
    vhost: Optional[str] = None


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
    extensions: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate binding configuration after initialization."""
        if self.type == "queue" and not self.queue:
            # Default queue configuration
            self.queue = AmqpQueue()
        elif self.type == "routingKey" and not self.exchange:
            # Default exchange configuration
            self.exchange = AmqpExchange()


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
    extensions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AmqpMessageBinding:
    """AMQP message binding following AsyncAPI specification."""
    
    # Message properties
    content_encoding: Optional[str] = None
    message_type: Optional[str] = None
    
    # Version information
    binding_version: str = "0.3.0"
    
    # Extension fields
    extensions: Dict[str, Any] = field(default_factory=dict)


def create_amqp_binding_from_dict(binding_dict: Dict[str, Any]) -> AmqpChannelBinding:
    """Create an AmqpChannelBinding from a dictionary.
    
    This helper function converts the dictionary format used in generated code
    to the proper binding object structure expected by the resolver.
    """
    if not binding_dict or "type" not in binding_dict:
        raise ValueError("Invalid AMQP binding: missing type field")
    
    binding_type = binding_dict["type"]
    
    # Create the binding based on type
    binding = AmqpChannelBinding(type=binding_type)
    
    if binding_type == "queue" and "queue" in binding_dict:
        queue_config = binding_dict["queue"]
        binding.queue = AmqpQueue(
            name=queue_config.get("name"),
            durable=queue_config.get("durable"),
            exclusive=queue_config.get("exclusive"),
            auto_delete=queue_config.get("auto_delete"),
            vhost=queue_config.get("vhost")
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
            vhost=exchange_config.get("vhost")
        )
    
    return binding