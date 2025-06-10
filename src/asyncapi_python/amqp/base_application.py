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
import json
from aio_pika.abc import AbstractIncomingMessage, ConsumerTag
from aio_pika import Message
from uuid import uuid4

from .error import RejectedError
from .endpoint import EndpointParams
from .connection import channel_pool
from .utils import encode_message, decode_message
from .params import AmqpParams
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
    # TODO: Create AbstractEndpoint instance to handle reply queue
    # TODO: Create AbstractEndpoint instance to handle error queue
    # TODO: Do not mess with aio_pika api here -- use endpoints
    # TODO: If rpc server rejects, and the error
    #       is invalid, we have to raise on both client and server
    #       to prevent permanent locking
    # TODO: Add configurable timeouts to calls

    def __init__(
        self,
        amqp_uri: str,
        producer_factory: type[P],
        consumer_factory: type[C],
        amqp_params: AmqpParams,
    ):
        self.__params = EndpointParams(
            pool=channel_pool(amqp_uri),
            encode=encode_message,
            decode=decode_message,
            register_correlation_id=self.__register_correlation_id,
            stop_application=self.stop,
            app_id=str(uuid4()),
            amqp_params=amqp_params,
        )
        self.__reply_futures: dict[
            str,
            Future[AbstractIncomingMessage],
        ] = defaultdict(lambda: Future())
        self.__stop_future: Optional[Future[None]] = None

        self.__reply_tag: Optional[ConsumerTag] = None
        self.__error_tag: Optional[ConsumerTag] = None

        self.producer: P = producer_factory(self.__params)
        self.consumer: C = consumer_factory(self.__params)

    async def start(self, blocking: bool = True):
        await self.consumer.start()
        await self.producer.start()
        async with self.__params.pool.acquire() as ch:
            reply_queue = await ch.declare_queue(
                self.__params.reply_queue_name, exclusive=True
            )
            self.__reply_tag = await reply_queue.consume(self.__handle_reply)
            error_queue = await ch.declare_queue(
                self.__params.error_queue_name, exclusive=True
            )
            self.__error_tag = await error_queue.consume(self.__handle_error)

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
        if self.__stop_future:
            stop_future, self.__stop_future = self.__stop_future, None
            stop_future.set_result(None)
        async with self.__params.pool.acquire() as ch:
            if self.__reply_tag:
                q = await ch.get_queue(self.__params.reply_queue_name)
                await q.cancel(self.__reply_tag)
            if self.__error_tag:
                q = await ch.get_queue(self.__params.error_queue_name)
                await q.cancel(self.__error_tag)

    async def __handle_reply(self, message: AbstractIncomingMessage):
        if future := self.__reply_futures.pop(message.correlation_id or "", None):
            future.set_result(message)
        await message.ack()

    async def __handle_error(self, message: AbstractIncomingMessage):
        try:
            # All valid errors must be json with keys 'error' and 'original_message'
            # All messages that do not satisfy the format are just dropped
            payload = json.loads(message.body)
            error, msg = payload["error"], payload["original_message"]
            exception = RejectedError(error, msg)
            await message.ack()
        except:
            # If the error is invalid, then send error to the author of the message
            await message.reject()
            if not message.app_id:
                return
            err_payload = json.dumps(
                {
                    "error": {"message": "Invalid error channel payload"},
                    "original_message": {
                        "headers": message.headers,
                        "body": json.loads(message.body),
                    },
                }
            ).encode()
            async with self.__params.pool.acquire() as ch:
                await ch.default_exchange.publish(
                    Message(
                        err_payload,
                        app_id=self.__params.app_id,
                    ),
                    self.__params.get_error_queue(message.app_id),
                )
            return

        # If error has no correlation id, raise here
        if not message.correlation_id:
            raise exception
        # If the correlation id is expected -- raise it where it is expected
        elif future := self.__reply_futures.pop(message.correlation_id or "", None):
            future.set_exception(exception)
        # Else drop message

    def __register_correlation_id(self) -> tuple[str, Future[AbstractIncomingMessage]]:
        corr_id = str(uuid4())
        return corr_id, self.__reply_futures[corr_id]
