from __future__ import annotations
from pydantic import BaseModel
from typing import Any


class Components(BaseModel):
    messages: dict[str, Message] = {}
    correlation_ids: dict[str, CorrelationId] = {}


JsonSchema = Any


class Message(BaseModel):
    headers: JsonSchema
    payload: JsonSchema


class CorrelationId(BaseModel):
    description: str | None = None
    location: str
