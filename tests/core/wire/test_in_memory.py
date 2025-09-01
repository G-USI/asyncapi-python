import asyncio
import pytest
from unittest.mock import Mock, patch

from asyncapi_python.contrib.wire.in_memory import (
    InMemoryMessage,
    InMemoryIncomingMessage,
    InMemoryBus,
    InMemoryProducer,
    InMemoryConsumer,
    InMemoryWireFactory,
    get_bus,
    reset_bus
)


# InMemoryMessage tests
def test_message_properties() -> None:
        """Test InMemoryMessage property access"""
        headers = {"content-type": "application/json"}
        message = InMemoryMessage(
            _payload=b'{"test": "data"}',
            _headers=headers,
            _correlation_id="corr-123",
            _reply_to="reply.queue"
        )
        
        assert message.payload == b'{"test": "data"}'
        assert message.headers == headers
        assert message.correlation_id == "corr-123"
        assert message.reply_to == "reply.queue"

def test_message_defaults() -> None:
        """Test InMemoryMessage with default values"""
        message = InMemoryMessage(_payload=b"test")
        
        assert message.payload == b"test"
        assert message.headers == {}
        assert message.correlation_id is None
        assert message.reply_to is None


# InMemoryIncomingMessage tests
def test_initial_ack_state() -> None:
        """Test initial acknowledgment state"""
        message = InMemoryIncomingMessage(_payload=b"test")
        
        assert not message.is_acknowledged
        assert not message.is_nacked
        assert not message.is_rejected

@pytest.mark.asyncio
async def test_ack_message() -> None:
        """Test message acknowledgment"""
        message = InMemoryIncomingMessage(_payload=b"test")
        
        await message.ack()
        
        assert message.is_acknowledged
        assert not message.is_nacked
        assert not message.is_rejected

@pytest.mark.asyncio
async def test_nack_message() -> None:
        """Test message negative acknowledgment"""
        message = InMemoryIncomingMessage(_payload=b"test")
        
        await message.nack()
        
        assert not message.is_acknowledged
        assert message.is_nacked
        assert not message.is_rejected

@pytest.mark.asyncio
async def test_reject_message() -> None:
        """Test message rejection"""
        message = InMemoryIncomingMessage(_payload=b"test")
        
        await message.reject()
        
        assert not message.is_acknowledged
        assert not message.is_nacked
        assert message.is_rejected

def test_inherits_from_memory_message() -> None:
        """Test InMemoryIncomingMessage inherits InMemoryMessage properties"""
        message = InMemoryIncomingMessage(
            _payload=b"test",
            _headers={"type": "test"},
            _correlation_id="corr-456"
        )
        
        assert message.payload == b"test"
        assert message.headers == {"type": "test"}
        assert message.correlation_id == "corr-456"


# InMemoryBus tests
@pytest.fixture
def bus() -> InMemoryBus:
    return InMemoryBus()

@pytest.mark.asyncio
async def test_publish_and_get_message(bus: InMemoryBus) -> None:
        """Test basic publish and get message functionality"""
        message = InMemoryMessage(_payload=b"test message")
        
        await bus.publish("test.channel", message)
        received = await bus.get_message("test.channel")
        
        assert received is not None
        assert received.payload == b"test message"
        assert isinstance(received, InMemoryIncomingMessage)

@pytest.mark.asyncio
async def test_get_message_empty_channel(bus: InMemoryBus) -> None:
        """Test getting message from empty channel returns None"""
        result = await bus.get_message("empty.channel")
        assert result is None

@pytest.mark.asyncio
async def test_fifo_message_ordering(bus: InMemoryBus) -> None:
        """Test messages are delivered in FIFO order"""
        msg1 = InMemoryMessage(_payload=b"first")
        msg2 = InMemoryMessage(_payload=b"second")
        msg3 = InMemoryMessage(_payload=b"third")
        
        await bus.publish("test.channel", msg1)
        await bus.publish("test.channel", msg2)
        await bus.publish("test.channel", msg3)
        
        received1 = await bus.get_message("test.channel")
        received2 = await bus.get_message("test.channel")
        received3 = await bus.get_message("test.channel")
        
        assert received1 is not None
        assert received2 is not None
        assert received3 is not None
        assert received1.payload == b"first"
        assert received2.payload == b"second"
        assert received3.payload == b"third"

