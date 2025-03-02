# Copyright 2024-2025 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
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
from dataclasses import dataclass
from itertools import chain, repeat
import json
from pathlib import Path
import tempfile
from typing import Literal, TypedDict, Optional

import jinja2 as j2

import asyncapi_python_codegen.document as d
from asyncapi_python_codegen.document.utils import populate_jsonschema_defs
from asyncapi_python.utils import snake_case

from datamodel_code_generator.__main__ import main as datamodel_codegen


def generate(
    *,
    input_path: Path,
    output_path: Path,
    template_dir: Path = Path(__file__).parent / "templates",
) -> dict[Path, str]:
    doc = d.Document.load_yaml(input_path)
    ops = [get_operation(k, op.get()) for k, op in doc.operations.items()]
    root = _Route(path=tuple(), op=None)

    send_ops = {x["path"]: x for x in ops if x["action"] == "send"}
    recv_ops = {x["path"]: x for x in ops if x["action"] == "receive"}

    send_routes_dict: dict[tuple[str, ...], _Route] = {}
    recv_routes_dict: dict[tuple[str, ...], _Route] = {}

    for path, _ops, routes in chain(
        zip(send_ops, repeat(send_ops), repeat(send_routes_dict)),
        zip(recv_ops, repeat(recv_ops), repeat(recv_routes_dict)),
    ):
        create_api_routing(path, _ops, routes)

    send_routes, recv_routes = (
        [root, *rs.values()] if rs.values() else []
        for rs in (send_routes_dict, recv_routes_dict)
    )

    return (
        {
            output_path / f: generate_routers(r, template_dir / "routes.py.j2")
            for f, r in (("producer.py", send_routes), ("consumer.py", recv_routes))
        }
        | {
            output_path
            / f"{f}.py": j2.Template((template_dir / f"{f}.py.j2").read_text()).render()
            for f in ("application", "__init__")
        }
        | {
            output_path
            / "messages.py": generate_message_types(ops, doc.filepath.parent),
            output_path / "py.typed": "",
        }
    )


def generate_routers(routes: list[_Route], template_path: Path) -> str:
    @dataclass
    class Router:
        id: int
        op: Optional[Operation]
        children: list[tuple[int, str]]

    routes_with_children = (
        (
            i,
            r,
            [
                (j, c)
                for j, c in enumerate(routes)
                if c.parent == r.path and c.path != r.path
            ],
        )
        for i, r in enumerate(routes)
    )
    routers = [
        Router(i, r.op, [(j, c.name) for j, c in cs]).__dict__
        for i, r, cs in routes_with_children
    ]
    template = j2.Template(template_path.read_text())
    return template.render(routers=routers)


def create_api_routing(
    path: tuple[str, ...],
    ops: dict[tuple[str, ...], Operation],
    routes: dict[tuple[str, ...], _Route],
):
    if not path:  # Skip root
        return

    router = _Route(path, ops.get(path))

    # Create Router if not in routes
    # Replace router if this is op
    if not (path in routes and routes[path].op):
        routes[path] = router

    create_api_routing(router.parent, ops, routes)


ExchangeType = Literal["topic", "direct", "fanout", "default", "headers"]


def get_operation(op_name: str, op: d.Operation) -> Operation:
    exchange_type: ExchangeType = "default"
    exchange: Optional[str] = None
    routing_key: Optional[str] = None

    ch = op.channel.get()
    reply_ch = op.reply.channel.get() if op.reply else None
    op_path = (snake_case(y) for x in op_name.split("/") for y in x.split(".") if y)
    addr = lambda x: x or ch.address or op.channel.escaped_doc_path[-1] or op_name

    if ch.bindings is None:
        # Default exchange + named queues
        routing_key = addr(None)
    elif (bind := ch.bindings).amqp.root.type == "queue":
        # Default exchange + named queues
        routing_key = addr(bind.amqp.root.queue.name)
    elif bind.amqp.root.type == "routingKey":
        # Named exchange + exclusive queues
        exchange = addr(bind.amqp.root.exchange.name)
        exchange_type = "fanout"

    # Get reply channel properties
    if reply_ch is not None:
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

    input_types: list[str]
    input_schemas: list[str]
    output_types: list[str]
    output_schemas: list[str]

    input_types, input_schemas = get_channel_types(ch, op.channel)
    output_types, output_schemas = (
        get_channel_types(op.reply.channel.get(), op.reply.channel)
        if op.reply
        else ([], [])
    )

    return {
        "name": op_name,
        "path": tuple(op_path),
        "action": op.action,
        "exchange": exchange,
        "exchange_type": exchange_type,
        "routing_key": routing_key,
        "input_types": input_types,
        "output_types": output_types,
        "input_schemas": input_schemas,
        "output_schemas": output_schemas,
    }


class Operation(TypedDict):
    name: str
    path: tuple[str, ...]
    action: Literal["send", "receive"]
    exchange: Optional[str]
    exchange_type: Optional[str]
    routing_key: Optional[str]
    input_types: list[str]
    output_types: list[str]
    input_schemas: list[str]
    output_schemas: list[str]


@dataclass
class _Route:
    path: tuple[str, ...]
    op: Optional[Operation]

    @property
    def name(self) -> str:
        if self.is_root:
            return ""
        return self.path[-1]

    @property
    def parent(self) -> tuple[str, ...]:
        return self.path[:-1]

    @property
    def is_root(self) -> bool:
        return not self.path


def get_channel_types(
    channel: d.Channel,
    channel_ref: d.Ref[d.Channel],
) -> tuple[list[str], list[str]]:
    types, schemas = [], []
    for message_key, message in channel.messages.items():

        if isinstance(message.root, d.Ref):
            msg_ref = message.root.flatten()
            msg_filepath = msg_ref.filepath
            msg_doc_path = msg_ref.raw_doc_path
            del msg_ref
        else:
            msg_filepath = channel_ref.filepath
            msg_doc_path = (*channel_ref.raw_doc_path, "messages", message_key)

        message_payload = message.get().payload.root
        if isinstance(message_payload, d.Ref):
            payload_ref = message_payload.flatten()
            pl_filepath = payload_ref.filepath
            pl_doc_path = payload_ref.raw_doc_path
            del payload_ref
        else:
            pl_filepath = msg_filepath
            pl_doc_path = (*msg_doc_path, "payload")

        types.append(message.get().title or message_key)
        schemas.append(str(pl_filepath) + "#/" + "/".join(pl_doc_path))

    return types, schemas


def generate_message_types(schemas: list[Operation], cwd: Path) -> str:
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
