from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .bindings import AmqpMessageBinding
from .common import *

__all__ = [
    "CorrelationId",
    "MessageBindings",
    "MessageExample",
    "MessageTrait",
    "Message",
]


@dataclass(frozen=True)
class CorrelationId:
    description: str | None
    location: str


@dataclass(frozen=True)
class MessageBindings:
    http: Any = None
    amqp1: Any = None
    mqtt: Any = None
    nats: Any = None
    stomp: Any = None
    redis: Any = None
    solace: Any = None
    ws: Any = None
    amqp: AmqpMessageBinding | None = None
    kafka: Any = None
    anypointmq: Any = None
    jms: Any = None
    sns: Any = None
    sqs: Any = None
    ibmmq: Any = None
    googlepubsub: Any = None
    pulsar: Any = None


@dataclass(frozen=True)
class MessageExample:
    name: str | None
    summary: str | None
    headers: Any
    payload: Any


@dataclass(frozen=True)
class MessageTrait:
    content_type: str | None
    headers: Any
    summary: str | None
    name: str | None
    title: str | None
    description: str | None
    deprecated: bool | None
    examples: list[MessageExample]
    correlation_id: CorrelationId | None
    tags: list[Tag]
    externalDocs: ExternalDocs | None
    bindings: MessageBindings | None


@dataclass(frozen=True)
class Message:
    content_type: str | None
    headers: Any
    payload: Any
    summary: str | None
    name: str | None
    title: str | None
    description: str | None
    deprecated: bool | None
    correlation_id: CorrelationId | None
    tags: list[Tag]
    externalDocs: ExternalDocs | None
    bindings: MessageBindings | None
    traits: list[MessageTrait]
    key: str
