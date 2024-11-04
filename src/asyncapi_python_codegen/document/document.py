from __future__ import annotations
from functools import cache
from pathlib import Path

from pydantic import Field
from .base import BaseModel
from typing import Annotated, Any, Literal
from typing_extensions import Self
import yaml
from .bindings import Bindings
from .components import Components, Message
from .ref import MaybeRef, Ref


class Document(BaseModel):
    filepath: Annotated[Path, Field(exclude=True)]
    asyncapi: Literal["3.0.0"]
    info: Info
    channels: dict[str, Channel] = {}
    operations: dict[str, Operation] = {}
    components: Components = Components()

    @classmethod
    def load_yaml(cls, path: Path) -> Self:
        with path.open() as file:
            raw_doc = yaml.safe_load(file)
        raw_doc["filepath"] = path.absolute()
        return cls.model_validate(raw_doc)

    def local_context(self, path: str) -> Any:
        res = self.model_dump(by_alias=True)
        h, *paths = path.split("/")
        if h != "#":
            raise ValueError("local context function got non-local request: {path}")
        *_, res = (res := res[p] for p in paths)
        return res


class Info(BaseModel):
    title: str
    version: str
    description: str | None = None


class Channel(BaseModel):
    address: str | None = None
    title: str | None = None
    description: str | None = None
    bindings: Bindings | None = None
    messages: dict[str, MaybeRef[Message]]


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
