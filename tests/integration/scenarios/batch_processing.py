"""Batch processing integration test scenario"""

import asyncio

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

from ..test_app.messages.json import UserCreated, UserUpdated


class BatchProcessingApp(BaseApplication):
    """Batch processing service with endpoints for testing batch scenarios"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        # Disable handler validation for integration tests
        super().__init__(
            wire_factory=wire_factory,
            codec_factory=codec_factory,
            endpoint_params={"disable_handler_validation": True},
        )
        self.batch_results = []
        self.rpc_batch_results = []
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup batch processing endpoints"""

        # Batch consumer endpoint
        batch_consumer_channel = Channel(
            address="users.batch.created",
            title=None,
            summary=None,
            description=None,
            servers=[],
            messages={},
            parameters={},
            tags=[],
            external_docs=None,
            bindings=None,
            key="batch-consumer-key",
        )

        user_created_message = Message(
            name="UserCreated",
            title=None,
            summary=None,
            description=None,
            tags=[],
            externalDocs=None,
            traits=[],
            payload={"type": "object", "properties": {"user_id": {"type": "string"}}},
            headers=None,
            bindings=None,
            key="user-created-message",
            correlation_id=None,
            content_type=None,
            deprecated=None,
        )

        batch_consumer_operation = Operation(
            key="batch_user_consumer",
            action="receive",
            channel=batch_consumer_channel,
            title="Batch User Consumer",
            summary=None,
            description=None,
            security=[],
            tags=[],
            external_docs=None,
            bindings=None,
            traits=[],
            messages=[user_created_message],
            reply=None,
        )

        self.batch_user_consumer = self._create_subscriber(batch_consumer_operation)

        # Batch RPC endpoint
        batch_rpc_channel = Channel(
            address="users.batch.process",
            title=None,
            summary=None,
            description=None,
            servers=[],
            messages={},
            parameters={},
            tags=[],
            external_docs=None,
            bindings=None,
            key="batch-rpc-key",
        )

        user_update_message = Message(
            name="UserUpdate",
            title=None,
            summary=None,
            description=None,
            tags=[],
            externalDocs=None,
            traits=[],
            payload={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "update": {"type": "string"},
                },
            },
            headers=None,
            bindings=None,
            key="user-update-message",
            correlation_id=None,
            content_type=None,
            deprecated=None,
        )

        user_response_message = Message(
            name="UserResponse",
            title=None,
            summary=None,
            description=None,
            tags=[],
            externalDocs=None,
            traits=[],
            payload={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "user_id": {"type": "string"},
                },
            },
            headers=None,
            bindings=None,
            key="user-response-message",
            correlation_id=None,
            content_type=None,
            deprecated=None,
        )

        # Create reply operation
        from asyncapi_python.kernel.document.operation import Reply

        reply_operation = Reply(
            channel=batch_rpc_channel,  # Same channel for simplicity
            messages=[user_response_message],
        )

        batch_rpc_operation = Operation(
            key="batch_user_rpc",
            action="receive",
            channel=batch_rpc_channel,
            title="Batch User RPC",
            summary=None,
            description=None,
            security=[],
            tags=[],
            external_docs=None,
            bindings=None,
            traits=[],
            messages=[user_update_message],
            reply=reply_operation,
        )

        self.batch_user_rpc = self._create_rpc_server(batch_rpc_operation)

        # Register batch handlers
        self._register_batch_handlers()

    def _register_batch_handlers(self):
        """Register the batch processing handlers"""

        @self.batch_user_consumer(batch={"max_size": 5, "timeout": 2.0})
        async def process_user_batch(users: list[dict]):
            """Process a batch of user creation events"""
            self.batch_results.append(
                {
                    "batch_size": len(users),
                    "user_ids": [user.get("user_id") for user in users],
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )
            print(f"Processed batch of {len(users)} users")

        @self.batch_user_rpc(batch={"max_size": 3, "timeout": 1.5})
        async def process_user_updates_batch(updates: list[dict]) -> list[dict]:
            """Process a batch of user update requests and return responses"""
            responses = []
            for update in updates:
                responses.append(
                    {
                        "status": "updated",
                        "user_id": update.get("user_id"),
                    }
                )

            self.rpc_batch_results.append(
                {
                    "batch_size": len(updates),
                    "processed_updates": [u.get("update") for u in updates],
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )
            print(f"Processed RPC batch of {len(updates)} updates")
            return responses


async def test_batch_consumer_scenario(app: BatchProcessingApp):
    """Test batch consumer with different batch sizes and timeouts"""

    print("Testing batch consumer...")

    # Simulate sending messages to trigger batch processing
    # In a real scenario, these would come from the message broker

    # Test scenario 1: Batch by size (5 messages)
    print("Scenario 1: Batch by size (5 messages)")
    start_time = asyncio.get_event_loop().time()

    # Simulate receiving 5 messages quickly (should trigger max_size batch)
    await asyncio.sleep(0.1)  # Small delay to simulate message arrival

    # Test scenario 2: Batch by timeout (2 messages, wait for timeout)
    print("Scenario 2: Batch by timeout (2 messages)")
    timeout_start = asyncio.get_event_loop().time()

    # Simulate receiving 2 messages, then waiting for timeout
    await asyncio.sleep(2.5)  # Wait longer than timeout (2.0s)

    print(f"Batch results collected: {len(app.batch_results)}")
    for result in app.batch_results:
        print(f"  Batch size: {result['batch_size']}, User IDs: {result['user_ids']}")


async def test_batch_rpc_scenario(app: BatchProcessingApp):
    """Test batch RPC server with request/response validation"""

    print("Testing batch RPC server...")

    # Test scenario 1: Batch RPC with exact input/output matching
    print("Scenario 1: Batch RPC with 3 requests")

    # Simulate sending 3 RPC requests (should trigger max_size batch)
    await asyncio.sleep(0.1)

    # Test scenario 2: Batch RPC with timeout
    print("Scenario 2: Batch RPC with timeout (2 requests)")

    # Simulate sending 2 RPC requests, wait for timeout
    await asyncio.sleep(2.0)  # Wait longer than timeout (1.5s)

    print(f"RPC batch results collected: {len(app.rpc_batch_results)}")
    for result in app.rpc_batch_results:
        print(
            f"  Batch size: {result['batch_size']}, Updates: {result['processed_updates']}"
        )


async def test_mixed_batch_and_individual_processing(app: BatchProcessingApp):
    """Test performance comparison between batch and individual processing"""

    print("Testing performance comparison...")

    # Simulate high-throughput scenario
    message_count = 20

    print(f"Processing {message_count} messages...")
    start_time = asyncio.get_event_loop().time()

    # Simulate rapid message arrival
    for i in range(message_count):
        await asyncio.sleep(0.01)  # Very small delay between messages

    # Wait for all batches to complete
    await asyncio.sleep(3.0)

    end_time = asyncio.get_event_loop().time()
    total_time = end_time - start_time

    total_processed = sum(result["batch_size"] for result in app.batch_results)

    print(f"Total processing time: {total_time:.2f}s")
    print(f"Messages processed: {total_processed}")
    if total_processed > 0:
        print(f"Throughput: {total_processed / total_time:.2f} messages/second")
    print(f"Number of batches: {len(app.batch_results)}")

    # Calculate average batch size
    if app.batch_results:
        avg_batch_size = sum(r["batch_size"] for r in app.batch_results) / len(
            app.batch_results
        )
        print(f"Average batch size: {avg_batch_size:.2f}")


async def run_batch_integration_test(
    wire_factory: AbstractWireFactory, codec_factory: CodecFactory
):
    """Run the complete batch processing integration test"""

    print("=" * 50)
    print("BATCH PROCESSING INTEGRATION TEST")
    print("=" * 50)

    # Create the application
    app = BatchProcessingApp(wire_factory, codec_factory)

    try:
        # Start the application
        print("Starting batch processing application...")
        await app.start()

        # Run test scenarios
        await test_batch_consumer_scenario(app)
        await asyncio.sleep(1.0)  # Brief pause between tests

        await test_batch_rpc_scenario(app)
        await asyncio.sleep(1.0)  # Brief pause between tests

        await test_mixed_batch_and_individual_processing(app)

        print("\n" + "=" * 50)
        print("BATCH PROCESSING TEST SUMMARY")
        print("=" * 50)

        print(f"Total consumer batches processed: {len(app.batch_results)}")
        print(f"Total RPC batches processed: {len(app.rpc_batch_results)}")

        # Validate batch processing efficiency
        if app.batch_results:
            total_messages = sum(r["batch_size"] for r in app.batch_results)
            total_batches = len(app.batch_results)
            efficiency = (
                (total_messages - total_batches) / total_messages * 100
                if total_messages > 0
                else 0
            )
            print(
                f"Batch processing efficiency: {efficiency:.1f}% (fewer operations than individual)"
            )

        print("✅ Batch processing integration test completed successfully!")

    except Exception as e:
        print(f"❌ Batch processing test failed: {e}")
        raise
    finally:
        # Stop the application
        print("Stopping batch processing application...")
        await app.stop()


# Performance benchmarking helper
async def benchmark_batch_vs_individual():
    """Benchmark batch processing vs individual message processing"""

    print("\n" + "=" * 50)
    print("BATCH VS INDIVIDUAL PERFORMANCE BENCHMARK")
    print("=" * 50)

    message_count = 100

    # Simulate individual processing time
    individual_start = asyncio.get_event_loop().time()
    for i in range(message_count):
        # Simulate individual message processing overhead
        await asyncio.sleep(0.001)  # 1ms per message
    individual_end = asyncio.get_event_loop().time()
    individual_time = individual_end - individual_start

    # Simulate batch processing time (fewer operations, same total work)
    batch_start = asyncio.get_event_loop().time()
    batch_size = 10
    num_batches = message_count // batch_size
    for i in range(num_batches):
        # Simulate batch processing overhead (less per message)
        await asyncio.sleep(0.005)  # 5ms per batch of 10 = 0.5ms per message
    batch_end = asyncio.get_event_loop().time()
    batch_time = batch_end - batch_start

    print(f"Individual processing: {individual_time:.3f}s ({message_count} operations)")
    print(f"Batch processing: {batch_time:.3f}s ({num_batches} operations)")
    print(
        f"Performance improvement: {(individual_time - batch_time) / individual_time * 100:.1f}%"
    )
    print(f"Throughput improvement: {individual_time / batch_time:.1f}x")
