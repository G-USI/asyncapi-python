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

from pydantic import model_validator

from .base import BaseModel
from typing import Any, Literal
from .ref import MaybeRef, Ref
from .bindings import Bindings


class Components(BaseModel):
    operations: dict[str, MaybeRef[Operation]] = {}
    channels: dict[str, MaybeRef[Channel]] = {}
    messages: dict[str, MaybeRef[Message]] = {}
    correlation_ids: dict[str, CorrelationId] = {}


class JsonSchema(BaseModel):
    # TODO: Create a better parser for JsonSchema
    type: str
    properties: dict[str, Any]
    required: list[str] = []


class Message(BaseModel):
    title: str
    headers: MaybeRef[JsonSchema] | None = None
    payload: MaybeRef[JsonSchema]

    @model_validator(mode="before")
    @classmethod
    def has_title(cls, data: dict[str, Any]):
        if not "title" in data:
            raise AssertionError(
                "As of now, all Message objects require "
                + "`title` field to be present to uniquely identify data types. "
                + "This limitation will be removed in the future."
            )
        return data


class CorrelationId(BaseModel):
    description: str | None = None
    location: str


class Operation(BaseModel):
    action: Literal["receive", "send"]
    channel: Ref[Channel]
    reply: OperationReply | None = None


class OperationReply(BaseModel):
    address: ReplyAddress | None = None
    channel: Ref[Channel]


class ReplyAddress(BaseModel):
    description: str | None = None
    location: str


class Channel(BaseModel):
    address: str | None = None
    title: str | None = None
    description: str | None = None
    bindings: Bindings | None = None
    messages: dict[str, MaybeRef[Message]]
