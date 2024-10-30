import json
import yaml
import subprocess
from itertools import chain
from typing import Any, Generator, TypedDict
from pathlib import Path
from .utils import snake_case, camel_case
from ...document import Document


def generate(
    *,
    input_path: Path,
    output_path: Path,
    template_dir: Path = Path(__file__).parent / "templates",
) -> dict[Path, str]:
    result: dict[Path, str] = {}

    doc = load_document(input_path)
    schemas = get_structs(doc)
    result[output_path / "models.py"] = generate_models(schemas)

    return result


class JsonSchema(TypedDict):
    path: str
    name: str
    schema: Any


def generate_models(schemas: list[JsonSchema]) -> str:
    args = """datamodel-codegen
    --output-model-type pydantic_v2.BaseModel
    --input-file-type jsonschema
    """.split()
    inp = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$defs": {x["name"]: x["schema"] for x in schemas},
    }
    return subprocess.run(
        args=args, capture_output=True, check=True, input=json.dumps(inp).encode()
    ).stdout.decode()


def get_structs(doc: Document) -> list[JsonSchema]:
    # Find schemas in messages
    message_schemas: Generator[JsonSchema, None, None] = (
        {
            "name": camel_case("upper", name),
            "path": f"#/components/messages/{name}",
            "schema": msg.payload.model_dump(),
        }
        for name, msg in doc.components.messages.items()
    )

    # Return results
    return list(
        chain(
            # TODO: Find more places, where schemas might be stored
            message_schemas
        )
    )


def load_document(input_path: Path) -> Document:
    with input_path.open() as f:
        return Document.model_validate(yaml.safe_load(f))
