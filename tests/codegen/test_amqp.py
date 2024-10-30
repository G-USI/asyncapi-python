from asyncapi_python_codegen.generators.amqp import generate
from pathlib import Path
import pytest


@pytest.mark.parametrize("example", ["amqp-ping-pong.yaml"])
def test_generate(tmp_path: Path, example: str):
    input_path = Path("examples") / example
    result = generate(input_path=input_path, output_path=tmp_path)
    for path, code in result.items():
        with path.open("w") as f:
            f.write(code)
