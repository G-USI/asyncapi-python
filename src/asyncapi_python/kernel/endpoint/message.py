from dataclasses import dataclass
from typing import Any


@dataclass
class WireMessage:
    """Simple wire message implementation"""

    _payload: bytes
    _headers: dict[str, Any]
    _correlation_id: str | None = None
    _reply_to: str | None = None

    @property
    def payload(self) -> bytes:
        return self._payload

    @property
    def headers(self) -> dict[str, Any]:
        return self._headers

    @property
    def correlation_id(self) -> str | None:
        return self._correlation_id

    @property
    def reply_to(self) -> str | None:
        return self._reply_to
