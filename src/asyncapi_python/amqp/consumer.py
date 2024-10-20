from .message_handler import AbstractMessageHandler
from .connection import connection_pool
from asyncio import Future
from typing import Awaitable, Callable
from pydantic import BaseModel
from logging import getLogger


class Consumer:
    def __init__(self, amqp_uri: str):
        self.__amqp_uri = amqp_uri
        self.__handlers: dict[str, AbstractMessageHandler] = {}
        self.__logger = getLogger(__name__)

    async def run(self):
        conn = connection_pool(self.__amqp_uri)
        return await Future()

    def on(
        self,
        *,
        key: str,
        input_type: type[BaseModel],
        output_type: type[BaseModel] | None,
        callback: Callable[[BaseModel], Awaitable[BaseModel | None]],
    ):
        if key in self.__handlers:
            raise AssertionError(f"Only one handler for `{key}` is allowed")
        self.__handlers[key] = AbstractMessageHandler()
