"""Offline manufacturing/retention contracts for custom MHA-VN-016."""

from __future__ import annotations

import inspect
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_vn_cone_tip_collar as part
import cone_shaft_land_bands as lands
import draw_vn_cone_tip_collar as drawing
import dt_cone_gear_spec as gears
import vn_cone_tip_collar_spec as spec
import dt_tip_collar_air as air
import _native_tip_collar_air as native_air
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _printed_tolerance import printed_band_mm
from _stock_fastener import STOCK_RECIPES
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


def test_terminal_flat_derives_complete_dog_fit_and_position_budget():
    radius_min = (lands.TERMINAL_DIA_MM + lands.RUNNING_DIA_BAND[1]) / 2.0
    needed = lands.TERMINAL_REQUIRED_HALF_CHORD_MM
    cap = radius_min + math.sqrt(radius_min**2 - needed**2)
    assert lands.TERMINAL_FLAT_AF_MM == math.floor(cap * 100.0) / 100.0
    assert lands.TERMINAL_HALF_CHORD_MIN_MM >= needed
    assert 0.0 < lands.TERMINAL_FLAT_OFFSET_MAX_MM < radius_min
    assert lands.TIP_SCREW_THREAD_RADIAL_PLAY_MM == pytest.approx((0.0772 - 0.0728) * 25.4 / 2.0)
    assert lands.TIP_SCREW_DOG_AXIS_OFFSET_MM == pytest.approx(
        (lands.TIP_SCREW_THREAD_RADIAL_PLAY_MM + spec.TAP_POSITION_RADIUS_MM)
        * (1.0 + 2.0 * lands.TIP_SCREW_FREE_PROJECTION_MM / spec.REQUIRED_FULL_ENGAGEMENT_MM),
    )
    assert lands.TIP_SCREW_DOG_ENVELOPE_RADIUS_MM == pytest.approx(
        (spec.DOG_DIA + spec.DOG_DIA_BAND[0] + lands.TIP_SCREW_DOG_TOTAL_RUNOUT_MM) / 2.0,
    )
    assert spec.SCREW_CONTROLS[0].characteristic == "total_runout"
    assert spec.SCREW_CONTROLS[0].datums == ("D",)
    assert spec.SCREW_CONTROLS[0].tolerance == f"{lands.TIP_SCREW_DOG_TOTAL_RUNOUT_MM:.2f}"
    assert spec.DOG_SIDE_MARGIN_MM > 0.0
    assert spec.DOG_SIDE_MARGIN_MM == pytest.approx(
        lands.TERMINAL_HALF_CHORD_MIN_MM - lands.TERMINAL_REQUIRED_HALF_CHORD_MM
    )


def test_terminal_web_guard_reads_current_cutter_floor(monkeypatch):
    assert gears.TERMINAL_WEB_REQUIREMENTS_MM == {6: 0.62, 12: 2.0}
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


def test_custom_wall_target_uses_loose_printed_bands():
    routine = printed_band_mm(2)
    assert spec.WIDTH_BAND_MM == spec.ROUTINE_BAND_MM == routine
    assert spec.OUTER_DIA < spec.STOCK_DIA
    assert min(spec.WORST_WALLS_MM.values()) >= spec.WALL_TARGET_MM >= spec.WALL_FLOOR_MM
    envelope = spec.THREAD_ENVELOPE_DIA
    assert envelope > spec.SET_SCREW_MAJOR_DIA
    assert spec.WORST_WALLS_MM["tap to south shoulder"] == pytest.approx(
        spec.TAP_STATION - spec.NOSE_LENGTH - routine
        - envelope / 2.0 - spec.EDGE_BREAK - spec.TAP_POSITION_RADIUS_MM,
    )
    assert spec.WORST_WALLS_MM["tap to north face"] == pytest.approx(
        spec.WIDTH - routine - spec.TAP_STATION
        - envelope / 2.0 - spec.EDGE_BREAK - spec.TAP_POSITION_RADIUS_MM,
    )
    assert spec.WORST_WALLS_MM["nose bore to round OD"] == pytest.approx(
        (spec.NOSE_DIA - routine) / 2.0
        - spec.BORE_FINISHED_DIA_LIMITS_MM[1] / 2.0 - 2.0 * spec.EDGE_BREAK,
    )
    assert spec.TAP_STATION == (spec.NOSE_LENGTH + spec.WIDTH) / 2.0
    assert spec.WORST_WALLS_MM["tap to flat side rims"] == pytest.approx(
        math.sqrt(((spec.OUTER_DIA - routine) / 2.0)**2 - (spec.FLAT_DISTANCE + routine)**2)
        - envelope / 2.0 - spec.EDGE_BREAK - spec.TAP_POSITION_RADIUS_MM,
    )


