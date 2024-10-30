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


def camel_case(kind: Literal["upper", "lower"], string: str):
    string = sub(r"(_|-)+", " ", string).title().replace(" ", "")
    match string, kind:
        case "", _:
            return ""
        case _, "lower":
            return string[0].lower() + string[1:]
        case _, "upper":
            return string[0].upper() + string[1:]
