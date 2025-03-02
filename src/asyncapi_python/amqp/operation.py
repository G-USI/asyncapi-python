# Copyright 2024-2025 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
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


from typing import (
    Generic,
    Literal,
    Type,
    TypeVar,
    Union,
)
from pydantic import BaseModel
from dataclasses import dataclass, field
from asyncapi_python.utils import snake_case

ExchangeType = Literal["topic", "direct", "fanout", "default", "headers"]

I = TypeVar("I", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)
O = TypeVar("O", bound=Union[BaseModel, None])


@dataclass
class Operation(Generic[I, O]):
    name: str
    """A name of the operation from asyncapi spec"""

    message_type: Type[I]
    """A message payload"""

    reply_type: Type[O]
    """A message payload sent to the reply queue. If None, assumes no reply."""

    routing_key: Union[str, None]
    """A queue name or a routing key (depending on the operation side). 
    If no name, the queue is exclusive, otherwise it is durable."""

    exchange_name: Union[str, None]
    """A name of the exchange that the queue will be bound, and to which the message will be sent"""

    exchange_type: ExchangeType
    """An exchange type."""

    debug_auto_delete: bool = field(default=False)
    """A debug param that will force automatic deletion of the resources for this operation. Used for tests."""

    @property
    def path(self) -> tuple[str, ...]:
        """A hierarchical path of the operation, like a/b/c or a.b.c
        with empty parts of the path dropped"""
        return tuple(
            snake_case(y) for x in self.name.split("/") for y in x.split(".") if y
        )
