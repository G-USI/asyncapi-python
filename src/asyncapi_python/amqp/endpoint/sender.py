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
from typing import Any, TypeVar, Union

from pydantic import BaseModel
from .base import AbstractEndpoint
from aio_pika import Message


I = TypeVar("I", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)
O = TypeVar("O", bound=Union[BaseModel, None])


class AbstractSender(AbstractEndpoint[I, O]):
    async def start(self):
        async with self._params.pool.acquire() as ch:
            q = await self._declare(ch)
            if q.exclusive:
                await q.delete()

    async def stop(self): ...

    @abstractmethod
    async def __call__(self, message: I) -> O:
        raise NotImplementedError

    async def validate_and_call(self, message: Any) -> O:
        return await self(self._op.message_type.model_validate(message))

    async def validate_json_and_call(self, message: Union[str, bytes, bytearray]) -> O:
        return await self(self._op.message_type.model_validate_json(message))


class Sender(AbstractSender[I, None]):
    async def __call__(self, message: I) -> None:
        ex_n = self._op.exchange_name or ""
        q_n = self._op.routing_key or ""
        body = self._params.encode(message)
        async with self._params.pool.acquire() as ch:
            ex = await ch.get_exchange(ex_n) if ex_n else ch.default_exchange
            await ex.publish(self._create_message(body), q_n)


class RpcSender(AbstractSender[I, U]):
    async def __call__(self, message: I) -> U:
        ex_n = self._op.exchange_name
        q_n = self._op.routing_key or ""
        body = self._params.encode(message)
        corr_id, future = self._params.register_correlation_id()
        async with self._params.pool.acquire() as ch:
            ex = await ch.get_exchange(ex_n) if ex_n else ch.default_exchange
            await ex.publish(self._create_message(body, corr_id), q_n)
            res = await future
        return self._params.decode(res.body, self._op.reply_type)