def test_full_thread_counts_male_and_female_incomplete_ends():
    assert spec.SET_SCREW_HOLE.kind == "tapped"
    assert spec.SET_SCREW_HOLE.size == spec.SET_SCREW_THREAD
    assert spec.SET_SCREW_HOLE.depth_mm == spec.TAP_DRILL_DEPTH
    assert spec.SET_SCREW_HOLE.overrides_mm["ThreadDepth"] == spec.TAP_FULL_DEPTH
    assert spec.TAP_DRILL_DEPTH > spec.TAP_FULL_DEPTH
    bore_max = spec.BORE_FINISHED_DIA_LIMITS_MM[1]
    land_min = lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0]
    float_max = (bore_max - land_min) / 2.0
    flat_max = lands.TERMINAL_FLAT_AF_MM + lands.FLAT_AF_BAND[0] - land_min / 2.0
    male_start = (
        flat_max + float_max + spec.DOG_LENGTH + spec.ROUTINE_BAND_MM + spec.SET_SCREW_PITCH
        + lands.TIP_SCREW_MAJOR_AXIAL_PROJECTION_MM + lands.TIP_SCREW_DOG_AXIAL_PROJECTION_MM
    )
    female_start = spec.FLAT_DISTANCE + 2.0 * spec.ROUTINE_BAND_MM - spec.TAP_FULL_DEPTH + spec.SET_SCREW_PITCH
    female_end = spec.FLAT_DISTANCE - spec.ROUTINE_BAND_MM - spec.EDGE_BREAK - spec.SET_SCREW_PITCH
    flat_min = lands.TERMINAL_FLAT_AF_MM + lands.FLAT_AF_BAND[1] - lands.TERMINAL_FINISHED_DIA_LIMITS_MM[1]/2.0
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
    assert spec.WORST_SOCKET_ACCESS_MM > 0.0
    flat_min = lands.TERMINAL_FLAT_AF_MM + lands.FLAT_AF_BAND[1] - lands.TERMINAL_FINISHED_DIA_LIMITS_MM[1]/2.0
    float_max = (spec.BORE_FINISHED_DIA_LIMITS_MM[1]-lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0])/2.0
    expected_access = (
        flat_min - float_max + spec.SET_SCREW_LENGTH - spec.SET_SCREW_LENGTH_BAND_MM
        - spec.FLAT_DISTANCE - spec.ROUTINE_BAND_MM
        - spec._STOCK_AXIAL_PROJECTION_LOSS_MM
    )
    assert spec.WORST_SOCKET_ACCESS_MM == pytest.approx(expected_access)
    assert expected_access - spec.IN / 16.0 <= 0.0  # the verified 1/4-inch screw is too short


def test_ground_dog_remains_wholly_on_the_d_flat():
    assert spec.DOG_SIDE_MARGIN_MM > 0.0
    assert spec.DOG_LENGTH > spec.ROUTINE_BAND_MM
    assert spec.DOG_DIA + spec.DOG_DIA_BAND[1] > 2.0 * spec.DOG_EDGE_BREAK
    assert spec.DOG_LENGTH - spec.ROUTINE_BAND_MM >= spec._STOCK_POINT_CHAMFER_MAX_MM
    assert spec.ROTATING_ENVELOPE_RADIUS_MM >= (spec.OUTER_DIA + spec.ROUTINE_BAND_MM) / 2.0
    flat_max = lands.TERMINAL_FLAT_AF_MM + lands.FLAT_AF_BAND[0] - lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0]/2.0
    float_max = (spec.BORE_FINISHED_DIA_LIMITS_MM[1]-lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0])/2.0
    assert spec.ROTATING_ENVELOPE_RADIUS_MM >= math.hypot(
        flat_max + float_max + spec.SET_SCREW_LENGTH + spec.SET_SCREW_LENGTH_BAND_MM,
        spec.SET_SCREW_MAJOR_DIA / 2.0,
    )


