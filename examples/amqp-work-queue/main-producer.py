import asyncio
import uuid
from datetime import datetime
from os import environ
from producer import Application
from producer.messages.json import Task
from asyncapi_python.contrib.wire.amqp import AmqpWire


AMQP_URI = environ.get("AMQP_URI", "amqp://guest:guest@localhost")
NUM_TASKS = 10

app = Application(AmqpWire(AMQP_URI))


async def main() -> None:
    print(f"Starting task producer - will create {NUM_TASKS} tasks")

    await app.start()

    # Produce tasks
    for i in range(NUM_TASKS):
        task_id = str(uuid.uuid4())[:8]
        task = Task(
            id=task_id,
            payload={
                "task_number": i + 1,
                "description": f"Process task {i + 1}",
                "data": f"Important work item #{i + 1}",
                "processing_time": 2 + (i % 3),  # Vary processing time
            },
            created_at=datetime.utcnow().isoformat(),
        )

        print(f"📤 Sending task {i + 1}/{NUM_TASKS} (ID: {task_id})")
        await app.producer.task_send(task)

        # Small delay to see distribution
        await asyncio.sleep(0.5)

    print(f"✅ All {NUM_TASKS} tasks sent to queue")
    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
