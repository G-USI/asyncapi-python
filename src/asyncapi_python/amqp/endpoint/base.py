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
from dataclasses import dataclass
from typing import (
    Awaitable,
    Callable,
    Generic,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
)

from aio_pika import Message
from pydantic import BaseModel
from ..error import Rejection, RejectedError
from ..connection import AmqpPool
from ..operation import Operation
from ..params import AmqpParams
from aio_pika.abc import (
    AbstractRobustChannel,
    AbstractRobustQueue,
    AbstractIncomingMessage,
)

I = TypeVar("I", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)
O = TypeVar("O", bound=Union[BaseModel, None])


class Encoder(Protocol):
    """A function that turns base model into bytes"""

    def __call__(self, message: BaseModel) -> bytes: ...


class Decoder(Protocol[I]):
    """A function that turns bytes into subclass of base model using schema"""

    def __call__(self, body: bytes, schema: Type[I]) -> I: ...


@dataclass
class EndpointParams:
    pool: AmqpPool
    encode: Callable[[I], bytes]
    decode: Callable[[bytes, Type[I]], I]
    register_correlation_id: Callable[
        [], tuple[str, Awaitable[AbstractIncomingMessage]]
    ]
    app_id: str
    stop_application: Callable[[], Awaitable[None]]
    amqp_params: AmqpParams

    @property
    def reply_queue_name(self) -> str:
        return f"reply-queue-{self.app_id}"

    @property
    def error_queue_name(self) -> str:
        return self.get_error_queue(self.app_id)

    @classmethod
    def get_error_queue(cls, app_id: str) -> str:
        return f"error-queue-{app_id}"


class AbstractEndpoint(ABC, Generic[I, O]):
    def __init__(self, op: Operation, params: EndpointParams):
        self._op = op
        self._params = params

    @abstractmethod
    async def start(self):
        raise NotImplementedError

    @abstractmethod
    async def stop(self):
        raise NotImplementedError

    async def _declare(self, ch: AbstractRobustChannel) -> AbstractRobustQueue:
        ex_name = self._op.exchange_name
        ex_type = self._op.exchange_type
        q_name = self._op.routing_key

        # Debug/Test mode
        # TODO: Inject this code instead of having if-else
        if self._op.debug_auto_delete:
            q = await ch.declare_queue(
                name=q_name,
                durable=False,
                exclusive=True,
            )
            if ex_name:
                ex = await ch.declare_exchange(
                    name=ex_name,
                    type=ex_type,
                    auto_delete=True,
                )
                await q.bind(ex)
        # Production mode
        else:
            q = await ch.declare_queue(
                name=q_name,
                durable=bool(q_name),
                exclusive=not bool(q_name),
            )
            if ex_name:
                ex = await ch.declare_exchange(name=ex_name, type=ex_type)
                await q.bind(ex)
        return q

    def _create_message(
        self,
        body: bytes,
        correlation_id: Optional[str] = None,
    ) -> Message:
        return Message(
            body,
            app_id=self._params.app_id,
            correlation_id=correlation_id,
            reply_to=self._params.reply_queue_name if correlation_id else None,
        )
