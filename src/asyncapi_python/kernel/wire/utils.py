"""Universal parameter validation utilities for all wire implementations."""

import re

from asyncapi_python.kernel.document.channel import Channel


def validate_parameters_strict(channel: Channel, provided: dict[str, str]) -> None:
    """
    Strict parameter validation - exact match required.
    Raises ValueError if any parameters are missing or unexpected.
    """
    required = set(channel.parameters.keys() if channel.parameters else [])
    provided_keys = set(provided.keys())

    # Check for missing parameters (only if channel has params defined)
    if channel.parameters:
        missing = required - provided_keys
        if missing:
            raise ValueError(
                f"Missing required parameters for channel '{channel.address}': {missing}. "
                f"Required: {sorted(required)}, Provided: {sorted(provided_keys)}"
            )

    # Check for extra parameters (ALWAYS - even if channel has no params)
    extra = provided_keys - required
    if extra:
        if channel.parameters:
            raise ValueError(
                f"Unexpected parameters for channel '{channel.address}': {extra}. "
                f"Expected: {sorted(required)}, Provided: {sorted(provided_keys)}"
            )
        else:
            raise ValueError(
                f"Unexpected parameters for channel '{channel.address}': {extra}. "
                f"Channel defines no parameters, but received: {sorted(provided_keys)}"
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
