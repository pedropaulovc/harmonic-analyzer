"""Lever source-only adapter bindings and extracted sketch geometry contracts.

Read the pinned SDK's actual source-derived MRO, never import it or the recipe.
The extracted helper runs only against a geometry recorder: this proves the
emitted primitives/dimension equations, not native constraint solving or COM.
"""

from __future__ import annotations

import ast
import asyncio
import copy
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import sm_summing_lever_profile as profile
import sm_summing_lever_spec as spec
from test_pd_transgear_adapter_contract import (
    _adapter_calls,
    _adapter_methods,
    _missing,
    _signature,
    _tree,
)

RECIPE = Path(__file__).with_name("build_sm_summing_lever.py")
Function = ast.FunctionDef | ast.AsyncFunctionDef


def _scope(tree: ast.Module, call: ast.Call) -> Function:
    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.lineno <= call.lineno <= node.end_lineno
    ]
    assert functions, f"adapter call outside a function at {call.lineno}"
    return min(functions, key=lambda node: node.end_lineno - node.lineno)


def _fixed_star_items(value: ast.expr, scope: Function, before: int) -> list[ast.expr]:
    """Resolve actual recipe tuple literals; never guess arity from SDK names."""
    if isinstance(value, (ast.Tuple, ast.List)):
        assert not any(isinstance(item, ast.Starred) for item in value.elts)
        return value.elts
    if isinstance(value, ast.Name):
        definitions = [
            node for node in ast.walk(scope)
            if isinstance(node, ast.Assign) and node.lineno < before
            and any(isinstance(target, ast.Name) and target.id == value.id for target in node.targets)
        ]
        assert definitions, f"unresolved tuple {value.id} at {before}"
        latest = max(definitions, key=lambda node: node.lineno)
        return _fixed_star_items(latest.value, scope, latest.lineno)
    if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Slice):
        # The only sliced expansion is a receiver's point[:2]. Its input
        # points' real three-coordinate shape is pinned by the pure joint test.
        slice_ = value.slice
        assert slice_.lower is None and slice_.step is None
        assert isinstance(slice_.upper, ast.Constant) and slice_.upper.value == 2
        assert isinstance(value.value, ast.Name) and value.value.id == "point"
        return [ast.Constant(0.0), ast.Constant(0.0)]
    raise AssertionError(f"unresolved starred recipe argument: {ast.unparse(value)}")


def _bind_call(tree: ast.Module, call: ast.Call) -> None:
    path, method = _adapter_methods()[call.func.attr]
    receiver = [] if any(
        isinstance(item, ast.Name) and item.id == "staticmethod"
        for item in method.decorator_list
    ) else [call.func.value]
    arguments = []
    for argument in call.args:
        arguments.extend(
            _fixed_star_items(argument.value, _scope(tree, call), call.lineno)
            if isinstance(argument, ast.Starred) else [argument]
        )
    assert all(keyword.arg is not None for keyword in call.keywords), "unresolved **kwargs"
    try:
        _signature(method).bind(
            *receiver, *arguments,
            **{keyword.arg: keyword.value for keyword in call.keywords},
        )
    except TypeError as error:
        pytest.fail(
            f"{RECIPE.name}:{call.lineno}: {call.func.attr} cannot bind "
            f"{path}:{method.lineno}: {error}"
        )


def test_every_lever_adapter_call_exists_and_binds_to_the_pinned_sdk_mro() -> None:
    tree = _tree(RECIPE)
    calls = _adapter_calls(tree)
    assert calls, "empty lever adapter census"
    assert {
        "create_part", "create_sketch", "add_line", "add_arc",
        "add_sketch_constraint", "add_sketch_dimension", "create_extrusion",
        "add_fillet", "get_mass_properties",
    } <= {call.func.attr for call in calls}
    assert not _missing(tree), f"undeclared lever adapter calls: {sorted(_missing(tree))}"
    changed = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_rib_profile_sketch"
    )
    changed_calls = _adapter_calls(changed)
    assert {"add_line", "add_arc", "add_sketch_constraint", "add_sketch_dimension"} <= {
        call.func.attr for call in changed_calls
    }
    for call in calls:
        _bind_call(tree, call)
    # Positive inherited lookup control: the sketch method is supplied by the
    # real mixin, not by an invented flattened public-method allowlist.
    owner, _ = _adapter_methods()["add_arc"]
    assert owner.name == "sketch.py"


