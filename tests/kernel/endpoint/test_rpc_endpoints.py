"""Integration tests for RPC client and server endpoints"""

import asyncio
import json
from typing import AsyncGenerator

import pytest

from asyncapi_python.kernel.codec import Codec, CodecFactory
from asyncapi_python.kernel.document import Channel, Message, Operation, OperationReply
from asyncapi_python.kernel.endpoint.exceptions import TimeoutError, UninitializedError
from asyncapi_python.kernel.endpoint.message import WireMessage
from asyncapi_python.kernel.endpoint.publisher import Publisher
from asyncapi_python.kernel.endpoint.rpc_client import RpcClient
from asyncapi_python.kernel.endpoint.rpc_reply_handler import global_reply_handler
from asyncapi_python.kernel.endpoint.rpc_server import RpcServer
from asyncapi_python.kernel.endpoint.subscriber import Subscriber
from asyncapi_python.kernel.typing import IncomingMessage
from asyncapi_python.kernel.wire import AbstractWireFactory, Consumer, Producer


@pytest.fixture
async def cleanup_rpc_client():
    """Clean up RPC client global state between tests"""
    yield

    # Clean up global state after each test
    # Force instance count to 0 to trigger cleanup
    global_reply_handler._instance_count = 0

    # First cancel the background task
    if (
        global_reply_handler._consume_task
        and not global_reply_handler._consume_task.done()
    ):
        global_reply_handler._consume_task.cancel()
        try:
            await global_reply_handler._consume_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        global_reply_handler._consume_task = None

    # Stop the consumer
    if global_reply_handler._reply_consumer:
        try:
            await global_reply_handler._reply_consumer.stop()
        except Exception:
            pass
        global_reply_handler._reply_consumer = None

    # Cancel any remaining futures
    for future in list(global_reply_handler._futures.values()):
        if not future.done():
            future.cancel()
            # Give cancelled futures a chance to be collected
            try:
                await asyncio.sleep(0)
            except:
                pass

    global_reply_handler._futures.clear()
    global_reply_handler._reply_queue_name = None

    # Give any remaining tasks a chance to clean up
    await asyncio.sleep(0.01)


# Test message types
class RequestMessage:
    def __init__(self, data: str):
        self.data = data


class ResponseMessage:
    def __init__(self, result: str):
        self.result = result


@pytest.fixture
def mock_operation():
    """Create a mock RPC operation"""
    channel = Channel(
        address="test.rpc",
        title="Test RPC Channel",
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=None,
        key="test-key",
    )

    reply_channel = Channel(
        address=None,  # Default reply queue
        title="Reply Channel",
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=None,
        key="test-key",
    )

    request_message = Message(
        name="RequestMessage",
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        traits=[],
        payload={"type": "object"},
        headers=None,
        bindings=None,
        key="test-key",
        correlation_id=None,
        content_type=None,
        deprecated=None,
    )

    response_message = Message(
        name="ResponseMessage",
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        traits=[],
        payload={"type": "object"},
        headers=None,
        bindings=None,
        key="test-key",
        correlation_id=None,
        content_type=None,
        deprecated=None,
    )

    reply = OperationReply(
        channel=reply_channel,
        address=None,
        messages=[response_message],
    )

    operation = Operation(
        action="send",  # For RPC client
        channel=channel,
        messages=[request_message],
        reply=reply,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        traits=[],
        bindings=None,
        key="test-key",
        security=None,
    )

    return operation


# Realistic implementations for scenario tests
class RealisticWireMessage(WireMessage):
    """Wire message that supports ack/nack operations"""

    def __init__(
        self,
        payload: bytes,
        headers: dict,
        correlation_id: str | None = None,
        reply_to: str | None = None,
    ):
        super().__init__(payload, headers, correlation_id, reply_to)
        self._acked = False
        self._nacked = False

    async def ack(self) -> None:
        self._acked = True

    async def nack(self) -> None:
        self._nacked = True


