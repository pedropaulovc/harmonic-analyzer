"""Offline manufacturing/retention contracts for custom MHA-DT-VN-54."""

from __future__ import annotations

import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_dt_vn_cone_tip_collar as part
import cone_shaft_land_bands as lands
import draw_dt_vn_cone_tip_collar as drawing
import dt_cone_gear_spec as gears
import dt_vn_cone_tip_collar_spec as spec
import dt_tip_collar_air as air
import _native_tip_collar_air as native_air
from _fastener_catalog import FASTENERS
from _printed_tolerance import printed_band_mm
from _test_stock_recipes import discovered_recipes
from gear_seat_fit import GEAR_SEAT_CLEARANCE, seat_bore_band


def test_one_actual_terminal_reader_preserves_named_classes():
    assert lands.TERMINAL_DIA_MM == lands.TERMINAL_DIA_IN * lands.MM_PER_IN
    assert spec.BORE_DIA == lands.TERMINAL_DIA_MM
    assert gears.bore_dia_mm(6) == gears.bore_dia_mm(12) == spec.BORE_DIA
    assert spec.BORE_DIA_BAND == seat_bore_band(lands.RUNNING_DIA_BAND)
    low = spec.BORE_DIA_BAND[1] - lands.RUNNING_DIA_BAND[0]
    high = spec.BORE_DIA_BAND[0] - lands.RUNNING_DIA_BAND[1]
    assert (low, high) == pytest.approx(GEAR_SEAT_CLEARANCE)
    assert spec.SET_SCREW_SEAT_RADIUS == pytest.approx(
        lands.TERMINAL_FLAT_AF_MM - lands.TERMINAL_DIA_MM / 2.0
        - spec.INSTALLED_BORE_AXIS_OFFSET_MM,
    )
    assert gears.bore_flat_af_mm(6) == gears.bore_flat_af_mm(12) == lands.TERMINAL_FLAT_AF_MM
    assert spec.BORE_MODEL_DIA_MM > spec.BORE_DIA
    assert tuple(spec.BORE_MODEL_DIA_MM + v for v in spec.BORE_MODEL_DIA_BAND) == pytest.approx(
        tuple(spec.BORE_DIA + v for v in spec.BORE_DIA_BAND),
    )
    assert spec.INSTALLED_BORE_AXIS_OFFSET_MM == pytest.approx(
        (spec.BORE_MODEL_DIA_MM - spec.BORE_DIA) / 2.0,
    )


def test_terminal_flat_keeps_round_guidance_and_lands_the_stock_point():
    # Round guidance: the deepest printed flat on the largest land still
    # stops short of the axis, so the round wraps past it.
    af_low, af_high = lands.TERMINAL_FINISHED_AF_LIMITS_MM
    land_low, land_high = lands.TERMINAL_FINISHED_DIA_LIMITS_MM
    assert lands.TERMINAL_FLAT_OFFSET_MIN_MM == pytest.approx(af_low - land_high / 2.0)
    assert lands.TERMINAL_FLAT_OFFSET_MIN_MM > 0.0
    assert lands.TERMINAL_FLAT_OFFSET_MAX_MM == pytest.approx(af_high - land_low / 2.0)
    assert lands.TERMINAL_HALF_CHORD_MIN_MM == pytest.approx(
        math.sqrt((land_low / 2.0) ** 2 - lands.TERMINAL_FLAT_OFFSET_MAX_MM**2)
    )
    assert spec.SET_SCREW_THREAD_RADIAL_PLAY_MM == pytest.approx((0.0772 - 0.0728) * 25.4 / 2.0)


def test_stock_flat_point_overlaps_the_d_flat_at_every_printed_limit():
    """Overlap gate: every lateral term is a printed tolerance, and the
    least point face must still overlap the least flat face."""
    float_max = (spec.BORE_FINISHED_DIA_LIMITS_MM[1] - lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0]) / 2.0
    terms = spec.SCREW_POINT_LATERAL_OFFSETS_MM
    assert set(terms) == {"tap centring", "tap angle", "screw thread play", "collar float"}
    assert terms["tap centring"] == printed_band_mm(2)
    assert terms["collar float"] == pytest.approx(float_max)
    assert spec.TAP_ANGLE_RAD == pytest.approx(math.radians(1.0))
    assert spec.SCREW_POINT_RADIUS_MIN_MM == pytest.approx(0.039 * 25.4 / 2.0)
    assert spec.FLAT_FACE_HALF_WIDTH_MIN_MM == pytest.approx(
        lands.TERMINAL_HALF_CHORD_MIN_MM - lands.TERMINAL_FLAT_EDGE_BREAK_MAX
    )
    offset = sum(terms.values())
    assert spec.SCREW_LANDING_MARGIN_MM == pytest.approx(
        spec.FLAT_FACE_HALF_WIDTH_MIN_MM + spec.SCREW_POINT_RADIUS_MIN_MM - offset
    )
    assert spec.SCREW_LANDING_MARGIN_MM > 0.0
    # Centre margin is reported only: the point's centre may leave the flat.
    assert spec.SCREW_POINT_CENTRE_MARGIN_MM == pytest.approx(
        spec.SCREW_LANDING_MARGIN_MM - spec.SCREW_POINT_RADIUS_MIN_MM
    )
    # Negative control: one more point radius of offset loses the landing.
    assert spec.screw_landing_margin_mm(offset + spec.SCREW_LANDING_MARGIN_MM + 1e-6) < 0.0


def test_terminal_web_guard_reads_current_cutter_floor(monkeypatch):
    assert gears.TERMINAL_WEB_REQUIREMENTS_MM == {6: 0.62, 12: 2.02438}
    for teeth, minimum in gears.TERMINAL_WEB_REQUIREMENTS_MM.items():
        assert gears.terminal_web_mm(teeth) >= minimum
    previous = gears.terminal_web_mm(6)
    original = gears.floor_limits_mm
    monkeypatch.setattr(gears, "floor_limits_mm", lambda teeth: (
        original(teeth)[0] - 0.1, original(teeth)[1],
    ))
    assert gears.terminal_web_mm(6) == pytest.approx(previous - 0.05)
    # Both six and twelve guard the derived band, not a frozen historical web.
    expected_cap = min(
        gears.floor_limits_mm(teeth)[0] - 2.0 * minimum - gears.bore_dia_mm(teeth)
        for teeth, minimum in gears.TERMINAL_WEB_REQUIREMENTS_MM.items()
    )
    assert gears.terminal_web_bore_upper_mm() <= expected_cap + 1e-9