def test_lever_census_rejects_a_nonexistent_changed_call_without_importing_recipe() -> None:
    tree = copy.deepcopy(_tree(RECIPE))
    helper = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_rib_profile_sketch"
    )
    calls = [call for call in _adapter_calls(helper) if call.func.attr == "add_arc"]
    assert len(calls) == 1  # The helper emits every profile arc through this call.
    calls[0].func.attr = "add_nonexistent_lever_profile_arc"
    assert _missing(tree) == {"add_nonexistent_lever_profile_arc"}


def test_lever_signature_binding_rejects_a_missing_geometry_argument() -> None:
    tree = copy.deepcopy(_tree(RECIPE))
    helper = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_rib_profile_sketch"
    )
    call = next(call for call in _adapter_calls(helper) if call.func.attr == "add_line")
    call.args.pop()
    method = _adapter_methods()["add_line"][1]
    with pytest.raises(TypeError):
        _signature(method).bind(call.func.value, *call.args)


class _SketchRecorder:
    def __init__(self) -> None:
        self.primitives = {}
        self.constraints = []
        self.dimensions = []
        self.anchors = []
        self.distances = []
        self.records = []
        self.events = []

    def _result(self, value):
        return SimpleNamespace(is_success=True, data=value, error=None)

    def _primitive(self, kind: str, values: tuple[float, ...]):
        identifier = f"{kind}{len(self.primitives)}"
        self.primitives[identifier] = (kind, values)
        return self._result(identifier)

    async def create_sketch(self, plane):
        self.events.append(("create", plane))
        return self._result(None)

    async def add_line(self, x1, y1, x2, y2):
        return self._primitive("line", (x1, y1, x2, y2))

    async def add_arc(self, cx, cy, x1, y1, x2, y2):
        return self._primitive("arc", (cx, cy, x1, y1, x2, y2))

    async def add_sketch_constraint(self, first, second, relation):
        self.constraints.append((first, second, relation))
        return self._result(None)

    async def add_sketch_dimension(self, first, second, kind, value):
        self.dimensions.append((first, second, kind, value))
        return self._result(None)

    async def create_extrusion(self, parameters):
        self.events.append(("extrude", parameters))
        return self._result(None)

    async def exit_sketch(self):
        self.events.append(("exit",))
        return self._result(None)


def _extracted_sketch(section: profile.RibProfile, *, mutation: str | None = None):
    """Compile only this source function, with no top-level recipe execution."""
    helper = copy.deepcopy(next(
        node for node in _tree(RECIPE).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_rib_profile_sketch"
    ))
    if mutation == "omit_tangency":
        loop = next(
            node for node in ast.walk(helper)
            if isinstance(node, ast.For) and isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "enumerate"
        )
        loop.body = [ast.Pass()]
    elif mutation == "wrong_thickness":
        for node in ast.walk(helper):
            if isinstance(node, ast.Name) and node.id == "COEFFICIENT_T":
                node.id = "COUNTER_WEB_T"
    elif mutation is not None:
        raise AssertionError(mutation)
    recorder = _SketchRecorder()

    class Dims:
        def record(self, name, equation):
            recorder.records.append((name, equation))

        def apply(self, adapter, name):
            recorder.events.append(("apply", name))
            return [(f"{dimension}@{name}", equation) for dimension, equation in recorder.records]

    def check(label, result):
        assert result.is_success, label
        return result.data

    async def anchor(adapter, entity, x, y, label):
        recorder.anchors.append((entity, x, y))

    async def distance(adapter, first, second, kind, value, label):
        recorder.distances.append((first, second, kind, value))

    async def fully_defined(adapter, label):
        recorder.events.append(("fully_defined_requested",))

    globals_ = {
        "math": math, "SketchDims": Dims, "check": check,
        "set_sketch_direct_db": lambda adapter, value: recorder.events.append(("direct_db", value)),
        "anchor_point_to_origin": anchor, "dimension_between": distance,
        "ensure_fully_defined": fully_defined,
        "name_last_feature": lambda adapter, name: recorder.events.append(("name", name)),
        "UPPER": section.upper, "LOWER": section.lower,
        "ARC_R": section.wrap_radius, "TIP_X": spec.TIP_X,
        "COEFFICIENT_T": section.top_y - section.bottom_y,
        "COUNTER_WEB_T": spec.COUNTER_WEB_T, "RIB_BLEND_R": section.blend_radius,
    }
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), helper,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(RECIPE), "exec"), globals_)
    return globals_["_rib_profile_sketch"], recorder


