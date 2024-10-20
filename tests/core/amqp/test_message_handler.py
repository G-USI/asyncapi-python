from typing import AsyncGenerator
from asyncapi_python.amqp.message_handler import MessageHandler, RpcMessageHandler
from asyncapi_python.amqp.utils import encode_message, decode_message
from asyncapi_python.amqp.connection import channel_pool
from pydantic import BaseModel
import datetime
import asyncio
import pytest
from aio_pika.abc import AbstractRobustChannel
from aio_pika import Message


class User(BaseModel):
    name: str
    surname: str
    birthdate: datetime.date


class UserSurname(BaseModel):
    surname: str


@pytest.fixture(scope="module")
def users():
    return [User(name="John", surname="Doe", birthdate=datetime.date(2022, 3, 4))] * 3


@pytest.mark.asyncio
async def test_message_handler(amqp: AbstractRobustChannel, users: list[User]):
    surnames: list[str] = []

    async def callback(u: User):
        surnames.append(u.surname)

    handler = MessageHandler("userLoggedIn", input_type=User, callback=callback)
    req_queue = await amqp.declare_queue(exclusive=True)
    for user in users:
        message = Message(body=encode_message(user))
        await amqp.default_exchange.publish(message, routing_key=req_queue.name)

    await req_queue.consume(handler)
    await asyncio.sleep(0.5)
    assert surnames == ["Doe"] * 3
    print(surnames)


@pytest.mark.asyncio
async def test_rpc_message_handler(amqp: AbstractRobustChannel, users: list[User]):
    req_queue = await amqp.declare_queue("req")
    res_queue = await amqp.declare_queue("res")

    async def rpc_callback(u: User) -> UserSurname:
        return UserSurname(surname=u.surname)

    handler = RpcMessageHandler(
        "getUserSurname",
        rpc_callback,
        input_type=User,
        output_type=UserSurname,
        channel=amqp,
    )

    for i, user in enumerate(users):
        message = Message(
            body=encode_message(user),
            correlation_id=str(hash(i)),
            reply_to=res_queue.name,
        )
        await amqp.default_exchange.publish(message, routing_key=req_queue.name)

    surnames: list[UserSurname] = []

    async def res_callback(s: UserSurname) -> None:
        surnames.append(s)

    res_handler = MessageHandler("onUserSurnameResponse", res_callback, UserSurname)

    await res_queue.consume(res_handler)
    await req_queue.consume(handler)
    await asyncio.sleep(0.5)

    assert surnames == [UserSurname(surname="Doe")] * 3
