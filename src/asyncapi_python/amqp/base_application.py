from .connection import channel_pool, AmqpPool
from .consumer import Consumer
from .producer import Producer
from abc import ABC, abstractmethod
from typing import Literal, TypedDict


class Queue(TypedDict):
    name: str | None
    durable: bool
    exclusive: bool
    auto_delete: bool


class Exchange(TypedDict):
    name: str | None
    type: Literal["topic", "direct", "fanout", "default", "headers"]
    durable: bool
    auto_delete: bool


class BaseApplication(ABC):
    def __init__(self, amqp_uri: str):
        self._uri = amqp_uri
        self._has_started = False
        self._pool = channel_pool(self._uri)
        self._consumer = Consumer(self._pool)

    def _assert_started(self):
        if not self._has_started:
            cls_name = self.__class__.__name__
            raise AssertionError(
                f"Invoke of {cls_name}::request or {cls_name}::publish "
                + "occurred before {cls_name}::start"
            )

    async def start(self, blocking: bool = True):
        async with self._pool.acquire() as ch:
            reply_queue = await ch.declare_queue(exclusive=True)
            self._producer = Producer(self._pool, reply_queue)
            await self._producer.run()
            self._has_started = True
        if blocking:
            await self._consumer.run_blocking(timeout=None)
        else:
            await self._consumer.run()
