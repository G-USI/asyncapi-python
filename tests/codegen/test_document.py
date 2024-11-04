from functools import partial
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
    doc = Document.load_yaml(path := Path("examples") / example)
    assert doc.filepath == path.absolute()


@pytest.mark.parametrize("example", ["amqp-ping-pong.yaml"])
def test_document_follows_ref(example: str):
    path = Path("examples") / example
    doc = Document.load_yaml(path)
    doc.operations["pingRequest"].channel.get(partial(context_function, path))


def context_function(yaml_file: Path, path: str):
    with yaml_file.open() as f:
        doc = yaml.safe_load(f)
    paths = path.split("/")
    paths = paths[paths.index("#") + 1 :]
    *_, item = (doc := doc[path] for path in paths)
    return item
