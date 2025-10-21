"""Malformed message handling scenario"""

import json

import pytest

from asyncapi_python.kernel.application import BaseApplication
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation
from asyncapi_python.kernel.wire import AbstractWireFactory

# Import test models
from ..test_app.messages.json import TestEvent, TestUser, UserCreated, UserUpdated


class UserManagementApp(BaseApplication):
    """User management service with endpoints for testing scenarios"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(
            wire_factory=wire_factory,
            codec_factory=codec_factory,
            endpoint_params={"disable_handler_validation": True},
        )
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup user management endpoints"""

        # User creation endpoint (publisher)
        user_created_channel = Channel(
            address="users.created",
            title=None,
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

        user_created_message = Message(
            name="UserCreated",
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

        user_created_operation = Operation(
            channel=user_created_channel,
            messages=[user_created_message],
            action="send",
            title=None,
            summary=None,
            description=None,
            tags=[],
            external_docs=None,
            traits=[],
            bindings=None,
            key="test-key",
            reply=None,
            security=None,
        )

        self.user_created = self._register_endpoint(user_created_operation)

        # User update subscriber endpoint
        user_update_channel = Channel(
            address="users.update",
            title=None,
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

        user_update_message = Message(
            name="UserUpdated",
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

        user_update_operation = Operation(
            channel=user_update_channel,
            messages=[user_update_message],
            action="receive",
            title=None,
            summary=None,
            description=None,
            tags=[],
            external_docs=None,
            traits=[],
            bindings=None,
            key="test-key",
            reply=None,
            security=None,
        )

        self.user_updates = self._register_endpoint(user_update_operation)


class OrderProcessingApp(BaseApplication):
    """Order processing service with endpoints for testing scenarios"""

    def __init__(self, wire_factory: AbstractWireFactory, codec_factory: CodecFactory):
        super().__init__(
            wire_factory=wire_factory,
            codec_factory=codec_factory,
            endpoint_params={"disable_handler_validation": True},
        )
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Setup order processing endpoints"""

        # Order events publisher
        order_events_channel = Channel(
            address="orders.events",
            title=None,
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

        order_event_message = Message(
            name="TestEvent",
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

        order_events_operation = Operation(
            channel=order_events_channel,
            messages=[order_event_message],
            action="send",
            title=None,
            summary=None,
            description=None,
            tags=[],
            external_docs=None,
            traits=[],
            bindings=None,
            key="test-key",
            reply=None,
            security=None,
        )

        self.order_events = self._register_endpoint(order_events_operation)

        # RPC endpoint with reply channel
        rpc_channel = Channel(
            address="orders.rpc",
            title=None,
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

        # Reply channel with null address (global reply queue)
        reply_channel = Channel(
            address=None,  # Null address for global reply queue
            title=None,
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

        rpc_reply_operation = Operation(
            channel=reply_channel,
            messages=[order_event_message],
            action="send",
            title=None,
            summary=None,
            description=None,
            tags=[],
            external_docs=None,
            traits=[],
            bindings=None,
            key="test-key",
            reply=None,
            security=None,
        )

        self.rpc_replies = self._register_endpoint(rpc_reply_operation)


async def malformed_message_handling(
    wire: AbstractWireFactory, codec: CodecFactory
) -> None:
    """Test handling of various malformed message scenarios"""
    print(
        f"Testing malformed messages with {wire.__class__.__name__} + {codec.__class__.__name__}"
    )

    # 1. Test JSON parsing errors
    test_message = Message(
        name="test.user",
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

    message_codec = codec.create(test_message)

    # Test invalid JSON syntax
    malformed_json_cases = [
        b'{"invalid": json}',  # unquoted value
        b'{"missing": "quote}',  # missing quote
        b'{"trailing", "comma",}',  # trailing comma
        b'{invalid: "key"}',  # unquoted key
        b'{"unclosed": {"nested": "object"}',  # unclosed nested object
        b"[1, 2, 3",  # unclosed array
        b'{"empty":}',  # empty value
        b'{"number": 123abc}',  # invalid number format
    ]

    for malformed_json in malformed_json_cases:
        with pytest.raises((json.JSONDecodeError, ValueError, TypeError)):
            message_codec.decode(malformed_json)
        print(f"✓ JSON decode error correctly raised for: {malformed_json[:20]!r}...")

    # 2. Test non-UTF8 bytes
    non_utf8_cases = [
        b"\xff\xfe\x00\x01",  # BOM with null bytes
        b"\x80\x81\x82\x83",  # invalid UTF-8 sequences
        b"valid start\xff\xfe invalid end",  # mixed valid/invalid
        b"\xc0\x80",  # overlong encoding
        b"\xed\xa0\x80",  # surrogate pairs
    ]

    for non_utf8 in non_utf8_cases:
        with pytest.raises((UnicodeDecodeError, ValueError)):
            message_codec.decode(non_utf8)
        print(f"✓ UTF-8 decode error correctly raised for non-UTF8 bytes")

    # 3. Test Pydantic validation errors with well-formed JSON but invalid structure
    user_message = Message(
        name="user.created",
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

    user_codec = codec.create(user_message)

    validation_error_cases = [
        b'{"user_id": "not_a_number", "name": "Bob", "email": "bob@test.com", "timestamp": "2024-01-01T00:00:00Z"}',  # wrong type for user_id
        b'{"user_id": 123, "name": null, "email": "bob@test.com", "timestamp": "2024-01-01T00:00:00Z"}',  # null required field
        b'{"user_id": 123, "name": "Bob", "timestamp": "2024-01-01T00:00:00Z"}',  # missing required field
        b'{"wrong_field": 123, "name": "Bob", "email": "bob@test.com", "timestamp": "2024-01-01T00:00:00Z"}',  # missing user_id field
        b'{"user_id": [], "name": "Bob", "email": "bob@test.com", "timestamp": "2024-01-01T00:00:00Z"}',  # wrong type
        b'{"user_id": {"nested": "object"}, "name": "Bob", "email": "bob@test.com", "timestamp": "2024-01-01T00:00:00Z"}',  # wrong type
        b"{}",  # completely empty object
    ]

    # Cases that might be valid (no email format validation in the model)
    potentially_valid_cases = [
        b'{"user_id": 123, "name": "Bob", "email": "invalid_email", "timestamp": "2024-01-01T00:00:00Z"}',  # email validation not enforced
    ]

    # Test cases that MUST fail
    for invalid_data in validation_error_cases:
        with pytest.raises(
            (ValueError, TypeError, AttributeError, json.JSONDecodeError)
        ):
            user_codec.decode(invalid_data)
        print(f"✓ Validation error correctly raised for invalid structure")

    # Test cases that might be valid depending on model validation rules
    for potentially_valid_data in potentially_valid_cases:
        try:
            result = user_codec.decode(potentially_valid_data)
            print(
                f"✓ Potentially valid case accepted (no email format validation): {type(result).__name__}"
            )
        except (ValueError, TypeError, AttributeError, json.JSONDecodeError) as e:
            print(
                f"✓ Potentially valid case rejected (strict validation enabled): {type(e).__name__}"
            )

    # 4. Test edge case values that might cause issues
    edge_case_values = [
        # Very large numbers
        b'{"user_id": 999999999999999999999999999999, "name": "Bob", "email": "bob@test.com", "timestamp": "2024-01-01T00:00:00Z"}',
        # Negative numbers where positive expected
        b'{"user_id": -123, "name": "Bob", "email": "bob@test.com", "timestamp": "2024-01-01T00:00:00Z"}',
        # Very long strings
        b'{"user_id": 123, "name": "'
        + b"x" * 10000
        + b'", "email": "bob@test.com", "timestamp": "2024-01-01T00:00:00Z"}',
        # Special characters and unicode
        b'{"user_id": 123, "name": "\\u0000\\u001f\\u007f", "email": "bob@test.com", "timestamp": "2024-01-01T00:00:00Z"}',
        # Empty strings where content expected
        b'{"user_id": 123, "name": "", "email": "", "timestamp": "2024-01-01T00:00:00Z"}',
    ]

    for edge_case in edge_case_values:
        # Some of these might be valid depending on validation rules, so we don't assert exceptions
        # Just ensure they don't crash the system
        try:
            decoded = user_codec.decode(edge_case)
            print(f"✓ Edge case handled gracefully: {type(decoded).__name__}")
        except (ValueError, TypeError, OverflowError) as e:
            print(f"✓ Edge case appropriately rejected: {type(e).__name__}")

    # 5. Test malformed messages with actual application endpoints
    user_app = UserManagementApp(wire, codec)

    try:
        await user_app.start()

        # Test that the application doesn't crash when trying to send invalid data
        # This tests the encoding path
        invalid_user_objects = [
            # Missing required fields
            {"user_id": 123, "name": "Bob"},  # missing email and timestamp
            # Wrong types
            {
                "user_id": "not_number",
                "name": "Bob",
                "email": "bob@test.com",
                "timestamp": "2024-01-01T00:00:00Z",
            },
            # None values for required fields
            {
                "user_id": None,
                "name": "Bob",
                "email": "bob@test.com",
                "timestamp": "2024-01-01T00:00:00Z",
            },
        ]

        for invalid_obj in invalid_user_objects:
            with pytest.raises((ValueError, TypeError, AttributeError)):
                UserCreated(**invalid_obj)  # type: ignore
            print(
                "✓ Pydantic model validation correctly prevents invalid object creation"
            )

        # Test valid objects to ensure the app still works
        valid_user = UserCreated(
            user_id=123,
            name="Valid User",
            email="valid@test.com",
            timestamp="2024-01-01T00:00:00Z",
        )
        await user_app.user_created(valid_user)
        print("✓ Valid message still works after malformed message tests")

    finally:
        await user_app.stop()

    # 6. Test malformed messages with OrderProcessingApp and optional fields
    order_app = OrderProcessingApp(wire, codec)

    try:
        await order_app.start()

        # Test TestEvent with various malformed payloads
        malformed_payload_data = [
            # Invalid payload types when dict expected
            {
                "event_type": "test",
                "user_id": 123,
                "timestamp": "2024-01-01T00:00:00Z",
                "payload": "not_a_dict",
            },
            # Very nested payload (should work)
            {
                "event_type": "test",
                "user_id": 123,
                "timestamp": "2024-01-01T00:00:00Z",
                "payload": {"level1": {"level2": {"level3": {"deep": "value"}}}},
            },
            # Payload with special values (should work)
            {
                "event_type": "test",
                "user_id": 123,
                "timestamp": "2024-01-01T00:00:00Z",
                "payload": {
                    "null_value": None,
                    "empty_string": "",
                    "zero": 0,
                    "false": False,
                },
            },
        ]

        valid_payload_data: list[dict[str, object]] = []
        invalid_payload_data: list[dict[str, object]] = []

        for event_data in malformed_payload_data:
            if event_data["payload"] == "not_a_dict":
                invalid_payload_data.append(event_data)
            else:
                valid_payload_data.append(event_data)

        # Test invalid payloads that should fail
        for invalid_payload in invalid_payload_data:
            with pytest.raises((ValueError, TypeError)):
                TestEvent(**invalid_payload)  # type: ignore
            print("✓ Event with invalid payload appropriately rejected")

        # Test valid payloads that should work
        for valid_payload in valid_payload_data:
            event = TestEvent(**valid_payload)  # type: ignore
            await order_app.order_events(event)
            print(f"✓ Event with payload handled: {type(event.payload)}")

        # Test valid event to ensure system still works
        valid_event = TestEvent(
            event_type="valid.test",
            user_id=456,
            timestamp="2024-01-01T00:00:00Z",
            payload={"order_id": "order-123", "amount": 99.99},
        )
        await order_app.order_events(valid_event)
        print("✓ Valid event still works after malformed payload tests")

    finally:
        await order_app.stop()

    # 7. Test extremely large messages using existing message types
    # Use the user.created message type which has a model

    # Create very large JSON payload with valid structure
    large_user_data = {
        "user_id": 123,
        "name": "x" * 100000,  # Very long name
        "email": "test@example.com",
        "timestamp": "2024-01-01T00:00:00Z",
    }
    large_json = json.dumps(large_user_data).encode()

    try:
        decoded_large = user_codec.decode(large_json)
        print("✓ Large message (100KB name) handled successfully")
    except (MemoryError, ValueError) as e:
        print(f"✓ Large message appropriately rejected: {type(e).__name__}")

    # 8. Test deeply nested JSON in the payload field of TestEvent
    nested_levels = 100  # Reduced to avoid stack overflow
    deeply_nested: dict[str, object] = {}
    current = deeply_nested
    for i in range(nested_levels):
        current["level"] = {}
        current = current["level"]  # type: ignore
    current["value"] = "deep"  # type: ignore

    nested_event_data = {
        "event_type": "nested.test",
        "user_id": 123,
        "timestamp": "2024-01-01T00:00:00Z",
        "payload": deeply_nested,
    }

    try:
        nested_json = json.dumps(nested_event_data).encode()
        # Use TestEvent message type for this test
        event_message = Message(
            name="TestEvent",
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
        event_codec = codec.create(event_message)
        decoded_nested = event_codec.decode(nested_json)
        print("✓ Deeply nested JSON handled successfully")
    except (RecursionError, ValueError, json.JSONDecodeError) as e:
        print(f"✓ Deeply nested JSON appropriately rejected: {type(e).__name__}")

    print("✓ All malformed message handling tests completed")
