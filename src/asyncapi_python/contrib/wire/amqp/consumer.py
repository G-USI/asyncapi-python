"""AMQP consumer implementation"""

import asyncio
from typing import Any, AsyncGenerator

try:
    from aio_pika import ExchangeType  # type: ignore[import-not-found]
    from aio_pika.abc import (  # type: ignore[import-not-found]
        AbstractChannel,
        AbstractConnection,
        AbstractExchange,
        AbstractQueue,
    )
except ImportError as e:
    raise ImportError(
        "aio-pika is required for AMQP support. "
        "Install with: pip install asyncapi-python[amqp]"
    ) from e

from asyncapi_python.kernel.wire.typing import Consumer

from .config import AmqpBindingType
from .message import AmqpIncomingMessage


class AmqpConsumer(Consumer[AmqpIncomingMessage]):
    """AMQP consumer implementation with comprehensive binding support"""

    def __init__(
        self,
        connection: AbstractConnection,
        queue_name: str,
        exchange_name: str = "",
        exchange_type: str = "direct",
        routing_key: str = "",
        binding_type: AmqpBindingType = AmqpBindingType.QUEUE,
        queue_properties: dict[str, Any] | None = None,
        binding_arguments: dict[str, Any] | None = None,
        arguments: dict[str, Any] | None = None,
    ):
        self._connection = connection
        self._queue_name = queue_name
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self._routing_key = routing_key
        self._binding_type = binding_type
        self._queue_properties = queue_properties or {}
        self._binding_arguments = binding_arguments or {}
        self._arguments = arguments or {}
        self._channel: AbstractChannel | None = None
        self._queue: AbstractQueue | None = None
        self._exchange: AbstractExchange | None = None
        self._started = False
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the consumer with pattern matching for binding types"""
        if self._started:
            return

        self._channel = await self._connection.channel()

        # Pattern matching for queue setup based on binding type
        match self._binding_type:
            # Reply channel pattern
            case AmqpBindingType.REPLY:
                self._queue = await self._channel.declare_queue(
                    name=self._queue_name,
                    durable=self._queue_properties.get("durable", True),
                    exclusive=self._queue_properties.get("exclusive", False),
                    auto_delete=self._queue_properties.get("auto_delete", False),
                    arguments=self._arguments,
                )

            # Simple queue binding pattern (default exchange)
            case AmqpBindingType.QUEUE:
                self._queue = await self._channel.declare_queue(
                    name=self._queue_name,
                    durable=self._queue_properties.get("durable", True),
                    exclusive=self._queue_properties.get("exclusive", False),
                    auto_delete=self._queue_properties.get("auto_delete", False),
                    arguments=self._arguments,
                )

            # Routing key binding pattern (pub/sub with named exchange)
            case AmqpBindingType.ROUTING_KEY:
                # Declare the exchange
                match self._exchange_type:
                    case "direct":
                        self._exchange = await self._channel.declare_exchange(
                            name=self._exchange_name,
                            type=ExchangeType.DIRECT,
                            durable=True,
                            arguments=self._arguments,
                        )
                    case "topic":
                        self._exchange = await self._channel.declare_exchange(
                            name=self._exchange_name,
                            type=ExchangeType.TOPIC,
                            durable=True,
                            arguments=self._arguments,
                        )
                    case "fanout":
                        self._exchange = await self._channel.declare_exchange(
                            name=self._exchange_name,
                            type=ExchangeType.FANOUT,
                            durable=True,
                            arguments=self._arguments,
                        )
                    case "headers":
                        self._exchange = await self._channel.declare_exchange(
                            name=self._exchange_name,
                            type=ExchangeType.HEADERS,
                            durable=True,
                            arguments=self._arguments,
                        )
                    case unknown_type:
                        raise ValueError(f"Unsupported exchange type: {unknown_type}")

                # Create exclusive queue for this consumer
                self._queue = await self._channel.declare_queue(
                    name="",  # Auto-generated name
                    durable=self._queue_properties.get("durable", False),
                    exclusive=self._queue_properties.get("exclusive", True),
                    auto_delete=self._queue_properties.get("auto_delete", True),
                    arguments=self._arguments,
                )

                # Bind queue to exchange with routing key
                await self._queue.bind(self._exchange, routing_key=self._routing_key)

            # Exchange binding pattern (advanced pub/sub with binding arguments)
            case AmqpBindingType.EXCHANGE:
                # Declare the exchange
                match self._exchange_type:
                    case "fanout":
                        self._exchange = await self._channel.declare_exchange(
                            name=self._exchange_name,
                            type=ExchangeType.FANOUT,
                            durable=True,
                            arguments=self._arguments,
                        )
                    case "headers":
                        self._exchange = await self._channel.declare_exchange(
                            name=self._exchange_name,
                            type=ExchangeType.HEADERS,
                            durable=True,
                            arguments=self._arguments,
                        )
                    case "topic":
                        self._exchange = await self._channel.declare_exchange(
                            name=self._exchange_name,
                            type=ExchangeType.TOPIC,
                            durable=True,
                            arguments=self._arguments,
                        )
                    case "direct":
                        self._exchange = await self._channel.declare_exchange(
                            name=self._exchange_name,
                            type=ExchangeType.DIRECT,
                            durable=True,
                            arguments=self._arguments,
                        )
                    case unknown_type:
                        raise ValueError(f"Unsupported exchange type: {unknown_type}")

                # Create exclusive queue for this consumer
                self._queue = await self._channel.declare_queue(
                    name="",  # Auto-generated name
                    durable=self._queue_properties.get("durable", False),
                    exclusive=self._queue_properties.get("exclusive", True),
                    auto_delete=self._queue_properties.get("auto_delete", True),
                    arguments=self._arguments,
                )

                # Bind queue to exchange with binding arguments (for headers exchange)
                if self._binding_arguments:
                    await self._queue.bind(
                        self._exchange, arguments=self._binding_arguments
                    )
                else:
                    await self._queue.bind(self._exchange)

        self._started = True

    async def stop(self) -> None:
        """Stop the consumer"""
        if not self._started:
            return

        self._stop_event.set()

        if self._channel:
            await self._channel.close()
            self._channel = None
            self._queue = None
            self._exchange = None

        self._started = False

    def recv(self) -> AsyncGenerator[AmqpIncomingMessage, None]:
        """Async generator that yields incoming messages"""
        return self._message_generator()

    async def _message_generator(self) -> AsyncGenerator[AmqpIncomingMessage, None]:
        """Internal async generator for messages"""
        if not self._started or not self._queue:
            raise RuntimeError("Consumer not started")

        async with self._queue.iterator() as queue_iter:
            async for amqp_message in queue_iter:
                if self._stop_event.is_set():
                    break

                # Convert to our message format
                incoming_msg = AmqpIncomingMessage(
                    _payload=amqp_message.body,
                    _headers=dict(amqp_message.headers) if amqp_message.headers else {},
                    _correlation_id=amqp_message.correlation_id,
                    _reply_to=amqp_message.reply_to,
                    _amqp_message=amqp_message,
                )

                yield incoming_msg
