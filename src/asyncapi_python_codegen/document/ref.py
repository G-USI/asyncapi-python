from pathlib import Path
from pydantic._internal._generics import get_args  # TODO: Internal API, this may break
from pydantic import BeforeValidator, Field, ValidationInfo, model_validator
from .base import BaseModel, RootModel
from typing import Any, Callable, Generic, TypeVar, Annotated, cast, TYPE_CHECKING


T = TypeVar("T", bound=BaseModel)


ContextFunction = Callable[[str], Any]


class Ref(BaseModel, Generic[T]):
    ref: Annotated[str, Field(alias="$ref")]
    filepath: Path | None
    doc_path: tuple[str, ...]

    @classmethod
    def type(cls) -> type[T]:
        return get_args(cls)[0]

    def get(self, context: ContextFunction) -> T:
        return self.type().model_validate(context(self.ref))

    @model_validator(mode="before")
    @classmethod
    def parse_ref(cls, data: Any) -> Any:
        match data:
            case {"$ref": ref} if isinstance(ref, str):
                match ref.split("#"):
                    case fp, dp:
                        ...
                    case dp,:
                        fp = "/"
            case x:
                raise ValueError(f"Requires {{$ref: ... }}, given {x} ")
        return {**data, "doc_path": dp.split("/")[1:], "filepath": Path(fp).absolute()}


class MaybeRef(RootModel[Ref[T] | T], Generic[T]):
    root: Ref[T] | T

    def get(self, context: ContextFunction) -> T:
        return self.root.get(context) if isinstance(self.root, Ref) else self.root
