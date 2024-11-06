from pathlib import Path
from asyncapi_python_codegen import document as d
from itertools import chain

from .utils import snake_case, camel_case


def generate(
    *,
    input_path: Path,
    output_path: Path,
) -> dict[Path, str]:
    # Get main document
    main_doc = d.Document.load_yaml(input_path)

    # Get all operations from this doc and from others
    all_ops: dict[str, d.Operation] = {
        k: v.get() for k, v in main_doc.operations.items()
    }
    channels = (v.channel.get() for v in all_ops.values())
    reply_channels = (v.reply.channel.get() for v in all_ops.values() if v.reply)
    all_channels = chain(channels, reply_channels)
    all_message_payloads = (
        m.get().payload for c in all_channels for m in c.messages.values()
    )
    print(list(all_message_payloads))

    return {}
