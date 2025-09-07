import asyncio
from typing import Generic
from typing_extensions import Unpack
from uuid import uuid4

from .abc import AbstractEndpoint, Send
from .exceptions import UninitializedError, TimeoutError
from .message import WireMessage
from ..typing import T_Input, T_Output, IncomingMessage
from asyncapi_python.kernel.wire import Producer


from .rpc_reply_handler import global_reply_handler


class RpcClient(AbstractEndpoint, Send[T_Input, T_Output], Generic[T_Input, T_Output]):
    """RPC client endpoint for request/response pattern

    Sends requests with correlation IDs and waits for responses
    on a shared global reply queue. All RPC client instances share
    a single reply consumer and background task for efficiency.
    """

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
        await global_reply_handler.ensure_reply_handler(self._wire, self._operation)

        # Create instance-specific producer for sending requests
        self._producer = await self._wire.create_producer(
            channel=self._operation.channel,
            parameters={},
            op_bindings=self._operation.bindings,
            is_reply=False,
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

    async def __call__(
        self,
        payload: T_Input,
        /,
        timeout: float = 30.0,
        **kwargs: Unpack[Send.RouterInputs],
    ) -> T_Output:
        """Send an RPC request and wait for response using global reply handling

        Args:
            payload: The request payload to send
            timeout: Maximum time to wait for response (default 30 seconds)

        Returns:
            The response payload

        Raises:
            TimeoutError: If response not received within timeout
            UninitializedError: If endpoint not started
        """
        if not self._producer:
            raise UninitializedError()

        # Generate correlation ID for this request
        correlation_id: str = str(uuid4())

        # Register with global futures dict
        response_future: asyncio.Future[IncomingMessage] = (
            global_reply_handler.register_request(correlation_id)
        )

        try:
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
            await self._producer.send_batch([wire_message])

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
