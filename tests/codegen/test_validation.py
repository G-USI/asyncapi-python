"""Tests for the validation system."""

from pathlib import Path

import pytest

from asyncapi_python_codegen.parser.document_loader import extract_all_operations
from asyncapi_python_codegen.validation import (
    Severity,
    ValidationError,
    ValidationIssue,
    rule,
    validate_spec,
)
from asyncapi_python_codegen.validation.context import ValidationContext


def test_validation_error_raised_for_missing_asyncapi_field(tmp_path: Path):
    """Test that missing asyncapi field raises ValidationError."""
    spec_file = tmp_path / "invalid.yaml"
    spec_file.write_text(
        """
operations:
  myOp:
    action: send
"""
    )

    with pytest.raises(ValueError, match="Missing 'asyncapi' version field"):
        extract_all_operations(spec_file)


def test_validation_error_for_invalid_channel_parameters(tmp_path: Path):
    """Test that parameters not in address raise ValidationError."""
    spec_file = tmp_path / "invalid_params.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  myChannel:
    address: static.address
    parameters:
      userId:
        schema:
          type: string
    messages:
      msg:
        payload:
          type: object
operations:
  myOp:
    action: send
    channel:
      $ref: '#/channels/myChannel'
"""
    )

    with pytest.raises(ValidationError) as exc_info:
        extract_all_operations(spec_file)

    assert len(exc_info.value.errors) > 0
    assert any(
        "not used in address" in error.message for error in exc_info.value.errors
    )


def test_validation_passes_for_valid_spec(tmp_path: Path):
    """Test that a valid spec passes validation."""
    spec_file = tmp_path / "valid.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  userChannel:
    address: user.{userId}
    parameters:
      userId:
        location: $message.payload#/userId
    messages:
      userMessage:
        payload:
          type: object
          properties:
            userId:
              type: string
    bindings:
      amqp:
        is: routingKey
operations:
  sendUser:
    action: send
    channel:
      $ref: '#/channels/userChannel'
    messages:
      - $ref: '#/channels/userChannel/messages/userMessage'
"""
    )

    # Should not raise
    operations = extract_all_operations(spec_file)
    assert "sendUser" in operations


def test_validation_can_be_disabled(tmp_path: Path):
    """Test that validation can be disabled."""
    spec_file = tmp_path / "invalid_params.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  myChannel:
    address: static.address
    parameters:
      userId:
        schema:
          type: string
    messages:
      msg:
        payload:
          type: object
operations:
  myOp:
    action: send
    channel:
      $ref: '#/channels/myChannel'
"""
    )

    # Should not raise when validation is disabled
    operations = extract_all_operations(spec_file, validate=False)
    assert "myOp" in operations


def test_warnings_do_not_fail_validation(tmp_path: Path):
    """Test that warnings are collected but don't fail validation."""
    spec_file = tmp_path / "with_warnings.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  myChannel:
    address: user
    parameters:
      userId:
        location: $message.payload#/userId
    messages:
      userMessage:
        payload:
          type: object
          properties:
            userId:
              type: string
    bindings:
      amqp:
        is: queue
operations:
  myOp:
    action: send
    channel:
      $ref: '#/channels/myChannel'
"""
    )

    # Should not raise - location warning doesn't fail
    operations = extract_all_operations(spec_file)
    assert "myOp" in operations


def test_custom_rule_registration():
    """Test that users can register custom validation rules."""

    @rule("custom")
    def custom_test_rule(ctx: ValidationContext) -> list[ValidationIssue]:
        if ctx.spec.get("asyncapi") == "3.0.0":
            return [
                ValidationIssue(
                    severity=Severity.INFO,
                    message="Custom rule triggered",
                    path="$.asyncapi",
                    rule="custom-test-rule",
                )
            ]
        return []

    # Create a simple spec
    spec = {
        "asyncapi": "3.0.0",
        "operations": {},
    }

    # Validate with custom category
    issues = validate_spec(
        spec=spec,
        operations={},
        spec_path=Path("."),
        categories=["custom"],
        fail_on_error=False,
    )

    assert len(issues) == 1
    assert issues[0].rule == "custom-test-rule"


def test_parameter_with_location_warns_not_implemented(tmp_path: Path):
    """Test that using location field generates a warning."""
    spec_file = tmp_path / "location.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  myChannel:
    address: user
    parameters:
      userId:
        location: $message.payload#/userId
    messages:
      userMessage:
        payload:
          type: object
operations:
  myOp:
    action: send
    channel:
      $ref: '#/channels/myChannel'
"""
    )

    # Should succeed but print warning
    operations = extract_all_operations(spec_file, fail_on_error=False)
    assert "myOp" in operations


