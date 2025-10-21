"""In-memory wire implementation for testing purposes"""

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from typing_extensions import Unpack

from asyncapi_python.kernel.wire import AbstractWireFactory, EndpointParams
from asyncapi_python.kernel.wire.typing import Consumer, Producer


@dataclass
class InMemoryMessage:
    """In-memory implementation of Message protocol"""

    _payload: bytes
    _headers: dict[str, Any] = field(default_factory=lambda: {})
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
class InMemoryIncomingMessage(InMemoryMessage):
    """In-memory implementation of IncomingMessage protocol with ack/nack/reject"""

    _acked: bool = field(default=False, init=False)
    _nacked: bool = field(default=False, init=False)
    _rejected: bool = field(default=False, init=False)

    async def ack(self) -> None:
        """Mark message as successfully processed"""
        self._acked = True

    async def nack(self) -> None:
        """Mark message as failed due to app internal reason"""
        self._nacked = True

    async def reject(self) -> None:
        """Mark message as failed due to external reasons"""
        self._rejected = True

    @property
    def is_acknowledged(self) -> bool:
        """Check if message was acknowledged"""
        return self._acked

    @property
    def is_nacked(self) -> bool:
        """Check if message was nacked"""
        return self._nacked

    @property
    def is_rejected(self) -> bool:
        """Check if message was rejected"""
        return self._rejected


class InMemoryBus:
    """Central message bus for in-memory wire communication"""

    def __init__(self) -> None:
        # Channel name -> queue of messages
        self._channels: dict[str, deque[InMemoryIncomingMessage]] = defaultdict(deque)
        # Active consumers per channel
        self._consumers: dict[str, list["InMemoryConsumer"]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, channel_name: str, message: InMemoryMessage) -> None:
        """Publish a message to a channel"""
        async with self._lock:
            # Convert to incoming message for consumers
            incoming_msg = InMemoryIncomingMessage(
                _payload=message.payload,
                _headers=message.headers.copy(),
                _correlation_id=message.correlation_id,
                _reply_to=message.reply_to,
            )

            # Add to channel queue
            self._channels[channel_name].append(incoming_msg)

            # Notify all consumers on this channel
            for consumer in self._consumers[channel_name]:
                consumer._notify_new_message()  # type: ignore[reportPrivateUsage]

    async def subscribe(self, channel_name: str, consumer: "InMemoryConsumer") -> None:
        """Subscribe a consumer to a channel"""
        async with self._lock:
            if consumer not in self._consumers[channel_name]:
                self._consumers[channel_name].append(consumer)

    async def unsubscribe(
        self, channel_name: str, consumer: "InMemoryConsumer"
    ) -> None:
        """Unsubscribe a consumer from a channel"""
        async with self._lock:
            if consumer in self._consumers[channel_name]:
                self._consumers[channel_name].remove(consumer)

    async def get_message(self, channel_name: str) -> InMemoryIncomingMessage | None:
        """Get next message from channel (FIFO)"""
        async with self._lock:
            channel_queue = self._channels[channel_name]
            if channel_queue:
                return channel_queue.popleft()
            return None


# Global message bus instance for testing
_bus = InMemoryBus()


class InMemoryProducer(Producer[InMemoryMessage]):
    """In-memory producer implementation"""

    def __init__(self, channel_name: str):
        self._channel_name = channel_name
        self._started = False

    async def start(self) -> None:
        """Start the producer"""
        self._started = True

    async def stop(self) -> None:
        """Stop the producer"""
        self._started = False

    async def send_batch(
        self, messages: list[InMemoryMessage], *, address_override: str | None = None
    ) -> None:
        """Send a batch of messages to the channel

        Args:
            messages: Messages to send
            address_override: Optional dynamic channel name to override static config.
                            If provided, overrides self._channel_name for this send operation.
                            If None, uses static channel_name from configuration.
        """
        if not self._started:
            raise RuntimeError("Producer not started")

        # Determine effective channel: override takes precedence over static config
        effective_channel = (
            address_override if address_override is not None else self._channel_name
        )

        # Validate we have a destination
        if not effective_channel:
            raise ValueError(
                f"Cannot send: no channel specified. "
                f"address_override={address_override}, channel_name={self._channel_name}"
            )

        for message in messages:
            await _bus.publish(effective_channel, message)


class InMemoryConsumer(Consumer[InMemoryIncomingMessage]):
    """In-memory consumer implementation"""

    def __init__(self, channel_name: str):
        self._channel_name = channel_name
        self._started = False
        self._message_event = asyncio.Event()
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the consumer"""
        self._started = True
        await _bus.subscribe(self._channel_name, self)

    async def stop(self) -> None:
        """Stop the consumer"""
        self._started = False
        self._stop_event.set()
        await _bus.unsubscribe(self._channel_name, self)

    def _notify_new_message(self) -> None:
        """Internal method called by bus when new message arrives"""
        self._message_event.set()

    def recv(self) -> AsyncGenerator[InMemoryIncomingMessage, None]:
        """Async generator that yields incoming messages"""
        return self._message_generator()

    async def _message_generator(self) -> AsyncGenerator[InMemoryIncomingMessage, None]:
        """Internal async generator for messages"""
        if not self._started:
            raise RuntimeError("Consumer not started")

        while self._started and not self._stop_event.is_set():
            # Try to get a message
            message = await _bus.get_message(self._channel_name)
            if message:
                yield message
                continue

            # No message available, wait for notification or stop
            try:
                await asyncio.wait_for(
                    self._message_event.wait(),
                    timeout=0.1,  # Small timeout to check stop condition
                )
                self._message_event.clear()
            except asyncio.TimeoutError:
                continue


class InMemoryWire(AbstractWireFactory[InMemoryMessage, InMemoryIncomingMessage]):
    """In-memory wire factory for testing"""

    async def create_consumer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Consumer[InMemoryIncomingMessage]:
        """Create an in-memory consumer"""
        channel = kwargs["channel"]
        return InMemoryConsumer(channel.address or "default")

    async def create_producer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Producer[InMemoryMessage]:
        """Create an in-memory producer"""
        channel = kwargs["channel"]
        return InMemoryProducer(channel.address or "default")


def get_bus() -> InMemoryBus:
    """Get the global in-memory message bus for testing"""
    return _bus


def reset_bus() -> None:
    """Reset the global message bus (useful between tests)"""
    global _bus
    _bus = InMemoryBus()
