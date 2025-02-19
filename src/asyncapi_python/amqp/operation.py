from typing import (
    Generic,
    Literal,
    Type,
    TypeVar,
    Union,
)
from pydantic import BaseModel
from dataclasses import dataclass

ExchangeType = Literal["topic", "direct", "fanout", "default", "headers"]

I = TypeVar("I", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)
O = TypeVar("O", bound=Union[BaseModel, None])


@dataclass
class Operation(Generic[I, O]):
    name: str
    """A name of the operation from asyncapi spec"""

    message_type: Type[I]
    """A message payload"""

    reply_type: Type[O]
    """A message payload sent to the reply queue. If None, assumes no reply."""

    routing_key: Union[str, None]
    """A queue name or a routing key (depending on the operation side). 
    If no name, the queue is exclusive, otherwise it is durable."""

    exchange_name: Union[str, None]
    """A name of the exchange that the queue will be bound, and to which the message will be sent"""

    exchange_type: ExchangeType
    """An exchange type."""
