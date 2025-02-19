# Copyright 2025 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
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


from abc import abstractmethod
from typing import (
    Any,
    Awaitable,
    Callable,
    TypeVar,
    Union,
)
from uuid import uuid4

from pydantic import BaseModel
from .base import AbstractEndpoint, Encoder, Decoder
from ..connection import AmqpPool
from ..operation import Operation
from aio_pika.abc import AbstractIncomingMessage
from aio_pika import Message


I = TypeVar("I", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)
O = TypeVar("O", bound=Union[BaseModel, None])


class AbstractSender(AbstractEndpoint[I, O]):
    def __init__(self, op: Operation[I, O], pool: AmqpPool, encoder: Encoder):
        super().__init__(op, pool)
        self._encoder = encoder

    async def start(self): ...

    @abstractmethod
    async def __call__(self, message: I) -> O:
        raise NotImplementedError

    async def validate_and_call(self, message: Any) -> O:
        return await self(self._op.message_type.model_validate(message))

    async def validate_json_and_call(self, message: Union[str, bytes, bytearray]) -> O:
        return await self(self._op.message_type.model_validate_json(message))


class Sender(AbstractSender[I, None]):
    async def __call__(self, message: I) -> None:
        ex_n = self._op.exchange_name or ""
        q_n = self._op.routing_key or ""
        body = self._encoder(message)
        async with self._pool.acquire() as ch:
            ex = await ch.get_exchange(ex_n)
            await ex.publish(Message(body), q_n)


class RpcSender(AbstractSender[I, U]):
    def __init__(
        self,
        op: Operation[I, U],
        pool: AmqpPool,
        encoder: Encoder,
        decoder: Decoder[U],
        await_corr_id: Callable[[str], Awaitable[AbstractIncomingMessage]],
        reply_to: str,
    ):
        super().__init__(op, pool, encoder)
        self._decoder = decoder
        self._await_corr_id = await_corr_id
        self._reply_to = reply_to

    async def __call__(self, message: I) -> U:
        corr_id = str(uuid4())
        ex_n = self._op.exchange_name or ""
        q_n = self._op.routing_key or ""
        body = self._encoder(message)
        async with self._pool.acquire() as ch:
            ex = await ch.get_exchange(ex_n)
            await ex.publish(
                Message(
                    body,
                    reply_to=self._reply_to,
                    correlation_id=corr_id,
                ),
                q_n,
            )
        res = await self._await_corr_id(corr_id)
        return self._decoder(res.body, self._op.reply_type)
