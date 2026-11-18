"""Offline contracts for the magnifying-clamp drawing."""

from __future__ import annotations

import itertools
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_mg_magnifying_clamp as part
import draw_mg_magnifying_clamp as drawing
import export_features
import mg_magnifying_clamp_geom as geom
import mg_magnifying_clamp_spec as spec
import mg_rod_clamp_joint as joint
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_face import FaceGeometry


def test_no_surface_finish_on_the_clamped_bore() -> None:
    # The lever is clamped in its bore: it neither runs nor slides (rule 6).
    assert not hasattr(spec, "SURFACE_FINISHES")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-clamp.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-clamp.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-clamp_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_clamp"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_LOCATION_KEEP) | set(drawing.TOP_LOCATION_KEEP) | set(drawing.BOTTOM_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert spec.STOCK_REFERENCE_DIMENSION == "HexAf"


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The hex and bore stations the assembly imports live in the drawing-FREE
    # geom module, so a print-note edit cannot enter the assembly recipe.
    import mg_magnifying_clamp_geom as geom

    assert geom.HEX_AF == pytest.approx(0.5 * 25.4)
    assert geom.BLOCK_DEPTH == pytest.approx(geom.HEX_AC)
    assert (geom.LEVER_BORE_Y, geom.BLOCK_HEIGHT) == (19.95, pytest.approx(1.16 * 25.4))
    for gone in ("BLOCK_WIDTH", "ROD_BORE_DIA", "ROD_BORE_X"):
        assert not hasattr(geom, gone)


def test_worst_case_walls_and_engagement_hold_the_contract() -> None:
    for name, (nominal, worst) in spec.DERIVED_WALL_BOUNDS.items():
        assert worst >= spec.WALL_TARGET, name
        assert nominal >= worst, name
    assert spec.DERIVED_WALL_BOUNDS["rod-tap drill point to the lever bore"][1] == pytest.approx(
        spec.ROD_TAP_FLOOR_WALL_WORST
    )
    # Bore and tap axes each have an independent ordinary .XX location
    # from the SAME actual flat; HEX size/angles, not custom notes, own form.
    import mg_magnifying_clamp_geom as geom

    band = 0.254  # .010
    entry_errors = [
        abs(tap_error - bore_error)
        for tap_error, bore_error in itertools.product((-band, band), repeat=2)
    ]
    assert geom.TAP_TO_BORE_ENTRY_Z_MAX == pytest.approx(max(entry_errors))
    assert geom.BORE_FULL_ANGULAR == pytest.approx(0.66 * 25.4 * math.tan(math.radians(0.3)))
    assert spec.BORE_TO_FLAT_WALL_WORST == pytest.approx(2.273871621267826)
    assert spec.ROD_TAP_FLOOR_WALL_WORST == pytest.approx(3.253726449848782)
    assert spec.THUMB_ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN
    assert joint.ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN
    assert spec.TAP_REACH_NEEDED <= spec.PLUG_TAP_USABLE_LENGTH
    assert spec.TAP_STOP_WINDOW > 0.0
    assert spec.THUMB_DRILL_NEAR_CLEAR > 0.0 and spec.THUMB_DRILL_FAR_CLEAR > 0.0
    assert spec.ROD_TAP_SPEC is joint.ROD_TAP_SPEC


def test_ordinary_hex_angular_corners_fit_the_derived_whole_body_envelope() -> None:
    import mg_magnifying_clamp_geom as geom

    # Construct actual face half-planes, not a copy of the envelope formula.
    # Opposite pairs take every ordinary size corner; each of six face normals
    # independently takes its +/-1-degree corner. Retain only real vertices.
    largest = 0.0
    height_band, af_band = 0.254, 0.127  # .XX height; assumed supplier ±.005 flats
    drift = (geom.BLOCK_HEIGHT + height_band) * math.tan(math.radians(1.0))
    for sizes in itertools.product((12.7 - af_band, 12.7 + af_band), repeat=3):
        for errors in itertools.product((-1.0, 1.0), repeat=6):
            faces = [
                (math.cos(math.radians(60.0 * index + errors[index])),
                 math.sin(math.radians(60.0 * index + errors[index])),
                 sizes[index % 3] / 2.0)
                for index in range(6)
            ]
            vertices = []
            for first, second in itertools.combinations(faces, 2):
                ax, az, a = first
                bx, bz, b = second
                det = ax * bz - az * bx
                if abs(det) < 1e-10:
                    continue
                x, z = (a * bz - az * b) / det, (ax * b - a * bx) / det
                if all(nx * x + nz * z <= limit + 1e-9 for nx, nz, limit in faces):
                    vertices.append((x, z))
            assert len(vertices) >= 3
            diameter = max(math.hypot(x1 - x2, z1 - z2)
                           for (x1, z1), (x2, z2) in itertools.combinations(vertices, 2))
            largest = max(largest, diameter + 2.0 * drift)
    assert largest <= geom.STOCK_ENVELOPE_MAX
    assert geom.STOCK_ENVELOPE_MAX == pytest.approx(0.66 * 25.4)
    assert largest > 15.0  # Nominal regular corners are not the body guarantee.


def test_hex_bore_wall_holds_the_target_at_the_ordinary_bands() -> None:
    import mg_magnifying_clamp_geom as geom

    opposite_flat, furthest_axis = 12.7 - 0.127, 6.35 + 0.254
    cut_radius = (geom.LEVER_BORE_DIA + 0.1016) / 2.0
    relative_runoff = geom.STOCK_ENVELOPE_MAX * math.tan(math.radians(1.0 + 0.3))
    wall = opposite_flat - furthest_axis - cut_radius - relative_runoff
    assert wall >= geom.WALL_TARGET
    assert wall == pytest.approx(geom.BORE_TO_FLAT_WALL_WORST)


