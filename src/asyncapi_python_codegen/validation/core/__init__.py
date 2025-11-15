"""Core AsyncAPI 3.0 validation rules.

These rules validate AsyncAPI 3.0 specification compliance and catch common errors.
Many of these rules address issues documented in BUG.md.
"""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

import re
from typing import Any

from ..base import rule
from ..context import ValidationContext
from ..errors import Severity, ValidationIssue


@rule("core")
def required_asyncapi_version(ctx: ValidationContext) -> list[ValidationIssue]:
    """Validate that asyncapi field exists and is version 3.x."""
    if "asyncapi" not in ctx.spec:
        return [
            ValidationIssue(
                severity=Severity.ERROR,
                message="Missing required 'asyncapi' field",
                path="$",
                rule="required-asyncapi-version",
                suggestion="Add 'asyncapi: 3.0.0' at the root level",
            )
        ]

    version = ctx.spec["asyncapi"]
    if not isinstance(version, str) or not version.startswith("3."):
        return [
            ValidationIssue(
                severity=Severity.ERROR,
                message=f"Unsupported AsyncAPI version: {version}",
                path="$.asyncapi",
                rule="required-asyncapi-version",
                suggestion="This library supports AsyncAPI 3.x",
            )
        ]

    return []


@rule("core")
def required_operations_or_channels(ctx: ValidationContext) -> list[ValidationIssue]:
    """Validate that at least operations or channels section exists."""
    has_operations = "operations" in ctx.spec and ctx.spec["operations"]
    has_channels = "channels" in ctx.spec and ctx.spec["channels"]

    if not has_operations and not has_channels:
        return [
            ValidationIssue(
                severity=Severity.ERROR,
                message="Document must have at least 'operations' or 'channels' section",
                path="$",
                rule="required-operations-or-channels",
            )
        ]

    return []


@rule("core")
def operations_is_dict(ctx: ValidationContext) -> list[ValidationIssue]:
    """Validate that operations section is a dict."""
    if "operations" in ctx.spec:
        if not isinstance(ctx.spec["operations"], dict):
            return [
                ValidationIssue(
                    severity=Severity.ERROR,
                    message="'operations' must be an object/dict",
                    path="$.operations",
                    rule="operations-is-dict",
                )
            ]

    return []


@rule("core")
def channel_address_matches_parameters(ctx: ValidationContext) -> list[ValidationIssue]:
    """
    Validate that channel address contains placeholders for all parameters.

    FIX BUG.md: This rule checks the 'address' field, not the channel key!
    The parameter generator was incorrectly checking channel keys for {placeholders}.
    """
    issues = []

    for channel_key, channel_def in ctx.get_channels().items():
        if not isinstance(channel_def, dict):
            continue

        # CRITICAL FIX: Use 'address' field, not channel key!
        address = channel_def.get("address", "")
        parameters = channel_def.get("parameters", {})

        if not parameters:
            continue  # No parameters to validate

        # Extract placeholders from address using regex
        placeholders = set(re.findall(r"\{([^}]+)\}", address))
        param_names = set(parameters.keys())

        # Check 1: All parameters should appear in address
        missing_in_address = param_names - placeholders
        if missing_in_address:
            # Check if any have location field - they don't need to be in address
            missing_without_location = {
                name
                for name in missing_in_address
                if not parameters.get(name, {}).get("location")
            }

            if missing_without_location:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Parameters defined but not used in address: {missing_without_location}",
                        path=f"$.channels.{channel_key}.parameters",
                        rule="channel-address-matches-parameters",
                        suggestion=f"Add to address: {address}.{{{', '.join(missing_without_location)}}}",
                    )
                )

        # Check 2: All placeholders should have parameter definitions
        undefined_params = placeholders - param_names
        if undefined_params:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Address uses undefined parameters: {undefined_params}",
                    path=f"$.channels.{channel_key}.address",
                    rule="channel-address-matches-parameters",
                    suggestion="Define these parameters in the 'parameters' section",
                )
            )

    return issues


@rule("core")
def parameter_requires_location(ctx: ValidationContext) -> list[ValidationIssue]:
    """All parameters MUST have a location field."""
    issues = []

    for channel_key, channel_def in ctx.get_channels().items():
        if not isinstance(channel_def, dict):
            continue

        parameters = channel_def.get("parameters", {})
        for param_name, param_def in parameters.items():
            if not isinstance(param_def, dict):
                continue

            location = param_def.get("location", "")
            if not location:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Parameter '{param_name}' must have 'location' field",
                        path=f"$.channels.{channel_key}.parameters.{param_name}",
                        rule="parameter-requires-location",
                        suggestion="Add location: $message.payload#/fieldName",
                    )
                )

    return issues


