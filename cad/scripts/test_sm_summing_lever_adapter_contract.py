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
import re
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
        self.distances = []
        self.records = []

    def _result(self, value):
        return SimpleNamespace(is_success=True, data=value, error=None)

    def _primitive(self, kind: str, values: tuple[float, ...]):
        identifier = f"{kind}{len(self.primitives)}"
        self.primitives[identifier] = (kind, values)
        return self._result(identifier)

    async def create_sketch(self, plane):
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

    async def exit_sketch(self):
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
            return [(f"{dimension}@{name}", equation) for dimension, equation in recorder.records]

    def check(label, result):
        assert result.is_success, label
        return result.data

    async def anchor(adapter, entity, x, y, label):
        return None

    async def distance(adapter, first, second, kind, value, label):
        recorder.distances.append((first, second, kind, value))

    async def fully_defined(adapter, label):
        return None

    globals_ = {
        "math": math, "SketchDims": Dims, "check": check,
        "set_sketch_direct_db": lambda adapter, value: None,
        "anchor_point_to_origin": anchor, "dimension_between": distance,
        "ensure_fully_defined": fully_defined,
        "name_last_feature": lambda adapter, name: None,
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
    jobs: list[tuple[str, str]],
) -> None:
    lines = {key: values for key, (kind, values) in recorder.primitives.items() if kind == "line"}
    arcs = {key: values for key, (kind, values) in recorder.primitives.items() if kind == "arc"}
    assert len(lines) == (5 if middle else 3)
    assert len(arcs) == (4 if middle else 3)
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
    _assert_recorded_sketch(recorder, section, middle, jobs)


@pytest.mark.parametrize("mutation", ["omit_tangency", "wrong_thickness"])
def test_extracted_sketch_contract_rejects_real_primitive_mutations(mutation: str) -> None:
    helper, recorder = _extracted_sketch(profile.PROFILE, mutation=mutation)
    jobs = []
    asyncio.run(helper(recorder, "MiddleRib", jobs, middle=True))
    with pytest.raises(AssertionError):
        _assert_recorded_sketch(recorder, profile.PROFILE, True, jobs)


def _source_helpers(names: tuple[str, ...], **bindings):
    """Extract exact helper bodies, substituting only their COM bind/import seam."""
    functions = []
    dependencies = ("coefficient_underside_root_geometry",)
    if "_assert_receiver_profile_walls" in names:
        dependencies += ("_assert_receiver_plate_backing",)
    for name in dict.fromkeys(dependencies + names):
        function = copy.deepcopy(next(
            node for node in _tree(RECIPE).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        ))
        imports = [node for node in function.body if isinstance(node, ast.ImportFrom)]
        assert all(node.module in {
            "magnifying_bracket_joint_layout", "solidworks_mcp.adapters.base",
        } for node in imports)
        function.body = [node for node in function.body if not isinstance(node, ast.ImportFrom)]
        functions.append(function)
    namespace = {
        "math": math, "_early_bound": lambda value, interface: value,
        "_telemetry": SimpleNamespace(
            success=lambda message: None, info=lambda message: None,
            traced=lambda name: lambda function: function,
            annotate=lambda **attributes: None,
        ),
        "COEFFICIENT_T": spec.COEFFICIENT_T,
        "COEFFICIENT_TOP_Y": spec.COEFFICIENT_TOP_Y,
        "COEFFICIENT_BOTTOM_Y": spec.COEFFICIENT_BOTTOM_Y,
        "COUNTER_WEB_T": spec.COUNTER_WEB_T,
        "RIB_BLEND_R": spec.RIB_BLEND_R, "RIB_BLEND_R_PLACES": spec.RIB_BLEND_R_PLACES,
        "RIB_REACH": spec.RIB_REACH, "PLATE_W_DEVIATIONS": spec.PLATE_W_DEVIATIONS,
        "CYL_R": spec.CYL_R, "PLATE_L": spec.PLATE_L, "PLATE_W": spec.PLATE_W,
        "RIB_T": spec.RIB_T, "SUM_H": spec.SUM_H,
        "RIB_OFFSET": spec.PLATE_L / 2.0 - spec.RIB_T,
        "ExtrusionParameters": SimpleNamespace,
    }
    # The coefficient slab, counter web and all ribs retain separate authorities.
    import magnifying_bracket_joint_layout as joint

    namespace.update(
        RECEIVER_PILOT_WALL_MIN=joint.RECEIVER_PILOT_WALL_MIN,
        LEVER_HOLE_POINTS=joint.LEVER_HOLE_POINTS, TAP_DRILL_DIA=joint.TAP_DRILL_DIA,
        receiver_wall_margin=profile.receiver_wall_margin,
        receiver_pilot_wall_budget=profile.receiver_pilot_wall_budget,
        receiver_pilot_material_wall_budget=joint.receiver_pilot_material_wall_budget,
        DRILL_DEPTH=joint.DRILL_DEPTH, DRILL_POINT_DEPTH=joint.DRILL_POINT_DEPTH,
    )
    namespace.update(bindings)
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *functions,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(RECIPE), "exec"), namespace)
    return namespace


