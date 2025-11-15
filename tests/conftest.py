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
import re
from os import environ
from typing import Generator

import pytest

from asyncapi_python.contrib.wire.in_memory import reset_bus
from asyncapi_python.kernel.document.bindings import AmqpChannelBinding
from asyncapi_python.kernel.document.channel import (
    AddressParameter,
    Channel,
    ChannelBindings,
)


@pytest.fixture(scope="session")
def amqp_uri() -> str:
    if env_uri := environ.get("PYTEST_AMQP_URI"):
        return env_uri
    return "amqp://guest:guest@localhost:5672/"


@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_in_memory_bus() -> Generator[None, None, None]:
    """Auto-reset the in-memory bus between tests"""
    reset_bus()
    yield
    reset_bus()


class PytestHelpers:
    """Test helper functions available via pytest.helpers"""

    @staticmethod
    def create_test_channel(
        address: str | None = None,
        binding: AmqpChannelBinding | None = None,
    ) -> Channel:
        """Create a minimal test channel with required fields.

        Automatically extracts parameters from address template (e.g., {location}).
        """
        bindings = None
        if binding:
            bindings = ChannelBindings(amqp=binding)

        # Extract parameters from address template
        parameters = {}
        if address:
            param_names = re.findall(r"\{(\w+)\}", address)
            for param_name in param_names:
                parameters[param_name] = AddressParameter(
                    key=param_name,
                    description=f"Test parameter {param_name}",
                    location=None,
                )

        return Channel(
            key="test_channel",
            address=address,
            title=None,
            summary=None,
            description=None,
            servers=[],
            messages={},
            parameters=parameters,
            tags=[],
            external_docs=None,
            bindings=bindings,
        )


# Register helpers
pytest.helpers = PytestHelpers()  # type: ignore