def test_procurement_is_custom_not_a_relabelled_vendor_collar():
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-VN-016"
    assert row["process"] != "purchased"
    assert row["material"] == part.MATERIAL
    assert "94355A213" in row["stock"]
    assert "18-8" in row["material_specification"]
    assert "supplier_skus" not in row
    assert part.PART_NAME not in FASTENERS
    assert "9414T1" not in STOCK_RECIPES
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


def test_native_marks_and_complete_two_sheet_manufacturing_package():
    sheet = DRAWINGS_BY_NAME["vn_cone_tip_collar"]
    assert drawing.SPEC is sheet
    assert sheet.artifact_stem == part.PART_NAME
    assert sheet.script == Path(drawing.__file__).resolve()
    assert drawing.SHEET_NAMES == ("Collar", "SetScrew")
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert set(spec.DRAWING_DIMENSIONS) == set(spec.DRAWING_PRECISION)
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        assert names == set(spec.DRAWING_PRECISION[feature])
    assert set(drawing.SCREW_KEEP) == {"DogDia", "DogLength"}
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) | set(drawing.BORE_KEEP) == {
        "CollarDia", "NoseDia", "BoreDia", "FlatDistance",
        "CollarWidth", "NoseLength", "ShoulderRadius",
    }
    assert set(drawing.TAP_KEEP) == {"TapStation", "TapRootLimit"}
    assert spec.BORE_DIA * spec.BORE_VIEW_SCALE[0] / spec.BORE_VIEW_SCALE[1] >= 28.0
    assert set(spec.PART_DATUMS) == set(spec.COLLAR_DATUMS + spec.SCREW_DATUMS)
    assert set(spec.GEOMETRIC_CONTROLS) == set(spec.COLLAR_CONTROLS + spec.SCREW_CONTROLS)
    source = inspect.getsource(part)
    assert "wizard_holes" in source and "AddThreadParameters" in source
    assert "apply_drawing_precision" in source
    assert "mark_dimensions_for_drawing" in source
    assert "merge_result=False" in source
    assert "GROUND DOG TIP" in spec.DRAWING_NOTES
    assert len(spec.DRAWING_NOTES.splitlines()) <= 4
    drawing_source = inspect.getsource(drawing)
    assert "add_native_hole_callout" in drawing_source
    assert "assert_imported_precision" in drawing_source
    assert "project_part_pmi" in drawing_source
    assert "author_part_pmi" in source
    assert "build_purchased_fastener_drawing" not in drawing_source
    assert "set_dimension_precision" not in drawing_source
    # Edges stay sharp in the model: the title block covers the collar's
    # breaks, and the dog's tighter limit is printed once on its diameter.
    assert "add_chamfer" not in source
    assert spec.DOG_EDGE_CALLOUT == f"EDGE BREAK {spec.DOG_EDGE_BREAK:.2f} MAX"
    assert '{"DogDia": spec.DOG_EDGE_CALLOUT}' in drawing_source


def test_blind_tap_qualifier_retains_native_depth_variables():
    definitions = {
        5: "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>",
        6: "",
        7: "<MOD-DIAM> <hw-thrutapdrldia> <HOLE-DEPTH> <hw-tapdrldepth>",
        8: "",
    }
    display = SimpleNamespace(
        GetText=lambda part: definitions[part],
        SetText=lambda part, text: definitions.__setitem__(part + 4, text),
    )
    drawing._require_full_thread_callout(display)
    assert definitions[5].endswith("<hw-threaddepth> FULL THREAD")
    assert "<hw-tapdrldepth>" in definitions[7]
    assert drawing.TAP_SCALE == spec.RADIAL_TAP_VIEW_SCALE