def test_vertical_bore_wander_is_spent_in_both_dependent_stacks() -> None:
    import mg_magnifying_clamp_geom as geom
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(geom.HEIGHT_PLACES, unit="in")
    radius_max = (geom.LEVER_BORE_DIA + 0.1016) / 2.0
    slope = math.tan(math.radians(0.3))
    # Spend the entire calculated full-height extent; no perfect-hex
    # midpoint or symmetric station is credited.
    wander = geom.STOCK_ENVELOPE_MAX * slope
    # The exempt 19.95 bore height prints .79; its limits are that number's.
    bore_y_min = 0.79 * 25.4 - band
    floor = bore_y_min - radius_max - joint.ROD_TAP_DRILL_DEPTH_MAX - geom.ROD_TAP_DRILL_POINT - wander
    assert floor == pytest.approx(geom.ROD_TAP_FLOOR_WALL_WORST)
    assert geom.BORE_FULL_ANGULAR == pytest.approx(wander)
    assert floor >= geom.WALL_TARGET
    assert geom.LEVER_BORE_Y == 19.95  # approved hook/seat interface, not re-solved
    assert geom.THUMB_ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN


def test_installed_thumb_full_overlap_includes_actual_male_tip_and_seating() -> None:
    import mg_magnifying_clamp_geom as geom
    from sh_vn_thumb_screw_spec import COLLAR_DIA, SHANK_LEN, TIP_CHAMFER, TIP_FLAT_R
    from _printed_tolerance import printed_band_mm
    from mg_lever_thread_joint import ROD_DIA, ROD_DIA_BAND

    band = printed_band_mm(geom.HEIGHT_PLACES, unit="in")
    bore_y_low = 0.79 * 25.4 - band  # the exempt bore height prints .79
    overlaps, collar_gaps = [], []
    # Actual parallel-cylinder sections at all height/diameter/angle corners.
    # Include every extreme seating, even the conservative upper bore cap:
    # this must not rely on a centreline or perfectly bottom-seated rod.
    for height, bore_y, bore_dia, rod_dia, drift, angle, seat in itertools.product(
        (geom.BLOCK_HEIGHT - band, geom.BLOCK_HEIGHT + band),
        (bore_y_low, bore_y_low + 2.0 * band),
        (geom.LEVER_BORE_DIA, geom.LEVER_BORE_DIA + 0.1016),
        (ROD_DIA + ROD_DIA_BAND[1], ROD_DIA),
        (-geom.BORE_FULL_ANGULAR, geom.BORE_FULL_ANGULAR),
        (-geom.THUMB_CONTACT_ANGLE_MAX, 0.0, geom.THUMB_CONTACT_ANGLE_MAX),
        (-1.0, 0.0, 1.0),
    ):
        sec, slope = 1.0 / math.cos(angle), abs(math.tan(angle))
        cy, rb, rr = bore_y + drift, bore_dia / 2.0, rod_dia / 2.0
        # Include the worst transverse finite-flat miss, not a centreline
        # contact. Independent bore/tap entrance errors remain present.
        miss = max(geom.THUMB_CONTACT_Z_MAX + rb * sec - rr - TIP_FLAT_R, 0.0)
        chord_loss = rr - math.sqrt(rr**2 - miss**2)
        contact = cy + seat * (rb - rr) * sec + rr * sec + TIP_FLAT_R * slope
        female = (cy + rb * sec + (joint.THREAD_MAJOR / 2.0 + geom.TAP_OVERSIZE_R) * slope, height - geom.EDGE_BREAK)
        male = (contact + TIP_CHAMFER, contact - chord_loss - 2.0 * TIP_FLAT_R * slope + SHANK_LEN * math.cos(angle))
        overlaps.append(min(female[1], male[1]) - max(female[0], male[0]))
        collar_gaps.append(male[1] - height - COLLAR_DIA / 2.0 * abs(math.sin(angle)))
    assert min(overlaps) >= geom.THUMB_ENGAGEMENT_WORST - 1e-9
    assert min(overlaps) >= joint.ENGAGEMENT_MIN
    assert min(collar_gaps) >= geom.THUMB_COLLAR_CLEARANCE_MIN - 1e-9
    assert geom.THUMB_COLLAR_CLEARANCE_MIN > 0.0


def test_stock_hex_needs_no_custom_wall_or_envelope_inspection_note() -> None:
    # As-bought 1/2 hex: an exact fraction, judged at an assumed ±.005 supply.
    assert spec.HEX_AF == pytest.approx(25.4 / spec.HEX_AF_FRACTION_DENOMINATOR)
    assert spec.HEX_STOCK_AF_BAND == pytest.approx(0.005 * 25.4)
    # The REF is untoleranced: the supplier's band governs and only the walls
    # charge it.
    assert spec.HEX_AF_CALLOUT == "HEX STOCK"


