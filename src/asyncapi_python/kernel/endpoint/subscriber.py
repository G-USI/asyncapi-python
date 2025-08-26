from typing import Callable, Generic, overload
from typing_extensions import Unpack

from .abc import AbstractEndpoint, Receive, HandlerParams
from ..typing import T_Input, T_Output, Handler
from asyncapi_python.kernel.wire import Consumer


class Subscriber(
    AbstractEndpoint, Receive[T_Input, T_Output], Generic[T_Input, T_Output]
):
    """Subscriber endpoint for receiving messages without sending replies"""

    def __init__(self, **kwargs: Unpack[AbstractEndpoint.Inputs]):
        super().__init__(**kwargs)
        self._consumer: Consumer | None = None
        self._handler: Handler[T_Input, T_Output] | None = None

    async def start(self) -> None:
        """Initialize the subscriber endpoint"""
        if self._consumer:
            return

        # Create consumer from wire factory
        self._consumer = await self._wire.create_consumer(
            channel=self._operation.channel,
            parameters={},
            op_bindings=self._operation.bindings,
            is_reply=False,
        )

        # Start the consumer
        if self._consumer:
            await self._consumer.start()

    async def stop(self) -> None:
        """Cleanup the subscriber endpoint"""
        if not self._consumer:
            return

        await self._consumer.stop()
        self._consumer = None

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
        """Register a handler for incoming messages

        Can be used as a decorator:
        @subscriber
        def handle_message(msg): ...

        Or with parameters:
        @subscriber(queue="high-priority")
        def handle_message(msg): ...
        """
        if fn is None:
            # Called with parameters: @subscriber(queue=...)
            def decorator(
                handler_fn: Handler[T_Input, T_Output],
            ) -> Handler[T_Input, T_Output]:
                self._register_handler(handler_fn, kwargs)
                return handler_fn

            return decorator
        else:
            # Called directly: @subscriber
            self._register_handler(fn, kwargs)
            return fn

    def _register_handler(
        self, handler: Handler[T_Input, T_Output], _params: HandlerParams
    ) -> None:
        """Register a handler and start consuming messages"""
        self._handler = handler
        # TODO: Start background task to consume messages and call handler
        # This will need to be implemented based on the wire consumer interface

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

            except Exception:
                # Handle processing errors
                await wire_message.nack()
                # TODO: Add proper error handling/logging
