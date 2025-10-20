# AsyncAPI Python Code Generator
>
> [!IMPORTANT]
> Although commits to dev branch might seem infrequent, the project is under active development **as of November 2025**.
>
> We currently produce only those changes that are required to satisfy our personal use cases.
>
> The number of commits will grow as we see increase in popularity of it, so do not hesitate
> to star this repo, open issues, and pull requests.

[Link to this github repository](https://github.com/G-USI/asyncapi-python)

Easily generate type-safe and async Python applications from AsyncAPI 3 specifications.

## Features

- [x] Creates `Application` class from [AsyncAPI 3](https://asyncapi.com) specifications, implementing every operation in the file
- [x] Generates typed Python code (messages are generated using [datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator))
- [x] Performs dynamic validation of messages with [Pydantic 2](https://docs.pydantic.dev/latest/)
- [x] Enforces the user code to implement all consumer methods as described by spec
- [x] Provides async code
- [x] Spec parser references other files through absolute or relative paths
- [ ] Spec parser references other files through url
- [x] Supports request-reply pattern
- [x] Supports publish-subscribe pattern
- [ ] AsyncAPI trait support
- [ ] Customizable message encoder/decoder
- [x] Works as a plugin for [pantsbuild](https://pantsbuild.org) (see [instructions](#usage-as-a-pants-plugin) below)

## Requirements

- `python>=3.10`
- `pydantic>=2`
- `pytz`
- For `codegen` extra
  - `jinja2`
  - `typer`
  - `datamodel-code-generator`
  - `pyyaml`
- For `amqp` extra
  - `aio-pika`

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

### Usage as a Pants plugin

> The following method was tested with pants version 2.23.1.
> Pleas note that Pants plugin API is still in development and things might break.

This library can act as a plugin for [Pants](https://pantsbuild.org). More specifically, it creates a new target type: `asyncapi_python_service` -- which can be used like:

```python
# BUILD
asyncapi_python_service(
  name="asyncapi_app",
  service="app.asyncapi.yaml",
  sources=[
    "app.asyncapi.yaml", 
    "lib.asyncapi.yaml", 
    "commons.*.asyncapi.yaml"
  ]
)
```

This will be generating python module named `asyncapi_app` on `codegen-export`, and `export` goals.
This target can later be used as a dependency of `python_sources`.

```python
# BUILD
python_sources(
  dependencies=[
    ":asyncapi_app",
    ":reqs",
  ],
)

python_requirements(
  name="reqs",
)
```

Note that this plugin does not do dependency injection, so asyncapi-python must be a dependency

```text
# requirements.txt
asyncapi-python[amqp]
```

### Deploying this plugin into your pants monorepo

```toml
# pants.toml
plugins = [
  "asyncapi_python[codegen]==0.2.5",  # Plugin version MUST match the version of your python clients
  ...
]
backend_packages = [
    "asyncapi_python_pants",
    ...
]
pythonpath = ["%(buildroot)s/pants-plugins"]
```

When everything is done, test if the plugin works by running `pants export-codegen ::`

## Supported Protocols / Use Cases

Below, you may see the table of protocols and the supported use cases. The tick signs (✅) contain links to the examples for each implemented protocol-use case pair, while the hammer signs (🔨) contain links to the Issues tracking the progress for protocol-use case pairs. The list of protocols and use cases is expected to increase over the progress of development.

| Use Case   | AMQP                                             |
| ---------- | ------------------------------------------------ |
| Pub-Sub    | [✅ amqp-pub-sub](./examples/amqp-pub-sub)            |
| Work Queue | [✅ amqp-work-queue](./examples/amqp-work-queue) |
| RPC        | [✅ amqp-rpc](./examples/amqp-rpc)               |

## Documentation

Although there's no documentation available at the moment, a set of comprehensive examples with comments for each implemented use-case is under the [examples](./examples/) directory.

## Contributing

Contributions are welcome! Please feel free to open an Issue or submit a Pull Request.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
