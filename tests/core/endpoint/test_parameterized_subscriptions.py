"""Tests for parameterized channel subscriptions with wildcards."""

import asyncio
from typing import Any

import pytest

from asyncapi_python.contrib.codec.json import JsonCodecFactory
from asyncapi_python.contrib.wire.in_memory import InMemoryWire
from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.document import Channel, Operation
from asyncapi_python.kernel.document.bindings import (
    AmqpChannelBinding,
    AmqpExchange,
    AmqpExchangeType,
)
from asyncapi_python.kernel.document.channel import AddressParameter, ChannelBindings
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.endpoint import Publisher, Subscriber
from pydantic import BaseModel, RootModel


class AlertMessage(BaseModel):
    """Test message with location and severity fields."""

    location: str
    severity: str
    data: str


@pytest.fixture
def parameterized_channel() -> Channel:
    """Create a parameterized channel with AMQP routing key binding."""
    return Channel(
        key="test_channel",
        address="alerts.{location}.{severity}",
        title="Test Channel",
        summary=None,
        description=None,
        servers=[],
        messages={
            "TestMessage": Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        },
        parameters={
            "location": AddressParameter(
                key="location",
                description="Location code",
                location="$message.payload#/location",
            ),
            "severity": AddressParameter(
                key="severity",
                description="Severity level",
                location="$message.payload#/severity",
            ),
        },
        tags=[],
        external_docs=None,
        bindings=ChannelBindings(
            amqp=AmqpChannelBinding(
                type="routingKey",
                exchange=AmqpExchange(
                    name="test_exchange",
                    type=AmqpExchangeType.TOPIC,
                ),
            )
        ),
    )


@pytest.fixture
def queue_channel() -> Channel:
    """Create a parameterized channel with AMQP queue binding."""
    return Channel(
        key="test_queue",
        address="queue.{priority}",
        title="Test Queue",
        summary=None,
        description=None,
        servers=[],
        messages={
            "TestMessage": Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        },
        parameters={
            "priority": AddressParameter(
                key="priority",
                description="Priority level",
                location="$message.payload#/priority",
            ),
        },
        tags=[],
        external_docs=None,
        bindings=ChannelBindings(
            amqp=AmqpChannelBinding(
                type="queue",
            )
        ),
    )


async def test_subscriber_accepts_parameters():
    """Subscriber should accept parameters dict in decorator."""
    wire = InMemoryWire()

    # Create a minimal module for codec factory with messages.json structure
    import types

    test_module = types.SimpleNamespace()
    test_module.messages = types.SimpleNamespace()
    test_module.messages.json = types.SimpleNamespace()
    test_module.messages.json.TestMessage = AlertMessage
    codec_factory = JsonCodecFactory(test_module)

    operation = Operation(
        key="test_op",
        action="receive",
        title=None,
        summary=None,
        description=None,
        channel=pytest.helpers.create_test_channel(  # type: ignore
            address="alerts.{location}.{severity}",
            binding=AmqpChannelBinding(
                type="routingKey",
                exchange=AmqpExchange(
                    name="test_exchange",
                    type=AmqpExchangeType.TOPIC,
                ),
            ),
        ),
        messages=[
            Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        ],
        reply=None,
        traits=[],
        security=[],
        tags=[],
        external_docs=None,
        bindings=None,
    )

    subscriber = Subscriber(
        operation=operation,
        wire_factory=wire,
        codec_factory=codec_factory,
    )

    # Register handler with wildcard parameters
    @subscriber(parameters={"location": "*", "severity": "high"})
    async def handle_alert(msg: AlertMessage) -> None:
        pass

    # Should not raise
    assert subscriber._subscription_parameters == {"location": "*", "severity": "high"}


async def test_subscriber_wildcard_parameters_flow_to_wire():
    """Subscriber parameters should be passed to wire factory."""
    wire = InMemoryWire()

    import types

    test_module = types.SimpleNamespace()
    test_module.messages = types.SimpleNamespace()
    test_module.messages.json = types.SimpleNamespace()
    test_module.messages.json.TestMessage = AlertMessage
    codec_factory = JsonCodecFactory(test_module)

    # Mock the wire factory to capture parameters
    captured_params: dict[str, str] = {}

    original_create_consumer = wire.create_consumer

    async def mock_create_consumer(**kwargs: Any) -> Any:
        nonlocal captured_params
        captured_params = kwargs.get("parameters", {})
        return await original_create_consumer(**kwargs)

    wire.create_consumer = mock_create_consumer  # type: ignore

    operation = Operation(
        key="test_op",
        action="receive",
        title=None,
        summary=None,
        description=None,
        channel=pytest.helpers.create_test_channel(  # type: ignore
            address="alerts.{location}.{severity}",
            binding=AmqpChannelBinding(
                type="routingKey",
                exchange=AmqpExchange(
                    name="test_exchange",
                    type=AmqpExchangeType.TOPIC,
                ),
            ),
        ),
        messages=[
            Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        ],
        reply=None,
        traits=[],
        security=[],
        tags=[],
        external_docs=None,
        bindings=None,
    )

    subscriber = Subscriber(
        operation=operation,
        wire_factory=wire,
        codec_factory=codec_factory,
    )

    # Register handler with parameters
    @subscriber(parameters={"location": "NYC", "severity": "*"})
    async def handle_alert(msg: AlertMessage) -> None:
        pass

    # Start subscriber (should create consumer with parameters)
    await subscriber.start()

    # Verify parameters were passed to wire factory
    assert captured_params == {"location": "NYC", "severity": "*"}

    await subscriber.stop()


