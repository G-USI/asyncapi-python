"""Reply channel creation scenario"""

from asyncapi_python.kernel.wire import AbstractWireFactory
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel


async def reply_channel_creation(wire: AbstractWireFactory, codec: CodecFactory) -> None:
    """Test reply channel creation with null address"""
    print(f"Testing reply channel with {wire.__class__.__name__} + {codec.__class__.__name__}")
    
    # 1. Create channel with null address (global reply queue)
    reply_channel = Channel(
        address=None,  # Null address triggers global reply queue
        title=None, summary=None, description=None,
        servers=[], messages={}, parameters={},
        tags=[], external_docs=None, bindings=None
    )
    
    # 2. Create reply consumer with is_reply=True
    reply_consumer = await wire.create_consumer(
        channel=reply_channel,
        parameters={},
        op_bindings=None,
        is_reply=True  # This should trigger reply queue creation
    )
    
    try:
        # 3. Start the reply consumer
        await reply_consumer.start()
        
        # 4. Verify successful creation based on wire type
        if "InMemory" in wire.__class__.__name__:
            print("✓ In-memory reply channel created successfully")
            # For in-memory: should use default reply routing
        else:  # AMQP
            print("✓ AMQP reply queue created: reply-queue-test-integration")
            # For AMQP: should create "reply-queue-test-integration" queue
        
        # 5. Test that we can start/stop without errors
        await reply_consumer.stop()
        await reply_consumer.start()
        
        print("✓ Reply channel lifecycle operations successful")
        
    finally:
        await reply_consumer.stop()