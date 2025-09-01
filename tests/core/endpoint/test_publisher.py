import pytest
from unittest.mock import AsyncMock, Mock, patch

from asyncapi_python.kernel.endpoint.publisher import Publisher
from asyncapi_python.contrib.wire.in_memory import InMemoryMessage, get_bus
from typing import AsyncGenerator
# Test model for publisher tests
from pydantic import BaseModel

class UserModel(BaseModel):
    name: str
    age: int
    email: str


# Fixtures
@pytest.fixture
async def publisher(mock_operation, in_memory_wire_factory, json_codec_factory) -> AsyncGenerator[Publisher, None]:
    """Create a publisher instance for testing"""
    publisher = Publisher(
        operation=mock_operation,
        wire_factory=in_memory_wire_factory,
        codec_factory=json_codec_factory
    )
    await publisher.start()
    yield publisher
    await publisher.stop()

@pytest.fixture
def sample_user() -> UserModel:
    return UserModel(name="John Doe", age=30, email="john@example.com")


# Publisher tests
@pytest.mark.asyncio
async def test_publisher_send_message(publisher: Publisher, sample_user: UserModel) -> None:
        """Test publisher can send a message"""
        await publisher(sample_user)
        
        # Verify message was sent to the wire
        bus = get_bus()
        received = await bus.get_message("test.channel")
        
        assert received is not None
        assert received.payload == b'{"name":"John Doe","age":30,"email":"john@example.com"}'

@pytest.mark.asyncio
async def test_publisher_message_encoding(publisher: Publisher, sample_user: UserModel) -> None:
        """Test publisher correctly encodes message using codec"""
        await publisher(sample_user)
        
        bus = get_bus()
        received = await bus.get_message("test.channel")
        
        # Verify the payload is properly JSON-encoded
        import json
        decoded_payload = json.loads(received.payload.decode('utf-8'))
        assert decoded_payload == {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com"
        }

@pytest.mark.asyncio
async def test_publisher_multiple_messages(publisher: Publisher) -> None:
        """Test publisher can send multiple messages"""
        user1 = UserModel(name="Alice", age=25, email="alice@example.com")
        user2 = UserModel(name="Bob", age=35, email="bob@example.com")
        
        await publisher(user1)
        await publisher(user2)
        
        bus = get_bus()
        received1 = await bus.get_message("test.channel")
        received2 = await bus.get_message("test.channel")
        
        assert received1 is not None
        assert received2 is not None
        
        # Verify both messages were sent
        import json
        payload1 = json.loads(received1.payload.decode('utf-8'))
        payload2 = json.loads(received2.payload.decode('utf-8'))
        
        assert payload1["name"] == "Alice"
        assert payload2["name"] == "Bob"

@pytest.mark.asyncio
async def test_publisher_encoding_error(mock_operation, in_memory_wire_factory, json_codec_factory) -> None:
        """Test publisher handles encoding errors gracefully"""
        publisher = Publisher(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=json_codec_factory
        )
        await publisher.start()
        
        # Try to send an object that can't be encoded by JSON codec
        class UnserializableObject:
            pass
        
        with pytest.raises(RuntimeError, match="Failed to encode payload"):
            await publisher(UnserializableObject())
        
        await publisher.stop()

@pytest.mark.asyncio
async def test_publisher_lifecycle_management(mock_operation, in_memory_wire_factory, json_codec_factory) -> None:
        """Test publisher start/stop lifecycle"""
        publisher = Publisher(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=json_codec_factory
        )
        
        # Should be able to start
        await publisher.start()
        assert publisher._producer is not None
        assert publisher._producer._started
        
        # Should be able to stop
        await publisher.stop()
        assert publisher._producer is None

@pytest.mark.asyncio
async def test_publisher_wire_message_properties(publisher: Publisher, sample_user: UserModel) -> None:
        """Test publisher sets correct wire message properties"""
        await publisher(sample_user)
        
        bus = get_bus()
        received = await bus.get_message("test.channel")
        
        # Verify wire message has correct structure
        assert isinstance(received.payload, bytes)
        assert isinstance(received.headers, dict)
        assert received.correlation_id is None  # Should be None for simple send
        assert received.reply_to is None  # Should be None for simple send

@pytest.mark.asyncio
async def test_publisher_with_headers(mock_operation, in_memory_wire_factory, json_codec_factory, sample_user: UserModel) -> None:
        """Test publisher can include headers in wire message"""
        # Create publisher
        publisher = Publisher(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=json_codec_factory
        )
        await publisher.start()
        
        # Send message (headers are set internally by the publisher)
        await publisher(sample_user)
        
        bus = get_bus()
        received = await bus.get_message("test.channel")
        
        # Verify message structure
        assert received.headers == {}  # Default empty headers
        assert received.payload is not None
        
        await publisher.stop()

