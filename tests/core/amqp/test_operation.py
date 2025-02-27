from asyncapi_python.amqp import Operation
from pydantic import BaseModel
import pytest


@pytest.mark.parametrize(
    "name,path",
    [
        ("abc", ("abc",)),
        ("a.b.c", ("a", "b", "c")),
        ("a..b.c", ("a", "b", "c")),
        (".a..b....c", ("a", "b", "c")),
        ("cde", ("cde",)),
        ("/c/d/e", ("c", "d", "e")),
        ("//cd/e", ("cd", "e")),
        ("c/d/e", ("c", "d", "e")),
    ],
)
def test_operation_path(name: str, path: tuple[str]):
    op: Operation[BaseModel, None] = Operation(
        name, BaseModel, None.__class__, None, "testQueue", "default"
    )
    assert op.path == path
