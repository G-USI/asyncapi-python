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


from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, RootModel


class Exchange(BaseModel):
    name: Optional[str] = None
    type: Literal["topic", "direct", "fanout", "default", "headers"] = "default"
    durable: bool = False
    auto_delete: bool = Field(alias="autoDelete", default=False)


class ExchangeBinding(BaseModel):
    type: Literal["routingKey"] = Field(alias="is", default="routingKey")
    exchange: Exchange = Exchange()


class Queue(BaseModel):
    name: Optional[str] = None
    durable: bool = False
    exclusive: bool = False
    auto_delete: bool = Field(alias="autoDelete", default=False)


class QueueBinding(BaseModel):
    type: Literal["queue"] = Field(alias="is", default="queue")
    queue: Queue = Queue()


class AmqpBinding(RootModel):
    root: Union[ExchangeBinding, QueueBinding] = QueueBinding()