def test_custom_wall_target_uses_printed_bands():
    routine = printed_band_mm(2)
    axial = printed_band_mm(3)
    assert spec.ROUTINE_BAND_MM == routine
    assert spec.WIDTH_BAND_MM == spec.AXIAL_BAND_MM == spec.TAP_STATION_BAND_MM == axial
    assert spec.OUTER_DIA < spec.STOCK_DIA
    assert min(spec.WORST_WALLS_MM.values()) >= spec.WALL_TARGET_MM == 2.0
    envelope = spec.THREAD_ENVELOPE_DIA
    assert envelope > spec.SET_SCREW_MAJOR_DIA
    # The through hole's 1 degree carries its far exit along the axis.
    od_max_r = (spec.OUTER_DIA + routine) / 2.0
    drift = math.tan(math.radians(1.0)) * (spec.FLAT_DISTANCE + routine + od_max_r)
    assert spec.WORST_WALLS_MM["tap to south shoulder"] == pytest.approx(
        spec.TAP_STATION - axial - spec.NOSE_LENGTH - axial
        - envelope / 2.0 - spec.EDGE_BREAK - drift,
    )
    assert spec.WORST_WALLS_MM["tap to north face"] == pytest.approx(
        spec.WIDTH - axial - spec.TAP_STATION - axial
        - envelope / 2.0 - spec.EDGE_BREAK - drift,
    )
    assert spec.WORST_WALLS_MM["nose bore to round OD"] == pytest.approx(
        (spec.NOSE_DIA - routine) / 2.0
        - spec.BORE_FINISHED_DIA_LIMITS_MM[1] / 2.0 - 2.0 * spec.EDGE_BREAK,
    )
    assert spec.TAP_STATION == (spec.NOSE_LENGTH + spec.WIDTH) / 2.0
    assert spec.WORST_WALLS_MM["tap to flat side rims"] == pytest.approx(
        math.sqrt(((spec.OUTER_DIA - routine) / 2.0)**2 - (spec.FLAT_DISTANCE + routine)**2)
        - envelope / 2.0 - spec.EDGE_BREAK - routine,
    )
    # Every axial term feeding a tap wall prints at .XXX.
    for name in ("TapStation", "NoseLength", "CollarWidth"):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 3


def test_full_thread_counts_male_and_female_incomplete_ends():
    assert spec.SET_SCREW_HOLE.kind == "tapped"
    assert spec.SET_SCREW_HOLE.size == spec.SET_SCREW_THREAD
    assert spec.SET_SCREW_HOLE.end == "through_all"
    assert not spec.SET_SCREW_HOLE.overrides_mm
    bore_max = spec.BORE_FINISHED_DIA_LIMITS_MM[1]
    land_min = lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0]
    float_max = (bore_max - land_min) / 2.0
    flat_max = lands.TERMINAL_FLAT_AF_MM + lands.FLAT_AF_BAND[0] - land_min / 2.0
    flat_min = lands.TERMINAL_FLAT_AF_MM + lands.FLAT_AF_BAND[1] - lands.TERMINAL_FINISHED_DIA_LIMITS_MM[1]/2.0
    tilt = spec.SET_SCREW_MAJOR_DIA / 2.0 * math.sin(spec.SET_SCREW_MAX_AXIS_ANGLE_RAD)
    point_chamfer = (spec.SET_SCREW_MAJOR_DIA - spec.SET_SCREW_FACTORY_POINT_MIN_DIA) / 2.0
    male_start = flat_max + float_max + 2.0 * tilt + point_chamfer + spec.SET_SCREW_PITCH
    # The through hole is whole only outside the bore it crosses.
    female_start = bore_max / 2.0 + spec.EDGE_BREAK + spec.SET_SCREW_PITCH
    female_end = spec.FLAT_DISTANCE - spec.ROUTINE_BAND_MM - spec.EDGE_BREAK - spec.SET_SCREW_PITCH
    face_chamfer_max = (
        (spec.SET_SCREW_MAJOR_DIA - spec.SET_SCREW_SOCKET_AF) / 2.0
        / math.tan(math.radians(spec.SET_SCREW_END_FACE_MIN_ANGLE_DEG))
    )
    male_end = (
        flat_min - float_max + spec.SET_SCREW_LENGTH - spec.SET_SCREW_LENGTH_BAND_MM
        - face_chamfer_max - spec.SET_SCREW_PITCH
        - spec._STOCK_AXIAL_PROJECTION_LOSS_MM
    )
    assert spec.WORST_FULL_ENGAGEMENT_MM == pytest.approx(min(female_end, male_end) - max(male_start, female_start))
    assert spec.WORST_FULL_ENGAGEMENT_MM >= 1.5 * spec.SET_SCREW_MAJOR_DIA
    expected_access = (
        flat_min - float_max + spec.SET_SCREW_LENGTH - spec.SET_SCREW_LENGTH_BAND_MM
        - spec.FLAT_DISTANCE - spec.ROUTINE_BAND_MM
        - spec._STOCK_AXIAL_PROJECTION_LOSS_MM
    )
    assert spec.WORST_SOCKET_ACCESS_MM == pytest.approx(expected_access)
    assert spec.WORST_SOCKET_ACCESS_MM > 0.0
    assert expected_access - spec.IN / 16.0 <= 0.0  # the verified 1/4-inch screw is too short


def test_stock_screw_stays_inside_the_rotating_envelope():
    assert spec.ROTATING_ENVELOPE_RADIUS_MM >= (spec.OUTER_DIA + spec.ROUTINE_BAND_MM) / 2.0
    flat_max = lands.TERMINAL_FLAT_AF_MM + lands.FLAT_AF_BAND[0] - lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0]/2.0
    float_max = (spec.BORE_FINISHED_DIA_LIMITS_MM[1]-lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0])/2.0
    assert spec.ROTATING_ENVELOPE_RADIUS_MM >= math.hypot(
        flat_max + float_max + spec.SET_SCREW_LENGTH + spec.SET_SCREW_LENGTH_BAND_MM,
        spec.SET_SCREW_MAJOR_DIA / 2.0,
    )


def test_procurement_is_custom_not_a_relabelled_vendor_collar():
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-DT-VN-54"
    assert row["process"] != "purchased"
    assert row["material"] == part.MATERIAL
    assert "94355A213" in row["stock"]
    assert "18-8" in row["material_specification"]
    assert "supplier_skus" not in row
    assert part.PART_NAME not in FASTENERS
    assert "9414T1" not in discovered_recipes()
    assert spec.SET_SCREW_SKU == "94355A213"
    assert spec.SET_SCREW_LENGTH == 5.0 * spec.IN / 16.0
    assert spec.SET_SCREW_SOCKET_AF == 0.035 * spec.IN
    assert not (Path(part.__file__).parent / "diagnostics" / "diag_build_9414T1.py").exists()
    assert spec.SET_SCREW_LENGTH_BAND_MM == 0.01 * spec.IN
    assert spec.SET_SCREW_SOCKET_DEPTH == 0.060 * spec.IN  # ASME minimum, not vendor-exact


