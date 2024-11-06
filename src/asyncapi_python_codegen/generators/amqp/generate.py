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
import subprocess
import jinja2 as j2
from typing import Any, Literal, TypedDict
from asyncapi_python_codegen import document as d
from itertools import chain

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
    } | {output_path / "models.py": generate_models(ops)}


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


def generate_models(schemas: list[Operation]) -> str:
    args = """datamodel-codegen
    --output-model-type pydantic_v2.BaseModel
    --input-file-type jsonschema
    """.split()

    inp = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$defs": {
            type_name: type_schema
            for s in schemas
            for type_name, type_schema in chain(
                zip(s["input_types"], s["input_schemas"]),
                zip(s["output_types"], s["output_schemas"]),
            )
        },
    }
    return subprocess.run(
        args=args, capture_output=True, check=True, input=json.dumps(inp).encode()
    ).stdout.decode()


def get_operation(op_name: str, op: d.Operation) -> Operation:
    exchange: str | None
    routing_key: str | None

    channel = op.channel.get()
    reply_channel = op.reply.channel.get() if op.reply else None
    addr = lambda x: x or channel.address or op_name
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

    return {
        "field_name": snake_case(op_name),
        "action": op.action,
        "exchange": exchange,
        "routing_key": routing_key,
        "input_types": [msg.get().title for msg in channel.messages.values()],
        "input_schemas": [
            msg.get().payload.get().model_dump() for msg in channel.messages.values()
        ],
        "output_types": (
            [msg.get().title for msg in reply_channel.messages.values()]
            if reply_channel
            else []
        ),
        "output_schemas": (
            [
                msg.get().payload.get().model_dump()
                for msg in reply_channel.messages.values()
            ]
            if reply_channel
            else []
        ),
    }


class Operation(TypedDict):
    field_name: str
    action: Literal["send", "receive"]
    exchange: str | None
    routing_key: str | None
    input_types: list[str]
    output_types: list[str]
    input_schemas: list[Any]
    output_schemas: list[Any]