@pytest.mark.parametrize(
    ("keep", "name", "center", "axes"),
    (
        ("TOP_LOCATION_KEEP", "ThumbTapFromDiagonalFlat", "TOP_CENTER", "TOP_AXES"),
        ("BOTTOM_KEEP", "RodTapFromDiagonalFlat", "BOTTOM_CENTER", "BOTTOM_AXES"),
    ),
)
def test_end_view_tap_location_runs_centre_to_flat_on_its_normal(keep, name, center, axes) -> None:
    # The measured flat's outward model normal (cos 30 X + sin 30 Z) on the
    # sheet, from the view's projected model axes.
    angles = getattr(drawing, axes)
    normal = tuple(
        math.cos(math.radians(30.0)) * f(angles["+X"]) + math.sin(math.radians(30.0)) * f(angles["+Z"])
        for f in (math.cos, math.sin)
    )
    cx, cy = getattr(drawing, center)
    tx, ty = getattr(drawing, keep)[name]
    off = (tx - cx, ty - cy)
    # On the normal through the tap centre (no offset along the flat, so no
    # extension line runs along the flat or through a corner) ...
    assert abs(off[0] * normal[1] - off[1] * normal[0]) < 1e-9
    # ... outward, the text >= 5 mm outside the flat.
    flat = spec.HEX_AF / 2.0 * drawing._S
    assert off[0] * normal[0] + off[1] * normal[1] - flat >= 0.005


def test_no_gdt_one_section_and_native_tap_callouts() -> None:
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    # The section hatches in the part's material crosshatch (IFaceHatch's
    # pattern is get-only): the part sets it, the sheet only reads it back.
    assert spec.SECTION_HATCH_PATTERN == "ANSI31 (Iron BrickStone)"
    # The tap drill Ø prints .XXX, its depths .XX.
    assert spec.TAP_CALLOUT_PRECISION["hw-tapdrldia"] == 3
    assert {places for name, places in spec.TAP_CALLOUT_PRECISION.items() if name != "hw-tapdrldia"} == {joint.HOLE_DEPTH_PLACES}


def test_end_views_are_third_angle_projections_of_the_front() -> None:
    half_pi = math.pi / 2.0
    assert drawing.FRONT_AXES == {"+Z": math.pi, "+Y": half_pi}
    assert drawing.TOP_AXES == {"+X": -half_pi, "+Z": math.pi}
    assert drawing.BOTTOM_AXES == {"+X": half_pi, "+Z": math.pi}
    # In line with the front: same column, above and below it.
    assert drawing.TOP_CENTER[0] == drawing.RIGHT_CENTER[0] == drawing.BOTTOM_CENTER[0]
    front_half = spec.BLOCK_HEIGHT / 2.0 * drawing._S
    end_half = spec.HEX_AC / 2.0 * drawing._S
    assert drawing.TOP_CENTER[1] - end_half > drawing.RIGHT_CENTER[1] + front_half
    assert drawing.BOTTOM_CENTER[1] + end_half < drawing.RIGHT_CENTER[1] - front_half


def test_thumb_tap_reference_thread_depth_brackets_only_the_thread() -> None:
    definitions = {5: "TAP INTO BORE", 7: "<hw-threaddepth> <hw-tapdrldepth>"}
    wanted = drawing.reference_thread_depth_definitions(definitions)
    assert wanted[7] == "(<hw-threaddepth>) <hw-tapdrldepth>"
    with pytest.raises(RuntimeError):
        drawing.reference_thread_depth_definitions(wanted)


def test_part_stamps_make_critical_properties() -> None:
    import _config

    config = _config.parts("mg-magnifying-clamp")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1


class _NativeSketch:
    """A sketch has native identity, but deliberately no IFeature.Name member."""

    def __init__(self, token, feature_name):
        self.token = token
        self.feature_name = feature_name


class _NativeFeature:
    def __init__(self, sketch, *, kind="ProfileFeature"):
        self.sketch = sketch
        self.Name = sketch.feature_name
        self.kind = kind

    def GetTypeName2(self):
        return self.kind

    def GetSpecificFeature2(self):
        return self.sketch


def _native_same(left, right):
    if isinstance(left, _NativeSketch) and isinstance(right, _NativeSketch):
        return int(left.token == right.token)
    return int(left is right)


class _WitnessComError(Exception):
    def __init__(self, hresult):
        super().__init__(f"native HRESULT {hresult}")
        self.hresult = hresult


class _WitnessDispatch:
    point_iid = "fixture-point-IID"
    segment_iid = "fixture-segment-IID"

    def __init__(self, interface):
        self.calls = []
        self.capabilities = {
            self.point_iid: interface == "ISketchPoint",
            self.segment_iid: interface == "ISketchSegment",
        }

    def QueryInterface(self, iid, use_iid):
        self.calls.append((iid, use_iid))
        assert use_iid == "fixture-IUnknown"
        outcome = self.capabilities[iid]
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is False:
            raise _WitnessComError(-2147467262)
        if outcome is None:
            return None
        assert outcome is True
        # Capability-only pointer: it deliberately exposes no sketch methods.
        return object()


def _install_witness_interfaces(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        IID_IUnknown="fixture-IUnknown", com_error=_WitnessComError,
    ))
    monkeypatch.setitem(sys.modules, "solidworks_mcp.adapters._generated.sldworks_2026", SimpleNamespace(
        ISketchPoint=SimpleNamespace(CLSID=_WitnessDispatch.point_iid),
        ISketchSegment=SimpleNamespace(CLSID=_WitnessDispatch.segment_iid),
    ))


def _native_sketch_segment(*, owner="ActualLocationProfile", kind=0, identifiers=(1, 2)):
    sketch = _NativeSketch(owner, owner)
    return SimpleNamespace(
        _oleobj_=_WitnessDispatch("ISketchSegment"),
        owner_sketch=sketch,
        GetSketch=lambda: sketch,
        GetType=lambda: kind,
        GetID=lambda: identifiers,
    )


