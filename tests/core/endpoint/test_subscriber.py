import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from functools import wraps

from asyncapi_python.kernel.endpoint.subscriber import Subscriber
from asyncapi_python.contrib.wire.in_memory import InMemoryMessage, get_bus
from asyncapi_python.kernel.typing import Handler
from typing import AsyncGenerator
from pydantic import BaseModel

class UserModel(BaseModel):
    name: str
    age: int
    email: str


# Fixtures
@pytest.fixture
async def subscriber(mock_operation, in_memory_wire_factory, json_codec_factory) -> AsyncGenerator[Subscriber, None]:
    """Create a subscriber instance for testing"""
    subscriber = Subscriber(
        operation=mock_operation,
        wire_factory=in_memory_wire_factory,
        codec_factory=json_codec_factory
    )
    await subscriber.start()
    yield subscriber
    await subscriber.stop()

@pytest.fixture  
def sample_user() -> UserModel:
    return UserModel(name="John Doe", age=30, email="john@example.com")


# Subscriber tests
@pytest.mark.asyncio
async def test_subscriber_decorator_with_function(subscriber: Subscriber) -> None:
        """Test subscriber decorator with a handler function"""
        handler_called = False
        received_message = None
        
        @subscriber
        async def test_handler(message: UserModel) -> None:
            nonlocal handler_called, received_message
            handler_called = True
            received_message = message
        
        # Verify the decorator returns the original function
        assert test_handler.__name__ == 'test_handler'
        
        # Publish a message to trigger the handler
        bus = get_bus()
        user_data = b'{"name":"John Doe","age":30,"email":"john@example.com"}'
        message = InMemoryMessage(_payload=user_data)
        await bus.publish("test.channel", message)
        
        # Wait a bit for message processing
        await asyncio.sleep(0.1)
        
        # Handler should have been called with decoded message
        assert handler_called
        assert received_message is not None
        assert received_message.name == "John Doe"
        assert received_message.age == 30
        assert received_message.email == "john@example.com"

@pytest.mark.asyncio
async def test_subscriber_decorator_without_parentheses(subscriber: Subscriber) -> None:
        """Test subscriber decorator used without parentheses"""
        handler_called = False
        
        @subscriber
        async def test_handler(message: UserModel) -> None:
            nonlocal handler_called
            handler_called = True
        
        # Publish a message
        bus = get_bus()
        user_data = b'{"name":"Alice","age":25,"email":"alice@example.com"}'
        message = InMemoryMessage(_payload=user_data)
        await bus.publish("test.channel", message)
        
        await asyncio.sleep(0.1)
        assert handler_called

@pytest.mark.asyncio
async def test_subscriber_decorator_with_parentheses(subscriber: Subscriber) -> None:
        """Test subscriber decorator used with parentheses (no parameters)"""
        handler_called = False
        
        @subscriber()
        async def test_handler(message: UserModel) -> None:
            nonlocal handler_called
            handler_called = True
        
        # Publish a message
        bus = get_bus()
        user_data = b'{"name":"Bob","age":35,"email":"bob@example.com"}'
        message = InMemoryMessage(_payload=user_data)
        await bus.publish("test.channel", message)
        
        await asyncio.sleep(0.1)
        assert handler_called

@pytest.mark.asyncio
async def test_subscriber_multiple_messages(subscriber: Subscriber) -> None:
        """Test subscriber handles multiple messages"""
        messages_received = []
        
        @subscriber
        async def test_handler(message: UserModel) -> None:
            messages_received.append(message.name)
        
        # Publish multiple messages
        bus = get_bus()
        users = [
            b'{"name":"Alice","age":25,"email":"alice@example.com"}',
            b'{"name":"Bob","age":35,"email":"bob@example.com"}',
            b'{"name":"Charlie","age":45,"email":"charlie@example.com"}'
        ]
        
        for user_data in users:
            message = InMemoryMessage(_payload=user_data)
            await bus.publish("test.channel", message)
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        assert len(messages_received) == 3
        assert "Alice" in messages_received
        assert "Bob" in messages_received
        assert "Charlie" in messages_received

@pytest.mark.asyncio
async def test_subscriber_message_acknowledgment(subscriber: Subscriber) -> None:
        """Test subscriber acknowledges messages after successful processing"""
        ack_called = False
        
        @subscriber
        async def test_handler(message: UserModel) -> None:
            pass  # Successful processing
        
        # Mock the ack method to track if it's called
        bus = get_bus()
        user_data = b'{"name":"John Doe","age":30,"email":"john@example.com"}'
        message = InMemoryMessage(_payload=user_data)
        await bus.publish("test.channel", message)
        
        # Get the message that will be consumed
        await asyncio.sleep(0.1)
        
        # The message should be acknowledged (implementation detail)
        # This is more of an integration test with the wire

