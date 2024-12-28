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


from .message_handler import AbstractMessageHandler, MessageHandler, RpcMessageHandler
from .message_handler_params import MessageHandlerParams
from .utils import encode_message, decode_message, union_model

import asyncio
from aio_pika import Message
from aio_pika.pool import Pool
from aio_pika.abc import AbstractRobustChannel
from asyncio import Future
from typing import Callable, Optional, Sequence, TypeVar, Union
from pydantic import BaseModel, RootModel
from logging import getLogger

T = TypeVar("T")
U = TypeVar("U")


class Consumer:
    def __init__(self, channel_pool: Pool[AbstractRobustChannel]):
        self._handlers: dict[MessageHandlerParams, AbstractMessageHandler] = {}
        self._logger = getLogger(__name__)
        self._pool = channel_pool

    async def run_blocking(self, timeout: Union[int, float, None]):
        await self.run()
        if timeout is not None:
            await asyncio.sleep(timeout)
        else:
            await Future()

    async def run(self):
        async with self._pool.acquire() as channel:
            for params, handler in self._handlers.items():
                await params.setup_consume(handler, channel)

    async def _reply_callback(self, message: Message, routing_key: str):
        async with self._pool.acquire() as channel:
            await channel.default_exchange.publish(message, routing_key)

    def on(
        self,
        *,
        params: MessageHandlerParams,
        input_types: Sequence[type[T]],
        output_types: Union[None, Sequence[type[U]]],
        callback: Callable,
    ):
        handler: AbstractMessageHandler
        if params in self._handlers:
            raise AssertionError(f"Only one handler for `{params}` is allowed")
        if output_types is None or len(output_types) == 0:
            handler = MessageHandler(
                name=params.root.name,
                callback=callback,
                decode_message=lambda x: decode_message(
                    x, union_model(tuple(input_types))
                ).root,
            )
        else:
            handler = RpcMessageHandler(
                name=params.root.name,
                callback=callback,
                reply_callback=self._reply_callback,
                encode_message=encode_message,
                decode_message=lambda x: decode_message(
                    x, union_model(tuple(input_types))
                ).root,
            )
        self._handlers[params] = handler
