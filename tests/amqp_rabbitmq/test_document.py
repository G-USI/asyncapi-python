from asyncapi_python.generators.amqp_rabbitmq.document import Document
from pathlib import Path
import pytest
import yaml


@pytest.mark.parametrize("example", ["amqp-basic"])
def test_amqp_example(example: str):
    path = Path("examples") / f"{example}.yaml"
    with path.open() as f:
        doc = Document.model_validate(yaml.safe_load(f))
    for channel in doc.channels.values():
        for message in channel.messages.values():
            message.payload.title
    doc.dto_code