def test_radial_tap_position_is_model_owned_and_complete():
    control, = spec.COLLAR_CONTROLS
    assert control.key == "radial_tap_position"
    assert control.characteristic == "position"
    assert control.tolerance_zone == "diametral"
    assert control.datums == ("A", "B", "C")
    assert float(control.tolerance) == spec.TAP_POSITION_DIA_MM
    assert tuple(datum.letter for datum in spec.COLLAR_DATUMS) == control.datums
    assert spec.THREAD_ENVELOPE_DIA == round(spec.THREAD_ENVELOPE_DIA, 2)


@pytest.mark.parametrize("refuse", [False, True])
def test_part_basic_and_max_types_are_authored_and_read_back(monkeypatch, refuse):
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

    tolerances = {name: Tolerance() for name in ("TapStation", "TapRootLimit")}
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
            "TapStation": 1, "TapRootLimit": 6,
        }


def test_drawing_refuses_lost_basic_location_or_root_max_type(monkeypatch):
    annotations = ["TapStation", "TapRootLimit"]
    types = {"TapStation": 1, "TapRootLimit": 6}
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    rows = [SimpleNamespace(
        name=name,
        GetSpecificAnnotation=lambda name=name: SimpleNamespace(
            GetDimension2=lambda _index: SimpleNamespace(Tolerance=SimpleNamespace(Type=types[name])),
        ),
    ) for name in annotations]
    drawing._assert_functional_dimension_types(object(), rows)
    for name in annotations:
        original = types[name]
        types[name] = 0
        with pytest.raises(RuntimeError, match="lost native types"):
            drawing._assert_functional_dimension_types(object(), rows)
        types[name] = original


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
    source = inspect.getsource(part.build)
    assert '"Description": spec.BOM_DESCRIPTION' in source


def test_station_ledger_does_not_double_pay_post_mount_world_vectors():
    import dt_cone_gear_shaft_spec as shaft
    import dt_cone_gear_stack as stack
    import dt_cone_pivot_post_spec as post

    terms = air.station_band_mm()
    assert terms == {
        "post boss half length": printed_band_mm(post.DRAWING_PRECISION_BY_NAME["ConeBossLen"]) / 2.0,
        "shaft integral thrust collar width": shaft.printed_band("CollarWidth"),
        "accepted gear stack terminal north face": -stack.face_band(stack.COUNT - 1, "north")[1],
        "T006 collar feeler set error": air.COLLAR_FEELER_BAND,
    }
    assert not any("mount" in name or "screw float" in name for name in terms)


def test_stepped_air_tiers_include_native_tool_root_and_reworked_screw():
    assert air.PARTITION_STATION_MM == spec.NOSE_LENGTH - spec.SHOULDER_ROOT_RADIUS
    assert {tier.name for tier in air.TIERS} == {"nose", "body", "screw"}
    nose, body, screw = air.TIERS
    assert nose.north_mm == body.south_mm == air.PARTITION_STATION_MM
    assert nose.radius_mm + nose.radius_upper_mm == (spec.NOSE_DIA + spec.ROUTINE_BAND_MM) / 2.0
    assert body.south_lower_mm == -spec.ROUTINE_BAND_MM
    assert body.north_mm + body.north_upper_mm == spec.WIDTH + spec.WIDTH_BAND_MM
    assert screw.south_lower_mm < -spec.TAP_POSITION_RADIUS_MM
    assert screw.radius_mm > spec.SET_SCREW_END_RADIUS


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


def _finite_loaded_case():
    shaft_radius = spec.BORE_DIA / 2.0
    bore_radius = spec.BORE_MODEL_DIA_MM / 2.0
    offset = bore_radius - shaft_radius
    witnesses = tuple(spec.BackArcWitness(
        (-shaft_radius, y, 0.0), (offset-bore_radius, y, 0.0),
        (offset, 0.0, 0.0), (0.0, 1.0, 0.0), shaft_radius, bore_radius,
    ) for y in (spec.EDGE_BREAK+0.00002, spec.WIDTH-spec.EDGE_BREAK-0.00002))
    return {
        "back_arc_witnesses": witnesses,
        "dog_tip_centre_mm": (lands.TERMINAL_FLAT_AF_MM-shaft_radius, spec.TAP_STATION, 0.0),
        "dog_axis_to_socket": (1.0, 0.0, 0.0),
        "dog_radius_mm": spec.DOG_DIA/2.0,
        "flat_offset_mm": lands.TERMINAL_FLAT_AF_MM-shaft_radius,
        "flat_half_chord_mm": math.sqrt(shaft_radius**2-(lands.TERMINAL_FLAT_AF_MM-shaft_radius)**2),
        "flat_axial_limits_mm": (0.0, spec.WIDTH+1.0),
    }


