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


from aio_pika import Message
from aio_pika.pool import Pool
from aio_pika.abc import (
    AbstractRobustChannel,
    AbstractRobustQueue,
    AbstractIncomingMessage,
)
from logging import getLogger
from pydantic import BaseModel, RootModel, create_model
from typing import Optional, Sequence, TypeVar, Union, Type
from collections.abc import Sequence as Seq
from asyncio import Future
from uuid import uuid4
from .utils import encode_message, decode_message, union_model

T = TypeVar("T")
U = TypeVar("U")


class Producer:
    def __init__(
        self,
        channel_pool: Pool[AbstractRobustChannel],
        reply_queue: AbstractRobustQueue,
    ):
        if not reply_queue.exclusive:
            raise AssertionError("Reply queue must be exclusive")

        self._logger = getLogger(__name__)
        self._pool = channel_pool
        self._replies: dict[str, Future[AbstractIncomingMessage]] = {}
        self._reply_queue = reply_queue
        self._reply_consumer_tag: Optional[str] = None

    async def _on_reply(self, msg: AbstractIncomingMessage):
        await msg.ack()
        if msg.correlation_id is None or msg.correlation_id not in self._replies:
            return
        future = self._replies.pop(msg.correlation_id)
        future.set_result(msg)

    async def run(self):
        self._reply_consumer_tag = await self._reply_queue.consume(self._on_reply)

    async def publish(
        self,
        message: T,
        exchange: Optional[str],
        routing_key: Optional[str],
    ):
        outbound_message = Message(body=encode_message(RootModel[T](message)))
        async with self._pool.acquire() as channel:
            await (
                await channel.get_exchange(exchange)
                if exchange is not None
                else channel.default_exchange
            ).publish(outbound_message, routing_key or "")

    async def request(
        self,
        message: T,
        exchange: Optional[str],
        routing_key: Optional[str],
        output_types: Sequence[type[U]],
    ) -> U:
        if not self._reply_consumer_tag:
            raise AssertionError(
                "Cannot make requests that expect replies before Consumer::start is called"
            )
        corr_id = str(uuid4())
        outbound_message = Message(
            body=encode_message(RootModel[T](message)),
            correlation_id=corr_id,
            reply_to=self._reply_queue.name,
        )
        reply_future = Future[AbstractIncomingMessage]()
        async with self._pool.acquire() as channel:
            await (
                await channel.get_exchange(exchange)
                if exchange is not None
                else channel.default_exchange
            ).publish(outbound_message, routing_key or "")
            self._logger.info(f"Sent request {message}")
            self._replies[corr_id] = reply_future
        res = decode_message(
            (await reply_future).body,
            union_model(tuple(output_types)),
        ).root
        self._logger.info(f"Got response {res}")
        return res
