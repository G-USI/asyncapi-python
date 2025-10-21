from abc import ABC, abstractmethod
from typing import Generic, TypedDict

from typing_extensions import NotRequired, Unpack

from ..document import Channel, OperationBindings
from ..typing import T_Recv, T_Send
from .typing import Consumer, Producer


class EndpointParams(TypedDict):
    channel: Channel
    parameters: dict[str, str]
    op_bindings: OperationBindings | None
    is_reply: bool
    app_id: NotRequired[str]  # Optional app_id for queue naming


class AbstractWireFactory(ABC, Generic[T_Send, T_Recv]):
    @abstractmethod
    async def create_consumer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Consumer[T_Recv]: ...

    @abstractmethod
    async def create_producer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Producer[T_Send]: ...
