# Asyncapi-Python AMQP RPC Example

The following example shows how to use `asyncapi-python` package to create remote procedure call communications.

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
   asyncapi-python-codegen spec/client.asyncapi.yaml client --force
   asyncapi-python-codegen spec/server.asyncapi.yaml server --force
   ```

1. Run server and client code simultaneously. This requires two terminals.

   ```bash
   .venv/bin/python main-server.py
   ```

   ```bash
   .venv/bin/python main-client.py
   ```
