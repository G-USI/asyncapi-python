from pants.backend.python.util_rules import pex
from pants.core.goals.resolves import ExportableTool
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule

from .rules import *
from .targets import *


def rules():
    return [
        *collect_rules(),
        *pex.rules(),
        UnionRule(GenerateSourcesRequest, GeneratePythonFromAsyncapiRequest),
    ]


def target_types():
    return [AsyncapiServiceTarget]
