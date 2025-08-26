from typing import ClassVar, Literal
from typing_extensions import Unpack
from .abc import AbstractEndpoint
from asyncapi_python.kernel.document import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory
from asyncapi_python.kernel.codec import CodecFactory
from .publisher import Publisher

# from .subscriber import Subscriber
# from .rpc_client import Client
# from .rpc_server import Server


class EndpointFactory:
    _registry: ClassVar[
        dict[tuple[Literal["send", "receive"], bool], type[AbstractEndpoint]]
    ] = {
        ("send", False): Publisher,
        # ("receive", False): Subscriber,
        # ("send", True): Client,
        # ("receive", True): Server,
    }

    @classmethod
    def create(cls, **kwargs: Unpack[AbstractEndpoint.Inputs]) -> AbstractEndpoint:
        op = kwargs["operation"]
        action, has_reply = op.action, op.reply is not None
        endpoint = cls._registry[(action, has_reply)](**kwargs)
        return endpoint