def test_manufacturing_configs_restore_the_installed_parent(monkeypatch):
    active = ["Default"]
    creations = []
    suppressions = []

    def show(name):
        active[0] = name
        return True

    def add(name, *_args):
        creations.append((name, active[0]))
        active[0] = name
        return object()

    model = SimpleNamespace(ShowConfiguration2=show, ConfigurationManager=SimpleNamespace(AddConfiguration2=add))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "active_configuration_name", lambda _adapter, _model: active[0])
    class Feature:
        def __init__(self, name):
            self.name = name

        def SetSuppression2(self, state, option, names):
            assert (state, option) == (0, 1)
            assert names is not None  # VT_NULL VARIANT, not Python None.
            suppressions.append((active[0], self.name))
            return True

        def IsSuppressed2(self, option, names):
            assert option == 1 and names is not None
            return ((active[0], self.name) in suppressions,)

    monkeypatch.setattr(part, "_feature_by_name", lambda _adapter, name: Feature(name))
    part._manufacturing_configurations(SimpleNamespace(currentModel=model))
    assert creations == [("Collar", "Default"), ("SetScrew", "Default")]
    assert active[0] == "Default"
    assert {name for config, name in suppressions if config == "Collar"} == set(part.SCREW_FEATURES)
    assert {name for config, name in suppressions if config == "SetScrew"} == set(part.COLLAR_FEATURES)




@pytest.mark.parametrize("refuse", [False, True])
def test_part_max_types_are_authored_and_read_back(monkeypatch, refuse):
    class Tolerance:
        __slots__ = ("value",)

        def __init__(self):
            self.value = 0

        @property
        def Type(self):
            return self.value

        @Type.setter
        def Type(self, value):
            if not refuse:
                self.value = value

    tolerances = {name: Tolerance() for name in ("TapRootLimit", "ShoulderRadius")}
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_named_dimension", lambda _adapter, _feature, name: (
        None, SimpleNamespace(Tolerance=tolerances[name]),
    ))
    if refuse:
        with pytest.raises(RuntimeError, match="native tolerance type"):
            part._functional_dimension_types(object())
    else:
        part._functional_dimension_types(object())
        assert {name: tol.Type for name, tol in tolerances.items()} == {
            "TapRootLimit": 6, "ShoulderRadius": 6,
        }


@pytest.mark.parametrize("expected", [drawing.TAP_DIMENSION_TYPES, drawing.SIDE_DIMENSION_TYPES])
def test_drawing_refuses_a_lost_max_type(monkeypatch, expected):
    types = dict(expected)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    rows = [SimpleNamespace(
        name=name,
        GetSpecificAnnotation=lambda name=name: SimpleNamespace(
            GetDimension2=lambda _index: SimpleNamespace(Tolerance=SimpleNamespace(Type=types[name])),
        ),
    ) for name in types]
    drawing._assert_functional_dimension_types(object(), rows, expected)
    for name in expected:
        types[name] = 0
        with pytest.raises(RuntimeError, match="lost native types"):
            drawing._assert_functional_dimension_types(object(), rows, expected)
        types[name] = expected[name]


class _Sheet:
    """One sheet: a sheet view plus drawing views holding named notes and
    dimensions; EditDelete removes the selected note."""

    def __init__(self, notes, callouts):
        self.selected = None
        self.views = {"sheet": [], "Drawing View3": []}
        for owner, name, text in notes:
            self.views[owner].append(self._note(name, text))
        self.callouts = callouts
        self.sheet_view = SimpleNamespace(GetAnnotations=lambda: self.views["sheet"])
        self.tap_view = SimpleNamespace(
            name="Drawing View3",
            GetAnnotations=lambda: self.views["Drawing View3"],
            GetDisplayDimensions=lambda: self.callouts,
        )
        self.sheet_view.GetNextView = lambda: self.tap_view
        self.tap_view.GetNextView = lambda: None

    def _note(self, name, text):
        note = SimpleNamespace(GetType=lambda: 6, OwnerType=1, GetName=lambda: name)
        note.GetSpecificAnnotation = lambda: SimpleNamespace(GetText=lambda: text)
        note.Select2 = lambda _append, _mark: setattr(self, "selected", note) or True
        return note

    def GetViews(self):
        return [[self.sheet_view, self.tap_view]]

    def ActivateSheet(self, name):
        return name == drawing.SHEET_NAMES[0]

    def GetFirstView(self):
        return self.sheet_view

    def ClearSelection2(self, _all):
        self.selected = None

    def EditDelete(self):
        for notes in self.views.values():
            if self.selected in notes:
                notes.remove(self.selected)


def _callout(name, *texts, hole=True):
    data = SimpleNamespace(GetTextCount=lambda: len(texts), GetTextAtIndex=lambda i: texts[i])
    return SimpleNamespace(
        IsHoleCallout=lambda: hole, GetDisplayData=lambda: data,
        GetAnnotation=lambda: SimpleNamespace(GetName=lambda: name),
    )