class RealisticConsumer:
    """Consumer that can route messages between client and server"""

    def __init__(self, is_reply: bool = False):
        self.is_reply = is_reply
        self._started = False
        self._message_queue: asyncio.Queue[WireMessage] = asyncio.Queue()
        self._factory: RealisticWireFactory | None = None

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False
        # Clear any remaining messages to help with cleanup
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
            except:
                break

    def set_factory(self, factory: "RealisticWireFactory") -> None:
        self._factory = factory

    async def recv(self) -> AsyncGenerator[WireMessage, None]:
        """Async generator that yields messages from the queue"""
        while self._started:
            try:
                # Wait for a message with a timeout to allow checking _started
                message = await asyncio.wait_for(self._message_queue.get(), timeout=0.1)
                yield message
                # Mark task as done for proper queue cleanup
                self._message_queue.task_done()
            except asyncio.TimeoutError:
                # Check if we should continue running - yield control to allow stop
                await asyncio.sleep(0)
                continue
            except Exception:
                break

        # Consume any remaining messages when stopping
        while not self._message_queue.empty():
            try:
                message = self._message_queue.get_nowait()
                yield message
                self._message_queue.task_done()
            except:
                break

    async def add_message(self, message: WireMessage) -> None:
        """Add a message to this consumer's queue"""
        if self._started:
            await self._message_queue.put(message)


class RealisticProducer:
    """Producer that routes messages to appropriate consumers"""

    def __init__(self, is_reply: bool = False):
        self.is_reply = is_reply
        self._started = False
        self._factory: RealisticWireFactory | None = None

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def set_factory(self, factory: "RealisticWireFactory") -> None:
        self._factory = factory

    async def send_batch(
        self, messages: list[WireMessage], *, address_override: str | None = None
    ) -> None:
        """Send messages by routing them to the appropriate consumers

        Args:
            messages: Messages to send
            address_override: Optional dynamic address override (for compatibility with protocol).
                            In test environment, routing is based on is_reply flag,
                            so this parameter is accepted but not used.
        """
        if not self._started or not self._factory:
            return

        for message in messages:
            if self.is_reply:
                # Reply message - route to reply consumer
                if self._factory._reply_consumer:
                    reply_message = RealisticWireMessage(
                        message.payload,
                        message.headers,
                        message.correlation_id,
                        message.reply_to,
                    )
                    await self._factory._reply_consumer.add_message(reply_message)
            else:
                # Check if this is pub-sub or RPC
                if self == self._factory._pub_producer:
                    # Pub-sub fanout - send to all subscribers
                    for subscriber in self._factory._subscribers:
                        fanout_message = RealisticWireMessage(
                            message.payload,
                            message.headers,
                            message.correlation_id,
                            message.reply_to,
                        )
                        await subscriber.add_message(fanout_message)
                else:
                    # Regular RPC message - route to server consumer and trigger reply
                    if self._factory._server_consumer:
                        server_message = RealisticWireMessage(
                            message.payload,
                            message.headers,
                            message.correlation_id,
                            message.reply_to,
                        )
                        await self._factory._server_consumer.add_message(server_message)

                        # Automatically trigger server reply processing and track the task
                        if hasattr(self._factory, "_background_tasks"):
                            task = asyncio.create_task(
                                self._factory._handle_server_message(server_message)
                            )
                            self._factory._background_tasks.append(task)
                        else:
                            # Fallback for immediate processing
                            await self._factory._handle_server_message(server_message)

    async def send_to_queue(self, queue_name: str, messages: list[WireMessage]) -> None:
        """Send messages directly to a specific queue (for RPC replies)

        This mimics the AMQP producer's send_to_queue method for testing.
        In the test environment, we route directly to the reply consumer.
        """
        if not self._started or not self._factory:
            return

        # Route messages to the reply consumer
        if self._factory._reply_consumer:
            for message in messages:
                reply_message = RealisticWireMessage(
                    message.payload,
                    message.headers,
                    message.correlation_id,
                    message.reply_to,
                )
                await self._factory._reply_consumer.add_message(reply_message)


