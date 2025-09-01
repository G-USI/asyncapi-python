"""Error handling scenario"""

import pytest
from asyncapi_python.kernel.wire import AbstractWireFactory
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.kernel.document.message import Message

# Import test models
import sys
from pathlib import Path
test_app_path = Path(__file__).parent.parent / "test_app"
sys.path.insert(0, str(test_app_path.parent))
import test_app.messages.json as test_models


async def error_handling(wire: AbstractWireFactory, codec: CodecFactory) -> None:
    """Test codec error handling"""
    print(f"Testing error handling with {wire.__class__.__name__} + {codec.__class__.__name__}")
    
    # 1. Create test message specification
    test_message = Message(
        name="test.user",  # Maps to TestUser class via _to_class_name conversion
        title=None, summary=None, description=None,
        tags=[], externalDocs=None, traits=[],
        payload={"type": "object"}, headers=None,
        bindings=None, correlation_id=None,
        content_type=None, deprecated=None
    )
    
    # 2. Create codec instance
    message_codec = codec.create(test_message)
    
    # 3. Test invalid decode with malformed JSON
    with pytest.raises((ValueError, Exception)):
        message_codec.decode(b"invalid json data")
    print("✓ Invalid JSON decode raises exception correctly")
    
    # 4. Test decode with valid JSON but wrong structure
    with pytest.raises((ValueError, Exception)):
        message_codec.decode(b'{"wrong": "structure", "missing": "required fields"}')
    print("✓ Invalid structure decode raises exception correctly")
    
    # 5. Test decode with non-UTF8 bytes
    with pytest.raises((ValueError, Exception)):
        message_codec.decode(b'\xff\xfe\x00\x01invalid bytes')
    print("✓ Invalid UTF-8 decode raises exception correctly")
    
    # 6. Test successful encode/decode with valid data
    test_user = test_models.TestUser(id=42, name="Bob", email="bob@test.com")
    
    # Encode should work
    encoded = message_codec.encode(test_user)
    assert isinstance(encoded, bytes)
    print("✓ Valid data encode successful")
    
    # Decode should work
    decoded = message_codec.decode(encoded)
    assert decoded.id == test_user.id
    assert decoded.name == test_user.name
    assert decoded.email == test_user.email
    print("✓ Valid data decode successful")
    
    # 7. Test encoding edge cases
    edge_case_user = test_models.TestUser(
        id=0,  # Edge case: zero ID
        name="",  # Edge case: empty string
        email="special+chars@example-domain.co.uk"  # Edge case: special chars
    )
    
    encoded_edge = message_codec.encode(edge_case_user)
    decoded_edge = message_codec.decode(encoded_edge)
    assert decoded_edge.id == 0
    assert decoded_edge.name == ""
    assert decoded_edge.email == "special+chars@example-domain.co.uk"
    print("✓ Edge case encoding/decoding successful")
    
    print("✓ All error handling tests passed")