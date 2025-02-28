import json
import traceback
from typing import Any

from pydantic import ValidationError


class Reject(BaseException):
    def asdict(self) -> dict[str, Any]:
        return {
            "__exception__": True,
            "type": self.__class__.__name__,
            "message": str(self),
            "traceback": traceback.format_exc(),
        }


class RejectBadRequest(Reject):
    def __init__(self, err: ValidationError):
        super().__init__(err)

    def asdict(self) -> dict[str, Any]:
        return json.loads(self.args[0])


class RejectedError(BaseException):
    def __init__(self, rejection: Any, original_message: Any):
        super().__init__(rejection, original_message)
