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


from asyncapi_python.amqp.message_handler_params import (
    MessageHandlerParams,
    QueueHandlerParams,
)
from asyncapi_python.amqp import Producer, Consumer, AmqpPool
from pydantic import BaseModel
import asyncio
import random
from itertools import product


async def test_request_response(
    producer: Producer, consumer: Consumer, amqp_pool: AmqpPool
):
    a, b = range(10), range(10)
    reqs = list(product(a, b))
    random.shuffle(reqs)
    expected_add = [a + b for a, b in reqs]
    expected_sub = [a - b for a, b in reqs]

    async with amqp_pool.acquire() as channel:
        add_queue = (await channel.declare_queue(exclusive=True)).name
        sub_queue = (await channel.declare_queue(exclusive=True)).name

    [
        consumer.on(
            params=MessageHandlerParams(
                root=QueueHandlerParams(name=name, exclusive=True)
            ),
            input_type=Request,
            output_type=Response,
            callback=callback,
        )
        for name, callback in [
            (add_queue, handle_add_request),
            (sub_queue, handle_sub_request),
        ]
    ]

    await producer.run()
    _, actual_add_response, actual_sub_response = await asyncio.gather(
        consumer.run(),
        post_requests(producer, [Request(a=a, b=b) for a, b in reqs], None, add_queue),
        post_requests(producer, [Request(a=a, b=b) for a, b in reqs], None, sub_queue),
    )
    assert expected_add == [res.result for res in actual_add_response]
    assert expected_sub == [res.result for res in actual_sub_response]


class Request(BaseModel):
    a: int
    b: int


class Response(BaseModel):
    result: int


async def handle_add_request(req: Request) -> Response:
    return Response(result=req.a + req.b)


async def handle_sub_request(req: Request) -> Response:
    return Response(result=req.a - req.b)


async def post_requests(
    producer: Producer, reqs: list[Request], exchange: str | None, routing_key: str
) -> list[Response]:
    reqs_futures = [
        producer.request(
            message=req,
            exchange=exchange,
            routing_key=routing_key,
            output_type=Response,
        )
        for req in reqs
    ]
    return list(await asyncio.gather(*reqs_futures))
