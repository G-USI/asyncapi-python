from typing import TypedDict


class AmqpParams(TypedDict, total=False):
    prefetch_count: int
