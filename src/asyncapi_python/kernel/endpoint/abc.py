from abc import ABC, abstractmethod
from typing import Callable, Generic, TypedDict, overload
from typing_extensions import Unpack

from asyncapi_python.kernel.document.message import Message
from ..typing import Handler, T_Input, T_Output
from asyncapi_python.kernel.wire import AbstractWireFactory
from asyncapi_python.kernel.document import Operation
from asyncapi_python.kernel.codec import Codec, CodecFactory


class HandlerParams(TypedDict, total=False):
    """Parameters for message handlers"""

    pass


class AbstractEndpoint(ABC):
    class Inputs(TypedDict):
        operation: Operation
        wire_factory: AbstractWireFactory
        codec_factory: CodecFactory

    def __init__(self, **kwargs: Unpack[Inputs]):
        self._operation = kwargs["operation"]
        self._wire = kwargs["wire_factory"]
        codec_factory = kwargs["codec_factory"]

        # Create codecs for operation messages
        self._codecs: list[Codec] = [
            codec_factory.create(msg) for msg in self._operation.messages
        ]

        # Create codecs for reply messages if reply exists
        self._reply_codecs: list[Codec] = (
            [codec_factory.create(msg) for msg in self._operation.reply.messages]
            if self._operation.reply
            else []
        )

    def _encode_message(self, payload):
        """Encode using main message codecs"""
        return self._try_codecs(self._codecs, "encode", payload)

    def _decode_message(self, payload):
        """Decode using main message codecs"""
        return self._try_codecs(self._codecs, "decode", payload)

    def _encode_reply(self, payload):
        """Encode using reply codecs"""
        if not self._reply_codecs:
            raise RuntimeError("No reply codecs - operation has no reply")
        return self._try_codecs(self._reply_codecs, "encode", payload)

    def _decode_reply(self, payload):
        """Decode using reply codecs"""
        if not self._reply_codecs:
            raise RuntimeError("No reply codecs - operation has no reply")
        return self._try_codecs(self._reply_codecs, "decode", payload)

    def _try_codecs(self, codecs: list[Codec], operation: str, payload):
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
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...


class Send(ABC, Generic[T_Input, T_Output]):
    """An interface that sending endpoint implements"""

    @abstractmethod
    async def __call__(self, payload: T_Input) -> T_Output: ...


class Receive(ABC, Generic[T_Input, T_Output]):

    @overload
    def __call__(
        self, fn: Handler[T_Input, T_Output]
    ) -> Handler[T_Input, T_Output]: ...

    @overload
    def __call__(
        self, fn: None = None, **kwargs: Unpack[HandlerParams]
    ) -> Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]]: ...

    @abstractmethod
    def __call__(
        self,
        fn: Handler[T_Input, T_Output] | None = None,
        **kwargs: Unpack[HandlerParams],
    ) -> (
        Handler[T_Input, T_Output]
        | Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]]
    ): ...