def test_collar_deletes_only_the_notes_it_did_not_place(monkeypatch):
    """Run 8087fd13c: one unplaced note, DetailItem348, sat across CollarWidth
    and CollarDia. It goes by not being ours, whatever its text says."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    sheet = _Sheet(
        [("sheet", "DetailItem1", "CHECK TAPPED HOLE"),
         ("Drawing View3", "DetailItem2", "RADIAL TAP VIEW SCALE 2:1"),
         ("Drawing View3", "DetailItem348", "2-56 Tapped Hole")],
        [_callout("RD1", "2-56 UNC - 2B", "THRU"), _callout("RD9", "x", hole=False)],
    )
    adapter = SimpleNamespace(currentModel=sheet)
    placed = frozenset({"DetailItem1", "DetailItem2"})
    with pytest.raises(RuntimeError, match="not settled|after the last rebuild"):
        drawing._assert_settled_annotations(adapter, placed, "RD1")
    drawing._delete_unplaced_notes(adapter, placed)
    assert set(drawing._sheet_notes(adapter)) == placed
    drawing._assert_settled_annotations(adapter, placed, "RD1")
    with pytest.raises(RuntimeError, match="not every placed note"):
        drawing._delete_unplaced_notes(adapter, placed | {"DetailItem7"})
    sheet.callouts = [_callout("RD1", "2-56 UNC - 2B", "6.80 DEEP")]
    with pytest.raises(RuntimeError, match="not settled"):
        drawing._assert_settled_annotations(adapter, placed, "RD1")
    sheet.callouts = []
    with pytest.raises(RuntimeError, match="not settled"):
        drawing._assert_settled_annotations(adapter, placed, "RD1")


def test_shoulder_root_prints_max_and_the_air_stack_books_it():
    """Machinist review of the r3 build asked about R0.25 0.00/-0.25: it is a
    tool-nose root, sharp to 0.25 all good, so it prints R0.25 MAX."""
    assert drawing.SIDE_DIMENSION_TYPES == {"ShoulderRadius": 6}
    assert not hasattr(spec, "SHOULDER_ROOT_BAND")
    nose = air.TIERS[0]
    assert nose.north_upper_mm >= spec.SHOULDER_ROOT_RADIUS


def test_native_default_bom_and_manufacturing_descriptions_share_spec_authority(monkeypatch):
    grouped = []
    configs = {name: SimpleNamespace(Description="", UseDescriptionInBOM=False)
               for name in spec.MANUFACTURING_DESCRIPTIONS}
    model = SimpleNamespace(GetConfigurationByName=configs.get)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "apply_grouped_bom_properties", lambda _adapter, names, **kwargs:
                        grouped.append((tuple(names), kwargs)))
    part._configuration_bom_identity(SimpleNamespace(currentModel=model))
    assert grouped == [(("Default",), {
        "part_number": _config.parts(part.PART_NAME)["number"],
        "description": spec.BOM_DESCRIPTION,
    })]
    assert _config.parts(part.PART_NAME)["description"] == spec.BOM_DESCRIPTION
    for name, description in spec.MANUFACTURING_DESCRIPTIONS.items():
        assert configs[name].Description == description
        assert configs[name].UseDescriptionInBOM is True


def test_stepped_air_tiers_include_native_tool_root_and_stock_screw():
    assert air.PARTITION_STATION_MM == spec.NOSE_LENGTH - spec.SHOULDER_ROOT_RADIUS
    assert {tier.name for tier in air.TIERS} == {"nose", "body", "screw"}
    nose, body, screw = air.TIERS
    assert nose.north_mm == body.south_mm == air.PARTITION_STATION_MM
    assert nose.north_upper_mm == spec.AXIAL_BAND_MM + spec.SHOULDER_ROOT_RADIUS
    assert nose.radius_mm + nose.radius_upper_mm == (spec.NOSE_DIA + spec.ROUTINE_BAND_MM) / 2.0
    assert body.south_lower_mm == -spec.AXIAL_BAND_MM
    assert body.north_mm + body.north_upper_mm == spec.WIDTH + spec.WIDTH_BAND_MM
    screw_reach = spec.SET_SCREW_LENGTH + spec.SET_SCREW_LENGTH_BAND_MM
    assert screw.south_lower_mm == pytest.approx(
        -(spec.TAP_STATION_BAND_MM + screw_reach * math.sin(spec.SET_SCREW_MAX_AXIS_ANGLE_RAD))
    )
    assert screw.radius_mm > spec.SET_SCREW_END_RADIUS
    assert screw.radius_mm + screw.radius_upper_mm == pytest.approx(math.hypot(
        spec._POINT_PLANE_MAX + screw_reach,
        spec.SET_SCREW_MAJOR_DIA / 2.0 + spec.TAP_LATERAL_BAND_MM
        + screw_reach * math.sin(spec.SET_SCREW_MAX_AXIS_ANGLE_RAD),
    ))


def test_filled_cylinder_projection_is_three_dimensional_not_z_only():
    # A mathematical primitive test, not a certificate of the actual machine.
    moving_origin, fixed_origin = (10.0, 0.0, -2.0), (0.0, 0.0, 0.0)
    axis = (0.0, 0.0, 1.0)
    z = (0.0, 0.0, 1.0)
    x = (1.0, 0.0, 0.0)
    def gap(normal):
        return air.cylinder_support(moving_origin, axis, 0.0, 1.0, 1.0, normal, maximum=False) - (
            air.cylinder_support(fixed_origin, axis, -3.0, 0.0, 2.0, normal, maximum=True)
        )
    assert gap(z) < 0.0
    assert gap(x) == pytest.approx(7.0)
    assert air.cylinder_support((0.0, 0.0, 0.0), axis, -1.0, 1.0, 2.0,
                                (0.6, 0.0, 0.8), maximum=True) == pytest.approx(2.0)


@pytest.mark.parametrize("result", [None, (False, 0.0, 0.0, 0.0),
                                    (1, 0.0, 0.0, 0.0),
                                    (True, 0.0, 0.0), (True, math.nan, 0.0, 0.0)])
def test_native_air_refuses_missing_or_invalid_extreme_points(result):
    body = SimpleNamespace(GetExtremePoint=lambda *_direction: result)
    with pytest.raises(RuntimeError, match="extreme point"):
        native_air._extreme(body, (0.0, 0.0, 1.0), "negative native readback")


def test_native_air_refuses_nan_transform_readback(monkeypatch):
    monkeypatch.setattr(native_air, "_early_bound", lambda value, _interface: value)
    utility = SimpleNamespace(CreateTransform=lambda _request: SimpleNamespace(
        ArrayData=(math.nan,) + (0.0,) * 15,
    ))
    with pytest.raises(RuntimeError, match="native p1 transform"):
        native_air._swing_transform(utility, 0.0)


def test_already_active_configuration_never_misreads_false_as_failure(monkeypatch):
    active = ["Default"]
    calls = []
    def show(name):
        calls.append(name)
        active[0] = name
        return True
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "active_configuration_name", lambda _adapter, _model: active[0])
    adapter = SimpleNamespace(currentModel=SimpleNamespace(ShowConfiguration2=show))
    part._activate_configuration(adapter, "Default")
    assert calls == []
    part._activate_configuration(adapter, "Collar")
    assert calls == ["Collar"]


@pytest.mark.parametrize("readback", [None, (0.0,)*4, (math.nan, 0.0, 0.0, 0.0, 0.0)])
def test_native_air_refuses_nonfinite_trimmed_face_points(readback):
    with pytest.raises(RuntimeError, match="closest point"):
        native_air._closest(SimpleNamespace(GetClosestPointOn=lambda *_args: readback),
                            (0.0, 0.0, 0.0), "actual trimmed face")


def test_native_transform_positive_control_and_reflection_refusal():
    identity = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
                0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
    assert native_air._array(SimpleNamespace(ArrayData=identity), "positive") == identity
    reflected = (-1.0, *identity[1:])
    with pytest.raises(RuntimeError, match="reflected"):
        native_air._array(SimpleNamespace(ArrayData=reflected), "negative")


@pytest.mark.parametrize("transition_result", [False, 1, None])
def test_configuration_transition_requires_actual_bool_and_name(monkeypatch, transition_result):
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "active_configuration_name", lambda *_args: "Default")
    adapter = SimpleNamespace(currentModel=SimpleNamespace(ShowConfiguration2=lambda _name: transition_result))
    with pytest.raises(RuntimeError, match="activate"):
        part._activate_configuration(adapter, "Collar")


@pytest.mark.parametrize("readback", [None, (), (1,), (False,), (True, True)])
def test_actual_configuration_suppression_must_read_back_one_native_bool(monkeypatch, readback):
    active = ["Default"]
    def show(name):
        active[0] = name
        return True
    def add(name, *_args):
        active[0] = name
        return object()
    class Feature:
        def __bool__(self):
            raise AssertionError("a bound native feature is not a BOOL result")
        def SetSuppression2(self, state, option, names):
            assert (state, option) == (0, 1) and names is not None
            return True
        def IsSuppressed2(self, option, names):
            assert option == 1 and names is not None
            return readback
    model = SimpleNamespace(ShowConfiguration2=show, ConfigurationManager=SimpleNamespace(AddConfiguration2=add))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "active_configuration_name", lambda *_args: active[0])
    monkeypatch.setattr(part, "_feature_by_name", lambda *_args: Feature())
    with pytest.raises(RuntimeError, match="suppression did not persist"):
        part._manufacturing_configurations(SimpleNamespace(currentModel=model))


@pytest.mark.parametrize("normal", [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.6, 0.0, 0.8)])
def test_exact_finite_drum_tilt_keeps_full_shadow_and_manufactured_caps(normal):
    for tier in air.DRUM_TIERS:
        straight = air.cylinder_support(
            (0.0, 0.0, 0.0), (0.0, 0.0, 1.0),
            tier.south_mm+tier.south_lower_mm, tier.north_mm+tier.north_upper_mm,
            tier.radius_mm+tier.radius_upper_mm, normal, maximum=True,
        )
        assert air._tilted_fixed_support(tier, normal, 0.0) == pytest.approx(straight)
        tilted = air._tilted_fixed_support(tier, normal, 0.02)
        assert tilted >= straight-1e-12
        assert air._tilted_fixed_support(tier, normal, 0.03) >= tilted-1e-12


def test_collar_air_shares_the_assembly_post_face_and_tip_tap_bands():
    import build_dt_drive_train_assembly as bdt

    # The assembly books the post band symmetrically; the collar air books it
    # less the screw clearance the pushed post takes up (MHA-DT-00 step 3).
    axial = air.AXIAL_TERMS_MM
    assert sum(axial[name] for name in (
        "post platform tap station", "post screw clearance", "post counterbore pattern",
        "post cone boss length",
    )) + air.POST_SCREW_CLEARANCE_TAKEN_UP_MM == pytest.approx(bdt.POST_BOSS_FACE_AXIAL_BAND_MM)
    tip = air.TIP_END_TERMS_MM
    assert sum(tip[name] for name in (
        "tip platform hold-down station", "tip hold-down screw clearance", "tip block foot tap station",
    )) == pytest.approx(bdt.TIP_TAP_LATERAL_BAND_MM)


def test_collar_air_gains_the_pushed_posts_axial_clearance(monkeypatch):
    import draw_dt_drive_train_assembly as sheet

    assert "HOLD MHA-DT-05 PUSHED TOWARD MHA-DT-21 ALONG THE SHAFT" in " ".join(
        sheet.CONE_CRANK_STEPS.split())
    taken = air.POST_SCREW_CLEARANCE_TAKEN_UP_MM
    assert taken > 0.0 and air.AXIAL_TERMS_MM["post screw clearance"] == pytest.approx(0.0)
    # Only the along-shaft share goes; the across and tilt shares stay.
    assert air.POST_END_TERMS_MM["post screw clearance"] == pytest.approx(taken)
    pushed = {(r["tier"], r["drum_tier"], r["angle_deg"]): r for r in air.full_sweep_proof()}
    monkeypatch.setitem(air.AXIAL_TERMS_MM, "post screw clearance", taken)
    loose = {(r["tier"], r["drum_tier"], r["angle_deg"]): r for r in air.full_sweep_proof()}
    for key in (k for k in pushed if k[0] == "nose"):
        along = abs(air.collar_pose_frame(key[2])[1][2])
        assert pushed[key]["air_mm"] - loose[key]["air_mm"] == pytest.approx(taken * along)



def test_collar_air_bounds_the_released_tip_by_the_post_journal_not_the_vendor_cup():
    shaft = air.shaft

    name = "shaft swing in the post journal off the cup"
    release = air.TIP_END_TERMS_MM[name]
    assert name in air.IN_SERVICE_CLEARANCES
    c = max(shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM)
    span = shaft.T006_TIP_STATION - air.cone_line.POST_STATION
    # Seated at one side of the journal, released to the other, over the
    # shaft spec's guaranteed support across the end-play stroke.
    assert release == pytest.approx(2.0 * c * span / shaft.JOURNAL_SUPPORT_SPAN_MIN_MM)
    # B18.6.2 bounds no cup depth or wall angle: the nominal 90 deg vendor cup
    # over the 0.25 end play would have booked less.
    assert release > 0.5


def test_collar_air_books_each_printed_source_once():
    common = {
        *air.AXIAL_TERMS_MM, *air.POST_END_TERMS_MM, *air.TIP_END_TERMS_MM,
        *air.SWING_TERMS_MM, "T120 set of the swing",
        "collar float on the journal", "collar cock on the journal",
        *(f"bank {name}" for name in air.bank.DATUM_CHAIN_STACK),
        "bank accepted stack length",
        "drum tier limits", "G19 cock in its running fit",
    }
    for tier in air.TIERS:
        terms = air.closure_terms_mm(tier, air.DRUM_TIERS[0], 0.0)
        assert set(terms) == common | set(tier.limits)
        assert set(terms) <= air.IN_SERVICE_CLEARANCES | air.INDEPENDENT_TOLERANCES
        assert all(value >= 0.0 for value in terms.values())
    # One post mounting error enters once: along the shaft, plus across it,
    # plus the face tilt it gives the shaft line.
    terms = air.closure_terms_mm(air.TIERS[0], air.DRUM_TIERS[0], 0.0)
    along = abs(air.collar_pose_frame(0.0)[1][2])
    for name in ("post platform tap station", "post screw clearance", "post counterbore pattern"):
        assert terms[name] > air.AXIAL_TERMS_MM[name] * along
    assert terms["bank accepted stack length"] == pytest.approx(
        air.bank.STACK_L20_ACCEPT_BAND[0]
    )


def test_collar_air_splits_the_stock_screw_limits_into_their_sources():
    screw = air.TIERS[2]
    # The sources add up to the composite tier limits.
    assert sum(a for a, _ in screw.limits.values()) == pytest.approx(-screw.south_lower_mm)
    assert sum(r for _, r in screw.limits.values()) == pytest.approx(screw.radius_upper_mm)
    # The thread rock and the collar's float are clearances, booked once
    # each; the float joins the collar's own float on the journal.
    rock, float_ = screw.limits["set screw rock in its thread"], screw.limits["collar float on the journal"]
    assert rock[0] > 0.0 and rock[1] > 0.0 and float_[1] > 0.0
    assert {"set screw rock in its thread", "collar float on the journal"} <= air.IN_SERVICE_CLEARANCES
    assert not set(screw.limits) & {"collar tier axial limit", "collar tier radial limit"}
    nose_terms = air.closure_terms_mm(air.TIERS[0], air.DRUM_TIERS[0], 0.0)
    screw_terms = air.closure_terms_mm(screw, air.DRUM_TIERS[0], 0.0)
    across = math.sqrt(1.0 - air.collar_pose_frame(0.0)[1][2] ** 2)
    assert screw_terms["collar float on the journal"] == pytest.approx(
        nose_terms["collar float on the journal"] + float_[1] * across)
    stack = air.AirStack("screw", "tooth_face", 0.0, 10.0, screw_terms, 0.0)
    assert "set screw rock in its thread" in stack.clearances


def test_collar_air_refuses_an_unclassified_source(monkeypatch):
    monkeypatch.setitem(air.AXIAL_TERMS_MM, "shim nobody classified", 0.01)
    with pytest.raises(ValueError, match="unclassified source.*shim nobody classified"):
        air.closure_terms_mm(air.TIERS[0], air.DRUM_TIERS[0], 0.0)
    with pytest.raises(ValueError, match="unclassified source"):
        air.AirStack("t", "d", 0.0, 10.0, {"collar feeler set": 1.0, "mystery": 1.0}, 0.0)


def test_collar_air_adds_clearances_and_rss_only_the_tolerances(monkeypatch):
    # The released resolution: the interval arc is part of the closing stack.
    rows = air.full_sweep_proof()
    assert {row["method"] for row in rows} == {"statistical"}
    assert min(row["arithmetic_mm"] for row in rows) <= 0.0
    assert min(row["air_mm"] for row in rows) > 0.0
    for row in rows:
        closure = row["closure_mm"]
        assert row["air_mm"] == pytest.approx(row["nominal_mm"] - sum(closure.values()))
        fixed = {"RSS of the printed tolerances", "continuous p1 interval arc"}
        assert fixed <= set(closure)
        assert set(closure) - fixed <= air.IN_SERVICE_CLEARANCES
        assert ("set screw rock in its thread" in closure) == (row["tier"] == "screw")
    stack = air.AirStack("t", "d", 0.0, 10.0, {"tip cup in its thread": 1.0, "collar feeler set": 3.0,
                                               "collar nose length": 4.0}, 0.5)
    assert stack.statistical_mm == pytest.approx(10.0 - 1.0 - 5.0 - 0.5)
    assert stack.arithmetic_mm == pytest.approx(10.0 - 8.0 - 0.5)
    monkeypatch.setattr(air, "closure_terms_mm", lambda *_args: {"collar feeler set": 0.01})
    rows = air.full_sweep_proof(intervals=20)
    assert {row["method"] for row in rows} == {"arithmetic"}
    assert all(row["air_mm"] == row["arithmetic_mm"] for row in rows)


def test_collar_air_refuses_when_the_booked_air_closes(monkeypatch):
    monkeypatch.setattr(air, "closure_terms_mm", lambda *_args: {"collar feeler set": 100.0})
    with pytest.raises(ValueError, match="can reach G19"):
        air.full_sweep_proof(intervals=4)


def test_native_cylinder_positive_control_uses_actual_property_and_finite_axis(monkeypatch):
    monkeypatch.setattr(native_air, "_early_bound", lambda value, _interface: value)
    surface = SimpleNamespace(IsCylinder=lambda: True,
                              CylinderParams=(0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.001))
    face = SimpleNamespace(GetSurface=lambda: surface)
    body = SimpleNamespace(GetFaces=lambda: (face,))
    assert native_air._cylinders(body, 1.0, (0.0, 1.0, 0.0), "positive") == [
        (face, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 1.0),
    ]
    surface.CylinderParams = (0.0, 0.0, 0.0, math.nan, 1.0, 0.0, 0.001)
    with pytest.raises(RuntimeError, match="cylinder parameters"):
        native_air._cylinders(body, 1.0, (0.0, 1.0, 0.0), "negative")


def test_custom_body_is_smallest_printed_od_retaining_existing_wall_target():
    required = 2.0*max(spec.BODY_RADIUS_REQUIREMENTS_MM.values())+spec.ROUTINE_BAND_MM
    assert spec.OUTER_DIA >= required
    assert spec.OUTER_DIA-0.01 < required
    assert spec.WALL_TARGET_MM == 2.0
    assert min(spec.WORST_WALLS_MM.values()) >= spec.WALL_TARGET_MM


def test_coupled_body_shift_has_one_source_and_keeps_radial_and_body_process_envelopes():
    import cone_line
    delta = lands.TIP_COLLAR_BODY_NORTH_SHIFT_MM
    assert delta == pytest.approx(0.50)
    assert spec.NOSE_LENGTH == pytest.approx(3.0 + delta)
    assert spec.WIDTH == pytest.approx(11.0 + delta)
    assert spec.TAP_STATION == pytest.approx(7.0 + delta)
    assert cone_line.TIP_END_EXTENSION_MM == pytest.approx(7.5 + delta)
    assert spec.WIDTH-spec.NOSE_LENGTH == 8.0
    assert spec.TAP_STATION-spec.NOSE_LENGTH == 4.0
    assert spec.WIDTH-spec.TAP_STATION == 4.0
    assert spec.NOSE_DIA == 6.40
    assert lands.TERMINAL_FLAT_AF_MM == 0.4318


def test_printed_physical_limits_keep_exact_native_model_and_real_fit_distinct():
    assert lands.TERMINAL_FINISHED_DIA_LIMITS_MM == pytest.approx((0.76708, 0.7874))
    assert spec.BORE_FINISHED_DIA_LIMITS_MM == pytest.approx((0.8128, 0.8636))
    assert lands.TERMINAL_DIA_MM == pytest.approx(0.7874)
    assert spec.BORE_MODEL_DIA_MM == pytest.approx(0.8382)
    minimum = (spec.BORE_FINISHED_DIA_LIMITS_MM[0]-lands.TERMINAL_FINISHED_DIA_LIMITS_MM[1])/2.0
    maximum = (spec.BORE_FINISHED_DIA_LIMITS_MM[1]-lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0])/2.0
    assert (minimum, maximum) == pytest.approx((lands.TIP_COLLAR_MIN_RADIAL_FLOAT_MM, lands.TIP_COLLAR_MAX_RADIAL_FLOAT_MM), abs=spec._PRINT_GRID_TOL_MM)


def test_original_journal_span_pays_north_withdrawal_once():
    from cone_stack_end_play import SHAFT_END_PLAY
    import dt_cone_gear_shaft_spec as shaft
    import dt_cone_pivot_post_spec as post
    expected = min(
        post.CONE_BOSS_LENGTH-printed_band_mm(post.DRAWING_PRECISION_BY_NAME["ConeBossLen"], unit=post.UNIT)-2.0*shaft.THRUST_EDGE_BREAK_MAX,
        shaft.JOURNAL_END+shaft.printed_length_deviations("Sec0End")[0]-shaft.JOURNAL_FREE_END_BREAK_MAX_MM-shaft.THRUST_EDGE_BREAK_MAX-SHAFT_END_PLAY[1],
    )
    assert shaft.JOURNAL_SUPPORT_SPAN_MIN_MM == pytest.approx(expected)


@pytest.mark.parametrize("section,native", [(0, 12.2555), (1, 9.525), (2, 6.35), (3, 3.175), (4, 0.7874)])
def test_all_land_physical_limit_readers_share_native_print_precision(section, native):
    import dt_cone_gear_shaft_spec as shaft
    assert shaft.DRAWING_PRECISION[f"Sec{section}Profile"][f"Sec{section}Dia"] == lands.LAND_DIA_PLACES[section]
    upper, lower = lands.SECTION_DIA_BANDS[section]
    nominal = round(native / 25.4, lands.LAND_DIA_PLACES[section]) * 25.4
    assert lands.land_finished_dia_limits_mm(native, section) == pytest.approx((nominal+lower, nominal+upper))
    if section:
        assert shaft.DRAWING_PRECISION[f"Sec{section}FlatProfile"][f"Sec{section}AF"] == lands.LAND_AF_PLACES[section]
        af = round(lands.SECTION_FLAT_AF[section], lands.LAND_AF_PLACES[section])
        assert lands.land_finished_af_limits_mm(section) == pytest.approx((af+lands.FLAT_AF_BAND[1], af+lands.FLAT_AF_BAND[0]))
    else:
        with pytest.raises(ValueError, match="no finished across-flat"):
            lands.land_finished_af_limits_mm(section)


def test_each_view_asserts_only_the_precision_it_keeps() -> None:
    # 027369849: each view asserted the whole map and failed on names that
    # live on other views.
    keeps = (drawing.END_KEEP.keys() | drawing.SIDE_KEEP.keys(), drawing.TAP_KEEP.keys(),
             drawing.BORE_KEEP.keys())
    for keep in keeps:
        assert set(drawing._precision(keep)) == set(keep)


def test_tap_root_limit_bounds_the_envelope_the_walls_book() -> None:
    """Codjiflo review of #2101: 2B alone has no root MAX, so the wall budget's
    tap envelope holds only while the sheet prints it.  The part carries the
    blanked gauge, the tap view imports its MAX at the booked diameter, and the
    north-face wall spends that diameter."""
    assert set(drawing.TAP_KEEP) == {"TapStation", "TapRootLimit"}
    assert spec.DRAWING_DIMENSIONS["TapRootGauge"] == {"TapRootLimit"}
    assert spec.DRAWING_PRECISION_BY_NAME["TapRootLimit"] == 2
    assert {"TapRootGauge", "TapRootPlane"} <= set(part.COLLAR_FEATURES)
    assert drawing.TAP_DIMENSION_TYPES == {"TapRootLimit": 6}
    assert round(spec.THREAD_ENVELOPE_DIA, 2) == spec.THREAD_ENVELOPE_DIA
    assert spec.WORST_WALLS_MM["tap to north face"] == pytest.approx(
        spec.WIDTH
        - spec.WIDTH_BAND_MM
        - spec.TAP_STATION
        - spec.TAP_STATION_BAND_MM
        - spec.THREAD_ENVELOPE_DIA / 2.0
        - spec.EDGE_BREAK
        - spec._TAP_AXIAL_DRIFT_MAX
    )


def test_part_sheet_carries_no_assembly_procedure() -> None:
    """Main's machinist review: four of the note lines were assembly or
    operating procedure. MHA-DT-00 step 3 sets the collar off its feeler and
    locks its set screw; the sheet keeps the stock line and the bore's fit."""
    import draw_dt_drive_train_assembly as assembly
    from cone_stack_end_play import COLLAR_FEELER

    printed = f"{spec.DRAWING_NOTES}\n{spec.INSTALLATION_NOTES}"
    for word in ("FEELER", "LEAF", "SNUG", "SWING", "SEAT", "T006"):
        assert word not in printed
    assert spec.INSTALLATION_NOTES.count("\n") == 1
    step = (
        f"PUSH MHA-DT-VN-54 ONTO A\n   {COLLAR_FEELER:.2f} FEELER ON T006; "
        "LOCK ITS SET SCREW ON THE FLAT."
    )
    assert step in assembly.CONE_CRANK_STEPS


