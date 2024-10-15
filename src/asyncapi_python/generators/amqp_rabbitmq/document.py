from __future__ import annotations
from functools import cached_property
from typing import Any, Literal
from pydantic import BaseModel, RootModel, computed_field, field_validator
import subprocess
from io import StringIO
import json


class Document(BaseModel):
    asyncapi: Literal["3.0.0"]
    info: Info
    channels: dict[str, Channel]

    @computed_field  # type: ignore[misc]
    @cached_property
    def message_spec(self) -> dict[str, Any]:
        result = {}
        for channel in self.channels.values():
            for message in channel.messages.values():
                result[message.payload.title] = message.payload.model_dump()
        return {"$schema": "http://json-schema.org/draft-07/schema#", "$defs": result}

    @computed_field  # type: ignore[misc]
    @cached_property
    def dto_code(self) -> str:
        return subprocess.run(
            check=True,
            capture_output=True,
            input=json.dumps(self.message_spec).encode(),
            args=[
                "datamodel-codegen",
                "--output-model-type",
                "pydantic_v2.BaseModel",
            ],
        ).stdout.decode()


class Info(BaseModel):
    version: str
    description: str | None = None


class Channel(BaseModel):
    messages: dict[str, Message]


class Message(BaseModel):
    payload: MessageSchema


class MessageSchema(RootModel):
    root: dict[str, Any]

    @field_validator("root")
    @classmethod
    def title_is_present(cls, v: dict[str, Any]) -> dict[str, Any]:
        err = (
            "All message payload schemas must have",
            "`title` field to derive typenames in the code",
        )
        assert "title" in v, " ".join(err)
        return v

    @computed_field  # type: ignore[misc]
    @property
    def title(self) -> str:
        return self.root["title"]
