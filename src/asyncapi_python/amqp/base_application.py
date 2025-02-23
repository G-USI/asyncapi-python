# Copyright 2024-2025 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
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

from asyncio import Future
from collections import defaultdict
from aio_pika.abc import AbstractIncomingMessage
from uuid import uuid4
from .endpoint import EndpointParams
from .connection import channel_pool
from .utils import encode_message, decode_message
from typing import Generic, Optional, TypeVar


class Router:
    def __init__(self, params: EndpointParams):
        self._params = params

    async def start(self) -> None:
        for f in self.__dict__.values():
            if not isinstance(f, Router):
                continue
            await f.start()

    async def stop(self) -> None:
        for f in self.__dict__.values():
            if not isinstance(f, Router):
                continue
            await f.stop()


P = TypeVar("P", bound=Router)
C = TypeVar("C", bound=Router)


class BaseApplication(Generic[P, C]):
    def __init__(
        self,
        amqp_uri: str,
        producer_factory: type[P],
        consumer_factory: type[C],
    ):
        self.__params = EndpointParams(
            pool=channel_pool(amqp_uri),
            encode=encode_message,
            decode=decode_message,
            reply_to=f"reply-queue-{uuid4()}",
            await_corr_id=self.__await_corr_id,
            stop_application=self.stop,
        )
        self.__reply_futures: dict[
            str,
            Future[AbstractIncomingMessage],
        ] = defaultdict(lambda: Future())
        self.__stop_future: Optional[Future[None]] = None

        self.producer: P = producer_factory(self.__params)
        self.consumer: C = consumer_factory(self.__params)

    async def start(self, blocking: bool = True):
        await self.consumer.start()
        await self.producer.start()
        async with self.__params.pool.acquire() as ch:
            reply_queue = await ch.declare_queue(self.__params.reply_to, exclusive=True)
            await reply_queue.consume(self.__handle_reply)

        if not blocking:
            return

        if self.__stop_future:
            raise AssertionError(
                "Calling start multiple times with blocking=True is not supported"
            )
        self.__stop_future = Future()
        await self.__stop_future

    async def stop(self) -> None:
        await self.producer.stop()
        await self.consumer.stop()
        if not self.__stop_future:
            return
        stop_future, self.__stop_future = self.__stop_future, None
        stop_future.set_result(None)

    def __handle_reply(self, message: AbstractIncomingMessage):
        if future := self.__reply_futures.pop(message.correlation_id or "", None):
            future.set_result(message)

    def __await_corr_id(self, corr_id: str) -> Future:
        return self.__reply_futures[corr_id]
