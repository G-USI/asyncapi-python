import asyncio
import sys
from os import environ
from worker import Application
from worker.messages.json import Task
from asyncapi_python.contrib.wire.amqp import AmqpWire


AMQP_URI = environ.get("AMQP_URI", "amqp://guest:guest@localhost")

# Get worker ID from command line argument or default to "worker"
worker_id = sys.argv[1] if len(sys.argv) > 1 else "worker"

app = Application(AmqpWire(AMQP_URI))


@app.consumer.task_process
async def handle_task(task: Task) -> None:
    print(
        f"🔨 [{worker_id}] Processing task {task.id}: {task.payload.get('description', 'N/A')}"
    )

    # Simulate processing time based on task data
    processing_time = task.payload.get("processing_time", 2)
    await asyncio.sleep(processing_time)

    task_number = task.payload.get("task_number", "?")
    print(
        f"✅ [{worker_id}] Completed task {task.id} (#{task_number}) - took {processing_time}s"
    )


async def main() -> None:
    print(f"🚀 Starting worker '{worker_id}' - waiting for tasks...")

    await app.start()

    # Keep worker running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print(f"\n🛑 [{worker_id}] Stopping worker...")
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
