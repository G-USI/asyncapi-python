from typing import ClassVar, Literal

from typing_extensions import Unpack

from .abc import AbstractEndpoint
from .publisher import Publisher
from .rpc_client import RpcClient
from .rpc_server import RpcServer
from .subscriber import Subscriber

__all__ = [
    "AbstractEndpoint",
    "Publisher",
    "Subscriber",
    "RpcClient",
    "RpcServer",
    "EndpointFactory",
]


class EndpointFactory:
    _registry: ClassVar[
        dict[tuple[Literal["send", "receive"], bool], type[AbstractEndpoint]]
    ] = {
        ("send", False): Publisher,
        ("receive", False): Subscriber,
        ("send", True): RpcClient,
        ("receive", True): RpcServer,
    }

    @classmethod
    def create(cls, **kwargs: Unpack[AbstractEndpoint.Inputs]) -> AbstractEndpoint:
        op = kwargs["operation"]
        action, has_reply = op.action, op.reply is not None
        endpoint = cls._registry[(action, has_reply)](**kwargs)
        return endpoint
