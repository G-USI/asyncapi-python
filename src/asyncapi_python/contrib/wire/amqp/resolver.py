"""Binding resolution with comprehensive pattern matching"""

from typing import Any

from asyncapi_python.kernel.wire import EndpointParams
from asyncapi_python.kernel.document.channel import Channel

from .config import AmqpConfig, AmqpBindingType
from .utils import validate_parameters_strict, substitute_parameters


def resolve_amqp_config(
    params: EndpointParams, operation_name: str, app_id: str | None = None
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

    # Strict parameter validation first
    validate_parameters_strict(channel, param_values)

    # Extract AMQP binding if present
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

        # Reply channel pattern (highest precedence)
        case (True, _, _, _):
            return AmqpConfig(
                queue_name=f"reply-queue-{app_id}" if app_id else "reply-queue-default",
                exchange_name="",  # Always default exchange for reply
                routing_key=(
                    f"reply-queue-{app_id}" if app_id else "reply-queue-default"
                ),
                binding_type=AmqpBindingType.REPLY,
                queue_properties={"durable": True, "exclusive": False},
            )

        # AMQP queue binding pattern
        case (False, binding, _, _) if (
            binding and hasattr(binding, "type") and binding.type == "queue"
        ):
            return resolve_queue_binding(binding, param_values, channel, operation_name)

        # AMQP routing key binding pattern
        case (False, binding, _, _) if (
            binding and hasattr(binding, "type") and binding.type == "routingKey"
        ):
            return resolve_routing_key_binding(
                binding, param_values, channel, operation_name
            )

        # AMQP exchange binding pattern - detect by presence of exchange field
        case (False, binding, _, _) if (
            binding and (hasattr(binding, "exchange") or (isinstance(binding, dict) and "exchange" in binding))
        ):
            return resolve_exchange_binding(
                binding, param_values, channel, operation_name, channel.key
            )

        # Channel address pattern (with parameter substitution)
        case (False, None, address, _) if address:
            resolved_address = substitute_parameters(address, param_values)
            return AmqpConfig(
                queue_name=resolved_address,
                exchange_name="",  # Default exchange
                routing_key=resolved_address,
                binding_type=AmqpBindingType.QUEUE,
                queue_properties={"durable": True, "exclusive": False},
            )

        # Operation name pattern (fallback)
        case (False, None, None, op_name) if op_name:
            return AmqpConfig(
                queue_name=op_name,
                exchange_name="",  # Default exchange
                routing_key=op_name,
                binding_type=AmqpBindingType.QUEUE,
                queue_properties={"durable": True, "exclusive": False},
            )

        # No match - reject creation
        case _:
            raise ValueError(
                f"Cannot resolve AMQP binding: no valid configuration found. "
                f"Channel: {channel.address}, Binding: {amqp_binding}, Operation: {operation_name}"
            )


def resolve_queue_binding(
    binding: Any, param_values: dict[str, str], channel: Channel, operation_name: str
) -> AmqpConfig:
    """Resolve AMQP queue binding configuration"""

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
    if queue_config:
        if hasattr(queue_config, "durable"):
            queue_properties["durable"] = queue_config.durable
        if hasattr(queue_config, "exclusive"):
            queue_properties["exclusive"] = queue_config.exclusive
        if hasattr(queue_config, "auto_delete"):
            queue_properties["auto_delete"] = queue_config.auto_delete

    return AmqpConfig(
        queue_name=queue_name,
        exchange_name="",  # Queue bindings use default exchange
        routing_key=queue_name,  # For default exchange, routing_key = queue_name
        binding_type=AmqpBindingType.QUEUE,
        queue_properties=queue_properties,
    )


def resolve_routing_key_binding(
    binding: Any, param_values: dict[str, str], channel: Channel, operation_name: str
) -> AmqpConfig:
    """Resolve AMQP routing key binding configuration for pub/sub patterns"""

    # Determine exchange name and type
    exchange_config = getattr(binding, "exchange", None)
    match (
        exchange_config and getattr(exchange_config, "name", None),
        channel.address,
        operation_name,
    ):
        case (exchange_name, _, _) if exchange_name:
            resolved_exchange = substitute_parameters(exchange_name, param_values)
        case (None, address, _) if address:
            resolved_exchange = substitute_parameters(address, param_values)
        case (None, None, op_name) if op_name:
            resolved_exchange = op_name
        case _:
            raise ValueError("Cannot determine exchange name for routing key binding")

    # Determine exchange type
    exchange_type = "topic"  # Default for routing key bindings
    if exchange_config and hasattr(exchange_config, "type"):
        exchange_type = exchange_config.type

    # Determine routing key
    match (getattr(binding, "routingKey", None), channel.address, operation_name):
        case (routing_key, _, _) if routing_key:
            resolved_routing_key = substitute_parameters(routing_key, param_values)
        case (None, address, _) if address:
            resolved_routing_key = substitute_parameters(address, param_values)
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
    )


def resolve_exchange_binding(
    binding: Any, param_values: dict[str, str], channel: Channel, operation_name: str, channel_key: str = ""
) -> AmqpConfig:
    """Resolve AMQP exchange binding configuration for advanced pub/sub"""

    # Determine exchange name with proper fallback chain
    # Handle both object attributes and dictionary keys
    if isinstance(binding, dict):
        exchange_config = binding.get("exchange")
    else:
        exchange_config = getattr(binding, "exchange", None)
    # Extract exchange name from config (handle both dict and object)
    exchange_name = None
    if exchange_config:
        if isinstance(exchange_config, dict):
            exchange_name = exchange_config.get("name")
        else:
            exchange_name = getattr(exchange_config, "name", None)
    
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

    # Determine exchange type
    exchange_type = "fanout"  # Default for exchange bindings
    if exchange_config:
        if isinstance(exchange_config, dict):
            exchange_type = exchange_config.get("type", "fanout")
        elif hasattr(exchange_config, "type"):
            exchange_type = exchange_config.type

    # Extract binding arguments for headers exchange
    binding_args = {}
    if isinstance(binding, dict):
        binding_args = binding.get("bindingKeys", {})
    elif hasattr(binding, "bindingKeys") and binding.bindingKeys:
        binding_args = binding.bindingKeys

    return AmqpConfig(
        queue_name="",  # Auto-generated exclusive queue
        exchange_name=resolved_exchange,
        exchange_type=exchange_type,
        routing_key="",  # No routing key for fanout/headers exchanges
        binding_type=AmqpBindingType.EXCHANGE,
        queue_properties={"durable": False, "exclusive": True, "auto_delete": True},
        binding_arguments=binding_args,
    )
