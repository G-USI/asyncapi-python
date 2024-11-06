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
