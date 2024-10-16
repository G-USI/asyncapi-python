import yaml
from pathlib import Path
from .document import Document
from re import sub
from jinja2 import Template
from contextlib import ExitStack


def generate(*, input_path: Path, output_path: Path) -> dict[Path, str]:
    template_dir = Path(__file__).parent / "templates"
    template_names = "__init__", "base", "producer", "consumer"

    with ExitStack() as s:
        template_filenames = (template_dir / f"{t}.py.j2" for t in template_names)
        template_files = (s.enter_context(t.open()) for t in template_filenames)
        templates = [Template(t.read()) for t in template_files]

    with input_path.open() as f:
        doc = Document.model_validate(yaml.safe_load(f))
    channels = [
        {
            "channel_name": (
                (
                    channel.bindings.amqp.root.queue.name
                    if channel.bindings.amqp.root.type == "queue"
                    else channel.bindings.amqp.root.exchange.name
                )
                or name
            ),
            "field_name": snake_case(name),
            "schema": " | ".join(m.payload.title for m in channel.messages.values()),
            "type": (
                "queue" if channel.bindings.amqp.root.type == "queue" else "exchange"
            ),
            "exchage_type": (
                channel.bindings.amqp.root.exchange.type
                if channel.bindings.amqp.root.type == "routingKey"
                else None
            ),
        }
        for name, channel in doc.channels.items()
    ]
    render_args = dict(
        exchange_channels=[x for x in channels if x["type"] == "exchange"],
        queue_channels=[x for x in channels if x["type"] == "queue"],
    )
    return {
        **{
            output_path / f"{module}.py": template.render(**render_args)
            for module, template in zip(template_names, templates)
        },
        output_path / "messages.py": doc.messages_code,
    }


def snake_case(s: str) -> str:
    return "_".join(
        sub(
            "([A-Z][a-z]+)",
            r" \1",
            sub(
                "([A-Z]+)",
                r" \1",
                s.replace("-", " "),
            ),
        ).split()
    ).lower()
