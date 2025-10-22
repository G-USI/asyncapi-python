"""Unit tests for AsyncAPI dataclass parser."""

from pathlib import Path

import pytest

from asyncapi_python.kernel.document import Channel, Message, Operation
from src.asyncapi_python_codegen.parser import (
    extract_all_operations,
    load_document_info,
)

# Test basic parser functionality


def test_load_document_info():
    """Test loading basic document information."""
    spec_path = Path("tests/codegen/specs/simple.yaml")
    info = load_document_info(spec_path)

    assert info["asyncapi_version"] == "3.0.0"
    assert info["title"] == "Simple Test Service"
    assert info["version"] == "1.0.0"
    assert info["description"] == "Basic AsyncAPI spec for testing"


def test_extract_simple_operations():
    """Test extracting operations from simple spec."""
    spec_path = Path("tests/codegen/specs/simple.yaml")
    operations = extract_all_operations(spec_path)

    assert len(operations) == 2
    assert "ping" in operations
    assert "pong" in operations

    # Test ping operation
    ping_op = operations["ping"]
    assert isinstance(ping_op, Operation)
    assert ping_op.action == "send"
    assert ping_op.channel.address == "ping.queue"
    assert ping_op.channel.title == "Ping Channel"
    assert "ping" in ping_op.channel.messages

    # Test pong operation
    pong_op = operations["pong"]
    assert pong_op.action == "receive"
    assert pong_op.channel.address == "pong.queue"
    assert "pong" in pong_op.channel.messages


def test_extract_rpc_operations():
    """Test extracting RPC operations with replies."""
    spec_path = Path("tests/codegen/specs/rpc.yaml")
    operations = extract_all_operations(spec_path)

    assert len(operations) == 4

    # Test RPC client operation
    user_create = operations["user.create"]
    assert user_create.action == "send"
    assert user_create.title == "Create User"
    assert user_create.channel.address == "user.requests"
    assert user_create.reply is not None
    assert user_create.reply.channel.title == "User Response Channel"

    # Test RPC server operation
    user_process = operations["user.process"]
    assert user_process.action == "receive"
    assert user_process.reply is not None

    # Test publisher operation
    notification_send = operations["notification.send"]
    assert notification_send.action == "send"
    assert notification_send.channel.address == "notifications.fanout"
    assert notification_send.reply is None

    # Test subscriber operation
    log_write = operations["log.write"]
    assert log_write.action == "receive"
    assert log_write.channel.address == "logs.topic"
    assert log_write.reply is None


# Test message and payload extraction


def test_message_payloads_preserved():
    """Test that message payloads are preserved as raw data."""
    spec_path = Path("tests/codegen/specs/simple.yaml")
    operations = extract_all_operations(spec_path)

    ping_message = operations["ping"].channel.messages["ping"]
    assert isinstance(ping_message, Message)
    assert isinstance(ping_message.payload, dict)

    # Check payload structure
    payload = ping_message.payload
    assert payload["type"] == "object"
    assert "properties" in payload
    assert "message" in payload["properties"]
    assert payload["properties"]["message"]["const"] == "ping"


def test_message_metadata():
    """Test that message metadata is extracted correctly."""
    spec_path = Path("tests/codegen/specs/simple.yaml")
    operations = extract_all_operations(spec_path)

    ping_message = operations["ping"].channel.messages["ping"]
    assert ping_message.title == "Ping Message"
    assert ping_message.name == "ping"  # Set to message key by parser
    assert ping_message.deprecated is None


# Test that dataclasses can be stringified for templates


def test_channel_repr_valid_python():
    """Test that Channel repr() produces valid Python code."""
    spec_path = Path("tests/codegen/specs/simple.yaml")
    operations = extract_all_operations(spec_path)

    channel = operations["ping"].channel
    channel_repr = repr(channel)

    # Should start with class name
    assert channel_repr.startswith("Channel(")
    assert channel_repr.endswith(")")

    # Should contain key data
    assert "address='ping.queue'" in channel_repr
    assert "title='Ping Channel'" in channel_repr


def test_operation_repr_valid_python():
    """Test that Operation repr() produces valid Python code."""
    spec_path = Path("tests/codegen/specs/rpc.yaml")
    operations = extract_all_operations(spec_path)

    operation = operations["user.create"]
    op_repr = repr(operation)

    # Should be valid Python constructor
    assert op_repr.startswith("Operation(")
    assert op_repr.endswith(")")

    # Should contain key data
    assert "action='send'" in op_repr
    assert "title='Create User'" in op_repr


# Test internal reference resolution


def test_internal_channel_refs():
    """Test resolving internal channel references."""
    spec_path = Path("tests/codegen/specs/simple.yaml")
    operations = extract_all_operations(spec_path)

    # References should be resolved to actual data
    ping_op = operations["ping"]
    assert ping_op.channel.address == "ping.queue"
    assert "ping" in ping_op.channel.messages


