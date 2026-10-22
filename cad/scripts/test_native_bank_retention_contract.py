"""Offline binding census for saved-bank retention; never import COM or the helper.

The receiver map is deliberately explicit: new native receivers/members must be
reviewed against the real generated interface, not invented by a geometry fake.
Imported temporary-body helpers retain their own contracts. This proves binding
shape/signature only, not native topology, saved-model metrology or soundness.
"""
from __future__ import annotations

import ast
import copy
import inspect
from functools import cache
from pathlib import Path

import pytest

from test_pd_transgear_adapter_contract import (
    ADAPTER,
    SDK,
    _adapter_methods,
    _class,
    _resolve_class,
    _signature,
    _tree,
)

HELPER = Path(__file__).with_name("_native_bank_retention.py")
GENERATED = SDK / "adapters" / "_generated" / "sldworks_2026.py"
RECEIVERS = {
    "assembly": "IAssemblyDoc",
    "component": "IComponent2",
    "item": "IComponent2",  # pedestal sorting lambda
    "face": "IFace2",  # returned by the checked _cylinders helper
    "edge": "IEdge",
    "curve": "ICurve",
    "surface": "ISurface",
    "part": "IPartDoc",
    "model": "IModelDoc2",
    "adapter.swApp": "ISldWorks",
}
ADAPTER_FIELDS = {"currentModel", "swApp"}
# Positive witnesses exercise method, property and out-param extraction without
# freezing the helper's implementation or number/order of native calls.
POSITIVE_CONTROLS = {
    "IAssemblyDoc": {"GetComponents"},
    "IComponent2": {"GetBodies3", "Name2"},
    "ICurve": {"IsCircle", "CircleParams"},
    "ISurface": {"IsPlane", "PlaneParams"},
    "IPartDoc": {"GetMaterialPropertyName2"},
    "IModelDoc2": {"ClosestDistance"},
}


@cache
def _interfaces() -> dict[str, ast.ClassDef]:
    return {
        node.name: node for node in _tree(GENERATED).body
        if isinstance(node, ast.ClassDef)
    }


def _property_map(cls: ast.ClassDef, name: str) -> dict[str, ast.expr]:
    assignments = [
        node for node in cls.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    ]
    assert len(assignments) == 1, f"{cls.name}: missing/ambiguous {name}"
    value = assignments[0].value
    assert isinstance(value, ast.Dict)
    return {ast.literal_eval(key): entry for key, entry in zip(value.keys, value.values, strict=True)}


@cache
def _members(interface: str):
    cls = _interfaces()[interface]
    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    return methods, _property_map(cls, "_prop_map_get_"), _property_map(cls, "_prop_map_put_")


def _dispatch(method: ast.FunctionDef) -> tuple[tuple[int, int], tuple]:
    """Read the actual makepy invocation, never execute generated definitions."""
    calls = [
        node for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"InvokeTypes", "_ApplyTypes_"}
    ]
    assert len(calls) == 1, f"{method.name}: unsupported generated invocation"
    call = calls[0]
    index = 3 if call.func.attr == "InvokeTypes" else 2
    return ast.literal_eval(call.args[index]), ast.literal_eval(call.args[index + 1])


def _native_signature(method: ast.FunctionDef) -> inspect.Signature:
    signature = _signature(method)
    # makepy's not-optional sentinel is a Python default, but omitting an input
    # sends DISP_E_PARAMNOTFOUND to COM. Out params default to Missing instead.
    return signature.replace(parameters=[
        parameter.replace(default=inspect.Parameter.empty)
        if isinstance(parameter.default, ast.Name)
        and parameter.default.id == "defaultNamedNotOptArg" else parameter
        for parameter in signature.parameters.values()
    ])


def _bind(method: ast.FunctionDef, call: ast.Call, *, native: bool) -> None:
    assert not any(isinstance(arg, ast.Starred) for arg in call.args), "unresolved positional splat"
    assert all(keyword.arg is not None for keyword in call.keywords), "unresolved keyword splat"
    static = any(isinstance(item, ast.Name) and item.id == "staticmethod" for item in method.decorator_list)
    signature = _native_signature(method) if native else _signature(method)
    try:
        signature.bind(
            *([] if static else [call.func.value]), *call.args,
            **{keyword.arg: keyword.value for keyword in call.keywords},
        )
    except TypeError as error:
        raise AssertionError(f"{method.name}: signature mismatch: {error}") from error


def _accesses(tree: ast.AST) -> list[ast.Attribute]:
    # SolidWorks native names are PascalCase, unlike Python/spec constants.
    # Scan unknown receivers too, so adding `new_face.GetBogus()` cannot escape
    # merely because `new_face` has not yet been enrolled in RECEIVERS.
    return [
        node for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        and (ast.unparse(node.value) in RECEIVERS
             or ast.unparse(node.value) == "adapter"
             or (node.attr[0].isupper() and not node.attr.isupper()))
    ]