def _native_inventory(*segments):
    owners = {}
    for segment in segments:
        sketch = segment.owner_sketch
        owners.setdefault(sketch.token, _NativeFeature(_NativeSketch(sketch.token, sketch.feature_name)))

    def features(top_level_only):
        assert top_level_only is False, "absorbed sketch owners must be inventoried"
        return tuple(reversed(tuple(owners.values())))

    return SimpleNamespace(GetFeatures=features)


def test_actual_thumb_drill_cone_clears_both_walls_over_its_finite_length() -> None:
    import mg_magnifying_clamp_geom as geom

    slope, band = math.tan(math.radians(0.3)), 0.254
    bore_r = geom.LEVER_BORE_DIA / 2.0
    drill_r = (geom.ROD_TAP_DRILL_DIA + 0.1016) / 2.0
    point = drill_r / math.tan(math.radians(59.0))
    # Height 1.16, bore height .79 and drill depth .37, each at its printed
    # .XX limit (the exempt bore height and the drill depth print rounded).
    top_min = 1.16 * 25.4 - band - (0.79 * 25.4 + band)
    top_max = 1.16 * 25.4 + band - (0.79 * 25.4 - band)
    depth_min, depth_max = 0.37 * 25.4 - band, 0.37 * 25.4 + band
    bore_wander = geom.STOCK_ENVELOPE_MAX * slope
    # Two independent common-flat .XX locations, then actual angular travel.
    relative_offset = 2.0 * band + (depth_max + point) * slope + bore_wander

    def far_clearance(distance):
        actual_radius = drill_r * (1.0 - distance / point)
        chord = math.sqrt(bore_r**2 - (relative_offset + actual_radius) ** 2)
        return top_min + chord - depth_max - bore_wander - distance

    chord = math.sqrt(bore_r**2 - (relative_offset + drill_r) ** 2)
    near = depth_min - (top_max - chord) - bore_wander
    endpoints = (far_clearance(0.0), far_clearance(point))
    # The chord is concave, and the cone radius is affine: its whole
    # continuous minimum lies at an endpoint. Interior probes catch an
    # implementation accidentally retaining full radius at the point.
    assert all(far_clearance(point * step / 200.0) >= min(endpoints) - 1e-9 for step in range(201))
    assert spec.THUMB_DRILL_NEAR_CLEAR == pytest.approx(near)
    assert spec.THUMB_DRILL_FAR_CYLINDER_CLEAR == pytest.approx(endpoints[0])
    assert spec.THUMB_DRILL_FAR_POINT_CLEAR == pytest.approx(endpoints[1])
    assert spec.THUMB_DRILL_FAR_CLEAR == pytest.approx(min(endpoints))
    assert near > 0.0 and min(endpoints) > 0.0
    # Mutation control: falsely extending the full drill cylinder through
    # the point loses >0.4 mm and must NOT define the real point clearance.
    cylinder_to_tip = endpoints[0] - point
    assert spec.THUMB_DRILL_FAR_CLEAR > cylinder_to_tip + 0.4


class _WitnessTransform:
    def __init__(self, forward, inverse):
        self.forward, self.inverse = forward, inverse

    def Inverse(self):
        return _WitnessTransform(self.inverse, self.forward)


class _WitnessPoint:
    _next_id = 1

    def __init__(self, owner, x, y, z=0.0):
        self.owner, self.X, self.Y, self.Z = owner, x, y, z
        self.relations = []
        self._oleobj_ = _WitnessDispatch("ISketchPoint")
        self.identifiers = _WitnessPoint._next_id, 0
        _WitnessPoint._next_id += 1

    @property
    def owner_sketch(self):
        return self.owner

    def GetID(self):
        return self.identifiers

    def GetSketch(self):
        return self.owner

    def GetRelations(self):
        return tuple(self.relations)


def _point_proxy(point):
    proxy = _WitnessPoint(point.GetSketch(), point.X, point.Y, point.Z)
    proxy.identifiers = point.GetID()
    proxy.relations = point.relations
    return proxy


class _WitnessRelation:
    def __init__(self, entities, kind):
        self.entities, self.kind = tuple(entities), kind
        self.Suppressed = False

    def GetRelationType(self):
        return self.kind

    def GetDefinitionEntities2(self):
        # Native definition order is not part of the relation contract.
        return self.entities[::-1]

    def GetEntities(self):
        return self.entities[::-1]

    def GetEntitiesType(self):
        # These describe the internal entities, not the definition array.
        return tuple(2 if isinstance(entity, _WitnessPoint) else 3 if hasattr(entity, "GetType") and entity.GetType() == 0 else 4 for entity in self.GetEntities())


