from dataclasses import dataclass
from typing import Any
from .message import Message
from .common import *

__all__ = ["AddressParameter", "ChannelBindings", "Channel"]


@dataclass
class AddressParameter:
    description: str | None
    location: str


@dataclass
class ChannelBindings:
    http: Any = None
    amqp1: Any = None
    mqtt: Any = None
    nats: Any = None
    stomp: Any = None
    redis: Any = None
    solace: Any = None
    ws: Any = None
    amqp: Any = None
    kafka: Any = None
    anypointmq: Any = None
    jms: Any = None
    sns: Any = None
    sqs: Any = None
    ibmmq: Any = None
    googlepubsub: Any = None
    pulsar: Any = None


@dataclass
class Channel:
    address: str | None
    title: str | None
    summary: str | None
    description: str | None
    servers: list[Server]
    messages: dict[str, Message]
    parameters: dict[str, AddressParameter]
    tags: list[Tag]
    external_docs: ExternalDocs | None
    bindings: ChannelBindings
