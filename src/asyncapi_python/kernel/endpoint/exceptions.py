class EndpointError(Exception):
    """Base exception for endpoint errors"""


class UninitializedError(EndpointError):
    """Raised when endpoint is used before initialization"""

    def __init__(self):
        super().__init__(
            "Tried to perform wire communication action before initializing wire"
        )


class TimeoutError(EndpointError):
    """Raised when an RPC call times out"""


class HandlerError(EndpointError):
    """Raised when a handler encounters an error"""
