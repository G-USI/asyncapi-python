# Copyright 2025 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import asyncio
from os import environ
from typing import Generator
import pytest
from pydantic import BaseModel

from asyncapi_python.contrib.codec.json import JsonCodecFactory
from asyncapi_python.contrib.wire.in_memory import InMemoryWireFactory, reset_bus
from asyncapi_python.kernel.document.message import Message
from asyncapi_python.kernel.document.operation import Operation, OperationReply
from asyncapi_python.kernel.document.channel import Channel


@pytest.fixture(scope="session")
def amqp_uri() -> str:
    if env_uri := environ.get("AMQP_URI"):
        return env_uri
    return "amqp://guest:guest@rabbitmq/"


@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Test Models - used across test modules  
class UserModel(BaseModel):
    name: str
    age: int
    email: str


class OrderModel(BaseModel):
    id: str
    amount: float
    user_id: str


@pytest.fixture
def sample_user_data() -> dict[str, str | int]:
    return {"name": "John Doe", "age": 30, "email": "john@example.com"}


@pytest.fixture
def sample_order_data() -> dict[str, str | float]:
    return {"id": "order-123", "amount": 99.99, "user_id": "user-456"}


# Mock AsyncAPI Document Objects
@pytest.fixture
def mock_user_message() -> Message:
    return Message(
        name="user.created",
        title="User Created",
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        payload={"type": "object"},  # Simple schema
        content_type="application/json",
        headers=None,
        deprecated=None,
        correlation_id=None,
        bindings=None,
        traits=[]
    )


@pytest.fixture
def mock_order_message() -> Message:
    return Message(
        name="order.placed",
        title="Order Placed",
        summary=None,
        description=None,
        tags=[],
        externalDocs=None,
        payload={"type": "object"},  # Simple schema
        content_type="application/json",
        headers=None,
        deprecated=None,
        correlation_id=None,
        bindings=None,
        traits=[]
    )


@pytest.fixture
def mock_channel() -> Channel:
    from asyncapi_python.kernel.document.channel import ChannelBindings
    return Channel(
        address="test.channel",
        title=None,
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters={},
        tags=[],
        external_docs=None,
        bindings=ChannelBindings()
    )


@pytest.fixture
def mock_operation(mock_user_message: Message, mock_channel: Channel) -> Operation:
    return Operation(
        action="send",
        channel=mock_channel,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        bindings=None,
        traits=[],
        messages=[mock_user_message],
        reply=None,
        security=[]
    )


@pytest.fixture
def mock_operation_with_reply(mock_user_message: Message, mock_order_message: Message, mock_channel: Channel) -> Operation:
    reply = OperationReply(
        address=None,
        channel=mock_channel,
        messages=[mock_order_message]
    )
    return Operation(
        action="send",
        channel=mock_channel,
        title=None,
        summary=None,
        description=None,
        tags=[],
        external_docs=None,
        bindings=None,
        traits=[],
        messages=[mock_user_message],
        reply=reply,
        security=[]
    )


# Mock module for codec factory
class MockMessagesJson:
    # Define test models directly here
    class UserCreated(BaseModel):
        name: str
        age: int
        email: str
    
    class OrderPlaced(BaseModel):
        id: str
        amount: float
        user_id: str


class MockMessages:
    json = MockMessagesJson()


class MockModule:
    messages = MockMessages()


@pytest.fixture
def mock_module() -> MockModule:
    return MockModule()


@pytest.fixture
def json_codec_factory(mock_module: MockModule) -> JsonCodecFactory:
    return JsonCodecFactory(mock_module)


@pytest.fixture
def in_memory_wire_factory() -> InMemoryWireFactory:
    # Reset bus before each test
    reset_bus()
    return InMemoryWireFactory()


@pytest.fixture(autouse=True)
def reset_in_memory_bus() -> Generator[None, None, None]:
    """Auto-reset the in-memory bus between tests"""
    reset_bus()
    yield
    reset_bus()
