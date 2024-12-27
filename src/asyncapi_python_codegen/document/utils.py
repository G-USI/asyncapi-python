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
from typing import Any, Union
import yaml

from .document_context import set_current_doc_path
from .ref import Ref
from collections import defaultdict


Reference = Union[None, tuple[Path, tuple[str, ...]]]
"""A reference type"""

ReferenceCounter = defaultdict[Reference, set[Reference]]
"""A reference counter"""


def count_references(schema: Any, this: Reference, counter: ReferenceCounter):
    if not isinstance(schema, dict):
        return

    if "$ref" in schema:
        ref: Ref[Any] = Ref.model_validate(schema)
        with set_current_doc_path(ref.filepath):
            ref = ref.flatten()
        with ref.filepath.open() as f:
            doc = yaml.safe_load(f)
        for p in ref.doc_path:
            doc = doc[p]
        child = (ref.filepath, ref.doc_path)
        counter[child].add(this)
        with set_current_doc_path(ref.filepath):
            return count_references(doc, child, counter)

    for v in schema.values():
        count_references(v, this, counter)


def populate_jsonschema(schema: Any) -> Any:
    counter: ReferenceCounter = defaultdict(lambda: set())
    shared_schemas: dict[str, Any] = {}
    count_references(schema, None, counter)
    res = populate_jsonschema_recur(schema, counter, shared_schemas)
    return {**res, **shared_schemas}


def populate_jsonschema_recur(
    schema: Any,
    counter: ReferenceCounter,
    shared_schemas: dict[str, Any],
    ignore_shared: bool = False,
) -> Any:
    if not isinstance(schema, dict):
        return schema

    if "$ref" in schema:
        ref: Ref[Any] = Ref.model_validate(schema)
        with set_current_doc_path(ref.filepath):
            ref = ref.flatten()

            back_refs = counter[(ref.filepath, ref.doc_path)]
            if len(back_refs) > 1 and not ignore_shared:
                ref_struct_name = ref.doc_path[-1]
                shared_schemas[ref_struct_name] = populate_jsonschema_recur(
                    schema, counter, shared_schemas, True
                )
                return {"$ref": f"#/$defs/{ref_struct_name}"}

        with ref.filepath.open() as f:
            doc = yaml.safe_load(f)
        for p in ref.doc_path:
            doc = doc[p]
        with set_current_doc_path(ref.filepath):
            return populate_jsonschema_recur(doc, counter, shared_schemas)

    return {
        k: populate_jsonschema_recur(v, counter, shared_schemas)
        for k, v in schema.items()
    }
