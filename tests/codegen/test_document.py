from asyncapi_python_codegen.document import Document
from pathlib import Path
import pytest
import yaml


@pytest.mark.parametrize(
    "example",
    [
        "amqp-basic.yaml",
        "amqp-ping-pong.yaml",
    ],
)
def test_document_loads_example(example: str):
    with (Path("examples") / example).open() as f:
        Document.model_validate(yaml.safe_load(f))
