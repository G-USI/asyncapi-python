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