@pytest.mark.asyncio
async def test_message_headers_preserved(bus: InMemoryBus) -> None:
        """Test message headers are preserved during publish/get"""
        headers = {"content-type": "application/json", "priority": "high"}
        message = InMemoryMessage(_payload=b"test", _headers=headers)
        
        await bus.publish("test.channel", message)
        received = await bus.get_message("test.channel")
        
        assert received is not None
        assert received.headers == headers

@pytest.mark.asyncio
async def test_message_correlation_and_reply_to(bus: InMemoryBus) -> None:
        """Test correlation_id and reply_to are preserved"""
        message = InMemoryMessage(
            _payload=b"test",
            _correlation_id="corr-123",
            _reply_to="reply.queue"
        )
        
        await bus.publish("test.channel", message)
        received = await bus.get_message("test.channel")
        
        assert received is not None
        assert received.correlation_id == "corr-123"
        assert received.reply_to == "reply.queue"

@pytest.mark.asyncio
async def test_consumer_subscription_notification(bus: InMemoryBus) -> None:
        """Test consumers are notified when messages are published"""
        consumer = InMemoryConsumer("test.channel")
        await bus.subscribe("test.channel", consumer)
        
        # Mock the notification method to track calls
        notification_called = False
        original_notify = consumer._notify_new_message
        
        def mock_notify():
            nonlocal notification_called
            notification_called = True
            original_notify()
        
        # Mock the notification method using patch
        with patch.object(consumer, '_notify_new_message', side_effect=mock_notify):
            message = InMemoryMessage(_payload=b"test")
            await bus.publish("test.channel", message)
            
            assert notification_called

@pytest.mark.asyncio
async def test_multiple_consumers_notification(bus: InMemoryBus) -> None:
        """Test multiple consumers are notified"""
        consumer1 = InMemoryConsumer("test.channel")
        consumer2 = InMemoryConsumer("test.channel")
        
        await bus.subscribe("test.channel", consumer1)
        await bus.subscribe("test.channel", consumer2)
        
        notifications = []
        
        def make_mock_notify(consumer_id):
            def mock_notify():
                notifications.append(consumer_id)
                # Call original to maintain functionality
                if consumer_id == 1:
                    consumer1._message_event.set()
                else:
                    consumer2._message_event.set()
            return mock_notify
        
        # Mock the notification methods using patch
        with patch.object(consumer1, '_notify_new_message', side_effect=make_mock_notify(1)), \
             patch.object(consumer2, '_notify_new_message', side_effect=make_mock_notify(2)):
            
            message = InMemoryMessage(_payload=b"test")
            await bus.publish("test.channel", message)
            
            assert 1 in notifications
            assert 2 in notifications

@pytest.mark.asyncio
async def test_consumer_unsubscribe(bus: InMemoryBus) -> None:
        """Test consumer unsubscription"""
        consumer = InMemoryConsumer("test.channel")
        
        await bus.subscribe("test.channel", consumer)
        await bus.unsubscribe("test.channel", consumer)
        
        # Consumer should not be notified after unsubscription
        notification_called = False
        def mock_notify():
            nonlocal notification_called
            notification_called = True
        
        # Mock the notification method using patch
        with patch.object(consumer, '_notify_new_message', side_effect=mock_notify):
            message = InMemoryMessage(_payload=b"test")
            await bus.publish("test.channel", message)
            
            assert not notification_called


# InMemoryProducer tests
@pytest.fixture
def producer() -> InMemoryProducer:
    return InMemoryProducer("test.channel")

@pytest.mark.asyncio
async def test_producer_lifecycle(producer: InMemoryProducer) -> None:
        """Test producer start/stop lifecycle"""
        assert not producer._started
        
        await producer.start()
        assert producer._started
        
        await producer.stop()
        assert not producer._started

@pytest.mark.asyncio
async def test_send_batch_when_started(producer: InMemoryProducer) -> None:
        """Test sending batch of messages when producer is started"""
        messages = [
            InMemoryMessage(_payload=b"msg1"),
            InMemoryMessage(_payload=b"msg2")
        ]
        
        await producer.start()
        
        # Should not raise exception
        await producer.send_batch(messages)
        
        # Verify messages were published to bus
        bus = get_bus()
        received1 = await bus.get_message("test.channel")
        received2 = await bus.get_message("test.channel")
        
        assert received1 is not None
        assert received2 is not None
        assert received1.payload == b"msg1"
        assert received2.payload == b"msg2"