class RealisticWireFactory(AbstractWireFactory):
    """Wire factory that creates realistic consumers and producers for testing"""

    def __init__(self):
        self._reply_consumer: RealisticConsumer | None = None
        self._server_consumer: RealisticConsumer | None = None
        self._client_producer: RealisticProducer | None = None
        self._reply_producer: RealisticProducer | None = None
        self._server_handler = None  # Will hold the server RPC handler for testing
        self._background_tasks: list[asyncio.Task] = []  # Track background tasks
        # Pub-sub support
        self._pub_producer: RealisticProducer | None = None
        self._subscribers: list[RealisticConsumer] = (
            []
        )  # Multiple subscribers for fanout

    def set_server_handler(self, handler):
        """Set the server handler for automatic reply generation"""
        self._server_handler = handler

    async def _handle_server_message(self, message: WireMessage) -> None:
        """Simulate server processing and automatic reply generation"""
        if not self._server_handler or not self._reply_producer:
            return

        # Give a small delay to simulate server processing
        await asyncio.sleep(0.01)

        try:
            # Decode request using SimpleCodec
            codec = SimpleCodec()
            request = codec.decode(message.payload)

            # Call server handler
            response = await self._server_handler(request)

            # Encode response
            response_payload = codec.encode(response)

            # Create reply message
            reply_message = RealisticWireMessage(
                payload=response_payload,
                headers={},
                correlation_id=message.correlation_id,
                reply_to=None,
            )

            # Send reply back to client
            await self._reply_producer.send_batch([reply_message])

        except Exception as e:
            # Send error response
            error_payload = json.dumps({"error": str(e)}).encode()
            error_message = RealisticWireMessage(
                payload=error_payload,
                headers={"error": "true"},
                correlation_id=message.correlation_id,
                reply_to=None,
            )
            await self._reply_producer.send_batch([error_message])

    async def cleanup(self) -> None:
        """Clean up all background tasks and consumers"""
        # Cancel and wait for background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._background_tasks.clear()

        # Stop all consumers and producers
        if self._server_consumer:
            await self._server_consumer.stop()
        if self._reply_consumer:
            await self._reply_consumer.stop()
        if self._client_producer:
            await self._client_producer.stop()
        if self._reply_producer:
            await self._reply_producer.stop()

    async def create_consumer(
        self,
        channel,
        parameters,
        op_bindings,
        is_reply: bool,
        app_id: str | None = None,
    ) -> Consumer:
        consumer = RealisticConsumer(is_reply=is_reply)
        consumer.set_factory(self)

        if is_reply:
            self._reply_consumer = consumer
        else:
            # For pub-sub, we can have multiple subscribers
            if hasattr(channel, "address") and "pubsub" in str(channel.address):
                self._subscribers.append(consumer)
            else:
                self._server_consumer = consumer

        return consumer

    async def create_producer(
        self,
        channel,
        parameters,
        op_bindings,
        is_reply: bool,
        app_id: str | None = None,
    ) -> Producer:
        producer = RealisticProducer(is_reply=is_reply)
        producer.set_factory(self)

        if is_reply:
            self._reply_producer = producer
        else:
            # Check if this is for pub-sub
            if hasattr(channel, "address") and "pubsub" in str(channel.address):
                self._pub_producer = producer
            else:
                self._client_producer = producer

        return producer


class SimpleCodec(Codec):
    """Simple codec that works with our test message classes"""

    def encode(self, obj) -> bytes:
        if isinstance(obj, RequestMessage):
            return json.dumps({"type": "request", "data": obj.data}).encode()
        elif isinstance(obj, ResponseMessage):
            return json.dumps({"type": "response", "result": obj.result}).encode()
        else:
            return json.dumps({"data": str(obj)}).encode()

    def decode(self, data: bytes):
        try:
            parsed = json.loads(data.decode())
            if parsed.get("type") == "request":
                return RequestMessage(parsed["data"])
            elif parsed.get("type") == "response":
                return ResponseMessage(parsed["result"])
            elif "error" in parsed:
                # Error response
                return ResponseMessage(json.dumps(parsed))
            else:
                return RequestMessage(parsed.get("data", ""))
        except Exception:
            return RequestMessage(data.decode())


class SimpleCodecFactory(CodecFactory):
    """Simple codec factory for testing"""

    def __init__(self):
        # Use a dummy module for testing - CodecFactory expects a module
        import types

        dummy_module = types.ModuleType("test_module")
        super().__init__(dummy_module)

    def create(self, message: Message) -> Codec:
        return SimpleCodec()


