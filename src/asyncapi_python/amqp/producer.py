from aio_pika import Message
from aio_pika.pool import Pool
from aio_pika.abc import (
    AbstractRobustChannel,
    AbstractRobustQueue,
    AbstractIncomingMessage,
)
from logging import getLogger
from pydantic import BaseModel
from typing import TypeVar
from asyncio import Future
from uuid import uuid4
from .utils import encode_message, decode_message

T = TypeVar("T", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)


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

    async def on_reply(self, msg: AbstractIncomingMessage):
        await msg.ack()
        if msg.correlation_id is None or msg.correlation_id not in self._replies:
            return
        future = self._replies.pop(msg.correlation_id)
        future.set_result(msg)

    async def publish(
        self,
        message: T,
        exchange: str | None,
        routing_key: str,
    ):
        outbound_message = Message(
            body=encode_message(message),
            reply_to=self._reply_queue.name,
        )
        async with self._pool.acquire() as channel:
            await (
                await channel.get_exchange(exchange)
                if exchange is not None
                else channel.default_exchange
            ).publish(outbound_message, routing_key)

    async def publish_reply(
        self,
        message: T,
        exchange: str | None,
        routing_key: str,
        output_type: type[U],
    ) -> U:
        corr_id = str(uuid4())
        outbound_message = Message(
            body=encode_message(message),
            correlation_id=corr_id,
            reply_to=self._reply_queue.name,
        )
        reply_future = Future[AbstractIncomingMessage]()
        async with self._pool.acquire() as channel:
            await (
                await channel.get_exchange(exchange)
                if exchange is not None
                else channel.default_exchange
            ).publish(outbound_message, routing_key)
            self._replies[corr_id] = reply_future
        return decode_message((await reply_future).body, output_type)
