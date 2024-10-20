import asyncio
from .message_handler import AbstractMessageHandler, MessageHandler, RpcMessageHandler
from .connection import connection_pool
from asyncio import Future
from typing import Awaitable, Callable, TypeVar
from pydantic import BaseModel
from logging import getLogger

T = TypeVar("T", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)


class Consumer:
    def __init__(self, amqp_uri: str):
        self.__amqp_uri = amqp_uri
        self.__handlers: dict[str, AbstractMessageHandler] = {}
        self.__logger = getLogger(__name__)

    async def run(self, timeout: float | None = None):
        conn = connection_pool(self.__amqp_uri)
        if timeout is not None:
            await asyncio.sleep(timeout)
        else:
            await Future()

    def on(
        self,
        *,
        key: str,
        input_type: type[T],
        output_type: type[U] | None,
        callback: Callable,
    ):
        handler: AbstractMessageHandler
        if key in self.__handlers:
            raise AssertionError(f"Only one handler for `{key}` is allowed")
        if output_type is None:
            handler = MessageHandler(key, callback=callback, input_type=input_type)
        else:
            handler = RpcMessageHandler(
                key,
                callback=callback,
                input_type=input_type,
                output_type=output_type,
                channel=None,
            )
        self.__handlers[key] = handler
