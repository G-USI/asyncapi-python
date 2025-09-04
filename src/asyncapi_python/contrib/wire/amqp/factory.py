"""AMQP wire factory implementation"""

from typing_extensions import Unpack

from aio_pika import connect_robust
from aio_pika.abc import AbstractRobustConnection

from asyncapi_python.kernel.wire import AbstractWireFactory, EndpointParams
from asyncapi_python.kernel.wire.typing import Producer, Consumer

from .message import AmqpWireMessage, AmqpIncomingMessage
from .producer import AmqpProducer
from .consumer import AmqpConsumer
from .resolver import resolve_amqp_config


class AmqpWire(AbstractWireFactory[AmqpWireMessage, AmqpIncomingMessage]):
    """AMQP wire factory implementation with comprehensive binding support"""

    def __init__(
        self,
        connection_url: str,
        app_id: str | None = None,
    ):
        self._connection_url = connection_url
        self._app_id = app_id
        self._connection: AbstractRobustConnection | None = None

    async def _get_connection(self) -> AbstractRobustConnection:
        """Get or create connection"""
        if self._connection is None or self._connection.is_closed:
            self._connection = await connect_robust(self._connection_url)
        return self._connection

    async def create_consumer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Consumer[AmqpIncomingMessage]:
        """
        Create an AMQP consumer using comprehensive binding resolution.

        Args:
            **kwargs: EndpointParams with channel, parameters, bindings, etc.
        """
        # Generate operation name from available information
        operation_name = self._generate_operation_name(kwargs)

        # Resolve AMQP configuration using pattern matching
        config = resolve_amqp_config(kwargs, operation_name, self._app_id)

        connection = await self._get_connection()

        return AmqpConsumer(connection=connection, **config.to_consumer_args())

    async def create_producer(
        self, **kwargs: Unpack[EndpointParams]
    ) -> Producer[AmqpWireMessage]:
        """
        Create an AMQP producer using comprehensive binding resolution.

        Args:
            **kwargs: EndpointParams with channel, parameters, bindings, etc.
        """
        # Generate operation name from available information
        operation_name = self._generate_operation_name(kwargs)

        # Resolve AMQP configuration using pattern matching
        config = resolve_amqp_config(kwargs, operation_name, self._app_id)

        connection = await self._get_connection()

        return AmqpProducer(connection=connection, **config.to_producer_args())

    def _generate_operation_name(self, params: EndpointParams) -> str:
        """Generate operation name from available endpoint parameters"""
        channel = params["channel"]

        # Use channel address if available
        if channel.address:
            return channel.address

        # Use channel title if available
        if channel.title:
            return channel.title

        # Use first message name if available
        if channel.messages:
            first_msg_name = next(iter(channel.messages.keys()))
            return f"op-{first_msg_name}"

        # Last resort - generate from app_id
        return f"op-{self._app_id}" if self._app_id else "op-default"

    async def close(self) -> None:
        """Close the connection"""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
