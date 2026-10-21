"""Import-free adapter signature and focused declared-native-interface checks.

The adapter census checks the pinned SDK MRO, NOT the COM contracts beneath it.
The separate native-member check parses the generated typelib as data and catches
undeclared members, call arity and result-shape mistakes on explicit bindings.
It cannot prove that QI supplied the requested interface or that a DISPID applies
to a live dispatch. Selection/attachment integer results use swSelectType_e:
the 11/25 ISketchPoint distinction needs SDK semantics and behavioral coverage,
not a different method signature. Dynamic callout metadata needs its own gates.
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
    methods = {node.name: node for node in declaration.body if isinstance(node, ast.FunctionDef)}
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
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            receiver = node.func.value
            interface = bindings.get(receiver.id) if isinstance(receiver, ast.Name) else None
            if isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name) and receiver.func.id == "_early_bound":
                if len(receiver.args) == 2 and isinstance(receiver.args[1], ast.Constant):
                    interface = receiver.args[1].value
            if interface is not None:
                methods, _maps = _native_declaration(interface)
                if node.func.attr not in methods:
                    failures.append(f"{interface}.{node.func.attr}")
                elif not _can_bind(node, methods[node.func.attr]):
                    failures.append(f"{interface}.{node.func.attr} arguments")
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


def test_closed_sketch_status_and_dimension_ownership_use_native_call_shapes() -> None:
    methods, maps = _native_declaration("ISketch")
    assert "GetConstrainedStatus" in methods
    assert all("GetConstrainedStatus" not in values for values in maps.values())
    methods, maps = _native_declaration("IDimension")
    assert "DrivenState" not in methods
    assert "DrivenState" in maps["_prop_map_get_"] & maps["_prop_map_put_"]
    # A property called as a method is a real binding error, not a valid
    # adapter operation. Exercise that failure in the import-free census.
    wrong = ast.parse('def bad_binding():\n    dimension = _early_bound(None, "IDimension")\n    dimension.DrivenState()')
    assert _undeclared_bound_calls(wrong) == ["IDimension.DrivenState"]


def test_clamp_location_native_calls_and_projection_properties_match_pinned_typelib() -> None:
    tree = _tree(SCRIPTS / "build_mg_magnifying_clamp.py")
    assert not _undeclared_bound_calls(tree)
    assert not _undeclared_bound_calls(_tree(SCRIPTS / "draw_mg_magnifying_clamp.py"))
    selection = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Select4")
    for interface in ("IEntity", "ISketchPoint", "ISketchSegment"):
        methods, _maps = _native_declaration(interface)
        assert _can_bind(selection, methods["Select4"])
    _methods, maps = _native_declaration("ICurve")
    assert "CircleParams" in maps["_prop_map_get_"]
    _methods, maps = _native_declaration("IDisplayDimension")
    assert "ShowParenthesis" in maps["_prop_map_get_"] & maps["_prop_map_put_"]
    mutated = copy.deepcopy(tree)
    conversion = next(node for node in ast.walk(mutated) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "SketchUseEdge3")
    conversion.args.append(ast.Constant(False))
    assert "ISketchManager.SketchUseEdge3 arguments" in _undeclared_bound_calls(mutated)
    for interface, property_name in (
        ("ISketch", "ModelToSketchTransform"),
        ("ISketchPoint", "X"),
        ("ISketchPoint", "Y"),
        ("IMathPoint", "ArrayData"),
        ("IFeature", "Name"),
    ):
        _methods, maps = _native_declaration(interface)
        assert property_name in maps["_prop_map_get_"]
    rim = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "SetSelectionPoint2")
    assert _can_bind(rim, _native_declaration("ISelectionMgr")[0]["SetSelectionPoint2"])
    mutated = copy.deepcopy(tree)
    rim = next(node for node in ast.walk(mutated) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "SetSelectionPoint2")
    rim.func.attr = "SetSelectionPoint"
    assert "ISelectionMgr.SetSelectionPoint arguments" in _undeclared_bound_calls(mutated)
    mutated = copy.deepcopy(tree)
    identifier = next(node for node in ast.walk(mutated) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "GetID")
    identifier.args.append(ast.Constant(0))
    assert "ISketchSegment.GetID arguments" in _undeclared_bound_calls(mutated)
    inventory = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "GetFeatures")
    assert _can_bind(inventory, _native_declaration("IFeatureManager")[0]["GetFeatures"])
    mutated = copy.deepcopy(tree)
    inventory = next(node for node in ast.walk(mutated) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "GetFeatures")
    inventory.args.append(ast.Constant(False))
    assert "IFeatureManager.GetFeatures arguments" in _undeclared_bound_calls(mutated)
    assert "FeatureManager" in _native_declaration("IModelDoc2")[1]["_prop_map_get_"]


def _native_return_type(method):
    """Read generated invocation metadata as AST data, never import COM."""
    invocations = [
        node for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("InvokeTypes", "_ApplyTypes_")
    ]
    assert len(invocations) == 1, f"{method.name}: expected one native invocation"
    invocation = invocations[0]
    result_index = 3 if invocation.func.attr == "InvokeTypes" else 2
    return ast.literal_eval(invocation.args[result_index])


@pytest.mark.parametrize("interface, member, retval", (
    ("IFeatureManager", "GetFeatures", 12),
    ("IFeature", "GetTypeName2", 8),
    ("IFeature", "GetSpecificFeature2", 9),
    ("ISketchSegment", "GetSketch", 9),
    ("ISketchSegment", "GetType", 3),
    ("ISketchSegment", "GetID", 12),
    ("ISldWorks", "IsSame", 3),
    ("ISelectionMgr", "GetSelectedObjectCount2", 3),
    ("ISelectionMgr", "GetSelectedObject6", 9),
    ("ISelectionMgr", "GetSelectedObjectType3", 3),
    ("ISelectionMgr", "SetSelectionPoint2", 11),
    ("ISelectionMgr", "GetSelectionPointInSketchSpace2", 12),
    ("ISketchArc", "GetCenterPoint2", 9),
    ("ISketchArc", "GetRadius", 5),
    ("IMathTransform", "Inverse", 9),
    ("ISldWorks", "GetMathUtility", 9),
    ("IMathUtility", "CreatePoint", 9),
    ("IMathPoint", "MultiplyTransform", 9),
    ("IModelDoc2", "AddDimension2", 9),
    ("IModelDoc2", "AddHorizontalDimension2", 9),
    ("IModelDoc2", "ClearSelection2", 24),
    ("IModelDoc2", "GraphicsRedraw2", 24),
    ("ISldWorks", "SetUserPreferenceToggle", 24),
    ("ISldWorks", "GetUserPreferenceToggle", 11),
    ("IDisplayDimension", "GetDimension2", 9),
    ("IDisplayDimension", "GetAnnotation", 9),
    ("IAnnotation", "GetAttachedEntities3", 12),
    ("IAnnotation", "GetAttachedEntityTypes", 12),
    ("IAnnotation", "IsDangling", 11),
    ("IDimension", "GetArcEndCondition", 3),
    ("IDimension", "SetArcEndCondition", 3),
))
def test_clamp_native_methods_have_declared_result_shapes_not_adapter_contracts(interface, member, retval) -> None:
    methods, maps = _native_declaration(interface)
    assert member in methods
    assert all(member not in values for values in maps.values())
    assert _native_return_type(methods[member]) == (retval, 0)


def test_native_return_type_census_distinguishes_void_mutators() -> None:
    # Positive controls exercise both generated calling forms. A VT_VOID
    # setter cannot be used as a success boolean even though the adapter can.
    setter = _native_declaration("ISldWorks")[0]["SetUserPreferenceToggle"]
    assert _native_return_type(setter) == (24, 0)
    assert _native_return_type(_native_declaration("IFeatureManager")[0]["GetFeatures"]) == (12, 0)
    mutated = copy.deepcopy(setter)
    invocation = next(node for node in ast.walk(mutated) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "InvokeTypes")
    invocation.args[3] = ast.Tuple(elts=[ast.Constant(11), ast.Constant(0)], ctx=ast.Load())
    assert _native_return_type(mutated) != _native_return_type(setter)


@pytest.mark.parametrize("recipe", ("draw_mg_magnifying_bracket.py", "draw_mg_magnifying_lever.py"))
def test_repaired_drawing_native_calls_bind_including_inline_interfaces(recipe) -> None:
    assert not _undeclared_bound_calls(_tree(SCRIPTS / recipe))
    wrong = ast.parse('def inline_binding(): _early_bound(None, "ISilhouetteEdge").NotADeclaredFaceAccessor()')
    assert _undeclared_bound_calls(wrong) == ["ISilhouetteEdge.NotADeclaredFaceAccessor"]
    for interface, property_name in (
        ("IView", "ReferencedDocument"),
        ("IView", "ModelToViewTransform"),
        ("IDimension", "FullName"),
        ("IDimension", "SystemValue"),
        ("ICThread", "ThreadCallout"),
        ("IAnnotation", "Owner"),
        ("IAnnotation", "OwnerType"),
        ("ICalloutVariable", "VariableName"),
        ("ICalloutVariable", "Type"),
        ("ICalloutStringVariable", "String"),
    ):
        assert property_name in _native_declaration(interface)[1]["_prop_map_get_"]
    # This drawing property returns INote; it is not the model feature's
    # writable ThreadCallout string. Owner/OwnerType are read only in practice
    # per SDK remarks even though the typelib also advertises their setters.
    assert "ThreadCallout" not in _native_declaration("ICThread")[1]["_prop_map_put_"]


@pytest.mark.parametrize("interface, member, arity, retval", (
    ("IView", "GetOutline", 0, 12),
    ("IView", "GetNotes", 0, 12),
    ("IView", "GetAnnotationsByType", 1, 12),
    ("IView", "SetViewPosition", 2, 11),
    ("INote", "GetExtent", 0, 12),
    ("INote", "GetAnnotation", 0, 9),
    ("IAnnotation", "GetPosition", 0, 12),
))
def test_bracket_layout_native_method_contracts(interface, member, arity, retval) -> None:
    methods, maps = _native_declaration(interface)
    assert member in methods
    assert all(member not in values for values in maps.values())
    assert _native_return_type(methods[member]) == (retval, 0)
    call = ast.Call(
        func=ast.Attribute(value=ast.Name(id="native", ctx=ast.Load()), attr=member, ctx=ast.Load()),
        args=[ast.Constant(None) for _ in range(arity)],
        keywords=[],
    )
    assert _can_bind(call, methods[member])
    call.args.append(ast.Constant(None))
    assert not _can_bind(call, methods[member])


@pytest.mark.parametrize("interface, member", (
    ("IView", "Angle"),
    ("IView", "Position"),
    ("INote", "PropertyLinkedText"),
))
def test_bracket_layout_native_properties_are_not_methods(interface, member) -> None:
    methods, maps = _native_declaration(interface)
    assert member not in methods
    assert member in maps["_prop_map_get_"] & maps["_prop_map_put_"]
