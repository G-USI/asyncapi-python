from contextlib import ExitStack
from functools import partial
import json
import yaml
import subprocess
import jinja2 as j2
from itertools import chain
from typing import Any, Generator, Literal, TypedDict
from pathlib import Path

from .utils import snake_case, camel_case
from ... import document
from ...document import Document


def generate(
    *,
    input_path: Path,
    output_path: Path,
) -> dict[Path, str]:
    result: dict[Path, str] = {}
    doc = Document.load_yaml(input_path)
    models = get_models(doc)
    ops = get_operations(doc, models)
    result.update(
        {
            output_path / p: s
            for p, s in generate_application(
                ops,
                doc.info.title,
                doc.info.description,
                doc.info.version,
            ).items()
        }
    )
    result[output_path / "models.py"] = generate_models(models)

    return result


class Operation(TypedDict):
    field_name: str
    action: Literal["send", "receive"]
    exchange: str | None
    routing_key: str | None
    input_types: list[str]
    output_types: list[str]
    has_reply: bool


class JsonSchema(TypedDict):
    path: str
    name: str
    schema: Any


def generate_application(
    ops: list[Operation],
    title: str,
    description: str | None,
    version: str,
    template_dir: Path = Path(__file__).parent / "templates",
    filenames: list[str] = ["__init__.py", "application.py"],
) -> dict[str, str]:
    render_args = dict(ops=ops, title=title, description=description, version=version)
    with ExitStack() as s:
        paths = (template_dir / f"{f}.j2" for f in filenames)
        contents = (s.enter_context(f.open()).read() for f in paths)
        templates = (j2.Template(c) for c in contents)
        return {f: t.render(**render_args) for t, f in zip(templates, filenames)}


def get_operations(
    doc: Document,
    models: list[JsonSchema],
) -> list[Operation]:
    result: list[Operation] = []
    for name, op in doc.operations.items():
        action = op.action
        channel = op.channel.get(doc.local_context)

        # Get channel properties
        exchange: str | None
        routing_key: str | None
        addr = lambda x: x or channel.address or name
        match channel.bindings:
            case None:
                # Default exchange + named queues
                exchange = None
                routing_key = addr(None)
            case bind if bind.amqp.root.type == "queue":
                # Default exchange + named queues
                exchange = None
                routing_key = addr(bind.amqp.root.queue.name)
            case bind if bind.amqp.root.type == "routingKey":
                # Named exchange + exclusive queues
                exchange = addr(bind.amqp.root.exchange.name)
                routing_key = None

        get_types = partial(get_channel_message_types, models)
        input_types: list[str] = get_types(channel)

        # Get reply channel properties
        if has_reply := op.reply is not None:
            reply_ch = op.reply.channel.get(doc.local_context)
            if reply_ch.address:
                raise NotImplementedError(
                    "Reply channel with static address is not supported"
                )
            if reply_ch.bindings is not None:
                if reply_ch.bindings.amqp.root.type != "queue":
                    raise NotImplementedError(
                        "Reply channel that is not of a queue type is not supported"
                    )
                if reply_ch.bindings.amqp.root.queue.name is not None:
                    raise NotImplementedError(
                        "As of now, reply channel must be a queue without name"
                    )
            output_types = get_types(reply_ch)
        else:
            output_types = []

        result.append(
            {
                "action": action,
                "exchange": exchange,
                "field_name": snake_case(name),
                "input_types": input_types,
                "routing_key": routing_key,
                "has_reply": has_reply,
                "output_types": output_types,
            }
        )

    return result


def get_channel_message_types(
    models: list[JsonSchema],
    ch: document.Channel,
) -> list[str]:
    res = []
    for m_ref in ch.messages.values():
        if not isinstance(m_ref.root, document.Ref):
            raise NotImplementedError(
                "Inline message schemas are not supported right now, use $ref inside channels"
            )
        if not (name := next(m["name"] for m in models if m_ref.root.ref == m["path"])):
            raise AssertionError(
                f"Channel declares message ref {m_ref.root.ref} that has "
                + "not been captured by data model generator"
            )
        res.append(name)
    return res


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


def get_models(doc: Document) -> list[JsonSchema]:
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
