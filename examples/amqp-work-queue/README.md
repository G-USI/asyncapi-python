# AMQP Work Queue Example

This example demonstrates the **Work Queue** (Task Queue) messaging pattern using AsyncAPI Python. In this pattern, tasks are distributed among multiple workers, with each task being processed by exactly one worker.

## Pattern Characteristics

- **1:N Distribution**: One producer sends tasks to multiple workers
- **Load Balancing**: Tasks are automatically distributed among available workers
- **Reliability**: Each task is delivered to exactly one worker (no duplication)
- **Scalability**: Add more workers to handle increased load

## Architecture

```
Producer → [Task Queue] → Worker 1
                      ├→ Worker 2  
                      └→ Worker 3
```

- **Producer**: Sends tasks to a durable queue
- **Queue**: AMQP queue that holds tasks until processed
- **Workers**: Multiple instances that compete for tasks

## Files

- `spec/common.asyncapi.yaml` - Shared channel and message definitions
- `spec/producer.asyncapi.yaml` - Task producer specification
- `spec/worker.asyncapi.yaml` - Task worker specification
- `main-producer.py` - Task producer implementation
- `main-worker.py` - Worker implementation (accepts worker ID argument)
- `test_workqueue.py` - Automated test demonstrating work queue behavior

## Quick Start

1. **Setup environment**:
   ```bash
   make venv install generate
   ```

2. **Run the automated test**:
   ```bash
   make test-workqueue
   ```

3. **Manual testing**: Start multiple workers in separate terminals, then run producer:
   ```bash
   # Terminal 1
   make worker1
   
   # Terminal 2  
   make worker2
   
   # Terminal 3
   make worker3
   
   # Terminal 4 - Send tasks
   make producer
   ```

## Expected Behavior

- ✅ Each task is processed by exactly one worker
- ✅ Tasks are distributed among available workers
- ✅ Workers can be added/removed dynamically
- ✅ Queue persists tasks if no workers are available
- ✅ Failed tasks can be retried (depending on configuration)

## AMQP Configuration

The work queue uses:
- **Queue Type**: Durable, non-exclusive queue
- **Routing**: Direct routing to named queue
- **Delivery**: Round-robin distribution among consumers
- **Acknowledgment**: Manual ACK for reliability

This pattern is ideal for background job processing, image processing pipelines, email sending, and other scalable task processing scenarios.