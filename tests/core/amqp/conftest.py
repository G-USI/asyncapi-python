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


from asyncapi_python.amqp import Producer, Consumer, AmqpPool
import pytest_asyncio
import pytest
import asyncio
from typing import AsyncGenerator
from aio_pika import connect_robust
from aio_pika.pool import Pool
from aio_pika.abc import AbstractRobustConnection
from os import environ
import pytest
import pytest_asyncio


@pytest_asyncio.fixture(scope="function")
async def producer(amqp_pool: AmqpPool) -> Producer:
    async with amqp_pool.acquire() as channel:
        queue = await channel.declare_queue(exclusive=True)
    return Producer(channel_pool=amqp_pool, reply_queue=queue)


@pytest_asyncio.fixture(scope="function")
async def consumer(amqp_pool: AmqpPool) -> Consumer:
    return Consumer(channel_pool=amqp_pool)


@pytest_asyncio.fixture(scope="function")
async def consumer2(amqp_pool: AmqpPool) -> Consumer:
    return Consumer(channel_pool=amqp_pool)


@pytest.fixture(scope="session")
def amqp_uri() -> str:
    if (env_uri := environ.get("AMQP_URI")) is not None:
        return env_uri
    return "amqp://guest:guest@rabbitmq/"


@pytest_asyncio.fixture(scope="function")
async def amqp_pool(amqp_uri: str) -> AsyncGenerator[AmqpPool, None]:
    async def get_connection():
        return await connect_robust(amqp_uri)

    connection_pool = Pool[AbstractRobustConnection](get_connection, max_size=2)

    async def get_channel():
        async with connection_pool.acquire() as connection:
            return await connection.channel()

    channel_pool: Pool = Pool(get_channel, max_size=10)
    yield channel_pool
    await channel_pool.close()
    await connection_pool.close()
