import asyncio
from os import environ
from sys import exit
from server import Application
from server.models import Ping, Pong


AMQP_URI = environ.get("AMQP_URI", "amqp://guest:guest@localhost")
MAX_REQUESTS = 3
request_count = 0

app = Application(AMQP_URI)


@app.consumer.on_ping_request
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
            exit(0)


async def main() -> None:
    app_handler = app.start(blocking=True)
    term_handler = termination_handler()
    await asyncio.gather(app_handler, term_handler)


if __name__ == "__main__":
    asyncio.run(main())