def test_internal_message_refs():
    """Test resolving internal message references."""
    spec_path = Path("tests/codegen/specs/rpc.yaml")
    operations = extract_all_operations(spec_path)

    user_create = operations["user.create"]
    create_user_msg = user_create.channel.messages["create_user"]

    # Message should have resolved payload
    assert isinstance(create_user_msg.payload, dict)
    assert create_user_msg.payload["type"] == "object"
    assert "name" in create_user_msg.payload["properties"]
    assert "email" in create_user_msg.payload["properties"]


# Test relative file reference resolution (A->B->C chain)


def test_relative_ref_chain():
    """Test A->B->C reference chain resolution."""
    spec_path = Path("tests/codegen/specs/relative_refs/main.yaml")
    operations = extract_all_operations(spec_path)

    assert len(operations) == 2

    # Test A -> B reference
    user_create = operations["user.create"]
    assert user_create.channel.address == "users.queue"
    assert user_create.channel.title == "User Channel from File B"

    # Test B -> C reference (user_request message)
    user_request_msg = user_create.channel.messages["user_request"]
    assert user_request_msg.title == "User Create Request from File C"
    assert isinstance(user_request_msg.payload, dict)

    # Verify payload came from File C
    payload = user_request_msg.payload
    assert "name" in payload["properties"]
    assert "email" in payload["properties"]
    assert "department" in payload["properties"]
    assert payload["properties"]["department"]["enum"] == [
        "engineering",
        "sales",
        "marketing",
    ]


def test_different_relative_paths():
    """Test references from different directory structures."""
    spec_path = Path("tests/codegen/specs/relative_refs/main.yaml")
    operations = extract_all_operations(spec_path)

    # Test main.yaml -> shared/notifications.yaml -> shared/messages.yaml
    notification_send = operations["notification.send"]
    assert notification_send.channel.address == "notifications.fanout"
    assert notification_send.channel.title == "Notification Channel"

    # Test notification message from File C
    notification_msg = notification_send.channel.messages["notification"]
    assert notification_msg.title == "Notification Message"
    payload = notification_msg.payload
    assert payload["properties"]["source_file"]["const"] == "file_c_messages"


def test_context_preservation():
    """Test that parsing context is properly maintained across files."""
    spec_path = Path("tests/codegen/specs/relative_refs/main.yaml")
    operations = extract_all_operations(spec_path)

    # Verify that messages from different files have correct content
    user_create = operations["user.create"]
    user_response_msg = user_create.channel.messages["user_response"]

    # This message should have the marker from File C
    payload = user_response_msg.payload
    assert payload["properties"]["from_file_c"]["const"] == "shared_messages"


# Test error handling and validation


def test_missing_file_error():
    """Test error when file doesn't exist."""
    with pytest.raises(RuntimeError, match="Failed to load YAML file"):
        extract_all_operations(Path("nonexistent.yaml"))


def test_invalid_yaml_structure():
    """Test error with invalid YAML structure."""
    # Create temporary invalid YAML for testing
    invalid_yaml = Path("tests/codegen/specs/invalid.yaml")
    invalid_yaml.parent.mkdir(parents=True, exist_ok=True)

    with invalid_yaml.open("w") as f:
        f.write("not_a_dict: [this, is, invalid]\n")

    try:
        with pytest.raises(ValueError, match="Missing 'asyncapi' version field"):
            extract_all_operations(invalid_yaml)
    finally:
        invalid_yaml.unlink(missing_ok=True)


def test_four_level_deep_recursion():
    """Test 4-level deep file reference chain: Level1->Level2->Level3->Level4.

    This test verifies that the MessageGenerator recursively collects component schemas
    from all referenced files, not just the main spec file.
    """
    from src.asyncapi_python_codegen.generators.messages import MessageGenerator

    spec_path = Path("tests/codegen/specs/deep_recursion/level1.yaml")

    # Test that MessageGenerator collects schemas from all 4 levels
    generator = MessageGenerator()
    schemas = generator._load_component_schemas(spec_path)

    # Without recursive file loading, we would only get Level1Schema
    # With recursive loading, we should get schemas from all 4 files
    assert "Level1Schema" in schemas, "Level1Schema from main file not found"
    assert (
        "Level2Schema" in schemas
    ), "Level2Schema from level2.yaml not found (recursive loading failed)"
    assert (
        "Level3Schema" in schemas
    ), "Level3Schema from level3.yaml not found (recursive loading failed)"
    assert (
        "Level4Schema" in schemas
    ), "Level4Schema from level4.yaml not found (recursive loading failed)"
    assert "DataMessage" in schemas, "DataMessage from level3.yaml not found"

    # Verify the deepest level schema has correct structure
    level4_schema = schemas["Level4Schema"]
    assert level4_schema["properties"]["level"]["const"] == 4
    assert level4_schema["properties"]["message"]["const"] == "from_level_4_deepest"

    # Also verify operations can be extracted (tests parser, not generator)
    operations = extract_all_operations(spec_path)
    assert len(operations) == 1

    process_data = operations["process.data"]
    assert process_data.channel.address == "data.queue"
    assert process_data.channel.title == "Data Channel from Level 2"
