from abc import ABC
from typing import Awaitable
from typing_extensions import Self
import aio_pika
from aio_pika.robust_connection import AbstractRobustConnection, AbstractRobustChannel
from aio_pika.channel import AbstractChannel, AbstractExchange, AbstractQueue
from aio_pika.message import Message
from pydantic import BaseModel


class BaseClient(ABC):
    @classmethod
    async def create(cls: type[Self], amqp_uri: str) -> Self:
        channel = (await connection(amqp_uri=amqp_uri)).channel()
        return cls(channel=channel)

    async def produce(
        self,
        *,
        message: BaseModel,
        exchange: str | None,
        reply_to: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        ch = await self._channel
        ch.default_exchange.publish(message)

    @property
    def _channel(self) -> Awaitable[AbstractChannel]:
        return self.__channel

    def __init__(self, *, channel: AbstractRobustChannel):
        self.__channel = channel
        self.__exchanges: dict[str, AbstractExchange] = {}
        self.__queues: dict[str, AbstractExchange] = {}

    @staticmethod
    def encode_json(message: BaseModel) -> bytes:
        return message.model_dump_json().encode()

    @staticmethod
    def decode_json(cls: type[BaseModel], message: bytes) -> BaseModel:
        return cls.model_validate_json(message)


GLOBAL_AMQP_CONNECTIONS: dict[str, AbstractRobustConnection] = {}


async def connection(amqp_uri: str) -> AbstractRobustConnection:
    if amqp_uri not in GLOBAL_AMQP_CONNECTIONS:
        GLOBAL_AMQP_CONNECTIONS[amqp_uri] = await aio_pika.connect_robust(amqp_uri)
    return GLOBAL_AMQP_CONNECTIONS[amqp_uri]