def test_stock_line_is_a_supply_size_the_turned_od_comes_from() -> None:
    """Main's machinist review: '3/4 STEEL BAR STOCK OK.' said the bar stays at
    19.05 while the sheet prints a turned Ø17.48."""
    assert spec.DRAWING_NOTES == "SUPPLY 3/4 ROUND BAR."
    assert spec.OUTER_DIA + spec.ROUTINE_BAND_MM < spec.STOCK_DIA


def test_ream_callout_carries_the_bore_fit_statement() -> None:
    """Main's machinist review: the REAM band's mate was named only in the
    unattached note block. Its fit lines now ride the callout, unchanged."""
    assert spec.BORE_CALLOUT == f"REAM THRU\n{spec.INSTALLATION_NOTES}"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '{"BoreDia": spec.BORE_CALLOUT}' in source
    assert '"Installation Notes"' not in source


@pytest.mark.parametrize("keeps", [True, False])
def test_quarter_turn_puts_the_flat_down_and_refuses_a_lost_turn(monkeypatch, keeps) -> None:
    """r4 review: the end view put the flat facing the turning view's reader
    while the turning view drew it at the bottom."""
    class View:
        def __init__(self):
            self.value = 0.0

        @property
        def Angle(self):
            return self.value

        @Angle.setter
        def Angle(self, value):
            if keeps:
                self.value = value

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    view = View()
    if not keeps:
        with pytest.raises(RuntimeError, match="quarter turn"):
            drawing._quarter_turn(object(), view, "end view")
        return
    drawing._quarter_turn(object(), view, "end view")
    # Model +X (the flat's side) on the sheet after the view's rotation.
    assert (math.cos(view.Angle), math.sin(view.Angle)) == pytest.approx((0.0, -1.0))


