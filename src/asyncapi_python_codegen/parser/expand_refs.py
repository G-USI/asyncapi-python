from functools import cache
from typing import Any, Callable, TypedDict, cast


RefPath = str
Ref = TypedDict("Ref", {"$ref": RefPath})
Item = Any
RefDict = dict[str, Item | Ref]
ExpandedDict = dict[str, Item]
RefExpander = Callable[[RefPath], ExpandedDict]


def expand_refs(root: RefDict) -> ExpandedDict:
    expander = ref_expander(root)
    return {k: expand_refs_recur(v, expander) for k, v in root.items()}


def expand_refs_recur(branch: Item | Ref, expander: RefExpander) -> Item:
    match branch:
        case {"$ref": x} if isinstance(x, str):
            return expander(x)
        case {**items}:
            return {k: expand_refs_recur(v, expander) for k, v in items.items()}
        case [*items]:
            return [expand_refs_recur(v, expander) for v in items]
        case _:
            return cast(Item, branch)


def ref_expander(root: RefDict, sep: str = "/") -> RefExpander:
    @cache
    def get_by_ref(ref: RefPath) -> ExpandedDict:
        _, *path = ref.split(sep)
        part = root
        for p in path:
            part = cast(dict, part)[p]

        match part:
            case {"$ref": x, **rest}:
                return get_by_ref(x)
            case [*items]:
                return {i: get_by_ref(f"{ref}/{i}") for i, _ in enumerate(items)}
            case {**items}:
                return {i: get_by_ref(f"{ref}/{i}") for i in items}
            case _:
                return part

    return get_by_ref
