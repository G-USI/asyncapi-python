"""Fan-in logging scenario - Multiple producers to single consumer"""

import asyncio
import uuid
from uuid import uuid4

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

# Import test models
from ..test_app.messages.json import LogEvent

# Generate unique channel ID for this scenario to avoid collisions
SCENARIO_CHANNEL_ID = str(uuid4())[:8]


class BaseLoggingService(BaseApplication):
    """Base class for services that produce log events"""

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
        """Setup logging endpoint for this service"""

        # Logging channel - all services log to the same channel with unique ID
        logging_channel = Channel(
            address=f"fan-in.{SCENARIO_CHANNEL_ID}.system.logs",
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

        log_message = Message(
            name="LogEvent",
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

        logging_operation = Operation(
            channel=logging_channel,
            messages=[log_message],
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

        self.log = self._register_endpoint(logging_operation)

    async def log_info(self, message: str, trace_id: str | None = None):
        """Log an info message"""
        event = LogEvent(
            service_name=self.service_name,
            level="INFO",
            message=message,
            timestamp="2024-01-01T00:00:00Z",
            trace_id=trace_id,
        )
        await self.log(event)

    async def log_error(self, message: str, trace_id: str | None = None):
        """Log an error message"""
        event = LogEvent(
            service_name=self.service_name,
            level="ERROR",
            message=message,
            timestamp="2024-01-01T00:00:00Z",
            trace_id=trace_id,
        )
        await self.log(event)


class UserService(BaseLoggingService):
    """User service that logs user-related events"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__("UserService", wire_factory, codec_factory)


class OrderService(BaseLoggingService):
    """Order service that logs order-related events"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__("OrderService", wire_factory, codec_factory)


class PaymentService(BaseLoggingService):
    """Payment service that logs payment-related events"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__("PaymentService", wire_factory, codec_factory)


class NotificationService(BaseLoggingService):
    """Notification service that logs notification-related events"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__("NotificationService", wire_factory, codec_factory)


class LogAggregatorService(BaseApplication):
    """Log aggregator service that receives logs from all services"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory=wire_factory, codec_factory=codec_factory)
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup log consumption endpoint"""

        # Consumer for system logs with unique ID
        logging_channel = Channel(
            address=f"fan-in.{SCENARIO_CHANNEL_ID}.system.logs",
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

        log_message = Message(
            name="LogEvent",
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

        logging_operation = Operation(
            channel=logging_channel,
            messages=[log_message],
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

        self.on_log_event = self._register_endpoint(logging_operation)


async def fan_in_logging(wire: AbstractWireFactory, codec: CodecFactory) -> None:
    """Test fan-in logging scenario with multiple producers and single consumer"""
    print(
        f"Testing fan-in logging with {wire.__class__.__name__} + {codec.__class__.__name__}"
    )

    # Create all producer services
    user_service = UserService(wire, codec)
    order_service = OrderService(wire, codec)
    payment_service = PaymentService(wire, codec)
    notification_service = NotificationService(wire, codec)

    # Create consumer service
    log_aggregator = LogAggregatorService(wire, codec)

    # Track received logs
    received_logs = []
    expected_log_count = 12  # 3 logs from each of 4 services
    consume_event = asyncio.Event()

    @log_aggregator.on_log_event
    async def handle_log_event(log: LogEvent):
        received_logs.append(log)
        print(
            f"✓ LogAggregator received: {log.service_name} [{log.level}] {log.message}"
        )
        if len(received_logs) >= expected_log_count:
            consume_event.set()

    producer_services = [
        user_service,
        order_service,
        payment_service,
        notification_service,
    ]

    try:
        # Start consumer first, then all producers
        await log_aggregator.start()
        for service in producer_services:
            await service.start()

        # Generate logs from all services concurrently
        trace_id = str(uuid.uuid4())

        # Each service logs multiple events with some sharing the same trace_id
        log_tasks = [
            # UserService logs
            user_service.log_info("User registration started", trace_id),
            user_service.log_info("User validation completed", trace_id),
            user_service.log_error("Password complexity check failed"),
            # OrderService logs
            order_service.log_info("Order validation started", trace_id),
            order_service.log_info("Order items verified", trace_id),
            order_service.log_info("Order created successfully"),
            # PaymentService logs
            payment_service.log_info("Payment gateway connection established"),
            payment_service.log_info("Payment processing started", trace_id),
            payment_service.log_error("Credit card declined"),
            # NotificationService logs
            notification_service.log_info("Email template loaded"),
            notification_service.log_info("SMS gateway ready"),
            notification_service.log_error("Push notification service unavailable"),
        ]

        # Send all logs concurrently to simulate real-world load
        await asyncio.gather(*log_tasks)
        print("✓ All services sent their log messages")

        # Wait for all logs to be consumed
        try:
            await asyncio.wait_for(consume_event.wait(), timeout=3.0)
            print(f"✓ LogAggregator consumed all {len(received_logs)} log messages")
        except asyncio.TimeoutError:
            print(
                f"⚠ Only {len(received_logs)}/{expected_log_count} log messages consumed within timeout"
            )

        # Verify we received logs from all services
        services_logged = set(log.service_name for log in received_logs)
        expected_services = {
            "UserService",
            "OrderService",
            "PaymentService",
            "NotificationService",
        }
        assert (
            services_logged == expected_services
        ), f"Missing logs from services: {expected_services - services_logged}"

        # Verify we have different log levels
        log_levels = set(log.level for log in received_logs)
        assert "INFO" in log_levels, "Should have INFO level logs"
        assert "ERROR" in log_levels, "Should have ERROR level logs"

        # Verify trace_id correlation
        trace_logs = [log for log in received_logs if log.trace_id == trace_id]
        assert (
            len(trace_logs) >= 4
        ), f"Should have at least 4 logs with trace_id {trace_id}, got {len(trace_logs)}"

        # Verify log distribution across services
        log_counts_by_service: dict[str, int] = {}
        for log in received_logs:
            log_counts_by_service[log.service_name] = (
                log_counts_by_service.get(log.service_name, 0) + 1
            )

        print(f"✓ Log distribution: {log_counts_by_service}")
        for service_name, count in log_counts_by_service.items():
            assert count == 3, f"{service_name} should have sent 3 logs, got {count}"

        print("✓ Fan-in logging scenario completed successfully")

    finally:
        # Clean shutdown
        await log_aggregator.stop()
        for service in producer_services:
            await service.stop()