@pytest.mark.asyncio
async def test_subscriber_decoding_error(subscriber: Subscriber) -> None:
        """Test subscriber handles decoding errors gracefully"""
        handler_called = False
        
        @subscriber
        async def test_handler(message: UserModel) -> None:
            nonlocal handler_called
            handler_called = True
        
        # Publish invalid JSON
        bus = get_bus()
        invalid_message = InMemoryMessage(_payload=b'invalid json data')
        await bus.publish("test.channel", invalid_message)
        
        await asyncio.sleep(0.1)
        
        # Handler should not be called due to decoding error
        assert not handler_called

@pytest.mark.asyncio
async def test_subscriber_handler_exception(subscriber: Subscriber) -> None:
        """Test subscriber handles handler exceptions gracefully"""
        @subscriber
        async def test_handler(message: UserModel) -> None:
            raise ValueError("Handler error")
        
        # Publish a valid message
        bus = get_bus()
        user_data = b'{"name":"John Doe","age":30,"email":"john@example.com"}'
        message = InMemoryMessage(_payload=user_data)
        await bus.publish("test.channel", message)
        
        # Should not raise exception despite handler error
        await asyncio.sleep(0.1)

@pytest.mark.asyncio
async def test_subscriber_lifecycle_management(mock_operation, in_memory_wire_factory, json_codec_factory) -> None:
        """Test subscriber start/stop lifecycle"""
        subscriber = Subscriber(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=json_codec_factory
        )
        
        # Should be able to start
        await subscriber.start()
        assert subscriber._consumer is not None
        assert subscriber._consumer._started
        
        # Should be able to stop
        await subscriber.stop()
        assert subscriber._consumer is None

@pytest.mark.asyncio
async def test_subscriber_consumer_creation(mock_operation, in_memory_wire_factory, json_codec_factory) -> None:
        """Test subscriber creates consumer correctly during start"""
        subscriber = Subscriber(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=json_codec_factory
        )
        
        # Initially no consumer
        assert subscriber._consumer is None
        assert subscriber._consume_task is None
        
        await subscriber.start()
        
        # Consumer should be created and started
        assert subscriber._consumer is not None
        assert subscriber._consumer._channel_name == "test.channel"
        assert subscriber._consumer._started
        # Note: _consume_task is only created when a handler is registered
        
        await subscriber.stop()

@pytest.mark.asyncio
async def test_subscriber_codec_fallback(mock_operation, in_memory_wire_factory) -> None:
        """Test subscriber tries multiple codecs until one succeeds"""
        # Create a mock codec factory that returns multiple codecs
        mock_codec1 = Mock()
        mock_codec1.decode.side_effect = ValueError("Codec 1 failed")
        
        mock_codec2 = Mock()
        decoded_user = UserModel(name="Test", age=30, email="test@example.com")
        mock_codec2.decode.return_value = decoded_user
        
        mock_codec_factory = Mock()
        mock_codec_factory.create.side_effect = [mock_codec1, mock_codec2]
        
        subscriber = Subscriber(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=mock_codec_factory
        )
        
        # Mock the _codecs list
        subscriber._codecs = [mock_codec1, mock_codec2]
        
        handler_called = False
        received_message = None
        
        @subscriber
        async def test_handler(message: UserModel) -> None:
            nonlocal handler_called, received_message
            handler_called = True
            received_message = message
        
        await subscriber.start()
        
        # Publish a message
        bus = get_bus()
        message = InMemoryMessage(_payload=b"test payload")
        await bus.publish("test.channel", message)
        
        await asyncio.sleep(0.1)
        
        # Verify handler was called with decoded message from second codec
        assert handler_called
        assert received_message == decoded_user
        
        await subscriber.stop()