@pytest.mark.parametrize("rib_t", [spec.RIB_T, 4.75])
def test_extracted_all_three_rib_operations_share_depth_and_drive_equation(rib_t: float) -> None:
    extrusions, profiles, gates = [], [], []

    async def sketch(adapter, stem, jobs, *, middle=False):
        profiles.append((stem, middle))

    async def measured(adapter, label):
        return 1000.0

    async def rebuild(adapter):
        return None

    async def gate(adapter, label, expected, tolerance):
        gates.append((label, expected, tolerance))

    async def middle_extrusion(parameters):
        extrusions.append(("middle", parameters.depth, parameters.both_directions))
        return SimpleNamespace(is_success=True)

    namespace = _source_helpers(
        ("_edge_rib", "_middle_rib"),
        RIB_T=rib_t, RIB_OFFSET=spec.PLATE_L / 2.0 - rib_t,
        _rib_profile_sketch=sketch, _measured_volume=measured,
        force_rebuild=rebuild, volume_check=gate,
        extrude_at_offset=lambda adapter, depth, offset, *, flip: extrusions.append(
            ("edge", depth, offset, flip)
        ),
        edge_rib_added_area_mm2=profile.edge_rib_added_area_mm2,
        check=lambda label, result: result,
        name_last_feature=lambda adapter, name: None,
        name_dimensions=lambda adapter, owner, names: [f"{name}@{owner}" for name in names],
        _assert_native_rib_profile=lambda adapter, stem: None,
    )
    adapter = SimpleNamespace(create_extrusion=middle_extrusion)
    jobs = []
    for flip, stem in ((False, "EdgeRibFront"), (True, "EdgeRibBack")):
        asyncio.run(namespace["_edge_rib"](adapter, flip, stem, stem, jobs))
    asyncio.run(namespace["_middle_rib"](adapter, jobs))
    offset = spec.PLATE_L / 2.0 - rib_t
    assert extrusions == [
        ("edge", rib_t, offset, False), ("edge", rib_t, offset, True),
        ("middle", rib_t, True),
    ]
    assert profiles == [("EdgeRibFront", False), ("EdgeRibBack", False), ("MiddleRib", True)]
    assert jobs == [
        ("EdgeRibThickness@EdgeRibFront", '"RibT"'),
        ("EdgeRibThickness@EdgeRibBack", '"RibT"'),
        ("MiddleRibThickness@MiddleRib", '"RibT"'),
    ]
    added = profile.edge_rib_added_area_mm2() * rib_t
    assert [expected for _, expected, _ in gates] == pytest.approx([1000.0 + added] * 2)


def test_extracted_taps_use_relocated_joint_axes_and_preserve_complete_pilot_volume_gate() -> None:
    import magnifying_bracket_joint_layout as joint

    cuts, gates = [], []

    async def mass():
        return SimpleNamespace(is_success=True, data=SimpleNamespace(volume=1000.0))

    async def gate(adapter, label, expected, tolerance):
        gates.append((expected, tolerance))

    namespace = _source_helpers(
        ("_bracket_mounting_taps",), TAP_SPEC=joint.TAP_SPEC,
        wizard_holes=lambda *args, **kwargs: cuts.append((args, kwargs)),
        volume_check=gate,
    )
    adapter = SimpleNamespace(get_mass_properties=mass)
    asyncio.run(namespace["_bracket_mounting_taps"](adapter))
    assert len(cuts) == 1
    arguments, options = cuts[0]
    assert arguments[:4] == (adapter, joint.TAP_SPEC, joint.LEVER_HOLE_POINTS, (0.0, 0.0, -1.0))
    assert all(y == pytest.approx(spec.COEFFICIENT_TOP_Y - 3.2512) for _, y, _ in arguments[2])
    assert options["expect_dia_mm"] == joint.TAP_DRILL_DIA
    assert joint.DRILL_DEPTH > spec.RIB_T
    complete_pilot = len(joint.LEVER_HOLE_POINTS) * math.pi * (joint.TAP_DRILL_DIA / 2.0)**2 * (
        joint.DRILL_DEPTH + joint.DRILL_POINT_DEPTH / 3.0
    )
    assert gates == [pytest.approx((1000.0 - complete_pilot, 0.02 * complete_pilot))]


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


def _native_boss_face_graph():
    levels = {
        "SummationAnchor": (-spec.ANCHOR_H / 2.0, spec.ANCHOR_H / 2.0),
        "SummationPlate": (-spec.COUNTER_WEB_T / 2.0, spec.COUNTER_WEB_T / 2.0),
        "CoefficientsPlate": (spec.COEFFICIENT_BOTTOM_Y, spec.COEFFICIENT_TOP_Y),
    }
    features = {
        name: _NativeFeature(faces=[_plane_face(level) for level in heights])
        for name, heights in levels.items()
    }
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(FeatureByName=features.get),
    )
    namespace = _source_helpers(("_assert_boss_face_graph",), ANCHOR_H=spec.ANCHOR_H)
    return namespace["_assert_boss_face_graph"], adapter, features


def test_extracted_boss_face_graph_uses_real_asymmetric_plate_and_flush_web_faces() -> None:
    check, adapter, _features = _native_boss_face_graph()
    assert spec.COUNTER_WEB_T / 2.0 == spec.COEFFICIENT_TOP_Y
    assert spec.ANCHOR_H / 2.0 - spec.COEFFICIENT_TOP_Y == pytest.approx(6.985)
    check(adapter)


@pytest.mark.parametrize("owner", ["SummationAnchor", "SummationPlate", "CoefficientsPlate"])
@pytest.mark.parametrize("side", [0, 1], ids=["lower", "upper"])
@pytest.mark.parametrize("damage", ["missing_owner", "missing_face", "shift", "wrong_normal"])
def test_extracted_boss_face_graph_rejects_wrong_native_faces(owner, side, damage) -> None:
    check, adapter, features = _native_boss_face_graph()
    feature = features[owner]
    if damage == "missing_owner":
        del features[owner]
    elif damage == "missing_face":
        feature.faces.pop(side)
    else:
        surface = feature.faces[side].GetSurface()
        normal_x, normal_y, normal_z, x, y, z = surface.PlaneParams
        if damage == "shift":
            surface.PlaneParams = (normal_x, normal_y, normal_z, x, y + 0.001, z)
        else:
            surface.PlaneParams = (1.0, 0.0, 0.0, x, y, z)
    with pytest.raises(RuntimeError):
        check(adapter)


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


def test_extracted_root_picks_stay_inside_reach_and_off_entry_and_knife_caps() -> None:
    namespace = _source_helpers(("rib_root_edge_families",))
    families = namespace["rib_root_edge_families"]()
    assert families
    for _, picks, length in families:
        assert picks
        assert length > 0.0
        assert all(-spec.PLATE_L / 2.0 < z < spec.PLATE_L / 2.0 for _, _, z in picks)
        assert all(x < spec.RIB_REACH for x, _, _ in picks)


