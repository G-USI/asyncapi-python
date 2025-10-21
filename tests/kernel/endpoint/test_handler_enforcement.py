"""Unit tests for handler enforcement and location tracking in receiving endpoints."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document import Channel, Operation
from asyncapi_python.kernel.endpoint import RpcServer, Subscriber
from asyncapi_python.kernel.wire import AbstractWireFactory


@pytest.fixture
def mock_channel():
    """Create a mock channel for testing."""
    return Channel(
        address="/test/channel",
        title="Test Channel",
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=None,
        key="test_channel",
    )


@pytest.fixture
def mock_operation(mock_channel):
    """Create a mock operation for testing."""
    return Operation(
        key="test_operation",
        action="receive",
        channel=mock_channel,
        title="Test Operation",
        summary=None,
        description=None,
        security=[],
        tags=[],
        external_docs=None,
        bindings=None,
        traits=[],
        messages=[],
        reply=None,
    )


@pytest.fixture
def mock_wire():
    """Create a mock wire factory."""
    wire = Mock(spec=AbstractWireFactory)

    # Mock consumer
    consumer = AsyncMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()
    consumer.recv = AsyncMock()

    # Mock producer for RPC
    producer = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.send_batch = AsyncMock()

    wire.create_consumer = AsyncMock(return_value=consumer)
    wire.create_producer = AsyncMock(return_value=producer)

    return wire


@pytest.fixture
def mock_codec():
    """Create a mock codec factory."""
    codec = Mock(spec=CodecFactory)
    codec.get_encoder = Mock(return_value=lambda x: b"encoded")
    codec.get_decoder = Mock(return_value=lambda x: {"decoded": True})
    codec.get_reply_encoder = Mock(return_value=lambda x: b"encoded_reply")
    codec.get_reply_decoder = Mock(return_value=lambda x: {"decoded_reply": True})
    return codec


# Subscriber Handler Enforcement Tests


def test_subscriber_requires_handler_at_start(mock_operation, mock_wire, mock_codec):
    """Test that subscriber requires a handler before starting."""
    subscriber = Subscriber(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Should raise error when starting without a handler
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(subscriber.start())

    assert "test_operation" in str(exc_info.value)
    assert "requires exactly one handler" in str(exc_info.value)


def test_subscriber_accepts_single_handler(mock_operation, mock_wire, mock_codec):
    """Test that subscriber accepts exactly one handler."""
    subscriber = Subscriber(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Register a handler
    @subscriber
    async def handler(msg):
        pass

    # Should start successfully with one handler
    async def test():
        await subscriber.start()
        await subscriber.stop()

    asyncio.run(test())

    # Verify handler was registered
    assert subscriber._handler == handler
    assert subscriber._handler_location is not None


def test_subscriber_rejects_multiple_handlers(mock_operation, mock_wire, mock_codec):
    """Test that subscriber rejects multiple handlers."""
    subscriber = Subscriber(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Register first handler
    @subscriber
    async def handler1(msg):
        pass

    # Try to register second handler - should fail
    with pytest.raises(RuntimeError) as exc_info:

        @subscriber
        async def handler2(msg):
            pass

    error_msg = str(exc_info.value)
    assert "test_operation" in error_msg
    assert "already has a handler registered" in error_msg
    assert "handler1" in error_msg
    assert "handler2" in error_msg


def test_subscriber_tracks_handler_location(mock_operation, mock_wire, mock_codec):
    """Test that subscriber tracks where handlers are defined."""
    subscriber = Subscriber(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Register first handler
    @subscriber
    async def my_handler(msg):
        pass

    # Verify location was tracked
    assert subscriber._handler_location is not None
    assert "test_handler_enforcement.py" in subscriber._handler_location
    assert str(my_handler.__code__.co_firstlineno) in subscriber._handler_location

    # Try to register another handler
    with pytest.raises(RuntimeError) as exc_info:

        @subscriber
        async def another_handler(msg):
            pass

    error_msg = str(exc_info.value)
    # Should show both handler locations
    assert "Existing handler: my_handler at" in error_msg
    assert "New handler: another_handler at" in error_msg
    assert "test_handler_enforcement.py" in error_msg


def test_subscriber_handles_lambda_handlers(mock_operation, mock_wire, mock_codec):
    """Test that subscriber handles lambda functions correctly."""
    subscriber = Subscriber(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Register lambda handler
    handler = lambda msg: None
    subscriber(handler)

    # Verify lambda was registered with location
    assert subscriber._handler == handler
    assert subscriber._handler_location is not None
    assert "test_handler_enforcement.py" in subscriber._handler_location

    # Try to register another lambda
    with pytest.raises(RuntimeError) as exc_info:
        subscriber(lambda msg: None)

    error_msg = str(exc_info.value)
    assert "<lambda>" in error_msg
    assert "test_handler_enforcement.py" in error_msg


# RPC Server Handler Enforcement Tests


def test_rpc_server_requires_handler_at_start(mock_operation, mock_wire, mock_codec):
    """Test that RPC server requires a handler before starting."""
    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Mock reply codecs
    rpc_server._reply_codecs = {"TestReply": Mock()}

    # Should raise error when starting without a handler
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(rpc_server.start())

    assert "test_operation" in str(exc_info.value)
    assert "requires exactly one handler" in str(exc_info.value)


def test_rpc_server_accepts_single_handler(mock_operation, mock_wire, mock_codec):
    """Test that RPC server accepts exactly one handler."""
    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Mock reply codecs
    rpc_server._reply_codecs = {"TestReply": Mock()}

    # Register a handler
    @rpc_server
    async def handler(msg):
        return {"response": "ok"}

    # Should start successfully with one handler
    async def test():
        await rpc_server.start()
        await rpc_server.stop()

    asyncio.run(test())

    # Verify handler was registered
    assert rpc_server._handler == handler
    assert rpc_server._handler_location is not None


def test_rpc_server_rejects_multiple_handlers(mock_operation, mock_wire, mock_codec):
    """Test that RPC server rejects multiple handlers."""
    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Register first handler
    @rpc_server
    async def process_request(msg):
        return {"status": "ok"}

    # Try to register second handler - should fail
    with pytest.raises(RuntimeError) as exc_info:

        @rpc_server
        async def another_processor(msg):
            return {"status": "ok"}

    error_msg = str(exc_info.value)
    assert "test_operation" in error_msg
    assert "already has a handler registered" in error_msg
    assert "process_request" in error_msg
    assert "another_processor" in error_msg


def test_rpc_server_tracks_handler_location(mock_operation, mock_wire, mock_codec):
    """Test that RPC server tracks where handlers are defined."""
    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Register first handler
    @rpc_server
    async def rpc_handler(msg):
        return {"result": "success"}

    # Verify location was tracked
    assert rpc_server._handler_location is not None
    assert "test_handler_enforcement.py" in rpc_server._handler_location
    assert str(rpc_handler.__code__.co_firstlineno) in rpc_server._handler_location

    # Try to register another handler
    with pytest.raises(RuntimeError) as exc_info:

        @rpc_server
        async def duplicate_handler(msg):
            return {"result": "success"}

    error_msg = str(exc_info.value)
    # Should show both handler locations
    assert "Existing handler: rpc_handler at" in error_msg
    assert "New handler: duplicate_handler at" in error_msg
    assert "test_handler_enforcement.py" in error_msg


def test_rpc_server_with_parameters(mock_operation, mock_wire, mock_codec):
    """Test that RPC server works with decorator parameters."""
    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    # Register handler with parameters
    @rpc_server(queue="high-priority")
    async def priority_handler(msg):
        return {"priority": "high"}

    # Verify handler was registered
    assert rpc_server._handler == priority_handler
    assert rpc_server._handler_location is not None

    # Try to register another handler with parameters
    with pytest.raises(RuntimeError) as exc_info:

        @rpc_server(queue="low-priority")
        async def another_handler(msg):
            return {"priority": "low"}

    error_msg = str(exc_info.value)
    assert "priority_handler" in error_msg
    assert "another_handler" in error_msg


# Handler Location Formatting Tests


def test_location_format_regular_function(mock_operation, mock_wire, mock_codec):
    """Test location format for regular functions."""
    subscriber = Subscriber(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    @subscriber
    async def test_function(msg):
        pass

    # Location should be in format: filename:linenumber
    assert ":" in subscriber._handler_location
    parts = subscriber._handler_location.split(":")
    assert len(parts) == 2
    assert parts[0].endswith(".py")
    assert parts[1].isdigit()


def test_location_format_lambda(mock_operation, mock_wire, mock_codec):
    """Test location format for lambda functions."""
    subscriber = Subscriber(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    test_lambda = lambda msg: None
    subscriber(test_lambda)

    # Lambda location should still have proper format
    assert ":" in subscriber._handler_location
    parts = subscriber._handler_location.split(":")
    assert len(parts) == 2
    assert parts[0].endswith(".py")
    assert parts[1].isdigit()


def test_error_message_structure(mock_operation, mock_wire, mock_codec):
    """Test the structure of error messages with location info."""
    subscriber = Subscriber(
        operation=mock_operation, wire_factory=mock_wire, codec_factory=mock_codec
    )

    @subscriber
    async def first(msg):
        pass

    with pytest.raises(RuntimeError) as exc_info:

        @subscriber
        async def second(msg):
            pass

    error_lines = str(exc_info.value).split("\n")

    # Error should be multi-line with clear structure
    assert len(error_lines) >= 4
    assert "already has a handler registered" in error_lines[0]
    assert "Existing handler:" in error_lines[1]
    assert "New handler:" in error_lines[2]
    assert "exactly one handler" in error_lines[3]
