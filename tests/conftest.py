import asyncio
from typing import AsyncGenerator
from aio_pika import connect_robust
import pytest
import pytest_asyncio

from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection
from aio_pika.pool import Pool


@pytest.fixture(scope="session")
def amqp_uri() -> str:
    return "amqp://guest:guest@rabbitmq/"


@pytest_asyncio.fixture(scope="function")
async def amqp_pool(amqp_uri: str) -> AsyncGenerator[Pool[AbstractRobustChannel], None]:
    async def get_connection() -> AbstractRobustConnection:
        return await connect_robust(amqp_uri)

    connection_pool: Pool = Pool(get_connection, max_size=2)

    async def get_channel():
        async with connection_pool.acquire() as connection:
            return await connection.channel()

    channel_pool: Pool = Pool(get_channel, max_size=10)
    yield channel_pool
    await channel_pool.close()
    await connection_pool.close()