def _assert_lower_junction_picks_cover_both_runs(families, namespace) -> None:
    """Sample the actual lower intersection, excluding the three solid ribs."""
    radius, bottom = namespace["CYL_R"], namespace["COEFFICIENT_BOTTOM_Y"]
    starts_ends = (
        (-namespace["RIB_OFFSET"], -namespace["RIB_T"] / 2.0),
        (namespace["RIB_T"] / 2.0, namespace["RIB_OFFSET"]),
    )
    picks = [point for _, points, _ in families for point in points]
    for start, end in starts_ends:
        hits = [
            (x, y, z) for x, y, z in picks
            if start < z < end
            and math.isclose(y, bottom, abs_tol=1e-10)
            and x > 0.0 and math.isclose(x*x + y*y, radius*radius, abs_tol=1e-10)
        ]
        assert len(hits) == 1, f"uncovered or ambiguous lower junction {start}..{end}"
        assert hits[0][2] == pytest.approx((start + end) / 2.0)


def test_lower_longitudinal_picks_cover_actual_junction_and_track_geometry_changes() -> None:
    namespace = _source_helpers(("rib_root_edge_families",))
    for changes in (
        {},
        {"COEFFICIENT_BOTTOM_Y": -5.0, "CYL_R": 13.0, "RIB_OFFSET": 70.0},
    ):
        namespace.update(changes)
        families = namespace["rib_root_edge_families"]()
        _assert_lower_junction_picks_cover_both_runs(families, namespace)
        # The original three cap-root families and their individual volume
        # budgets are not replaced by a looser all-roots allowance.
        assert [name for name, _, _ in families[:3]] == [
            "RibCylinderRootFillets", "RibCounterRootFillets", "RibRootFillets",
        ]
        assert [length for _, _, length in families[:3]] == pytest.approx([
            4.0 * math.tau * namespace["CYL_R"], 4.0 * namespace["SUM_H"], 8.0 * namespace["RIB_REACH"],
        ])
        for index in (0, 1):
            mutated = copy.deepcopy(families)
            mutated[-1][1].pop(index)
            with pytest.raises(AssertionError, match="uncovered"):
                _assert_lower_junction_picks_cover_both_runs(mutated, namespace)
        mutated = copy.deepcopy(families)
        mutated[-1][1][0][1] = namespace["COEFFICIENT_TOP_Y"]
        with pytest.raises(AssertionError, match="uncovered"):
            _assert_lower_junction_picks_cover_both_runs(mutated, namespace)


@pytest.mark.parametrize("changes", [
    {"COEFFICIENT_BOTTOM_Y": 0.0}, {"COEFFICIENT_BOTTOM_Y": -20.0},
    {"RIB_BLEND_R": 0.0}, {"RIB_BLEND_R": math.nan},
    {"RIB_OFFSET": 76.2}, {"RIB_OFFSET": 3.0},
])
def test_lower_blend_geometry_fails_closed_outside_tangent_inboard_premises(changes) -> None:
    namespace = _source_helpers((), **changes)
    with pytest.raises(ValueError, match="premises"):
        namespace["coefficient_underside_root_geometry"]()


def _root_face(
    box_mm: tuple[float, ...], *, radius: float = spec.RIB_BLEND_R, torus: bool = False,
    unknown: bool = False,
    cylinder_center=(0.0, 0.0), axis=(0.0, 0.0, 1.0),
):
    surface = SimpleNamespace(
        IsCylinder=lambda: not torus and not unknown, IsTorus=lambda: torus and not unknown,
        CylinderParams=(cylinder_center[0] / 1000.0, cylinder_center[1] / 1000.0, 0.0, *axis, radius / 1000.0),
        TorusParams=(0.0,) * 7 + (radius / 1000.0,),
    )

    def extreme(dx, dy, dz):
        direction = (dx, dy, dz)
        assert sum(abs(value) for value in direction) == 1.0
        values = [
            box_mm[index + 3] if component > 0.0 else box_mm[index]
            for index, component in enumerate(direction)
        ]
        return True, values[0] / 1000.0, values[1] / 1000.0, values[2] / 1000.0

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
    with pytest.raises(RuntimeError, match="native root radius"):
        namespace["_assert_root_feature_bounds"](_feature_adapter(feature), "RibRootFillets", 1)


def _underside_native_faces(namespace):
    radius = namespace["RIB_BLEND_R"]
    bottom = namespace["COEFFICIENT_BOTTOM_Y"]
    cylinder = namespace["CYL_R"]
    center = (math.sqrt((cylinder + radius)**2 - (bottom - radius)**2), bottom - radius)
    tangent = tuple(value * cylinder / (cylinder + radius) for value in center)
    runs = (
        (-namespace["RIB_OFFSET"], -namespace["RIB_T"] / 2.0),
        (namespace["RIB_T"] / 2.0, namespace["RIB_OFFSET"]),
    )
    boxes = [
        (tangent[0], tangent[1], start + radius, center[0], bottom, end - radius)
        for start, end in runs
    ]
    return [_root_face(box, cylinder_center=center) for box in boxes], boxes, center