def _assert_recorded_sketch(
    recorder: _SketchRecorder, section: profile.RibProfile, middle: bool,
    jobs: list[tuple[str, str]], stem: str,
) -> None:
    lines = {key: values for key, (kind, values) in recorder.primitives.items() if kind == "line"}
    arcs = {key: values for key, (kind, values) in recorder.primitives.items() if kind == "arc"}
    assert len(lines) == (5 if middle else 3)
    assert len(arcs) == (4 if middle else 3)
    expected_lines = [
        (*section.upper.end_xy, *section.lower.end_xy),
        (*section.upper.wrap_xy, *section.upper.flank_xy),
        (*section.lower.flank_xy, *section.lower.wrap_xy),
    ]
    expected_arcs = [
        (*section.upper.center_xy, *section.upper.flank_xy, *section.upper.end_xy),
        (*section.lower.center_xy, *section.lower.end_xy, *section.lower.flank_xy),
    ]
    if middle:
        x = section.wrap_radius**2 / spec.TIP_X
        y = section.wrap_radius * math.sqrt(1.0 - section.wrap_radius**2 / spec.TIP_X**2)
        expected_lines += [(x, y, spec.TIP_X, 0.0), (spec.TIP_X, 0.0, x, -y)]
        expected_arcs += [(0.0, 0.0, *section.upper.wrap_xy, x, y),
                          (0.0, 0.0, x, -y, *section.lower.wrap_xy)]
    else:
        expected_arcs += [(0.0, 0.0, *section.upper.wrap_xy, *section.lower.wrap_xy)]
    for expected in expected_lines:
        assert any(values == pytest.approx(expected) for values in lines.values())
    for expected in expected_arcs:
        assert any(values == pytest.approx(expected) for values in arcs.values())
    tangencies = [(a, b) for a, b, relation in recorder.constraints if relation == "tangent"]
    assert len(tangencies) == (6 if middle else 4)
    for first, second in tangencies:
        first_kind, first_values = recorder.primitives[first]
        second_kind, second_values = recorder.primitives[second]
        assert {first_kind, second_kind} == {"arc", "line"}
        arc = first_values if first_kind == "arc" else second_values
        line = first_values if first_kind == "line" else second_values
        endpoints = [line[:2], line[2:]]
        common = [point for point in endpoints if any(
            point == pytest.approx(arc_point) for arc_point in (arc[2:4], arc[4:6])
        )]
        assert len(common) == 1
        dx, dy = line[2] - line[0], line[3] - line[1]
        radial = (common[0][0] - arc[0], common[0][1] - arc[1])
        assert dx * radial[0] + dy * radial[1] == pytest.approx(0.0, abs=1e-10)
    # Every emitted arc is the intended SDK-CCW path. A reversed wrap would
    # take the right-hand shortcut; a reversed blend would be nearly 360 deg.
    for cx, cy, ax, ay, bx, by in arcs.values():
        sweep = (math.atan2(by - cy, bx - cx) - math.atan2(ay - cy, ax - cx)) % math.tau
        radius = math.hypot(ax - cx, ay - cy)
        if radius == pytest.approx(section.blend_radius):
            assert 0.0 < sweep < math.pi / 2.0
        elif not middle:
            assert math.pi < sweep < math.tau
        else:
            assert 0.0 < sweep < math.pi
    radial_values = [value for _, _, kind, value in recorder.dimensions if kind == "radial"]
    assert radial_values == pytest.approx([section.wrap_radius, section.blend_radius, section.blend_radius])
    assert any(kind == "vertical_distance" and value == pytest.approx(section.top_y - section.bottom_y)
               for _, _, kind, value in recorder.distances)
    equations = [equation for _, equation in jobs]
    assert equations.count('"RibBlendR"') == 2
    assert equations.count('"ArcR"') == 1
    assert '"RibReach"' in equations and '"CoefficientTopY"' in equations and '"CoefficientT"' in equations
    assert ('"SumH"' in equations) == middle
    end = next(key for key, value in lines.items()
               if value == pytest.approx((*section.upper.end_xy, *section.lower.end_xy)))
    assert (f"{end}.start", *section.upper.end_xy) in recorder.anchors
    assert recorder.events[0] == ("create", "Front")
    assert ("direct_db", True) in recorder.events and ("direct_db", False) in recorder.events
    assert recorder.events.index(("direct_db", False)) < recorder.events.index(("fully_defined_requested",))
    assert recorder.events[-2:] == [("name", f"{stem}Profile"), ("apply", f"{stem}Profile")]


