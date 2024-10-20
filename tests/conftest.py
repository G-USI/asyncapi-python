import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio

from aio_pika.abc import AbstractChannel
from aio_pika.robust_connection import connect_robust


@pytest.fixture(scope="session")
def amqp_uri() -> str:
    return "amqp://guest:guest@rabbitmq/"


@pytest_asyncio.fixture(scope="function")
async def amqp(amqp_uri: str) -> AsyncGenerator[AbstractChannel, None]:
    connection = await connect_robust(amqp_uri)
    try:
        channel = await connection.channel()
        yield channel
    finally:
        await channel.close()
        await connection.close()
