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


def populate_jsonschema_defs(schema: Any) -> Any:
    """Given a $defs element of the JsonSchema
    1. Constructs back references map for all links
    2. Populates types by copying its body into parent $def (if there is only one reference)
    3. Adds a new $defs object (if there is more than one reference), and rewrites $refs
    4. Returns a huge jsonschema $defs object containing all structs that have been referenced by the structs
       from the original schema
    """
    counter: ReferenceCounter = defaultdict(lambda: set())
    shared_schemas: dict[str, Any] = {}
    _count_references(schema, None, counter)
    res = _populate_jsonschema_recur(schema, counter, shared_schemas)
    return {**res, **shared_schemas}


def _count_references(schema: Any, this: Reference, counter: ReferenceCounter):
    """Recursively constructs back references within the JsonSchema"""
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
            return _count_references(doc, child, counter)

    for v in schema.values():
        _count_references(v, this, counter)


def _populate_jsonschema_recur(
    schema: Any,
    counter: ReferenceCounter,
    shared_schemas: dict[str, Any],
    ignore_shared: bool = False,
) -> Any:
    """Recursively populates JsonSchema $defs object"""
    if not isinstance(schema, dict):
        return schema

    if "$ref" in schema:
        ref: Ref[Any] = Ref.model_validate(schema)
        with set_current_doc_path(ref.filepath):
            ref = ref.flatten()

            back_refs = counter[(ref.filepath, ref.doc_path)]
            if len(back_refs) > 1 and not ignore_shared:
                ref_struct_name = ref.doc_path[-1]
                shared_schemas[ref_struct_name] = _populate_jsonschema_recur(
                    schema, counter, shared_schemas, True
                )
                return {"$ref": f"#/$defs/{ref_struct_name}"}

        with ref.filepath.open() as f:
            doc = yaml.safe_load(f)
        for p in ref.doc_path:
            doc = doc[p]
        with set_current_doc_path(ref.filepath):
            return _populate_jsonschema_recur(doc, counter, shared_schemas)

    return {
        k: _populate_jsonschema_recur(v, counter, shared_schemas)
        for k, v in schema.items()
    }
