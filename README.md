# AsyncAPI Python Code Generator

A command line interface to generate Python code from AsyncAPI specifications. This tool helps you automatically create Python implementations of AsyncAPI services, reducing boilerplate code and ensuring consistency with your API specifications.

## Features

- Generates Python code from AsyncAPI specifications
- Creates both consumer and producer implementations
- Supports AMQP protocol
- Includes connection pooling and management
- Provides base application structure

## Installation

For code generation (development env), run:

```bash
pip install asyncapi-python[codegen]
```

For runtime, run:

```bash
pip install asyncapi-python[amqp]
```

You can replace `amqp` with any other supported protocols. For more info, see [Supported Protocols](#supported-protocols--use-cases) section.

## Supported Protocols / Use Cases

Below, you may see the table of protocols and the supported use cases. The tick signs (✅) contain links to the examples for each implemented protocol-use case.

| Use Case   | AMQP                                             |
| ---------- | ------------------------------------------------ |
| Pub-Sub    | [✅ amqp-pub-sub](./examples/amqp-rpc)           |
| Work Queue | [✅ amqp-work-queue](./examples/amqp-work-queue) |
| RPC        | [✅ amqp-rpc](./examples/amqp-ping-pong)         |

## Documentation

A set of examples is available under the [examples](./examples/) directory.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