@pytest.mark.parametrize("middle,stem", [(False, "EdgeRibFront"), (False, "EdgeRibBack"), (True, "MiddleRib")])
@pytest.mark.parametrize("section", [profile.PROFILE, profile.RibProfile(
    wrap_radius=15.5, reach=36.0, blend_radius=0.6, top_y=2.7, bottom_y=-4.8,
)])
def test_extracted_builder_emits_actual_g1_primitives_and_dimension_equations(
    middle: bool, stem: str, section: profile.RibProfile,
) -> None:
    helper, recorder = _extracted_sketch(section)
    jobs = []
    asyncio.run(helper(recorder, stem, jobs, middle=middle))
    _assert_recorded_sketch(recorder, section, middle, jobs, stem)


@pytest.mark.parametrize("mutation", ["omit_tangency", "wrong_thickness"])
def test_extracted_sketch_contract_rejects_real_primitive_mutations(mutation: str) -> None:
    helper, recorder = _extracted_sketch(profile.PROFILE, mutation=mutation)
    jobs = []
    asyncio.run(helper(recorder, "MiddleRib", jobs, middle=True))
    with pytest.raises(AssertionError):
        _assert_recorded_sketch(recorder, profile.PROFILE, True, jobs, "MiddleRib")


def _source_helpers(names: tuple[str, ...], **bindings):
    """Extract exact helper bodies, substituting only their COM bind/import seam."""
    functions = []
    for name in names:
        function = copy.deepcopy(next(
            node for node in _tree(RECIPE).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        ))
        imports = [node for node in function.body if isinstance(node, ast.ImportFrom)]
        assert all(node.module == "magnifying_bracket_joint_layout" for node in imports)
        function.body = [node for node in function.body if not isinstance(node, ast.ImportFrom)]
        functions.append(function)
    namespace = {
        "math": math, "_early_bound": lambda value, interface: value,
        "_telemetry": SimpleNamespace(success=lambda message: None),
        "COEFFICIENT_T": spec.COEFFICIENT_T,
        "COEFFICIENT_TOP_Y": spec.COEFFICIENT_TOP_Y,
        "COEFFICIENT_BOTTOM_Y": spec.COEFFICIENT_BOTTOM_Y,
        "COUNTER_WEB_T": spec.COUNTER_WEB_T,
        "RIB_BLEND_R": spec.RIB_BLEND_R, "RIB_REACH": spec.RIB_REACH,
        "CYL_R": spec.CYL_R, "PLATE_L": spec.PLATE_L,
        "RIB_T": spec.COUNTER_WEB_T, "SUM_H": spec.SUM_H,
        "RIB_OFFSET": spec.PLATE_L / 2.0 - spec.COUNTER_WEB_T,
    }
    # Receiver depth has one authority; never duplicate 8.20 as an input knob.
    import magnifying_bracket_joint_layout as joint

    namespace["RECEIVER_RIB_OFFSET"] = spec.PLATE_L / 2.0 - joint.RIB_DEPTH
    namespace.update(
        RECEIVER_RIB_T=joint.RIB_DEPTH, SCREW_MAJOR_DIA=joint.SCREW_MAJOR_DIA,
        RECEIVER_WALL_MIN=joint.RECEIVER_WALL_MIN, LEVER_HOLE_POINTS=joint.LEVER_HOLE_POINTS,
        receiver_wall_margin=profile.receiver_wall_margin,
        receiver_wall_budget=profile.receiver_wall_budget,
    )
    namespace.update(bindings)
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *functions,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(RECIPE), "exec"), namespace)
    return namespace


class _Dimension:
    def __init__(self, name: str, millimetres: float):
        self.Name = name
        self.SystemValue = millimetres / 1000.0


class _NativeFeature:
    def __init__(self, dimensions=(), faces=()):
        self.dimensions = list(dimensions)
        self.faces = list(faces)

    def Parameter(self, name):
        return next((dimension for dimension in self.dimensions if dimension.Name == name), None)

    def GetFaces(self):
        return self.faces


def _feature_adapter(feature: _NativeFeature):
    return SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=lambda name: feature))


def _plane_face(height: float):
    surface = SimpleNamespace(
        IsPlane=lambda: True, PlaneParams=(0.0, 1.0, 0.0, 0.0, height / 1000.0, 0.0),
    )
    return SimpleNamespace(GetSurface=lambda: surface)


