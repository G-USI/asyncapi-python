from abc import ABC, abstractmethod
from aio_pika.message import AbstractIncomingMessage, Message
from typing import Awaitable, Callable, Generic, TypeVar
from pydantic import BaseModel
from logging import getLogger
from .utils import decode_message, encode_message
from .connection import channel_pool
from asyncio import Future


T = TypeVar("T", bound=BaseModel)
U = TypeVar("U", bound=BaseModel | None)
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
        input_type: type[T],
    ):
        super().__init__(name, callback)
        self._input_type = input_type

    async def on_call(self, message: AbstractIncomingMessage) -> None:
        message_body = decode_message(message.body, self._input_type)
        await self._callback(message_body)


class RpcMessageHandler(AbstractMessageHandler[T, V]):
    def __init__(
        self,
        name: str,
        callback: Callable[[T], Awaitable[V]],
        input_type: type[T],
        output_type: type[V],
    ):
        super().__init__(name, callback)
        self._input_type = input_type
        self._output_type = output_type

    async def on_call(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id is None:
            raise AssertionError("RPC Call got empty correlation_id")
        if message.reply_to is None:
            raise AssertionError("RPC Call got empty reply_to header")
        message_body = decode_message(message.body, self._input_type)
        result = await self._callback(message_body)
        async with channel_pool().acquire() as channel:
            await channel.default_exchange.publish(
                Message(
                    encode_message(result),
                    correlation_id=message.correlation_id,
                ),
                message.reply_to,
            )
