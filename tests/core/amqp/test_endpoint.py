# Copyright 2025 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
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


from asyncio import Future
import asyncio
from collections import defaultdict

from pydantic import BaseModel, RootModel
from asyncapi_python.amqp import (
    Operation,
    EndpointParams,
    AmqpPool,
    Sender,
    RpcSender,
    Receiver,
    RpcReceiver,
)
from asyncapi_python.amqp.utils import encode_message, decode_message
from aio_pika.abc import AbstractIncomingMessage
from uuid import uuid4
import pytest


class Log(BaseModel):
    content: str


class AddRequest(BaseModel):
    a: int
    b: int


class AddResponse(RootModel):
    root: int


@pytest.fixture(scope="function")
def rpc_operation() -> Operation:
    return Operation(
        name="operations/add",
        routing_key="testRpcQueue",
        message_type=AddRequest,
        reply_type=AddResponse,
        exchange_name=None,
        exchange_type="default",
    )


@pytest.fixture(scope="function")
def operation() -> Operation:
    return Operation(
        name="operations/log",
        routing_key="testQueue",
        message_type=Log,
        reply_type=None.__class__,
        exchange_name=None,
        exchange_type="default",
    )


@pytest.fixture(scope="function")
def correlation_ids() -> dict[str, Future[AbstractIncomingMessage]]:
    return defaultdict(lambda: Future())


@pytest.fixture(scope="function")
def params(
    amqp_pool: AmqpPool,
    correlation_ids: dict[str, Future[AbstractIncomingMessage]],
) -> EndpointParams:
    return EndpointParams(
        pool=amqp_pool,
        register_correlation_id=lambda: ((uuid := str(uuid4()), correlation_ids[uuid])),
        encode=encode_message,
        decode=decode_message,
        app_id="app-1",
        stop_application=lambda: exit(-1),
    )


async def test_queue(params: EndpointParams, operation: Operation):
    producer: Sender[Log] = Sender(operation, params)
    consumer: Receiver[Log] = Receiver(operation, params)

    count = [0]

    async def on_log(msg: Log):
        assert msg.content == str(count[0])
        count[0] += 1

    consumer(on_log)

    await producer.start()
    await consumer.start()

    for i in map(str, range(3)):
        log = Log(content=i)
        await producer(log)

    await asyncio.sleep(0.2)
    assert count[0] == 3


async def test_rpc(
    params: EndpointParams,
    rpc_operation: Operation,
    amqp_pool: AmqpPool,
    correlation_ids: dict[str, Future[AbstractIncomingMessage]],
):
    producer: RpcSender[AddRequest, AddResponse] = RpcSender(rpc_operation, params)
    consumer: RpcReceiver[AddRequest, AddResponse] = RpcReceiver(rpc_operation, params)

    async def on_request(msg: AddRequest) -> AddResponse:
        return AddResponse(root=msg.a + msg.b)

    async def on_reply(msg: AbstractIncomingMessage):
        future = correlation_ids.pop(msg.correlation_id or "")
        future.set_result(msg)

    consumer(on_request)

    await producer.start()
    await consumer.start()

    async with amqp_pool.acquire() as ch:
        q = await ch.declare_queue(params.reply_queue_name, auto_delete=True)
        await q.consume(on_reply)

    assert await producer(AddRequest(a=1, b=2)) == AddResponse(root=3)
    assert await producer(AddRequest(a=3, b=2)) == AddResponse(root=5)
    assert await producer(AddRequest(a=4, b=6)) == AddResponse(root=10)
    assert await producer(AddRequest(a=3, b=1)) == AddResponse(root=4)
