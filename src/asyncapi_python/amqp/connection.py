from functools import cache
from aio_pika.robust_connection import (
    AbstractRobustConnection,
    AbstractRobustChannel,
    connect_robust,
)
from aio_pika.pool import Pool


@cache
def connection_pool(amqp_uri: str) -> Pool[AbstractRobustConnection]:
    async def get_connection():
        return await connect_robust(amqp_uri)

    return Pool(get_connection, max_size=2)


@cache
def channel_pool(amqp_uri: str) -> Pool[AbstractRobustChannel]:
    async def get_channel():
        async with connection_pool(amqp_uri).acquire() as connection:
            return await connection.channel()

    return Pool(get_channel, max_size=10)