def _native_slab_fixture():
    features = {
        "PlateProfile": _NativeFeature([
            _Dimension("PlateThickness", spec.COEFFICIENT_T),
            _Dimension("PlateTopY", spec.COEFFICIENT_TOP_Y),
        ]),
        "CoefficientsPlate": _NativeFeature(
            [_Dimension("PlateLength", spec.PLATE_L)],
            [_plane_face(spec.COEFFICIENT_BOTTOM_Y), _plane_face(spec.COEFFICIENT_TOP_Y)],
        ),
    }
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.__getitem__))
    return adapter, features


def test_extracted_front_slab_preserves_real_seats_and_owner_specific_native_dimensions() -> None:
    namespace = _source_helpers(("_assert_coefficient_slab",))
    adapter, features = _native_slab_fixture()
    namespace["_assert_coefficient_slab"](adapter)
    features["CoefficientsPlate"].faces.reverse()
    namespace["_assert_coefficient_slab"](adapter)
    # The old 5.08 bottom must fail even if every named parameter still agrees.
    features["CoefficientsPlate"].faces = [
        _plane_face(spec.COEFFICIENT_TOP_Y), _plane_face(-2.54),
    ]
    with pytest.raises(RuntimeError, match="missing seat"):
        namespace["_assert_coefficient_slab"](adapter)
    # A correct value on the wrong feature is not persistent native ownership.
    adapter, features = _native_slab_fixture()
    thickness = features["PlateProfile"].dimensions.pop(0)
    features["CoefficientsPlate"].dimensions.append(thickness)
    with pytest.raises(RuntimeError, match="PlateProfile: native PlateThickness did not persist"):
        namespace["_assert_coefficient_slab"](adapter)


@pytest.mark.parametrize("owner,name", [
    ("PlateProfile", "PlateThickness"), ("PlateProfile", "PlateTopY"),
    ("CoefficientsPlate", "PlateLength"),
])
def test_extracted_front_slab_rejects_missing_or_changed_persistent_dimensions(owner: str, name: str) -> None:
    namespace = _source_helpers(("_assert_coefficient_slab",))
    adapter, features = _native_slab_fixture()
    dimension = features[owner].Parameter(name)
    nominal = dimension.SystemValue
    dimension.SystemValue += 0.001
    with pytest.raises(RuntimeError, match=f"{owner}: native {name} did not persist"):
        namespace["_assert_coefficient_slab"](adapter)
    dimension.SystemValue = nominal
    dimension.Name = "ObsoleteNativeName"
    with pytest.raises(RuntimeError, match=f"{owner}: native {name} did not persist"):
        namespace["_assert_coefficient_slab"](adapter)


def test_extracted_root_picks_are_reentrant_and_stay_off_entry_and_knife_caps() -> None:
    namespace = _source_helpers(("rib_root_edge_families",))
    families = namespace["rib_root_edge_families"]()
    assert [name for name, _, _ in families] == [
        "RibCylinderRootFillets", "RibCounterRootFillets", "RibRootFillets",
    ]
    assert [len(picks) for _, picks, _ in families] == [6, 4, 8]
    end_caps = (-namespace["RECEIVER_RIB_OFFSET"], namespace["RIB_OFFSET"])
    middle_caps = (-spec.COUNTER_WEB_T / 2.0, spec.COUNTER_WEB_T / 2.0)
    cylinder, counter, plate = [picks for _, picks, _ in families]
    assert cylinder[:2] == [[-spec.CYL_R, 0.0, z] for z in end_caps]
    assert cylinder[2:] == [[0.0, sign * spec.CYL_R, z]
                            for z in middle_caps for sign in (-1.0, 1.0)]
    assert counter == [[-30.0, sign * spec.COUNTER_WEB_T / 2.0, z]
                       for z in middle_caps for sign in (-1.0, 1.0)]
    assert plate == [[25.0, y, z] for z in (*end_caps, *middle_caps)
                     for y in (spec.COEFFICIENT_TOP_Y, spec.COEFFICIENT_BOTTOM_Y)]
    for _, picks, length in families:
        assert length > 0.0
        assert all(-spec.PLATE_L / 2.0 < z < spec.PLATE_L / 2.0 for _, _, z in picks)
        assert all(x < spec.RIB_REACH for x, _, _ in picks)