@pytest.mark.asyncio
async def test_send_batch_when_not_started(producer: InMemoryProducer) -> None:
        """Test sending batch raises error when producer not started"""
        messages = [InMemoryMessage(_payload=b"test")]
        
        with pytest.raises(RuntimeError, match="Producer not started"):
            await producer.send_batch(messages)

@pytest.mark.asyncio
async def test_send_empty_batch(producer: InMemoryProducer) -> None:
        """Test sending empty batch"""
        await producer.start()
        await producer.send_batch([])  # Should not raise exception


# InMemoryConsumer tests
@pytest.fixture
def consumer() -> InMemoryConsumer:
    return InMemoryConsumer("test.channel")

@pytest.mark.asyncio
async def test_consumer_lifecycle(consumer: InMemoryConsumer) -> None:
        """Test consumer start/stop lifecycle"""
        assert not consumer._started
        
        await consumer.start()
        assert consumer._started
        
        await consumer.stop()
        assert not consumer._started

@pytest.mark.asyncio
async def test_recv_when_not_started(consumer: InMemoryConsumer) -> None:
        """Test recv raises error when consumer not started"""
        async_gen = consumer.recv()
        
        with pytest.raises(RuntimeError, match="Consumer not started"):
            await async_gen.__anext__()

@pytest.mark.asyncio
async def test_recv_single_message(consumer: InMemoryConsumer) -> None:
        """Test receiving a single message"""
        # Publish message to bus first
        bus = get_bus()
        message = InMemoryMessage(_payload=b"test message")
        await bus.publish("test.channel", message)
        
        await consumer.start()
        
        async_gen = consumer.recv()
        received = await async_gen.__anext__()
        
        assert received.payload == b"test message"
        assert isinstance(received, InMemoryIncomingMessage)

@pytest.mark.asyncio
async def test_recv_multiple_messages(consumer: InMemoryConsumer) -> None:
        """Test receiving multiple messages in sequence"""
        bus = get_bus()
        
        # Publish multiple messages
        for i in range(3):
            message = InMemoryMessage(_payload=f"message {i}".encode())
            await bus.publish("test.channel", message)
        
        await consumer.start()
        
        received_messages = []
        async_gen = consumer.recv()
        
        for _ in range(3):
            received = await async_gen.__anext__()
            received_messages.append(received.payload)
        
        assert received_messages == [b"message 0", b"message 1", b"message 2"]

@pytest.mark.asyncio
async def test_recv_waits_for_messages(consumer: InMemoryConsumer) -> None:
        """Test consumer waits for messages when none available"""
        await consumer.start()
        
        async def publish_after_delay():
            await asyncio.sleep(0.1)
            bus = get_bus()
            message = InMemoryMessage(_payload=b"delayed message")
            await bus.publish("test.channel", message)
        
        # Start publishing task
        publish_task = asyncio.create_task(publish_after_delay())
        
        # Start consuming - should wait for message
        async_gen = consumer.recv()
        received = await async_gen.__anext__()
        
        await publish_task
        
        assert received.payload == b"delayed message"

@pytest.mark.asyncio
async def test_consumer_stop_terminates_recv(consumer: InMemoryConsumer) -> None:
        """Test stopping consumer terminates recv generator"""
        await consumer.start()
        
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            await consumer.stop()
        
        stop_task = asyncio.create_task(stop_after_delay())
        
        # Start consuming and expect it to terminate when stopped
        async_gen = consumer.recv()
        messages_received = 0
        
        async for message in async_gen:
            messages_received += 1
            # Should not receive any messages and loop should terminate
        
        await stop_task
        assert messages_received == 0

