"""Import-free adapter signature and focused declared-native-interface checks.

The adapter census checks the pinned SDK MRO, NOT the COM contracts beneath it.
The separate native-member check parses the generated typelib as data and catches
wrong explicit interface bindings; neither check proves native execution.
Starred adapter arguments remain symbolic: geometry tests/native gates own data.
"""

from __future__ import annotations

import ast
import copy
import functools
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


@functools.cache
def _native_declaration(interface):
    wrapper = SCRIPTS.parent.parent / "SolidworksMCP-python" / "src" / "solidworks_mcp" / "adapters" / "_generated" / "sldworks_2026.py"
    declaration = next(node for node in _tree(wrapper).body if isinstance(node, ast.ClassDef) and node.name == interface)
    methods = {node.name for node in declaration.body if isinstance(node, ast.FunctionDef)}
    maps = {}
    for node in declaration.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("_prop_map_get_", "_prop_map_put_"):
                    maps[target.id] = {ast.literal_eval(key) for key in node.value.keys}
    return methods, maps


def _undeclared_bound_calls(tree):
    failures = []
    for function in (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        bindings = {}
        for node in ast.walk(function):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "_early_bound":
                if len(node.value.args) == 2 and isinstance(node.value.args[1], ast.Constant):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            bindings[target.id] = node.value.args[1].value
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id in bindings:
                interface = bindings[node.func.value.id]
                methods, _maps = _native_declaration(interface)
                if node.func.attr not in methods:
                    failures.append(f"{interface}.{node.func.attr}")
    return failures


def test_declared_native_interfaces_reject_the_wrong_document_binding() -> None:
    # Positive control before relying on absence: a known property must be
    # present in BOTH maps, while FeatureByName must be a declared part method.
    _methods, maps = _native_declaration("IBody2")
    assert "Name" in maps["_prop_map_get_"] & maps["_prop_map_put_"]
    assert "FeatureByName" in _native_declaration("IPartDoc")[0]
    assert "FeatureByName" not in _native_declaration("IModelDoc2")[0]
    tree = _tree(SCRIPTS / "build_mg_magnifying_bracket.py")
    assert not _undeclared_bound_calls(tree)
    mutated = copy.deepcopy(tree)
    binding = next(
        node for node in ast.walk(mutated)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_early_bound"
        and len(node.args) == 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == "IPartDoc"
    )
    binding.args[1] = ast.Constant("IModelDoc2")
    assert "IModelDoc2.FeatureByName" in _undeclared_bound_calls(mutated)
