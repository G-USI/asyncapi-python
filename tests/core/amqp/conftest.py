from asyncapi_python.amqp import Producer, Consumer, AmqpPool
import pytest_asyncio


@pytest_asyncio.fixture(scope="function")
async def producer(amqp_pool: AmqpPool) -> Producer:
    async with amqp_pool.acquire() as channel:
        queue = await channel.declare_queue(exclusive=True)
    return Producer(channel_pool=amqp_pool, reply_queue=queue)


@pytest_asyncio.fixture(scope="function")
async def consumer(amqp_pool: AmqpPool) -> Consumer:
    return Consumer(channel_pool=amqp_pool)
