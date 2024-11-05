from __future__ import annotations
from pathlib import Path

from pydantic import Field
from .base import BaseModel
from typing import Annotated, Any, Literal
import yaml
from .components import Channel, Components, Message, Operation
from .ref import MaybeRef, Ref
from .document_context import set_current_doc_path


DOCUMENT_CACHE: dict[Path, Document] = {}


class Document(BaseModel):
    filepath: Annotated[Path, Field(exclude=True)]
    asyncapi: Literal["3.0.0"]
    info: Info
    channels: dict[str, Channel] = {}
    operations: dict[str, MaybeRef[Operation]] = {}
    components: Components = Components()

    @staticmethod
    def load_yaml(path: Path) -> "Document":
        path = path.absolute()
        if path in DOCUMENT_CACHE:
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
