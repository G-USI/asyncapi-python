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


from pathlib import Path
from typing import Generator
from typing_extensions import Self
from contextlib import contextmanager

DOCUMENT_CONTEXT_STACK: list[Path] = []


@contextmanager
def set_current_doc_path(path: Path) -> Generator[None, None, None]:
    DOCUMENT_CONTEXT_STACK.append(path)
    yield
    DOCUMENT_CONTEXT_STACK.pop()


def current_doc_path():
    if not DOCUMENT_CONTEXT_STACK:
        raise AssertionError(
            "No Document path available. "
            + "Make sure you have used `with` statement on the "
            + "current DocumentPath during construction.\n"
        )
    return DOCUMENT_CONTEXT_STACK[-1]
