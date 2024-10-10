from typing import Any, Literal
from pydantic import BaseModel, RootModel


class Schema(RootModel):
    root: dict[str, Any]


class Message(BaseModel):
    payload: Schema


class Channel(BaseModel):
    address: str
    messages: dict[str, Message]


class Document(BaseModel):
    asyncapi: Literal["3.0.0"]
    channels: dict[str, Channel]
