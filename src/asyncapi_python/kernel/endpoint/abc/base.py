from abc import ABC, abstractmethod
from typing import Any, Callable, TypedDict

from typing_extensions import NotRequired, Required, Unpack

from asyncapi_python.kernel.codec import Codec, CodecFactory
from asyncapi_python.kernel.document import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

from .params import EndpointParams

__all__ = ["AbstractEndpoint"]


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

    def _extract_parameters(self, payload: Any) -> dict[str, str]:
        """Extract channel parameters from decoded payload.

        Uses the channel parameter definitions to extract values from the payload
        using the codec's extract_field method. Parameters without a location are skipped.

        Args:
            payload: The decoded message payload

        Returns:
            Dictionary mapping parameter names to extracted string values

        Raises:
            ValueError: If parameter extraction fails for any parameter
        """
        parameters: dict[str, str] = {}
        for param_name, param_def in self._operation.channel.parameters.items():
            if param_def.location:
                try:
                    # Use first codec (all should extract consistently)
                    codec = self._codecs[0]
                    value = codec.extract_field(payload, param_def.location)
                    parameters[param_name] = value
                except ValueError as e:
                    raise ValueError(f"Failed to extract parameter '{param_name}': {e}")
        return parameters

    def _build_address(self, parameters: dict[str, str]) -> str:
        """Build address from channel template and parameters.

        Replaces {param_name} placeholders in the channel address with the
        corresponding parameter values.

        Args:
            parameters: Dictionary of parameter names to values

        Returns:
            The fully resolved address string

        Raises:
            ValueError: If channel address is None
        """
        address = self._operation.channel.address
        if address is None:
            raise ValueError(
                "Channel address is None, cannot build parameterized address"
            )
        for param_name, param_value in parameters.items():
            address = address.replace(f"{{{param_name}}}", param_value)
        return address

    def _build_address_with_parameters(self, payload: Any) -> str | None:
        """Extract parameters from payload and build address if needed.

        Convenience method that extracts parameters and builds the address in one call.
        Returns None if no parameters are defined or extracted.

        Args:
            payload: The decoded message payload

        Returns:
            The resolved address string, or None if no parameters to extract

        Raises:
            ValueError: If parameter extraction or address building fails
        """
        parameters = self._extract_parameters(payload)
        return self._build_address(parameters) if parameters else None

    @abstractmethod
    async def start(self, **params: Unpack[StartParams]) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...
