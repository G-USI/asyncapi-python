# Asyncapi-Python AMQP Pub-Sub Example

The following example shows how to use `asyncapi-python` package to create publisher-subscriber communications.

## Requirements

1. A working `amqp` broker

   > This example assumes that it will be accessible by `amqp://guest:guest@localhost`.
   > If this is not true, set `AMQP_URI` envvar accordingly

## Steps

1. `cd` into this directory

1. Create python virtual environment and activate it.

   Alternatively, run `make venv install`.

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   ```

1. Generate client and server modules.

   Alternatively, run `make generate`.

   ```bash
   asyncapi-python-codegen spec/publisher.asyncapi.yaml publisher --force
   asyncapi-python-codegen spec/subscriber.asyncapi.yaml subscriber --force
   ```

1. Run subscriber, and then publisher. This requires two terminals.

   ```bash
   .venv/bin/python main-subscriber.py
   ```

   ```bash
   .venv/bin/python main-publisher.py
   ```
