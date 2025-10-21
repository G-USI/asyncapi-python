import asyncio
from typing import Any, TypedDict

from typing_extensions import NotRequired, Required, Unpack

from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

from .codec import CodecFactory
from .endpoint import AbstractEndpoint, EndpointFactory
from .endpoint.abc import EndpointParams


class BaseApplication:
    class Inputs(TypedDict):
        wire_factory: Required[AbstractWireFactory[Any, Any]]
        codec_factory: Required[CodecFactory[Any, Any]]
        endpoint_params: NotRequired[EndpointParams]

    def __init__(self, **kwargs: Unpack[Inputs]) -> None:
        self.__endpoints: set[AbstractEndpoint] = set()
        self.__wire_factory: AbstractWireFactory[Any, Any] = kwargs["wire_factory"]
        self.__codec_factory: CodecFactory[Any, Any] = kwargs["codec_factory"]
        self.__endpoint_params: EndpointParams = kwargs.get("endpoint_params", {})
        self._stop_event: asyncio.Event | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._exception_future: asyncio.Future[Exception] | None = None

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
        await asyncio.gather(
            *(
                e.start(exception_callback=self._propagate_exception)
                for e in self.__endpoints
            )
        )

        if blocking:
            # Block until stop() is called or process is interrupted
            self._stop_event = asyncio.Event()
            self._exception_future = asyncio.Future()

            try:
                # Create tasks for both conditions
                stop_task = asyncio.create_task(self._stop_event.wait())

                # Convert Future to awaitable
                async def _wait_for_exception():
                    if self._exception_future is None:
                        # Create a never-completing future if no exception future exists
                        await asyncio.Event().wait()
                        return  # This line will never be reached
                    return await asyncio.wrap_future(self._exception_future)

                exception_task = asyncio.create_task(_wait_for_exception())

                # Wait for either stop event or exception
                _, pending = await asyncio.wait(
                    [stop_task, exception_task], return_when=asyncio.FIRST_COMPLETED
                )
                # Cancel remaining tasks
                for task in pending:
                    task.cancel()

                # Check if an exception was raised
                if exception_task.done() and not exception_task.cancelled():
                    exc = exception_task.result()
                    if exc is not None:
                        await self.stop()
                        raise exc

            except asyncio.CancelledError:
                # Handle graceful shutdown on cancellation
                await self.stop()
                raise

    async def stop(self) -> None:
        """Stop all endpoints in the application."""
        await asyncio.gather(*(e.stop() for e in self.__endpoints))

        # Signal the blocking start() method to exit if it's waiting
        if self._stop_event:
            self._stop_event.set()

    def _add_endpoint(self, endpoint: AbstractEndpoint) -> None:
        """Add an endpoint to this application."""
        self.__endpoints.add(endpoint)

    def _propagate_exception(self, exception: Exception) -> None:
        """Propagate exception from endpoint to application level."""
        if self._exception_future and not self._exception_future.done():
            self._exception_future.set_result(exception)


__all__ = ["BaseApplication"]