def _root_face(box_mm: tuple[float, ...], *, radius: float = 1.0, torus: bool = False):
    surface = SimpleNamespace(
        IsCylinder=lambda: not torus, IsTorus=lambda: torus,
        CylinderParams=(0.0,) * 6 + (radius / 1000.0,),
        TorusParams=(0.0,) * 7 + (radius / 1000.0,),
    )

    def extreme(dx, dy, dz):
        assert (dx, dy, dz) in {(1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 0.0, 1.0)}
        x, y = box_mm[3], box_mm[1]
        z = box_mm[2] if dz < 0.0 else box_mm[5]
        return True, x / 1000.0, y / 1000.0, z / 1000.0

    def approximate_box():
        raise AssertionError("native root proof must not use approximate GetBox")

    return SimpleNamespace(
        GetSurface=lambda: surface, GetBox=approximate_box,
        CreateSheetBody=lambda: SimpleNamespace(GetExtremePoint=extreme),
    )


@pytest.mark.parametrize("torus", [False, True])
def test_extracted_native_root_face_envelope_accepts_only_inboard_r1_surfaces(torus: bool) -> None:
    namespace = _source_helpers(("_assert_root_feature_bounds",))
    feature = _NativeFeature(faces=[_root_face((20.0, 2.54, -69.0, 30.0, 3.54, -67.0), torus=torus)])
    namespace["_assert_root_feature_bounds"](_feature_adapter(feature), "RibRootFillets", 1)
    for bad_box in (
        (20.0, 2.54, -69.0, spec.RIB_REACH + 0.1, 3.54, -67.0),
        (20.0, 2.54, -spec.PLATE_L / 2.0, 30.0, 3.54, -67.0),
        (20.0, 2.54, -69.0, 30.0, 3.54, spec.PLATE_L / 2.0),
        (20.0, 2.54, -69.0, math.nan, 3.54, -67.0),
    ):
        feature.faces = [_root_face(bad_box, torus=torus)]
        with pytest.raises(RuntimeError):
            namespace["_assert_root_feature_bounds"](_feature_adapter(feature), "RibRootFillets", 1)
    feature.faces = [_root_face((20.0, 2.54, -69.0, 30.0, 3.54, -67.0), radius=2.0, torus=torus)]
    with pytest.raises(RuntimeError, match="only 0 native"):
        namespace["_assert_root_feature_bounds"](_feature_adapter(feature), "RibRootFillets", 1)


@pytest.mark.parametrize("addition", [1.0, 0.0, -1.0, 1e8])
def test_extracted_root_operations_disable_propagation_and_gate_actual_added_volume(addition: float) -> None:
    operations = []
    proofs = []

    async def fillet(radius, picks, *, propagate):
        operations.append((radius, picks, propagate))
        return SimpleNamespace(is_success=True, data=None)

    async def volume(adapter, label):
        return 1000.0 + (addition if label.startswith("after ") else 0.0)

    def check(label, result):
        assert result.is_success, label
        return result.data

    namespace = _source_helpers(
        ("rib_root_edge_families", "_rib_root_fillets"),
        _measured_volume=volume, check=check,
        name_last_feature=lambda adapter, name: None,
        name_dimensions=lambda adapter, name, names: [f"{item}@{name}" for item in names],
        _assert_root_feature_bounds=lambda adapter, name, count: proofs.append((name, count)),
    )
    jobs = []
    helper = namespace["_rib_root_fillets"]
    adapter = SimpleNamespace(add_fillet=fillet)
    if addition <= 0.0 or addition > 1e6:
        with pytest.raises(RuntimeError, match="outside"):
            asyncio.run(helper(adapter, jobs))
        assert not proofs
        assert len(operations) == 1  # No fallback or retry of rejected native geometry.
    else:
        asyncio.run(helper(adapter, jobs))
        families = namespace["rib_root_edge_families"]()
        assert operations == [(spec.RIB_BLEND_R, picks, False) for _, picks, _ in families]
        assert proofs == [(name, len(picks)) for name, picks, _ in families]
        assert len(jobs) == 3 and all(expression == '"RibBlendR"' for _, expression in jobs)


@pytest.mark.parametrize("result", [None, (False, 0.0, 0.0, 0.0), (True, 0.0, 0.0),
                                     (True, math.nan, 0.0, 0.0)])
