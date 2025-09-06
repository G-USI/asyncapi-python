"""AMQP producer implementation"""

from typing import Any

try:
    from aio_pika import Message as AmqpMessage, ExchangeType  # type: ignore[import-not-found]
    from aio_pika.abc import (  # type: ignore[import-not-found]
        AbstractConnection,
        AbstractChannel,
        AbstractExchange,
    )
except ImportError as e:
    raise ImportError(
        "aio-pika is required for AMQP support. Install with: pip install asyncapi-python[amqp]"
    ) from e

from asyncapi_python.kernel.wire.typing import Producer

from .message import AmqpWireMessage


class AmqpProducer(Producer[AmqpWireMessage]):
    """AMQP producer implementation with comprehensive exchange type support"""

    def __init__(
        self,
        connection: AbstractConnection,
        queue_name: str,
        exchange_name: str = "",
        exchange_type: str = "direct",
        routing_key: str = "",
        queue_properties: dict[str, Any] | None = None,
    ):
        self._connection = connection
        self._queue_name = queue_name
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self._routing_key = routing_key
        self._queue_properties = queue_properties or {}
        self._channel: AbstractChannel | None = None
        self._target_exchange: AbstractExchange | None = None
        self._started = False

    async def start(self) -> None:
        """Start the producer with exchange type pattern matching"""
        if self._started:
            return

        self._channel = await self._connection.channel()

        # Pattern matching for exchange setup based on type
        match (self._exchange_name, self._exchange_type):
            # Default exchange pattern (queue-based routing)
            case ("", _):
                self._target_exchange = self._channel.default_exchange
                # Declare queue for default exchange routing
                if self._queue_name:
                    await self._channel.declare_queue(
                        name=self._queue_name,
                        durable=self._queue_properties.get("durable", True),
                        exclusive=self._queue_properties.get("exclusive", False),
                        auto_delete=self._queue_properties.get("auto_delete", False),
                    )

            # Named exchange patterns
            case (exchange_name, "direct"):
                self._target_exchange = await self._channel.declare_exchange(
                    name=exchange_name, type=ExchangeType.DIRECT, durable=True
                )

            case (exchange_name, "topic"):
                self._target_exchange = await self._channel.declare_exchange(
                    name=exchange_name, type=ExchangeType.TOPIC, durable=True
                )

            case (exchange_name, "fanout"):
                self._target_exchange = await self._channel.declare_exchange(
                    name=exchange_name, type=ExchangeType.FANOUT, durable=True
                )

            case (exchange_name, "headers"):
                self._target_exchange = await self._channel.declare_exchange(
                    name=exchange_name, type=ExchangeType.HEADERS, durable=True
                )

            case (exchange_name, unknown_type):
                raise ValueError(f"Unsupported exchange type: {unknown_type}")

        self._started = True

    async def stop(self) -> None:
        """Stop the producer"""
        if not self._started:
            return

        if self._channel:
            await self._channel.close()
            self._channel = None
            self._target_exchange = None

        self._started = False

    async def send_batch(self, messages: list[AmqpWireMessage]) -> None:
        """Send a batch of messages using the configured exchange"""
        if not self._started or not self._channel or not self._target_exchange:
            raise RuntimeError("Producer not started")

        for message in messages:
            amqp_message = AmqpMessage(
                body=message.payload,
                headers=message.headers,
                correlation_id=message.correlation_id,
                reply_to=message.reply_to,
            )

            # Publish to the configured target exchange (not always default)
            await self._target_exchange.publish(
                amqp_message,
                routing_key=self._routing_key,
            )
