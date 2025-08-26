from typing import AsyncGenerator, Generic, Protocol

from ..typing import T_Send, T_Recv


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
