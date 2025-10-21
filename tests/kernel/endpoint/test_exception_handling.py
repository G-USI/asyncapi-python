"""Unit tests for exception handling in subscriber and RPC server endpoints."""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, Mock

import pytest

from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document import Channel, Message, Operation
from asyncapi_python.kernel.endpoint import RpcServer, Subscriber
from asyncapi_python.kernel.exceptions import Reject
from asyncapi_python.kernel.wire import AbstractWireFactory


class MockIncomingMessage:
    """Mock incoming message with ack/nack/reject tracking"""

    def __init__(self, payload: bytes):
        self._payload = payload
        self._acked = False
        self._nacked = False
        self._rejected = False
        self._correlation_id = "test-correlation"
        self._reply_to = "test-reply-to"

    @property
    def payload(self) -> bytes:
        return self._payload

    @property
    def headers(self) -> dict:
        return {}

    @property
    def correlation_id(self) -> str | None:
        return self._correlation_id

    @property
    def reply_to(self) -> str | None:
        return self._reply_to

    async def ack(self) -> None:
        self._acked = True

    async def nack(self) -> None:
        self._nacked = True

    async def reject(self) -> None:
        self._rejected = True

    @property
    def is_acked(self) -> bool:
        return self._acked

    @property
    def is_nacked(self) -> bool:
        return self._nacked

    @property
    def is_rejected(self) -> bool:
        return self._rejected


class MockConsumer:
    """Mock consumer that yields test messages"""

    def __init__(self):
        self._started = False
        self._messages: asyncio.Queue[MockIncomingMessage] = asyncio.Queue()

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def add_message(self, message: MockIncomingMessage) -> None:
        """Add a message to be consumed"""
        try:
            self._messages.put_nowait(message)
        except asyncio.QueueFull:
            pass

    async def recv(self) -> AsyncGenerator[MockIncomingMessage, None]:
        """Yield messages from the queue"""
        while self._started:
            try:
                message = await asyncio.wait_for(self._messages.get(), timeout=0.1)
                yield message
                self._messages.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception:
                break


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
    # Create a mock message for the operation
    mock_message = Message(
        name="TestMessage",
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        traits=[],
        payload={"type": "object"},
        headers=None,
        bindings=None,
        key="test-message",
        correlation_id=None,
        content_type=None,
        deprecated=None,
    )

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
        messages=[mock_message],  # Add the mock message
        reply=None,
    )


@pytest.fixture
def mock_codec():
    """Create a mock codec factory."""
    codec_factory = Mock(spec=CodecFactory)

    # Mock message for the operation
    mock_message = Mock(spec=Message)
    mock_message.name = "TestMessage"

    # Mock codec instance
    mock_message_codec = Mock()
    mock_message_codec.decode.return_value = {"test": "data"}
    mock_message_codec.encode.return_value = b"encoded"

    # Factory returns the codec
    codec_factory.create.return_value = mock_message_codec

    return codec_factory


@pytest.fixture
def mock_wire_with_consumer():
    """Create a mock wire factory with controllable consumer."""
    wire = Mock(spec=AbstractWireFactory)
    consumer = MockConsumer()

    # Mock producer for RPC
    producer = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.send_batch = AsyncMock()

    wire.create_consumer = AsyncMock(return_value=consumer)
    wire.create_producer = AsyncMock(return_value=producer)

    return wire, consumer


@pytest.mark.asyncio
async def test_subscriber_nacks_and_stops_on_regular_exception(
    mock_operation, mock_codec, mock_wire_with_consumer
):
    """Test that subscriber nacks message and stops processing on regular exceptions like 1//0"""
    wire, consumer = mock_wire_with_consumer
    exception_callback = Mock()

    subscriber = Subscriber(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )

    # Register handler that throws division by zero
    @subscriber
    async def handler(msg):
        return 1 // 0  # ZeroDivisionError

    # Add a test message
    test_message = MockIncomingMessage(b'{"test": "data"}')
    consumer.add_message(test_message)

    # Start subscriber with exception callback
    await subscriber.start(exception_callback=exception_callback)

    # Give time for message processing
    await asyncio.sleep(0.3)

    # Verify message was nacked (not acked or rejected)
    assert test_message.is_nacked
    assert not test_message.is_acked
    assert not test_message.is_rejected

    # Verify exception callback was called
    exception_callback.assert_called_once()
    called_exception = exception_callback.call_args[0][0]
    assert isinstance(called_exception, ZeroDivisionError)

    await subscriber.stop()


