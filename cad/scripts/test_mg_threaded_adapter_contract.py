"""Import-free adapter signature and focused declared-native-interface checks.

The adapter census checks the pinned SDK MRO, NOT the COM contracts beneath it.
The separate native-member check parses the generated typelib as data and catches
undeclared members, call arity and result-shape mistakes on explicit bindings.
It cannot prove that QI supplied the requested interface or that a DISPID applies
to a live dispatch. Selection/attachment integer results use swSelectType_e:
the 11/25 ISketchPoint distinction needs SDK semantics and behavioral coverage,
not a different method signature. Dynamic callout metadata needs its own gates.
Relation effects require actual owner-inventory readback: a constructor's returned
handle and this declaration census cannot prove which constraint was applied.
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
        ("ISketchPoint", "Z"),
        ("ISketch", "RelationManager"),
        ("ISketchManager", "AddToDB"),
        ("ISketchSegment", "ConstructionGeometry"),
        ("ISketchRelation", "Suppressed"),
        ("ISketchPoint", "Y"),
        ("IMathPoint", "ArrayData"),
        ("IFeature", "Name"),
    ):
        _methods, maps = _native_declaration(interface)
        assert property_name in maps["_prop_map_get_"]
    creation = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "CreateLine")
    assert _can_bind(creation, _native_declaration("ISketchManager")[0]["CreateLine"])
    mutated = copy.deepcopy(tree)
    creation = next(node for node in ast.walk(mutated) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "CreateLine")
    creation.args.append(ast.Constant(0.0))
    assert "ISketchManager.CreateLine arguments" in _undeclared_bound_calls(mutated)
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


@pytest.mark.parametrize("recipe", (
    "draw_mg_magnifying_bracket.py",
    "draw_mg_magnifying_lever.py",
    "draw_mg_magnifying_clamp.py",
    "draw_mg_magnifier_assembly.py",
))
def test_repaired_drawing_native_calls_bind_including_inline_interfaces(recipe) -> None:
    assert not _undeclared_bound_calls(_tree(SCRIPTS / recipe))
    wrong = ast.parse('def inline_binding(): _early_bound(None, "ISilhouetteEdge").NotADeclaredFaceAccessor()')
    assert _undeclared_bound_calls(wrong) == ["ISilhouetteEdge.NotADeclaredFaceAccessor"]
    for interface, property_name in (
        ("IView", "ReferencedDocument"),
        ("IModelDoc2", "Extension"),
        ("IView", "ModelToViewTransform"),
        ("IDimension", "FullName"),
        ("IDimension", "SystemValue"),
        ("IDimension", "Tolerance"),
        ("IDimensionTolerance", "Type"),
        ("ICThread", "ThreadCallout"),
        ("IAnnotation", "Owner"),
        ("IAnnotation", "OwnerType"),
        ("IAnnotation", "Visible"),
        ("ICalloutVariable", "VariableName"),
        ("ICalloutVariable", "Type"),
        ("ICalloutStringVariable", "String"),
        ("IDrawingComponent", "Component"),
        ("IDrawingComponent", "Visible"),
        ("IComponent2", "Name2"),
        ("IComponent2", "Transform2"),
        ("ICurve", "CircleParams"),
        ("IMathPoint", "ArrayData"),
    ):
        assert property_name in _native_declaration(interface)[1]["_prop_map_get_"]
    # This drawing property returns INote; it is not the model feature's
    # writable ThreadCallout string. Owner/OwnerType are read only in practice
    # per SDK remarks even though the typelib also advertises their setters.
    assert "ThreadCallout" not in _native_declaration("ICThread")[1]["_prop_map_put_"]


@pytest.mark.parametrize("interface, member, arity, retval", (
    ("ISketchManager", "CreateLine", 6, 9),
    ("ISketch", "GetSketchSegments", 0, 12),
    ("ISldWorks", "IsSame", 2, 3),
    ("ISketchRelationManager", "AddRelation", 2, 9),
    ("ISketchRelation", "GetRelationType", 0, 3),
    ("ISketchRelation", "GetDefinitionEntities2", 0, 12),
    ("ISketchRelation", "GetEntities", 0, 12),
    ("ISketchRelation", "GetEntitiesType", 0, 12),
    ("ISketchPoint", "GetID", 0, 12),
    ("ISketchSegment", "GetRelations", 0, 12),
    ("ISketchPoint", "GetRelations", 0, 12),
    ("ISketchPoint", "GetSketch", 0, 9),
    ("ISketchLine", "GetStartPoint2", 0, 9),
    ("ISketchLine", "GetEndPoint2", 0, 9),
    ("IDisplayDimension", "GetAnnotation", 0, 9),
    ("IView", "GetOutline", 0, 12),
    ("IView", "GetNotes", 0, 12),
    ("IView", "GetAnnotationsByType", 1, 12),
    ("IView", "SetViewPosition", 2, 11),
    ("INote", "GetExtent", 0, 12),
    ("INote", "GetAnnotation", 0, 9),
    ("IAnnotation", "GetPosition", 0, 12),
    ("IDisplayDimension", "GetDisplayData", 0, 9),
    ("IPartDoc", "FeatureByName", 1, 9),
    ("IView", "GetCorresponding", 1, 9),
    ("IFeature", "GetFaces", 0, 12),
    ("IModelDocExtension", "GetCorrespondingEntity2", 1, 9),
    ("IModelDocExtension", "GetCorresponding2", 1, 9),
    ("INote", "GetText", 0, 8),
    ("IAnnotation", "GetAttachedEntities3", 0, 12),
    ("IAnnotation", "GetAttachedEntityCount3", 0, 3),
    ("IAnnotation", "GetAttachedEntityTypes", 0, 12),
    ("IAnnotation", "GetLeaderCount", 0, 3),
    ("IAnnotation", "IsDangling", 0, 11),
    ("IAnnotation", "GetDisplayData", 0, 9),
    ("IDisplayData", "GetTextCount", 0, 3),
    ("IDisplayData", "GetTextAtIndex", 1, 8),
    ("IDisplayData", "GetTextPositionAtIndex", 1, 12),
    ("IDisplayData", "GetTextHeightAtIndex", 1, 5),
    ("IDisplayData", "GetTextRefPositionAtIndex", 1, 3),
    ("IDisplayData", "GetTextAngleAtIndex", 1, 5),
    ("IDisplayData", "GetTextLineSpacingAtIndex", 1, 5),
    ("IDrawingDoc", "GetViews", 0, 12),
    ("IDisplayData", "GetArrowHeadCount", 0, 3),
    ("IDisplayData", "GetArrowHeadAtIndex2", 1, 12),
    ("IDimensionTolerance", "GetMinValue", 0, 5),
    ("IDimensionTolerance", "GetMaxValue", 0, 5),
    ("IDisplayDimension", "SetPrecision3", 4, 3),
    ("IDisplayDimension", "GetPrimaryPrecision2", 0, 3),
    ("IAnnotation", "Select2", 2, 11),
    ("IEdge", "GetCurve", 0, 9),
    ("ICurve", "IsCircle", 0, 11),
    ("IEdge", "GetClosestPointOn", 3, 12),
    ("IComponent2", "GetPathName", 0, 8),
    ("IView", "GetVisibleDrawingComponents", 0, 12),
    ("IView", "GetVisibleComponents", 0, 12),
    ("IView", "GetVisibleEntities2", 2, 12),
    ("IView", "GetPolylines7", 2, 12),
    ("IView", "GetDetailCircleInfo2", 0, 12),
    ("IView", "UpdateViewDisplayGeometry", 0, 24),
    ("ISketchSegment", "Select4", 2, 11),
    ("ISldWorks", "GetMathUtility", 0, 9),
    ("IMathUtility", "CreatePoint", 1, 9),
    ("IMathPoint", "MultiplyTransform", 1, 9),
    ("IView", "GetCThreads", 0, 12),
    ("IView", "GetDisplayMode2", 0, 3),
    ("IView", "GetCThreadQuality", 0, 11),
    ("ICThread", "GetAnnotation", 0, 9),
    ("ICThread", "GetDisplayData", 0, 9),
    ("IDisplayData", "GetLineCount", 0, 3),
    ("IDisplayData", "GetLineAtIndex2", 1, 12),
    ("IDisplayData", "GetPolyLineCount", 0, 3),
    ("IDisplayData", "GetPolylineAtIndex2", 1, 12),
    ("IDisplayData", "GetArcCount", 0, 3),
    ("IDisplayData", "GetArcAtIndex2", 1, 12),
    ("IView", "GetBaseView", 0, 9),
    ("IModelDoc2", "GetPathName", 0, 8),
    ("IModelDoc2", "GetType", 0, 3),
    ("IModelDoc2", "ViewZoomtofit2", 0, 24),
    ("IFace2", "GetEdges", 0, 12),
    ("IModelDocExtension", "GetPersistReference3", 1, 12),
    ("IModelDocExtension", "IsSamePersistentID", 2, 3),
    ("IDimension", "GetFeatureOwner", 0, 9),
    ("IModelDoc2", "GetSaveFlag", 0, 11),
    ("IModelDoc2", "GetTitle", 0, 8),
    ("IModelDoc2", "GetLayerManager", 0, 9),
    ("IModelDocExtension", "GetUserPreferenceToggle", 2, 11),
    ("IFeature", "GetDefinition", 0, 9),
    ("IView", "GetOrientationName", 0, 8),
    ("IView", "GetFacettedHlrDisplay", 0, 11),
    ("IView", "GetUseParentDisplayMode", 0, 11),
    ("ISldWorks", "RevisionNumber", 0, 8),
    ("ILayerMgr", "GetLayer", 1, 9),
))
def test_witness_and_bracket_native_method_contracts(interface, member, arity, retval) -> None:
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
    ("IDisplayDimension", "CenterText"),
    ("IDisplayDimension", "OffsetText"),
    ("IDisplayDimension", "ShowParenthesis"),
    ("IDimension", "Name"),
    ("IAnnotation", "Visible"),
    ("INote", "PropertyLinkedText"),
))
def test_bracket_layout_native_properties_are_not_methods(interface, member) -> None:
    methods, maps = _native_declaration(interface)
    assert member not in methods
    assert member in maps["_prop_map_get_"] & maps["_prop_map_put_"]


@pytest.mark.parametrize("interface, member", (
    ("ISketchManager", "AddToDB"),
    ("ISketchSegment", "ConstructionGeometry"),
))
def test_witness_native_mutators_are_declared_read_write_properties(interface, member) -> None:
    # Declaration/read-write support does not imply endpoint uniqueness:
    # AddToDB suppresses inference, but exact-coordinate DB points still merge.
    methods, maps = _native_declaration(interface)
    assert member not in methods
    assert member in maps["_prop_map_get_"] & maps["_prop_map_put_"]


@pytest.mark.parametrize("classifier_name", ("_witness_relation_records", "_point_identity", "_point_flat_attachment"))
@pytest.mark.parametrize(("interface", "iid"), (
    ("ISketchPoint", "{83A33DBD-27C5-11CE-BFD4-00400513BB57}"),
    ("ISketchSegment", "{83A33DBF-27C5-11CE-BFD4-00400513BB57}"),
))
def test_definition_capability_uses_pinned_interface_iids_not_coclass_ids(interface, iid, classifier_name) -> None:
    # Parse only: importing the generated module here would load pywin32.
    # Neither point-key agreement nor native QI is proven by this offline census.
    wrapper = SCRIPTS.parent.parent / "SolidworksMCP-python" / "src" / "solidworks_mcp" / "adapters" / "_generated" / "sldworks_2026.py"
    declaration = next(node for node in _tree(wrapper).body if isinstance(node, ast.ClassDef) and node.name == interface)
    assert any(isinstance(base, ast.Name) and base.id == "DispatchBaseClass" for base in declaration.bases)
    identifiers = {}
    for node in declaration.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "IID":
            for target in node.targets:
                if isinstance(target, ast.Name):
                    identifiers[target.id] = ast.literal_eval(node.value.args[0])
    assert identifiers["CLSID"] == iid
    assert identifiers["coclass_clsid"] != iid
    classifier = next(node for node in _tree(SCRIPTS / "build_mg_magnifying_clamp.py").body if isinstance(node, ast.FunctionDef) and node.name == classifier_name)
    imported_interfaces = {
        alias.name
        for node in ast.walk(classifier)
        if isinstance(node, ast.ImportFrom) and node.module == "solidworks_mcp.adapters._generated.sldworks_2026"
        for alias in node.names
    }
    assert interface in imported_interfaces
    methods, _maps = _native_declaration(interface)
    assert _native_return_type(methods["GetID"]) == (12, 0)
    assert _native_return_type(methods["GetSketch"]) == (9, 0)


def test_native_polyline_census_retains_optional_variant_out_parameter() -> None:
    method = _native_declaration("IView")[0]["GetPolylines7"]
    invocation = next(
        node for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("InvokeTypes", "_ApplyTypes_")
    )
    argument_index = 4 if invocation.func.attr == "InvokeTypes" else 3
    assert ast.literal_eval(invocation.args[argument_index]) == ((2, 1), (16396, 2))
    # Native SHORT input, optional BYREF VARIANT output. The one-argument
    # recipe call is valid; the full two-argument signature is checked above.
    call = ast.parse("native.GetPolylines7(1)").body[0].value
    assert _can_bind(call, method)


@pytest.mark.parametrize("interface, member, retval, writable", (
    ("IDrawingComponent", "Component", 9, False),
    ("IDrawingComponent", "Visible", 11, True),
    ("IComponent2", "Name2", 8, True),
    ("IComponent2", "Visible", 3, True),
    ("IComponent2", "Transform2", 9, True),
    ("ICurve", "CircleParams", 12, False),
    ("IMathPoint", "ArrayData", 12, True),
    ("ISketchManager", "AddToDB", 11, True),
    # These diagnostics only read getters. Typelib setter entries are ABI
    # metadata, not permission to mutate SDK-documented read-only properties.
    ("IAnnotation", "Owner", 9, True),
    ("IAnnotation", "OwnerType", 3, True),
    ("IAnnotation", "Layer", 8, True),
    ("ISldWorks", "ActiveDoc", 9, False),
    ("IView", "ReferencedConfiguration", 8, True),
    ("IView", "ModelToViewTransform", 9, True),
    ("IMathTransform", "ArrayData", 12, True),
    ("ILayer", "Visible", 11, True),
    ("ILayer", "Printable", 11, True),
    ("IWizardHoleFeatureData2", "Type", 3, True),
    ("IWizardHoleFeatureData2", "FastenerSize", 8, True),
    ("IWizardHoleFeatureData2", "EndCondition", 3, True),
    ("IWizardHoleFeatureData2", "ThreadEndCondition", 3, True),
    ("IWizardHoleFeatureData2", "ThreadClass", 8, True),
    ("IWizardHoleFeatureData2", "CosmeticThreadType", 3, True),
    ("IWizardHoleFeatureData2", "HoleDepth", 5, True),
    ("IWizardHoleFeatureData2", "TapDrillDepth", 5, True),
    ("IWizardHoleFeatureData2", "ThruTapDrillDepth", 5, True),
    ("IWizardHoleFeatureData2", "ThreadDepth", 5, True),
    ("IWizardHoleFeatureData2", "TapDrillDiameter", 5, True),
    ("IWizardHoleFeatureData2", "ThruTapDrillDiameter", 5, True),
    ("IWizardHoleFeatureData2", "ThreadDiameter", 5, True),
))
def test_thread_detail_geometry_properties_have_native_result_shapes(interface, member, retval, writable) -> None:
    methods, maps = _native_declaration(interface)
    assert member not in methods
    assert member in maps["_prop_map_get_"]
    assert (member in maps["_prop_map_put_"]) is writable
    wrapper = SCRIPTS.parent.parent / "SolidworksMCP-python" / "src" / "solidworks_mcp" / "adapters" / "_generated" / "sldworks_2026.py"
    declaration = next(node for node in _tree(wrapper).body if isinstance(node, ast.ClassDef) and node.name == interface)
    getter_map = next(
        node.value for node in declaration.body
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "_prop_map_get_" for target in node.targets)
    )
    entry = next(value for key, value in zip(getter_map.keys, getter_map.values, strict=True) if ast.literal_eval(key) == member)
    assert ast.literal_eval(entry)[2] == (retval, 0)
