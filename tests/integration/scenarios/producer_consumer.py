"""Producer->Consumer roundtrip scenario"""

from asyncapi_python.kernel.wire import AbstractWireFactory
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message

# Import test models
import sys
from pathlib import Path
test_app_path = Path(__file__).parent.parent / "test_app"
sys.path.insert(0, str(test_app_path.parent))
import test_app.messages.json as test_models


async def producer_consumer_roundtrip(wire: AbstractWireFactory, codec: CodecFactory) -> None:
    """Test producer->consumer message roundtrip"""
    print(f"Testing roundtrip with {wire.__class__.__name__} + {codec.__class__.__name__}")
    
    # 1. Create test channel
    test_channel = Channel(
        address="test.roundtrip.channel",
        title=None, summary=None, description=None,
        servers=[], messages={}, parameters={},
        tags=[], external_docs=None, bindings=None
    )
    
    # 2. Create test message specification
    test_message = Message(
        name="test.user",  # Maps to TestUser class via _to_class_name conversion
        title=None, summary=None, description=None,
        tags=[], externalDocs=None, traits=[],
        payload={"type": "object"}, headers=None,
        bindings=None, correlation_id=None,
        content_type=None, deprecated=None
    )
    
    # 3. Create codec instance
    message_codec = codec.create(test_message)
    
    # 4. Create test data
    test_user = test_models.TestUser(id=123, name="Alice", email="alice@example.com")
    
    # 5. Create producer and consumer
    producer = await wire.create_producer(
        channel=test_channel, parameters={}, op_bindings=None, is_reply=False
    )
    consumer = await wire.create_consumer(
        channel=test_channel, parameters={}, op_bindings=None, is_reply=False
    )
    
    try:
        # 6. Start endpoints
        await producer.start()
        await consumer.start()
        
        # 7. Encode and send message
        encoded_payload = message_codec.encode(test_user)
        
        # Create wire message based on wire type
        if "InMemory" in wire.__class__.__name__:
            from asyncapi_python.contrib.wire.in_memory import InMemoryMessage
            wire_message = InMemoryMessage(
                _payload=encoded_payload,
                _headers={"content-type": "application/json"},
                _correlation_id="test-123",
                _reply_to=None
            )
        else:  # AMQP
            from asyncapi_python.contrib.wire.amqp import AmqpWireMessage
            wire_message = AmqpWireMessage(
                _payload=encoded_payload,
                _headers={"content-type": "application/json"},
                _correlation_id="test-123",
                _reply_to=None
            )
        
        await producer.send_batch([wire_message])
        
        # 8. Receive and verify message
        received_message = None
        async for msg in consumer.recv():
            received_message = msg
            await msg.ack()
            break
        
        assert received_message is not None, "No message received"
        assert received_message.correlation_id == "test-123"
        
        # 9. Decode and verify payload
        decoded_user = message_codec.decode(received_message.payload)
        assert decoded_user.id == test_user.id
        assert decoded_user.name == test_user.name
        assert decoded_user.email == test_user.email
        
        print(f"✓ Roundtrip successful: {decoded_user}")
        
    finally:
        await producer.stop()
        await consumer.stop()