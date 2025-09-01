import json
import pytest
from pydantic import BaseModel, ValidationError

from asyncapi_python.contrib.codec.json import JsonCodec, JsonCodecFactory
from asyncapi_python.kernel.document.message import Message

# Test models for codec tests
class UserModel(BaseModel):
    name: str
    age: int
    email: str

class OrderModel(BaseModel):
    id: str
    amount: float
    user_id: str


# Fixtures
@pytest.fixture
def user_codec() -> JsonCodec:
    return JsonCodec(UserModel)

@pytest.fixture
def order_codec() -> JsonCodec:
    return JsonCodec(OrderModel)

@pytest.fixture
def sample_user() -> UserModel:
    return UserModel(name="John Doe", age=30, email="john@example.com")

@pytest.fixture
def sample_order() -> OrderModel:
    return OrderModel(id="order-123", amount=99.99, user_id="user-456")


# JsonCodec tests
def test_encode_valid_model(user_codec: JsonCodec, sample_user: UserModel) -> None:
    """Test encoding a valid Pydantic model to JSON bytes"""
    result = user_codec.encode(sample_user)
    
    assert isinstance(result, bytes)
    decoded_json = json.loads(result.decode('utf-8'))
    assert decoded_json == {"name": "John Doe", "age": 30, "email": "john@example.com"}

def test_decode_valid_json_bytes(user_codec: JsonCodec) -> None:
    """Test decoding valid JSON bytes to Pydantic model"""
    sample_data = {"name": "John Doe", "age": 30, "email": "john@example.com"}
    json_bytes = json.dumps(sample_data).encode('utf-8')
    result = user_codec.decode(json_bytes)
    
    assert isinstance(result, UserModel)
    assert result.name == "John Doe"
    assert result.age == 30
    assert result.email == "john@example.com"

def test_round_trip_encoding(user_codec: JsonCodec, sample_user: UserModel) -> None:
    """Test that encode -> decode produces the same data"""
    encoded = user_codec.encode(sample_user)
    decoded = user_codec.decode(encoded)
    
    assert decoded == sample_user

def test_decode_invalid_json(user_codec: JsonCodec) -> None:
    """Test decoding invalid JSON bytes raises ValueError"""
    invalid_json = b"{'invalid': json}"
    
    with pytest.raises(ValueError, match="Failed to decode JSON payload"):
        user_codec.decode(invalid_json)

def test_decode_invalid_utf8(user_codec: JsonCodec) -> None:
    """Test decoding invalid UTF-8 bytes raises ValueError"""
    invalid_utf8 = b'\xff\xfe invalid utf-8'
    
    with pytest.raises(ValueError, match="Failed to decode JSON payload"):
        user_codec.decode(invalid_utf8)

def test_decode_validation_error(user_codec: JsonCodec) -> None:
    """Test decoding JSON that fails Pydantic validation raises ValueError"""
    invalid_data = json.dumps({"name": "John", "age": "not-a-number"}).encode('utf-8')
    
    with pytest.raises(ValueError, match="Failed to decode JSON payload"):
        user_codec.decode(invalid_data)

def test_decode_missing_required_fields(user_codec: JsonCodec) -> None:
    """Test decoding JSON missing required fields raises ValueError"""
    incomplete_data = json.dumps({"name": "John"}).encode('utf-8')
    
    with pytest.raises(ValueError, match="Failed to decode JSON payload"):
        user_codec.decode(incomplete_data)

def test_different_model_types(order_codec: JsonCodec, sample_order: OrderModel) -> None:
    """Test codec works with different model types"""
    encoded = order_codec.encode(sample_order)
    decoded = order_codec.decode(encoded)
    
    assert decoded == sample_order
    assert decoded.id == "order-123"
    assert decoded.amount == 99.99


# JsonCodecFactory tests
def test_create_codec_for_message(json_codec_factory: JsonCodecFactory, mock_user_message: Message) -> None:
    """Test creating codec for a message"""
    codec = json_codec_factory.create(mock_user_message)
    
    assert isinstance(codec, JsonCodec)
    # Note: We can't easily test _model_class without complex mocking
    # so we'll test the codec functionality instead
    
def test_create_codec_for_different_message(json_codec_factory: JsonCodecFactory, mock_order_message: Message) -> None:
    """Test creating codec for different message type"""
    codec = json_codec_factory.create(mock_order_message)
    
    assert isinstance(codec, JsonCodec)

def test_codec_caching(json_codec_factory: JsonCodecFactory, mock_user_message: Message) -> None:
    """Test that codecs are cached and reused"""
    codec1 = json_codec_factory.create(mock_user_message)
    codec2 = json_codec_factory.create(mock_user_message)
    
    assert codec1 is codec2  # Same instance due to caching

def test_create_codec_no_payload(json_codec_factory: JsonCodecFactory) -> None:
    """Test creating codec for message without payload raises ValueError"""
    from asyncapi_python.kernel.document.message import Message
    
    message_no_payload = Message(
        name="test.message",
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        payload=None,  # No payload
        content_type="application/json",
        headers=None,
        deprecated=None,
        correlation_id=None,
        bindings=None,
        traits=[]
    )
    
    with pytest.raises(ValueError, match="Message payload is required for JSON codec"):
        json_codec_factory.create(message_no_payload)

def test_create_codec_no_name(json_codec_factory: JsonCodecFactory) -> None:
    """Test creating codec for message without name raises ValueError"""
    from asyncapi_python.kernel.document.message import Message
    
    message_no_name = Message(
        name=None,  # No name
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        payload={"type": "object"},
        content_type="application/json",
        headers=None,
        deprecated=None,
        correlation_id=None,
        bindings=None,
        traits=[]
    )
    
    with pytest.raises(ValueError, match="Message name is required to resolve model class"):
        json_codec_factory.create(message_no_name)

def test_create_codec_unknown_message_name(json_codec_factory: JsonCodecFactory) -> None:
    """Test creating codec for unknown message name raises ValueError"""
    from asyncapi_python.kernel.document.message import Message
    
    unknown_message = Message(
        name="unknown.message",  # Not in mock module
        title=None,
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        payload={"type": "object"},
        content_type="application/json",
        headers=None,
        deprecated=None,
        correlation_id=None,
        bindings=None,
        traits=[]
    )
    
    with pytest.raises(ValueError, match="Model class UnknownMessage not found"):
        json_codec_factory.create(unknown_message)

def test_to_class_name_conversion(json_codec_factory: JsonCodecFactory) -> None:
    """Test message name to class name conversion"""
    # Test the private method indirectly through various message names
    test_cases = [
        ("user.created", "UserCreated"),
        ("order.placed", "OrderPlaced"), 
        ("user-updated", "UserUpdated"),
        ("system_status", "SystemStatus"),
        ("simple", "Simple")
    ]
    
    for message_name, expected_class_name in test_cases:
        result = json_codec_factory._to_class_name(message_name)
        assert result == expected_class_name

def test_cross_factory_caching(mock_module: object, mock_user_message: Message) -> None:
    """Test that codec registry is shared across factory instances"""
    factory1 = JsonCodecFactory(mock_module)
    factory2 = JsonCodecFactory(mock_module)
    
    codec1 = factory1.create(mock_user_message)
    codec2 = factory2.create(mock_user_message)
    
    assert codec1 is codec2  # Shared registry