def test_lower_blend_is_additive_and_its_complete_envelope_cannot_shrink_pilot_walls() -> None:
    import magnifying_bracket_joint_layout as joint

    namespace = _source_helpers(())
    edge_x, center, tangent, runs = namespace["coefficient_underside_root_geometry"]()
    cylinder, radius = spec.CYL_R, spec.RIB_BLEND_R
    assert edge_x**2 + spec.COEFFICIENT_BOTTOM_Y**2 == pytest.approx(cylinder**2)
    assert math.hypot(*center) == pytest.approx(cylinder + radius)
    assert math.dist(center, tangent) == pytest.approx(radius)
    assert math.hypot(*tangent) == pytest.approx(cylinder)
    assert center[1] + radius == pytest.approx(spec.COEFFICIENT_BOTTOM_Y)
    widths = []
    for index in range(101):
        y = tangent[1] + (spec.COEFFICIENT_BOTTOM_Y - tangent[1]) * index / 100.0
        sharp_x = math.sqrt(cylinder**2 - y*y)
        blended_x = center[0] - math.sqrt(max(0.0, radius**2 - (y - center[1])**2))
        widths.append(blended_x - sharp_x)
        assert blended_x >= sharp_x - 1e-10  # retained solid only grows
    assert max(widths) > 0.0
    # Even the larger bounded three-way cap-corner neighbourhood is outside
    # both pilot envelopes with printed axis/free-edge variation and wander.
    pilot_radius = (
        (max(joint.TAP_DRILL_DIA, round(joint.TAP_DRILL_DIA, 2)) + joint.RECEIVER_DRILLED_DIAMETER_PLUS) / 2.0
        + joint.DRILL_WANDER_MAX
    )
    x_max = center[0] + radius
    for hole_x, _, _ in joint.LEVER_HOLE_POINTS:
        assert x_max < hole_x - joint.LINEAR_BAND - joint.POSITION_BAND - pilot_radius
    assert x_max < spec.RIB_REACH < spec.HOLE_X < spec.PLATE_W
    assert spec.COEFFICIENT_BOTTOM_Y + radius < spec.COEFFICIENT_TOP_Y
    assert all(-spec.PLATE_L / 2.0 < start - radius < end + radius < spec.PLATE_L / 2.0 for start, end in runs)
    # Analytic negative control: a much larger round would enter
    # the pilot's protected X envelope; the native gate must refuse it.
    namespace = _source_helpers(("_assert_root_feature_bounds",), RIB_BLEND_R=3.0)
    with pytest.raises(RuntimeError, match="retained interface"):
        namespace["_assert_root_feature_bounds"](
            _feature_adapter(_NativeFeature()), "CoefficientUndersideRootFillets", 2,
        )


def test_native_lower_blend_requires_both_longitudinal_cylinders_but_allows_bounded_corner_patches() -> None:
    namespace = _source_helpers(("_assert_root_feature_bounds",))
    audit = namespace["_assert_root_feature_bounds"]
    faces, boxes, _ = _underside_native_faces(namespace)
    corner = _root_face(boxes[0], unknown=True)
    for ordered in (faces + [corner], [corner] + list(reversed(faces))):
        audit(_feature_adapter(_NativeFeature(faces=ordered)), "CoefficientUndersideRootFillets", 2)
    for incomplete in ([faces[0], faces[0]], [faces[1], faces[1]]):
        with pytest.raises(RuntimeError, match="missing native longitudinal blend run"):
            audit(_feature_adapter(_NativeFeature(faces=incomplete)), "CoefficientUndersideRootFillets", 2)
    with pytest.raises(RuntimeError, match="only 0 native"):
        audit(_feature_adapter(_NativeFeature(faces=[corner, corner])), "CoefficientUndersideRootFillets", 2)


@pytest.mark.parametrize("mutation", [
    "top_junction", "receiver", "outer_plate_edge", "entry_cap", "knife_cap",
    "wrong_axis", "wrong_center", "wrong_radius", "short_run", "y_nonfinite",
])
def test_native_lower_blend_rejects_wrong_junction_interface_and_incomplete_geometry(mutation) -> None:
    namespace = _source_helpers(("_assert_root_feature_bounds",))
    faces, boxes, center = _underside_native_faces(namespace)
    box = list(boxes[0])
    axis, radius = (0.0, 0.0, 1.0), spec.RIB_BLEND_R
    if mutation == "top_junction":
        box[1], box[4] = spec.COEFFICIENT_TOP_Y, spec.COEFFICIENT_TOP_Y + radius
    elif mutation == "receiver":
        box[3] = 16.0
    elif mutation == "outer_plate_edge":
        box[3] = spec.PLATE_W
    elif mutation == "entry_cap":
        box[2] = -spec.PLATE_L / 2.0
    elif mutation == "knife_cap":
        box[5] = spec.PLATE_L / 2.0
    elif mutation == "wrong_axis":
        axis = (0.0, 1.0, 0.0)
    elif mutation == "wrong_center":
        center = (center[0] + 0.1, center[1])
    elif mutation == "wrong_radius":
        radius = 0.5
    elif mutation == "short_run":
        box[2] += 5.0
    elif mutation == "y_nonfinite":
        box[1] = math.nan
    faces[0] = _root_face(tuple(box), cylinder_center=center, axis=axis, radius=radius)
    with pytest.raises(RuntimeError):
        namespace["_assert_root_feature_bounds"](
            _feature_adapter(_NativeFeature(faces=faces)), "CoefficientUndersideRootFillets", 2,
        )


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
        assert len(jobs) == len(families) and all(expression == '"RibBlendR"' for _, expression in jobs)


@pytest.mark.parametrize("increment", ["within", "zero", "negative", "excess"])
def test_longitudinal_family_has_its_own_increment_bound_without_relaxing_old_roots(increment) -> None:
    operations = []
    namespace = _source_helpers(("rib_root_edge_families",))
    families = namespace["rib_root_edge_families"]()
    new_name, _, length = families[-1]
    expected_length = (
        2.0 * namespace["RIB_OFFSET"]
        - namespace["RIB_T"] + 4.0 * namespace["RIB_BLEND_R"]
    )
    assert length == pytest.approx(expected_length)
    upper = 2.0 * spec.RIB_BLEND_R**2 * expected_length
    additions = {"within": upper * 0.5, "zero": 0.0, "negative": -1.0, "excess": upper + 0.01}

    async def fillet(radius, picks, *, propagate):
        operations.append((radius, picks, propagate))
        return SimpleNamespace(is_success=True)

    async def volume(adapter, label):
        addition = additions[increment] if label == f"after {new_name}" else 1.0
        return 1000.0 + (addition if label.startswith("after ") else 0.0)

    namespace = _source_helpers(
        ("rib_root_edge_families", "_rib_root_fillets"),
        _measured_volume=volume, check=lambda label, result: None,
        name_last_feature=lambda adapter, name: None,
        name_dimensions=lambda adapter, name, names: [f"{item}@{name}" for item in names],
        _assert_root_feature_bounds=lambda adapter, name, count: None,
    )
    adapter = SimpleNamespace(add_fillet=fillet)
    if increment == "within":
        asyncio.run(namespace["_rib_root_fillets"](adapter, []))
    else:
        with pytest.raises(RuntimeError, match="outside"):
            asyncio.run(namespace["_rib_root_fillets"](adapter, []))
    assert operations == [(spec.RIB_BLEND_R, picks, False) for _, picks, _ in families]


