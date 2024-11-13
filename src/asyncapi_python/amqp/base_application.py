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


from .connection import channel_pool, AmqpPool
from .consumer import Consumer
from .producer import Producer
from typing import Literal, Optional, TypedDict


class Queue(TypedDict):
    name: Optional[str]
    durable: bool
    exclusive: bool
    auto_delete: bool


class Exchange(TypedDict):
    name: Optional[str]
    type: Literal["topic", "direct", "fanout", "default", "headers"]
    durable: bool
    auto_delete: bool


class BaseApplication:
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
