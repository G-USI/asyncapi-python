"""Tests for AMQP wire implementation"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.contrib.wire.amqp import AmqpWireFactory, AmqpWireMessage


@pytest.fixture
def mock_connection():
    """Mock AMQP connection"""
    connection = AsyncMock()
    connection.is_closed = False
    return connection


@pytest.fixture
def mock_channel():
    """Mock AMQP channel"""
    channel = AsyncMock()
    queue = AsyncMock()
    queue.iterator.return_value.__aenter__.return_value = []
    channel.declare_queue.return_value = queue
    return channel


@pytest.fixture
def wire_factory():
    """AMQP wire factory fixture"""
    return AmqpWireFactory(
        connection_url="amqp://localhost",
        app_id="test-app"
    )


@pytest.mark.asyncio
@patch('asyncapi_python.contrib.wire.amqp.connect_robust')
async def test_create_consumer_regular_channel(mock_connect, wire_factory, mock_connection, mock_channel):
    """Test creating consumer for regular channel"""
    mock_connect.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    
    channel = Channel(
        address="user.events",
        title=None,
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=None
    )
    
    consumer = await wire_factory.create_consumer(
        channel=channel,
        parameters={},
        op_bindings=None,
        is_reply=False
    )
    
    await consumer.start()
    
    # Should declare queue with channel name
    mock_channel.declare_queue.assert_called_once_with(
        "user.events", durable=True
    )


@pytest.mark.asyncio  
@patch('asyncapi_python.contrib.wire.amqp.connect_robust')
async def test_create_consumer_reply_channel_null_address(mock_connect, wire_factory, mock_connection, mock_channel):
    """Test creating consumer for reply channel with null address (global reply queue)"""
    mock_connect.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    
    channel = Channel(
        address=None,  # Null address for global reply queue
        title=None,
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=None
    )
    
    consumer = await wire_factory.create_consumer(
        channel=channel,
        parameters={},
        op_bindings=None,
        is_reply=True  # Reply channel
    )
    
    await consumer.start()
    
    # Should declare global reply queue
    mock_channel.declare_queue.assert_called_once_with(
        "reply-queue-test-app", durable=True, exclusive=False
    )


@pytest.mark.asyncio
@patch('asyncapi_python.contrib.wire.amqp.connect_robust')
async def test_create_consumer_reply_channel_with_address(mock_connect, wire_factory, mock_connection, mock_channel):
    """Test creating consumer for reply channel with specific address"""
    mock_connect.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    
    channel = Channel(
        address="custom-reply-queue",
        title=None,
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=None
    )
    
    consumer = await wire_factory.create_consumer(
        channel=channel,
        parameters={},
        op_bindings=None,
        is_reply=True
    )
    
    await consumer.start()
    
    # Should use specific reply queue name
    mock_channel.declare_queue.assert_called_once_with(
        "custom-reply-queue", durable=True, exclusive=False
    )


@pytest.mark.asyncio
@patch('asyncapi_python.contrib.wire.amqp.connect_robust')
async def test_create_producer(mock_connect, wire_factory, mock_connection, mock_channel):
    """Test creating producer"""
    mock_connect.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    
    channel = Channel(
        address="user.commands",
        title=None,
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=None
    )
    
    producer = await wire_factory.create_producer(
        channel=channel,
        parameters={},
        op_bindings=None,
        is_reply=False
    )
    
    await producer.start()
    
    # Should declare queue for producer
    mock_channel.declare_queue.assert_called_once_with(
        "user.commands", durable=True
    )


def test_amqp_wire_message():
    """Test AmqpWireMessage properties"""
    message = AmqpWireMessage(
        _payload=b"test payload",
        _headers={"content-type": "application/json"},
        _correlation_id="123",
        _reply_to="reply-queue"
    )
    
    assert message.payload == b"test payload"
    assert message.headers == {"content-type": "application/json"}
    assert message.correlation_id == "123"
    assert message.reply_to == "reply-queue"