def test_location_path_must_exist_in_all_messages(tmp_path: Path):
    """Test that parameter location path must exist in ALL messages, not just some."""
    spec_file = tmp_path / "location_missing_in_some.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  alerts:
    address: alerts.{location}
    parameters:
      location:
        location: $message.payload#/location
    bindings:
      amqp:
        is: routingKey
        exchange:
          name: alerts_exchange
          type: topic
    messages:
      alert1:
        payload:
          type: object
          properties:
            location:
              type: string
            message:
              type: string
      alert2:
        payload:
          type: object
          properties:
            message:
              type: string
operations:
  sendAlert:
    action: send
    channel:
      $ref: '#/channels/alerts'
"""
    )

    with pytest.raises(ValidationError) as exc_info:
        extract_all_operations(spec_file)

    # Should fail because 'location' field is missing in alert2
    assert any(
        "not found in all message schemas" in error.message
        and "alert2" in error.message
        for error in exc_info.value.errors
    )


def test_location_path_exists_in_all_messages_passes(tmp_path: Path):
    """Test that validation passes when location exists in all messages."""
    spec_file = tmp_path / "location_in_all.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  alerts:
    address: alerts.{location}
    parameters:
      location:
        location: $message.payload#/location
    bindings:
      amqp:
        is: routingKey
        exchange:
          name: alerts_exchange
          type: topic
    messages:
      alert1:
        payload:
          type: object
          properties:
            location:
              type: string
            message:
              type: string
      alert2:
        payload:
          type: object
          properties:
            location:
              type: string
            severity:
              type: string
operations:
  sendAlert:
    action: send
    channel:
      $ref: '#/channels/alerts'
"""
    )

    # Should succeed - location exists in both messages
    operations = extract_all_operations(spec_file, fail_on_error=True)
    assert "sendAlert" in operations


def test_location_path_with_single_message(tmp_path: Path):
    """Test that validation works correctly with single message."""
    spec_file = tmp_path / "location_single_message.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  users:
    address: users.{userId}
    parameters:
      userId:
        location: $message.payload#/userId
    bindings:
      amqp:
        is: queue
    messages:
      userEvent:
        payload:
          type: object
          properties:
            userId:
              type: string
            name:
              type: string
operations:
  publishUser:
    action: send
    channel:
      $ref: '#/channels/users'
"""
    )

    # Should succeed - location exists in the single message
    operations = extract_all_operations(spec_file, fail_on_error=True)
    assert "publishUser" in operations


def test_location_path_with_no_messages(tmp_path: Path):
    """Test that validation skips channels with no messages."""
    spec_file = tmp_path / "location_no_messages.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  emptyChannel:
    address: empty.{param}
    parameters:
      param:
        location: $message.payload#/param
    bindings:
      amqp:
        is: queue
operations:
  emptyOp:
    action: send
    channel:
      $ref: '#/channels/emptyChannel'
    messages:
      - payload:
          type: object
          properties:
            param:
              type: string
"""
    )

    # Should succeed - validation skips channels with no messages
    operations = extract_all_operations(spec_file, fail_on_error=True)
    assert "emptyOp" in operations


def test_undefined_placeholders_in_address(tmp_path: Path):
    """Test that undefined placeholders in address raise error."""
    spec_file = tmp_path / "undefined_params.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  myChannel:
    address: user.{userId}.{role}
    parameters:
      userId:
        schema:
          type: string
    messages:
      msg:
        payload:
          type: object
operations:
  myOp:
    action: send
    channel:
      $ref: '#/channels/myChannel'
