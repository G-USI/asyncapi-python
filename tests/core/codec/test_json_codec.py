"""Tests for JSON codec extract_field() method with RootModel support"""

from enum import Enum

import pytest
from pydantic import BaseModel, RootModel

from asyncapi_python.contrib.codec.json import JsonCodec


# Test models
class SimpleMessage(BaseModel):
    """Regular BaseModel for testing"""

    chat_id: int
    message: str


class NestedUser(BaseModel):
    """Nested model for path traversal testing"""

    id: str
    name: str


class MessageWithNested(BaseModel):
    """Model with nested fields"""

    user: NestedUser
    content: str


class Severity(str, Enum):
    """Enum for testing enum extraction"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MessageWithEnum(BaseModel):
    """Model with enum field"""

    severity: Severity
    description: str


class ComplexData(BaseModel):
    """Complex nested data"""

    items: list[str]
    metadata: dict[str, str]


class MessageWithComplex(BaseModel):
    """Model with complex types"""

    data: ComplexData


# RootModel wrappers
class SimpleRootModel(RootModel[SimpleMessage]):
    """Single-level RootModel wrapper"""

    root: SimpleMessage


class InnerRootModel(RootModel[NestedUser]):
    """Inner RootModel for nested testing"""

    root: NestedUser


class OuterMessageWithRootModel(BaseModel):
    """Message containing a RootModel field"""

    user: InnerRootModel
    content: str


class DoubleRootModel(RootModel[SimpleRootModel]):
    """Nested RootModel (RootModel containing RootModel)"""

    root: SimpleRootModel


# Tests
def test_extract_field_from_base_model():
    """Test extracting fields from regular BaseModel"""
    codec = JsonCodec(SimpleMessage)
    message = SimpleMessage(chat_id=123, message="hello")

    result = codec.extract_field(message, "$message.payload#/chat_id")
    assert result == "123"

    result = codec.extract_field(message, "$message.payload#/message")
    assert result == "hello"


def test_extract_field_from_root_model():
    """Test extracting fields from single-level RootModel wrapper"""
    codec = JsonCodec(SimpleRootModel)
    wrapped = SimpleRootModel.model_validate({"chat_id": 456, "message": "world"})

    # Should unwrap RootModel and access fields on the root
    result = codec.extract_field(wrapped, "$message.payload#/chat_id")
    assert result == "456"

    result = codec.extract_field(wrapped, "$message.payload#/message")
    assert result == "world"


def test_extract_field_from_nested_root_model():
    """Test extracting fields from nested RootModel (RootModel containing RootModel)"""
    codec = JsonCodec(DoubleRootModel)

    # Create nested RootModel: DoubleRootModel -> SimpleRootModel -> SimpleMessage
    inner = SimpleRootModel.model_validate({"chat_id": 789, "message": "nested"})
    wrapped = DoubleRootModel.model_validate(inner.model_dump())

    # Should recursively unwrap both RootModel layers
    result = codec.extract_field(wrapped, "$message.payload#/chat_id")
    assert result == "789"

    result = codec.extract_field(wrapped, "$message.payload#/message")
    assert result == "nested"


def test_extract_field_nested_path():
    """Test extracting nested fields using path like $message.payload#/user/id"""
    codec = JsonCodec(MessageWithNested)
    message = MessageWithNested(
        user=NestedUser(id="user123", name="Alice"), content="test"
    )

    result = codec.extract_field(message, "$message.payload#/user/id")
    assert result == "user123"

    result = codec.extract_field(message, "$message.payload#/user/name")
    assert result == "Alice"


def test_extract_field_nested_path_with_root_model():
    """Test extracting nested fields when intermediate field is a RootModel"""
    codec = JsonCodec(OuterMessageWithRootModel)

    # The user field is a RootModel wrapper
    user_wrapped = InnerRootModel.model_validate({"id": "user456", "name": "Bob"})
    message = OuterMessageWithRootModel(user=user_wrapped, content="test")

    # Should unwrap the RootModel at the intermediate step
    result = codec.extract_field(message, "$message.payload#/user/id")
    assert result == "user456"

    result = codec.extract_field(message, "$message.payload#/user/name")
    assert result == "Bob"


def test_extract_field_enum_value():
    """Test extracting enum values (should return the enum value, not the enum object)"""
    codec = JsonCodec(MessageWithEnum)
    message = MessageWithEnum(severity=Severity.HIGH, description="critical alert")

    result = codec.extract_field(message, "$message.payload#/severity")
    assert result == "high"  # Should extract the value, not "Severity.HIGH"


def test_extract_field_complex_type():
    """Test extracting complex types (should JSON serialize)"""
    codec = JsonCodec(MessageWithComplex)
    message = MessageWithComplex(
        data=ComplexData(items=["a", "b", "c"], metadata={"key": "value"})
    )

    result = codec.extract_field(message, "$message.payload#/data")
    # Should be JSON serialized
    assert '"items": ["a", "b", "c"]' in result
    assert '"metadata": {"key": "value"}' in result


def test_extract_field_invalid_location():
    """Test error handling for invalid location format"""
    codec = JsonCodec(SimpleMessage)
    message = SimpleMessage(chat_id=123, message="hello")

    with pytest.raises(ValueError, match="Invalid location format"):
        codec.extract_field(message, "invalid/location")

    with pytest.raises(ValueError, match="Invalid location format"):
        codec.extract_field(message, "#/chat_id")


def test_extract_field_missing_path():
    """Test error handling for non-existent paths"""
    codec = JsonCodec(SimpleMessage)
    message = SimpleMessage(chat_id=123, message="hello")

    with pytest.raises(ValueError, match="Path 'nonexistent' not found in payload"):
        codec.extract_field(message, "$message.payload#/nonexistent")


def test_extract_field_missing_nested_path():
    """Test error handling for non-existent nested paths"""
    codec = JsonCodec(MessageWithNested)
    message = MessageWithNested(
        user=NestedUser(id="user123", name="Alice"), content="test"
    )

    with pytest.raises(
        ValueError, match="Path 'user/nonexistent' not found in payload"
    ):
        codec.extract_field(message, "$message.payload#/user/nonexistent")


def test_extract_field_primitive_types() -> None:
    """Test extraction returns proper string representations of primitive types"""

    class PrimitiveMessage(BaseModel):
        str_field: str
        int_field: int
        float_field: float
        bool_field: bool

    codec = JsonCodec(PrimitiveMessage)
    message = PrimitiveMessage(
        str_field="test", int_field=42, float_field=3.14, bool_field=True
    )

    assert codec.extract_field(message, "$message.payload#/str_field") == "test"
    assert codec.extract_field(message, "$message.payload#/int_field") == "42"
    assert codec.extract_field(message, "$message.payload#/float_field") == "3.14"
    assert codec.extract_field(message, "$message.payload#/bool_field") == "True"
