from typing import Literal

from pydantic import BaseModel, Field, RootModel


class Exchange(BaseModel):
    name: str = ""
    type: Literal["topic", "direct", "fanout", "default", "headers"] = "default"
    durable: bool = False
    auto_delete: bool = Field(alias="autoDelete", default=False)


class ExchangeBinding(BaseModel):
    type: Literal["routingKey"] = Field(alias="is", default="routingKey")
    exchange: Exchange = Exchange()


class Queue(BaseModel):
    name: str | None = None
    durable: bool = False
    exclusive: bool = False
    auto_delete: bool = Field(alias="autoDelete", default=False)


class QueueBinding(BaseModel):
    type: Literal["queue"] = Field(alias="is", default="queue")
    queue: Queue = Queue()


class AmqpBinding(RootModel):
    root: ExchangeBinding | QueueBinding = QueueBinding()
