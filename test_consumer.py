from out import Consumer
from out.messages import TestMessage, TestNotification
import asyncio

amqp_uri = "amqp://guest:guest@rabbitmq/"

consumer = asyncio.run(Consumer.create(amqp_uri=amqp_uri))


@consumer.test_notifier
async def nt(x: TestNotification):
    print("Got {x}")


@consumer.test_work_queue
async def wk(x: TestMessage):
    print("Got {x}")


if __name__ == "__main__":
    asyncio.run(consumer.run())