@rule("core")
def parameter_location_syntax_valid(ctx: ValidationContext) -> list[ValidationIssue]:
    """
    Validate that parameter location fields use valid runtime expression syntax.

    FIX BUG.md: Validates location field syntax (though runtime extraction not implemented).
    """
    issues = []

    for channel_key, channel_def in ctx.get_channels().items():
        if not isinstance(channel_def, dict):
            continue

        parameters = channel_def.get("parameters", {})
        for param_name, param_def in parameters.items():
            if not isinstance(param_def, dict):
                continue

            location = param_def.get("location")
            if not location:
                continue

            # Validate location syntax
            if not isinstance(location, str):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Parameter '{param_name}' location must be a string",
                        path=f"$.channels.{channel_key}.parameters.{param_name}.location",
                        rule="parameter-location-syntax-valid",
                    )
                )
                continue

            # Check for valid runtime expression pattern
            # Valid: "$message.header#/userId", "$message.payload#/user/id"
            if not location.startswith("$message."):
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        message=f"Parameter '{param_name}' location should start with '$message.'",
                        path=f"$.channels.{channel_key}.parameters.{param_name}.location",
                        rule="parameter-location-syntax-valid",
                        suggestion="Use format: $message.payload#/path or $message.header#/path",
                    )
                )

    return issues


@rule("core")
def location_must_be_payload(ctx: ValidationContext) -> list[ValidationIssue]:
    """Location must use $message.payload#/ format (headers not supported)."""
    issues = []

    for channel_key, channel_def in ctx.get_channels().items():
        if not isinstance(channel_def, dict):
            continue

        parameters = channel_def.get("parameters", {})
        for param_name, param_def in parameters.items():
            if not isinstance(param_def, dict):
                continue

            location = param_def.get("location")
            if location and not location.startswith("$message.payload#/"):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Parameter '{param_name}' location must start with '$message.payload#/'",
                        path=f"$.channels.{channel_key}.parameters.{param_name}.location",
                        rule="location-must-be-payload",
                        suggestion="Use format: $message.payload#/path/to/field",
                    )
                )

    return issues


@rule("core")
def location_path_exists_in_schema(ctx: ValidationContext) -> list[ValidationIssue]:
    """Validate location path exists in ALL message payload schemas.

    Parameters with location fields must reference paths that exist in every
    message in the channel, not just some of them. This prevents runtime errors
    when processing messages that lack the required field.
    """
    issues = []

    for channel_key, channel_def in ctx.get_channels().items():
        if not isinstance(channel_def, dict):
            continue

        parameters = channel_def.get("parameters", {})
        messages = channel_def.get("messages", {})

        for param_name, param_def in parameters.items():
            if not isinstance(param_def, dict):
                continue

            location = param_def.get("location")
            if not location:
                continue

            # Parse path from location
            path = location.replace("$message.payload#/", "")
            parts = [p for p in path.split("/") if p]

            # Check if path exists in ALL message schemas
            missing_in_messages = []
            for msg_name, msg_def in messages.items():
                if not isinstance(msg_def, dict):
                    continue
                if not _path_exists_in_schema(msg_def.get("payload"), parts):
                    missing_in_messages.append(msg_name)

            if missing_in_messages:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Parameter '{param_name}' location path '{path}' not found in all message schemas. "
                        f"Missing in: {', '.join(missing_in_messages)}",
                        path=f"$.channels.{channel_key}.parameters.{param_name}.location",
                        rule="location-path-exists-in-schema",
                        suggestion=f"Add '{path}' field to all message payloads in this channel",
                    )
                )

    return issues


def _path_exists_in_schema(schema: dict[str, Any] | None, parts: list[str]) -> bool:
    """Helper to check if path exists in JSON schema."""
    if not schema or not parts:
        return False

    current = schema
    for part in parts:
        if current.get("type") == "object":
            props = current.get("properties", {})
            if part in props:
                current = props[part]
            else:
                return False
        else:
            return False
    return True


