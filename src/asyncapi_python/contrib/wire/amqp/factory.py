"""AMQP wire factory implementation"""

import secrets
from typing import Any, Callable, Optional, cast

from typing_extensions import Unpack

try:
    from aio_pika import connect, connect_robust  # type: ignore[import-not-found]
    from aio_pika.abc import AbstractConnection  # type: ignore[import-not-found]
except ImportError as e:
    raise ImportError(
        "aio-pika is required for AMQP support. Install with: pip install asyncapi-python[amqp]"
    ) from e

from asyncapi_python.kernel.wire import AbstractWireFactory, EndpointParams
from asyncapi_python.kernel.wire.typing import Consumer, Producer

from .consumer import AmqpConsumer
from .message import AmqpIncomingMessage, AmqpWireMessage
from .producer import AmqpProducer
from .resolver import resolve_amqp_config


class AmqpWire(AbstractWireFactory[AmqpWireMessage, AmqpIncomingMessage]):
    """AMQP wire factory implementation with configurable connection robustness.

    By default, connections fail fast (for Kubernetes environments).
    Set robust=True to enable automatic reconnection with exponential backoff.
    """

    def __init__(
        self,
        connection_url: str,
        robust: bool = False,
        reconnect_interval: float = 1.0,
        max_reconnect_interval: float = 60.0,
        connection_attempts: int = 3,
        heartbeat: Optional[int] = 60,
        connection_timeout: Optional[float] = 10.0,
        on_connection_lost: Optional[Callable[[Exception], Any]] = None,
    ):
        """
        Initialize AMQP wire factory.

        Args:
            connection_url: AMQP connection URL
            robust: Enable robust connection with auto-reconnect (default: False)
            reconnect_interval: Initial reconnect interval in seconds (for robust mode)
            max_reconnect_interval: Maximum reconnect interval in seconds (for robust mode)
            connection_attempts: Number of connection attempts before giving up
            heartbeat: Heartbeat interval in seconds (None to disable)
            connection_timeout: Connection timeout in seconds
            on_connection_lost: Callback when connection is lost (for non-robust mode)
        """
        self._connection_url = connection_url
        # Generate fallback app_id with random hex characters
        # Note: For RPC, app_id should be provided via EndpointParams from application level
        random_hex = secrets.token_hex(4)  # 4 bytes = 8 hex chars
        self._app_id = f"wire-{random_hex}"
        self._connection: AbstractConnection | None = None
        self._robust = robust
        self._reconnect_interval = reconnect_interval
        self._max_reconnect_interval = max_reconnect_interval
        self._connection_attempts = connection_attempts
        self._heartbeat = heartbeat
        self._connection_timeout = connection_timeout
        self._on_connection_lost = on_connection_lost

    @property
    def app_id(self) -> str:
        """Get the generated app_id for this wire instance"""
        return self._app_id

    async def _get_connection(self) -> AbstractConnection:
        """Get or create connection with configurable robustness"""
        if self._connection is None or self._connection.is_closed:
            if self._robust:
                # Use robust connection with automatic reconnection
                self._connection = await connect_robust(
                    self._connection_url,
                    reconnect_interval=self._reconnect_interval,
                    connection_attempts=self._connection_attempts,
                    heartbeat=self._heartbeat,
                    timeout=self._connection_timeout,
                )
            else:
                # Use standard connection that fails fast
                try:
                    self._connection = await connect(
                        self._connection_url,
                        heartbeat=self._heartbeat,
                        timeout=self._connection_timeout,
                    )

                    # Set up connection lost handler for non-robust mode
                    if self._on_connection_lost:
                        self._connection.close_callbacks.add(
                            cast(Any, self._handle_connection_lost)
                        )

                except Exception as e:
                    # In non-robust mode, let connection failures propagate
                    # This allows Kubernetes to restart the pod
                    raise ConnectionError(
                        f"Failed to connect to AMQP broker: {e}"
                    ) from e

        return self._connection

    def _handle_connection_lost(
        self, connection: AbstractConnection, exception: Optional[BaseException] = None
    ) -> None:
        """Handle connection lost event in non-robust mode"""
        if self._on_connection_lost and exception and isinstance(exception, Exception):
            self._on_connection_lost(exception)
        else:
            # Default behavior: let the process die for Kubernetes restart
            if exception:
                raise ConnectionError(
                    f"AMQP connection lost: {exception}"
                ) from exception
            else:
                raise ConnectionError("AMQP connection lost unexpectedly")

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

        # Use provided app_id if available, otherwise use instance app_id
        # This allows application-level control over queue naming
        app_id = kwargs.get("app_id", self._app_id)

        # Resolve AMQP configuration using pattern matching
        config = resolve_amqp_config(kwargs, operation_name, app_id)

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

        # Use provided app_id if available, otherwise use instance app_id
        # This allows application-level control over queue naming
        app_id = kwargs.get("app_id", self._app_id)

        # Resolve AMQP configuration using pattern matching
        config = resolve_amqp_config(kwargs, operation_name, app_id)

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
