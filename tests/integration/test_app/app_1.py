"""App 1 - User Management Service

Contains endpoints for user-related operations used in integration scenarios.
"""

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.wire import AbstractWireFactory
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation

from .messages.json import TestUser, UserCreated, UserUpdated


class UserManagementApp(BaseApplication):
    """User management service with endpoints for testing scenarios"""
    
    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(wire_factory, codec_factory)
        self._setup_endpoints()
    
    def _setup_endpoints(self):
        """Setup user management endpoints"""
        
        # User creation endpoint (publisher)
        user_created_channel = Channel(
            address="users.created",
            title=None, summary=None, description=None,
            servers=[], messages={}, parameters={},
            tags=[], external_docs=None, bindings=None
        )
        
        user_created_message = Message(
            name="UserCreated",
            title=None, summary=None, description=None,
            tags=[], externalDocs=None, traits=[],
            payload={"type": "object"}, headers=None,
            bindings=None, correlation_id=None,
            content_type=None, deprecated=None
        )
        
        user_created_operation = Operation(
            channel=user_created_channel,
            messages=[user_created_message],
            action="send",
            title=None, summary=None, description=None,
            tags=[], external_docs=None, traits=[],
            bindings=None, reply=None, security=None
        )
        
        self.user_created = self._register_endpoint(user_created_operation)
        
        # User update subscriber endpoint
        user_update_channel = Channel(
            address="users.update",
            title=None, summary=None, description=None,
            servers=[], messages={}, parameters={},
            tags=[], external_docs=None, bindings=None
        )
        
        user_update_message = Message(
            name="UserUpdated", 
            title=None, summary=None, description=None,
            tags=[], externalDocs=None, traits=[],
            payload={"type": "object"}, headers=None,
            bindings=None, correlation_id=None,
            content_type=None, deprecated=None
        )
        
        user_update_operation = Operation(
            channel=user_update_channel,
            messages=[user_update_message],
            action="receive",
            title=None, summary=None, description=None,
            tags=[], external_docs=None, traits=[],
            bindings=None, reply=None, security=None
        )
        
        self.user_updates = self._register_endpoint(user_update_operation)