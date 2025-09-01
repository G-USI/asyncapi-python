"""AMQP wire implementation using aio-pika"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator
from typing_extensions import Unpack

from aio_pika import connect_robust, Message as AmqpMessage
from aio_pika.abc import (
    AbstractRobustConnection,
    AbstractRobustChannel,
    AbstractRobustQueue,
    AbstractIncomingMessage,
)

from asyncapi_python.kernel.wire import AbstractWireFactory, EndpointParams
from asyncapi_python.kernel.wire.typing import Producer, Consumer


@dataclass
class AmqpWireMessage:
    """AMQP wire message implementation"""
    _payload: bytes
    _headers: dict[str, Any] = field(default_factory=dict)
    _correlation_id: str | None = None
    _reply_to: str | None = None

    @property
    def payload(self) -> bytes:
        return self._payload

    @property
    def headers(self) -> dict[str, Any]:
        return self._headers

    @property
    def correlation_id(self) -> str | None:
        return self._correlation_id

    @property
    def reply_to(self) -> str | None:
        return self._reply_to


@dataclass
class AmqpIncomingMessage(AmqpWireMessage):
    """AMQP incoming message with ack/nack/reject support"""
    _amqp_message: AbstractIncomingMessage = field(repr=False, default=None)

    async def ack(self) -> None:
        """Acknowledge message processing"""
        await self._amqp_message.ack()

    async def nack(self, requeue: bool = True) -> None:
        """Negative acknowledge message"""
        await self._amqp_message.nack(requeue=requeue)

    async def reject(self, requeue: bool = False) -> None:
        """Reject message"""
        await self._amqp_message.reject(requeue=requeue)


class AmqpProducer(Producer[AmqpWireMessage]):
    """AMQP producer implementation"""

    def __init__(
        self,
        connection: AbstractRobustConnection,
        channel_name: str,
        exchange_name: str = "",
        routing_key: str | None = None,
    ):
        self._connection = connection
        self._channel_name = channel_name
        self._exchange_name = exchange_name
        self._routing_key = routing_key or channel_name
        self._channel: AbstractRobustChannel | None = None
        self._started = False

    async def start(self) -> None:
        """Start the producer"""
        if self._started:
            return

        self._channel = await self._connection.channel()
        
        # Declare exchange if specified
        if self._exchange_name:
            await self._channel.declare_exchange(
                self._exchange_name, durable=True
            )
        
        # Declare queue if not using default exchange
        if not self._exchange_name:
            await self._channel.declare_queue(
                self._channel_name, durable=True
            )

        self._started = True

    async def stop(self) -> None:
        """Stop the producer"""
        if not self._started:
            return

        if self._channel:
            await self._channel.close()
            self._channel = None

        self._started = False

    async def send_batch(self, messages: list[AmqpWireMessage]) -> None:
        """Send a batch of messages"""
        if not self._started or not self._channel:
            raise RuntimeError("Producer not started")

        for message in messages:
            amqp_message = AmqpMessage(
                body=message.payload,
                headers=message.headers,
                correlation_id=message.correlation_id,
                reply_to=message.reply_to,
            )

            await self._channel.default_exchange.publish(
                amqp_message,
                routing_key=self._routing_key,
            )


class AmqpConsumer(Consumer[AmqpIncomingMessage]):
    """AMQP consumer implementation"""

    def __init__(
        self,
        connection: AbstractRobustConnection,
        channel_name: str,
        is_reply: bool = False,
        app_id: str | None = None,
    ):
        self._connection = connection
        self._channel_name = channel_name
        self._is_reply = is_reply
        self._app_id = app_id
        self._channel: AbstractRobustChannel | None = None
        self._queue: AbstractRobustQueue | None = None
        self._started = False
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the consumer"""
        if self._started:
            return

        self._channel = await self._connection.channel()
        
        # Handle reply queue logic
        if self._is_reply:
            if self._channel_name is None:
                # Global reply queue for app_id
                queue_name = f"reply-queue-{self._app_id or 'global'}"
                self._queue = await self._channel.declare_queue(
                    queue_name, durable=True, exclusive=False
                )
            else:
                # Specific reply queue name provided
                self._queue = await self._channel.declare_queue(
                    self._channel_name, durable=True, exclusive=False
                )
        else:
            # Regular queue
            self._queue = await self._channel.declare_queue(
                self._channel_name, durable=True
            )

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


class AmqpWireFactory(AbstractWireFactory[AmqpWireMessage, AmqpIncomingMessage]):
    """AMQP wire factory implementation"""

    def __init__(
        self,
        connection_url: str,
        app_id: str | None = None,
    ):
        self._connection_url = connection_url
        self._app_id = app_id
        self._connection: AbstractRobustConnection | None = None

    async def _get_connection(self) -> AbstractRobustConnection:
        """Get or create connection"""
        if self._connection is None or self._connection.is_closed:
            self._connection = await connect_robust(self._connection_url)
        return self._connection

    async def create_consumer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Consumer[AmqpIncomingMessage]:
        """Create an AMQP consumer"""
        channel = kwargs["channel"]
        is_reply = kwargs["is_reply"]
        
        connection = await self._get_connection()
        
        # For reply channels, null address means use global reply queue
        channel_name = channel.address if not is_reply or channel.address is not None else None
        
        return AmqpConsumer(
            connection=connection,
            channel_name=channel_name,
            is_reply=is_reply,
            app_id=self._app_id,
        )

    async def create_producer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Producer[AmqpWireMessage]:
        """Create an AMQP producer"""
        channel = kwargs["channel"]
        
        connection = await self._get_connection()
        
        return AmqpProducer(
            connection=connection,
            channel_name=channel.address or "default",
        )

    async def close(self) -> None:
        """Close the connection"""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()