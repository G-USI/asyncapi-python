from __future__ import annotations

from .bindings import Bindings

from typing import Any
from pydantic import BaseModel, RootModel, field_validator, computed_field


class Channel(BaseModel):
    bindings: Bindings = Bindings()
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
