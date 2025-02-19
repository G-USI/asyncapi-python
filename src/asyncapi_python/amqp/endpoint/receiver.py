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
    Optional,
    TypeVar,
    Union,
    cast,
)

from pydantic import BaseModel
from .base import AbstractEndpoint, Encoder, Decoder, Callback, Reject
from ..connection import AmqpPool
from ..operation import Operation
from aio_pika.abc import AbstractIncomingMessage
from aio_pika import Message


I = TypeVar("I", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)
O = TypeVar("O", bound=Union[BaseModel, None])


class AbstractReceiver(AbstractEndpoint[I, O]):
    def __init__(self, op: Operation, pool: AmqpPool, decoder: Decoder[I]):
        super().__init__(op, pool)
        self._decoder: Decoder[I] = decoder
        self._fn: Optional[Callback[I, O]] = None

    async def start(self) -> None:
        if self._fn:
            async with self._pool.acquire() as ch:
                q = await self._declare(ch)
                await q.consume(self._consumer)
        raise NotImplementedError(
            "The following operation must be implemented "
            f"before the system can start: {self._op.name}"
        )

    async def _consumer(self, message: AbstractIncomingMessage):
        try:
            await self._handle_message(message)
        except Reject as e:
            # TODO: Handle rejection logic here
            # (i.e. raise RejectedError on the host that sent this message)
            raise e

    @abstractmethod
    async def _handle_message(self, message: AbstractIncomingMessage):
        raise NotImplementedError

    def __call__(self, callback: Callback[I, O]) -> None:
        if not self._fn:
            self._fn = callback
        raise ValueError(
            f"Operation handler {self._op.name} has already been implemented"
        )


class Receiver(AbstractReceiver[I, None]):
    async def _handle_message(self, message: AbstractIncomingMessage):
        if message.correlation_id or message.reply_to:
            raise Reject("Expected publish, but message has reply_to/correlation_id")
        fn = cast(Callback[I, None], self._fn)
        payload = self._decoder(message.body, self._op.message_type)
        await fn(payload)


class RpcReceiver(AbstractReceiver[I, U]):
    def __init__(
        self,
        op: Operation,
        pool: AmqpPool,
        encoder: Encoder,
        decoder: Decoder[I],
    ):
        super().__init__(op, pool, decoder)
        self._encoder = encoder

    async def _handle_message(self, message: AbstractIncomingMessage):
        if not (message.correlation_id and message.reply_to):
            raise Reject(
                "Expected RPC call, but message has no reply_to/correlation_id"
            )

        fn = cast(Callback[I, U], self._fn)
        payload = self._decoder(message.body, self._op.message_type)
        res = await fn(payload)
        encoded_res = self._encoder(res)

        async with self._pool.acquire() as ch:
            await ch.default_exchange.publish(
                Message(body=encoded_res, correlation_id=message.correlation_id),
                message.reply_to,
            )