def test_signed_two_ended_clamp_is_not_the_loose_d_envelope():
    record = spec.validate_installed_clamp_pose(**_finite_loaded_case())
    assert all(value > 0.0 for value in record["positive_end_reactions"])
    assert sum(record["positive_end_reactions"]) == pytest.approx(1.0)
    assert all(offset[0] > 0.0 for offset in record["back_arc_offsets_mm"])
    assert record["loaded_radial_float_mm"] < record["loose_d_journal_offset_mm"]
    assert record["whole_dog_side_margin_mm"] > 0.0
    assert record["whole_dog_end_margin_mm"] > 0.0


@pytest.mark.parametrize("failure", ["concentric", "wrong_back", "missing_end", "unseated",
                                      "wrong_force", "whole_side", "whole_end", "nonfinite"])
def test_signed_clamp_refuses_false_seating_and_partial_dog(failure):
    from dataclasses import replace
    values = _finite_loaded_case()
    witnesses = list(values["back_arc_witnesses"])
    if failure == "concentric":
        witnesses = [replace(w, bore_axis_origin_mm=(0.0, 0.0, 0.0)) for w in witnesses]
    elif failure == "wrong_back":
        witnesses = [replace(w, shaft_point_mm=(-w.shaft_point_mm[0], w.shaft_point_mm[1], 0.0)) for w in witnesses]
    elif failure == "missing_end":
        witnesses = witnesses[:1]
    elif failure == "unseated":
        witnesses[1] = replace(witnesses[1], bore_point_mm=(-0.3, witnesses[1].bore_point_mm[1], 0.0))
    elif failure == "wrong_force":
        values["dog_axis_to_socket"] = (-1.0, 0.0, 0.0)
    elif failure == "whole_side":
        values["flat_half_chord_mm"] = values["dog_radius_mm"] + lands.TERMINAL_FLAT_EDGE_BREAK_MAX/2.0
    elif failure == "whole_end":
        values["flat_axial_limits_mm"] = (0.0, spec.TAP_STATION+values["dog_radius_mm"]/2.0)
    else:
        values["dog_tip_centre_mm"] = (math.nan, spec.TAP_STATION, 0.0)
    values["back_arc_witnesses"] = tuple(witnesses)
    with pytest.raises(ValueError):
        spec.validate_installed_clamp_pose(**values)


def test_full_source_air_requires_observed_bank_face_contract():
    with pytest.raises(ValueError, match="bank"):
        air.full_sweep_proof(installed=air.installation_acceptances()[0], bank_thrust=None)


@pytest.mark.parametrize("readback", [None, (0.0,)*4, (math.nan, 0.0, 0.0, 0.0, 0.0)])
def test_native_clamp_refuses_nonfinite_trimmed_face_points(readback):
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


def test_axial_dog_couple_uses_the_actual_back_contact_not_the_shaft_centre():
    values = _finite_loaded_case()
    angle = lands.TIP_SCREW_TO_JOURNAL_MAX_AXIS_ANGLE_RAD/2.0
    values["dog_axis_to_socket"] = (math.cos(angle), math.sin(angle), 0.0)
    result = spec.validate_installed_clamp_pose(**values)
    south, north = (w.shaft_point_mm[1] for w in values["back_arc_witnesses"])
    lever = values["dog_tip_centre_mm"][0] - values["back_arc_witnesses"][0].shaft_point_mm[0]
    expected = ((spec.TAP_STATION-south)-lever*math.tan(angle))/(north-south)
    assert result["positive_end_reactions"][1] == pytest.approx(expected)
    assert lands._LOADED_FORCE_COUPLE_ARM_MM == pytest.approx(
        lands.TERMINAL_FINISHED_DIA_LIMITS_MM[1]*math.tan(lands._LOADED_AXIS_ANGLE_UPPER_RAD),
    )


