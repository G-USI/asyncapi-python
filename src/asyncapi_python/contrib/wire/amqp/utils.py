"""Parameter validation and substitution utilities"""

# TODO: This thing should be general wire utils, not tied to specific wire

import re
from asyncapi_python.kernel.document.channel import Channel


def validate_parameters_strict(channel: Channel, provided: dict[str, str]) -> None:
    """
    Strict parameter validation - all defined parameters must be provided.
    Raises ValueError with detailed message if any parameters are missing.
    """
    if not channel.parameters:
        return  # No parameters defined, nothing to validate

    required = set(channel.parameters.keys())
    provided_keys = set(provided.keys())

    missing = required - provided_keys
    if missing:
        raise ValueError(
            f"Missing required parameters for channel '{channel.address}': {missing}. "
            f"Required: {sorted(required)}, Provided: {sorted(provided_keys)}"
        )

    extra = provided_keys - required
    if extra:
        raise ValueError(
            f"Unexpected parameters for channel '{channel.address}': {extra}. "
            f"Expected: {sorted(required)}, Provided: {sorted(provided_keys)}"
        )


def substitute_parameters(template: str, parameters: dict[str, str]) -> str:
    """
    Substitute {param} placeholders with actual values.
    All placeholders must have corresponding parameter values.
    """
    # Find all {param} placeholders
    placeholders = re.findall(r"\{(\w+)\}", template)

    # Check for undefined placeholders
    undefined = [p for p in placeholders if p not in parameters]
    if undefined:
        raise ValueError(
            f"Template '{template}' references undefined parameters: {undefined}. "
            f"Available parameters: {sorted(parameters.keys())}"
        )

    # Perform substitution
    result = template
    for key, value in parameters.items():
        result = result.replace(f"{{{key}}}", value)

    return result


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
