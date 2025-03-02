# Copyright 2025 Yaroslav Petrov <yaroslav.v.petrov@gmail.com>
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

import json
import traceback
from typing import Any

from pydantic import ValidationError


class Rejection(BaseException):
    def asdict(self) -> dict[str, Any]:
        return {
            "__exception__": True,
            "type": self.__class__.__name__,
            "message": str(self),
            "traceback": traceback.format_exc(),
        }


class BadRequestRejection(Rejection):
    def __init__(self, err: ValidationError):
        super().__init__(err)

    def asdict(self) -> dict[str, Any]:
        return json.loads(self.args[0])


class RejectedError(BaseException):
    def __init__(self, rejection: Any, original_message: Any):
        super().__init__(rejection, original_message)