def test_every_modeled_root_including_lower_longitudinal_family_gets_native_max_band() -> None:
    dimensions = {}
    precision = []

    class Tolerance:
        Type = 0

        def SetValues(self, lower, upper):
            self.lower, self.upper = lower, upper
            return True

        def GetMinValue(self):
            return self.lower

        def GetMaxValue(self):
            return self.upper

    def dimension(adapter, owner, name):
        value = SimpleNamespace(SystemValue=spec.RIB_BLEND_R / 1000.0, Tolerance=Tolerance())
        dimensions[(owner, name)] = value
        return None, value

    namespace = _source_helpers(
        ("rib_root_edge_families", "_rib_radius_max_limits"),
        RIB_BLEND_R_BAND=spec.RIB_BLEND_R_BAND, RIB_BLEND_R_TOL_TYPE=spec.RIB_BLEND_R_TOL_TYPE,
        deviations=lambda band: (band[1], band[0]), _named_dimension=dimension,
        set_dimension_display_precision=lambda adapter, owner, name, places: precision.append((owner, name, places)),
    )
    namespace["_rib_radius_max_limits"](object())
    families = namespace["rib_root_edge_families"]()
    assert len(dimensions) == 6 + len(families)
    for owner, _, _ in families:
        name = "RibRootRadius" if owner == "RibRootFillets" else f"{owner}Radius"
        tolerance = dimensions[(owner, name)].Tolerance
        assert tolerance.Type == spec.RIB_BLEND_R_TOL_TYPE
        assert tolerance.GetMinValue() == -spec.RIB_BLEND_R / 1000.0
        assert tolerance.GetMaxValue() == 0.0
        assert (owner, name, spec.RIB_BLEND_R_PLACES) in precision


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

    def longitudinal_face(branch):
        nx, ny = branch.normal_xy

        def closest(x, y, z):
            queries.append((x * 1000.0, y * 1000.0, z * 1000.0))
            if invalid is not None:
                return invalid
            distance = spec.RIB_WRAP_R - nx * x * 1000.0 - ny * y * 1000.0
            return x + (nx * distance + perturb) / 1000.0, y + ny * distance / 1000.0, z, 0.0, 0.0

        return SimpleNamespace(
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
    return [cap, longitudinal_face(profile.UPPER), longitudinal_face(profile.LOWER)], queries


def _receiver_adapter(rib_faces, *, damage=None):
    """Finite, independently trimmed plate faces; no infinite-plane stand-in."""
    import magnifying_bracket_joint_layout as joint

    queries = []
    inner_z = joint.LEVER_FRONT_LOCAL_Z + spec.RIB_T
    tip_z = joint.LEVER_FRONT_LOCAL_Z + joint.DRILL_DEPTH + joint.DRILL_POINT_DEPTH

    def plate_face(axis, level, label):
        normal, origin = [0.0] * 3, [0.0] * 3
        normal[axis] = 1.0
        origin[axis] = (level + (0.1 if damage == f"shift_{label}" else 0.0)) / 1000.0
        values = (*normal, *origin)
        if damage == "invalid_plane":
            values = (math.nan, *values[1:])
        surface = SimpleNamespace(IsPlane=lambda: True, PlaneParams=values)

        def closest(x, y, z):
            point = [x * 1000.0, y * 1000.0, z * 1000.0]
            queries.append((label, tuple(point)))
            if damage == "invalid_point":
                return (math.nan, 0.0, 0.0, 0.0, 0.0)
            point[axis] = level
            z_max = tip_z - 0.1 if damage == "short_backing" else spec.PLATE_L / 2.0
            point[2] = max(inner_z, min(z_max, point[2]))
            if damage == "gap" and math.isclose(point[2], (inner_z + tip_z) / 2.0):
                point[2] += 0.1
            if axis == 1:
                x_max = joint.LEVER_HOLE_POINTS[0][0] if damage == "narrow_backing" else spec.PLATE_W
                point[0] = max(spec.CYL_R, min(x_max, point[0]))
            return tuple(value / 1000.0 for value in point) + (0.0, 0.0)

        return SimpleNamespace(
            GetSurface=lambda: None if damage == "missing_surface" else surface,
            GetClosestPointOn=closest,
        )

    backing = [
        plate_face(axis, level, label)
        for axis, level, label in (
            (1, spec.COEFFICIENT_TOP_Y, "top"),
            (1, spec.COEFFICIENT_BOTTOM_Y, "bottom"),
            (0, spec.PLATE_W, "free_edge"),
        )
        if damage != f"missing_{label}"
    ]
    features = {
        "EdgeRibBack": _NativeFeature(faces=rib_faces),
        "CoefficientsPlate": _NativeFeature(faces=backing),
    }
    if damage == "missing_owner":
        features.pop("CoefficientsPlate")
    return SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get)), queries


@pytest.mark.parametrize("clearance", [1.99, math.nan, math.inf, -math.inf])
def test_extracted_receiver_rejects_invalid_pilot_longitudinal_budget(clearance) -> None:
    faces, _ = _receiver_faces()
    adapter, _ = _receiver_adapter(faces)
    namespace = _source_helpers(
        ("_assert_receiver_profile_walls",),
        receiver_pilot_wall_budget=lambda: (
            SimpleNamespace(x_mm=29.7, minimum_mm=clearance, minimum_witness=()),
        ),
    )
    with pytest.raises(RuntimeError, match="printed-pilot longitudinal wall"):
        namespace["_assert_receiver_profile_walls"](adapter)


