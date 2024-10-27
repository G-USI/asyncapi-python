from pydantic import RootModel, BaseModel, ConfigDict
from typing import Literal
from aio_pika.abc import AbstractRobustChannel
from .message_handler import AbstractMessageHandler


class ExchangeHandlerParams(BaseModel):
    kind: Literal["exchange"]
    name: str
    routing_key: str


class QueueHandlerParams(BaseModel):
    kind: Literal["queue"]
    name: str


class MessageHandlerParams(RootModel):
    model_config = ConfigDict(frozen=True)
    root: QueueHandlerParams | ExchangeHandlerParams

    async def setup_consume(
        self,
        handler: AbstractMessageHandler,
        channel: AbstractRobustChannel,
    ):
        match self.root:
            case ExchangeHandlerParams(name, routing_key):
                exchange = await channel.declare_exchange(name)
                queue = await channel.declare_queue(exclusive=True)
                await queue.bind(exchange, routing_key)
            case QueueHandlerParams(name):
                queue = await channel.declare_queue(name)
            case _:
                raise NotImplementedError
        await queue.consume(handler)
