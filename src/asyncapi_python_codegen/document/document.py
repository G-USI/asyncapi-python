from __future__ import annotations
from pydantic import BaseModel
from typing import Literal
from .bindings import Bindings
from .components import Components, Message
from .ref import Ref


class Document(BaseModel):
    asyncapi: Literal["3.0.0"]
    info: Info
    channels: dict[str, Channel] = {}
    operations: dict[str, Operation] = {}
    components: Components = Components()


class Info(BaseModel):
    title: str
    version: str
    description: str | None = None


class Channel(BaseModel):
    address: str | None = None
    title: str | None = None
    description: str | None = None
    bindings: Bindings | None = None
    messages: dict[str, Message | Ref[Message]]


class Operation(BaseModel):
    action: Literal["receive", "send"]
    channel: Ref[Channel]
    reply: OperationReply | None = None


class OperationReply(BaseModel):
    address: ReplyAddress
    channel: Ref[Channel]


class ReplyAddress(BaseModel):
    description: str | None = None
    location: str
