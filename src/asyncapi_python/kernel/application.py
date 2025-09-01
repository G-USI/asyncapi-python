import asyncio

from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory
from .endpoint import AbstractEndpoint, EndpointFactory
from .codec import CodecFactory


class BaseApplication:
    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory) -> None:
        self.__endpoints: set[AbstractEndpoint] = set()
        self.__wire_factory: AbstractWireFactory = wire_factory
        self.__codec_factory: CodecFactory = codec_factory

    def _register_endpoint(self, op: Operation) -> AbstractEndpoint:
        endpoint = EndpointFactory.create(operation=op, wire_factory=self.__wire_factory, codec_factory=self.__codec_factory)
        self.__endpoints.add(endpoint)
        return endpoint

    async def start(self) -> None:
        _ = await asyncio.gather(*(e.start() for e in self.__endpoints))

    async def stop(self) -> None:
        _ = await asyncio.gather(*(e.stop() for e in self.__endpoints))


__all__ = ["BaseApplication"]