def test_installed_air_authority_keeps_real_fit_and_axial_material_travel():
    import dt_cone_support_pose as pose
    from cone_stack_end_play import SHAFT_END_PLAY, STACK_FLOAT
    installed, thrust = air.installation_acceptances()
    expected = pose.InstalledSupportMotionAcceptance(
        air.POST_CENTRE_INSPECTION_XYZ_MM, air.CUP_SEATED_NORTH_CENTRE_XYZ_MM,
        air.NORTH_RADIAL_MOTION_MAX_MM, air.TERMINAL_INSPECTION_STATION_MIN_MM,
        SHAFT_END_PLAY[1],
    )
    assert installed == expected
    assert installed.north_radial_motion_max_mm > max(air.CUP_SEATED_NORTH_CENTRE_XYZ_MM)
    assert thrust.face_tir_mm == air.BANK_WORKING_FACE_TIR_MM
    assert thrust.indicated_span_mm == air.BANK_WORKING_TRACE_MIN_MM
    assert STACK_FLOAT[0] > air.TERMINAL_PROBE_DIAMETER_MAX_MM
    terms = air.projection_closure_terms_mm(
        air.TIERS[1], (-1.0, 0.0, 0.0), installed=installed, bank_thrust=thrust,
    )
    assert "retained shaft end-play north material travel" not in terms
    assert terms["correlated north motion and axial material travel"] >= 0.0



def test_selected_motion_limit_and_metrology_flow_through_one_inspection_authority():
    installed, _thrust = air.installation_acceptances()
    assert air.NORTH_RADIAL_MOTION_MAX_MM == pytest.approx(0.480)
    assert installed.north_radial_motion_max_mm == air.NORTH_RADIAL_MOTION_MAX_MM
    assert air.TERMINAL_CENTRE_EXPANDED_UNCERTAINTY_MAX_MM == pytest.approx(0.005)
    assert air.TERMINAL_INDICATOR_RESOLUTION_MAX_MM == pytest.approx(0.001)
    notes = " ".join(air.installation_requirements())
    assert f"rho^2/{installed.north_radial_motion_max_mm:.3f}^2+q/e<=1" in notes
    assert "OBSERVED UPPER PLUS ITS EXPANDED UNCERTAINTY" in notes
    assert "RESOLUTION <=0.001 IS NOT ACCURACY" in notes
    assert "CORRELATED q/e UNCERTAINTY" in notes
    assert "CUP-SEATED UNCERTAINTY FAMILY MUST REMAIN INSIDE THE FIXED BOX" in notes
    assert "CRITICAL RUNNING-BORE/SHAFT-SEAT SETUP ONLY" in notes
    assert "NO COMMODITY RECEIVING OR FULL-P1 TRACKING" in notes


def test_selected_motion_domain_does_not_erase_actual_raw_pivot_transport():
    from dataclasses import replace
    installed, thrust = air.installation_acceptances()
    former = replace(installed, north_radial_motion_max_mm=0.55)
    arguments = (air.TIERS[1], (0.0, 0.0, 1.0), air.DRUM_TIERS[0], 9.725825)
    current_terms = air.projection_closure_terms_mm(
        *arguments, installed=installed, bank_thrust=thrust,
    )
    former_terms = air.projection_closure_terms_mm(
        *arguments, installed=former, bank_thrust=thrust,
    )
    assert current_terms["actual pivot transport remainder"] > 0.0
    assert current_terms["actual pivot transport remainder"] == former_terms["actual pivot transport remainder"]
    assert current_terms["correlated north motion and axial material travel"] < former_terms["correlated north motion and axial material travel"]

@pytest.mark.parametrize("station", [math.nan, air.TERMINAL_INSPECTION_STATION_MIN_MM-0.1,
                                     air.TERMINAL_INSPECTION_STATION_MAX_MM+0.1])
def test_inspection_station_refuses_unobserved_or_inaccessible_back_arc(station):
    with pytest.raises(ValueError, match="inspection station"):
        air.installation_acceptances(terminal_station_mm=station)


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


