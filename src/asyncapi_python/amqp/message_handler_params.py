from pydantic import RootModel, BaseModel, ConfigDict, computed_field
from typing import Literal
from aio_pika.abc import AbstractRobustChannel
from .message_handler import AbstractMessageHandler


class ExchangeHandlerParams(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["exchange"] = "exchange"
    type: Literal["direct", "fanout", "topic", "headers"]
    name: str
    routing_key: str | None
    auto_delete: bool = False


class QueueHandlerParams(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["queue"] = "queue"
    name: str
    exclusive: bool = False
    auto_delete: bool = False
    durable: bool = False


class MessageHandlerParams(RootModel):
    model_config = ConfigDict(frozen=True)
    root: QueueHandlerParams | ExchangeHandlerParams

    async def setup_consume(
        self,
        handler: AbstractMessageHandler,
        channel: AbstractRobustChannel,
    ):
        match self.root:
            case ExchangeHandlerParams(
                name=name, routing_key=rk, type=et, auto_delete=ad
            ):
                exchange = await channel.declare_exchange(name, type=et, auto_delete=ad)
                queue = await channel.declare_queue(exclusive=True)
                await queue.bind(exchange, rk)
            case QueueHandlerParams(name=name, exclusive=ex, auto_delete=ad, durable=d):
                queue = await channel.declare_queue(
                    name, exclusive=ex, auto_delete=ad, durable=d
                )
            case _:
                raise NotImplementedError
        await queue.consume(handler)
