"""Exception classes for AsyncAPI Python kernel."""


class Reject(Exception):
    """Exception raised to reject a message and continue processing.

    When raised in a handler, the message will be rejected (negative acknowledgment)
    and the application will continue running.

    Args:
        reason: The reason for rejecting the message
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


__all__ = ["Reject"]