def test_extracted_receiver_reads_both_trimmed_flanks_at_uniform_rib_mid_depth() -> None:
    import magnifying_bracket_joint_layout as joint

    faces, queries = _receiver_faces()
    adapter, backing_queries = _receiver_adapter(faces)
    namespace = _source_helpers(("_assert_receiver_profile_walls",))
    namespace["_assert_receiver_profile_walls"](adapter)
    assert len(queries) == 2 * len(joint.LEVER_HOLE_POINTS)
    for index, (x, y, _) in enumerate(joint.LEVER_HOLE_POINTS):
        for actual in queries[2 * index:2 * index + 2]:
            assert actual == pytest.approx((x, y, -spec.PLATE_L / 2.0 + spec.RIB_T / 2.0))
    assert backing_queries
    bad_faces, _ = _receiver_faces(perturb=0.1)
    bad_adapter, _ = _receiver_adapter(bad_faces)
    with pytest.raises(RuntimeError, match="signed profile"):
        namespace["_assert_receiver_profile_walls"](bad_adapter)


def test_native_backing_witnesses_span_full_nominal_pilot_width_through_point_tip() -> None:
    import magnifying_bracket_joint_layout as joint

    faces, _ = _receiver_faces()
    adapter, queries = _receiver_adapter(faces)
    namespace = _source_helpers(("_assert_receiver_plate_backing",))
    namespace["_assert_receiver_plate_backing"](adapter)
    assert len(queries) == 18 * len(joint.LEVER_HOLE_POINTS)
    radius = joint.TAP_DRILL_DIA / 2.0
    for x, y, entry_z in joint.LEVER_HOLE_POINTS:
        inner_z = entry_z + spec.RIB_T
        tip_z = entry_z + joint.DRILL_DEPTH + joint.DRILL_POINT_DEPTH
        assert tip_z > inner_z
        for z in (inner_z, (inner_z + tip_z) / 2.0, tip_z):
            for side in (-1.0, 1.0):
                for label, level in (("top", spec.COEFFICIENT_TOP_Y), ("bottom", spec.COEFFICIENT_BOTTOM_Y)):
                    assert any(
                        actual_label == label and point == pytest.approx((x + side * radius, level, z))
                        for actual_label, point in queries
                    )
                assert any(
                    label == "free_edge" and point == pytest.approx((spec.PLATE_W, y + side * radius, z))
                    for label, point in queries
                )


@pytest.mark.parametrize("damage", [
    "missing_owner", "missing_top", "missing_bottom", "missing_free_edge",
    "shift_top", "shift_bottom", "shift_free_edge", "short_backing",
    "gap", "narrow_backing", "invalid_point", "invalid_plane", "missing_surface",
])
def test_native_backing_refuses_wrong_planes_or_trimmed_material_beyond_rib(damage) -> None:
    faces, _ = _receiver_faces()
    adapter, _ = _receiver_adapter(faces, damage=damage)
    namespace = _source_helpers(("_assert_receiver_profile_walls",))
    with pytest.raises(RuntimeError, match="backing"):
        namespace["_assert_receiver_profile_walls"](adapter)


@pytest.mark.parametrize("material_wall", [2.032, 2.103])
def test_receiver_checks_connected_material_budget_after_nominal_native_readbacks(material_wall: float) -> None:
    import magnifying_bracket_joint_layout as joint

    faces, queries = _receiver_faces()
    adapter, backing_queries = _receiver_adapter(faces)
    calls, radii = [], []

    def pilot_budget():
        calls.append((len(queries), len(backing_queries)))
        return material_wall

    def signed_margin(x, y, radius):
        radii.append(radius)
        return profile.receiver_wall_margin(x, y, radius)

    namespace = _source_helpers(
        ("_assert_receiver_profile_walls",),
        receiver_wall_margin=signed_margin,
        receiver_pilot_material_wall_budget=pilot_budget,
    )
    namespace["_assert_receiver_profile_walls"](adapter)
    assert radii == [joint.TAP_DRILL_DIA / 2.0] * len(joint.LEVER_HOLE_POINTS)
    assert calls == [(2 * len(joint.LEVER_HOLE_POINTS), 18 * len(joint.LEVER_HOLE_POINTS))]


@pytest.mark.parametrize("material_wall", [1.99, 0.0, math.nan, math.inf, -math.inf])
def test_receiver_rejects_failed_connected_material_budget_after_native_backing(material_wall: float) -> None:
    faces, _ = _receiver_faces()
    adapter, backing_queries = _receiver_adapter(faces)
    calls = []

    def pilot_budget():
        calls.append(len(backing_queries))
        return material_wall

    namespace = _source_helpers(
        ("_assert_receiver_profile_walls",),
        receiver_pilot_material_wall_budget=pilot_budget,
    )
    with pytest.raises(RuntimeError, match="connected-material wall"):
        namespace["_assert_receiver_profile_walls"](adapter)
    assert calls == [len(backing_queries)] and backing_queries


@pytest.mark.parametrize("invalid", [(0.0, 0.0, 0.0), (math.nan, 0.0, 0.0, 0.0, 0.0)])
def test_extracted_receiver_distance_readback_refuses_invalid_points(invalid) -> None:
    faces, _ = _receiver_faces(invalid=invalid)
    adapter, _ = _receiver_adapter(faces)
    namespace = _source_helpers(("_assert_receiver_profile_walls",))
    with pytest.raises(RuntimeError, match="invalid native trimmed-face closest point"):
        namespace["_assert_receiver_profile_walls"](adapter)
    cap_adapter, _ = _receiver_adapter(faces[:1])
    with pytest.raises(RuntimeError, match="no native longitudinal profile faces"):
        namespace["_assert_receiver_profile_walls"](cap_adapter)



