"""Binding resolution with comprehensive pattern matching"""

import re
from typing import Any

from asyncapi_python.kernel.document.bindings import AmqpChannelBinding
from asyncapi_python.kernel.document.channel import Channel
from asyncapi_python.kernel.wire import EndpointParams
from asyncapi_python.kernel.wire.utils import substitute_parameters

from .config import AmqpBindingType, AmqpConfig


def _validate_no_wildcards_in_queue(param_values: dict[str, str]) -> None:
    """Validate that parameter values don't contain AMQP wildcards when using queue bindings.

    AMQP queue names are literal - they don't support pattern matching.
    Only topic exchange routing keys support wildcards (* and #).

    Args:
        param_values: Dictionary of parameter values to check

    Raises:
        ValueError: If any parameter value contains wildcard characters
    """
    wildcards_found: list[str] = []
    for param_name, param_value in param_values.items():
        if "*" in param_value or "#" in param_value:
            wildcards_found.append(f"{param_name}={param_value}")

    if wildcards_found:
        raise ValueError(
            f"AMQP queue bindings do not support wildcard patterns ('*' or '#'). "
            f"Found wildcards in parameters: {', '.join(wildcards_found)}. "
            f"Use 'is: routingKey' with a topic exchange for pattern matching, "
            f"or provide concrete parameter values for queue bindings."
        )


def _substitute_routing_key_with_wildcards(
    template: str, param_values: dict[str, str]
) -> str:
    """
    Substitute parameters in routing key template, using wildcards for missing parameters.

    For topic exchange bindings, missing parameters are replaced with '*' (single-word wildcard).
    If no parameters are provided and template has placeholders, all are replaced with '*'.
    Parameter values can also explicitly contain wildcards ('*' or '#').

    Args:
        template: Template string with {param} placeholders (e.g., "weather.{location}.{severity}")
        param_values: Dictionary of parameter values (can be empty, partial, or contain wildcards)

    Returns:
        Resolved routing key with wildcards for missing parameters

    Examples:
        - template="weather.{location}.{severity}", params={} → "weather.*.*"
        - template="weather.{location}.{severity}", params={"location": "NYC"} → "weather.NYC.*"
        - template="weather.{location}.{severity}", params={"severity": "#"} → "weather.*.#"
    """
    # Find all {param} placeholders
    placeholders = re.findall(r"\{(\w+)\}", template)

    # Build substitution dict - use provided value or '*' wildcard for missing params
    substitutions = {p: param_values.get(p, "*") for p in placeholders}

    # Perform substitution
    result = template
    for key, value in substitutions.items():
        result = result.replace(f"{{{key}}}", value)

    return result