class _TapProjectionFixture:
    """Native-shaped state, distinct sketch frames, and read-only measured value."""

    def __init__(self, monkeypatch, *, mode="retained"):
        from solidworks_mcp.adapters import com_variant
        import _telemetry
        _install_witness_interfaces(monkeypatch)

        self.mode = mode
        self.events, self.selections, self.lines, self.relations, self.displays = [], [], [], [], []
        self.status = 3
        self.sketch = _NativeSketch("right", "LeverBoreLocationProfile")
        self.sketch.ModelToSketchTransform = _WitnessTransform(
            lambda p: (-p[2], p[1], p[0]), lambda p: (p[2], p[1], -p[0]),
        )
        self.sketch.GetConstrainedStatus = lambda: self.status
        self.sketch.GetSketchSegments = lambda: (self.circle, self.flat, *self.lines)
        source = _NativeSketch("top", "ThumbPlacement")
        source.ModelToSketchTransform = _WitnessTransform(
            lambda p: (p[0], -p[2], p[1] - 0.0295),
            lambda p: (p[0], p[2] + 0.0295, -p[1]),
        )
        self.tap = _WitnessPoint(source, 0.0, 0.0)
        self.center = _WitnessPoint(self.sketch, 0.0, 0.01995)
        self.circle = _native_sketch_segment(owner=self.sketch.feature_name, kind=1)
        self.circle.owner_sketch = self.sketch
        self.circle.GetSketch = lambda: self.sketch
        self.circle.GetCenterPoint2 = lambda: self.center
        self.circle.GetRadius = lambda: 0.00325
        self.source_circle = SimpleNamespace(_oleobj_=_WitnessDispatch("IEdge"))
        self.circle.relations = [_WitnessRelation((self.source_circle,), 32)]
        self.circle.GetRelations = lambda: tuple(self.circle.relations)
        self.flat = _native_sketch_segment(owner=self.sketch.feature_name, kind=0, identifiers=(99, 1))
        self.flat.owner_sketch = self.sketch
        self.flat.GetSketch = lambda: self.sketch
        flat_start, flat_end = _WitnessPoint(self.sketch, -0.00635, 0.0), _WitnessPoint(self.sketch, -0.00635, 0.0295)
        self.flat.GetStartPoint2, self.flat.GetEndPoint2 = lambda: flat_start, lambda: flat_end
        self.flat.ConstructionGeometry = True
        self.source_flat = SimpleNamespace(_oleobj_=_WitnessDispatch("IEdge"))
        self.flat.relations = [_WitnessRelation((self.source_flat,), 32)]
        self.flat.GetRelations = lambda: tuple(self.flat.relations)
        self.manager = SimpleNamespace(AddToDB=False, CreateLine=self.create_line)
        self.sketch.RelationManager = SimpleNamespace(AddRelation=self.add_relation)
        selection = SimpleNamespace(
            GetSelectedObjectCount2=lambda _mark: len(self.selections),
            GetSelectedObjectType3=lambda index, _mark: 11 if isinstance(self.selections[index - 1], _WitnessPoint) else 10,
            GetSelectedObject6=lambda index, _mark: self.selections[index - 1],
        )
        self.model = SimpleNamespace(
            GetActiveSketch2=lambda: None if mode == "no-active-sketch" else self.sketch,
            ClearSelection2=lambda _all: self.selections.clear(),
            SelectionManager=selection,
            FeatureManager=SimpleNamespace(GetFeatures=lambda top: _native_inventory(self.circle, self.tap).GetFeatures(top)),
            AddDimension2=self.dimension,
            GraphicsRedraw2=lambda: None,
            FeatureByName=lambda _name: _NativeFeature(self.sketch),
        )

        def math_point(coordinates):
            return SimpleNamespace(
                ArrayData=tuple(coordinates),
                MultiplyTransform=lambda transform: math_point(transform.forward(tuple(coordinates))),
            )

        self.preferences = {}
        self.adapter = SimpleNamespace(
            currentModel=self.model, currentSketchManager=self.manager,
            swApp=SimpleNamespace(
                IsSame=_native_same, GetMathUtility=lambda: SimpleNamespace(CreatePoint=math_point),
                SetUserPreferenceToggle=lambda key, value: self.preferences.__setitem__(key, value),
                GetUserPreferenceToggle=lambda key: self.preferences[key],
            ),
        )
        monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
        monkeypatch.setattr(part, "_native_select", lambda _adapter, entity, _interface, *, append: self.selections.append(entity))
        monkeypatch.setattr(com_variant, "double_array", lambda values: values)
        monkeypatch.setattr(com_variant, "dispatch_array", lambda values: values)
        monkeypatch.setattr(_telemetry, "info", lambda message, **fields: self.events.append((message, fields)))

    def create_line(self, x1, y1, z1, x2, y2, z2):
        assert self.manager.AddToDB is True, "database insertion must suppress inference"
        if self.mode == "missing-line":
            return None
        # AddToDB does not prevent exact-coordinate database point reuse.
        existing = [self.center]
        for old in self.lines:
            existing.extend((old.GetStartPoint2(), old.GetEndPoint2()))

        def point_at(x, y, z):
            for point in existing:
                if (point.X, point.Y, point.Z) == (x, y, z):
                    return point
            point = _WitnessPoint(self.sketch, x, y, z)
            existing.append(point)
            return point

        start, end = point_at(x1, y1, z1), point_at(x2, y2, z2)
        line = _native_sketch_segment(owner=self.sketch.feature_name, identifiers=(len(self.lines) + 2, 1))
        line.owner_sketch = self.sketch
        line.GetSketch = lambda: self.sketch
        line.GetStartPoint2, line.GetEndPoint2 = lambda: start, lambda: end
        line.relations = []
        line.GetRelations = lambda: tuple(line.relations)
        line.ConstructionGeometry = False
        self.lines.append(line)
        return line

    def add_relation(self, entities, kind):
        assert self.manager.AddToDB is False, "restore inference isolation before constraints solve"
        if self.mode == "missing-relation":
            return None
        relation = _WitnessRelation(entities, kind)
        if self.mode == "wrong-definition" and kind == 26:
            relation.entities = (entities[0], _WitnessPoint(self.tap.owner, self.tap.X, self.tap.Y))
        if self.mode == "wrong-relation-kind":
            relation.kind = 17
        if self.mode == "segment-dispatch-proxy" and kind in (4, 9):
            segment = entities[-1]
            proxy = _native_sketch_segment(
                owner=segment.owner_sketch.feature_name,
                kind=segment.GetType(), identifiers=segment.GetID(),
            )
            proxy.owner_sketch = segment.owner_sketch
            proxy.GetSketch = lambda: segment.owner_sketch
            assert _native_same(proxy, segment) == 0
            relation.entities = (*entities[:-1], proxy)
        for entity in entities:
            entity.relations.append(relation)
        self.relations.append(relation)
        # A small stateful model of these four equations, not a native-success
        # claim. Constraints move independent point objects without merging them.
        if self.mode != "unsolved":
            if kind == 4:
                entities[0].GetEndPoint2().Y = entities[0].GetStartPoint2().Y
            elif kind == 26:
                source = entities[1]
                model = source.owner.ModelToSketchTransform.Inverse().forward((source.X, source.Y, source.Z))
                entities[0].X = self.sketch.ModelToSketchTransform.forward(model)[0]
            elif kind == 25:
                end, center = entities
                end.Y = center.Y
                line = next(line for line in self.lines if line.GetEndPoint2() is end)
                line.GetStartPoint2().Y = end.Y
            elif kind == 9:
                end, circle = entities
                center = circle.GetCenterPoint2()
                half_chord = math.sqrt(circle.GetRadius() ** 2 - (end.Y - center.Y) ** 2)
                end.X = center.X + math.copysign(half_chord, end.X - center.X)
        if self.mode == "underdefined":
            self.status = 2
        return relation

    def dimension(self, *position):
        assert len(self.selections) == 2
        measured_point, selected_flat = self.selections
        assert isinstance(measured_point, _WitnessPoint) and selected_flat is self.flat
        assert position == pytest.approx((0.02, 0.02, 0.0))
        if measured_point is not self.center:
            assert measured_point is self.lines[-1].GetStartPoint2()
            assert [relation.kind for relation in self.relations[-4:]] == [4, 26, 25, 9]
        if self.mode == "missing-dimension":
            return None
        state = self

        class MeasuredDimension:
            DrivenState, Name = 2, ""
            Tolerance = SimpleNamespace(Type=0)

            @property
            def FullName(self):
                return f"{self.Name}@LeverBoreLocationProfile@Clamp.Part"

            @property
            def SystemValue(self):
                return abs(measured_point.X - state.flat.GetStartPoint2().X) + (0.0002 if state.mode == "wrong-value" else 0.0)

        attached = list(self.selections)
        if self.mode == "coordinate-copy":
            attached[0] = _WitnessPoint(self.sketch, attached[0].X, attached[0].Y)
        annotation = SimpleNamespace(
            GetAttachedEntities3=lambda: tuple(attached[::-1]),
            GetAttachedEntityTypes=lambda: (10, 11),
            IsDangling=lambda: None if self.mode == "unknown-dangling" else self.mode == "dangling",
        )
        measured = MeasuredDimension()
        display = SimpleNamespace(GetDimension2=lambda _index: measured, GetAnnotation=lambda: annotation, ShowParenthesis=True, GetPrimaryPrecision2=lambda: 2)
        annotation.GetSpecificAnnotation = lambda: display
        annotation.Visible = 1
        self.displays.append(display)
        return display

    def install_rebuild(self, monkeypatch, points):
        part._measure_location(self.adapter, self.center, self.flat, "LeverBoreFromZFlat")
        dimensions = {display.GetDimension2(0).Name: display for display in self.displays}
        monkeypatch.setattr(part, "_location_sources", lambda _adapter: {"LeverBoreLocationProfile": ("Right", self.source_circle, "ISketchSegment", (("LeverBoreFromZFlat", self.source_flat),))})
        monkeypatch.setattr(part, "_tap_placement_points", lambda _adapter: dict(points))
        monkeypatch.setattr(part, "_named_dimension", lambda _adapter, _feature, name: (dimensions[name], dimensions[name].GetDimension2(0)))
        return dimensions


