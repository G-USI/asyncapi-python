"""Global RPC reply handler for managing shared reply queue across all RPC clients."""

import asyncio
import secrets
from typing import Any

from asyncapi_python.kernel.document import Channel, Operation
from asyncapi_python.kernel.wire import AbstractWireFactory, Consumer

from ..typing import IncomingMessage
from .abc import EndpointParams


class GlobalRpcReplyHandler:
    """Manages global reply queue and routing for all RPC clients

    This class handles the shared state and background task that processes
    all RPC replies and routes them to the correct waiting client based
    on correlation IDs.
    """

    def __init__(self) -> None:
        self._futures: dict[str, asyncio.Future[IncomingMessage]] = {}
        self._reply_consumer: Consumer[Any] | None = None
        self._consume_task: asyncio.Task[None] | None = None
        self._reply_queue_name: str | None = None
        self._instance_count: int = 0

    async def ensure_reply_handler(
        self,
        wire_factory: AbstractWireFactory[Any, Any],
        operation: Operation,
        endpoint_params: EndpointParams,
    ) -> None:
        """Ensure reply consumer and task are running

        Args:
            wire_factory: Wire factory for creating consumer
            operation: Operation definition
            endpoint_params: Endpoint parameters including service_name
        """
        if self._reply_consumer is None:
            # Extract service_name from endpoint_params
            service_name = endpoint_params.get("service_name", "app")

            # Generate app_id with service name + random hex (same format as AmqpWire)
            random_hex = secrets.token_hex(4)  # 4 bytes = 8 hex chars
            app_id = f"{service_name}-{random_hex}"

            # Use app_id as the reply queue name
            self._reply_queue_name = f"reply-{app_id}"

            # Create reply channel with the generated queue name as address
            reply_channel = self._get_or_create_reply_channel(
                operation, self._reply_queue_name
            )

            # Create reply consumer with the channel (wire factory will use the address)
            self._reply_consumer = await wire_factory.create_consumer(
                channel=reply_channel,
                parameters={},
                op_bindings=None,
                is_reply=True,
                app_id=app_id,
            )

            # Start the consumer
            await self._reply_consumer.start()

            # Start background task
            self._consume_task = asyncio.create_task(self._consume_all_replies())

    def _get_or_create_reply_channel(
        self, operation: Operation, queue_name: str
    ) -> Channel:
        """Get reply channel from operation or create default one with specified queue name"""
        if operation.reply and operation.reply.channel:
            return operation.reply.channel
        else:
            # Create a default reply channel with the generated queue name as address
            return Channel(
                address=queue_name,  # Use the generated queue name as address
                title="Global RPC Reply Queue",
                summary=None,
                description=None,
                servers=[],
                messages={},
                parameters={},
                tags=[],
                external_docs=None,
                bindings=None,
                key="global-reply",
            )

    async def _consume_all_replies(self) -> None:
        """Background task consuming ALL RPC replies from all clients"""
        if not self._reply_consumer:
            return

        try:
            async for wire_message in self._reply_consumer.recv():
                try:
                    # Match reply to waiting request by correlation ID
                    correlation_id: str | None = wire_message.correlation_id
                    if correlation_id and correlation_id in self._futures:
                        future: asyncio.Future[IncomingMessage] = self._futures.pop(
                            correlation_id
                        )  # Remove and resolve
                        if not future.done():
                            future.set_result(wire_message)

                    # Acknowledge message
                    await wire_message.ack()

                except Exception:
                    # Handle errors in individual message processing
                    await wire_message.nack()
        except Exception:
            # If the consumer fails completely, cancel all pending futures
            for future in self._futures.values():
                if not future.done():
                    future.cancel()
            self._futures.clear()

    def register_request(self, correlation_id: str) -> asyncio.Future[IncomingMessage]:
        """Register a new RPC request and return its future"""
        future: asyncio.Future[IncomingMessage] = asyncio.Future()
        self._futures[correlation_id] = future
        return future

    def cleanup_request(self, correlation_id: str) -> None:
        """Clean up a request future (used on timeout/error)"""
        self._futures.pop(correlation_id, None)

    @property
    def reply_queue_name(self) -> str | None:
        """Get the global reply queue name"""
        return self._reply_queue_name

    def increment_instance_count(self) -> None:
        """Increment the instance count"""
        self._instance_count += 1

    def decrement_instance_count(self) -> int:
        """Decrement instance count and return new count"""
        self._instance_count -= 1
        return self._instance_count

    async def cleanup_if_last_instance(self) -> None:
        """Clean up global resources if no instances remain"""
        if self._instance_count == 0:
            # First cancel the background task
            if self._consume_task and not self._consume_task.done():
                self._consume_task.cancel()
                try:
                    await self._consume_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    # Handle any other exceptions during cleanup
                    pass
                self._consume_task = None

            # Then stop the consumer
            if self._reply_consumer:
                try:
                    await self._reply_consumer.stop()
                except Exception:
                    # Handle any exceptions during consumer stop
                    pass
                self._reply_consumer = None

            # Cancel any remaining futures
            for future in list(self._futures.values()):
                if not future.done():
                    future.cancel()
                    # Give cancelled futures a chance to be collected
                    try:
                        await asyncio.sleep(0)
                    except:
                        pass
            self._futures.clear()
            self._reply_queue_name = None


# Global singleton instance for all RPC clients
global_reply_handler = GlobalRpcReplyHandler()