def test_manufactured_face_grade_cannot_remove_real_running_gear_cock():
    from dt_cone_support_pose import BankThrustAcceptance
    installed, grade = air.installation_acceptances()
    tight = BankThrustAcceptance(grade.face_tir_mm/100.0, grade.indicated_span_mm)
    for tier in air.DRUM_TIERS:
        terms = air.projection_closure_terms_mm(
            air.TIERS[1], (-0.8, 0.0, 0.6), tier, installed=installed, bank_thrust=tight,
        )
        assert terms["drum FULL retained running/face tilted finite-cylinder enclosure"] > 0.0
        assert terms["drum running bore radial fit"] == pytest.approx(
            air.drum.BORE_DIAMETRAL_CLEARANCE_MM[1]/2.0*0.8,
        )


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


def test_manufacturing_bore_datum_uses_the_real_in_band_native_radius():
    source = inspect.getsource(drawing)
    assert '(spec.BORE_MODEL_DIA_MM / 2.0, 1.0, 0.0), "collar bore datum"' in source
    assert '(spec.BORE_DIA / 2.0, 1.0, 0.0), "collar bore datum"' not in source
    builder = inspect.getsource(part.build)
    assert '"InstalledShaftAxis"' in builder
    assert "-spec.INSTALLED_BORE_AXIS_OFFSET_MM" in builder


def test_custom_body_is_smallest_printed_od_retaining_existing_wall_target():
    required = 2.0*max(spec.BODY_RADIUS_REQUIREMENTS_MM.values())+spec.ROUTINE_BAND_MM
    assert spec.OUTER_DIA >= required
    assert spec.OUTER_DIA-0.01 < required
    assert spec.WALL_TARGET_MM == 2.0
    assert spec.WALL_FLOOR_MM == 1.5
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
    assert lands.TERMINAL_FLAT_AF_MM == 0.420


def test_correlated_full_stroke_support_pays_interior_without_independent_maxima():
    from dt_cone_support_pose import correlated_north_motion_support_mm
    assert correlated_north_motion_support_mm(0.20, 1.0, 0.25) == pytest.approx(0.29)
    assert correlated_north_motion_support_mm(0.55, 1.0, 0.25) == pytest.approx(0.55)
    assert correlated_north_motion_support_mm(0.55, -1.0, 0.25) == pytest.approx(0.55)
    assert correlated_north_motion_support_mm(0.480, 1.0, 0.25) == pytest.approx(0.4804)
    assert correlated_north_motion_support_mm(0.480, -1.0, 0.25) == pytest.approx(0.480)
    assert correlated_north_motion_support_mm(0.0, 1.0, 0.25) == pytest.approx(0.25)


def test_full_source_air_rejects_old_tight_all_state_axis_grade():
    from dt_cone_support_pose import InstalledAxisAcceptance
    old_tight_grade = InstalledAxisAcceptance((0.025, 0.025, 0.025), 0.001)
    with pytest.raises(ValueError, match="support-motion"):
        air.full_sweep_proof(installed=old_tight_grade, bank_thrust=air.installation_acceptances()[1])


def test_printed_physical_limits_keep_exact_native_model_and_real_fit_distinct():
    assert lands.TERMINAL_FINISHED_DIA_LIMITS_MM == pytest.approx((0.774, 0.794))
    assert spec.BORE_FINISHED_DIA_LIMITS_MM == pytest.approx((0.819, 0.879))
    assert lands.TERMINAL_DIA_MM == pytest.approx(0.79375)
    assert spec.BORE_MODEL_DIA_MM == pytest.approx(0.84875)
    minimum = (spec.BORE_FINISHED_DIA_LIMITS_MM[0]-lands.TERMINAL_FINISHED_DIA_LIMITS_MM[1])/2.0
    maximum = (spec.BORE_FINISHED_DIA_LIMITS_MM[1]-lands.TERMINAL_FINISHED_DIA_LIMITS_MM[0])/2.0
    assert (minimum, maximum) == pytest.approx((lands.TIP_COLLAR_MIN_RADIAL_FLOAT_MM, lands.TIP_COLLAR_MAX_RADIAL_FLOAT_MM))