@pytest.mark.asyncio
async def test_concurrent_consumers_same_channel() -> None:
        """Test multiple consumers on same channel each receive messages"""
        consumer1 = InMemoryConsumer("test.channel")
        consumer2 = InMemoryConsumer("test.channel")
        
        await consumer1.start()
        await consumer2.start()
        
        # Publish messages
        bus = get_bus()
        for i in range(4):
            message = InMemoryMessage(_payload=f"message {i}".encode())
            await bus.publish("test.channel", message)
        
        # Both consumers should receive messages (FIFO, first-come-first-served)
        async_gen1 = consumer1.recv()
        async_gen2 = consumer2.recv()
        
        received1 = []
        received2 = []
        
        # Simulate concurrent consumption
        async def consume1():
            async for msg in async_gen1:
                received1.append(msg.payload)
                if len(received1) >= 2:  # Stop after 2 messages
                    break
        
        async def consume2():
            async for msg in async_gen2:
                received2.append(msg.payload)
                if len(received2) >= 2:  # Stop after 2 messages
                    break
        
        await asyncio.gather(consume1(), consume2())
        
        # Both consumers should have received messages
        all_received = received1 + received2
        assert len(all_received) == 4
        
        # Clean up
        await consumer1.stop()
        await consumer2.stop()


# InMemoryWireFactory tests
@pytest.fixture
def factory() -> InMemoryWireFactory:
    return InMemoryWireFactory()

@pytest.mark.asyncio
async def test_create_consumer(factory: InMemoryWireFactory, mock_channel) -> None:
        """Test creating consumer from wire factory"""
        consumer = await factory.create_consumer(
            channel=mock_channel,
            parameters={},
            op_bindings=None,
            is_reply=False
        )
        
        assert isinstance(consumer, InMemoryConsumer)
        # We can check the _channel_name attribute since we know it's InMemoryConsumer
        assert consumer._channel_name == "test.channel"

@pytest.mark.asyncio
async def test_create_producer(factory: InMemoryWireFactory, mock_channel) -> None:
        """Test creating producer from wire factory"""
        producer = await factory.create_producer(
            channel=mock_channel,
            parameters={},
            op_bindings=None,
            is_reply=False
        )
        
        assert isinstance(producer, InMemoryProducer)
        # We can check the _channel_name attribute since we know it's InMemoryProducer
        assert producer._channel_name == "test.channel"

@pytest.mark.asyncio
async def test_create_consumer_default_channel(factory: InMemoryWireFactory) -> None:
        """Test creating consumer with no channel address uses default"""
        from asyncapi_python.kernel.document.channel import Channel, ChannelBindings
        
        channel_no_address = Channel(
            address=None,  # No address
            title=None,
            summary=None,
            description=None,
            servers=[],
            messages={},
            parameters={},
            tags=[],
            external_docs=None,
            bindings=ChannelBindings()
        )
        
        consumer = await factory.create_consumer(
            channel=channel_no_address,
            parameters={},
            op_bindings=None,
            is_reply=False
        )
        # Note: We can only check this on the concrete InMemoryConsumer implementation
        if hasattr(consumer, '_channel_name'):
            assert consumer._channel_name == "default"

@pytest.mark.asyncio
async def test_create_producer_default_channel(factory: InMemoryWireFactory) -> None:
        """Test creating producer with no channel address uses default"""
        from asyncapi_python.kernel.document.channel import Channel, ChannelBindings
        
        channel_no_address = Channel(
            address=None,  # No address
            title=None,
            summary=None,
            description=None,
            servers=[],
            messages={},
            parameters={},
            tags=[],
            external_docs=None,
            bindings=ChannelBindings()
        )
        
        producer = await factory.create_producer(
            channel=channel_no_address,
            parameters={},
            op_bindings=None,
            is_reply=False
        )
        # Note: We can only check this on the concrete InMemoryProducer implementation
        if hasattr(producer, '_channel_name'):
            assert producer._channel_name == "default"


# Global bus operations tests
def test_get_bus_returns_same_instance() -> None:
        """Test get_bus returns the same instance"""
        bus1 = get_bus()
        bus2 = get_bus()
        assert bus1 is bus2

@pytest.mark.asyncio
async def test_reset_bus_clears_state() -> None:
        """Test reset_bus clears all bus state"""
        bus = get_bus()
        
        # Add some messages
        message = InMemoryMessage(_payload=b"test")
        await bus.publish("test.channel", message)
        
        # Verify message exists
        received = await bus.get_message("test.channel")
        assert received is not None
        
        # Reset bus
        reset_bus()
        
        # Get new bus instance and verify it's clean
        new_bus = get_bus()
        empty_result = await new_bus.get_message("test.channel")
        assert empty_result is None

def test_reset_bus_creates_new_instance() -> None:
        """Test reset_bus creates a new bus instance"""
        bus1 = get_bus()
        reset_bus()
        bus2 = get_bus()
        
        assert bus1 is not bus2