def test_nose_dia_moves_from_the_end_view_onto_the_turning_view(monkeypatch) -> None:
    """r4 review: Ø6.40 sat only on the end view (rule 11)."""
    marks = [SimpleNamespace(name=name) for name in ("FlatDistance", "NoseDia", "CollarDia")]
    moves = []
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, mark: mark.name)
    monkeypatch.setattr(drawing, "move_model_dimension", lambda _adapter, mark, view, xy, source_view: (
        moves.append((mark.name, view, xy, source_view)) or "moved"
    ))
    left, moved = drawing._nose_dia_onto_side(object(), marks, "end", "side")
    assert moved == "moved"
    assert [mark.name for mark in left] == ["FlatDistance", "CollarDia"]
    assert moves == [("NoseDia", "side", drawing.NOSE_DIA_ON_SIDE, "end")]
    with pytest.raises(RuntimeError, match="one collar nose diameter"):
        drawing._nose_dia_onto_side(object(), marks[:1], "end", "side")


def test_nose_length_function_line_reads_above_its_value() -> None:
    """r4 review: 3.500's extension lines struck its function line."""
    below, above = drawing._side_callouts()
    assert above == {"NoseLength": spec.AXIAL_FUNCTION_CALLOUTS["NoseLength"]}
    assert "NoseLength" not in below
    assert below.keys() == drawing._function_callouts(drawing.SIDE_KEEP).keys() - {"NoseLength"}


