# Copyright 2024 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
