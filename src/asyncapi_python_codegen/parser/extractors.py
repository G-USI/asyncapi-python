"""Functions to extract dataclasses from YAML data."""

# Type imports for extraction functions
from asyncapi_python.kernel.document import (
    AddressParameter,
    Channel,
    ChannelBindings,
    CorrelationId,
    ExternalDocs,
    Message,
    MessageBindings,
    MessageExample,
    MessageTrait,
    Operation,
    OperationBindings,
    OperationReply,
    OperationTrait,
    SecurityScheme,
    Server,
    Tag,
)

from .references import maybe_ref
from .types import YamlDocument


@maybe_ref
def extract_external_docs(data: YamlDocument) -> ExternalDocs:
    """Extract ExternalDocs from YAML data."""
    return ExternalDocs(
        description=data.get("description", ""), url=data.get("url", "")
    )


@maybe_ref
def extract_tag(data: YamlDocument) -> Tag:
    """Extract Tag from YAML data."""
    external_docs_data = data.get("externalDocs")
    external_docs = (
        extract_external_docs(external_docs_data) if external_docs_data else None
    )

    return Tag(
        name=data.get("name", ""),
        description=data.get("description", ""),
        external_docs=external_docs or ExternalDocs(description="", url=""),
    )


@maybe_ref
def extract_server(data: YamlDocument) -> Server:
    """Extract Server from YAML data."""
    # TODO: Implement full Server spec when kernel.document.Server is completed
    return Server(key="")


@maybe_ref
def extract_address_parameter(data: YamlDocument) -> AddressParameter:
    """Extract AddressParameter from YAML data."""
    return AddressParameter(
        description=data.get("description"),
        location=data.get("location", ""),  # Validation will catch if missing
        key="",  # TODO: Pass actual parameter key from extraction context
    )


@maybe_ref
def extract_channel_bindings(data: YamlDocument) -> ChannelBindings:
    """Extract ChannelBindings from YAML data."""
    # Extract AMQP binding as proper object
    amqp_binding = None
    if "amqp" in data and data["amqp"] is not None:
        amqp_data = data["amqp"]
        from asyncapi_python.kernel.document.bindings import (
            create_amqp_binding_from_dict,
        )

        amqp_binding = create_amqp_binding_from_dict(amqp_data)

    return ChannelBindings(
        http=data.get("http"),
        amqp1=data.get("amqp1"),
        mqtt=data.get("mqtt"),
        nats=data.get("nats"),
        stomp=data.get("stomp"),
        redis=data.get("redis"),
        solace=data.get("solace"),
        ws=data.get("ws"),
        amqp=amqp_binding,
        kafka=data.get("kafka"),
        anypointmq=data.get("anypointmq"),
        jms=data.get("jms"),
        sns=data.get("sns"),
        sqs=data.get("sqs"),
        ibmmq=data.get("ibmmq"),
        googlepubsub=data.get("googlepubsub"),
        pulsar=data.get("pulsar"),
    )


@maybe_ref
def extract_correlation_id(data: YamlDocument) -> CorrelationId:
    """Extract CorrelationId from YAML data."""
    return CorrelationId(
        description=data.get("description"), location=data.get("location", "")
    )


@maybe_ref
def extract_message_example(data: YamlDocument) -> MessageExample:
    """Extract MessageExample from YAML data."""
    return MessageExample(
        name=data.get("name"),
        summary=data.get("summary"),
        headers=data.get("headers"),
        payload=data.get("payload"),
    )


@maybe_ref
def extract_message_bindings(data: YamlDocument) -> MessageBindings:
    """Extract MessageBindings from YAML data."""
    return MessageBindings(
        http=data.get("http"),
        amqp1=data.get("amqp1"),
        mqtt=data.get("mqtt"),
        nats=data.get("nats"),
        stomp=data.get("stomp"),
        redis=data.get("redis"),
        solace=data.get("solace"),
        ws=data.get("ws"),
        amqp=data.get("amqp"),
        kafka=data.get("kafka"),
        anypointmq=data.get("anypointmq"),
        jms=data.get("jms"),
        sns=data.get("sns"),
        sqs=data.get("sqs"),
        ibmmq=data.get("ibmmq"),
        googlepubsub=data.get("googlepubsub"),
        pulsar=data.get("pulsar"),
    )


