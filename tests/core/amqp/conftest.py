# Copyright 2024-2025 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
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


from asyncapi_python.amqp import AmqpPool, channel_pool
import pytest_asyncio
from typing import AsyncGenerator


@pytest_asyncio.fixture(scope="function")
async def amqp_pool(amqp_uri: str) -> AsyncGenerator[AmqpPool, None]:
    channel_pool.cache_clear()
    pool = channel_pool(amqp_uri)
    yield pool