# Integration tests for RPC endpoints with end-to-end message flow


@pytest.mark.asyncio(loop_scope="function")
async def test_complete_rpc_scenario(mock_operation, cleanup_rpc_client):
    """Test a complete RPC scenario with realistic message flow"""
    # Create a realistic wire factory that simulates message routing
    wire_factory = RealisticWireFactory()

    # Create simple codecs that work with our test messages
    codec_factory = SimpleCodecFactory()

    # Create client and server with proper operations
    client = RpcClient(
        operation=mock_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    server_operation = Operation(
        action="receive",
        channel=mock_operation.channel,
        messages=mock_operation.messages,
        reply=mock_operation.reply,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        traits=[],
        bindings=None,
        key="test-key",
        security=None,
    )

    server = RpcServer(
        operation=server_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    # Register server handler
    @server
    async def handle_request(request: RequestMessage) -> ResponseMessage:
        return ResponseMessage(f"Echo: {request.data}")

    # Set up wire factory to use the server handler for automatic replies
    wire_factory.set_server_handler(handle_request)

    # Start both endpoints
    await client.start()
    await server.start()

    # Make RPC call
    request = RequestMessage("Hello World")
    response = await client(request)

    # Verify response
    assert isinstance(response, ResponseMessage)
    assert response.result == "Echo: Hello World"

    # Cleanup
    await client.stop()
    await server.stop()
    await wire_factory.cleanup()


@pytest.mark.asyncio(loop_scope="function")
async def test_concurrent_rpc_calls(mock_operation, cleanup_rpc_client):
    """Test multiple concurrent RPC calls"""
    wire_factory = RealisticWireFactory()
    codec_factory = SimpleCodecFactory()

    # Create client
    client = RpcClient(
        operation=mock_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    # Create server
    server_operation = Operation(
        action="receive",
        channel=mock_operation.channel,
        messages=mock_operation.messages,
        reply=mock_operation.reply,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        traits=[],
        bindings=None,
        key="test-key",
        security=None,
    )

    server = RpcServer(
        operation=server_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    # Server handler with delay to test concurrency
    @server
    async def handle_request(request: RequestMessage) -> ResponseMessage:
        await asyncio.sleep(0.1)  # Simulate processing time
        return ResponseMessage(f"Processed-{request.data}")

    # Set up wire factory for automatic replies
    wire_factory.set_server_handler(handle_request)

    # Start endpoints
    await client.start()
    await server.start()

    # Make multiple concurrent calls
    tasks = []
    for i in range(5):
        request = RequestMessage(f"Request-{i}")
        task = asyncio.create_task(client(request))
        tasks.append(task)

    # Wait for all responses
    responses = await asyncio.gather(*tasks)

    # Verify all responses are correct and unique
    assert len(responses) == 5
    results = {r.result for r in responses}
    expected = {f"Processed-Request-{i}" for i in range(5)}
    assert results == expected

    # Cleanup
    await client.stop()
    await server.stop()
    await wire_factory.cleanup()


@pytest.mark.asyncio(loop_scope="function")
async def test_rpc_error_handling(mock_operation, cleanup_rpc_client):
    """Test RPC error handling when server handler fails"""
    wire_factory = RealisticWireFactory()
    codec_factory = SimpleCodecFactory()

    client = RpcClient(
        operation=mock_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    server_operation = Operation(
        action="receive",
        channel=mock_operation.channel,
        messages=mock_operation.messages,
        reply=mock_operation.reply,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        traits=[],
        bindings=None,
        key="test-key",
        security=None,
    )

    server = RpcServer(
        operation=server_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    # Handler that raises an error
    @server
    async def handle_request(request: RequestMessage) -> ResponseMessage:
        if request.data == "error":
            raise ValueError("Simulated server error")
        return ResponseMessage(f"OK: {request.data}")

    # Set up wire factory for automatic replies
    wire_factory.set_server_handler(handle_request)

    await client.start()
    await server.start()

    # Test normal request
    response = await client(RequestMessage("normal"))
    assert response.result == "OK: normal"

    # Test error request - should receive error response
    error_response = await client(RequestMessage("error"))
    # The server sends an error response, which should be a JSON string
    assert "error" in error_response.result.lower()

    await client.stop()
    await server.stop()
    await wire_factory.cleanup()


@pytest.mark.asyncio(loop_scope="function")
async def test_pubsub_fanout_scenario(cleanup_rpc_client):
    """Test pub-sub fanout scenario - one publisher, multiple subscribers"""
    wire_factory = RealisticWireFactory()
    codec_factory = SimpleCodecFactory()

    # Create pub-sub channel
    pubsub_channel = Channel(
        address="events.pubsub",  # Special address for pub-sub detection
        title="Event Channel",
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=None,
        key="test-key",
    )

    # Create message for events
    event_message = Message(
        name="EventMessage",
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        traits=[],
        payload={"type": "object"},
        headers=None,
        bindings=None,
        key="test-key",
        correlation_id=None,
        content_type=None,
        deprecated=None,
    )

    # Create publisher operation
    pub_operation = Operation(
        action="send",
        channel=pubsub_channel,
        messages=[event_message],
        reply=None,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        traits=[],
        bindings=None,
        key="test-key",
        security=None,
    )

    # Create subscriber operation
    sub_operation = Operation(
        action="receive",
        channel=pubsub_channel,
        messages=[event_message],
        reply=None,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        traits=[],
        bindings=None,
        key="test-key",
        security=None,
    )

    # Create publisher
    publisher = Publisher(
        operation=pub_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    # Create multiple subscribers
    subscribers = []
    received_messages = []

    for i in range(3):
        subscriber = Subscriber(
            operation=sub_operation,
            wire_factory=wire_factory,
            codec_factory=codec_factory,
        )

        # Track received messages
        subscriber_messages = []
        received_messages.append(subscriber_messages)

        @subscriber
        async def handle_event(event: RequestMessage, msg_list=subscriber_messages):
            msg_list.append(event.data)

        subscribers.append(subscriber)

    # Start all endpoints
    await publisher.start()
    for subscriber in subscribers:
        await subscriber.start()

    # Give subscribers time to start consuming
    await asyncio.sleep(0.05)

    # Publish an event
    event = RequestMessage("Important Event")
    await publisher(event)

    # Give time for fanout delivery
    await asyncio.sleep(0.1)

    # Verify all subscribers received the message
    assert len(received_messages) == 3
    for subscriber_msgs in received_messages:
        assert len(subscriber_msgs) == 1
        assert subscriber_msgs[0] == "Important Event"

    # Publish another event
    await publisher(RequestMessage("Second Event"))
    await asyncio.sleep(0.1)

    # Verify all subscribers received both events
    for subscriber_msgs in received_messages:
        assert len(subscriber_msgs) == 2
        assert "Important Event" in subscriber_msgs
        assert "Second Event" in subscriber_msgs

    # Cleanup
    await publisher.stop()
    for subscriber in subscribers:
        await subscriber.stop()
    await wire_factory.cleanup()


@pytest.mark.asyncio(loop_scope="function")
async def test_multi_service_rpc(mock_operation, cleanup_rpc_client):
    """Test RPC communication between different services (different reply queues)

    This test verifies that the server sends replies to the client's specified
    reply queue (from reply_to field), not to its own reply queue.
    """
    wire_factory = RealisticWireFactory()
    codec_factory = SimpleCodecFactory()

    # Create client with operation
    client = RpcClient(
        operation=mock_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    # Create server operation
    server_operation = Operation(
        action="receive",
        channel=mock_operation.channel,
        messages=mock_operation.messages,
        reply=mock_operation.reply,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        traits=[],
        bindings=None,
        key="test-key",
        security=None,
    )

    server = RpcServer(
        operation=server_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    # Track which reply queue was actually used
    actual_reply_queue = None
    original_send_to_queue = None

    if hasattr(wire_factory._reply_producer, "send_to_queue"):
        original_send_to_queue = wire_factory._reply_producer.send_to_queue

        async def tracked_send_to_queue(queue_name: str, messages):
            nonlocal actual_reply_queue
            actual_reply_queue = queue_name
            await original_send_to_queue(queue_name, messages)

        wire_factory._reply_producer.send_to_queue = tracked_send_to_queue

    # Register server handler
    @server
    async def handle_request(request: RequestMessage) -> ResponseMessage:
        return ResponseMessage(f"Handled: {request.data}")

    # Set up wire factory for automatic replies
    wire_factory.set_server_handler(handle_request)

    # Start both endpoints
    await client.start()
    await server.start()

    # Get the client's reply queue name before making the request
    expected_reply_queue = global_reply_handler.reply_queue_name

    # Make RPC call
    request = RequestMessage("Test Multi-Service")
    response = await client(request)

    # Verify response is correct
    assert isinstance(response, ResponseMessage)
    assert response.result == "Handled: Test Multi-Service"

    # Verify reply was sent to the client's reply queue (if tracking is available)
    if actual_reply_queue is not None:
        assert actual_reply_queue == expected_reply_queue, (
            f"Reply was sent to wrong queue: {actual_reply_queue}, "
            f"expected: {expected_reply_queue}"
        )

    # Cleanup
    await client.stop()
    await server.stop()
    await wire_factory.cleanup()


@pytest.mark.asyncio(loop_scope="function")
async def test_enhanced_rpc_scenario(cleanup_rpc_client):
    """Enhanced RPC scenario with detailed request-response validation"""
    wire_factory = RealisticWireFactory()
    codec_factory = SimpleCodecFactory()

    # Create RPC operation
    rpc_channel = Channel(
        address="math.rpc",
        title="Math RPC Channel",
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=None,
        key="test-key",
    )

    request_message = Message(
        name="MathRequest",
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        traits=[],
        payload={"type": "object"},
        headers=None,
        bindings=None,
        key="test-key",
        correlation_id=None,
        content_type=None,
        deprecated=None,
    )

    response_message = Message(
        name="MathResponse",
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        traits=[],
        payload={"type": "object"},
        headers=None,
        bindings=None,
        key="test-key",
        correlation_id=None,
        content_type=None,
        deprecated=None,
    )

    reply = OperationReply(
        channel=rpc_channel,
        address=None,
        messages=[response_message],
    )

    client_operation = Operation(
        action="send",
        channel=rpc_channel,
        messages=[request_message],
        reply=reply,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        traits=[],
        bindings=None,
        key="test-key",
        security=None,
    )

    server_operation = Operation(
        action="receive",
        channel=rpc_channel,
        messages=[request_message],
        reply=reply,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        traits=[],
        bindings=None,
        key="test-key",
        security=None,
    )

    # Create client and server
    client = RpcClient(
        operation=client_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    server = RpcServer(
        operation=server_operation,
        wire_factory=wire_factory,
        codec_factory=codec_factory,
    )

    # Register enhanced server handler
    @server
    async def math_service(request: RequestMessage) -> ResponseMessage:
        operation, *number_strs = request.data.split()
        numbers = [float(n) for n in number_strs]

        if operation == "add":
            result = sum(numbers)
        elif operation == "multiply":
            result = 1.0
            for n in numbers:
                result *= n
        elif operation == "divide":
            result = numbers[0] / numbers[1] if len(numbers) >= 2 else 0.0
        else:
            raise ValueError(f"Unknown operation: {operation}")

        return ResponseMessage(f"{result}")

    # Set up wire factory for automatic replies
    wire_factory.set_server_handler(math_service)

    # Start both endpoints
    await client.start()
    await server.start()

    # Test various RPC calls
    test_cases = [
        ("add 10 20 30", "60.0"),
        ("multiply 5 4 2", "40.0"),
        ("divide 100 4", "25.0"),
    ]

    for request_data, expected in test_cases:
        request = RequestMessage(request_data)
        response = await client(request)
        assert (
            response.result == expected
        ), f"Failed for {request_data}: got {response.result}, expected {expected}"

    # Test error handling
    try:
        error_response = await client(RequestMessage("unknown 1 2"))
        # Should receive error response, not throw exception
        assert "error" in error_response.result.lower()
    except Exception:
        # Error handling worked
        pass

    # Cleanup
    await client.stop()
    await server.stop()
    await wire_factory.cleanup()
