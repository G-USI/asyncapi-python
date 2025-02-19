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


from abc import ABC, abstractmethod
from typing import (
    Awaitable,
    Callable,
    Generic,
    Protocol,
    Type,
    TypeVar,
    Union,
)

from pydantic import BaseModel
from ..connection import AmqpPool
from ..operation import Operation
from aio_pika.abc import (
    AbstractRobustChannel,
    AbstractRobustQueue,
)

I = TypeVar("I", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)
O = TypeVar("O", bound=Union[BaseModel, None])


class Reject(BaseException): ...


class RejectedError(BaseException): ...


class Encoder(Protocol):
    """A function that turns base model into bytes"""

    def __call__(self, message: BaseModel) -> bytes: ...


class Decoder(Protocol[I]):
    """A function that turns bytes into subclass of base model using schema"""

    def __call__(self, body: bytes, schema: Type[I]) -> I: ...


Callback = Callable[[I], Awaitable[O]]
"""A callback that turns input type into output type"""


class AbstractEndpoint(ABC, Generic[I, O]):
    def __init__(self, op: Operation, pool: AmqpPool):
        self._op = op
        self._pool = pool

    @abstractmethod
    async def start(self):
        raise NotImplementedError

    async def _declare(self, ch: AbstractRobustChannel) -> AbstractRobustQueue:
        ex_name = self._op.exchange_name
        ex_type = self._op.exchange_type
        q_name = self._op.routing_key

        q = await ch.declare_queue(
            name=q_name,
            durable=bool(q_name),
            exclusive=not bool(q_name),
        )
        if ex_name:
            ex = await ch.declare_exchange(name=ex_name, type=ex_type)
            await q.bind(ex)
        return q
