from typing import AsyncGenerator, Generic, Protocol, TypeVar


class Message(Protocol):
    @property
    def payload(self) -> bytes:
        """Payload of the message"""

    @property
    def headers(self) -> dict[str, str]:
        """Message headers"""

    @property
    def correlation_id(self) -> str | None:
        """AsyncAPI 3.0 correlation ID for RPC request/response matching"""

    @property
    def reply_to(self) -> str | None:
        """AsyncAPI 3.0 reply-to address for dynamic RPC responses"""


class IncomingMessage(Message, Protocol):
    async def ack(self) -> None:
        """Processing of the message successful"""

    async def nack(self) -> None:
        """Processing of the message failed due to app internal reason"""

    async def reject(self) -> None:
        """Processing of the message failed due to external reasons (e.g. protocol validation)"""


T_Send = TypeVar("T_Send", bound=Message)


T_Recv = TypeVar("T_Recv", covariant=True, bound=IncomingMessage)


class EndpointLifecycle(Protocol):
    async def start(self) -> None:
        """Signals application start. Receiving side must start its operation."""

    async def stop(self) -> None:
        """Signals stop to the endpoint. Receiving side must stop its background tasks and terminate self."""


class Producer(Protocol, EndpointLifecycle, Generic[T_Send]):
    async def send_batch(self, messages: list[T_Send]) -> None:
        """Sends batch of messages to channel"""


class Consumer(Protocol, EndpointLifecycle, Generic[T_Recv]):
    def recv(self) -> AsyncGenerator[T_Recv, None]:
        """Starts streaming incoming messages"""