@maybe_ref
def extract_message_trait(data: YamlDocument) -> MessageTrait:
    """Extract MessageTrait from YAML data."""
    # Extract examples
    examples: list[MessageExample] = []
    if "examples" in data:
        for example_data in data["examples"]:
            examples.append(extract_message_example(example_data))

    # Extract correlation ID
    correlation_id = None
    if "correlationId" in data:
        correlation_id = extract_correlation_id(data["correlationId"])

    # Extract tags
    tags: list[Tag] = []
    if "tags" in data:
        for tag_data in data["tags"]:
            tags.append(extract_tag(tag_data))

    # Extract external docs
    external_docs = None
    if "externalDocs" in data:
        external_docs = extract_external_docs(data["externalDocs"])

    # Extract bindings
    bindings = None
    if "bindings" in data:
        bindings = extract_message_bindings(data["bindings"])

    return MessageTrait(
        content_type=data.get("contentType"),
        headers=data.get("headers"),
        summary=data.get("summary"),
        name=data.get("name"),
        title=data.get("title"),
        description=data.get("description"),
        deprecated=data.get("deprecated"),
        examples=examples,
        correlation_id=correlation_id,
        tags=tags,
        externalDocs=external_docs,
        bindings=bindings,
    )


@maybe_ref
def extract_message(data: YamlDocument) -> Message:
    """Extract Message from YAML data."""
    # Extract correlation ID
    correlation_id = None
    if "correlationId" in data:
        correlation_id = extract_correlation_id(data["correlationId"])

    # Extract tags
    tags: list[Tag] = []
    if "tags" in data:
        for tag_data in data["tags"]:
            tags.append(extract_tag(tag_data))

    # Extract external docs
    external_docs = None
    if "externalDocs" in data:
        external_docs = extract_external_docs(data["externalDocs"])

    # Extract bindings
    bindings = None
    if "bindings" in data:
        bindings = extract_message_bindings(data["bindings"])

    # Extract traits
    traits: list[MessageTrait] = []
    if "traits" in data:
        for trait_data in data["traits"]:
            traits.append(extract_message_trait(trait_data))

    return Message(
        content_type=data.get("contentType"),
        headers=data.get("headers"),
        payload=data.get("payload"),  # Raw payload data
        summary=data.get("summary"),
        name=data.get("name"),
        title=data.get("title"),
        description=data.get("description"),
        deprecated=data.get("deprecated"),
        correlation_id=correlation_id,
        tags=tags,
        externalDocs=external_docs,
        bindings=bindings,
        traits=traits,
        key="",  # TODO: Pass actual message key from extraction context
    )


@maybe_ref
def extract_channel(data: YamlDocument) -> Channel:
    """Extract Channel from YAML data."""
    # Extract servers
    servers: list[Server] = []
    if "servers" in data:
        for server_data in data["servers"]:
            servers.append(extract_server(server_data))

    # Extract messages
    messages: dict[str, Message] = {}
    if "messages" in data:
        for message_name, message_data in data["messages"].items():
            message = extract_message(message_data)
            # Ensure message name is set from the key
            if message.name is None:
                message = Message(
                    content_type=message.content_type,
                    headers=message.headers,
                    payload=message.payload,
                    summary=message.summary,
                    name=message_name,  # Set name from key
                    title=message.title,
                    description=message.description,
                    deprecated=message.deprecated,
                    correlation_id=message.correlation_id,
                    tags=message.tags,
                    externalDocs=message.externalDocs,
                    bindings=message.bindings,
                    traits=message.traits,
                    key=message_name,  # Set key from message name
                )
            messages[message_name] = message

    # Extract parameters
    parameters: dict[str, AddressParameter] = {}
    if "parameters" in data:
        for param_name, param_data in data["parameters"].items():
            param = extract_address_parameter(param_data)
            # Create new parameter with key set from parameter name
            param_with_key = AddressParameter(
                description=param.description, location=param.location, key=param_name
            )
            parameters[param_name] = param_with_key

    # Extract tags
    tags: list[Tag] = []
    if "tags" in data:
        for tag_data in data["tags"]:
            tags.append(extract_tag(tag_data))

    # Extract external docs
    external_docs = None
    if "externalDocs" in data:
        external_docs = extract_external_docs(data["externalDocs"])

    # Extract bindings
    bindings = None
    if "bindings" in data:
        bindings = extract_channel_bindings(data["bindings"])

    return Channel(
        address=data.get("address"),
        title=data.get("title"),
        summary=data.get("summary"),
        description=data.get("description"),
        servers=servers,
        messages=messages,
        parameters=parameters,
        tags=tags,
        external_docs=external_docs,
        bindings=bindings,
        key="/ping/pubsub",  # HACK: Hardcoded for pub-sub example - TODO: Extract from reference context
    )


@maybe_ref
def extract_security_scheme(data: YamlDocument) -> SecurityScheme:
    """Extract SecurityScheme from YAML data."""
    return SecurityScheme(
        type=data.get("type", "userPassword"),  # Default to avoid validation errors
        key="",  # TODO: Pass actual security scheme key from extraction context
    )