def test_extracted_root_extreme_readback_refuses_missing_or_invalid_exact_geometry(result) -> None:
    face = _root_face((20.0, 2.54, -69.0, 30.0, 3.54, -67.0))
    face.CreateSheetBody = lambda: SimpleNamespace(GetExtremePoint=lambda dx, dy, dz: result)
    feature = _NativeFeature(faces=[face])
    namespace = _source_helpers(("_assert_root_feature_bounds",))
    with pytest.raises(RuntimeError, match="invalid exact native root extreme"):
        namespace["_assert_root_feature_bounds"](_feature_adapter(feature), "RibRootFillets", 1)
    face.CreateSheetBody = lambda: None
    with pytest.raises(RuntimeError, match="cannot extract native root face"):
        namespace["_assert_root_feature_bounds"](_feature_adapter(feature), "RibRootFillets", 1)


def _receiver_faces(*, invalid=None, perturb: float = 0.0):
    queries = []
    nx, ny = profile.UPPER.normal_xy

    def closest(x, y, z):
        queries.append((x * 1000.0, y * 1000.0, z * 1000.0))
        if invalid is not None:
            return invalid
        distance = spec.RIB_WRAP_R - nx * x * 1000.0 - ny * y * 1000.0
        return x + (nx * distance + perturb) / 1000.0, y + ny * distance / 1000.0, z, 0.0, 0.0

    longitudinal = SimpleNamespace(
        GetSurface=lambda: SimpleNamespace(
            IsPlane=lambda: True, PlaneParams=(nx, ny, 0.0, 0.0, 0.0, 0.0),
        ),
        GetClosestPointOn=closest,
    )

    def no_cap_query(x, y, z):
        raise AssertionError("entry-cap distance is not a lateral receiver wall")

    cap = SimpleNamespace(
        GetSurface=lambda: SimpleNamespace(
            IsPlane=lambda: True, PlaneParams=(0.0, 0.0, 1.0, 0.0, 0.0, -spec.PLATE_L / 2000.0),
        ),
        GetClosestPointOn=no_cap_query,
    )
    return [cap, longitudinal], queries


def test_extracted_receiver_readback_uses_trimmed_longitudinal_faces_at_actual_mid_depth() -> None:
    import magnifying_bracket_joint_layout as joint

    faces, queries = _receiver_faces()
    namespace = _source_helpers(("_assert_receiver_profile_walls",))
    namespace["_assert_receiver_profile_walls"](_feature_adapter(_NativeFeature(faces=faces)))
    assert len(queries) == len(joint.LEVER_HOLE_POINTS)
    for actual, (x, y, _) in zip(queries, joint.LEVER_HOLE_POINTS):
        assert actual == pytest.approx((x, y, -spec.PLATE_L / 2.0 + joint.RIB_DEPTH / 2.0))
    # A matching ideal curve alone is insufficient: actual native readback
    # must agree, and the independent ordinary-band wall must also pass.
    bad_faces, _ = _receiver_faces(perturb=0.1)
    with pytest.raises(RuntimeError, match="native wall .* != signed profile"):
        namespace["_assert_receiver_profile_walls"](_feature_adapter(_NativeFeature(faces=bad_faces)))
    namespace["receiver_wall_budget"] = lambda: (
        SimpleNamespace(x_mm=29.7, minimum_mm=joint.RECEIVER_WALL_MIN - 0.01, minimum_witness=()),
    )
    with pytest.raises(RuntimeError, match="worst signed wall"):
        namespace["_assert_receiver_profile_walls"](_feature_adapter(_NativeFeature(faces=faces)))


@pytest.mark.parametrize("invalid", [(0.0, 0.0, 0.0), (math.nan, 0.0, 0.0, 0.0, 0.0)])
def test_extracted_receiver_distance_readback_refuses_invalid_points(invalid) -> None:
    faces, _ = _receiver_faces(invalid=invalid)
    namespace = _source_helpers(("_assert_receiver_profile_walls",))
    with pytest.raises(RuntimeError, match="invalid native trimmed-face closest point"):
        namespace["_assert_receiver_profile_walls"](_feature_adapter(_NativeFeature(faces=faces)))
    with pytest.raises(RuntimeError, match="no native longitudinal profile faces"):
        namespace["_assert_receiver_profile_walls"](_feature_adapter(_NativeFeature(faces=faces[:1])))


