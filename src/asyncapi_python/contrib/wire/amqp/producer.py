"""AMQP producer implementation"""

from typing import Any

try:
    from aio_pika import ExchangeType
    from aio_pika import Message as AmqpMessage  # type: ignore[import-not-found]
    from aio_pika.abc import (  # type: ignore[import-not-found]
        AbstractChannel,
        AbstractConnection,
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
        arguments: dict[str, Any] | None = None,
    ):
        self._connection = connection
        self._queue_name = queue_name
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self._routing_key = routing_key
        self._queue_properties = queue_properties or {}
        self._arguments = arguments or {}
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
                        arguments=self._arguments,
                    )

            # Named exchange patterns
            case (exchange_name, "direct"):
                self._target_exchange = await self._channel.declare_exchange(
                    name=exchange_name,
                    type=ExchangeType.DIRECT,
                    durable=True,
                    arguments=self._arguments,
                )

            case (exchange_name, "topic"):
                self._target_exchange = await self._channel.declare_exchange(
                    name=exchange_name,
                    type=ExchangeType.TOPIC,
                    durable=True,
                    arguments=self._arguments,
                )

            case (exchange_name, "fanout"):
                self._target_exchange = await self._channel.declare_exchange(
                    name=exchange_name,
                    type=ExchangeType.FANOUT,
                    durable=True,
                    arguments=self._arguments,
                )

            case (exchange_name, "headers"):
                self._target_exchange = await self._channel.declare_exchange(
                    name=exchange_name,
                    type=ExchangeType.HEADERS,
                    durable=True,
                    arguments=self._arguments,
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

    async def send_batch(
        self, messages: list[AmqpWireMessage], *, address_override: str | None = None
    ) -> None:
        """Send a batch of messages using the configured exchange

        Args:
            messages: Messages to send
            address_override: Optional dynamic routing key/queue to override static config.
                            If provided, overrides self._routing_key for this send operation.
                            If None, uses static routing_key from configuration/bindings.
        """
        if not self._started or not self._channel or not self._target_exchange:
            raise RuntimeError("Producer not started")

        # Determine effective routing key: override takes precedence over static config
        effective_routing_key = (
            address_override if address_override is not None else self._routing_key
        )

        # Validate we have a destination
        # Fail ONLY if both are truly missing:
        # - address_override is None (not provided by caller)
        # - AND self._routing_key is "" (no static config was derived from channel/bindings/operation)
        # Note: empty string IS valid when explicitly configured (fanout exchanges, default exchange)
        if address_override is None and not self._routing_key:
            raise ValueError(
                f"Cannot send: no routing destination available. "
                f"RPC replies require reply_to from the request, or the channel must "
                f"have address/bindings/operation-name to derive destination. "
                f"(address_override={address_override}, routing_key={self._routing_key!r})"
            )

        for message in messages:
            amqp_message = AmqpMessage(
                body=message.payload,
                headers=message.headers,
                correlation_id=message.correlation_id,
                reply_to=message.reply_to,
            )

            # Publish to the configured target exchange with dynamic or static routing key
            await self._target_exchange.publish(
                amqp_message,
                routing_key=effective_routing_key,
            )
