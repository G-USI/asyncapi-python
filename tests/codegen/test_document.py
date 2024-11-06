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


from functools import partial
from asyncapi_python_codegen.document import Document
from pathlib import Path
import pytest
import yaml


@pytest.mark.parametrize(
    "example",
    [
        "ping-pong/server.asyncapi.yaml",
        "ping-pong/client.asyncapi.yaml",
    ],
)
def test_document_loads_example(example: str):
    doc = Document.load_yaml(path := Path("examples") / example)
    assert doc.filepath == path.absolute()


@pytest.mark.parametrize(
    "example,op_key",
    [
        ["ping-pong/server.asyncapi.yaml", "onPingRequest"],
        ["ping-pong/client.asyncapi.yaml", "pingRequest"],
    ],
)
def test_document_follows_ref(example: str, op_key: str):
    path = Path("examples") / example
    doc = Document.load_yaml(path)
    channel = doc.operations[op_key].get().channel.get()
    assert channel.address == "/ping"


def context_function(yaml_file: Path, path: str):
    with yaml_file.open() as f:
        doc = yaml.safe_load(f)
    paths = path.split("/")
    paths = paths[paths.index("#") + 1 :]
    *_, item = (doc := doc[path] for path in paths)
    return item
