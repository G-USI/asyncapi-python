from typing import TypedDict
from typing_extensions import NotRequired

__all__ = ["EndpointParams", "HandlerParams"]


class EndpointParams(TypedDict, total=False):
    """Optional parameters for endpoint configuration"""

    service_name: str  # Service name for generating app_id
    default_rpc_timeout: (
        float | None
    )  # Default timeout in seconds for RPC client requests (default: 180.0), or None to disable
    disable_handler_validation: bool  # Opt-out of handler enforcement for testing


class HandlerParams(TypedDict):
    """Parameters for message handlers"""

    parameters: NotRequired[
        dict[str, str]
    ]  # Channel parameter values for subscription (e.g., {"location": "*", "severity": "high"})