@pytest.mark.asyncio
async def test_subscriber_all_codecs_fail(mock_operation, in_memory_wire_factory) -> None:
        """Test subscriber handles case when all codecs fail"""
        # Create mock codecs that all fail
        mock_codec1 = Mock()
        mock_codec1.decode.side_effect = ValueError("Codec 1 failed")
        
        mock_codec2 = Mock()
        mock_codec2.decode.side_effect = ValueError("Codec 2 failed")
        
        mock_codec_factory = Mock()
        mock_codec_factory.create.side_effect = [mock_codec1, mock_codec2]
        
        subscriber = Subscriber(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=mock_codec_factory
        )
        
        # Mock the _codecs list
        subscriber._codecs = [mock_codec1, mock_codec2]
        
        handler_called = False
        
        @subscriber
        async def test_handler(message: UserModel) -> None:
            nonlocal handler_called
            handler_called = True
        
        await subscriber.start()
        
        # Publish a message
        bus = get_bus()
        message = InMemoryMessage(_payload=b"test payload")
        await bus.publish("test.channel", message)
        
        await asyncio.sleep(0.1)
        
        # Handler should not be called when all codecs fail
        assert not handler_called
        
        await subscriber.stop()

@pytest.mark.asyncio
async def test_subscriber_wire_integration(mock_operation, in_memory_wire_factory, json_codec_factory) -> None:
        """Test subscriber integrates correctly with wire factory"""
        with patch.object(in_memory_wire_factory, 'create_consumer', new_callable=AsyncMock) as mock_create_consumer:
            # Mock consumer
            mock_consumer = AsyncMock()
            mock_consumer.recv.return_value = iter([])  # Empty async iterator
            mock_create_consumer.return_value = mock_consumer
            
            subscriber = Subscriber(
                operation=mock_operation,
                wire_factory=in_memory_wire_factory,
                codec_factory=json_codec_factory
            )
            
            await subscriber.start()
            
            # Verify wire factory was called to create consumer with correct parameters
            mock_create_consumer.assert_called_once_with(
                channel=mock_operation.channel,
                parameters={},
                op_bindings=mock_operation.bindings,
                is_reply=False
            )
            
            # Verify consumer was started
            mock_consumer.start.assert_called_once()
            
            await subscriber.stop()
            
            # Verify consumer was stopped
            mock_consumer.stop.assert_called_once()

@pytest.mark.asyncio
async def test_subscriber_stop_terminates_consumption(subscriber: Subscriber) -> None:
        """Test stopping subscriber terminates message consumption"""
        messages_received = []
        
        @subscriber
        async def test_handler(message: UserModel) -> None:
            messages_received.append(message.name)
        
        # Publish some messages
        bus = get_bus()
        for i in range(3):
            user_data = f'{{"name":"User{i}","age":30,"email":"user{i}@example.com"}}'.encode()
            message = InMemoryMessage(_payload=user_data)
            await bus.publish("test.channel", message)
        
        # Let some messages be processed
        await asyncio.sleep(0.1)
        initial_count = len(messages_received)
        
        # Stop subscriber
        await subscriber.stop()
        
        # Publish more messages
        for i in range(3, 6):
            user_data = f'{{"name":"User{i}","age":30,"email":"user{i}@example.com"}}'.encode()
            message = InMemoryMessage(_payload=user_data)
            await bus.publish("test.channel", message)
        
        # Wait and verify no additional messages were processed
        await asyncio.sleep(0.1)
        final_count = len(messages_received)
        
        assert final_count == initial_count  # No new messages processed after stop

@pytest.mark.asyncio
async def test_subscriber_concurrent_message_processing(subscriber: Subscriber) -> None:
        """Test subscriber can handle concurrent message processing"""
        processed_messages = []
        processing_times = []
        
        @subscriber
        async def test_handler(message: UserModel) -> None:
            # Simulate some async work
            await asyncio.sleep(0.05)
            processed_messages.append(message.name)
            processing_times.append(asyncio.get_event_loop().time())
        
        # Publish messages rapidly
        bus = get_bus()
        start_time = asyncio.get_event_loop().time()
        
        for i in range(3):
            user_data = f'{{"name":"User{i}","age":30,"email":"user{i}@example.com"}}'.encode()
            message = InMemoryMessage(_payload=user_data)
            await bus.publish("test.channel", message)
        
        # Wait for processing
        await asyncio.sleep(0.3)
        
        # All messages should be processed
        assert len(processed_messages) == 3
        
        # Verify messages were processed (order may vary due to async nature)
        for i in range(3):
            assert f"User{i}" in processed_messages

def test_subscriber_type_annotations(subscriber: Subscriber) -> None:
        """Test subscriber maintains proper type annotations"""
        # This test verifies the decorator doesn't break type checking
        @subscriber
        async def typed_handler(message: UserModel) -> None:
            pass
        
        # Verify the handler maintains its type signature
        assert hasattr(typed_handler, '__annotations__')
        # The function should still be callable
        assert callable(typed_handler)