def _flat_group_fixture(monkeypatch):
    import sys

    fixture = _TapProjectionFixture(monkeypatch)
    points = dict(zip(spec.Z_FLAT_DIMENSIONS[1:], (fixture.tap, _WitnessPoint(fixture.tap.owner, 0.0, 0.0)), strict=True))
    for name, point in points.items():
        part._measure_tap_from_flat(fixture.adapter, point, fixture.circle, fixture.flat, name)
    # R26 bd160ae task.log 158–161, 295–337, 355–410: the observed bore
    # source/view IDs are (0,2), flat line (1,2). Other members remain stateful
    # synthetic regressions, NOT claims of native forward success for those taps.
    fixture.center.identifiers = (0, 2)
    fixture.flat.GetID = lambda: (1, 2)
    for index, line in enumerate(fixture.lines):
        line.GetStartPoint2().identifiers = (5 + 3 * index, 6 + 3 * index)
        line.GetEndPoint2().identifiers = (6 + 3 * index, 7 + 3 * index)
    dimensions = fixture.install_rebuild(monkeypatch, points)
    fixture.source_displays = dimensions
    wrapper = sys.modules["solidworks_mcp.adapters._generated.sldworks_2026"]
    sys.modules["pythoncom"].IID_IDispatch = "fixture-IDispatch"
    for interface in ("IAnnotation", "IDimension", "IFeature", "IModelDoc2", "ISketch", "IView"):
        setattr(wrapper, interface, SimpleNamespace(CLSID=f"fixture-{interface}-IID"))

    def tag(value, interface):
        if not hasattr(value, "_oleobj_"):
            value._oleobj_ = _WitnessDispatch(interface)
        value._oleobj_.capabilities[getattr(wrapper, interface).CLSID] = True
        value._oleobj_.capabilities["fixture-IDispatch"] = True
        return value

    fixture.tag = tag
    fixture.drawing_sketch = tag(_NativeSketch("drawing-right", fixture.sketch.feature_name), "ISketch")
    fixture.forward_sketch = tag(_NativeSketch("drawing-right", fixture.sketch.feature_name), "ISketch")
    tag(fixture.sketch, "ISketch")
    tag(fixture.model, "IModelDoc2")
    fixture.model.GetType = lambda: 1
    # R26 411=0, 412=1: GetFeatureOwner's sketch is deliberately NOT part
    # authority, even though the feature name and native dimension agree.
    fixture.dimension_feature = tag(_NativeFeature(fixture.drawing_sketch), "IFeature")
    fixture.forward_feature = tag(_NativeFeature(fixture.forward_sketch), "IFeature")
    fixture.forward_entities, fixture.source_by_import = {}, {}
    fixture.mapping_calls, fixture.inverse_calls = [], []

    def source_key(entity):
        kind = "ISketchPoint" if isinstance(entity, _WitnessPoint) else entity.GetType()
        return entity.GetSketch().token, kind, *entity.GetID()

    fixture.source_key = source_key

    def drawing_entity(source, owner):
        if isinstance(source, _WitnessPoint):
            proxy = _point_proxy(source)
            proxy.owner = owner
            proxy.X += 0.125
            return tag(proxy, "ISketchPoint")
        proxy = _native_sketch_segment(owner=owner.feature_name, kind=source.GetType(), identifiers=source.GetID())
        proxy.owner_sketch = owner
        proxy.GetSketch = lambda: owner
        return tag(proxy, "ISketchSegment")

    def import_entity(source):
        tag(source, "ISketchPoint" if isinstance(source, _WitnessPoint) else "ISketchSegment")
        proxy = drawing_entity(source, fixture.drawing_sketch)
        fixture.source_by_import[id(proxy)] = source
        key = source_key(source)
        if key not in fixture.forward_entities:
            fixture.forward_entities[key] = drawing_entity(source, fixture.forward_sketch)
        return proxy

    def corresponding_view(entity):
        fixture.mapping_calls.append(entity)
        if entity is fixture.dimension_feature:
            return fixture.forward_feature
        # Only actual source entities are accepted; owner-only mapping is not
        # an alternative. Source IDs identify the fake API input, not the view.
        assert entity.GetSketch() is fixture.sketch
        return fixture.forward_entities.get(source_key(entity))

    def inverse_forbidden(entity):
        fixture.inverse_calls.append(entity)
        raise AssertionError("reverse correspondence is not part of attachment acceptance")

    fixture.import_entity = import_entity
    fixture.model.Extension = SimpleNamespace(GetCorresponding2=inverse_forbidden)
    view = tag(SimpleNamespace(ReferencedDocument=fixture.model, GetCorresponding=corresponding_view), "IView")
    annotations = []
    for name, source_display in dimensions.items():
        source_dimension = tag(source_display.GetDimension2(0), "IDimension")
        source_dimension.dimension_token = name
        source_dimension.GetFeatureOwner = lambda: fixture.dimension_feature
        source_annotation = tag(source_display.GetAnnotation(), "IAnnotation")
        source_annotation.OwnerType, source_annotation.Owner = 3, fixture.model
        dimension = tag(SimpleNamespace(
            Name=name, FullName=source_dimension.FullName, DrivenState=1,
            SystemValue=source_dimension.SystemValue, Tolerance=SimpleNamespace(Type=0),
            dimension_token=name, GetFeatureOwner=lambda: fixture.dimension_feature,
        ), "IDimension")
        text = {}
        attached = tuple(import_entity(entity) for entity in source_annotation.GetAttachedEntities3())
        annotation = tag(SimpleNamespace(
            GetAttachedEntities3=lambda value=attached: value,
            GetAttachedEntityTypes=source_annotation.GetAttachedEntityTypes,
            IsDangling=lambda: False, Visible=1, OwnerType=0, Owner=view,
        ), "IAnnotation")
        display = SimpleNamespace(
            GetDimension2=lambda _index, value=dimension: value,
            GetPrimaryPrecision2=lambda: 2, ShowParenthesis=False,
            GetAnnotation=lambda value=annotation: value,
            SetText=lambda kind, value, state=text: state.__setitem__(kind, value),
            GetText=lambda kind, state=text: state.get(kind, ""),
        )
        annotation.GetSpecificAnnotation = lambda value=display: value
        annotations.append(annotation)

    def native_same(left, right):
        if hasattr(left, "dimension_token") and hasattr(right, "dimension_token"):
            return int(left.dimension_token == right.dimension_token)
        return _native_same(left, right)

    fixture.same = native_same
    fixture.adapter.swApp.IsSame = native_same
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_named_dimension", part._named_dimension)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.GetSpecificAnnotation().GetDimension2(0).Name)
    return fixture, view, annotations[::-1]