def resolve_amqp_config(
    params: EndpointParams, operation_name: str, app_id: str
) -> AmqpConfig:
    """
    Resolve AMQP configuration using comprehensive pattern matching for precedence rules.

    Precedence (highest to lowest):
    1. Reply channel special case
    2. Channel AMQP binding (queue/routingKey/exchange)
    3. Channel address (with parameter substitution)
    4. Operation name
    5. REJECT if none available
    """
    channel = params["channel"]
    param_values = params["parameters"] or {}
    is_reply = params["is_reply"]

    # Extract AMQP binding if present (validation will be done later based on binding type)
    amqp_binding = None
    if channel.bindings and hasattr(channel.bindings, "amqp") and channel.bindings.amqp:
        amqp_binding = channel.bindings.amqp

    # Comprehensive pattern matching for precedence
    match (
        is_reply,
        amqp_binding,
        channel.address,
        operation_name,
    ):

        # Reply channel pattern - anonymous queue (no address, no binding)
        case (True, None, None, _):
            # Anonymous reply queue: exclusive and temporary (deleted on connection loss)
            return AmqpConfig(
                queue_name=f"reply-{app_id}",  # App-specific reply queue
                exchange_name="",  # Default exchange for reply
                routing_key=f"reply-{app_id}",  # Direct routing to the reply queue
                binding_type=AmqpBindingType.REPLY,
                queue_properties={
                    "durable": False,
                    "exclusive": True,
                    "auto_delete": True,
                },
                arguments={},
            )

        # Reply channel with explicit address - check if direct queue or topic exchange
        case (True, _, address, _) if address:
            resolved_address = substitute_parameters(address, param_values)
            # If address starts with "reply-", treat it as a direct queue name (RPC pattern)
            if resolved_address.startswith("reply-"):
                return AmqpConfig(
                    queue_name=resolved_address,  # Use address as queue name
                    exchange_name="",  # Default exchange for direct routing
                    routing_key=resolved_address,  # Route directly to queue
                    binding_type=AmqpBindingType.REPLY,
                    queue_properties={
                        "durable": False,
                        "exclusive": True,
                        "auto_delete": True,
                    },
                    arguments={},
                )
            else:
                # Topic-based reply pattern - shared exchange with filtering
                return AmqpConfig(
                    queue_name=f"reply-{app_id}",  # App-specific reply queue
                    exchange_name=resolved_address,  # Shared exchange for replies
                    exchange_type="topic",  # Enable pattern matching for filtering
                    routing_key=app_id,  # Filter messages by app_id
                    binding_type=AmqpBindingType.REPLY,
                    queue_properties={"durable": True, "exclusive": False},
                    arguments={},
                )

        # Reply channel with binding - defer to binding resolution
        case (True, binding, _, _) if binding and binding.type == "queue":
            config = resolve_queue_binding(
                binding, param_values, channel, operation_name
            )
            # Override queue name with reply- prefix for reply queues
            config.queue_name = f"reply-{app_id}-{config.queue_name}"
            config.routing_key = config.queue_name
            config.binding_type = AmqpBindingType.REPLY
            return config

        case (True, binding, _, _) if binding and binding.type == "routingKey":
            config = resolve_routing_key_binding(
                binding, param_values, channel, operation_name
            )
            # For reply with routing key binding, create a prefixed queue
            config.queue_name = f"reply-{app_id}"
            config.binding_type = AmqpBindingType.REPLY
            return config

        # AMQP queue binding pattern (dataclass only)
        case (False, binding, _, _) if binding and binding.type == "queue":
            return resolve_queue_binding(binding, param_values, channel, operation_name)

        # AMQP routing key binding pattern (dataclass only)
        case (False, binding, _, _) if binding and binding.type == "routingKey":
            return resolve_routing_key_binding(
                binding, param_values, channel, operation_name
            )

        # AMQP exchange binding pattern (dataclass only)
        case (False, binding, _, _) if binding and binding.exchange:
            return resolve_exchange_binding(
                binding, param_values, channel, operation_name, channel.key
            )

        # Channel address pattern (with parameter substitution)
        case (False, None, address, _) if address:
            # Validate no wildcards for implicit queue binding
            _validate_no_wildcards_in_queue(param_values)
            resolved_address = substitute_parameters(address, param_values)
            return AmqpConfig(
                queue_name=resolved_address,
                exchange_name="",  # Default exchange
                routing_key=resolved_address,
                binding_type=AmqpBindingType.QUEUE,
                queue_properties={"durable": True, "exclusive": False},
                arguments={},
            )

        # Operation name pattern (fallback)
        case (False, None, None, op_name) if op_name:
            # Validate no wildcards for implicit queue binding
            _validate_no_wildcards_in_queue(param_values)
            return AmqpConfig(
                queue_name=op_name,
                exchange_name="",  # Default exchange
                routing_key=op_name,
                binding_type=AmqpBindingType.QUEUE,
                queue_properties={"durable": True, "exclusive": False},
                arguments={},
            )

        # No match - reject creation
        case _:
            raise ValueError(
                f"Cannot resolve AMQP binding: no valid configuration found. "
                f"Channel: {channel.address}, Binding: {amqp_binding}, Operation: {operation_name}"
            )


def resolve_queue_binding(
    binding: AmqpChannelBinding,
    param_values: dict[str, str],
    channel: Channel,
    operation_name: str,
) -> AmqpConfig:
    """Resolve AMQP queue binding configuration

    Queue bindings require:
    - No wildcards allowed in parameter values
    """

    # Validate no wildcards in queue binding parameters
    _validate_no_wildcards_in_queue(param_values)

    # Determine queue name with precedence
    match (getattr(binding, "queue", None), channel.address, operation_name):
        case (queue_config, _, _) if queue_config and getattr(
            queue_config, "name", None
        ):
            queue_name = substitute_parameters(queue_config.name, param_values)
        case (_, address, _) if address:
            queue_name = substitute_parameters(address, param_values)
        case (_, _, op_name) if op_name:
            queue_name = op_name
        case _:
            raise ValueError("Cannot determine queue name for queue binding")

    # Extract queue properties
    queue_config = getattr(binding, "queue", None)
    queue_properties = {"durable": True, "exclusive": False}  # Defaults
    arguments: dict[str, Any] = {}
    if queue_config:
        if hasattr(queue_config, "durable"):
            queue_properties["durable"] = queue_config.durable
        if hasattr(queue_config, "exclusive"):
            queue_properties["exclusive"] = queue_config.exclusive
        if hasattr(queue_config, "auto_delete"):
            queue_properties["auto_delete"] = queue_config.auto_delete
        if hasattr(queue_config, "arguments") and queue_config.arguments:
            arguments = queue_config.arguments

    return AmqpConfig(
        queue_name=queue_name,
        exchange_name="",  # Queue bindings use default exchange
        routing_key=queue_name,  # For default exchange, routing_key = queue_name
        binding_type=AmqpBindingType.QUEUE,
        queue_properties=queue_properties,
        arguments=arguments,
    )


