from dataclasses import dataclass
from typing import Any, Literal

from .bindings import AmqpOperationBinding
from .channel import Channel
from .common import *
from .message import Message

__all__ = [
    "SecurityScheme",
    "OperationReplyAddress",
    "OperationReply",
    "OperationBindings",
    "OperationTrait",
    "Operation",
]


@dataclass(frozen=True)
class SecurityScheme:
    type: Literal[
        "userPassword",
        "apiKey",
        "X509",
        "symmetricEncryption",
        "asymmetricEncryption",
        "oauth2Flows",
        "openIdConnect",
        "HTTPSecurityScheme",
        "SaslSecurityScheme",
    ]
    key: str


@dataclass(frozen=True)
class OperationReplyAddress:
    location: str
    description: str | None


@dataclass(frozen=True)
class OperationReply:
    channel: Channel
    messages: list[Message]
    address: str | None


@dataclass(frozen=True)
class OperationBindings:
    # TODO: Reproduce full schema here
    http: Any = None
    amqp1: Any = None
    mqtt: Any = None
    nats: Any = None
    stomp: Any = None
    redis: Any = None
    solace: Any = None
    ws: Any = None
    amqp: AmqpOperationBinding | None = None
    kafka: Any = None
    anypointmq: Any = None
    jms: Any = None
    sns: Any = None
    sqs: Any = None
    ibmmq: Any = None
    googlepubsub: Any = None
    pulsar: Any = None


@dataclass(frozen=True)
class OperationTrait:
    title: str | None
    summary: str | None
    description: str | None
    channel: Channel
    security: list[SecurityScheme]
    tags: list[Tag]
    external_docs: ExternalDocs | None
    bindings: OperationBindings


@dataclass(frozen=True)
class Operation:
    action: Literal["send", "receive"]
    title: str | None
    summary: str | None
    description: str | None
    channel: Channel
    messages: list[Message]
    reply: OperationReply | None
    traits: list[OperationTrait]
    security: list[SecurityScheme]
    tags: list[Tag]
    external_docs: ExternalDocs | None
    bindings: OperationBindings | None
    key: str
