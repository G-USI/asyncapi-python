from pydantic import BaseModel
from typing import TypeVar

T = TypeVar("T", bound=BaseModel)


def encode_message(message: T) -> bytes:
    return message.model_dump_json().encode()


def decode_message(message: bytes, schema: type[T]) -> T:
    return schema.model_validate_json(message)
