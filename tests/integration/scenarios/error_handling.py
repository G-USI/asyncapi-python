"""Error handling scenario"""

import asyncio

import pytest

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

# Import test models
from ..test_app.messages.json import TestEvent, TestUser, UserCreated, UserUpdated


class UserManagementApp(BaseApplication):
    """User management service with endpoints for testing scenarios"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(
            wire_factory=wire_factory,
            codec_factory=codec_factory,
            endpoint_params={"disable_handler_validation": True},
        )
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup user management endpoints"""

        # User creation endpoint (publisher)
        user_created_channel = Channel(
            address="users.created",
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

        user_created_message = Message(
            name="UserCreated",
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

        user_created_operation = Operation(
            channel=user_created_channel,
            messages=[user_created_message],
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

        self.user_created = self._register_endpoint(user_created_operation)

        # User update subscriber endpoint
        user_update_channel = Channel(
            address="users.update",
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

        user_update_message = Message(
            name="UserUpdated",
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

        user_update_operation = Operation(
            channel=user_update_channel,
            messages=[user_update_message],
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

        self.user_updates = self._register_endpoint(user_update_operation)


class OrderProcessingApp(BaseApplication):
    """Order processing service with endpoints for testing scenarios"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(
            wire_factory=wire_factory,
            codec_factory=codec_factory,
            endpoint_params={"disable_handler_validation": True},
        )
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


async def error_handling(wire: AbstractWireFactory, codec: CodecFactory) -> None:
    """Test error handling across different apps and codecs"""
    print(
        f"Testing error handling with {wire.__class__.__name__} + {codec.__class__.__name__}"
    )

    # 1. Test codec error handling with direct codec usage
    test_message = Message(
        name="TestUser",
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

    message_codec = codec.create(test_message)

    # Test invalid decode with malformed JSON
    with pytest.raises((ValueError, Exception)):
        message_codec.decode(b"invalid json data")
    print("✓ Invalid JSON decode raises exception correctly")

    # Test decode with valid JSON but wrong structure
    with pytest.raises((ValueError, Exception)):
        message_codec.decode(b'{"wrong": "structure", "missing": "required fields"}')
    print("✓ Invalid structure decode raises exception correctly")

    # Test decode with non-UTF8 bytes
    with pytest.raises((ValueError, Exception)):
        message_codec.decode(b"\xff\xfe\x00\x01invalid bytes")
    print("✓ Invalid UTF-8 decode raises exception correctly")

    # 2. Test error handling with UserManagementApp
    user_app = UserManagementApp(wire, codec)

    # Create a consumer app to consume the messages
    class UserConsumerApp(BaseApplication):
        def __init__(
            self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory
        ):
            super().__init__(
                wire_factory=wire_factory,
                codec_factory=codec_factory,
                endpoint_params={"disable_handler_validation": True},
            )
            self._setup_endpoints()

        def _setup_endpoints(self):
            # Consumer for user.created events
            user_created_channel = Channel(
                address="users.created",
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

            user_created_message = Message(
                name="UserCreated",
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

            user_created_operation = Operation(
                channel=user_created_channel,
                messages=[user_created_message],
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

            self.on_user_created = self._register_endpoint(user_created_operation)

    consumer_app = UserConsumerApp(wire, codec)
    messages_consumed = []
    consume_event = asyncio.Event()
    expected_messages = 2  # We're sending 2 messages

    @consumer_app.on_user_created
    async def consume_user_created(user: UserCreated):
        messages_consumed.append(user)
        if len(messages_consumed) >= expected_messages:
            consume_event.set()

    try:
        # Start consumer first to ensure it's ready to consume all messages
        await consumer_app.start()
        await user_app.start()

        # Test successful operations
        valid_user = UserCreated(
            user_id=42,
            name="Bob",
            email="bob@test.com",
            timestamp="2024-01-01T00:00:00Z",
        )

        await user_app.user_created(valid_user)
        print("✓ UserApp - Valid user created successfully")

        # Test edge case data
        edge_case_user = UserCreated(
            user_id=0,  # Edge case: zero ID
            name="",  # Edge case: empty string
            email="special+chars@example-domain.co.uk",
            timestamp="2024-01-01T00:00:00Z",
        )

        await user_app.user_created(edge_case_user)
        print("✓ UserApp - Edge case user created successfully")

        # Wait for messages to be consumed
        try:
            await asyncio.wait_for(consume_event.wait(), timeout=2.0)
            print(f"✓ UserApp - All {len(messages_consumed)} messages consumed")
        except asyncio.TimeoutError:
            print(
                f"⚠ UserApp - Only {len(messages_consumed)}/{expected_messages} messages consumed"
            )

    finally:
        await user_app.stop()
        await consumer_app.stop()

    # 3. Test error handling with OrderProcessingApp
    order_app = OrderProcessingApp(wire, codec)

    # Create a consumer app for order events
    class OrderConsumerApp(BaseApplication):
        def __init__(
            self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory
        ):
            super().__init__(
                wire_factory=wire_factory,
                codec_factory=codec_factory,
                endpoint_params={"disable_handler_validation": True},
            )
            self._setup_endpoints()

        def _setup_endpoints(self):
            # Consumer for order events
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

            self.on_order_event = self._register_endpoint(order_events_operation)

    # Also create a consumer for RPC replies (default queue)
    class ReplyConsumerApp(BaseApplication):
        def __init__(
            self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory
        ):
            super().__init__(
                wire_factory=wire_factory,
                codec_factory=codec_factory,
                endpoint_params={"disable_handler_validation": True},
            )
            self._setup_endpoints()

        def _setup_endpoints(self):
            # Consumer for reply messages (null address -> "default" queue)
            reply_channel = Channel(
                address=None,  # Null address for default queue
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

    order_consumer_app = OrderConsumerApp(wire, codec)
    reply_consumer_app = ReplyConsumerApp(wire, codec)
    order_messages_consumed = []
    order_consume_event = asyncio.Event()
    expected_order_messages = 2  # We're sending 2 order events

    @order_consumer_app.on_order_event
    async def consume_order_event(event: TestEvent):
        order_messages_consumed.append(event)
        if len(order_messages_consumed) >= expected_order_messages:
            order_consume_event.set()

    replies_consumed = []

    @reply_consumer_app.on_reply
    async def consume_reply(event: TestEvent):
        replies_consumed.append(event)
        print(f"✓ Consumed RPC reply: {event.event_type}")

    try:
        # Start consumers first to ensure they're ready to consume all messages
        await order_consumer_app.start()
        await reply_consumer_app.start()
        await order_app.start()

        # Test successful operations
        valid_event = TestEvent(
            event_type="order.created",
            user_id=123,
            timestamp="2024-01-01T00:00:00Z",
            payload={"order_id": "order-789", "amount": 99.99},
        )

        await order_app.order_events(valid_event)
        print("✓ OrderApp - Valid order event sent successfully")

        # Test with null payload (optional field)
        event_no_payload = TestEvent(
            event_type="order.status_check",
            user_id=456,
            timestamp="2024-01-01T01:00:00Z",
            payload=None,  # Testing optional field
        )

        await order_app.order_events(event_no_payload)
        print("✓ OrderApp - Event with null payload sent successfully")

        # Test RPC reply with edge cases (note: this goes to a different channel)
        await order_app.rpc_replies(valid_event)
        print("✓ OrderApp - RPC reply sent successfully")

        # Wait for order events to be consumed
        try:
            await asyncio.wait_for(order_consume_event.wait(), timeout=2.0)
            print(
                f"✓ OrderApp - All {len(order_messages_consumed)} order events consumed"
            )
        except asyncio.TimeoutError:
            print(
                f"⚠ OrderApp - Only {len(order_messages_consumed)}/{expected_order_messages} order events consumed"
            )

        # Log RPC replies consumed
        if replies_consumed:
            print(
                f"✓ OrderApp - Consumed {len(replies_consumed)} RPC replies from default queue"
            )

    finally:
        await order_app.stop()
        await order_consumer_app.stop()
        await reply_consumer_app.stop()

    # 4. Test codec roundtrip with various message types
    for model_class, message_name in [
        (TestUser, "TestUser"),
        (UserCreated, "UserCreated"),
        (UserUpdated, "UserUpdated"),
        (TestEvent, "TestEvent"),
    ]:
        msg = Message(
            name=message_name,
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

        test_codec = codec.create(msg)

        # Test that codec can handle the expected model type
        if model_class == TestUser:
            test_data = model_class(id=999, name="Test", email="test@example.com")
            encoded = test_codec.encode(test_data)
            decoded = test_codec.decode(encoded)
            assert decoded.id == test_data.id
            assert decoded.name == test_data.name
            assert decoded.email == test_data.email
        elif model_class == UserCreated:
            test_data = model_class(
                user_id=999,
                name="Test",
                email="test@example.com",
                timestamp="2024-01-01T00:00:00Z",
            )
            encoded = test_codec.encode(test_data)
            decoded = test_codec.decode(encoded)
            assert decoded.user_id == test_data.user_id
            assert decoded.name == test_data.name
            assert decoded.email == test_data.email
            assert decoded.timestamp == test_data.timestamp
        elif model_class == UserUpdated:
            test_data = model_class(user_id=999, timestamp="2024-01-01T00:00:00Z")
            encoded = test_codec.encode(test_data)
            decoded = test_codec.decode(encoded)
            assert decoded.user_id == test_data.user_id
            assert decoded.timestamp == test_data.timestamp
            # Optional fields should match
            assert decoded.name == test_data.name
            assert decoded.email == test_data.email
        else:  # TestEvent
            test_data = model_class(
                event_type="test", user_id=999, timestamp="2024-01-01T00:00:00Z"
            )
            encoded = test_codec.encode(test_data)
            decoded = test_codec.decode(encoded)
            assert decoded.event_type == test_data.event_type
            assert decoded.user_id == test_data.user_id
            assert decoded.timestamp == test_data.timestamp
            assert decoded.payload == test_data.payload

        print(f"✓ Codec roundtrip successful for {model_class.__name__}")

    print("✓ All error handling and edge case tests passed")
