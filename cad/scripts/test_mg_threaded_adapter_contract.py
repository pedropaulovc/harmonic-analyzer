"""Import-free AST census of affected MG recipes against the pinned SDK MRO.

No recipe/SDK/COM import or native operation occurs. Starred point tuples are
symbolic: the census proves the target signature accepts their possible
arity, while the geometry tests/native gate own the point data itself.
"""

from __future__ import annotations

import ast
import copy
import itertools

import pytest

from test_pd_transgear_adapter_contract import SCRIPTS, _adapter_calls, _adapter_methods, _missing, _signature, _tree

RECIPES = (
    "build_mg_magnifying_bracket.py",
    "build_mg_magnifying_lever.py",
    "build_mg_magnifying_clamp.py",
    "build_mg_magnifier_assembly.py",
    "draw_mg_magnifying_bracket.py",
    "draw_mg_magnifying_lever.py",
    "draw_mg_magnifying_clamp.py",
    "draw_mg_magnifier_assembly.py",
)


def _can_bind(call, method) -> bool:
    signature = _signature(method)
    receiver = [] if any(isinstance(item, ast.Name) and item.id == "staticmethod" for item in method.decorator_list) else [call.func.value]
    assert all(keyword.arg is not None for keyword in call.keywords), "dynamic keyword mapping needs explicit census support"
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}
    stars = sum(isinstance(argument, ast.Starred) for argument in call.args)
    fixed = len(call.args) - stars
    # At most the concrete signature's positional slots are useful. There is
    # no execution/evaluation of a starred tuple or of SDK defaults here.
    for counts in itertools.product(range(len(signature.parameters) + 1), repeat=stars):
        try:
            signature.bind(*receiver, *([None] * (fixed + sum(counts))), **keywords)
        except TypeError:
            continue
        return True
    return False


@pytest.mark.parametrize("recipe", RECIPES)
def test_all_direct_adapter_calls_exist_and_bind_without_imports(recipe) -> None:
    tree = _tree(SCRIPTS / recipe)
    calls = _adapter_calls(tree)
    assert calls, f"{recipe}: empty adapter census"
    assert not _missing(tree), f"{recipe}: missing SDK methods {sorted(_missing(tree))}"
    for call in calls:
        path, method = _adapter_methods()[call.func.attr]
        assert _can_bind(call, method), f"{recipe}:{call.lineno}: {call.func.attr} cannot bind {path}:{method.lineno}"


@pytest.mark.parametrize("recipe", RECIPES)
def test_census_catches_missing_method_and_invalid_keyword_mutations(recipe) -> None:
    tree = copy.deepcopy(_tree(SCRIPTS / recipe))
    call = _adapter_calls(tree)[0]
    original = call.func.attr
    call.func.attr = "not_a_pinned_sdk_method"
    assert "not_a_pinned_sdk_method" in _missing(tree)
    call.func.attr = original
    call.keywords.append(ast.keyword(arg="not_a_pinned_sdk_parameter", value=ast.Constant(None)))
    assert not _can_bind(call, _adapter_methods()[original][1])
