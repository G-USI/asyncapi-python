from datetime import datetime
from out.messages import TestMessage
from out import Producer

import asyncio
import pytz


amqp_uri = "amqp://guest:guest@rabbitmq/"


async def main() -> None:
    p = await Producer.create(amqp_uri=amqp_uri)
    await p.test_work_queue(
        TestMessage(
            message="Test message",
            date=datetime(2024, 1, 1, tzinfo=pytz.UTC),
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
