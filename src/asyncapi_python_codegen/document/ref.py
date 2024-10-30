from pydantic._internal._generics import get_args  # TODO: Internal API, this may break
from pydantic import BaseModel, Field, RootModel
from typing import Any, Callable, Generic, TypeVar, Annotated

T = TypeVar("T", bound=BaseModel)


ContextFunction = Callable[[str], Any]


class Ref(BaseModel, Generic[T]):
    ref: Annotated[str, Field(alias="$ref")]

    @classmethod
    def type(cls) -> type[T]:
        return get_args(cls)[0]

    def get(self, context: ContextFunction) -> T:
        return self.type().model_validate(context(self.ref))


class MaybeRef(RootModel[Ref[T] | T], Generic[T]):
    root: Ref[T] | T

    def get(self, context: ContextFunction) -> T:
        return self.root.get(context) if isinstance(self.root, Ref) else self.root
