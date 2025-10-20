"""Unit tests for batch processing in subscriber and RPC server endpoints."""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, Mock

import pytest

from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document import Channel, Message, Operation
from asyncapi_python.kernel.endpoint import RpcServer, Subscriber
from asyncapi_python.kernel.exceptions import Reject
from asyncapi_python.kernel.typing import BatchConfig
from asyncapi_python.kernel.wire import AbstractWireFactory


class MockIncomingMessage:
    """Mock incoming message with ack/nack/reject tracking"""

    def __init__(
        self, payload: bytes, correlation_id: str = None, reply_to: str = None
    ):
        self._payload = payload
        self._acked = False
        self._nacked = False
        self._rejected = False
        self._correlation_id = correlation_id or "test-correlation"
        self._reply_to = reply_to or "test-reply-to"

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


class MockBatchConsumer:
    """Mock consumer that yields test messages for batch testing"""

    def __init__(self):
        self._started = False
        self._messages: list[MockIncomingMessage] = []
        self._message_index = 0

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def add_messages(self, messages: list[MockIncomingMessage]) -> None:
        """Add messages to be consumed"""
        self._messages.extend(messages)

    async def recv(self) -> AsyncGenerator[MockIncomingMessage, None]:
        """Yield messages from the list"""
        try:
            while self._started:
                if self._message_index < len(self._messages):
                    message = self._messages[self._message_index]
                    self._message_index += 1
                    yield message
                    # Small delay to allow batch processing
                    await asyncio.sleep(0.01)
                else:
                    # Keep the consumer alive even after messages are exhausted to allow timeout testing
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            # Handle cancellation gracefully
            return


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

    # Create a reply message and operation for RPC
    from asyncapi_python.kernel.document.operation import OperationReply

    reply_message = Message(
        name="TestReplyMessage",
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        traits=[],
        payload={"type": "object"},
        headers=None,
        bindings=None,
        key="test-reply-message",
        correlation_id=None,
        content_type=None,
        deprecated=None,
    )

    reply_operation = OperationReply(
        channel=mock_channel,
        messages=[reply_message],
        address=None,
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
        messages=[mock_message],
        reply=reply_operation,
    )


@pytest.fixture
def mock_codec():
    """Create a mock codec factory."""
    codec_factory = Mock(spec=CodecFactory)

    mock_message = Mock(spec=Message)
    mock_message.name = "TestMessage"

    mock_message_codec = Mock()
    mock_message_codec.decode.return_value = {"test": "data"}
    mock_message_codec.encode.return_value = b"encoded"

    codec_factory.create.return_value = mock_message_codec

    return codec_factory


@pytest.fixture
def mock_wire_with_batch_consumer():
    """Create a mock wire factory with batch consumer."""
    wire = Mock(spec=AbstractWireFactory)
    consumer = MockBatchConsumer()

    producer = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.send_batch = AsyncMock()

    wire.create_consumer = AsyncMock(return_value=consumer)
    wire.create_producer = AsyncMock(return_value=producer)

    return wire, consumer


# Subscriber Batch Processing Tests


@pytest.mark.asyncio
async def test_subscriber_batch_config_validation():
    """Test BatchConfig validation in subscriber"""
    # This test verifies BatchConfig TypedDict structure
    batch_config: BatchConfig = {"max_size": 10, "timeout": 5.0}

    assert batch_config["max_size"] == 10
    assert batch_config["timeout"] == 5.0


@pytest.mark.asyncio
async def test_subscriber_batch_by_size(
    mock_operation, mock_codec, mock_wire_with_batch_consumer
):
    """Test subscriber processes batch when max_size is reached"""
    wire, consumer = mock_wire_with_batch_consumer

    subscriber = Subscriber(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )

    processed_batches = []

    @subscriber(batch={"max_size": 3, "timeout": 10.0})
    async def batch_handler(messages: list[dict]):
        processed_batches.append(messages.copy())

    # Add 5 messages (should create 1 batch of 3 + 1 partial batch of 2)
    test_messages = [
        MockIncomingMessage(b'{"msg": "1"}'),
        MockIncomingMessage(b'{"msg": "2"}'),
        MockIncomingMessage(b'{"msg": "3"}'),
        MockIncomingMessage(b'{"msg": "4"}'),
        MockIncomingMessage(b'{"msg": "5"}'),
    ]
    consumer.add_messages(test_messages)

    await subscriber.start()
    await asyncio.sleep(0.2)  # Allow processing
    await subscriber.stop()

    # Should have processed one full batch of 3
    assert len(processed_batches) >= 1
    assert len(processed_batches[0]) == 3

    # All messages in the full batch should be acked
    for i in range(3):
        assert test_messages[i].is_acked
        assert not test_messages[i].is_nacked
        assert not test_messages[i].is_rejected


