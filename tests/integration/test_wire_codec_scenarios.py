"""Integration tests for wire+codec+scenario combinations"""

from typing import Awaitable, Callable
import pytest

from asyncapi_python.kernel.wire import AbstractWireFactory
from asyncapi_python.kernel.codec import CodecFactory
from asyncapi_python.contrib.wire.in_memory import InMemoryWireFactory
from asyncapi_python.contrib.wire.amqp import AmqpWireFactory
from asyncapi_python.contrib.codec.json import JsonCodecFactory

from .scenarios import (
    producer_consumer_roundtrip,
    reply_channel_creation,
    error_handling,
    malformed_message_handling,
)

# Import test app module
from . import test_app


# Wire implementations
IN_MEMORY_WIRE = InMemoryWireFactory()
AMQP_WIRE = AmqpWireFactory(
    connection_url="amqp://guest:guest@rabbitmq:5672/", app_id="test-integration"
)

# Codec implementations
JSON_CODEC = JsonCodecFactory(test_app)


# Parametrized integration test - crossproduct of wire × codec × scenario
@pytest.mark.parametrize("wire", [IN_MEMORY_WIRE, AMQP_WIRE])
@pytest.mark.parametrize("codec", [JSON_CODEC])
@pytest.mark.parametrize(
    "scenario",
    [
        producer_consumer_roundtrip,
        reply_channel_creation,
        error_handling,
        malformed_message_handling,
    ],
)
@pytest.mark.asyncio
async def test_wire_codec_scenario(
    wire: AbstractWireFactory,
    codec: CodecFactory,
    scenario: Callable[[AbstractWireFactory, CodecFactory], Awaitable[None]],
) -> None:
    """Test all combinations of wire, codec, and scenario"""
    await scenario(wire, codec)
