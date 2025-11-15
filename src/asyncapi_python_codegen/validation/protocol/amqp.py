"""AMQP protocol-specific validation rules."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from typing import Any

from ..base import rule
from ..context import ValidationContext
from ..errors import Severity, ValidationIssue


@rule("protocol.amqp")
def amqp_parameterized_channels_require_binding_type(
    ctx: ValidationContext,
) -> list[ValidationIssue]:
    """Parameterized channels MUST specify AMQP binding type (routingKey or queue).

    When compiling for AMQP, any channel with parameters must explicitly specify
    whether the parameterized address should be interpreted as:
    - "routingKey": Topic exchange routing key with pattern matching
    - "queue": Direct queue name for point-to-point messaging

    This disambiguates how AMQP should handle the parameterized address.
    """
    issues: list[ValidationIssue] = []

    for channel_key, channel_def in ctx.get_channels().items():
        if not isinstance(channel_def, dict):
            continue

        # Only check channels with parameters
        parameters: dict[str, Any] = channel_def.get("parameters", {})
        if not parameters:
            continue  # No parameters, no ambiguity

        # Check for AMQP binding
        bindings: dict[str, Any] = channel_def.get("bindings", {})
        amqp_binding: dict[str, Any] = bindings.get("amqp", {})

        # Require explicit "is" field for parameterized channels
        if "is" not in amqp_binding:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Channel '{channel_key}' has parameters but AMQP binding lacks 'is' field",
                    path=f"$.channels.{channel_key}.bindings.amqp",
                    rule="amqp-parameterized-channels-require-binding-type",
                    suggestion="Add 'is: routingKey' for topic exchange routing or 'is: queue' for direct queue addressing",
                )
            )
        elif amqp_binding["is"] not in ["routingKey", "queue"]:
            # Validate the value is one of the allowed types
            invalid_value: Any = amqp_binding["is"]
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Channel '{channel_key}' has invalid AMQP binding type: '{invalid_value}'",
                    path=f"$.channels.{channel_key}.bindings.amqp.is",
                    rule="amqp-parameterized-channels-require-binding-type",
                    suggestion="Use 'is: routingKey' for topic exchanges or 'is: queue' for direct queues",
                )
            )

    return issues
