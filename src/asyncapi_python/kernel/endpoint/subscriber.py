import asyncio
from typing import Any, Callable, Generic, overload

from typing_extensions import Unpack

from asyncapi_python.kernel.wire import Consumer
from asyncapi_python.kernel.wire.utils import validate_parameters_strict

from ..exceptions import Reject
from ..typing import BatchConfig, BatchConsumer, Handler, IncomingMessage, T_Input
from .abc import AbstractEndpoint, HandlerParams, Receive


class Subscriber(AbstractEndpoint, Receive[T_Input, None], Generic[T_Input]):
    """Subscriber endpoint for receiving messages without sending replies"""

    def __init__(self, **kwargs: Unpack[AbstractEndpoint.Inputs]):
        super().__init__(**kwargs)
        self._consumer: Consumer[Any] | None = None
        self._handler: Handler[T_Input, None] | None = None
        self._batch_handler: BatchConsumer[Any] | None = (
            None  # Any because batch type is determined at runtime
        )
        self._handler_location: str | None = None
        self._batch_config: BatchConfig | None = None
        self._consume_task: asyncio.Task[None] | None = None
        self._subscription_parameters: dict[str, str] = (
            {}
        )  # Parameters for subscription (wildcards or concrete values)

    async def start(self, **params: Unpack[AbstractEndpoint.StartParams]) -> None:
        """Initialize the subscriber endpoint"""
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
                f"Subscriber endpoint '{self._operation.key}' requires exactly one handler. "
                f"Use @{self._operation.key} decorator to register a handler function."
            )

        # Validate subscription parameters before creating consumer
        validate_parameters_strict(
            self._operation.channel, self._subscription_parameters
        )

        # Create consumer from wire factory
        self._consumer = await self._wire.create_consumer(
            channel=self._operation.channel,
            parameters=self._subscription_parameters,
            op_bindings=self._operation.bindings,
            is_reply=False,
        )

        # Start the consumer
        if self._consumer:
            await self._consumer.start()

            # Start consuming task if we have a handler but no task yet
            if (self._handler or self._batch_handler) and not self._consume_task:
                if self._batch_handler:
                    self._consume_task = asyncio.create_task(
                        self._consume_messages_batch()
                    )
                else:
                    self._consume_task = asyncio.create_task(self._consume_messages())

    async def stop(self) -> None:
        """Cleanup the subscriber endpoint"""
        if not self._consumer:
            return

        # Cancel the consume task
        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
            self._consume_task = None

        await self._consumer.stop()
        self._consumer = None

    @overload
    @overload
    def __call__(self, fn: Handler[T_Input, None]) -> Handler[T_Input, None]: ...

    @overload
    def __call__(
        self,
        fn: None = None,
        *,
        batch: BatchConfig,
        **kwargs: Unpack[HandlerParams],
    ) -> Callable[[BatchConsumer[T_Input]], BatchConsumer[T_Input]]: ...

    @overload
    @overload
    def __call__(
        self, fn: None = None, **kwargs: Unpack[HandlerParams]
    ) -> Callable[[Handler[T_Input, None]], Handler[T_Input, None]]: ...

    def __call__(  # type: ignore[override]
        self,
        fn: Handler[T_Input, None] | BatchConsumer[T_Input] | None = None,
        *,
        batch: BatchConfig | None = None,
        **kwargs: Unpack[HandlerParams],
    ) -> (
        Handler[T_Input, None]
        | BatchConsumer[T_Input]
        | Callable[[Handler[T_Input, None]], Handler[T_Input, None]]
        | Callable[[BatchConsumer[T_Input]], BatchConsumer[T_Input]]
    ):
        """Register a handler for incoming messages

        Can be used as a decorator:
        @subscriber
        def handle_message(msg): ...

        Or with parameters:
        @subscriber(queue="high-priority")
        def handle_message(msg): ...
        """
        if fn is None:
            # Called with parameters: @subscriber(batch=..., ...)
            if batch is not None:
                # Batch mode - expect BatchConsumer
                def batch_decorator(
                    handler_fn: BatchConsumer[T_Input],
                ) -> BatchConsumer[T_Input]:
                    self._register_handler(handler_fn, batch, kwargs)
                    return handler_fn

                return batch_decorator
            else:
                # Regular mode - expect Handler
                def decorator(
                    handler_fn: Handler[T_Input, None],
                ) -> Handler[T_Input, None]:
                    self._register_handler(handler_fn, None, kwargs)
                    return handler_fn

                return decorator
        else:
            # Called directly: @subscriber
            self._register_handler(fn, batch, kwargs)
            return fn

    def _register_handler(
        self,
        handler: Handler[T_Input, None] | BatchConsumer[T_Input],
        batch_config: BatchConfig | None,
        params: HandlerParams,
    ) -> None:
        """Register a handler and start consuming messages"""
        if self._should_validate_handlers() and (
            self._handler is not None or self._batch_handler is not None
        ):
            existing_handler = self._handler or self._batch_handler
            assert existing_handler is not None  # for mypy
            raise RuntimeError(
                f"Subscriber endpoint '{self._operation.key}' already has a handler registered.\n"
                f"Existing handler: {existing_handler.__name__} at {self._handler_location}\n"
                f"New handler: {handler.__name__} at {handler.__code__.co_filename}:{handler.__code__.co_firstlineno}\n"
                f"Each subscriber endpoint must have exactly one handler."
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

        # Start background task to consume messages if consumer is ready
        if self._consumer and not self._consume_task:
            try:
                if self._batch_handler:
                    self._consume_task = asyncio.create_task(
                        self._consume_messages_batch()
                    )
                else:
                    self._consume_task = asyncio.create_task(self._consume_messages())
            except RuntimeError:
                # No event loop running, task will be created later when start() is called
                pass

    async def _consume_messages(self) -> None:
        """Background task that consumes messages and calls the handler"""
        if not self._consumer or not self._handler:
            return

        async for wire_message in self._consumer.recv():
            try:
                # Decode the message payload
                decoded_payload = self._decode_message(wire_message.payload)

                # Call the user handler
                await self._handler(decoded_payload)

                # Acknowledge successful processing
                await wire_message.ack()

            except Reject as e:
                # Handle message rejection - reject and continue
                await wire_message.reject()

            except Exception as e:
                # Any other exception should stop the application
                await wire_message.nack()
                # Propagate to application level
                if self._exception_callback:
                    self._exception_callback(e)
                return  # Stop processing messages

    async def _consume_messages_batch(self) -> None:
        """Background task that consumes messages in batches and calls the batch handler"""
        if not self._consumer or not self._batch_handler or not self._batch_config:
            return

        batch: list[tuple[T_Input, IncomingMessage]] = []

        async def process_batch():
            """Process the current batch"""
            if not batch:
                return

            # Extract messages and wire messages separately
            decoded_messages = [item[0] for item in batch]
            wire_messages = [item[1] for item in batch]

            try:
                # Call the batch handler
                if self._batch_handler is None:
                    raise RuntimeError("No batch handler configured")
                await self._batch_handler(decoded_messages)

                # Acknowledge all messages in the batch
                for wire_message in wire_messages:
                    await wire_message.ack()

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
                    # Decode the message payload
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
                        await wire_message.nack()