def test_nose_dia_on_the_turning_view_clears_its_neighbours() -> None:
    # Left of the nose's south face, right of FlatDistance's text.
    assert drawing.END_KEEP["FlatDistance"][0] < drawing.NOSE_DIA_ON_SIDE[0]
    assert drawing.NOSE_DIA_ON_SIDE[0] < drawing.SIDE_CENTER[0] - spec.WIDTH * 4 / 2000.0
    # Farm run 20261101T005319353Z: its text box ran to keep + 18.3 mm and
    # crossed NoseLength's south extension line at x 182; it ends one text
    # clearance (1.78 mm) short of it.
    assert drawing.NOSE_DIA_ON_SIDE[0] + 0.0183 < 0.182 - 0.00178
    assert not 0.165 + 0.0183 < 0.182 - 0.00178


def test_three_place_lengths_state_their_function() -> None:
    """Main's machinist review: 11.500, 3.500 and 7.500 had no stated function.
    They hold the tap's walls; at .XX those walls fall below the floor."""
    three_place = {
        name
        for name, places in spec.DRAWING_PRECISION_BY_NAME.items()
        if places == 3 and name != "BoreDia"
    }
    assert three_place == {"NoseLength", "CollarWidth", "TapStation"}
    assert set(spec.AXIAL_FUNCTION_CALLOUTS) == three_place
    for text in spec.AXIAL_FUNCTION_CALLOUTS.values():
        assert not re.search(r"\d", text) and "\n" not in text
    side = drawing._function_callouts(drawing.SIDE_KEEP)
    tap = drawing._function_callouts(drawing.TAP_KEEP)
    assert side.keys() | tap.keys() == three_place
    loosen = 2.0 * (printed_band_mm(2) - spec.AXIAL_BAND_MM)
    for wall in ("tap to south shoulder", "tap to north face"):
        assert spec.WORST_WALLS_MM[wall] - loosen < 1.5


