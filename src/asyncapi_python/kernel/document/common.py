from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalDocs:
    description: str
    url: str


@dataclass(frozen=True)
class Tag:
    name: str
    description: str
    external_docs: ExternalDocs


@dataclass(frozen=True)
class Server:
    key: str  # TODO: Implement full Server spec


__all__ = ["ExternalDocs", "Tag", "Server"]