@pytest.mark.asyncio
async def test_subscriber_batch_by_timeout(
    mock_operation, mock_codec, mock_wire_with_batch_consumer
):
    """Test subscriber processes batch when timeout is reached"""
    wire, consumer = mock_wire_with_batch_consumer

    subscriber = Subscriber(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )

    processed_batches = []

    @subscriber(batch={"max_size": 10, "timeout": 0.1})  # 100ms timeout
    async def batch_handler(messages: list[dict]):
        processed_batches.append(messages.copy())

    # Add 2 messages (less than max_size, should trigger timeout)
    test_messages = [
        MockIncomingMessage(b'{"msg": "1"}'),
        MockIncomingMessage(b'{"msg": "2"}'),
    ]
    consumer.add_messages(test_messages)

    await subscriber.start()
    await asyncio.sleep(0.3)  # Wait for timeout + processing
    await subscriber.stop()

    # Should have processed one batch due to timeout
    assert len(processed_batches) == 1
    assert len(processed_batches[0]) == 2

    # All messages should be acked
    for message in test_messages:
        assert message.is_acked


@pytest.mark.asyncio
async def test_subscriber_batch_reject_exception(
    mock_operation, mock_codec, mock_wire_with_batch_consumer
):
    """Test subscriber batch handling of Reject exceptions"""
    wire, consumer = mock_wire_with_batch_consumer
    exception_callback = Mock()

    subscriber = Subscriber(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )

    call_count = 0

    @subscriber(batch={"max_size": 2, "timeout": 1.0})
    async def batch_handler(messages: list[dict]):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First batch - reject
            raise Reject("Invalid batch")
        else:
            # Second batch - process normally
            pass

    # Add 4 messages (2 batches of 2)
    test_messages = [
        MockIncomingMessage(b'{"msg": "1"}'),
        MockIncomingMessage(b'{"msg": "2"}'),
        MockIncomingMessage(b'{"msg": "3"}'),
        MockIncomingMessage(b'{"msg": "4"}'),
    ]
    consumer.add_messages(test_messages)

    await subscriber.start(exception_callback=exception_callback)
    await asyncio.sleep(0.3)
    await subscriber.stop()

    # First batch should be rejected
    assert test_messages[0].is_rejected
    assert test_messages[1].is_rejected

    # Second batch should be acked
    assert test_messages[2].is_acked
    assert test_messages[3].is_acked

    # Exception callback should not be called (Reject doesn't propagate)
    exception_callback.assert_not_called()


@pytest.mark.asyncio
async def test_subscriber_batch_regular_exception(
    mock_operation, mock_codec, mock_wire_with_batch_consumer
):
    """Test subscriber batch handling of regular exceptions"""
    wire, consumer = mock_wire_with_batch_consumer
    exception_callback = Mock()

    subscriber = Subscriber(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )

    @subscriber(batch={"max_size": 2, "timeout": 1.0})
    async def batch_handler(messages: list[dict]):
        raise ValueError("Processing error")

    # Add 2 messages
    test_messages = [
        MockIncomingMessage(b'{"msg": "1"}'),
        MockIncomingMessage(b'{"msg": "2"}'),
    ]
    consumer.add_messages(test_messages)

    await subscriber.start(exception_callback=exception_callback)
    await asyncio.sleep(0.3)
    await subscriber.stop()

    # All messages should be nacked
    for message in test_messages:
        assert message.is_nacked

    # Exception callback should be called
    exception_callback.assert_called_once()
    called_exception = exception_callback.call_args[0][0]
    assert isinstance(called_exception, ValueError)


# RPC Server Batch Processing Tests


@pytest.mark.asyncio
async def test_rpc_server_batch_processing(
    mock_operation, mock_codec, mock_wire_with_batch_consumer
):
    """Test RPC server batch processing with input/output validation"""
    wire, consumer = mock_wire_with_batch_consumer

    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )
    rpc_server._reply_codecs = [Mock()]  # Add reply codecs

    @rpc_server(batch={"max_size": 3, "timeout": 1.0})
    async def batch_handler(requests: list[dict]) -> list[dict]:
        # Return same number of responses as requests
        return [{"response": f"processed_{i}"} for i in range(len(requests))]

    # Add 3 RPC requests
    test_messages = [
        MockIncomingMessage(b'{"request": "1"}', "corr-1", "reply-queue"),
        MockIncomingMessage(b'{"request": "2"}', "corr-2", "reply-queue"),
        MockIncomingMessage(b'{"request": "3"}', "corr-3", "reply-queue"),
    ]
    consumer.add_messages(test_messages)

    await rpc_server.start()
    await asyncio.sleep(0.3)

    # Check reply producer calls before stopping
    reply_producer = rpc_server._reply_producer
    await rpc_server.stop()

    # All requests should be acked
    for message in test_messages:
        assert message.is_acked

    # Reply producer should have been called for each request
    # Each reply uses send_batch with address_override
    assert reply_producer.send_batch.call_count == 3