def test_installation_notes_name_the_journal_and_its_clearance() -> None:
    """Machinist review of the round-2 build: the Ø0.849 bore named neither
    the journal it slides on nor the fit. It names MHA-DT-04's terminal
    journal at that drawing's finished limits, and the diametral clearance
    the two bands give, which is the retention float the collar is sized on."""
    shaft = _config.parts("dt-cone-gear-shaft")["number"]
    land_low, land_high = lands.TERMINAL_FINISHED_DIA_LIMITS_MM
    bore_low, bore_high = spec.BORE_FINISHED_DIA_LIMITS_MM
    assert shaft == "MHA-DT-04"
    assert (bore_low - land_high, bore_high - land_low) == pytest.approx(
        (2.0 * lands.TIP_COLLAR_MIN_RADIAL_FLOAT_MM, 2.0 * lands.TIP_COLLAR_MAX_RADIAL_FLOAT_MM),
        abs=spec._PRINT_GRID_TOL_MM,
    )
    lines = spec.INSTALLATION_NOTES.splitlines()
    assert lines[:2] == [
        f"FITS {shaft} TERMINAL JOURNAL \u00d8{land_low:.4f} TO {land_high:.4f};",
        f"DIAMETRAL CLEARANCE {bore_low - land_high:.4f} TO {bore_high - land_low:.4f}.",
    ]
    assert lines[1] == "DIAMETRAL CLEARANCE 0.0254 TO 0.0965."
    assert bore_low - land_high > 0.0
    # The longest line the notes box has printed (the old supply line).
    assert max(map(len, lines)) <= 55


def test_final_stock_set_screw_references_accept_an_unlabelled_native_length(monkeypatch):
    from _supplier_dimensions import _presentation

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "_sheet_notes", lambda *_args: {"title": ("", object())})
    monkeypatch.setattr(drawing, "_note_text", lambda _annotation: spec.SET_SCREW_SUPPLIER_TITLE)
    monkeypatch.setattr(
        drawing, "_is_same_attachment",
        lambda _adapter, actual, expected, _kind: actual is expected,
    )
    views = [
        SimpleNamespace(Name=name, ReferencedConfiguration="SetScrew", displays=[])
        for name in ("side", "end", "iso")
    ]
    for view in views:
        view.GetDisplayDimensions = lambda view=view: tuple(view.displays)
    monkeypatch.setattr(drawing, "_sheet_views", lambda *_args: [object(), *views])
    identities = {}
    owners = {
        name: feature
        for feature, names in spec.SET_SCREW_SUPPLIER_DIMENSIONS.items()
        for name in names
    }
    for name in spec.SET_SCREW_SUPPLIER_SIZES_MM:
        view = views[1] if name == "SocketAF" else views[0]
        entities = (object(), object())
        annotation = SimpleNamespace(
            name=name, Owner=view,
            GetAttachedEntities3=lambda entities=entities: entities,
            GetAttachedEntityTypes=lambda: (1, 1),
        )
        native = SimpleNamespace(
            FullName=f"{name}@{owners[name]}@stock", Tolerance=SimpleNamespace(Type=0),
        )
        display = SimpleNamespace(
            GetAnnotation=lambda annotation=annotation: annotation,
            GetDimension2=lambda _index, native=native: native,
        )
        view.displays.append(display)
        identities[name] = (native.FullName, view.Name, entities, (1, 1))
    checked = {}

    def check_presentation(_adapter, _display, **options):
        # Execute the real presentation validator: an empty callout is invalid,
        # while no below-text is the intended native length presentation.
        options = dict(options)
        options.pop("expected_degrees", None)
        options.setdefault("fraction_denominator", None)
        _presentation(_adapter, **options)
        checked[options["label"]] = options["callout"]

    monkeypatch.setattr(drawing, "assert_supplier_reference_dimension", check_presentation)
    mm_sheet = SimpleNamespace(currentModel=SimpleNamespace(Extension=SimpleNamespace(
        GetUserPreferenceInteger=lambda _preference, _option: 0,  # swMM
    )))
    drawing._assert_stock_references(mm_sheet, {"title"}, identities, {"side", "end", "iso"})
    assert checked == {
        "stock set-screw ScrewLength": None,
        "stock set-screw ScrewMajorDia": spec.SET_SCREW_THREAD,
        "stock set-screw SocketAF": "HEX SOCKET AF",
    }
