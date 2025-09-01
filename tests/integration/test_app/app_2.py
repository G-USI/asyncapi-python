"""App 2 - Order Processing Service

Contains endpoints for order-related operations used in integration scenarios.
"""

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.wire import AbstractWireFactory
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation

from .messages.json import TestEvent


class OrderProcessingApp(BaseApplication):
    """Order processing service with endpoints for testing scenarios"""
    
    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory, codec_factory)
        self._setup_endpoints()
    
    def _setup_endpoints(self):
        """Setup order processing endpoints"""
        
        # Order events publisher
        order_events_channel = Channel(
            address="orders.events",
            title=None, summary=None, description=None,
            servers=[], messages={}, parameters={},
            tags=[], external_docs=None, bindings=None
        )
        
        order_event_message = Message(
            name="TestEvent",
            title=None, summary=None, description=None,
            tags=[], externalDocs=None, traits=[],
            payload={"type": "object"}, headers=None,
            bindings=None, correlation_id=None,
            content_type=None, deprecated=None
        )
        
        order_events_operation = Operation(
            channel=order_events_channel,
            messages=[order_event_message],
            action="send",
            title=None, summary=None, description=None,
            tags=[], external_docs=None, traits=[],
            bindings=None, reply=None, security=None
        )
        
        self.order_events = self._register_endpoint(order_events_operation)
        
        # RPC endpoint with reply channel
        rpc_channel = Channel(
            address="orders.rpc",
            title=None, summary=None, description=None,
            servers=[], messages={}, parameters={},
            tags=[], external_docs=None, bindings=None
        )
        
        # Reply channel with null address (global reply queue)
        reply_channel = Channel(
            address=None,  # Null address for global reply queue
            title=None, summary=None, description=None,
            servers=[], messages={}, parameters={},
            tags=[], external_docs=None, bindings=None
        )
        
        rpc_reply_operation = Operation(
            channel=reply_channel,
            messages=[order_event_message],
            action="send",
            title=None, summary=None, description=None,
            tags=[], external_docs=None, traits=[],
            bindings=None, reply=None, security=None
        )
        
        self.rpc_replies = self._register_endpoint(rpc_reply_operation)