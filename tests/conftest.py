from typing import AsyncGenerator
import pytest
import pytest_asyncio

from asyncapi_python.amqp.connection import channel_pool
from aio_pika.abc import AbstractRobustChannel


@pytest.fixture
def amqp_uri() -> str:
    return "amqp://guest:guest@rabbitmq/"


@pytest_asyncio.fixture
async def amqp(amqp_uri: str) -> AsyncGenerator[AbstractRobustChannel, None]:
    async with channel_pool(amqp_uri).acquire() as conn:
        yield conn
