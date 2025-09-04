import asyncio
from os import environ
from sys import exit
from server import Application
from server.messages.json import Ping, Pong
from asyncapi_python.contrib.wire.amqp import AmqpWire


AMQP_URI = environ.get("AMQP_URI", "amqp://guest:guest@localhost")
MAX_REQUESTS = 3
request_count = 0

app = Application(AmqpWire(AMQP_URI))


@app.consumer.onpingrequest
async def handle_ping_request(msg: Ping) -> Pong:
    global request_count
    print(f"Handling request: {msg}")
    res = Pong()
    print(f"Returning response: {res}")
    request_count += 1
    return res


async def termination_handler():
    """A function to terminate the app after all requests are handled"""
    while True:
        await asyncio.sleep(1)
        if request_count >= MAX_REQUESTS:
            await app.stop()
            exit(0)


async def main() -> None:
    await app.start()
    # Keep running until termination_handler exits
    await termination_handler()


if __name__ == "__main__":
    asyncio.run(main())
