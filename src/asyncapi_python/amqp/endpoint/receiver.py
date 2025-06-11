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


from abc import abstractmethod
import json
from typing import Awaitable, Callable, Optional, TypeVar, Union, cast, get_args

from pydantic import BaseModel, ValidationError

from .base import AbstractEndpoint, EndpointParams
from ..error import Rejection, BadRequestRejection
from ..operation import Operation
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustQueue


I = TypeVar("I", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)
O = TypeVar("O", bound=Union[BaseModel, None])


Callback = Callable[[I], Awaitable[O]]
"""A callback that turns input type into output type"""


class AbstractReceiver(AbstractEndpoint[I, O]):
    def __init__(self, op: Operation, params: EndpointParams):
        super().__init__(op, params)
        self._fn: Optional[Callback[I, O]] = None
        self._consumer_tag: Optional[str] = None
        self._queue: Optional[AbstractRobustQueue] = None

    async def start(self) -> None:
        print("start", self._op)
        if self._fn:
            async with self._params.pool.acquire() as ch:
                if prefetch_count := self._params.amqp_params.get("prefetch_count"):
                    await ch.set_qos(prefetch_count=prefetch_count)
                q = self._queue = await self._declare(ch)
                self._consumer_tag = await q.consume(self._consumer)
            return
        path = ".".join(self._op.path)
        args = get_args(getattr(self.__class__, "__orig_bases__")[0])
        i = args[0].__name__
        o = args[1].__name__ if len(args) > 1 else None
        raise NotImplementedError(
            "The following operation must be implemented "
            f"before the system can start: {self._op.name}. "
            "This can be done by:\n\n\n"
            "```python\n"
            f"@app.consumer.{path}\n"
            f"async def callback(msg: {i}) -> {o}:\n"
            "    # TODO: Implement callback for this handler\n"
            "    raise NotImplementedError\n"
            "```\n"
        )

    async def stop(self):
        if not (self._consumer_tag and self._queue):
            return
        await self._queue.cancel(self._consumer_tag)

    async def _consumer(self, message: AbstractIncomingMessage):
        try:
            payload = self._decode_payload(message)
            await self._handle_message(message, payload)
            await message.ack()
        except Rejection as e:
            await self._reject(e, message)

    def _decode_payload(self, message: AbstractIncomingMessage) -> I:
        try:
            payload: I = self._params.decode(message.body, self._op.message_type)
        except ValidationError as e:
            raise BadRequestRejection(e)
        return payload

    async def _reject(self, err: Rejection, message: AbstractIncomingMessage):
        await message.reject()
        if not (app_id := message.app_id):
            return

        err_payload = json.dumps(
            {
                "error": err.asdict(),
                "original_message": {
                    "headers": message.headers,
                    "body": json.loads(message.body),
                },
            }
        ).encode()
        err_msg = self._create_message(err_payload, message.correlation_id)
        routing_key = self._params.get_error_queue(app_id)
        async with self._params.pool.acquire() as ch:
            await ch.default_exchange.publish(err_msg, routing_key)

    @abstractmethod
    async def _handle_message(self, message: AbstractIncomingMessage, payload: I):
        raise NotImplementedError

    def __call__(self, callback: Callback[I, O]) -> None:
        if not self._fn:
            self._fn = callback
            return
        raise ValueError(
            f"Operation handler {self._op.name} has already been implemented"
        )


class Receiver(AbstractReceiver[I, None]):
    async def _handle_message(self, message: AbstractIncomingMessage, payload: I):
        if message.correlation_id or message.reply_to:
            raise Rejection("Expected publish, but message has reply_to/correlation_id")
        fn = cast(Callback[I, None], self._fn)
        await fn(payload)


class RpcReceiver(AbstractReceiver[I, U]):
    async def _handle_message(self, message: AbstractIncomingMessage, payload: I):
        if not (message.correlation_id and message.reply_to):
            raise Rejection(
                "Expected RPC call, but message has no reply_to/correlation_id"
            )

        fn = cast(Callback[I, U], self._fn)
        res = await fn(payload)
        encoded_res = self._params.encode(res)

        async with self._params.pool.acquire() as ch:
            await ch.default_exchange.publish(
                self._create_message(
                    encoded_res, correlation_id=message.correlation_id
                ),
                message.reply_to,
            )
