from typing import AsyncGenerator, Generic, TypeVar
from abc import abstractmethod, ABC
from ..document import Channel


T_Send = TypeVar("T_Send")
T_SendResult = TypeVar("T_SendResult")
T_Recv = TypeVar("T_Recv", covariant=True)


class Producer(ABC, Generic[T_Send, T_SendResult]):
    @abstractmethod
    async def send_batch(self, messages: list[T_Send]) -> list[T_SendResult]: ...


class Consumer(ABC, Generic[T_Recv]):
    @abstractmethod
    async def start_recv(self) -> AsyncGenerator[T_Recv]: ...


class AbstractTransportFactory(ABC, Generic[T_Send, T_SendResult, T_Recv]):
    @abstractmethod
    async def create_consumer(
        self, channel: Channel, parameter_values: dict[str, str]
    ) -> Consumer[T_Recv]: ...

    @abstractmethod
    async def create_producer(
        self, channel: Channel, parameter_values: dict[str, str]
    ) -> Producer[T_Send, T_SendResult]: ...