@pytest.mark.parametrize("failure", ("hide-refused", "unknown-visible", "prefix-printed", "source-constraint-lost"))
def test_group_visibility_and_source_proof_remain_strict_after_native_rebuild(monkeypatch, failure) -> None:
    fixture, view, annotations = _flat_group_fixture(monkeypatch)
    if failure == "hide-refused":
        class RefusingAnnotation:
            def __init__(self, native):
                self.native = native

            def __getattr__(self, name):
                return getattr(self.native, name)

            @property
            def Visible(self):
                return self.native.Visible

            @Visible.setter
            def Visible(self, _value):
                pass  # Native refusal fixture: the required state never persisted.

        annotations = [RefusingAnnotation(a) if drawing.dimension_name(fixture.adapter, a) == "RodTapFromZFlat" else a for a in annotations]
        with pytest.raises(RuntimeError, match="native visibility"):
            drawing._group_flat_locations(fixture.adapter, view, annotations)
        return
    drawing._group_flat_locations(fixture.adapter, view, annotations)
    if failure == "unknown-visible":
        annotations[0].Visible = 0
    elif failure == "prefix-printed":
        leader = next(a for a in annotations if drawing.dimension_name(fixture.adapter, a) == "LeverBoreFromZFlat")
        leader.GetSpecificAnnotation().SetText(1, "3X ")
    else:
        fixture.lines[0].GetStartPoint2().relations.clear()
    with pytest.raises(RuntimeError):
        drawing._assert_grouped_flat_locations(drawing._flat_group_annotations(fixture.adapter, view, annotations))


