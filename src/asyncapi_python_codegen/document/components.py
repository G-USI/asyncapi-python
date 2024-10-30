from __future__ import annotations
from .base import BaseModel
from typing import Any
from .ref import MaybeRef


class Components(BaseModel):
    messages: dict[str, Message] = {}
    correlation_ids: dict[str, CorrelationId] = {}


class JsonSchema(BaseModel):
    # TODO: Create a better parser for JsonSchema
    type: str
    properties: dict[str, Any]
    required: list[str] = []


class Message(BaseModel):
    headers: MaybeRef[JsonSchema] | None = None
    payload: MaybeRef[JsonSchema]


class CorrelationId(BaseModel):
    description: str | None = None
    location: str
