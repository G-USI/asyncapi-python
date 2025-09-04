import asyncio
from os import environ
from publisher import Application
from publisher.messages.json import Ping
from asyncapi_python.contrib.wire.amqp import AmqpWire


AMQP_URI = environ.get("AMQP_URI", "amqp://guest:guest@localhost")
NUM_REQUESTS = 3

app = Application(AmqpWire(AMQP_URI))


async def main() -> None:
    await app.start()
    for _ in range(NUM_REQUESTS):
        req = Ping()
        print(f"Sending request: {req}")
        await app.producer.application_ping(req)
    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