def resolve_routing_key_binding(
    binding: AmqpChannelBinding,
    param_values: dict[str, str],
    channel: Channel,
    operation_name: str,
) -> AmqpConfig:
    """Resolve AMQP routing key binding configuration for pub/sub patterns

    For routing key bindings:
    - Parameter values can explicitly contain wildcards ('*' or '#')
    - Wildcards are allowed for topic exchange pattern matching
    """

    # Determine exchange name and type
    # For exchange name, we need concrete values (no wildcards)
    # If param_values has placeholders, use them; otherwise use literal exchange name
    exchange_config = getattr(binding, "exchange", None)
    match (
        exchange_config and getattr(exchange_config, "name", None),
        channel.address,
        operation_name,
    ):
        case (exchange_name, _, _) if exchange_name:
            # Exchange name should be literal (no parameter substitution for exchange names)
            resolved_exchange = exchange_name
        case (None, address, _) if address:
            # If address is used for exchange, check if it has parameters
            # If it does, use wildcards; if not, use as-is
            resolved_exchange = _substitute_routing_key_with_wildcards(
                address, param_values
            )
        case (None, None, op_name) if op_name:
            resolved_exchange = op_name
        case _:
            raise ValueError("Cannot determine exchange name for routing key binding")

    # Determine exchange type
    exchange_type = "topic"  # Default for routing key bindings
    if exchange_config and hasattr(exchange_config, "type"):
        exchange_type = exchange_config.type

    # Extract exchange arguments
    arguments: dict[str, Any] = {}
    if (
        exchange_config
        and hasattr(exchange_config, "arguments")
        and exchange_config.arguments
    ):
        arguments = exchange_config.arguments

    # Determine routing key - this is where wildcards are allowed
    match (getattr(binding, "routingKey", None), channel.address, operation_name):
        case (routing_key, _, _) if routing_key:
            # Use wildcard substitution for routing keys
            resolved_routing_key = _substitute_routing_key_with_wildcards(
                routing_key, param_values
            )
        case (None, address, _) if address:
            # Use wildcard substitution for routing keys from address
            resolved_routing_key = _substitute_routing_key_with_wildcards(
                address, param_values
            )
        case (None, None, op_name) if op_name:
            resolved_routing_key = op_name
        case _:
            raise ValueError("Cannot determine routing key for routing key binding")

    return AmqpConfig(
        queue_name="",  # Auto-generated exclusive queue for pub/sub
        exchange_name=resolved_exchange,
        exchange_type=exchange_type,
        routing_key=resolved_routing_key,
        binding_type=AmqpBindingType.ROUTING_KEY,
        queue_properties={"durable": False, "exclusive": True, "auto_delete": True},
        arguments=arguments,
    )


def resolve_exchange_binding(
    binding: AmqpChannelBinding,
    param_values: dict[str, str],
    channel: Channel,
    operation_name: str,
    channel_key: str = "",
) -> AmqpConfig:
    """Resolve AMQP exchange binding configuration for advanced pub/sub"""

    # Get exchange config from dataclass binding
    exchange_config = getattr(binding, "exchange", None)
    exchange_name = getattr(exchange_config, "name", None) if exchange_config else None

    match (
        exchange_name,
        channel.address,
        channel_key,
        operation_name,
    ):
        case (exchange_name, _, _, _) if exchange_name:
            resolved_exchange = substitute_parameters(exchange_name, param_values)
        case (None, address, _, _) if address:
            resolved_exchange = substitute_parameters(address, param_values)
        case (None, None, ch_key, _) if ch_key:
            # Use channel key as fallback when address is null
            resolved_exchange = ch_key.lstrip("/")  # Remove leading slash
        case (None, None, "", op_name) if op_name:
            resolved_exchange = op_name
        case _:
            raise ValueError("Cannot determine exchange name for exchange binding")

    # Determine exchange type from dataclass
    exchange_type = "fanout"  # Default for exchange bindings
    if exchange_config and hasattr(exchange_config, "type"):
        exchange_type = exchange_config.type

    # Extract exchange arguments
    arguments: dict[str, Any] = {}
    if (
        exchange_config
        and hasattr(exchange_config, "arguments")
        and exchange_config.arguments
    ):
        arguments = exchange_config.arguments

    # Extract binding arguments for headers exchange from dataclass
    binding_args: dict[str, Any] = {}
    # Note: bindingKeys is not part of AmqpChannelBinding spec
    # This would be handled by operation-level bindings if needed

    return AmqpConfig(
        queue_name="",  # Auto-generated exclusive queue
        exchange_name=resolved_exchange,
        exchange_type=exchange_type,
        routing_key="",  # No routing key for fanout/headers exchanges
        binding_type=AmqpBindingType.EXCHANGE,
        queue_properties={"durable": False, "exclusive": True, "auto_delete": True},
        binding_arguments=binding_args,
        arguments=arguments,
    )