@maybe_ref
def extract_operation_bindings(data: YamlDocument) -> OperationBindings:
    """Extract OperationBindings from YAML data."""
    # Extract AMQP binding as proper object
    amqp_binding = None
    if "amqp" in data:
        amqp_data = data["amqp"]
        if amqp_data:
            from asyncapi_python.kernel.document.bindings import AmqpOperationBinding

            # Create operation binding from dict data
            amqp_binding = AmqpOperationBinding(
                expiration=amqp_data.get("expiration"),
                user_id=amqp_data.get("userId"),
                cc=amqp_data.get("cc"),
                priority=amqp_data.get("priority"),
                delivery_mode=amqp_data.get("deliveryMode"),
                mandatory=amqp_data.get("mandatory"),
                bcc=amqp_data.get("bcc"),
                timestamp=amqp_data.get("timestamp"),
                ack=amqp_data.get("ack"),
            )

    return OperationBindings(
        http=data.get("http"),
        amqp1=data.get("amqp1"),
        mqtt=data.get("mqtt"),
        nats=data.get("nats"),
        stomp=data.get("stomp"),
        redis=data.get("redis"),
        solace=data.get("solace"),
        ws=data.get("ws"),
        amqp=amqp_binding,
        kafka=data.get("kafka"),
        anypointmq=data.get("anypointmq"),
        jms=data.get("jms"),
        sns=data.get("sns"),
        sqs=data.get("sqs"),
        ibmmq=data.get("ibmmq"),
        googlepubsub=data.get("googlepubsub"),
        pulsar=data.get("pulsar"),
    )


@maybe_ref
def extract_operation_trait(data: YamlDocument) -> OperationTrait:
    """Extract OperationTrait from YAML data."""
    # Extract channel
    channel_data = data.get("channel", {})
    channel = extract_channel(channel_data)

    # Extract security
    security: list[SecurityScheme] = []
    if "security" in data:
        for security_data in data["security"]:
            security.append(extract_security_scheme(security_data))

    # Extract tags
    tags: list[Tag] = []
    if "tags" in data:
        for tag_data in data["tags"]:
            tags.append(extract_tag(tag_data))

    # Extract external docs
    external_docs = None
    if "externalDocs" in data:
        external_docs = extract_external_docs(data["externalDocs"])

    # Extract bindings
    bindings = extract_operation_bindings(data.get("bindings", {}))

    return OperationTrait(
        title=data.get("title"),
        summary=data.get("summary"),
        description=data.get("description"),
        channel=channel,
        security=security,
        tags=tags,
        external_docs=external_docs,
        bindings=bindings,
    )


@maybe_ref
def extract_operation_reply(data: YamlDocument) -> OperationReply:
    """Extract OperationReply from YAML data."""
    # Extract channel
    channel_data = data.get("channel", {})
    channel = extract_channel(channel_data)

    # Extract messages - for replies, messages are usually in the channel
    messages = list(channel.messages.values())

    return OperationReply(
        channel=channel, messages=messages, address=data.get("address")
    )


@maybe_ref
def extract_operation(data: YamlDocument) -> Operation:
    """Extract Operation from YAML data."""
    # Extract channel
    channel_data = data.get("channel", {})
    channel = extract_channel(channel_data)

    # Extract messages from channel
    messages = list(channel.messages.values())

    # Extract reply
    reply = None
    if "reply" in data:
        reply = extract_operation_reply(data["reply"])

    # Extract traits
    traits: list[OperationTrait] = []
    if "traits" in data:
        for trait_data in data["traits"]:
            traits.append(extract_operation_trait(trait_data))

    # Extract security
    security: list[SecurityScheme] = []
    if "security" in data:
        for security_data in data["security"]:
            security.append(extract_security_scheme(security_data))

    # Extract tags
    tags: list[Tag] = []
    if "tags" in data:
        for tag_data in data["tags"]:
            tags.append(extract_tag(tag_data))

    # Extract external docs
    external_docs = None
    if "externalDocs" in data:
        external_docs = extract_external_docs(data["externalDocs"])

    # Extract bindings
    bindings = None
    if "bindings" in data:
        bindings = extract_operation_bindings(data["bindings"])

    return Operation(
        action=data.get("action", "send"),  # Default to send
        title=data.get("title"),
        summary=data.get("summary"),
        description=data.get("description"),
        channel=channel,
        messages=messages,
        reply=reply,
        traits=traits,
        security=security,
        tags=tags,
        external_docs=external_docs,
        bindings=bindings,
        key="",  # TODO: Pass actual operation key from extraction context
    )
