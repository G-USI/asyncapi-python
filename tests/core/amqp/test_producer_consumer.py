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
    ExchangeHandlerParams,
)
from asyncapi_python.amqp import Producer, Consumer
from pydantic import BaseModel
from functools import partial
import asyncio
import random


async def test_producer_consumer(
    producer: Producer,
    consumer: Consumer,
    consumer2: Consumer,
):
    exchange_name = f"test_exchange_{random.randint(10000, 99999)}"
    users = [
        UserRegisteredEvent.model_validate(x)
        for x in [
            dict(id=0, username="zero"),
            dict(id=1, username="one"),
            dict(id=2, username="two"),
        ]
    ]

    # Setup consumers
    states: list[dict[int, str]] = [{} for _ in range(2)]
    for cons, s in zip([consumer, consumer2], states):
        cons.on(
            params=MessageHandlerParams(
                root=ExchangeHandlerParams(
                    type="fanout",
                    name=exchange_name,
                    auto_delete=True,
                    routing_key=None,
                )
            ),
            input_types=(UserRegisteredEvent,),
            output_types=None,
            callback=partial(on_user_registered, s),
        )
        await cons.run()

    # Send messages
    await asyncio.gather(
        *(producer.publish(u, exchange=exchange_name, routing_key=None) for u in users)
    )
    await asyncio.sleep(0.5)

    expected = {0: "zero", 1: "one", 2: "two"}
    assert states[0] == expected
    assert states[1] == expected


class UserRegisteredEvent(BaseModel):
    id: int
    username: str


async def on_user_registered(state: dict[int, str], x: UserRegisteredEvent):
    state[x.id] = x.username
