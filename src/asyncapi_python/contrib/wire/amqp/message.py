"""AMQP message classes"""

from dataclasses import dataclass, field
from typing import Any

try:
    from aio_pika.abc import AbstractIncomingMessage  # type: ignore[import-not-found]
except ImportError as e:
    raise ImportError(
        "aio-pika is required for AMQP support. Install with: pip install asyncapi-python[amqp]"
    ) from e


@dataclass
class AmqpWireMessage:
    """AMQP wire message implementation"""

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
class AmqpIncomingMessage(AmqpWireMessage):
    """AMQP incoming message with ack/nack/reject support"""

    _amqp_message: AbstractIncomingMessage | None = field(repr=False, default=None)

    async def ack(self) -> None:
        """Acknowledge message processing"""
        if self._amqp_message:
            await self._amqp_message.ack()

    async def nack(self, requeue: bool = True) -> None:
        """Negative acknowledge message"""
        if self._amqp_message:
            await self._amqp_message.nack(requeue=requeue)

    async def reject(self, requeue: bool = False) -> None:
        """Reject message"""
        if self._amqp_message:
            await self._amqp_message.reject(requeue=requeue)
