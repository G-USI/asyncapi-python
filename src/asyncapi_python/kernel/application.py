import asyncio
from typing import TypedDict
from typing_extensions import Unpack, Required, NotRequired

from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory
from .endpoint import AbstractEndpoint, EndpointFactory
from .endpoint.abc import EndpointParams
from .codec import CodecFactory


class BaseApplication:
    class Inputs(TypedDict):
        wire_factory: Required[AbstractWireFactory]
        codec_factory: Required[CodecFactory]
        endpoint_params: NotRequired[EndpointParams]

    def __init__(self, **kwargs: Unpack[Inputs]) -> None:
        self.__endpoints: set[AbstractEndpoint] = set()
        self.__wire_factory: AbstractWireFactory = kwargs["wire_factory"]
        self.__codec_factory: CodecFactory = kwargs["codec_factory"]
        self.__endpoint_params: EndpointParams = kwargs.get("endpoint_params", {})

    def _register_endpoint(self, op: Operation) -> AbstractEndpoint:
        endpoint = EndpointFactory.create(
            operation=op,
            wire_factory=self.__wire_factory,
            codec_factory=self.__codec_factory,
            endpoint_params=self.__endpoint_params,
        )
        self.__endpoints.add(endpoint)
        return endpoint

    async def start(self, *, blocking: bool = False) -> None:
        """Start all endpoints in the application.
        
        Args:
            blocking: If True, block until stop() is called or process is interrupted.
                     If False (default), return immediately after starting endpoints.
        """
        _ = await asyncio.gather(*(e.start() for e in self.__endpoints))
        
        if blocking:
            # Block until stop() is called or process is interrupted
            self._stop_event = asyncio.Event()
            try:
                await self._stop_event.wait()
            except asyncio.CancelledError:
                # Handle graceful shutdown on cancellation
                await self.stop()
                raise

    async def stop(self) -> None:
        """Stop all endpoints in the application."""
        _ = await asyncio.gather(*(e.stop() for e in self.__endpoints))
        
        # Signal the blocking start() method to exit if it's waiting
        if hasattr(self, '_stop_event'):
            self._stop_event.set()

    def _add_endpoint(self, endpoint: AbstractEndpoint) -> None:
        """Add an endpoint to this application."""
        self.__endpoints.add(endpoint)


__all__ = ["BaseApplication"]
