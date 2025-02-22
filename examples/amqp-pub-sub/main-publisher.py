import asyncio
from os import environ
from publisher import Application
from publisher.messages import Ping


AMQP_URI = environ.get("AMQP_URI", "amqp://guest:guest@localhost")
NUM_REQUESTS = 3

app = Application(AMQP_URI)


async def main() -> None:
    await app.start(blocking=False)
    for _ in range(NUM_REQUESTS):
        req = Ping()
        print(f"Sending request: {req}")
        await app.producer.application.ping(req)


if __name__ == "__main__":
    asyncio.run(main())
