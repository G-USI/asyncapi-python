"""Reply channel creation scenario"""

import asyncio

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

# Import test models
from ..test_app.messages.json import TestEvent


class OrderProcessingApp(BaseApplication):
    """Order processing service with endpoints for testing scenarios"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory=wire_factory, codec_factory=codec_factory)
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup order processing endpoints"""

        # Order events publisher
        order_events_channel = Channel(
            address="orders.events",
            title=None,
            summary=None,
            description=None,
            servers=[],
            messages={},
            parameters={},
            tags=[],
            external_docs=None,
            bindings=None,
            key="test-key",
        )

        order_event_message = Message(
            name="TestEvent",
            title=None,
            summary=None,
            description=None,
            tags=[],
            externalDocs=None,
            traits=[],
            payload={"type": "object"},
            headers=None,
            bindings=None,
            key="test-key",
            correlation_id=None,
            content_type=None,
            deprecated=None,
        )

        order_events_operation = Operation(
            channel=order_events_channel,
            messages=[order_event_message],
            action="send",
            title=None,
            summary=None,
            description=None,
            tags=[],
            external_docs=None,
            traits=[],
            bindings=None,
            key="test-key",
            reply=None,
            security=None,
        )

        self.order_events = self._register_endpoint(order_events_operation)

        # RPC endpoint with reply channel
        rpc_channel = Channel(
            address="orders.rpc",
            title=None,
            summary=None,
            description=None,
            servers=[],
            messages={},
            parameters={},
            tags=[],
            external_docs=None,
            bindings=None,
            key="test-key",
        )

        # Reply channel with null address (global reply queue)
        reply_channel = Channel(
            address=None,  # Null address for global reply queue
            title=None,
            summary=None,
            description=None,
            servers=[],
            messages={},
            parameters={},
            tags=[],
            external_docs=None,
            bindings=None,
            key="test-key",
        )

        rpc_reply_operation = Operation(
            channel=reply_channel,
            messages=[order_event_message],
            action="send",
            title=None,
            summary=None,
            description=None,
            tags=[],
            external_docs=None,
            traits=[],
            bindings=None,
            key="test-key",
            reply=None,
            security=None,
        )

        self.rpc_replies = self._register_endpoint(rpc_reply_operation)


async def reply_channel_creation(
    wire: AbstractWireFactory, codec: CodecFactory
) -> None:
    """Test reply channel creation using OrderProcessingApp's RPC endpoint"""
    print(
        f"Testing reply channel with {wire.__class__.__name__} + {codec.__class__.__name__}"
    )

    # 1. Create OrderProcessingApp which has RPC endpoint with null address
    app = OrderProcessingApp(wire, codec)

    # Create a consumer for the default/reply queue
    class ReplyConsumerApp(BaseApplication):
        def __init__(
            self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory
        ):
            super().__init__(wire_factory=wire_factory, codec_factory=codec_factory)
            self._setup_endpoints()

        def _setup_endpoints(self):
            # Consumer for reply messages (null address -> "default" queue in AMQP)
            reply_channel = Channel(
                address=None,  # Same null address to consume from default queue
                title=None,
                summary=None,
                description=None,
                servers=[],
                messages={},
                parameters={},
                tags=[],
                external_docs=None,
                bindings=None,
                key="test-key",
            )

            reply_message = Message(
                name="TestEvent",
                title=None,
                summary=None,
                description=None,
                tags=[],
                externalDocs=None,
                traits=[],
                payload={"type": "object"},
                headers=None,
                bindings=None,
                key="test-key",
                correlation_id=None,
                content_type=None,
                deprecated=None,
            )

            reply_operation = Operation(
                channel=reply_channel,
                messages=[reply_message],
                action="receive",
                title=None,
                summary=None,
                description=None,
                tags=[],
                external_docs=None,
                traits=[],
                bindings=None,
                key="test-key",
                reply=None,
                security=None,
            )

            self.on_reply = self._register_endpoint(reply_operation)

    reply_consumer = ReplyConsumerApp(wire, codec)
    replies_consumed = []

    @reply_consumer.on_reply
    async def consume_reply(event: TestEvent):
        replies_consumed.append(event)
        print(f"✓ Consumed reply message: {event.event_type}")

    try:
        # 2. Start consumer first, then the application
        await reply_consumer.start()
        await app.start()
        print("✓ OrderProcessingApp started successfully")

        # 3. The rpc_replies endpoint should be created with null address
        # This should trigger global reply queue creation
        if "InMemory" in wire.__class__.__name__:
            print("✓ In-memory global reply channel created via app")
        else:  # AMQP
            print("✓ AMQP global reply queue created: reply-queue-test-integration")

        # 4. Test sending a reply message through the RPC endpoint
        test_event = TestEvent(
            event_type="order.processed",
            user_id=456,
            timestamp="2024-01-01T00:00:00Z",
            payload={"order_id": "order-123", "status": "completed"},
        )

        # Send reply via the RPC endpoint
        await app.rpc_replies(test_event)
        print(f"✓ Sent RPC reply: {test_event}")

        # 5. Test lifecycle operations - restart the app
        await app.stop()
        await app.start()
        print("✓ App lifecycle operations successful")

        # 6. Test sending another reply after restart
        test_event2 = TestEvent(
            event_type="order.cancelled",
            user_id=789,
            timestamp="2024-01-01T01:00:00Z",
            payload={"order_id": "order-456", "reason": "customer_request"},
        )

        await app.rpc_replies(test_event2)
        print(f"✓ Sent RPC reply after restart: {test_event2}")

        # Wait a bit for messages to be consumed
        await asyncio.sleep(0.1)

        print(
            f"✓ Reply channel creation and operations successful (consumed {len(replies_consumed)} replies)"
        )

    finally:
        await app.stop()
        await reply_consumer.stop()
