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


from functools import cache
from pathlib import Path
from pydantic._internal._generics import get_args  # TODO: Internal API, this may break
from pydantic import ConfigDict, Field, model_validator
from .base import BaseModel, RootModel
from .document_context import (
    current_doc_path,
    set_current_doc_path,
    DOCUMENT_CONTEXT_STACK,
)
from typing import Any, Callable, Generic, TypeVar, Annotated


T = TypeVar("T", bound=BaseModel)


ContextFunction = Callable[[str], Any]


class Ref(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    ref: Annotated[
        str,
        Field(
            alias="$ref",
            serialization_alias="$ref",
            validation_alias="$ref",
        ),
    ]
    filepath: Annotated[Path, Field(exclude=True)]
    doc_path: Annotated[tuple[str, ...], Field(exclude=True)]

    @classmethod
    def type(cls) -> type[T]:
        return get_args(cls)[0]

    @cache
    def get(self) -> T:
        from .document import Document

        doc = Document.load_yaml(self.filepath).model_dump(by_alias=True)
        for p in self.doc_path:
            doc = doc[p]

        with set_current_doc_path(self.filepath):
            if "$ref" in doc:
                return self.__class__.model_validate(doc).get()
            return self.type().model_validate(doc)

    @model_validator(mode="before")
    @classmethod
    def parse_ref(cls, data: Any) -> Any:
        fp: str | Path

        match data:
            case {"ref": ref} | {"$ref": ref} if isinstance(ref, str):
                match ref.split("#"):
                    case "", dp:
                        fp = current_doc_path()
                    case fp, dp if not Path(fp).is_absolute():
                        fp = current_doc_path().parent / fp
                    case fp, dp:
                        ...

            case x:
                raise ValueError(f"Requires {{$ref: ... }}, given {x} ")
        return {
            **data,
            "$ref": ref,
            "doc_path": dp.split("/")[1:],
            "filepath": Path(fp).absolute(),
        }


class MaybeRef(RootModel[Ref[T] | T], Generic[T]):
    root: Ref[T] | T

    def get(self) -> T:
        return self.root.get() if isinstance(self.root, Ref) else self.root