@pytest.mark.asyncio
async def test_rpc_server_batch_input_output_length_mismatch(
    mock_operation, mock_codec, mock_wire_with_batch_consumer
):
    """Test RPC server batch validation: len(inputs) must equal len(outputs)"""
    wire, consumer = mock_wire_with_batch_consumer
    exception_callback = Mock()

    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )
    rpc_server._reply_codecs = [Mock()]

    @rpc_server(batch={"max_size": 2, "timeout": 1.0})
    async def batch_handler(requests: list[dict]) -> list[dict]:
        # Return wrong number of responses (should fail)
        return [{"response": "only_one"}]  # 2 inputs, 1 output

    test_messages = [
        MockIncomingMessage(b'{"request": "1"}', "corr-1", "reply-queue"),
        MockIncomingMessage(b'{"request": "2"}', "corr-2", "reply-queue"),
    ]
    consumer.add_messages(test_messages)

    await rpc_server.start(exception_callback=exception_callback)
    await asyncio.sleep(0.3)
    await rpc_server.stop()

    # All messages should be nacked due to validation error
    for message in test_messages:
        assert message.is_nacked

    # Exception callback should be called
    exception_callback.assert_called_once()
    called_exception = exception_callback.call_args[0][0]
    assert isinstance(called_exception, RuntimeError)
    assert "len(inputs) must equal len(outputs)" in str(called_exception)


@pytest.mark.asyncio
async def test_rpc_server_batch_reject_exception(
    mock_operation, mock_codec, mock_wire_with_batch_consumer
):
    """Test RPC server batch handling of Reject exceptions"""
    wire, consumer = mock_wire_with_batch_consumer
    exception_callback = Mock()

    rpc_server = RpcServer(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )
    rpc_server._reply_codecs = [Mock()]

    call_count = 0

    @rpc_server(batch={"max_size": 2, "timeout": 1.0})
    async def batch_handler(requests: list[dict]) -> list[dict]:
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            raise Reject("Invalid batch request")
        else:
            return [{"status": "ok"} for _ in requests]

    # Add 4 messages (2 batches of 2)
    test_messages = [
        MockIncomingMessage(b'{"request": "1"}', "corr-1", "reply-queue"),
        MockIncomingMessage(b'{"request": "2"}', "corr-2", "reply-queue"),
        MockIncomingMessage(b'{"request": "3"}', "corr-3", "reply-queue"),
        MockIncomingMessage(b'{"request": "4"}', "corr-4", "reply-queue"),
    ]
    consumer.add_messages(test_messages)

    await rpc_server.start(exception_callback=exception_callback)
    await asyncio.sleep(0.3)
    await rpc_server.stop()

    # First batch should be rejected
    assert test_messages[0].is_rejected
    assert test_messages[1].is_rejected

    # Second batch should be acked
    assert test_messages[2].is_acked
    assert test_messages[3].is_acked

    # Exception callback should not be called (Reject doesn't propagate)
    exception_callback.assert_not_called()


@pytest.mark.asyncio
async def test_batch_config_total_typeddict():
    """Test that BatchConfig is a total TypedDict (all fields required)"""
    # This should work (all required fields provided)
    valid_config: BatchConfig = {"max_size": 10, "timeout": 5.0}

    assert valid_config["max_size"] == 10
    assert valid_config["timeout"] == 5.0

    # Note: TypedDict validation happens at type check time with mypy,
    # not at runtime, so we can't test runtime validation here.
    # This test documents the expected structure.


@pytest.mark.asyncio
async def test_mixed_batch_and_regular_handlers_not_allowed(
    mock_operation, mock_codec, mock_wire_with_batch_consumer
):
    """Test that endpoints cannot have both batch and regular handlers"""
    wire, consumer = mock_wire_with_batch_consumer

    subscriber = Subscriber(
        operation=mock_operation, wire_factory=wire, codec_factory=mock_codec
    )

    # Register regular handler first
    @subscriber
    async def regular_handler(msg: dict):
        pass

    # Try to register batch handler - should fail
    with pytest.raises(RuntimeError) as exc_info:

        @subscriber(batch={"max_size": 5, "timeout": 1.0})
        async def batch_handler(messages: list[dict]):
            pass

    error_msg = str(exc_info.value)
    assert "already has a handler registered" in error_msg
    assert "regular_handler" in error_msg
    assert "batch_handler" in error_msg
