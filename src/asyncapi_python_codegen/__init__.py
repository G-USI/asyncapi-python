from pathlib import Path
import typer
import yaml

from . import generators as g

app = typer.Typer()


@app.command()
def generate(
    input_file: Path,
    output_dir: Path,
    protocol: str = "amqp",
    platform: str = "rabbitmq",
) -> None:
    # Create empty out dir (and assert it is empty)
    output_dir.mkdir(parents=True, exist_ok=True)
    if next(output_dir.iterdir(), None):
        raise AssertionError("Output dir must be empty")

    # Generate code
    generation_result: dict[Path, str]
    match (protocol, platform):
        case ("amqp", "rabbitmq"):
            generation_result = g.amqp_rabbitmq.generate(
                input_path=input_file, output_path=output_dir
            )
        case (pr, pl):
            raise NotImplementedError(
                f"Protocol-platform pair {pr}-{pl} is not supported"
            )

    for path, code in generation_result.items():
        with path.open("w") as file:
            file.write(code)


if __name__ == "__main__":
    app()
