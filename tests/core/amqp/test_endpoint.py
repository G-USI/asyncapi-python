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
import json

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
from asyncapi_python.amqp import Rejection, RejectedError
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
        debug_auto_delete=True,
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
        debug_auto_delete=True,
    )


@pytest.fixture(scope="function")
def err_operation() -> Operation:
    return Operation(
        name="operations/error",
        routing_key="testErrorQueue",
        message_type=Log,
        reply_type=None.__class__,
        exchange_name=None,
        exchange_type="default",
        debug_auto_delete=True,
    )


@pytest.fixture(scope="function")
def err_rpc_operation() -> Operation:
    return Operation(
        name="operations/add/error",
        routing_key="testErrorRpcQueue",
        message_type=AddRequest,
        reply_type=AddResponse,
        exchange_name=None,
        exchange_type="default",
        debug_auto_delete=True,
    )


@pytest.fixture(scope="function")
def correlation_ids() -> dict[str, Future[AbstractIncomingMessage]]:
    return defaultdict(lambda: Future())


def params(
    app_id: str,
    amqp_pool: AmqpPool,
    correlation_ids: dict[str, Future[AbstractIncomingMessage]],
) -> EndpointParams:
    return EndpointParams(
        pool=amqp_pool,
        register_correlation_id=lambda: ((uuid := str(uuid4()), correlation_ids[uuid])),
        encode=encode_message,
        decode=decode_message,
        app_id=app_id,
        stop_application=lambda: exit(-1),
        amqp_params={},
    )


@pytest.fixture(scope="function")
def params_0(amqp_pool, correlation_ids):
    return params("app-0", amqp_pool, correlation_ids)


@pytest.fixture(scope="function")
def params_1(amqp_pool, correlation_ids):
    return params("app-1", amqp_pool, correlation_ids)


@pytest.fixture(scope="function")
def params_2(amqp_pool, correlation_ids):
    return params("app-2", amqp_pool, correlation_ids)


@pytest.mark.asyncio
async def test_queue(params_1: EndpointParams, operation: Operation):
    producer: Sender[Log] = Sender(operation, params_1)
    consumer: Receiver[Log] = Receiver(operation, params_1)

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
    params_0: EndpointParams,
    rpc_operation: Operation,
    amqp_pool: AmqpPool,
    correlation_ids: dict[str, Future[AbstractIncomingMessage]],
):
    producer: RpcSender[AddRequest, AddResponse] = RpcSender(rpc_operation, params_0)
    consumer: RpcReceiver[AddRequest, AddResponse] = RpcReceiver(
        rpc_operation, params_0
    )

    async def on_request(msg: AddRequest) -> AddResponse:
        return AddResponse(root=msg.a + msg.b)

    async def on_reply(msg: AbstractIncomingMessage):
        future = correlation_ids.pop(msg.correlation_id or "")
        future.set_result(msg)
        await msg.ack()

    consumer(on_request)

    await producer.start()
    await consumer.start()

    async with amqp_pool.acquire() as ch:
        q = await ch.declare_queue(params_0.reply_queue_name, exclusive=True)
        await q.consume(on_reply)

    assert await producer(AddRequest(a=1, b=2)) == AddResponse(root=3)
    assert await producer(AddRequest(a=3, b=2)) == AddResponse(root=5)
    assert await producer(AddRequest(a=4, b=6)) == AddResponse(root=10)
    assert await producer(AddRequest(a=3, b=1)) == AddResponse(root=4)


async def test_reject(
    params_1: EndpointParams, err_operation: Operation, amqp_pool: AmqpPool
):
    producer: Sender[Log] = Sender(err_operation, params_1)
    consumer: Receiver[Log] = Receiver(err_operation, params_1)

    error_sent = [0]

    async def on_log(_: Log):
        raise Rejection("Access to logging denied")

    consumer(on_log)

    await producer.start()
    await consumer.start()

    async def on_error(msg: AbstractIncomingMessage):
        assert not msg.correlation_id
        payload = json.loads(msg.body)
        err, orig = payload.get("error", None), payload.get("original_message", None)
        assert err
        assert orig
        error_sent[0] += 1
        await msg.ack()

    async with amqp_pool.acquire() as ch:
        q = await ch.declare_queue(params_1.error_queue_name, exclusive=True)
        await q.consume(on_error)

    log = Log(content="Something went wrong")
    await producer(log)

    await asyncio.sleep(0.2)
    assert error_sent[0] == 1


async def test_err_rpc(
    params_2: EndpointParams,
    err_rpc_operation: Operation,
    amqp_pool: AmqpPool,
    correlation_ids: dict[str, Future[AbstractIncomingMessage]],
):

    producer: RpcSender[AddRequest, AddResponse] = RpcSender(
        err_rpc_operation, params_2
    )
    consumer: RpcReceiver[AddRequest, AddResponse] = RpcReceiver(
        err_rpc_operation, params_2
    )

    async def on_request(msg: AddRequest) -> AddResponse:
        if msg.b == 2:
            raise Rejection("This service rejects when b=2")
        return AddResponse(root=msg.a + msg.b)

    async def on_reply(msg: AbstractIncomingMessage):
        future = correlation_ids.pop(msg.correlation_id or "")
        future.set_result(msg)

    async def on_error(msg: AbstractIncomingMessage):
        payload = json.loads(msg.body)
        future = correlation_ids.pop(msg.correlation_id or "")
        future.set_exception(
            RejectedError(payload["error"], payload["original_message"])
        )

    consumer(on_request)

    await producer.start()
    await consumer.start()

    async with amqp_pool.acquire() as ch:
        q = await ch.declare_queue(params_2.reply_queue_name, exclusive=True)
        await q.consume(on_reply)
        q = await ch.declare_queue(params_2.error_queue_name, exclusive=True)
        await q.consume(on_error)

    with pytest.raises(RejectedError):
        await producer(AddRequest(a=1, b=2))
    with pytest.raises(RejectedError):
        await producer(AddRequest(a=3, b=2))
    assert await producer(AddRequest(a=4, b=6)) == AddResponse(root=10)
    assert await producer(AddRequest(a=3, b=1)) == AddResponse(root=4)