@pytest.mark.asyncio 
async def test_publisher_producer_creation(mock_operation, in_memory_wire_factory, json_codec_factory) -> None:
        """Test publisher creates producer correctly during start"""
        publisher = Publisher(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=json_codec_factory
        )
        
        # Initially no producer
        assert publisher._producer is None
        
        await publisher.start()
        
        # Producer should be created and started
        assert publisher._producer is not None
        assert publisher._producer._channel_name == "test.channel"
        assert publisher._producer._started
        
        await publisher.stop()

@pytest.mark.asyncio
async def test_publisher_codec_fallback(mock_operation, in_memory_wire_factory) -> None:
        """Test publisher tries multiple codecs until one succeeds"""
        # Create a mock codec factory that returns multiple codecs
        mock_codec1 = Mock()
        mock_codec1.encode.side_effect = ValueError("Codec 1 failed")
        
        mock_codec2 = Mock()
        mock_codec2.encode.return_value = b"encoded by codec 2"
        
        mock_codec_factory = Mock()
        mock_codec_factory.create.side_effect = [mock_codec1, mock_codec2]
        
        publisher = Publisher(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=mock_codec_factory
        )
        
        await publisher.start()
        
        # Mock the _codecs list to have our mock codecs
        publisher._codecs = [mock_codec1, mock_codec2]
        
        test_payload = {"test": "data"}
        await publisher(test_payload)
        
        # Verify first codec was tried and failed
        mock_codec1.encode.assert_called_once_with(test_payload)
        
        # Verify second codec was tried and succeeded
        mock_codec2.encode.assert_called_once_with(test_payload)
        
        # Verify message was sent with second codec result
        bus = get_bus()
        received = await bus.get_message("test.channel")
        assert received.payload == b"encoded by codec 2"
        
        await publisher.stop()

@pytest.mark.asyncio
async def test_publisher_all_codecs_fail(mock_operation, in_memory_wire_factory) -> None:
        """Test publisher raises error when all codecs fail"""
        # Create mock codecs that all fail
        mock_codec1 = Mock()
        mock_codec1.encode.side_effect = ValueError("Codec 1 failed")
        
        mock_codec2 = Mock() 
        mock_codec2.encode.side_effect = ValueError("Codec 2 failed")
        
        mock_codec_factory = Mock()
        mock_codec_factory.create.side_effect = [mock_codec1, mock_codec2]
        
        publisher = Publisher(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=mock_codec_factory
        )
        
        await publisher.start()
        
        # Mock the _codecs list
        publisher._codecs = [mock_codec1, mock_codec2]
        
        test_payload = {"test": "data"}
        
        with pytest.raises(RuntimeError, match="Failed to encode payload with any available codec"):
            await publisher(test_payload)
        
        await publisher.stop()

@pytest.mark.asyncio
async def test_publisher_no_codecs_available(mock_operation, in_memory_wire_factory) -> None:
        """Test publisher raises error when no codecs are available"""
        mock_codec_factory = Mock()
        mock_codec_factory.create.return_value = None
        
        publisher = Publisher(
            operation=mock_operation,
            wire_factory=in_memory_wire_factory,
            codec_factory=mock_codec_factory
        )
        
        await publisher.start()
        
        # Mock empty codecs list
        publisher._codecs = []
        
        test_payload = {"test": "data"}
        
        with pytest.raises(RuntimeError, match="No codecs available"):
            await publisher(test_payload)
        
        await publisher.stop()

@pytest.mark.asyncio
async def test_publisher_return_type(publisher: Publisher, sample_user: UserModel) -> None:
        """Test publisher __call__ returns None as specified by type signature"""
        result = await publisher(sample_user)
        assert result is None

@pytest.mark.asyncio
async def test_publisher_wire_integration(mock_operation, in_memory_wire_factory, json_codec_factory, sample_user: UserModel) -> None:
        """Test publisher integrates correctly with wire factory"""
        with patch.object(in_memory_wire_factory, 'create_producer', new_callable=AsyncMock) as mock_create_producer:
            # Mock producer
            mock_producer = AsyncMock()
            mock_create_producer.return_value = mock_producer
            
            publisher = Publisher(
                operation=mock_operation,
                wire_factory=in_memory_wire_factory,
                codec_factory=json_codec_factory
            )
            
            await publisher.start()
            
            # Verify wire factory was called to create producer with correct parameters
            mock_create_producer.assert_called_once_with(
                channel=mock_operation.channel,
                parameters={},
                op_bindings=mock_operation.bindings,
                is_reply=False
            )
            
            # Verify producer was started
            mock_producer.start.assert_called_once()
            
            await publisher.stop()
            
            # Verify producer was stopped
            mock_producer.stop.assert_called_once()