def _audit(tree: ast.AST) -> dict[str, set[str]]:
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    census: dict[str, set[str]] = {}
    for access in _accesses(tree):
        receiver = ast.unparse(access.value)
        parent = parents.get(access)
        call = parent if isinstance(parent, ast.Call) and parent.func is access else None
        if receiver == "adapter":
            if access.attr in ADAPTER_FIELDS:
                assert call is None, f"adapter field called: {access.attr}"
                assert isinstance(access.ctx, ast.Load), "adapter state mutation"
            else:
                methods = _adapter_methods()
                assert access.attr in methods, f"undeclared adapter member: {access.attr}"
                assert call is not None, f"adapter method not called: {access.attr}"
                _bind(methods[access.attr][1], call, native=False)
            census.setdefault("adapter", set()).add(access.attr)
            continue
        assert receiver in RECEIVERS, f"unenrolled native receiver: {receiver}.{access.attr}"
        interface = RECEIVERS[receiver]
        methods, getters, setters = _members(interface)
        census.setdefault(interface, set()).add(access.attr)
        label = f"{interface}.{access.attr}"
        if isinstance(access.ctx, ast.Store):
            assert access.attr in setters, f"undeclared native property put: {label}"
            # The retention helper is read-only even when a native setter exists.
            raise AssertionError(f"native property mutation: {label}")
        assert isinstance(access.ctx, ast.Load), f"unsupported native access: {label}"
        if access.attr in getters:
            assert call is None, f"native property called: {label}"
            entry = getters[access.attr]
            assert isinstance(entry, ast.Tuple)
            assert len(ast.literal_eval(entry.elts[2])) == 2, f"missing property retval: {label}"
        else:
            assert access.attr in methods, f"undeclared native member: {label}"
            assert call is not None, f"native method not called: {label}"
            method = methods[access.attr]
            _bind(method, call, native=True)
            retval, _arguments = _dispatch(method)
            if retval[0] == 24:
                assert isinstance(parents.get(call), ast.Expr), f"void result consumed: {label}"
    assert census, "empty native/adapter census"
    return census


def test_every_direct_retention_binding_matches_actual_sources() -> None:
    census = _audit(_tree(HELPER))
    for interface, members in POSITIVE_CONTROLS.items():
        assert members <= census.get(interface, set()), f"missing census control: {interface}"
    assert ADAPTER_FIELDS <= census.get("adapter", set())
    # Both adapter fields must be real declarations on the concrete adapter,
    # rather than attributes silently invented by an unrestricted fake.
    ref = _resolve_class(ADAPTER, "PyWin32Adapter")
    assert ref is not None
    declared = {
        node.target.attr for node in ast.walk(_class(ref))
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Attribute)
        and isinstance(node.target.value, ast.Name) and node.target.value.id == "self"
    }
    assert ADAPTER_FIELDS <= declared


def test_property_extractor_positive_controls_actual_maps() -> None:
    methods, getters, setters = _members("IBody2")
    assert "Name" in getters and "Name" in setters and "Name" not in methods
    methods, getters, setters = _members("ICurve")
    assert "IsCircle" in methods and "IsCircle" not in getters
    assert "CircleParams" in getters and "CircleParams" not in setters
    assert _dispatch(methods["IsCircle"])[0] == (11, 0)


@pytest.mark.parametrize(
    "interface,member,inputs,outs",
    [
        ("IComponent2", "GetBodies3", 1, ((16396, 2),)),
        ("IPartDoc", "GetMaterialPropertyName2", 1, ((16392, 2),)),
        ("IModelDoc2", "ClosestDistance", 2, ((16396, 2), (16396, 2))),
    ],
)
def test_generated_output_defaults_are_optional_not_missing_inputs(interface, member, inputs, outs) -> None:
    method = _members(interface)[0][member]
    _retval, arguments = _dispatch(method)
    assert arguments[inputs:] == outs
    defaults = method.args.defaults
    assert [ast.unparse(default) for default in defaults[inputs:]] == ["pythoncom.Missing"] * len(outs)
    signature = _native_signature(method)
    signature.bind(*([object()] * (1 + inputs)))
    signature.bind(*([object()] * (1 + inputs + len(outs))))
    with pytest.raises(TypeError):
        signature.bind(*([object()] * inputs))


@pytest.mark.parametrize(
    "source,reason",
    [
        ("component.GetBodiesTypo(0)", "undeclared native member"),
        ("component.Name2()", "native property called"),
        ("component.GetPathName", "native method not called"),
        ("component.GetBodies3(0, None, None)", "signature mismatch"),
        ("component.GetBodies3()", "signature mismatch"),
        ("face.GetEdges(wrong=True)", "signature mismatch"),
        ("new_face.GetEdges()", "unenrolled native receiver"),
        ("adapter.no_such_retention_method()", "undeclared adapter member"),
        ("adapter.currentModel()", "adapter field called"),
        ("component.Name2 = 'changed'", "native property mutation"),
        ("if adapter.swApp.SetUserPreferenceToggle(1, True):\n    pass", "void result consumed"),
        ("result = adapter.swApp.SetUserPreferenceToggle(1, True)", "void result consumed"),
    ],
)
def test_census_negative_controls_against_real_declarations(source, reason) -> None:
    with pytest.raises(AssertionError, match=reason):
        _audit(ast.parse(source))


def test_actual_helper_mutation_cannot_pass_vacuously() -> None:
    tree = copy.deepcopy(_tree(HELPER))
    calls = [
        node for node in ast.walk(tree) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == "GetBodies3"
    ]
    assert calls, "positive control: actual GetBodies3 call must be found"
    calls[0].func.attr = "GetBodiesTypo"
    with pytest.raises(AssertionError, match="undeclared native member"):
        _audit(tree)
    with pytest.raises(AssertionError, match="empty native/adapter census"):
        _audit(ast.parse("pass"))
