"""AMQP configuration classes and enums"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AmqpBindingType(Enum):
    """Types of AMQP bindings supported"""

    QUEUE = "queue"
    ROUTING_KEY = "routingKey"
    EXCHANGE = "exchange"
    REPLY = "reply"


@dataclass
class AmqpConfig:
    """Resolved AMQP configuration from AsyncAPI bindings and precedence rules"""

    queue_name: str
    exchange_name: str = ""
    exchange_type: str = "direct"
    routing_key: str = ""
    binding_type: AmqpBindingType = AmqpBindingType.QUEUE
    queue_properties: dict[str, Any] = field(default_factory=lambda: {})
    binding_arguments: dict[str, Any] = field(default_factory=lambda: {})
    arguments: dict[str, Any] = field(default_factory=lambda: {})

    def to_producer_args(self) -> dict[str, Any]:
        """Convert to AmqpProducer constructor arguments"""
        return {
            "queue_name": self.queue_name,
            "exchange_name": self.exchange_name,
            "exchange_type": self.exchange_type,
            "routing_key": self.routing_key,
            "queue_properties": self.queue_properties,
            "arguments": self.arguments,
        }

    def to_consumer_args(self) -> dict[str, Any]:
        """Convert to AmqpConsumer constructor arguments"""
        return {
            "queue_name": self.queue_name,
            "exchange_name": self.exchange_name,
            "exchange_type": self.exchange_type,
            "routing_key": self.routing_key,
            "binding_type": self.binding_type,
            "queue_properties": self.queue_properties,
            "binding_arguments": self.binding_arguments,
            "arguments": self.arguments,
        }
