from asyncapi_python_codegen.parser import expand_refs
import pytest


def test_no_ref():
    file = {"A": {"B": 1}, "C": {"D": "hello", "E": None}}
    expected = file
    actual = expand_refs(file)
    assert expected == actual


def test_value_ref():
    file = {"A": {"B": 1}, "C": {"D": "hello", "E": {"$ref": "#/A/B"}}}
    expected = {"A": {"B": 1}, "C": {"D": "hello", "E": 1}}
    actual = expand_refs(file)
    assert expected == actual


def test_root_object_ref():
    file = {"A": {"B": 1}, "C": {"D": "hello", "E": {"$ref": "#/A"}}}
    expected = {"A": {"B": 1}, "C": {"D": "hello", "E": {"B": 1}}}
    actual = expand_refs(file)
    assert expected == actual


def test_recursive_ref():
    file = {
        "A": {"B": {"$ref": "#/F"}},
        "C": {"D": "hello", "E": {"$ref": "#/A"}},
        "F": 0,
    }
    expected = {
        "A": {"B": 0},
        "C": {"D": "hello", "E": {"B": 0}},
        "F": 0,
    }
    actual = expand_refs(file)
    assert expected == actual


@pytest.mark.skip(reason="URL-based expansion is yet unsupported functionality")
def test_url_ref():
    raise NotImplementedError
