import yaml
from itertools import chain
from typing import Any, Generator, TypedDict
from pathlib import Path
from .utils import snake_case, camel_case
from ...document import Document


def generate(
    *,
    input_path: Path,
    output_path: Path,
    template_path: Path = Path(__file__).parent / "templates",
) -> dict[Path, str]:
    doc = load_document(input_path)
    structs = get_structs(doc)

    raise NotImplementedError


class JsonSchema(TypedDict):
    path: str
    name: str
    schema: Any


def get_structs(doc: Document) -> list[JsonSchema]:
    # Find schemas in messages
    message_schemas: Generator[JsonSchema, None, None] = (
        {
            "name": camel_case("upper", name),
            "path": f"#/components/messages/{name}",
            "schema": msg.model_dump(),
        }
        for name, msg in doc.components.messages.items()
    )

    # Return results
    # TODO: Find more places where schemas might be stored
    return list(
        chain(
            message_schemas,
        )
    )


def load_document(input_path: Path) -> Document:
    with input_path.open() as f:
        return Document.model_validate(yaml.safe_load(f))
