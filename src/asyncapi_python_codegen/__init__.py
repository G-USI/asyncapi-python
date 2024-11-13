# Copyright 2024 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from pathlib import Path
import typer
from . import generators as g

app = typer.Typer()


@app.command()
def generate(
    input_file: Path,
    output_dir: Path,
    protocol: str = "amqp",
    force: bool = False,
) -> None:
    # Create empty out dir (and assert it is empty)
    output_dir.mkdir(parents=True, exist_ok=True)
    if next(output_dir.iterdir(), None) and not force:
        raise AssertionError(
            "Output dir must be empty unless --force option is specified"
        )

    # Generate code
    generation_result: dict[Path, str]
    if protocol == "amqp":
        generation_result = g.amqp.generate(
            input_path=input_file, output_path=output_dir
        )
    else:
        raise NotImplementedError(f"Protocol {protocol} is not supported")

    # Write files
    for path, code in generation_result.items():
        with path.open("w") as file:
            file.write(code)


if __name__ == "__main__":
    app()
