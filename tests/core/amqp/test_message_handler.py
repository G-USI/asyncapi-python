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

    handler = MessageHandler(
        "userLoggedIn",
        decode_message=lambda x: decode_message(x, User),
        callback=callback,
    )
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
    req_queue = await amqp.declare_queue(exclusive=True)
    res_queue = await amqp.declare_queue(exclusive=True)

    async def rpc_callback(u: User) -> UserSurname:
        return UserSurname(surname=u.surname)

    async def reply_callback(x: Message, k: str):
        await amqp.default_exchange.publish(x, k)

    handler = RpcMessageHandler(
        "getUserSurname",
        rpc_callback,
        encode_message=encode_message,
        decode_message=lambda x: decode_message(x, User),
        reply_callback=reply_callback,
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

    res_handler = MessageHandler(
        "onUserSurnameResponse",
        res_callback,
        decode_message=lambda x: decode_message(x, UserSurname),
    )

    await res_queue.consume(res_handler)
    await req_queue.consume(handler)
    await asyncio.sleep(0.5)

    assert surnames == [UserSurname(surname="Doe")] * 3
