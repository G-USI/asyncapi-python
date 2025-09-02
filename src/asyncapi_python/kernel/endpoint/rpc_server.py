import asyncio
from typing import Callable, Generic, overload
from typing_extensions import Unpack

from .abc import AbstractEndpoint, Receive, HandlerParams
from .exceptions import HandlerError
from .message import WireMessage
from ..typing import T_Input, T_Output, Handler, IncomingMessage
from asyncapi_python.kernel.wire import Consumer, Producer


class RpcServer(
    AbstractEndpoint, Receive[T_Input, T_Output], Generic[T_Input, T_Output]
):
    """RPC server endpoint for handling requests and sending responses
    
    Receives requests with correlation IDs and sends responses
    back to the reply_to address.
    """

    def __init__(self, **kwargs: Unpack[AbstractEndpoint.Inputs]):
        super().__init__(**kwargs)
        self._consumer: Consumer[IncomingMessage] | None = None
        self._reply_producer: Producer[WireMessage] | None = None
        self._handler: Handler[T_Input, T_Output] | None = None
        self._consume_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Initialize the RPC server endpoint"""
        if self._consumer:
            return

        # Validate we have reply codecs
        if not self._reply_codecs:
            raise RuntimeError("RPC server operation has no reply messages defined")

        # Create consumer for receiving requests
        self._consumer = await self._wire.create_consumer(
            channel=self._operation.channel,
            parameters={},
            op_bindings=self._operation.bindings,
            is_reply=False,
        )

        # Create producer for sending replies
        # Use reply channel if specified, otherwise use default exchange
        if self._operation.reply and self._operation.reply.channel:
            reply_channel = self._operation.reply.channel
        else:
            # Create a default reply channel (null address for direct reply)
            from asyncapi_python.kernel.document import Channel
            reply_channel = Channel(
                address=None,  # Use default/null address for direct reply
                title="Reply Channel",
                summary=None,
                description=None,
                servers=[],
                messages={},
                parameters={},
                tags=[],
                external_docs=None,
                bindings=None,
            )
        
        self._reply_producer = await self._wire.create_producer(
            channel=reply_channel,
            parameters={},
            op_bindings=None,
            is_reply=True,
        )

        # Start consumer and producer
        if self._consumer:
            await self._consumer.start()
        if self._reply_producer:
            await self._reply_producer.start()
            
        # Start consuming task if we have a handler but no task yet
        if self._handler and not self._consume_task:
            self._consume_task = asyncio.create_task(self._consume_requests())

    async def stop(self) -> None:
        """Cleanup the RPC server endpoint"""
        # Cancel the consume task
        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
            self._consume_task = None

        # Stop consumer and producer
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
        if self._reply_producer:
            await self._reply_producer.stop()
            self._reply_producer = None

    @overload
    def __call__(
        self, fn: Handler[T_Input, T_Output]
    ) -> Handler[T_Input, T_Output]: ...

    @overload
    def __call__(
        self, fn: None = None, **kwargs: Unpack[HandlerParams]
    ) -> Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]]: ...

    def __call__(
        self,
        fn: Handler[T_Input, T_Output] | None = None,
        **kwargs: Unpack[HandlerParams],
    ) -> (
        Handler[T_Input, T_Output]
        | Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]]
    ):
        """Register a handler for incoming RPC requests
        
        Can be used as a decorator:
        @rpc_server
        async def handle_request(msg) -> Response: ...
        
        Or with parameters:
        @rpc_server(queue="high-priority")
        async def handle_request(msg) -> Response: ...
        """
        if fn is None:
            # Called with parameters: @rpc_server(queue=...)
            def decorator(
                handler_fn: Handler[T_Input, T_Output],
            ) -> Handler[T_Input, T_Output]:
                self._register_handler(handler_fn, kwargs)
                return handler_fn

            return decorator
        else:
            # Called directly: @rpc_server
            self._register_handler(fn, kwargs)
            return fn

    def _register_handler(
        self, handler: Handler[T_Input, T_Output], _params: HandlerParams
    ) -> None:
        """Register a handler and start consuming requests"""
        if self._handler:
            raise ValueError("RPC server already has a handler registered")
            
        self._handler = handler
        # Start background task to consume requests if consumer is ready
        if self._consumer and not self._consume_task:
            try:
                self._consume_task = asyncio.create_task(self._consume_requests())
            except RuntimeError:
                # No event loop running, task will be created later when start() is called
                pass

    async def _consume_requests(self) -> None:
        """Background task that consumes requests and sends responses"""
        if not self._consumer or not self._handler or not self._reply_producer:
            return

        async for wire_message in self._consumer.recv():
            try:
                # Validate RPC metadata
                if not wire_message.correlation_id or not wire_message.reply_to:
                    # Not an RPC request, skip
                    if hasattr(wire_message, 'nack'):
                        await wire_message.nack()
                    continue

                # Decode the request payload
                decoded_payload = self._decode_message(wire_message.payload)

                # Call the user handler to get response
                try:
                    response = await self._handler(decoded_payload)
                except Exception as e:
                    # Handler error - send error response if possible
                    await self._send_error_response(
                        wire_message.correlation_id,
                        wire_message.reply_to,
                        str(e)
                    )
                    if hasattr(wire_message, 'ack'):
                        await wire_message.ack()
                    continue

                # Encode response
                encoded_response = self._encode_reply(response)

                # Create reply message with same correlation ID
                reply_message = WireMessage(
                    _payload=encoded_response,
                    _headers={},
                    _correlation_id=wire_message.correlation_id,
                    _reply_to=None,  # No further reply expected
                )

                # Send reply to the reply_to address
                # The wire implementation should handle routing to reply_to
                await self._send_reply(reply_message, wire_message.reply_to)

                # Acknowledge successful processing
                if hasattr(wire_message, 'ack'):
                    await wire_message.ack()

            except Exception:
                # Handle processing errors
                if hasattr(wire_message, 'nack'):
                    await wire_message.nack()

    async def _send_reply(self, reply_message: WireMessage, reply_to: str) -> None:
        """Send reply message to the specified address"""
        if not self._reply_producer:
            return
            
        # Send the reply
        # The wire implementation should route this to the reply_to address
        await self._reply_producer.send_batch([reply_message])

    async def _send_error_response(
        self, correlation_id: str, reply_to: str, error_message: str
    ) -> None:
        """Send an error response for a failed request"""
        if not self._reply_producer:
            return

        # Create error payload
        # This is a simplified error response - could be enhanced
        error_payload = f'{{"error": "{error_message}"}}'.encode()

        # Create error reply message
        error_reply = WireMessage(
            _payload=error_payload,
            _headers={"error": "true"},
            _correlation_id=correlation_id,
            _reply_to=None,
        )

        await self._send_reply(error_reply, reply_to)