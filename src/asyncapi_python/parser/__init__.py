from pathlib import Path
from typing import Any
from .document import Document
import yaml


def populate_refs(parsed_yaml: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError
