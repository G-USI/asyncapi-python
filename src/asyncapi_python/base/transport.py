from typing import AsyncGenerator, Generic, TypeVar
from abc import abstractmethod, ABC
from .document import Channel


T_Send = TypeVar("T_Send")
T_SendResult = TypeVar("T_SendResult")
T_Recv = TypeVar("T_Recv", covariant=True)


class AbstractProducer(ABC, Generic[T_Send, T_SendResult]):
    @abstractmethod
    async def send_batch(self, messages: list[T_Send]) -> list[T_SendResult]: ...


class AbstractConsumer(ABC, Generic[T_Recv]):
    @abstractmethod
    def start_recv(self) -> AsyncGenerator[T_Recv, None]: ...


class AbstractTransportFactory(ABC, Generic[T_Send, T_SendResult, T_Recv]):
    @abstractmethod
    async def create_consumer(
        self, channel: Channel, parameter_values: dict[str, str]
    ) -> AbstractConsumer[T_Recv]: ...

    @abstractmethod
    async def create_producer(
        self, channel: Channel, parameter_values: dict[str, str]
    ) -> AbstractProducer[T_Send, T_SendResult]: ...
