import asyncio
from typing import Callable, Generic, Union, overload

from typing_extensions import Unpack

from asyncapi_python.kernel.wire import Consumer, Producer
from asyncapi_python.kernel.wire.utils import validate_parameters_strict

from ..exceptions import Reject
from ..typing import (
    BatchConfig,
    BatchHandler,
    Handler,
    IncomingMessage,
    T_Input,
    T_Output,
)
from .abc import AbstractEndpoint, HandlerParams, Receive
from .message import WireMessage


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
        self._batch_handler: BatchHandler[T_Input, T_Output] | None = None
        self._handler_location: str | None = None
        self._batch_config: BatchConfig | None = None
        self._consume_task: asyncio.Task[None] | None = None
        self._subscription_parameters: dict[str, str] = (
            {}
        )  # Parameters for subscription (wildcards or concrete values)

    async def start(self, **params: Unpack[AbstractEndpoint.StartParams]) -> None:
        """Initialize the RPC server endpoint"""
        if self._consumer:
            return

        # Get exception callback from parameters
        self._exception_callback = params.get("exception_callback")

        # Validate that we have exactly one handler (if validation is enabled)
        if (
            self._should_validate_handlers()
            and not self._handler
            and not self._batch_handler
        ):
            raise RuntimeError(
                f"RPC server endpoint '{self._operation.key}' requires exactly one handler. "
                f"Use @{self._operation.key} decorator to register a handler function."
            )

        # Validate we have reply codecs
        if not self._reply_codecs:
            raise RuntimeError("RPC server operation has no reply messages defined")

        # Validate subscription parameters before creating consumer
        validate_parameters_strict(
            self._operation.channel, self._subscription_parameters
        )

        # Create consumer for receiving requests
        self._consumer = await self._wire.create_consumer(
            channel=self._operation.channel,
            parameters=self._subscription_parameters,
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
                key="reply",
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
        if (self._handler or self._batch_handler) and not self._consume_task:
            if self._batch_handler:
                self._consume_task = asyncio.create_task(self._consume_requests_batch())
            else:
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
    ) -> Callable[
        [BatchHandler[T_Input, T_Output]], BatchHandler[T_Input, T_Output]
    ]: ...

    @overload
    @overload
    def __call__(
        self, fn: None = None, **kwargs: Unpack[HandlerParams]
    ) -> Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]]: ...

    def __call__(  # type: ignore[override]
        self,
        fn: Handler[T_Input, T_Output] | BatchHandler[T_Input, T_Output] | None = None,
        *,
        batch: BatchConfig | None = None,
        **kwargs: Unpack[HandlerParams],
    ) -> Union[
        Handler[T_Input, T_Output],
        BatchHandler[T_Input, T_Output],
        Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]],
        Callable[[BatchHandler[T_Input, T_Output]], BatchHandler[T_Input, T_Output]],
    ]:
        """Register a handler for incoming RPC requests

        Can be used as a decorator:
        @rpc_server
        async def handle_request(msg) -> Response: ...

        Or with parameters:
        @rpc_server(queue="high-priority")
        async def handle_request(msg) -> Response: ...
        """
        if fn is None:
            # Called with parameters: @rpc_server(batch=..., ...)
            if batch is not None:
                # Batch mode - expect BatchHandler
                def batch_decorator(
                    handler_fn: BatchHandler[T_Input, T_Output],
                ) -> BatchHandler[T_Input, T_Output]:
                    self._register_handler(handler_fn, batch, kwargs)
                    return handler_fn

                return batch_decorator
            else:
                # Regular mode - expect Handler
                def decorator(
                    handler_fn: Handler[T_Input, T_Output],
                ) -> Handler[T_Input, T_Output]:
                    self._register_handler(handler_fn, None, kwargs)
                    return handler_fn

                return decorator
        else:
            # Called directly: @rpc_server
            self._register_handler(fn, batch, kwargs)
            return fn

    def _register_handler(
        self,
        handler: Handler[T_Input, T_Output] | BatchHandler[T_Input, T_Output],
        batch_config: BatchConfig | None,
        params: HandlerParams,
    ) -> None:
        """Register a handler and start consuming requests"""
        if self._should_validate_handlers() and (
            self._handler is not None or self._batch_handler is not None
        ):
            existing_handler = self._handler or self._batch_handler
            assert existing_handler is not None  # for mypy
            raise RuntimeError(
                f"RPC server endpoint '{self._operation.key}' already has a handler registered.\n"
                f"Existing handler: {existing_handler.__name__} at {self._handler_location}\n"
                f"New handler: {handler.__name__} at {handler.__code__.co_filename}:{handler.__code__.co_firstlineno}\n"
                f"Each RPC server endpoint must have exactly one handler."
            )

        # Extract subscription parameters if provided
        if "parameters" in params:
            self._subscription_parameters = params["parameters"]

        # Determine if this is a batch handler by checking if batch config exists
        if batch_config is not None:
            self._batch_handler = handler  # type: ignore
            self._batch_config = batch_config
            self._handler = None
        else:
            self._handler = handler  # type: ignore
            self._batch_handler = None
            self._batch_config = None

        self._handler_location = (
            f"{handler.__code__.co_filename}:{handler.__code__.co_firstlineno}"
        )
        # Start background task to consume requests if consumer is ready
        if self._consumer and not self._consume_task:
            try:
                if self._batch_handler:
                    self._consume_task = asyncio.create_task(
                        self._consume_requests_batch()
                    )
                else:
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
                    await wire_message.nack()
                    continue

                # Decode the request payload
                decoded_payload = self._decode_message(wire_message.payload)

                # Call the user handler to get response
                try:
                    response = await self._handler(decoded_payload)
                except Reject as e:
                    # Message rejected - reject and continue
                    await wire_message.reject()
                    continue
                except Exception as e:
                    # Any other exception - nack and propagate to stop application
                    await wire_message.nack()
                    # Propagate to application level
                    if self._exception_callback:
                        self._exception_callback(e)
                    return  # Stop processing messages

                # Encode response
                encoded_response = self._encode_reply(response)

                # Create reply message with same correlation ID
                reply_message = WireMessage(
                    _payload=encoded_response,
                    _headers={},
                    _correlation_id=wire_message.correlation_id,
                    _reply_to=None,  # No further reply expected
                )

                # Send reply to client's reply_to address (or static config if None)
                await self._send_reply(reply_message, wire_message.reply_to)

                # Acknowledge successful processing
                await wire_message.ack()

            except Exception:
                # Handle processing errors
                await wire_message.nack()

    async def _consume_requests_batch(self) -> None:
        """Background task that consumes requests in batches and sends batched responses"""
        if (
            not self._consumer
            or not self._batch_handler
            or not self._reply_producer
            or not self._batch_config
        ):
            return

        batch: list[tuple[T_Input, IncomingMessage]] = []

        async def process_batch():
            """Process the current batch"""
            if not batch:
                return

            # Extract messages and wire messages separately
            decoded_requests = [item[0] for item in batch]
            wire_messages = [item[1] for item in batch]

            try:
                # Call the batch handler to get responses
                if self._batch_handler is None:
                    raise RuntimeError("No batch handler configured")
                responses = await self._batch_handler(decoded_requests)

                # Validate response count matches request count (as specified in requirements)
                if len(responses) != len(decoded_requests):
                    raise RuntimeError(
                        f"Batch RPC handler returned {len(responses)} responses "
                        f"but received {len(decoded_requests)} requests. "
                        f"For batch RPC operations, len(inputs) must equal len(outputs)."
                    )

                # Send replies for each request-response pair
                for wire_message, response in zip(wire_messages, responses):
                    try:
                        # Encode response
                        encoded_response = self._encode_reply(response)

                        # Create reply message with same correlation ID
                        reply_message = WireMessage(
                            _payload=encoded_response,
                            _headers={},
                            _correlation_id=wire_message.correlation_id,
                            _reply_to=None,  # No further reply expected
                        )

                        # Send reply to client's reply_to address (or static config if None)
                        await self._send_reply(reply_message, wire_message.reply_to)

                        # Acknowledge successful processing
                        await wire_message.ack()

                    except Exception as e:
                        # Individual response failed - nack this request only
                        await wire_message.nack()

            except Reject:
                # Reject all messages in the batch and continue
                for wire_message in wire_messages:
                    await wire_message.reject()

            except Exception as e:
                # Any other exception - nack all messages and stop
                for wire_message in wire_messages:
                    await wire_message.nack()
                # Propagate to application level
                if self._exception_callback:
                    self._exception_callback(e)
                raise  # Stop processing

        batch_start_time = None
        exception_occurred = False

        try:
            async for wire_message in self._consumer.recv():
                try:
                    # Validate RPC metadata
                    if not wire_message.correlation_id or not wire_message.reply_to:
                        # Not an RPC request, skip
                        await wire_message.nack()
                        continue

                    # Decode the request payload
                    decoded_payload = self._decode_message(wire_message.payload)

                    # Add to batch
                    batch.append((decoded_payload, wire_message))

                    # Record start time for the first message in batch
                    if len(batch) == 1:
                        batch_start_time = asyncio.get_event_loop().time()

                    # Check if batch is full
                    if len(batch) >= self._batch_config["max_size"]:
                        # Process batch when full
                        try:
                            await process_batch()
                        finally:
                            # Always clear batch after processing attempt
                            batch.clear()
                            batch_start_time = None

                    # Check if timeout expired (only if we have messages)
                    elif batch and batch_start_time:
                        current_time = asyncio.get_event_loop().time()
                        if (
                            current_time - batch_start_time
                            >= self._batch_config["timeout"]
                        ):
                            # Process batch due to timeout
                            try:
                                await process_batch()
                            finally:
                                # Always clear batch after processing attempt
                                batch.clear()
                                batch_start_time = None

                except Exception:
                    # Individual message decode error - nack and continue
                    await wire_message.nack()
                    continue

        except Exception:
            # Final exception handling - nack any remaining messages
            exception_occurred = True
            for _, wire_message in batch:
                await wire_message.nack()
            # Only call exception callback if it hasn't been called from process_batch
            # Exception from process_batch will be a re-raise, so we don't need to call again
            pass
        finally:
            # Process any remaining messages in batch only if no exception occurred
            if batch and not exception_occurred:
                try:
                    await process_batch()
                except Exception:
                    # If processing remaining batch fails, just nack all and continue
                    for _, wire_message in batch:
                        await wire_message.nack()

    async def _send_reply(
        self, reply_message: WireMessage, reply_to_address: str | None = None
    ) -> None:
        """Send reply message

        Args:
            reply_message: The reply message to send
            reply_to_address: Optional dynamic reply address (from request's reply_to field).
                            If None, uses producer's static configuration from bindings.
        """
        if not self._reply_producer:
            return

        # Send reply with optional address override
        # - If reply_to_address is provided: send to that specific queue (direct RPC reply)
        # - If None: use producer's static routing from AsyncAPI spec (topic-based reply)
        await self._reply_producer.send_batch(
            [reply_message], address_override=reply_to_address
        )