@pytest.mark.parametrize("torus", [False, True], ids=["cylinder", "torus"])
@pytest.mark.parametrize("radius", [2.0, math.nan], ids=["r2", "nonfinite"])
def test_extracted_root_guard_rejects_wrong_radius_after_sufficient_valid_r1_faces(
    torus: bool, radius: float,
) -> None:
    namespace = _source_helpers(("_assert_root_feature_bounds",))
    inboard = (20.0, 2.54, -69.0, 30.0, 3.54, -67.0)
    good = _root_face(inboard)
    bad = _root_face(inboard, radius=radius, torus=torus)
    # One proved R1 already satisfies the count. Every other recognized face
    # must still satisfy its own radius constraint, in either traversal order.
    for faces in ([good, bad], [bad, good]):
        with pytest.raises(RuntimeError, match="native root radius"):
            namespace["_assert_root_feature_bounds"](
                _feature_adapter(_NativeFeature(faces=faces)), "RibRootFillets", 1
            )


@pytest.mark.parametrize("bad_box", [
    (20.0, 2.54, -69.0, spec.RIB_REACH + 0.1, 3.54, -67.0),
    (20.0, 2.54, -spec.PLATE_L / 2.0, 30.0, 3.54, -67.0),
    (20.0, 2.54, -69.0, 30.0, 3.54, spec.PLATE_L / 2.0),
    (20.0, 2.54, -69.0, math.nan, 3.54, -67.0),
], ids=["x-reach", "minus-z-entry", "plus-z-entry", "nonfinite"])
def test_extracted_root_guard_bounds_unknown_patches_after_sufficient_valid_r1_faces(
    bad_box: tuple[float, ...],
) -> None:
    namespace = _source_helpers(("_assert_root_feature_bounds",))
    good = _root_face((20.0, 2.54, -69.0, 30.0, 3.54, -67.0))
    unknown = _root_face(bad_box, unknown=True)
    # A nonanalytic transition patch cannot evade exact containment merely
    # because another cylinder has already established the required R1 count.
    for faces in ([good, unknown], [unknown, good]):
        with pytest.raises(RuntimeError):
            namespace["_assert_root_feature_bounds"](
                _feature_adapter(_NativeFeature(faces=faces)), "RibRootFillets", 1
            )


def test_extracted_root_guard_accepts_inboard_unknown_patches_without_counting_them_as_r1() -> None:
    namespace = _source_helpers(("_assert_root_feature_bounds",))
    inboard = (20.0, 2.54, -69.0, 30.0, 3.54, -67.0)
    good = _root_face(inboard)
    unknown = _root_face(inboard, unknown=True)
    adapter = _feature_adapter(_NativeFeature(faces=[good, unknown]))
    namespace["_assert_root_feature_bounds"](adapter, "RibRootFillets", 1)
    with pytest.raises(RuntimeError, match="only 1 native"):
        namespace["_assert_root_feature_bounds"](adapter, "RibRootFillets", 2)
    with pytest.raises(RuntimeError, match="only 0 native"):
        namespace["_assert_root_feature_bounds"](
            _feature_adapter(_NativeFeature(faces=[unknown])), "RibRootFillets", 1
        )


# --- Spring-row locators follow the spring-tap pattern's globals (#290). ---

_SPRING_EXPRS = ("SPRING_ROW_X_EXPR", "SPRING_SEED_STATION_EXPR", "SPRING_PITCH_EXPR")
_PATTERN_GLOBALS = {"HoleX", "ChannelZ0", "ChannelPitch", "HoleZOffset", "PlateL"}
_BUILT_GLOBALS_MM = {
    "PlateL": spec.PLATE_L, "HexDepth": spec.HEX_DEPTH, "HoleX": spec.HOLE_X,
    "ChannelZ0": spec.CHANNEL_Z0, "ChannelPitch": spec.CHANNEL_PITCH,
    "HoleZOffset": spec.HOLE_Z_OFFSET,
}


def _equation_value(expression: str, values: dict[str, float]) -> float:
    python = re.sub(r'"(\w+)"', lambda name: repr(values[name.group(1)]), expression)
    return float(eval(python, {"__builtins__": {}}))


def _recipe_namespace(functions: tuple[str, ...], **bindings) -> dict:
    """The recipe's module constants plus the named functions, imports stripped."""
    import sm_summing_lever_notes as notes

    namespace = {
        name: value for module in (spec, notes) for name, value in vars(module).items()
        if name.isupper()
    }
    namespace.update(math=math, re=re)
    body = []
    for node in _tree(RECIPE).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name)
            and (target.id.startswith("SPRING_ROW_") or target.id in _SPRING_EXPRS)
            for target in node.targets
        ):
            body.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in functions:
            function = copy.deepcopy(node)
            function.body = [item for item in function.body if not isinstance(item, ast.ImportFrom)]
            body.append(function)
    namespace.update(bindings)
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(RECIPE), "exec"), namespace)
    return namespace


def _run_spring_row_sketch() -> tuple[dict, dict[str, tuple[str | None, float]], list]:
    emitted: list[float] = []
    rows: list[tuple[str, str | None]] = []
    events: list = []

    class Dims:
        def record(self, name, drive=None):
            rows.append((name, drive))

        def apply(self, adapter, feature):
            assert len(rows) == len(emitted), "recorded names drifted from emitted dims"
            return [(f"{name}@{feature}", drive) for name, drive in rows if drive]

    async def distance(adapter, first, second, kind, value, label):
        emitted.append(value)

    async def anchor(adapter, point, x, y, label):
        emitted.extend(abs(value) for value in (x, y) if value)

    async def drive(adapter, name, expression):
        events.append(("drive", name, expression))

    async def rebuild(adapter):
        events.append(("rebuild",))

    async def nothing(*args):
        return None

    model = SimpleNamespace(
        ClearSelection2=lambda flag: None, BlankSketch=lambda: None,
        Extension=SimpleNamespace(SelectByID2=lambda *args: True),
    )
    recorder = _SketchRecorder()
    recorder.currentModel = model
    namespace = _recipe_namespace(
        ("_spring_row_coordinates",),
        SketchDims=Dims, check=lambda label, result: result.data,
        set_sketch_direct_db=lambda adapter, value: None,
        _as_construction=lambda adapter, entity: None,
        anchor_point_to_origin=anchor, dimension_between=distance,
        ensure_fully_defined=nothing, name_last_feature=lambda adapter, name: None,
        drive_dimension=drive, force_rebuild=rebuild,
        _assert_spring_row_equations=lambda adapter, drives: events.append(("readback", drives)),
        set_dimension_basic_tolerance=lambda *args: None,
        set_dimension_display_precision=lambda *args: None,
        set_dimension_prefix=lambda *args: None,
        mark_dimensions_for_drawing=lambda *args: None,
        null_callout=lambda: None,
    )
    asyncio.run(namespace["_spring_row_coordinates"](recorder))
    dims = {name: (drive, value) for (name, drive), value in zip(rows, emitted)}
    return namespace, dims, events


