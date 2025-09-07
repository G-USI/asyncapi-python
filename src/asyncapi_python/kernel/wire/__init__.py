from .typing import Producer, Consumer
from ..typing import T_Recv, T_Send
from typing import Generic, TypedDict
from typing_extensions import Unpack
from abc import abstractmethod, ABC
from ..document import Channel, OperationBindings


class EndpointParams(TypedDict):
    channel: Channel
    parameters: dict[str, str]
    op_bindings: OperationBindings | None
    is_reply: bool


class AbstractWireFactory(ABC, Generic[T_Send, T_Recv]):
    @abstractmethod
    async def create_consumer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Consumer[T_Recv]: ...

    @abstractmethod
    async def create_producer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Producer[T_Send]: ...