async def test_queue_binding_with_wildcards_raises_error():
    """Queue bindings with wildcard parameters should raise ValueError."""
    from asyncapi_python.contrib.wire.amqp import AmqpWire

    import types

    test_module = types.SimpleNamespace()

    # This would fail at runtime when creating consumer
    wire = AmqpWire("amqp://guest:guest@localhost")
    codec_factory = JsonCodecFactory(test_module)

    operation = Operation(
        key="test_op",
        action="receive",
        title=None,
        summary=None,
        description=None,
        channel=pytest.helpers.create_test_channel(  # type: ignore
            address="queue.{priority}",
            binding=AmqpChannelBinding(type="queue"),
        ),
        messages=[
            Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        ],
        reply=None,
        traits=[],
        security=[],
        tags=[],
        external_docs=None,
        bindings=None,
    )

    subscriber = Subscriber(
        operation=operation,
        wire_factory=wire,
        codec_factory=codec_factory,
    )

    @subscriber(parameters={"priority": "*"})
    async def handle_task(msg: AlertMessage) -> None:
        pass

    # Should raise ValueError when starting (wire layer validation)
    with pytest.raises(ValueError, match="wildcard patterns"):
        await subscriber.start()


async def test_default_empty_parameters():
    """Subscriber without parameters should use empty dict."""
    wire = InMemoryWire()

    import types

    test_module = types.SimpleNamespace()
    test_module.messages = types.SimpleNamespace()
    test_module.messages.json = types.SimpleNamespace()
    test_module.messages.json.TestMessage = AlertMessage
    codec_factory = JsonCodecFactory(test_module)

    operation = Operation(
        key="test_op",
        action="receive",
        title=None,
        summary=None,
        description=None,
        channel=pytest.helpers.create_test_channel(  # type: ignore
            address="simple.queue",
            binding=None,
        ),
        messages=[
            Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        ],
        reply=None,
        traits=[],
        security=[],
        tags=[],
        external_docs=None,
        bindings=None,
    )

    subscriber = Subscriber(
        operation=operation,
        wire_factory=wire,
        codec_factory=codec_factory,
    )

    @subscriber
    async def handle_msg(msg: AlertMessage) -> None:
        pass

    # Should use empty parameters
    assert subscriber._subscription_parameters == {}

    await subscriber.start()
    await subscriber.stop()


async def test_subscriber_rejects_missing_parameters():
    """Subscriber should raise ValueError when required parameters are missing."""
    from asyncapi_python.contrib.wire.amqp import AmqpWire

    wire = AmqpWire("amqp://guest:guest@localhost")

    import types

    test_module = types.SimpleNamespace()
    test_module.messages = types.SimpleNamespace()
    test_module.messages.json = types.SimpleNamespace()
    test_module.messages.json.TestMessage = AlertMessage
    codec_factory = JsonCodecFactory(test_module)

    # Create channel with 2 parameters
    channel = Channel(
        key="test_channel",
        address="alerts.{location}.{severity}",
        title="Test Channel",
        summary=None,
        description=None,
        servers=[],
        messages={
            "TestMessage": Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        },
        parameters={
            "location": AddressParameter(
                key="location",
                description="Location code",
                location="$message.payload#/location",
            ),
            "severity": AddressParameter(
                key="severity",
                description="Severity level",
                location="$message.payload#/severity",
            ),
        },
        tags=[],
        external_docs=None,
        bindings=ChannelBindings(
            amqp=AmqpChannelBinding(
                type="routingKey",
                exchange=AmqpExchange(
                    name="test_exchange",
                    type=AmqpExchangeType.TOPIC,
                ),
            )
        ),
    )

    operation = Operation(
        key="test_op",
        action="receive",
        title=None,
        summary=None,
        description=None,
        channel=channel,
        messages=[
            Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        ],
        reply=None,
        traits=[],
        security=[],
        tags=[],
        external_docs=None,
        bindings=None,
    )

    subscriber = Subscriber(
        operation=operation,
        wire_factory=wire,
        codec_factory=codec_factory,
    )

    # Register with only 1 parameter (missing severity)
    @subscriber(parameters={"location": "NYC"})
    async def handle_alert(msg: AlertMessage) -> None:
        pass

    # Should raise ValueError when starting
    with pytest.raises(ValueError, match="Missing required parameters"):
        await subscriber.start()