def test_spring_row_locators_are_driven_by_the_pattern_globals_and_evaluate_to_spec() -> None:
    namespace, dims, events = _run_spring_row_sketch()
    expected = {
        "SpringRowX": (namespace["SPRING_ROW_X_EXPR"], spec.HOLE_X),
        "SpringStartZ": (None, spec.HOLE_END_OFFSET_LAST),
        "SpringPitch": (namespace["SPRING_PITCH_EXPR"], spec.CHANNEL_PITCH),
    }
    assert set(namespace["SPRING_ROW_LOCATORS"]) == set(expected)
    for name, (pattern_expression, spec_value) in expected.items():
        expression, built = dims[name]
        assert expression is not None, f"{name} is a free sketch value"
        assert set(re.findall(r'"(\w+)"', expression)) <= _PATTERN_GLOBALS
        if pattern_expression is not None:
            assert expression == pattern_expression
        assert _equation_value(expression, _BUILT_GLOBALS_MM) == pytest.approx(spec_value, abs=1e-9)
        assert built == pytest.approx(spec_value, abs=1e-9)
    assert namespace["SPRING_SEED_STATION_EXPR"] in dims["SpringStartZ"][0]
    # Datum B, the +Z end of the symmetric "PlateL" plate, is a driven anchor too.
    assert _equation_value(dims["SpringRowEndZ"][0], _BUILT_GLOBALS_MM) == pytest.approx(spec.PLATE_L / 2.0)
    # Every drive is applied, then rebuilt, then natively read back.
    drives = [(f"{name}@SpringRowCoordinates", drive) for name, (drive, _) in dims.items() if drive]
    assert events == [("drive", *job) for job in drives] + [("rebuild",), ("readback", drives)]


def test_the_pattern_features_use_the_locators_own_expressions() -> None:
    plate = next(
        node for node in _tree(RECIPE).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_coefficients_plate"
    )
    used = {node.id for node in ast.walk(plate) if isinstance(node, ast.Name)}
    assert set(_SPRING_EXPRS) <= used


@pytest.mark.parametrize("pitch", [spec.CHANNEL_PITCH, 7.5])
def test_an_equations_edit_to_channel_pitch_moves_holes_and_locators_together(pitch: float) -> None:
    namespace, dims, _ = _run_spring_row_sketch()
    edited = {**_BUILT_GLOBALS_MM, "ChannelPitch": pitch}
    seed_z = _equation_value(namespace["SPRING_SEED_STATION_EXPR"], edited)
    second_z = seed_z - _equation_value(namespace["SPRING_PITCH_EXPR"], edited)
    assert _equation_value(dims["SpringStartZ"][0], edited) == pytest.approx(spec.PLATE_L / 2.0 - seed_z)
    assert _equation_value(dims["SpringPitch"][0], edited) == pytest.approx(seed_z - second_z)
    assert _equation_value(dims["SpringRowX"][0], edited) == pytest.approx(
        _equation_value(namespace["SPRING_ROW_X_EXPR"], edited)
    )


class _EquationManager:
    def __init__(self, rows: list[tuple[str, str, float]]) -> None:
        self.rows = rows
        self.Status = -1

    def GetCount(self) -> int:
        return len(self.rows)

    def Equation(self, index: int) -> str:
        return f'"{self.rows[index][0]}" = {self.rows[index][1]}'

    def Value(self, index: int) -> float:
        self.Status = index
        return self.rows[index][2]


@pytest.mark.parametrize("mode", ["live", "frozen", "missing", "stale", "detached-pitch"])
def test_spring_row_readback_requires_live_equations_and_matching_system_values(mode: str) -> None:
    _, dims, events = _run_spring_row_sketch()
    drives = events[-1][1]
    inch = {name: value / 25.4 for name, value in _BUILT_GLOBALS_MM.items()}
    rows = [(name, f"{value * 25.4}mm", value) for name, value in inch.items()]
    rows += [(name, expression, _equation_value(expression, inch)) for name, expression in drives]
    system = {name: value for name, (_, value) in dims.items()}
    pattern_spacing = spec.CHANNEL_PITCH
    if mode == "frozen":
        rows[-1] = (rows[-1][0], f"{spec.CHANNEL_PITCH}mm", rows[-1][2])
    elif mode == "missing":
        rows.pop()
    elif mode == "stale":
        system["SpringStartZ"] += 0.01
    elif mode == "detached-pitch":
        pattern_spacing += 0.01
    manager = _EquationManager(rows)
    model = SimpleNamespace(
        GetEquationMgr=lambda: manager,
        FeatureByName=lambda name: SimpleNamespace(
            Parameter=lambda leaf: SimpleNamespace(SystemValue=pattern_spacing / 1000.0)
        ),
    )
    namespace = _recipe_namespace(
        ("_evaluate_drive", "_assert_spring_row_equations"),
        _early_bound=lambda value, interface: value,
        _read_member=lambda value, name: getattr(value, name)(),
        _named_dimension=lambda adapter, owner, leaf: (
            None, SimpleNamespace(SystemValue=system[leaf] / 1000.0)
        ),
        _telemetry=SimpleNamespace(success=lambda message: None),
    )
    adapter = SimpleNamespace(currentModel=model)
    if mode == "live":
        namespace["_assert_spring_row_equations"](adapter, drives)
    else:
        with pytest.raises(RuntimeError):
            namespace["_assert_spring_row_equations"](adapter, drives)
