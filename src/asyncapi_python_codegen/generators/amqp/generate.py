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


from __future__ import annotations
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import jinja2 as j2
from typing import Literal, Optional, TypedDict
from asyncapi_python_codegen import document as d
from itertools import chain
from datamodel_code_generator.__main__ import main as datamodel_codegen

from asyncapi_python_codegen.document.utils import populate_jsonschema_defs

from .utils import snake_case


def generate(
    *,
    input_path: Path,
    output_path: Path,
) -> dict[Path, str]:
    # Get main document
    doc = d.Document.load_yaml(input_path)

    # Get all operations from this doc, add types, exchanges, and routing keys
    ops = [get_operation(k, v.get()) for k, v in doc.operations.items()]

    # Generate models.py using and render all Jinja templates
    return {
        output_path / k: v
        for k, v in generate_application(
            ops,
            doc.info.title,
            doc.info.description,
            doc.info.version,
        ).items()
    } | {
        output_path / "models.py": generate_models(ops, doc.filepath.parent),
        output_path / "py.typed": "",
    }


def generate_application(
    ops: list[Operation],
    title: str,
    description: Optional[str],
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


def generate_models(schemas: list[Operation], cwd: Path) -> str:
    inp = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$defs": populate_jsonschema_defs(
            {
                type_name: {"$ref": type_schema}
                for s in schemas
                for type_name, type_schema in chain(
                    zip(s["input_types"], s["input_schemas"]),
                    zip(s["output_types"], s["output_schemas"]),
                )
            }
        ),
    }

    with tempfile.TemporaryDirectory() as dir:
        schema_path = Path(dir) / "schema.json"
        models_path = Path(dir) / "models.py"

        args = f"""
        --input { str(schema_path.absolute()) }
        --output { str(models_path.absolute()) }
        --output-model-type pydantic_v2.BaseModel
        --input-file-type jsonschema
        --reuse-model
        --allow-extra-fields
        --collapse-root-models
        --target-python-version 3.9
        --use-title-as-name
        --capitalize-enum-members
        --snake-case-field
        --allow-population-by-field-name
        """.split()

        with schema_path.open("w") as schema:
            json.dump(inp, schema)

        datamodel_codegen(args=args)

        with models_path.open() as f:
            models_code = f.read()

    return models_code


def get_operation(op_name: str, op: d.Operation) -> Operation:
    exchange: Optional[str]
    routing_key: Optional[str]

    channel = op.channel.get()
    reply_channel = op.reply.channel.get() if op.reply else None
    addr = lambda x: x or channel.address or op_name

    if channel.bindings is None:
        # Default exchange + named queues
        exchange = None
        routing_key = addr(None)
    elif (bind := channel.bindings).amqp.root.type == "queue":
        # Default exchange + named queues
        exchange = None
        routing_key = addr(bind.amqp.root.queue.name)
    elif bind.amqp.root.type == "routingKey":
        # Named exchange + exclusive queues
        exchange = addr(bind.amqp.root.exchange.name)
        routing_key = None

    # Get reply channel properties
    if reply_channel is not None:
        if reply_channel.address:
            raise NotImplementedError(
                "Reply channel with static address is not supported"
            )
        if reply_channel.bindings is not None:
            if reply_channel.bindings.amqp.root.type != "queue":
                raise NotImplementedError(
                    "Reply channel that is not of a queue type is not supported"
                )
            if reply_channel.bindings.amqp.root.queue.name is not None:
                raise NotImplementedError(
                    "As of now, reply channel must be a queue without name"
                )

    input_types: list[str]
    input_schemas: list[str]
    output_types: list[str]
    output_schemas: list[str]

    input_types, input_schemas = get_channel_types(
        channel, op.channel.filepath, op.channel.doc_path
    )
    output_types, output_schemas = (
        get_channel_types(
            op.reply.channel.get(),
            op.reply.channel.filepath,
            op.reply.channel.doc_path,
        )
        if op.reply
        else ([], [])
    )

    return {
        "field_name": snake_case(op_name),
        "action": op.action,
        "exchange": exchange,
        "routing_key": routing_key,
        "input_types": input_types,
        "input_schemas": input_schemas,
        "output_types": output_types,
        "output_schemas": output_schemas,
    }


def get_channel_types(
    channel: d.Channel,
    channel_filepath: Path,
    channel_doc_path: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    types, schemas = [], []
    for message_key, message in channel.messages.items():

        if isinstance(message.root, d.Ref):
            msg_ref = message.root.flatten()
            msg_filepath = msg_ref.filepath
            msg_doc_path = msg_ref.doc_path
            del msg_ref
        else:
            msg_filepath = channel_filepath
            msg_doc_path = (*channel_doc_path, "messages", message_key)

        message_payload = message.get().payload.root
        if isinstance(message_payload, d.Ref):
            payload_ref = message_payload.flatten()
            pl_filepath = payload_ref.filepath
            pl_doc_path = payload_ref.doc_path
            del payload_ref
        else:
            pl_filepath = msg_filepath
            pl_doc_path = (*msg_doc_path, "payload")

        types.append(message.get().title or message_key)
        schemas.append(str(pl_filepath) + "#/" + "/".join(pl_doc_path))

    return types, schemas


class Operation(TypedDict):
    field_name: str
    action: Literal["send", "receive"]
    exchange: str | None
    routing_key: str | None
    input_types: list[str]
    output_types: list[str]
    input_schemas: list[str]
    output_schemas: list[str]