async def test_subscriber_rejects_extra_parameters():
    """Subscriber should raise ValueError when extra parameters are provided."""
    from asyncapi_python.contrib.wire.amqp import AmqpWire

    wire = AmqpWire("amqp://guest:guest@localhost")

    import types

    test_module = types.SimpleNamespace()
    test_module.messages = types.SimpleNamespace()
    test_module.messages.json = types.SimpleNamespace()
    test_module.messages.json.TestMessage = AlertMessage
    codec_factory = JsonCodecFactory(test_module)

    # Create channel with 1 parameter
    channel = Channel(
        key="test_channel",
        address="alerts.{location}",
        title="Test Channel",
        summary=None,
        description=None,
        servers=[],
        messages={
            "TestMessage": Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        },
        parameters={
            "location": AddressParameter(
                key="location",
                description="Location code",
                location="$message.payload#/location",
            ),
        },
        tags=[],
        external_docs=None,
        bindings=ChannelBindings(
            amqp=AmqpChannelBinding(
                type="routingKey",
                exchange=AmqpExchange(
                    name="test_exchange",
                    type=AmqpExchangeType.TOPIC,
                ),
            )
        ),
    )

    operation = Operation(
        key="test_op",
        action="receive",
        title=None,
        summary=None,
        description=None,
        channel=channel,
        messages=[
            Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        ],
        reply=None,
        traits=[],
        security=[],
        tags=[],
        external_docs=None,
        bindings=None,
    )

    subscriber = Subscriber(
        operation=operation,
        wire_factory=wire,
        codec_factory=codec_factory,
    )

    # Register with 2 parameters (location + extra severity)
    @subscriber(parameters={"location": "NYC", "severity": "high"})
    async def handle_alert(msg: AlertMessage) -> None:
        pass

    # Should raise ValueError when starting
    with pytest.raises(ValueError, match="Unexpected parameters"):
        await subscriber.start()


async def test_publisher_extracts_parameters_from_root_model():
    """Publisher should extract parameters from RootModel-wrapped payloads."""
    from asyncapi_python.contrib.wire.in_memory import get_bus, reset_bus

    # Reset the bus for clean test
    reset_bus()
    wire = InMemoryWire()

    import types

    # Create RootModel wrapper for alert message
    class AlertRootModel(RootModel[AlertMessage]):
        """RootModel wrapper for testing parameter extraction"""

        root: AlertMessage

    test_module = types.SimpleNamespace()
    test_module.messages = types.SimpleNamespace()
    test_module.messages.json = types.SimpleNamespace()
    test_module.messages.json.TestMessage = AlertRootModel
    codec_factory = JsonCodecFactory(test_module)

    # Create parameterized channel directly
    channel = Channel(
        key="test_channel",
        address="alerts.{location}.{severity}",
        title="Test Channel",
        summary=None,
        description=None,
        servers=[],
        messages={
            "TestMessage": Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        },
        parameters={
            "location": AddressParameter(
                key="location",
                description="Location code",
                location="$message.payload#/location",
            ),
            "severity": AddressParameter(
                key="severity",
                description="Severity level",
                location="$message.payload#/severity",
            ),
        },
        tags=[],
        external_docs=None,
        bindings=ChannelBindings(
            amqp=AmqpChannelBinding(
                type="routingKey",
                exchange=AmqpExchange(
                    name="test_exchange",
                    type=AmqpExchangeType.TOPIC,
                ),
            )
        ),
    )

    # Create operation with parameterized channel
    operation = Operation(
        key="test_op",
        action="send",
        title=None,
        summary=None,
        description=None,
        channel=channel,
        messages=[
            Message(
                name="TestMessage",
                title="Test Message",
                summary=None,
                description=None,
                content_type="application/json",
                headers=None,
                tags=[],
                externalDocs=None,
                bindings=None,
                deprecated=None,
                correlation_id=None,
                traits=[],
                payload={"type": "object"},
                key="",
            )
        ],
        reply=None,
        traits=[],
        security=[],
        tags=[],
        external_docs=None,
        bindings=None,
    )

    publisher = Publisher(
        operation=operation,
        wire_factory=wire,
        codec_factory=codec_factory,
    )

    # Capture the channel name used for publishing by intercepting bus.publish
    captured_channel: str | None = None
    bus = get_bus()
    original_publish = bus.publish

    async def mock_publish(channel_name: str, message: Any) -> None:
        nonlocal captured_channel
        captured_channel = channel_name
        await original_publish(channel_name, message)

    bus.publish = mock_publish  # type: ignore

    await publisher.start()

    # Send message wrapped in RootModel
    wrapped_message = AlertRootModel.model_validate(
        {"location": "NYC", "severity": "high", "data": "test"}
    )
    await publisher(wrapped_message)

    # Should extract parameters from RootModel and build correct address
    assert captured_channel == "alerts.NYC.high"

    await publisher.stop()
