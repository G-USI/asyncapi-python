import asyncio
from os import environ
from client import Application
from client.models import Ping, Pong


AMQP_URI = environ.get("AMQP_URI", "amqp://guest:guest@localhost")
NUM_REQUESTS = 3

app = Application(AMQP_URI)


async def main() -> None:
    await app.start(blocking=False)
    for _ in range(NUM_REQUESTS):
        req = Ping()
        print(f"Sending request: {req}")
        res: Pong = await app.ping_request(req)
        print(f"Got response: {res}")


if __name__ == "__main__":
    asyncio.run(main())
