from pathlib import Path
import typer
from . import generators as g

app = typer.Typer()


@app.command()
def generate(input_file: Path, output_dir: Path, protocol: str = "amqp") -> None:
    # Create empty out dir (and assert it is empty)
    output_dir.mkdir(parents=True, exist_ok=True)
    if next(output_dir.iterdir(), None):
        raise AssertionError("Output dir must be empty")

    # Generate code
    generation_result: dict[Path, str]
    match protocol:
        case "amqp":
            generation_result = g.amqp.generate(
                input_path=input_file, output_path=output_dir
            )
        case _:
            raise NotImplementedError(f"Protocol {protocol} is not supported")

    # Write files
    for path, code in generation_result.items():
        with path.open("w") as file:
            file.write(code)


if __name__ == "__main__":
    app()
