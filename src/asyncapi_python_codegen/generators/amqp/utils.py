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


from re import sub
from typing import Literal


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


def camel_case(kind: Literal["upper", "lower"], string: str) -> str:
    if not string:
        return ""

    string = sub(r"(_|-)+", " ", string).title().replace(" ", "")

    if kind == "lower":
        return string[0].lower() + string[1:]
    elif kind == "upper":
        return string[0].upper() + string[1:]