_FEATURE_KINDS = {
    "bottom_face": "face",
    "top_face": "face",
    "hex_flats": "stock",
    "lever_bore": "hole",
    "thumb_tap": "threaded_hole",
    "rod_tap": "threaded_hole",
}


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]) -> FaceGeometry:
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, tuple(v / 1000 for v in box_mm))


def _owners(geometry: FaceGeometry) -> list[str]:
    selectors = export_features.feature_selectors("mg_magnifying_clamp")
    return [name for name, specs in selectors.items() if any(spec.matches(geometry) for spec in specs)]


def test_the_clamp_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert "mg_magnifying_clamp" in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest("mg_magnifying_clamp")
    assert {name: feature["kind"] for name, feature in manifest["features"].items()} == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert manifest["notes"]["manufacturing"] == []
    h, r_tap = geom.BLOCK_HEIGHT, spec.ROD_TAP_DRILL_DIA / 2
    bore_r = geom.LEVER_BORE_DIA / 2
    thumb_low = geom.LEVER_BORE_Y + math.sqrt(bore_r**2 - r_tap**2)
    expected = {
        "bottom_face": [_plane((0.0, -1.0, 0.0), 0.0)],
        "top_face": [_plane((0.0, 1.0, 0.0), h)],
        "hex_flats": [
            _plane((math.sin(math.radians(a)), 0.0, math.cos(math.radians(a))), geom.HEX_AF / 2)
            for a in range(0, 360, 60)
        ],
        "lever_bore": [
            _cylinder(geom.LEVER_BORE_DIA, (1.0, 0.0, 0.0), (-geom.HEX_AC / 2, geom.LEVER_BORE_Y - bore_r, -bore_r, geom.HEX_AC / 2, geom.LEVER_BORE_Y + bore_r, bore_r))
        ],
        "thumb_tap": [
            _cylinder(spec.ROD_TAP_DRILL_DIA, (0.0, -1.0, 0.0), (-r_tap, thumb_low, -r_tap, r_tap, h, r_tap))
        ],
        "rod_tap": [
            _cylinder(spec.ROD_TAP_DRILL_DIA, (0.0, 1.0, 0.0), (-r_tap, 0.0, -r_tap, r_tap, joint.ROD_TAP_DRILL_DEPTH, r_tap))
        ],
    }
    for name, faces in expected.items():
        for face in faces:
            assert _owners(face) == [name], name


def test_clamp_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest("mg_magnifying_clamp")["features"]
    inch = 25.4
    for name in ("bottom_face", "top_face"):
        assert features[name]["height"] == pytest.approx([1.15 * inch, 1.17 * inch])
    bore = features["lever_bore"]
    # The F drill at the title block's DRILLED HOLES +.004/0.
    assert bore["dia"] == pytest.approx([0.257 * inch, 0.261 * inch])
    assert bore["height"] == pytest.approx([0.78 * inch, 0.80 * inch])
    assert bore["thru"] is True and bore["axis"] == [1.0, 0.0, 0.0]
    for name in ("lever_bore", "thumb_tap", "rod_tap"):
        assert features[name]["location_from_z_flat"] == pytest.approx([0.24 * inch, 0.26 * inch])
    thumb, rod = features["thumb_tap"], features["rod_tap"]
    for tap in (thumb, rod):
        assert tap["thread"] == "#4-40 UNC-2B"
        assert tap["dia"] == pytest.approx([0.089 * inch, 0.093 * inch], abs=1e-3)
        assert tap["plug_tap_lead"] == pytest.approx(5 * inch / 40)
    assert thumb["drill_depth"] == pytest.approx([0.36 * inch, 0.38 * inch])
    assert thumb["thread_depth_ref"] == pytest.approx(geom.THUMB_TAP_LENGTH)
    assert rod["thread_depth"] == pytest.approx([0.32 * inch, 0.34 * inch])
    assert rod["drill_depth"] == pytest.approx([0.47 * inch, 0.49 * inch])
    # The thumb plug tap's stop window: full thread through the wall, short
    # of the far bore wall, inside the tap's reach.
    low, high = thumb["tap_reach"]
    assert low == pytest.approx(spec.TAP_REACH_NEEDED) and high == pytest.approx(spec.FAR_WALL_NEAREST)
    assert 0 < low < high < spec.PLUG_TAP_USABLE_LENGTH
    flats = features["hex_flats"]
    assert flats["af_ref"] == geom.HEX_AF and flats["requirements"] == []
