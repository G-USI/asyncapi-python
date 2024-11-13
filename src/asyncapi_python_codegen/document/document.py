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
from pathlib import Path

from pydantic import Field
from .base import BaseModel
from typing import Annotated, Any, Literal, Optional
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
    description: Optional[str] = None
