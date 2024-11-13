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


from __future__ import annotations

from .base import BaseModel, RootModel
from typing import Any, Literal, Optional
from .ref import MaybeRef, Ref
from .bindings import Bindings


class Components(BaseModel):
    operations: dict[str, MaybeRef[Operation]] = {}
    channels: dict[str, MaybeRef[Channel]] = {}
    messages: dict[str, MaybeRef[Message]] = {}
    correlation_ids: dict[str, CorrelationId] = {}
    schemas: dict[str, MaybeRef[JsonSchema]] = {}


class JsonSchema(RootModel):
    # TODO: Create a better parser for JsonSchema
    root: Any


class Message(BaseModel):
    title: Optional[str] = None
    headers: Optional[MaybeRef[JsonSchema]] = None
    payload: MaybeRef[JsonSchema]


class CorrelationId(BaseModel):
    description: Optional[str] = None
    location: str


class Operation(BaseModel):
    action: Literal["receive", "send"]
    channel: Ref[Channel]
    reply: Optional[OperationReply] = None


class OperationReply(BaseModel):
    address: Optional[ReplyAddress] = None
    channel: Ref[Channel]


class ReplyAddress(BaseModel):
    description: Optional[str] = None
    location: str


class Channel(BaseModel):
    address: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    bindings: Optional[Bindings] = None
    messages: dict[str, MaybeRef[Message]]
