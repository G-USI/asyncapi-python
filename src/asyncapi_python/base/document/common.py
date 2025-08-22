from dataclasses import dataclass


@dataclass
class ExternalDocs:
    description: str
    url: str


@dataclass
class Tag:
    name: str
    description: str
    external_docs: ExternalDocs


@dataclass
class Server: ...  # TODO: Implement Server spec


__all__ = ["ExternalDocs", "Tag", "Server"]