"""
    )

    with pytest.raises(ValidationError) as exc_info:
        extract_all_operations(spec_file)

    assert any(
        "undefined parameters" in error.message for error in exc_info.value.errors
    )


def test_operation_references_nonexistent_channel(tmp_path: Path):
    """Test that operation referencing non-existent channel raises error."""
    spec_file = tmp_path / "bad_channel_ref.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  realChannel:
    address: real
    messages:
      msg:
        payload:
          type: object
operations:
  myOp:
    action: send
    channel:
      $ref: '#/channels/fakeChannel'
"""
    )

    # Parser will fail when trying to resolve $ref (before validation runs)
    with pytest.raises(
        RuntimeError, match="JSON pointer segment 'fakeChannel' not found"
    ):
        extract_all_operations(spec_file)


def test_invalid_operation_action(tmp_path: Path):
    """Test that invalid operation action raises error."""
    spec_file = tmp_path / "bad_action.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  myChannel:
    address: test
    messages:
      msg:
        payload:
          type: object
operations:
  myOp:
    action: publish
    channel:
      $ref: '#/channels/myChannel'
"""
    )

    with pytest.raises(ValidationError) as exc_info:
        extract_all_operations(spec_file)

    assert any(
        "must be 'send' or 'receive'" in error.message
        for error in exc_info.value.errors
    )


def test_amqp_parameterized_channel_without_binding_type_fails(tmp_path: Path):
    """Test that parameterized channel without AMQP binding type fails validation."""
    spec_file = tmp_path / "amqp_no_binding_type.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  weatherAlerts:
    address: weather.{location}.{severity}
    parameters:
      location:
        location: $message.payload#/location
      severity:
        location: $message.payload#/severity
    messages:
      alert:
        payload:
          type: object
          properties:
            location:
              type: string
            severity:
              type: string
    bindings:
      amqp:
        # Missing 'is' field!
        exchange:
          name: weather_alerts
          type: topic
operations:
  publishAlert:
    action: send
    channel:
      $ref: '#/channels/weatherAlerts'
"""
    )

    with pytest.raises(ValidationError) as exc_info:
        extract_all_operations(spec_file)

    assert any("lacks 'is' field" in error.message for error in exc_info.value.errors)


def test_amqp_parameterized_channel_with_routing_key_passes(tmp_path: Path):
    """Test that parameterized channel with is: routingKey passes validation."""
    spec_file = tmp_path / "amqp_routing_key.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  weatherAlerts:
    address: weather.{location}.{severity}
    parameters:
      location:
        location: $message.payload#/location
      severity:
        location: $message.payload#/severity
    messages:
      alert:
        payload:
          type: object
          properties:
            location:
              type: string
            severity:
              type: string
    bindings:
      amqp:
        is: routingKey
        exchange:
          name: weather_alerts
          type: topic
operations:
  publishAlert:
    action: send
    channel:
      $ref: '#/channels/weatherAlerts'
"""
    )

    # Should not raise
    operations = extract_all_operations(spec_file)
    assert "publishAlert" in operations


def test_amqp_parameterized_channel_with_queue_passes(tmp_path: Path):
    """Test that parameterized channel with is: queue passes validation."""
    spec_file = tmp_path / "amqp_queue.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  userNotifications:
    address: user.{userId}.notifications
    parameters:
      userId:
        location: $message.payload#/userId
    messages:
      notification:
        payload:
          type: object
          properties:
            userId:
              type: string
    bindings:
      amqp:
        is: queue
operations:
  sendNotification:
    action: send
    channel:
      $ref: '#/channels/userNotifications'
"""
    )

    # Should not raise
    operations = extract_all_operations(spec_file)
    assert "sendNotification" in operations


def test_amqp_parameterized_channel_with_invalid_binding_type_fails(tmp_path: Path):
    """Test that parameterized channel with invalid binding type fails validation."""
    spec_file = tmp_path / "amqp_invalid_type.yaml"
    spec_file.write_text(
        """
asyncapi: 3.0.0
channels:
  myChannel:
    address: my.{param}.channel
    parameters:
      param:
        location: $message.payload#/param
    messages:
      msg:
        payload:
          type: object
          properties:
            param:
              type: string
    bindings:
      amqp:
        is: topic  # Invalid! Should be 'routingKey' or 'queue'
operations:
  myOp:
    action: send
    channel:
      $ref: '#/channels/myChannel'
"""
    )

    with pytest.raises(ValidationError) as exc_info:
        extract_all_operations(spec_file)

    assert any(
        "invalid" in error.message and "binding type" in error.message
        for error in exc_info.value.errors
    )
