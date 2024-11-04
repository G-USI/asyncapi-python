from __future__ import annotations
from pathlib import Path

from pydantic import Field
from .base import BaseModel
from typing import Annotated, Any, Literal
import yaml
from .bindings import Bindings
from .components import Components, Message
from .ref import MaybeRef, Ref
from .document_context import set_current_doc_path


DOCUMENT_CACHE: dict[Path, Document] = {}


class Document(BaseModel):
    filepath: Annotated[Path, Field(exclude=True)]
    asyncapi: Literal["3.0.0"]
    info: Info
    channels: dict[str, Channel] = {}
    operations: dict[str, Operation] = {}
    components: Components = Components()

    @staticmethod
    def load_yaml(path: Path) -> "Document":
        path = path.absolute()
        if path in DOCUMENT_CACHE:
            print("REUSING CACHE")
            return DOCUMENT_CACHE[path]
        with path.open() as file:
            raw_doc = yaml.safe_load(file)
        raw_doc["filepath"] = path.absolute()
        with set_current_doc_path(path):
            doc = Document.model_validate(raw_doc)
        DOCUMENT_CACHE[path] = doc
        return doc


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
    address: ReplyAddress | None = None
    channel: Ref[Channel]


class ReplyAddress(BaseModel):
    description: str | None = None
    location: str
