from typing import AsyncGenerator
from asyncapi_python.amqp.message_handler import MessageHandler, RpcMessageHandler
from asyncapi_python.amqp.utils import encode_message, decode_message
from asyncapi_python.amqp.connection import channel_pool
from pydantic import BaseModel
import datetime
import pytest
import pytest_asyncio
from aio_pika.abc import AbstractRobustChannel
import asyncio


class User(BaseModel):
    name: str
    surname: str
    birthdate: datetime.date


@pytest.mark.asyncio
async def test_message_handler(amqp: AbstractRobustChannel):
    await amqp.declare_queue("hello", auto_delete=True)
    await asyncio.sleep(10)
