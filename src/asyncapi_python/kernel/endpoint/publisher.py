from typing import Generic

from typing_extensions import Unpack

from asyncapi_python.kernel.wire import Producer

from ..typing import T_Input
from .abc import AbstractEndpoint, Send
from .exceptions import UninitializedError
from .message import WireMessage


class Publisher(AbstractEndpoint, Send[T_Input, None], Generic[T_Input]):
    """Publisher endpoint for sending messages without expecting replies"""

    def __init__(self, **kwargs: Unpack[AbstractEndpoint.Inputs]):
        super().__init__(**kwargs)
        self._producer: Producer[WireMessage] | None = None

    async def start(self, **params: Unpack[AbstractEndpoint.StartParams]) -> None:
        """Initialize the publisher endpoint"""
        if self._producer:
            return

        # Get exception callback from parameters
        self._exception_callback = params.get("exception_callback")

        # Validate we have codecs for messages
        if not self._codecs:
            raise RuntimeError("Operation has no named messages")

        # Create producer from wire factory
        self._producer = await self._wire.create_producer(
            channel=self._operation.channel,
            parameters={},
            op_bindings=self._operation.bindings,
            is_reply=False,
        )

        # Start the producer
        if self._producer:
            await self._producer.start()

    async def stop(self) -> None:
        """Cleanup the publisher endpoint"""
        if not self._producer:
            return

        await self._producer.stop()
        self._producer = None

    async def __call__(
        self, payload: T_Input, /, **kwargs: Unpack[Send.RouterInputs]
    ) -> None:
        """Send a message without expecting a reply

        Args:
            payload: The message payload to send
        """
        if not self._producer:
            raise UninitializedError()

        # Extract parameters and build address (if parameters exist)
        address_override = self._build_address_with_parameters(payload)

        # Encode payload using main message codecs
        encoded_payload = self._encode_message(payload)

        # Create wire message with encoded payload
        wire_message = WireMessage(
            _payload=encoded_payload, _headers={}, _correlation_id=None, _reply_to=None
        )

        # Send via producer
        await self._producer.send_batch(
            [wire_message], address_override=address_override
        )
