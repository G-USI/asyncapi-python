"""Producer->Consumer roundtrip scenario"""

import asyncio

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

from ..test_app.messages.json import UserCreated, UserUpdated


class UserManagementApp(BaseApplication):
    """User management service with endpoints for testing scenarios"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        # Disable handler validation for integration tests
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


class ConsumerApp(BaseApplication):
    """Consumer app to receive messages"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        # Disable handler validation for integration tests
        super().__init__(
            wire_factory=wire_factory,
            codec_factory=codec_factory,
            endpoint_params={"disable_handler_validation": True},
        )
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup consumer endpoints to match producer channels"""

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
            action="receive",  # Consumer receives messages
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


async def producer_consumer_roundtrip(
    wire: AbstractWireFactory, codec: CodecFactory
) -> None:
    """Test producer->consumer message roundtrip using UserManagementApp"""
    print(
        f"Testing roundtrip with {wire.__class__.__name__} + {codec.__class__.__name__}"
    )

    # 1. Create producer and consumer apps
    producer_app = UserManagementApp(wire, codec)
    consumer_app = ConsumerApp(wire, codec)

    # 2. Set up consumer handler BEFORE starting to avoid missing messages
    received_messages = []
    consume_event = asyncio.Event()

    @consumer_app.on_user_created
    async def handle_user_created(user: UserCreated):
        received_messages.append(user)
        print(f"✓ Consumer received user created event: {user}")
        # Only set event when we receive the message we expect (from this test)
        if user.user_id == 123 and user.name == "Alice":
            consume_event.set()

    try:
        # 3. Start both applications (consumer will start consuming immediately)
        await producer_app.start()
        await consumer_app.start()

        # 4. Create and send test user data
        test_user = UserCreated(
            user_id=123,
            name="Alice",
            email="alice@example.com",
            timestamp="2024-01-01T00:00:00Z",
        )

        await producer_app.user_created(test_user)
        print(f"✓ Producer sent user created event: {test_user}")

        # 5. Wait for consumer to receive the message
        try:
            await asyncio.wait_for(consume_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            raise AssertionError("Consumer did not receive message within timeout")

        # 6. Verify we received our specific message
        our_message = None
        for msg in received_messages:
            if msg.user_id == 123 and msg.name == "Alice":
                our_message = msg
                break

        assert (
            our_message is not None
        ), f"Expected message not found. Received: {received_messages}"
        assert our_message.user_id == test_user.user_id
        assert our_message.name == test_user.name
        assert our_message.email == test_user.email
        print("✓ Message content verified correctly")

        # Log if we consumed extra messages from queue
        if len(received_messages) > 1:
            print(
                f"ℹ Consumed {len(received_messages)} total messages from queue (including {len(received_messages)-1} from previous tests)"
            )

        # 7. Test user updates with producer receiving
        received_updates = []
        update_event = asyncio.Event()

        @producer_app.user_updates
        async def handle_user_update(update: UserUpdated):
            received_updates.append(update)
            print(f"✓ Producer received user update: {update}")
            update_event.set()

        # 8. Create a second producer to send updates
        class Producer2App(BaseApplication):
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
                # Setup publisher for user updates
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

                self.send_update = self._register_endpoint(user_update_operation)

        producer2_app = Producer2App(wire, codec)
        await producer2_app.start()

        # 9. Send update from producer2
        test_update = UserUpdated(
            user_id=123,
            name="Alice Updated",
            email="alice.updated@example.com",
            timestamp="2024-01-01T01:00:00Z",
        )

        await producer2_app.send_update(test_update)
        print(f"✓ Producer2 sent user update: {test_update}")

        # 10. Wait for producer1 to receive the update
        try:
            await asyncio.wait_for(update_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            raise AssertionError("Producer did not receive update within timeout")

        # 11. Verify the update was received correctly
        assert len(received_updates) == 1
        received_update = received_updates[0]
        assert received_update.user_id == test_update.user_id
        assert received_update.name == test_update.name
        assert received_update.email == test_update.email

        print("✓ Roundtrip successful: all messages produced and consumed correctly")

    finally:
        # Clean shutdown of all apps
        await producer_app.stop()
        await consumer_app.stop()
        if "producer2_app" in locals():
            await producer2_app.stop()
