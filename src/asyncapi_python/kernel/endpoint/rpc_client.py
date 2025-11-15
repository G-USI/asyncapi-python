import asyncio
from typing import Generic
from uuid import uuid4

from typing_extensions import NotRequired, Unpack

from asyncapi_python.kernel.wire import Producer

from ..typing import IncomingMessage, T_Input, T_Output
from .abc import AbstractEndpoint, Send
from .exceptions import TimeoutError, UninitializedError
from .message import WireMessage
from .rpc_reply_handler import global_reply_handler


class RpcClient(AbstractEndpoint, Send[T_Input, T_Output], Generic[T_Input, T_Output]):
    """RPC client endpoint for request/response pattern

    Sends requests with correlation IDs and waits for responses
    on a shared global reply queue. All RPC client instances share
    a single reply consumer and background task for efficiency.
    """

    class RouterInputs(Send.RouterInputs):
        """Router inputs for RPC client, extending Send.RouterInputs with timeout"""

        timeout: NotRequired[
            float | None
        ]  # Timeout in seconds for this RPC request, or None to disable timeout

    def __init__(self, **kwargs: Unpack[AbstractEndpoint.Inputs]):
        super().__init__(**kwargs)
        # Instance-specific state
        self._producer: Producer[WireMessage] | None = None

    async def start(self, **params: Unpack[AbstractEndpoint.StartParams]) -> None:
        """Initialize the RPC client endpoint"""
        if self._producer:
            return

        # Get exception callback from parameters
        self._exception_callback = params.get("exception_callback")

        # Validate we have codecs for messages and replies
        if not self._codecs:
            raise RuntimeError("Operation has no named messages")
        if not self._reply_codecs:
            raise RuntimeError("Operation has no reply messages")

        # Increment instance count and ensure global reply handler
        global_reply_handler.increment_instance_count()

        # Ensure global reply handling is set up (only happens once)
        await global_reply_handler.ensure_reply_handler(
            self._wire, self._operation, self._endpoint_params
        )

        # Extract service_name from endpoint_params for app_id
        service_name = self._endpoint_params.get("service_name", "app")

        # Create instance-specific producer for sending requests
        self._producer = await self._wire.create_producer(
            channel=self._operation.channel,
            parameters={},
            op_bindings=self._operation.bindings,
            is_reply=False,
            app_id=service_name,
        )

        # Start producer
        if self._producer:
            await self._producer.start()

    async def stop(self) -> None:
        """Cleanup the RPC client endpoint"""
        # Stop instance producer
        if self._producer:
            await self._producer.stop()
            self._producer = None

        # Decrement count and cleanup if last instance
        remaining_count = global_reply_handler.decrement_instance_count()
        if remaining_count == 0:
            await global_reply_handler.cleanup_if_last_instance()

    async def __call__(  # type: ignore[override]
        self, payload: T_Input, /, **kwargs: Unpack[RouterInputs]
    ) -> T_Output:
        """Send an RPC request and wait for response using global reply handling

        Args:
            payload: The request payload to send
            **kwargs: Router inputs including optional timeout:
                     - Not provided: uses default_rpc_timeout from endpoint_params (default: 180.0)
                     - float: uses the specified timeout in seconds
                     - None: disables timeout (waits indefinitely)

        Returns:
            The response payload

        Raises:
            TimeoutError: If response not received within timeout
            UninitializedError: If endpoint not started
        """
        if not self._producer:
            raise UninitializedError()

        # Determine timeout: use provided value, or fall back to endpoint_params default
        if "timeout" in kwargs:
            # Explicitly provided (could be float or None)
            timeout = kwargs["timeout"]
        else:
            # Not provided, use default from endpoint_params
            timeout = self._endpoint_params.get("default_rpc_timeout", 180.0)

        # Generate correlation ID for this request
        correlation_id: str = str(uuid4())

        # Register with global futures dict
        response_future: asyncio.Future[IncomingMessage] = (
            global_reply_handler.register_request(correlation_id)
        )

        try:
            # Extract parameters and build address (if parameters exist)
            address_override = self._build_address_with_parameters(payload)

            # Encode request payload
            encoded_payload: bytes = self._encode_message(payload)

            # Create wire message with RPC metadata (use global reply queue)
            wire_message: WireMessage = WireMessage(
                _payload=encoded_payload,
                _headers={},
                _correlation_id=correlation_id,
                _reply_to=global_reply_handler.reply_queue_name,  # Global reply queue
            )

            # Send request
            await self._producer.send_batch(
                [wire_message], address_override=address_override
            )

            # Wait for response with timeout (handled by global background task)
            try:
                response_message: IncomingMessage = await asyncio.wait_for(
                    response_future, timeout=timeout
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"RPC request timed out after {timeout} seconds")

            # Decode and return response
            decoded_response: T_Output = self._decode_reply(response_message.payload)
            return decoded_response

        finally:
            # Clean up future on timeout or error (if not already removed)
            global_reply_handler.cleanup_request(correlation_id)
