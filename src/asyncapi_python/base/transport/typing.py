from typing import AsyncGenerator, Generic, Protocol, TypeVar


class Message(Protocol):
    @property
    def payload(self) -> bytes:
        """Payload of the message"""

    @property
    def headers(self) -> dict[str, str]:
        """Message headers"""


class IncomingMessage(Message, Protocol):
    async def ack(self) -> None:
        """Processing of the message successful"""

    async def nack(self) -> None:
        """Processing of the message failed due to app internal reason"""

    async def reject(self) -> None:
        """Processing of the message failed due to external reasons (e.g. protocol validation)"""


T_Send = TypeVar("T_Send", bound=Message)


T_Recv = TypeVar("T_Recv", covariant=True, bound=IncomingMessage)


class Panic(Protocol):
    async def panic(self) -> None:
        """Signals unrecoverable error. Receiving side must call its background tasks and terminate them"""


class Producer(Protocol, Panic, Generic[T_Send]):
    async def send_batch(self, messages: list[T_Send]) -> None:
        """Sends batch of messages to channel"""


class Consumer(Protocol, Panic, Generic[T_Recv]):
    def recv(self) -> AsyncGenerator[T_Recv, None]:
        """Starts streaming incoming messages"""
