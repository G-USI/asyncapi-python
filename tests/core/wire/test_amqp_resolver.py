"""Tests for AMQP resolver validation logic."""

import re

import pytest

from asyncapi_python.contrib.wire.amqp.resolver import (
    _validate_no_wildcards_in_queue,
    resolve_amqp_config,
)
from asyncapi_python.kernel.document.bindings import (
    AmqpChannelBinding,
    AmqpExchange,
    AmqpExchangeType,
)
from asyncapi_python.kernel.document.channel import (
    AddressParameter,
    Channel,
    ChannelBindings,
)
from asyncapi_python.kernel.wire import EndpointParams


def create_test_channel(
    address: str | None = None,
    binding: AmqpChannelBinding | None = None,
) -> Channel:
    """Create a minimal test channel with required fields.

    Automatically extracts parameters from address template (e.g., {location}).
    """
    bindings = None
    if binding:
        bindings = ChannelBindings(amqp=binding)

    # Extract parameters from address template
    parameters = {}
    if address:
        param_names = re.findall(r"\{(\w+)\}", address)
        for param_name in param_names:
            parameters[param_name] = AddressParameter(
                key=param_name,
                description=f"Test parameter {param_name}",
                location=None,
            )

    return Channel(
        key="test_channel",
        address=address,
        title=None,
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters=parameters,
        tags=[],
        external_docs=None,
        bindings=bindings,
    )


def test_validate_no_wildcards_accepts_concrete_values():
    """Concrete parameter values should pass validation."""
    params = {"location": "NYC", "severity": "high"}
    # Should not raise
    _validate_no_wildcards_in_queue(params)


def test_validate_no_wildcards_rejects_star_wildcard():
    """Parameter values with * wildcard should be rejected."""
    params = {"location": "*", "severity": "high"}
    with pytest.raises(ValueError) as exc_info:
        _validate_no_wildcards_in_queue(params)

    assert "wildcard patterns" in str(exc_info.value)
    assert "location=*" in str(exc_info.value)


def test_validate_no_wildcards_rejects_hash_wildcard():
    """Parameter values with # wildcard should be rejected."""
    params = {"location": "NYC", "severity": "#"}
    with pytest.raises(ValueError) as exc_info:
        _validate_no_wildcards_in_queue(params)

    assert "wildcard patterns" in str(exc_info.value)
    assert "severity=#" in str(exc_info.value)


def test_validate_no_wildcards_rejects_multiple_wildcards():
    """Multiple wildcard parameters should all be reported."""
    params = {"location": "*", "severity": "#", "priority": "high"}
    with pytest.raises(ValueError) as exc_info:
        _validate_no_wildcards_in_queue(params)

    error_msg = str(exc_info.value)
    assert "wildcard patterns" in error_msg
    assert "location=*" in error_msg
    assert "severity=#" in error_msg


def test_validate_no_wildcards_accepts_empty_dict():
    """Empty parameter dict should pass validation."""
    params = {}
    # Should not raise
    _validate_no_wildcards_in_queue(params)


def test_resolve_queue_binding_rejects_wildcards():
    """Queue bindings should reject wildcard parameters."""
    # Create channel with queue binding
    channel = create_test_channel(
        address="weather.{location}.{severity}",
        binding=AmqpChannelBinding(type="queue"),
    )

    params: EndpointParams = {
        "channel": channel,
        "parameters": {"location": "*", "severity": "high"},
        "op_bindings": None,
        "is_reply": False,
    }

    with pytest.raises(ValueError) as exc_info:
        resolve_amqp_config(params, "test_op", "test_app")

    assert "wildcard patterns" in str(exc_info.value)
    assert "location=*" in str(exc_info.value)


def test_resolve_routing_key_binding_accepts_wildcards():
    """Routing key bindings should accept wildcard parameters."""
    # Create channel with routingKey binding
    channel = create_test_channel(
        address="weather.{location}.{severity}",
        binding=AmqpChannelBinding(
            type="routingKey",
            exchange=AmqpExchange(
                name="weather_exchange",
                type=AmqpExchangeType.TOPIC,
            ),
        ),
    )

    params: EndpointParams = {
        "channel": channel,
        "parameters": {"location": "*", "severity": "high"},
        "op_bindings": None,
        "is_reply": False,
    }

    # Should not raise
    config = resolve_amqp_config(params, "test_op", "test_app")

    # Verify the routing key was substituted with wildcards
    assert config.routing_key == "weather.*.high"


def test_resolve_channel_address_without_binding_rejects_wildcards():
    """Channel address without explicit binding (implicit queue) should reject wildcards."""
    # Channel without bindings defaults to queue binding
    channel = create_test_channel(
        address="task.{priority}",
        binding=None,
    )

    params: EndpointParams = {
        "channel": channel,
        "parameters": {"priority": "*"},
        "op_bindings": None,
        "is_reply": False,
    }

    with pytest.raises(ValueError) as exc_info:
        resolve_amqp_config(params, "test_op", "test_app")

    assert "wildcard patterns" in str(exc_info.value)
    assert "priority=*" in str(exc_info.value)


def test_resolve_channel_address_without_binding_accepts_concrete_params():
    """Channel address without explicit binding should accept concrete parameters."""
    channel = create_test_channel(
        address="task.{priority}",
        binding=None,
    )

    params: EndpointParams = {
        "channel": channel,
        "parameters": {"priority": "high"},
        "op_bindings": None,
        "is_reply": False,
    }

    # Should not raise
    config = resolve_amqp_config(params, "test_op", "test_app")

    # Verify the address was substituted with concrete value
    assert config.queue_name == "task.high"
