from pydantic import BaseModel, Field
from typing import Any, Callable, Generic, TypeVar, Annotated, get_args

T = TypeVar("T", bound=BaseModel)


class Ref(BaseModel, Generic[T]):
    ref: Annotated[str, Field(alias="$ref")]

    @classmethod
    def type(cls) -> type[T]:
        return get_args(cls)[0]

    def get(self, context: Callable[[str], Any]) -> T:
        return self.type().model_validate(context(self.ref))