@rule("core")
def operation_references_valid_channel(ctx: ValidationContext) -> list[ValidationIssue]:
    """Validate that operations reference channels that exist."""
    issues = []
    channels = ctx.get_channels()
    operations_spec = ctx.get_operations_spec()

    for op_id, op_def in operations_spec.items():
        if not isinstance(op_def, dict):
            continue

        channel_ref = op_def.get("channel")
        if channel_ref:
            # Handle both direct reference and $ref
            if isinstance(channel_ref, dict) and "$ref" in channel_ref:
                # TODO: Resolve $ref and validate
                continue
            elif isinstance(channel_ref, str):
                # Direct channel reference
                if channel_ref not in channels:
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            message=f"Operation references non-existent channel '{channel_ref}'",
                            path=f"$.operations.{op_id}.channel",
                            rule="operation-references-valid-channel",
                        )
                    )

    return issues


@rule("core")
def operation_messages_ignored(ctx: ValidationContext) -> list[ValidationIssue]:
    """Warn when operation.messages is specified but will be ignored.

    In AsyncAPI 3.0, when an operation references a channel, the channel's messages
    are used, and any messages specified directly on the operation are ignored.
    """
    issues = []
    operations_spec = ctx.get_operations_spec()

    for op_id, op_def in operations_spec.items():
        if not isinstance(op_def, dict):
            continue

        # Check if operation has both channel reference and messages
        has_channel = "channel" in op_def and op_def["channel"]
        has_messages = "messages" in op_def and op_def["messages"]

        if has_channel and has_messages:
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    message=f"Operation '{op_id}' specifies 'messages' but they will be ignored",
                    path=f"$.operations.{op_id}.messages",
                    rule="operation-messages-ignored",
                    suggestion="Remove 'messages' from operation - channel messages are used instead",
                )
            )

    return issues


@rule("core")
def valid_operation_action(ctx: ValidationContext) -> list[ValidationIssue]:
    """Validate that operation action is 'send' or 'receive'."""
    issues = []
    operations_spec = ctx.get_operations_spec()

    for op_id, op_def in operations_spec.items():
        if not isinstance(op_def, dict):
            continue

        action = op_def.get("action")
        if action and action not in ["send", "receive"]:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Operation action must be 'send' or 'receive', got '{action}'",
                    path=f"$.operations.{op_id}.action",
                    rule="valid-operation-action",
                )
            )

    return issues


@rule("core")
def channel_id_no_braces(ctx: ValidationContext) -> list[ValidationIssue]:
    """Prohibit curly braces in channel identifiers.

    Channel IDs (keys) should not contain {braces}. Parameters belong in the
    channel's address field, not in the channel identifier itself.
    """
    issues = []

    for channel_key, channel_def in ctx.get_channels().items():
        if not isinstance(channel_def, dict):
            continue

        # Check if channel ID contains braces
        if "{" in channel_key or "}" in channel_key:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Channel ID '{channel_key}' must not contain curly braces",
                    path=f"$.channels.{channel_key}",
                    rule="channel-id-no-braces",
                    suggestion="Use a simple identifier for the channel key and put parameters in the 'address' field",
                )
            )

    return issues


@rule("core")
def channel_has_address_if_not_reference(
    ctx: ValidationContext,
) -> list[ValidationIssue]:
    """Validate that channels have an address field (can be null for reusable channels)."""
    issues = []

    for channel_key, channel_def in ctx.get_channels().items():
        if not isinstance(channel_def, dict):
            continue

        # Skip if this is a reference
        if "$ref" in channel_def:
            continue

        # Address field should exist (can be null)
        if "address" not in channel_def:
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    message=f"Channel '{channel_key}' has no 'address' field",
                    path=f"$.channels.{channel_key}",
                    rule="channel-has-address",
                    suggestion="Add 'address' field or set to null for reusable channels",
                )
            )

    return issues


@rule("core")
def channel_address_same_as_id(ctx: ValidationContext) -> list[ValidationIssue]:
    """Warn when channel address is identical to channel ID.

    When the address field is the same as the channel identifier, it's redundant.
    The address field should only be specified when it differs from the channel ID
    or when it contains parameters.
    """
    issues = []

    for channel_key, channel_def in ctx.get_channels().items():
        if not isinstance(channel_def, dict):
            continue

        # Skip if this is a reference
        if "$ref" in channel_def:
            continue

        # Get the address field
        address = channel_def.get("address")

        # Check if address is identical to channel ID
        if address and address == channel_key:
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    message=f"Channel '{channel_key}' has address identical to its ID",
                    path=f"$.channels.{channel_key}.address",
                    rule="channel-address-same-as-id",
                    suggestion="Remove redundant 'address' field or use null if the address should match the channel ID",
                )
            )

    return issues
