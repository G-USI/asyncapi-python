from pathlib import Path
import typer
from typing import Literal

import yaml

from .parser import populate_refs, Document
from . import generators as g

app = typer.Typer()

Platform = Literal["rabbitmq"]
Protocol = Literal["amqp"]


@app.command()
def generate(
    input_file: str,
    protocol: Protocol = "amqp",
    platform: Platform = "rabbitmq",
) -> None:
    # Read file into dict
    with Path(input_file).open() as f:
        parsed_yaml = yaml.safe_load(f)

    # Go recursive, populating refs
    populated_yaml = populate_refs(parsed_yaml)

    # Produce Document instance
    document = Document.model_validate(populated_yaml)

    # Generate code
    match (protocol, platform):
        case ("amqp", "rabbitmq"):
            g.amqp_rabbitmq.generate(document)
        case (pr, pl):
            raise NotImplementedError(
                f"Protocol-platform pair {pr}-{pl} is not supported"
            )


if __name__ == "__main__":
    app()
