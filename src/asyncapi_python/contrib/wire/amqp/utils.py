"""AMQP-specific parameter validation utilities"""

import re

from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.wire.utils import (
    substitute_parameters,
    validate_parameters_strict,
)

# Re-export for backward compatibility
__all__ = [
    "validate_parameters_strict",
    "substitute_parameters",
    "validate_channel_template",
]


def validate_channel_template(
    channel: Channel, template_name: str, template: str
) -> None:
    """
    Validate that a template only references defined channel parameters.
    Should be called during application startup to catch configuration errors early.
    """
    if not template:
        return

    placeholders = re.findall(r"\{(\w+)\}", template)
    if not placeholders:
        return  # No parameters used in template

    if not channel.parameters:
        raise ValueError(
            f"Channel {template_name} template '{template}' uses parameters {placeholders} "
            f"but no parameters are defined for the channel"
        )

    undefined = [p for p in placeholders if p not in channel.parameters]
    if undefined:
        raise ValueError(
            f"Channel {template_name} template '{template}' references "
            f"undefined parameters: {undefined}. "
            f"Defined parameters: {sorted(channel.parameters.keys())}"
        )
