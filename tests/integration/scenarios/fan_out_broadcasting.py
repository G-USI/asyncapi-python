"""Fan-out broadcasting scenario - Single producer to multiple consumers"""

import asyncio
from uuid import uuid4

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

# Import test models
from ..test_app.messages.json import UserAction

# Generate unique channel ID for this scenario to avoid collisions
SCENARIO_CHANNEL_ID = str(uuid4())[:8]


class EventBroadcaster(BaseApplication):
    """Event broadcaster that publishes user action events to multiple consumers"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory=wire_factory, codec_factory=codec_factory)
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup event broadcasting endpoints for each consumer service"""

        # Create separate endpoints for each consumer service to simulate fan-out
        self.broadcast_endpoints = {}
        service_names = [
            "EmailService",
            "SmsService",
            "PushNotificationService",
            "AnalyticsService",
            "AuditService",
        ]

        for service_name in service_names:
            # User actions channel specific to this consumer
            user_actions_channel = Channel(
                address=f"fan-out.{SCENARIO_CHANNEL_ID}.user.actions.{service_name}",
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

            user_action_message = Message(
                name="UserAction",
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

            broadcast_operation = Operation(
                channel=user_actions_channel,
                messages=[user_action_message],
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

            # Register endpoint for this specific service
            endpoint = self._register_endpoint(broadcast_operation)
            self.broadcast_endpoints[service_name] = endpoint

    async def broadcast_user_action(self, action):
        """Broadcast action to all consumer services (simulating fan-out)"""
        # Send to all service-specific channels to simulate broadcast behavior
        tasks = []
        for service_name, endpoint in self.broadcast_endpoints.items():
            tasks.append(endpoint(action))
        await asyncio.gather(*tasks)


class BaseConsumerService(BaseApplication):
    """Base class for services that consume user action events"""

    def __init__(
        self,
        service_name: str,
        wire_factory: AbstractWireFactory,
        codec_factory: CodecFactory,
    ):
        # Pass service_name via endpoint_params
        endpoint_params = {"service_name": service_name}
        super().__init__(
            wire_factory=wire_factory,
            codec_factory=codec_factory,
            endpoint_params=endpoint_params,
        )
        self.service_name = service_name  # Store for use in _setup_endpoints
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup user action consumption endpoint with service-specific queue for fan-out"""

        # Consumer for user actions with unique ID and service-specific queue for true fan-out
        user_actions_channel = Channel(
            address=f"fan-out.{SCENARIO_CHANNEL_ID}.user.actions.{self.service_name}",
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

        user_action_message = Message(
            name="UserAction",
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

        consume_operation = Operation(
            channel=user_actions_channel,
            messages=[user_action_message],
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

        self.on_user_action = self._register_endpoint(consume_operation)


class EmailService(BaseConsumerService):
    """Email service that processes user actions for email notifications"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__("EmailService", wire_factory, codec_factory)


class SmsService(BaseConsumerService):
    """SMS service that processes user actions for SMS notifications"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__("SmsService", wire_factory, codec_factory)


class PushNotificationService(BaseConsumerService):
    """Push notification service that processes user actions for mobile notifications"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__("PushNotificationService", wire_factory, codec_factory)


class AnalyticsService(BaseConsumerService):
    """Analytics service that processes user actions for data analysis"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__("AnalyticsService", wire_factory, codec_factory)


class AuditService(BaseConsumerService):
    """Audit service that processes user actions for compliance logging"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__("AuditService", wire_factory, codec_factory)


async def fan_out_broadcasting(wire: AbstractWireFactory, codec: CodecFactory) -> None:
    """Test fan-out broadcasting scenario with single producer and multiple consumers"""
    print(
        f"Testing fan-out broadcasting with {wire.__class__.__name__} + {codec.__class__.__name__}"
    )

    # Create broadcaster
    broadcaster = EventBroadcaster(wire, codec)

    # Create all consumer services
    email_service = EmailService(wire, codec)
    sms_service = SmsService(wire, codec)
    push_service = PushNotificationService(wire, codec)
    analytics_service = AnalyticsService(wire, codec)
    audit_service = AuditService(wire, codec)

    consumer_services = [
        email_service,
        sms_service,
        push_service,
        analytics_service,
        audit_service,
    ]

    # Track received events per service
    received_events: dict[str, list] = {
        "EmailService": [],
        "SmsService": [],
        "PushNotificationService": [],
        "AnalyticsService": [],
        "AuditService": [],
    }

    # Events to track completion
    expected_events_per_service = 3  # We'll broadcast 3 events
    expected_total_events = expected_events_per_service * len(consumer_services)
    consume_event = asyncio.Event()
    total_received = 0

    # Register handlers for each service using decorator pattern
    @email_service.on_user_action
    async def handle_email_user_action(action: UserAction):
        nonlocal total_received
        received_events["EmailService"].append(action)
        total_received += 1
        print(
            f"✓ EmailService received: {action.action_type} for user {action.user_id}"
        )
        if total_received >= expected_total_events:
            consume_event.set()

    @sms_service.on_user_action
    async def handle_sms_user_action(action: UserAction):
        nonlocal total_received
        received_events["SmsService"].append(action)
        total_received += 1
        print(f"✓ SmsService received: {action.action_type} for user {action.user_id}")
        if total_received >= expected_total_events:
            consume_event.set()

    @push_service.on_user_action
    async def handle_push_user_action(action: UserAction):
        nonlocal total_received
        received_events["PushNotificationService"].append(action)
        total_received += 1
        print(
            f"✓ PushNotificationService received: {action.action_type} for user {action.user_id}"
        )
        if total_received >= expected_total_events:
            consume_event.set()

    @analytics_service.on_user_action
    async def handle_analytics_user_action(action: UserAction):
        nonlocal total_received
        received_events["AnalyticsService"].append(action)
        total_received += 1
        print(
            f"✓ AnalyticsService received: {action.action_type} for user {action.user_id}"
        )
        if total_received >= expected_total_events:
            consume_event.set()

    @audit_service.on_user_action
    async def handle_audit_user_action(action: UserAction):
        nonlocal total_received
        received_events["AuditService"].append(action)
        total_received += 1
        print(
            f"✓ AuditService received: {action.action_type} for user {action.user_id}"
        )
        if total_received >= expected_total_events:
            consume_event.set()

    try:
        # Start all consumers first, then broadcaster
        for service in consumer_services:
            await service.start()
        await broadcaster.start()

        # Broadcast different types of user actions
        user_actions = [
            UserAction(
                action_type="user.registration",
                user_id=123,
                timestamp="2024-01-01T00:00:00Z",
                metadata={"source": "web", "campaign": "signup_bonus"},
            ),
            UserAction(
                action_type="user.login",
                user_id=456,
                timestamp="2024-01-01T01:00:00Z",
                metadata={"device": "mobile", "location": "US"},
            ),
            UserAction(
                action_type="user.purchase",
                user_id=789,
                timestamp="2024-01-01T02:00:00Z",
                metadata={"amount": 99.99, "product": "premium_plan"},
            ),
        ]

        # Broadcast each event
        for action in user_actions:
            await broadcaster.broadcast_user_action(action)
            print(f"✓ Broadcasted: {action.action_type} for user {action.user_id}")
            # Small delay between broadcasts to simulate realistic timing
            await asyncio.sleep(0.01)

        # Wait for all consumers to receive all events
        try:
            await asyncio.wait_for(consume_event.wait(), timeout=3.0)
            print(f"✓ All consumers received all events (total: {total_received})")
        except asyncio.TimeoutError:
            print(
                f"⚠ Only {total_received}/{expected_total_events} events consumed within timeout"
            )

        # Verify each service received all events
        for service_name, events in received_events.items():
            assert (
                len(events) == expected_events_per_service
            ), f"{service_name} should have received {expected_events_per_service} events, got {len(events)}"

            # Verify events are in correct order and have correct content
            event_types = [event.action_type for event in events]
            expected_types = ["user.registration", "user.login", "user.purchase"]
            assert (
                event_types == expected_types
            ), f"{service_name} received events in wrong order: {event_types}"

            # Verify user IDs match
            user_ids = [event.user_id for event in events]
            expected_user_ids = [123, 456, 789]
            assert (
                user_ids == expected_user_ids
            ), f"{service_name} received wrong user IDs: {user_ids}"

        print(
            f"✓ All {len(consumer_services)} consumer services received events correctly"
        )

        # Test that consumers can process at different speeds (simulate processing time)
        processing_results = {}

        async def simulate_processing(service_name: str, processing_time: float):
            await asyncio.sleep(processing_time)
            processing_results[service_name] = (
                f"Processed {len(received_events[service_name])} events"
            )
            print(f"✓ {service_name} completed processing after {processing_time}s")

        # Simulate different processing speeds
        processing_tasks = [
            simulate_processing("EmailService", 0.1),  # Fast
            simulate_processing("SmsService", 0.2),  # Medium
            simulate_processing("PushNotificationService", 0.05),  # Very fast
            simulate_processing("AnalyticsService", 0.3),  # Slow
            simulate_processing("AuditService", 0.15),  # Medium-fast
        ]

        # All services can process independently
        await asyncio.gather(*processing_tasks)

        # Verify all services completed processing
        assert len(processing_results) == len(
            consumer_services
        ), "Not all services completed processing"
        for service_name in received_events.keys():
            assert (
                service_name in processing_results
            ), f"{service_name} did not complete processing"

        print("✓ All consumers processed events at their own pace")
        print("✓ Fan-out broadcasting scenario completed successfully")

    finally:
        # Clean shutdown
        await broadcaster.stop()
        for service in consumer_services:
            await service.stop()