def test_actual_printed_maximum_round_sizes_are_not_rejected_as_hidden_model_digits():
    values = _finite_loaded_case()
    r = lands.TERMINAL_FINISHED_DIA_LIMITS_MM[1]/2.0
    R = spec.BORE_FINISHED_DIA_LIMITS_MM[1]/2.0
    gap = R-r
    values["back_arc_witnesses"] = tuple(
        spec.BackArcWitness((-r, y, 0.0), (gap-R, y, 0.0),
                            (gap, 0.0, 0.0), (0.0, 1.0, 0.0), r, R)
        for y in (spec.EDGE_BREAK, spec.WIDTH-spec.EDGE_BREAK)
    )
    a = lands.TERMINAL_FLAT_AF_MM-r
    values["dog_tip_centre_mm"] = (a, spec.TAP_STATION, 0.0)
    values["flat_offset_mm"] = a
    values["flat_half_chord_mm"] = math.sqrt(r*r-a*a)
    result = spec.validate_installed_clamp_pose(**values)
    assert min(result["positive_end_reactions"]) > 0.0


def test_round_readbacks_outside_actual_printed_limits_are_not_masked():
    values = _finite_loaded_case()
    r = lands.TERMINAL_FINISHED_DIA_LIMITS_MM[1]/2.0+0.001
    R = spec.BORE_FINISHED_DIA_LIMITS_MM[1]/2.0+0.001
    gap = R-r
    values["back_arc_witnesses"] = tuple(
        spec.BackArcWitness((-r, y, 0.0), (gap-R, y, 0.0),
                            (gap, 0.0, 0.0), (0.0, 1.0, 0.0), r, R)
        for y in (spec.EDGE_BREAK, spec.WIDTH-spec.EDGE_BREAK)
    )
    a = lands.TERMINAL_FLAT_AF_MM-r
    values["dog_tip_centre_mm"] = (a, spec.TAP_STATION, 0.0)
    values["flat_offset_mm"] = a
    values["flat_half_chord_mm"] = math.sqrt(r*r-a*a)
    with pytest.raises(ValueError, match="finished limits"):
        spec.validate_installed_clamp_pose(**values)


def test_original_journal_span_pays_north_withdrawal_once():
    from cone_stack_end_play import SHAFT_END_PLAY
    import dt_cone_gear_shaft_spec as shaft
    import dt_cone_pivot_post_spec as post
    expected = min(
        post.CONE_BOSS_LENGTH-printed_band_mm(post.DRAWING_PRECISION_BY_NAME["ConeBossLen"])-2.0*shaft.THRUST_EDGE_BREAK_MAX,
        shaft.JOURNAL_END-shaft.printed_band("Sec0End")-shaft.JOURNAL_FREE_END_BREAK_MAX_MM-shaft.THRUST_EDGE_BREAK_MAX-SHAFT_END_PLAY[1],
    )
    assert shaft.JOURNAL_SUPPORT_SPAN_MIN_MM == pytest.approx(expected)


@pytest.mark.parametrize("section,native", [(0, 12.2308), (1, 9.525), (2, 6.35), (3, 3.175), (4, 0.79375)])
def test_all_land_physical_limit_readers_share_native_print_precision(section, native):
    import dt_cone_gear_shaft_spec as shaft
    assert shaft.DRAWING_PRECISION[f"Sec{section}Profile"][f"Sec{section}Dia"] == lands.LAND_DIA_PLACES[section]
    upper, lower = lands.SECTION_DIA_BANDS[section]
    nominal = round(native, lands.LAND_DIA_PLACES[section])
    assert lands.land_finished_dia_limits_mm(native, section) == pytest.approx((nominal+lower, nominal+upper))
    if section:
        assert shaft.DRAWING_PRECISION[f"Sec{section}FlatProfile"][f"Sec{section}AF"] == lands.LAND_AF_PLACES[section]
        af = round(lands.SECTION_FLAT_AF[section], lands.LAND_AF_PLACES[section])
        assert lands.land_finished_af_limits_mm(section) == pytest.approx((af+lands.FLAT_AF_BAND[1], af+lands.FLAT_AF_BAND[0]))
    else:
        with pytest.raises(ValueError, match="no finished across-flat"):
            lands.land_finished_af_limits_mm(section)
