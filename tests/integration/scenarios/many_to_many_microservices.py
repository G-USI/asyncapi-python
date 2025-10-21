"""Many-to-many microservices scenario - Complex service interactions"""

import asyncio
from uuid import uuid4

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

# Import test models
from ..test_app.messages.json import (
    InventoryUpdated,
    OrderPlaced,
    OrderShipped,
    PaymentProcessed,
    UserCreated,
)

# Generate unique channel ID for this scenario to avoid collisions
SCENARIO_CHANNEL_ID = str(uuid4())[:8]


class UserServiceApp(BaseApplication):
    """User service that publishes user creation events"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory=wire_factory, codec_factory=codec_factory)
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup user creation publishing endpoint"""

        # User created events channel with unique ID
        user_created_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.users.created",
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

        self.publish_user_created = self._register_endpoint(user_created_operation)


class OrderServiceApp(BaseApplication):
    """Order service that consumes user events and publishes order events"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory=wire_factory, codec_factory=codec_factory)
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup user consumption and order publishing endpoints"""

        # Consumer for user created events with unique ID
        user_created_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.users.created",
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

        # Publishers for order placed events - separate channels for payment and inventory services
        self.order_placed_endpoints = {}

        # Payment service channel
        payment_order_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.orders.placed.payment",
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

        # Inventory service channel
        inventory_order_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.orders.placed.inventory",
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

        order_placed_message = Message(
            name="OrderPlaced",
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

        # Payment service endpoint
        payment_operation = Operation(
            channel=payment_order_channel,
            messages=[order_placed_message],
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

        # Inventory service endpoint
        inventory_operation = Operation(
            channel=inventory_order_channel,
            messages=[order_placed_message],
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

        self.order_placed_endpoints["payment"] = self._register_endpoint(
            payment_operation
        )
        self.order_placed_endpoints["inventory"] = self._register_endpoint(
            inventory_operation
        )

    async def publish_order_placed(self, order):
        """Publish order to both payment and inventory services"""
        await asyncio.gather(
            self.order_placed_endpoints["payment"](order),
            self.order_placed_endpoints["inventory"](order),
        )


class PaymentServiceApp(BaseApplication):
    """Payment service that consumes order events and publishes payment events"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory=wire_factory, codec_factory=codec_factory)
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup order consumption and payment publishing endpoints"""

        # Consumer for order placed events from payment-specific channel
        order_placed_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.orders.placed.payment",
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

        order_placed_message = Message(
            name="OrderPlaced",
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

        order_placed_operation = Operation(
            channel=order_placed_channel,
            messages=[order_placed_message],
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

        self.on_order_placed = self._register_endpoint(order_placed_operation)

        # Publisher for payment processed events
        payment_processed_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.payments.processed",
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

        payment_processed_message = Message(
            name="PaymentProcessed",
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

        payment_processed_operation = Operation(
            channel=payment_processed_channel,
            messages=[payment_processed_message],
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

        self.publish_payment_processed = self._register_endpoint(
            payment_processed_operation
        )


class InventoryServiceApp(BaseApplication):
    """Inventory service that consumes order events and publishes inventory events"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory=wire_factory, codec_factory=codec_factory)
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup order consumption and inventory publishing endpoints"""

        # Consumer for order placed events from inventory-specific channel
        order_placed_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.orders.placed.inventory",
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

        order_placed_message = Message(
            name="OrderPlaced",
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

        order_placed_operation = Operation(
            channel=order_placed_channel,
            messages=[order_placed_message],
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

        self.on_order_placed = self._register_endpoint(order_placed_operation)

        # Publisher for inventory updated events
        inventory_updated_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.inventory.updated",
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

        inventory_updated_message = Message(
            name="InventoryUpdated",
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

        inventory_updated_operation = Operation(
            channel=inventory_updated_channel,
            messages=[inventory_updated_message],
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

        self.publish_inventory_updated = self._register_endpoint(
            inventory_updated_operation
        )


class ShippingServiceApp(BaseApplication):
    """Shipping service that consumes payment and inventory events, publishes shipping events"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory=wire_factory, codec_factory=codec_factory)
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup payment/inventory consumption and shipping publishing endpoints"""

        # Consumer for payment processed events
        payment_processed_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.payments.processed",
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

        payment_processed_message = Message(
            name="PaymentProcessed",
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

        payment_processed_operation = Operation(
            channel=payment_processed_channel,
            messages=[payment_processed_message],
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

        self.on_payment_processed = self._register_endpoint(payment_processed_operation)

        # Consumer for inventory updated events
        inventory_updated_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.inventory.updated",
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

        inventory_updated_message = Message(
            name="InventoryUpdated",
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

        inventory_updated_operation = Operation(
            channel=inventory_updated_channel,
            messages=[inventory_updated_message],
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

        self.on_inventory_updated = self._register_endpoint(inventory_updated_operation)

        # Publisher for order shipped events
        order_shipped_channel = Channel(
            address=f"many-to-many.{SCENARIO_CHANNEL_ID}.orders.shipped",
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

        order_shipped_message = Message(
            name="OrderShipped",
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

        order_shipped_operation = Operation(
            channel=order_shipped_channel,
            messages=[order_shipped_message],
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

        self.publish_order_shipped = self._register_endpoint(order_shipped_operation)


async def many_to_many_microservices(
    wire: AbstractWireFactory, codec: CodecFactory
) -> None:
    """Test many-to-many microservices scenario with complex service interactions"""
    print(
        f"Testing many-to-many microservices with {wire.__class__.__name__} + {codec.__class__.__name__}"
    )

    # Create all services
    user_service = UserServiceApp(wire, codec)
    order_service = OrderServiceApp(wire, codec)
    payment_service = PaymentServiceApp(wire, codec)
    inventory_service = InventoryServiceApp(wire, codec)
    shipping_service = ShippingServiceApp(wire, codec)

    all_services = [
        user_service,
        order_service,
        payment_service,
        inventory_service,
        shipping_service,
    ]

    # Track events flowing through the system
    events_received: dict[str, list] = {
        "order_service_user_events": [],
        "payment_service_order_events": [],
        "inventory_service_order_events": [],
        "shipping_service_payment_events": [],
        "shipping_service_inventory_events": [],
        "final_shipped_orders": [],
    }

    # Track order completion status
    order_statuses = (
        {}
    )  # order_id -> {"payment": bool, "inventory": bool, "shipped": bool}

    # Events for workflow coordination
    order_placed_event = asyncio.Event()
    payment_processed_event = asyncio.Event()
    inventory_updated_event = asyncio.Event()
    order_shipped_event = asyncio.Event()

    # Set up service handlers with workflow logic
    @order_service.on_user_created
    async def handle_user_created(user: UserCreated):
        # Only process our specific test users to avoid interference from other tests
        if user.user_id not in [99999, 99998, 99997]:
            print(
                f"ⓘ OrderService: Ignoring user from other test: {user.name} (ID: {user.user_id})"
            )
            return

        events_received["order_service_user_events"].append(user)
        print(f"✓ OrderService: Processing user {user.name} (ID: {user.user_id})")

        # Create an order for this user
        order = OrderPlaced(
            order_id=f"order-{user.user_id}",
            user_id=user.user_id,
            items=[
                {"sku": "item-123", "quantity": 2},
                {"sku": "item-456", "quantity": 1},
            ],
            total_amount=199.99,
            timestamp="2024-01-01T00:00:00Z",
        )

        # Initialize order status tracking
        order_statuses[order.order_id] = {
            "payment": False,
            "inventory": False,
            "shipped": False,
        }

        await order_service.publish_order_placed(order)
        print(f"✓ OrderService: Published order {order.order_id}")
        order_placed_event.set()

    @payment_service.on_order_placed
    async def handle_order_for_payment(order: OrderPlaced):
        # Only process our test orders
        if order.user_id not in [99999, 99998, 99997]:
            print(f"ⓘ PaymentService: Ignoring order from other test: {order.order_id}")
            return

        events_received["payment_service_order_events"].append(order)
        print(
            f"✓ PaymentService: Processing payment for order {order.order_id} (${order.total_amount})"
        )

        # Process payment
        payment = PaymentProcessed(
            order_id=order.order_id,
            payment_id=f"pay-{order.order_id}",
            amount=order.total_amount,
            payment_method="credit_card",
            timestamp="2024-01-01T00:01:00Z",
        )

        order_statuses[order.order_id]["payment"] = True

        await payment_service.publish_payment_processed(payment)
        print(f"✓ PaymentService: Payment {payment.payment_id} processed")
        payment_processed_event.set()

    @inventory_service.on_order_placed
    async def handle_order_for_inventory(order: OrderPlaced):
        # Only process our test orders
        if order.user_id not in [99999, 99998, 99997]:
            print(
                f"ⓘ InventoryService: Ignoring order from other test: {order.order_id}"
            )
            return

        events_received["inventory_service_order_events"].append(order)
        print(f"✓ InventoryService: Reserving inventory for order {order.order_id}")

        # Update inventory
        inventory = InventoryUpdated(
            order_id=order.order_id,
            items_reserved=[
                {"sku": item["sku"], "quantity": item["quantity"], "reserved": True}
                for item in order.items
            ],
            timestamp="2024-01-01T00:01:30Z",
        )

        order_statuses[order.order_id]["inventory"] = True

        await inventory_service.publish_inventory_updated(inventory)
        print(f"✓ InventoryService: Inventory updated for order {order.order_id}")
        inventory_updated_event.set()

    @shipping_service.on_payment_processed
    async def handle_payment_processed(payment: PaymentProcessed):
        # Only process our test orders
        if not (
            payment.order_id.startswith("order-99999")
            or payment.order_id.startswith("order-99998")
            or payment.order_id.startswith("order-99997")
        ):
            print(
                f"ⓘ ShippingService: Ignoring payment from other test: {payment.order_id}"
            )
            return

        events_received["shipping_service_payment_events"].append(payment)
        print(f"✓ ShippingService: Payment confirmed for order {payment.order_id}")

        # Check if we can ship (both payment and inventory must be ready)
        await _check_and_ship_order(payment.order_id)

    @shipping_service.on_inventory_updated
    async def handle_inventory_updated(inventory: InventoryUpdated):
        # Only process our test orders
        if not (
            inventory.order_id.startswith("order-99999")
            or inventory.order_id.startswith("order-99998")
            or inventory.order_id.startswith("order-99997")
        ):
            print(
                f"ⓘ ShippingService: Ignoring inventory from other test: {inventory.order_id}"
            )
            return

        events_received["shipping_service_inventory_events"].append(inventory)
        print(f"✓ ShippingService: Inventory confirmed for order {inventory.order_id}")

        # Check if we can ship (both payment and inventory must be ready)
        await _check_and_ship_order(inventory.order_id)

    async def _check_and_ship_order(order_id: str):
        """Ship order if both payment and inventory are ready"""
        if order_id in order_statuses:
            status = order_statuses[order_id]
            if status["payment"] and status["inventory"] and not status["shipped"]:
                # Both prerequisites met, ship the order
                shipped_order = OrderShipped(
                    order_id=order_id,
                    tracking_number=f"track-{order_id}",
                    carrier="FastShip",
                    timestamp="2024-01-01T00:02:00Z",
                )

                status["shipped"] = True
                events_received["final_shipped_orders"].append(shipped_order)

                await shipping_service.publish_order_shipped(shipped_order)
                print(
                    f"✓ ShippingService: Order {order_id} shipped with tracking {shipped_order.tracking_number}"
                )
                order_shipped_event.set()

    try:
        # Start all services
        for service in all_services:
            await service.start()

        print("✓ All microservices started")

        # Clear any existing queues by waiting a bit for cleanup
        await asyncio.sleep(0.1)

        # Initiate the workflow by creating a user
        test_user = UserCreated(
            user_id=99999,  # Use unique ID to avoid conflicts with other tests
            name="ManyToMany TestUser",
            email="manytomany@example.com",
            timestamp="2024-01-01T00:00:00Z",
        )

        await user_service.publish_user_created(test_user)
        print(f"✓ UserService: Published user creation for {test_user.name}")

        # Wait for each step of the workflow
        await asyncio.wait_for(order_placed_event.wait(), timeout=2.0)
        await asyncio.wait_for(payment_processed_event.wait(), timeout=2.0)
        await asyncio.wait_for(inventory_updated_event.wait(), timeout=2.0)
        await asyncio.wait_for(order_shipped_event.wait(), timeout=2.0)

        print("✓ Complete workflow executed successfully")

        # Verify the workflow completed correctly
        assert len(events_received["order_service_user_events"]) == 1
        assert len(events_received["payment_service_order_events"]) == 1
        assert len(events_received["inventory_service_order_events"]) == 1
        assert len(events_received["shipping_service_payment_events"]) == 1
        assert len(events_received["shipping_service_inventory_events"]) == 1
        assert len(events_received["final_shipped_orders"]) == 1

        # Verify order completion
        shipped_order = events_received["final_shipped_orders"][0]
        order_id = shipped_order.order_id
        assert order_statuses[order_id]["payment"] is True
        assert order_statuses[order_id]["inventory"] is True
        assert order_statuses[order_id]["shipped"] is True

        print(
            f"✓ Order {order_id} completed full workflow: User → Order → Payment & Inventory → Shipping"
        )

        # Test multiple orders to verify scalability
        print("✓ Testing multiple concurrent orders...")

        # Reset events for second test
        for key in events_received:
            events_received[key].clear()
        order_placed_event.clear()
        payment_processed_event.clear()
        inventory_updated_event.clear()
        order_shipped_event.clear()

        # Create multiple users concurrently
        users = [
            UserCreated(
                user_id=99998,
                name="Bob Smith MultiTest",
                email="bob@example.com",
                timestamp="2024-01-01T01:00:00Z",
            ),
            UserCreated(
                user_id=99997,
                name="Carol Brown MultiTest",
                email="carol@example.com",
                timestamp="2024-01-01T01:00:01Z",
            ),
        ]

        # Publish users concurrently
        await asyncio.gather(
            *[user_service.publish_user_created(user) for user in users]
        )

        # Wait for all workflows to complete (should handle multiple orders)
        await asyncio.sleep(1.0)  # Give time for all events to propagate

        # Verify multiple orders were processed
        assert (
            len(events_received["final_shipped_orders"]) >= 2
        ), f"Expected at least 2 shipped orders, got {len(events_received['final_shipped_orders'])}"

        print(
            f"✓ Successfully processed {len(events_received['final_shipped_orders'])} concurrent orders"
        )
        print("✓ Many-to-many microservices scenario completed successfully")

    except asyncio.TimeoutError as e:
        print(
            f"⚠ Workflow timeout - some services may not have processed events in time"
        )
        print(f"Events received: {events_received}")
        raise e

    finally:
        # Clean shutdown
        for service in all_services:
            await service.stop()
