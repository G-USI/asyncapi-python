from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, TypedDict, overload, Union
from typing_extensions import Unpack, Required, NotRequired

from ..typing import Handler, T_Input, T_Output, BatchConfig
from asyncapi_python.kernel.wire import AbstractWireFactory
from asyncapi_python.kernel.document import Operation
from asyncapi_python.kernel.codec import Codec, CodecFactory


class EndpointParams(TypedDict):
    """Optional parameters for endpoint configuration"""

    disable_handler_validation: NotRequired[
        bool
    ]  # Opt-out of handler enforcement for testing


class HandlerParams(TypedDict):
    """Parameters for message handlers"""

    pass  # Currently empty, but extensible for future parameters like queue, routing_key, etc.


class AbstractEndpoint(ABC):
    class Inputs(TypedDict):
        """Constructor parameters"""

        operation: Required[Operation]
        wire_factory: Required[AbstractWireFactory[Any, Any]]
        codec_factory: Required[CodecFactory[Any, Any]]
        endpoint_params: NotRequired[EndpointParams]  # Optional endpoint configuration

    class StartParams(TypedDict):
        """Parameters for starting an endpoint"""

        exception_callback: NotRequired[Callable[[Exception], None]]
        """Callback to propagate exceptions"""

    def __init__(self, **kwargs: Unpack[Inputs]):
        self._operation = kwargs["operation"]
        self._wire = kwargs["wire_factory"]
        codec_factory = kwargs["codec_factory"]
        # Endpoint sets its own defaults - empty dict if not provided
        self._endpoint_params = kwargs.get("endpoint_params", {})
        self._exception_callback: Callable[[Exception], None] | None = None

        # Create codecs for operation messages
        self._codecs: list[Codec[Any, Any]] = [
            codec_factory.create(msg) for msg in self._operation.messages
        ]

        # Create codecs for reply messages if reply exists
        self._reply_codecs: list[Codec[Any, Any]] = (
            [codec_factory.create(msg) for msg in self._operation.reply.messages]
            if self._operation.reply
            else []
        )

    def _encode_message(self, payload: Any) -> Any:
        """Encode using main message codecs"""
        return self._try_codecs(self._codecs, "encode", payload)

    def _decode_message(self, payload: Any) -> Any:
        """Decode using main message codecs"""
        return self._try_codecs(self._codecs, "decode", payload)

    def _encode_reply(self, payload: Any) -> Any:
        """Encode using reply codecs"""
        if not self._reply_codecs:
            raise RuntimeError("No reply codecs - operation has no reply")
        return self._try_codecs(self._reply_codecs, "encode", payload)

    def _decode_reply(self, payload: Any) -> Any:
        """Decode using reply codecs"""
        if not self._reply_codecs:
            raise RuntimeError("No reply codecs - operation has no reply")
        return self._try_codecs(self._reply_codecs, "decode", payload)

    def _should_validate_handlers(self) -> bool:
        """Check if handler validation should be performed"""
        return not self._endpoint_params.get("disable_handler_validation", False)

    def _try_codecs(
        self, codecs: list[Codec[Any, Any]], operation: str, payload: Any
    ) -> Any:
        """Try operation with each codec in sequence until one succeeds"""
        if not codecs:
            raise RuntimeError("No codecs available")

        last_error = None

        for codec in codecs:
            try:
                if operation == "encode":
                    return codec.encode(payload)
                else:  # decode
                    return codec.decode(payload)
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(
            f"Failed to {operation} payload with any available codec. Last error: {last_error}"
        )

    @abstractmethod
    async def start(self, **params: Unpack[StartParams]) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...


class Send(ABC, Generic[T_Input, T_Output]):
    """An interface that sending endpoint implements"""

    class RouterInputs(TypedDict):
        """Base inputs for send endpoints. Router subclasses can extend this with specific parameters."""

        pass  # Empty for now, extensible for future fields

    @abstractmethod
    async def __call__(
        self, payload: T_Input, /, **kwargs: Unpack[RouterInputs]
    ) -> T_Output: ...


class Receive(ABC, Generic[T_Input, T_Output]):

    @overload
    def __call__(
        self, fn: Handler[T_Input, T_Output]
    ) -> Handler[T_Input, T_Output]: ...

    @overload
    def __call__(
        self,
        fn: None = None,
        *,
        batch: BatchConfig,
        **kwargs: Unpack[HandlerParams],
    ) -> Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]]: ...

    @overload
    def __call__(
        self, fn: None = None, **kwargs: Unpack[HandlerParams]
    ) -> Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]]: ...

    @abstractmethod
    def __call__(
        self,
        fn: Handler[T_Input, T_Output] | None = None,
        *,
        batch: BatchConfig | None = None,
        **kwargs: Unpack[HandlerParams],
    ) -> Union[
        Handler[T_Input, T_Output],
        Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]],
    ]: ...