@pytest.mark.asyncio
async def test_subscriber_rejects_and_continues_on_reject_exception(
    mock_operation, mock_codec, mock_wire_with_consumer
):
    """Test that subscriber rejects message and continues processing on Reject exceptions"""
    wire, consumer = mock_wire_with_consumer
    exception_callback = Mock()

    subscriber = Subscriber(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )

    processed_messages = []
    call_count = 0

    # Register handler that rejects first message, processes second
    @subscriber
    async def handler(msg):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First message - reject it
            raise Reject("Invalid message format")
        else:
            # Second message - process normally
            processed_messages.append(msg)

    # Add two test messages
    first_message = MockIncomingMessage(b'{"invalid": "message"}')
    second_message = MockIncomingMessage(b'{"valid": "message"}')
    consumer.add_message(first_message)
    consumer.add_message(second_message)

    # Start subscriber
    await subscriber.start(exception_callback=exception_callback)

    # Give time for message processing
    await asyncio.sleep(0.3)

    # Verify first message was rejected (not acked or nacked)
    assert first_message.is_rejected
    assert not first_message.is_acked
    assert not first_message.is_nacked

    # Verify second message was processed and acked
    assert second_message.is_acked
    assert not second_message.is_nacked
    assert not second_message.is_rejected

    # Verify exception callback was NOT called (Reject doesn't propagate)
    exception_callback.assert_not_called()

    # Verify second message was processed
    assert len(processed_messages) == 1

    await subscriber.stop()


@pytest.mark.asyncio
async def test_subscriber_continues_after_reject_but_stops_on_regular_exception(
    mock_operation, mock_codec, mock_wire_with_consumer
):
    """Test mixed scenario: subscriber continues after Reject but stops on regular exception"""
    wire, consumer = mock_wire_with_consumer
    exception_callback = Mock()

    subscriber = Subscriber(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )

    processed_count = 0

    @subscriber
    async def handler(msg):
        nonlocal processed_count
        processed_count += 1

        if processed_count == 1:
            # First message - reject
            raise Reject("Bad format")
        elif processed_count == 2:
            # Second message - process successfully
            return
        else:
            # Third message - throw regular exception
            raise ValueError("Processing error")

    # Add three messages
    msg1 = MockIncomingMessage(b'{"msg": "1"}')
    msg2 = MockIncomingMessage(b'{"msg": "2"}')
    msg3 = MockIncomingMessage(b'{"msg": "3"}')
    consumer.add_message(msg1)
    consumer.add_message(msg2)
    consumer.add_message(msg3)

    await subscriber.start(exception_callback=exception_callback)
    await asyncio.sleep(0.3)

    # First message: rejected, continue processing
    assert msg1.is_rejected

    # Second message: acked, continue processing
    assert msg2.is_acked

    # Third message: nacked, stop processing
    assert msg3.is_nacked

    # Exception callback called only for ValueError
    exception_callback.assert_called_once()
    called_exception = exception_callback.call_args[0][0]
    assert isinstance(called_exception, ValueError)

    await subscriber.stop()


@pytest.mark.asyncio
async def test_rpc_server_nacks_and_stops_on_regular_exception(
    mock_operation, mock_codec, mock_wire_with_consumer
):
    """Test that RPC server nacks message and stops processing on regular exceptions"""
    wire, consumer = mock_wire_with_consumer
    exception_callback = Mock()

    # Mock reply codecs for RPC server
    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )
    rpc_server._reply_codecs = [Mock()]  # Add reply codecs

    # Register handler that throws exception
    @rpc_server
    async def handler(msg):
        raise RuntimeError("Server error")

    # Add test message with RPC metadata
    test_message = MockIncomingMessage(b'{"test": "request"}')
    # Override RPC metadata for RPC server
    test_message._correlation_id = "test-correlation-id"
    test_message._reply_to = "test-reply-queue"
    consumer.add_message(test_message)

    await rpc_server.start(exception_callback=exception_callback)
    await asyncio.sleep(0.3)

    # Verify message was nacked
    assert test_message.is_nacked
    assert not test_message.is_acked
    assert not test_message.is_rejected

    # Verify exception callback was called
    exception_callback.assert_called_once()
    called_exception = exception_callback.call_args[0][0]
    assert isinstance(called_exception, RuntimeError)

    await rpc_server.stop()


@pytest.mark.asyncio
async def test_rpc_server_rejects_and_continues_on_reject_exception(
    mock_operation, mock_codec, mock_wire_with_consumer
):
    """Test that RPC server rejects message and continues on Reject exceptions"""
    wire, consumer = mock_wire_with_consumer
    exception_callback = Mock()

    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )
    rpc_server._reply_codecs = [Mock()]

    request_count = 0

    @rpc_server
    async def handler(msg):
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            raise Reject("Invalid request format")
        else:
            return {"status": "success"}

    # Add two messages with RPC metadata
    first_request = MockIncomingMessage(b'{"invalid": "request"}')
    first_request._correlation_id = "first-correlation"
    first_request._reply_to = "test-reply-queue"

    second_request = MockIncomingMessage(b'{"valid": "request"}')
    second_request._correlation_id = "second-correlation"
    second_request._reply_to = "test-reply-queue"

    consumer.add_message(first_request)
    consumer.add_message(second_request)

    await rpc_server.start(exception_callback=exception_callback)
    await asyncio.sleep(0.3)

    # First request rejected, continue processing
    assert first_request.is_rejected
    assert not first_request.is_acked

    # Second request processed successfully
    assert second_request.is_acked
    assert not second_request.is_nacked

    # No exception propagated for Reject
    exception_callback.assert_not_called()

    await rpc_server.stop()
