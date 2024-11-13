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


from abc import ABC, abstractmethod
from aio_pika.message import AbstractIncomingMessage, Message
from typing import Awaitable, Callable, Generic, TypeVar, Union
from pydantic import BaseModel
from logging import getLogger


T = TypeVar("T", bound=BaseModel)
U = TypeVar("U", bound=Union[BaseModel, None])
V = TypeVar("V", bound=BaseModel)


class AbstractMessageHandler(ABC, Generic[T, U]):
    def __init__(self, name: str, callback: Callable[[T], Awaitable[U]]):
        self._logger = getLogger(__name__)
        self._name = name
        self._callback = callback

    async def __call__(self, message: AbstractIncomingMessage) -> None:
        cls = f"{self.__class__.__name__}#{self._name}"
        self._logger.info(f"{cls}: got message: {message.info()}")
        self._logger.debug(f"content: {message.body!r}")
        await self.on_call(message)
        await message.ack()
        self._logger.info(f"{cls} finished message: {message.info()}")

    @abstractmethod
    async def on_call(self, message: AbstractIncomingMessage) -> None:
        raise NotImplementedError


class MessageHandler(AbstractMessageHandler[T, None]):
    def __init__(
        self,
        name: str,
        callback: Callable[[T], Awaitable[None]],
        decode_message: Callable[[bytes], T],
    ):
        super().__init__(name, callback)
        self._decode_message = decode_message

    async def on_call(self, message: AbstractIncomingMessage) -> None:
        message_body = self._decode_message(message.body)
        await self._callback(message_body)


class RpcMessageHandler(AbstractMessageHandler[T, V]):
    def __init__(
        self,
        name: str,
        callback: Callable[[T], Awaitable[V]],
        reply_callback: Callable[[Message, str], Awaitable[None]],
        decode_message: Callable[[bytes], T],
        encode_message: Callable[[V], bytes],
    ):
        super().__init__(name, callback)
        self._reply_callback = reply_callback
        self._decode_message = decode_message
        self._encode_message = encode_message

    async def on_call(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id is None:
            raise AssertionError("RPC Call got empty correlation_id")
        if message.reply_to is None:
            raise AssertionError("RPC Call got empty reply_to header")
        message_body = self._decode_message(message.body)
        result = await self._callback(message_body)
        await self._reply_callback(
            Message(
                self._encode_message(result),
                correlation_id=message.correlation_id,
            ),
            message.reply_to,
        )