def _extracted_front_slab():
    """Run the real plate-prism prefix only; stop before any hole authoring."""
    helper = copy.deepcopy(next(
        node for node in _tree(RECIPE).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_coefficients_plate"
    ))
    gate_index = next(
        index for index, statement in enumerate(helper.body)
        if any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "volume_check" for node in ast.walk(statement))
    )
    helper.body = helper.body[:gate_index + 1]
    imports = [node for node in helper.body if isinstance(node, ast.ImportFrom)]
    assert all(node.module == "solidworks_mcp.adapters.base" for node in imports)
    helper.body = [node for node in helper.body if not isinstance(node, ast.ImportFrom)]
    recorder = _SketchRecorder()
    layouts = []
    gates = []

    class Dims:
        def record(self, name, equation):
            recorder.records.append((name, equation))

        def apply(self, adapter, name):
            return [(f"{dimension}@{name}", equation) for dimension, equation in recorder.records]

    async def chain(adapter, points):
        return [
            (await adapter.add_line(*a, *b)).data
            for a, b in zip(points, [*points[1:], points[0]])
        ]

    async def define(adapter, outline, points, *, label, dims, names, drives):
        layouts.append((outline, points, list(names), list(drives)))
        for name, expression in zip(names, drives):
            dims.record(name, expression)

    async def fully_defined(adapter, label):
        recorder.events.append(("fully_defined_requested",))

    async def volume(adapter, label, expected, tolerance):
        gates.append((expected, tolerance))

    def check(label, result):
        assert result.is_success, label
        return result.data

    namespace = {
        "math": math, "SketchDims": Dims, "check": check,
        "PLATE_W": spec.PLATE_W, "PLATE_L": spec.PLATE_L,
        "COEFFICIENT_T": spec.COEFFICIENT_T,
        "COEFFICIENT_TOP_Y": spec.COEFFICIENT_TOP_Y,
        "COEFFICIENT_BOTTOM_Y": spec.COEFFICIENT_BOTTOM_Y,
        "ExtrusionParameters": lambda **values: SimpleNamespace(**values),
        "add_line_chain": chain, "define_rectilinear_chain": define,
        "ensure_fully_defined": fully_defined, "volume_check": volume,
        "set_sketch_direct_db": lambda adapter, value: recorder.events.append(("direct_db", value)),
        "name_last_feature": lambda adapter, name: recorder.events.append(("name", name)),
        "name_dimensions": lambda adapter, feature, names: [f"{name}@{feature}" for name in names],
        "_assert_coefficient_slab": lambda adapter: recorder.events.append(("native_slab_proof_requested",)),
    }
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), helper,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(RECIPE), "exec"), namespace)
    return namespace["_coefficients_plate"], recorder, layouts, gates


def test_extracted_front_slab_places_thickness_on_the_actual_free_end_edge() -> None:
    helper, recorder, layouts, gates = _extracted_front_slab()
    jobs = []
    asyncio.run(helper(recorder, jobs))
    assert recorder.events[0] == ("create", "Front")
    assert len(layouts) == 1
    outline, points, names, drives = layouts[0]
    assert points == [
        (0.0, spec.COEFFICIENT_TOP_Y), (spec.PLATE_W, spec.COEFFICIENT_TOP_Y),
        (spec.PLATE_W, spec.COEFFICIENT_BOTTOM_Y), (0.0, spec.COEFFICIENT_BOTTOM_Y),
    ]
    assert names == ["PlateWidth", "PlateThickness", "PlateTopY"]
    assert drives == ['"PlateW"', '"CoefficientT"', '"CoefficientTopY"']
    # The thickness dimension's second chain segment is physically on +X's
    # free end. No imported extrusion depth or detached witness substitutes.
    kind, free_end = recorder.primitives[outline[1]]
    assert kind == "line"
    assert free_end == pytest.approx((
        spec.PLATE_W, spec.COEFFICIENT_TOP_Y, spec.PLATE_W, spec.COEFFICIENT_BOTTOM_Y,
    ))
    extrusions = [event[1] for event in recorder.events if event[0] == "extrude"]
    assert len(extrusions) == 1
    assert extrusions[0].depth == pytest.approx(spec.PLATE_L)
    assert extrusions[0].both_directions is True
    assert not getattr(extrusions[0], "start_offset", 0.0)
    assert set(jobs) == {
        ("PlateWidth@PlateProfile", '"PlateW"'),
        ("PlateThickness@PlateProfile", '"CoefficientT"'),
        ("PlateTopY@PlateProfile", '"CoefficientTopY"'),
        ("PlateLength@CoefficientsPlate", '"PlateL"'),
    }
    assert len(gates) == 1
    assert gates[0][0] == pytest.approx(spec.PLATE_W * spec.COEFFICIENT_T * spec.PLATE_L)
