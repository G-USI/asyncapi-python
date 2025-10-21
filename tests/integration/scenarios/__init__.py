"""Test scenarios for wire+codec combinations"""

from .error_handling import error_handling
from .fan_in_logging import fan_in_logging
from .fan_out_broadcasting import fan_out_broadcasting
from .malformed_messages import malformed_message_handling
from .many_to_many_microservices import many_to_many_microservices
from .producer_consumer import producer_consumer_roundtrip
from .reply_channel import reply_channel_creation

__all__ = [
    "producer_consumer_roundtrip",
    "reply_channel_creation",
    "error_handling",
    "malformed_message_handling",
    "fan_in_logging",
    "fan_out_broadcasting",
    "many_to_many_microservices",
]
