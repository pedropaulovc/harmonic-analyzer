"""Offline contracts for the oblique trammel's pivot pin (MHA-CH-06-TL-23)."""

from __future__ import annotations

import inspect
import re
from math import atan, cos, hypot, pi, sin, tan
from types import SimpleNamespace

import pytest

import _config
import _drawing_contract
import _drawing_gdt
import _drawing_layout_audit
import _mcmaster_5972k41 as bearing_catalogue
import build_ch_rocker_arm_tl_oblique_pivot_pin as part
import ch_rocker_arm_tl_oblique_pivot_block_spec as block
import ch_rocker_arm_tl_oblique_pivot_pin_spec as spec
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_pivot_pin as drawing
import export_features
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_leaders import segments_cross
from _fit_deviations import deviations
from _feature_requirements import requirements_for
from _gtol_controls import validate_part_pmi
from _gtol_frame import gtol_frame_signature, gtol_frame_xml
from _layout_audit import arrowhead_segments
from _layout_geometry import (
    Box, Segment, clip_segment_to_box, point_segment_distance,
    segment_box_distance, segment_box_overlap_length,
)
from _printed_limits import drilled_limits, limits
from prechips.model import TOLERANCE_REQUIREMENTS

STEM = "ch_rocker_arm_tl_oblique_pivot_pin"
DASHED = "ch-rocker-arm-tl-oblique-pivot-pin"
_STOP_CONTROL_KEYS = tuple(row.key for row in (*spec.PART_DATUMS, *spec.GEOMETRIC_CONTROLS))


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_section_lengths_derive_from_the_bearing_and_collar_constants() -> None:
    assert spec.BEARING_LENGTH == (
        trammel.BEARINGS_PER_PIN * trammel.BEARING_WIDTH + trammel.BEARING_SHOULDER
    )
    assert spec.BEARING_LENGTH == 22.0
    assert spec.COLLAR_HEIGHT == trammel.PIN_COLLAR_HEIGHT
    assert spec.COLLAR_HEIGHT == trammel.BEARING_RECESS + trammel.PIN_COLLAR_PROUD
    assert spec.CARRIER_LENGTH == 24.5 > trammel.CARRIER_THICK
    assert spec.CARRIER_LENGTH == spec.CROSS_HOLE_FROM_SEAT + spec.CROSS_HOLE_FROM_END
    assert spec.OVERALL_LENGTH == (
        spec.BEARING_LENGTH + spec.COLLAR_HEIGHT + spec.CARRIER_LENGTH
    )
    assert spec.FIT_DIA == trammel.BEARING_BORE


def test_fit_limits_match_the_printed_callouts() -> None:
    k5_low, k5_high = (spec.FIT_DIA + d for d in deviations(spec.BEARING_BAND))
    h6_low, h6_high = (spec.FIT_DIA + d for d in deviations(spec.CARRIER_BAND))
    assert (round(k5_low, 6), round(k5_high, 6)) == (10.001, 10.007)
    assert (round(h6_low, 6), round(h6_high, 6)) == (9.991, 10.0)
    race_low, race_high = (
        bearing_catalogue.BORE + d for d in deviations(bearing_catalogue.BORE_BAND)
    )
    hole_low, hole_high = (spec.FIT_DIA + d for d in deviations(spec.PIN_HOLE_BAND))
    interference = (round(k5_low - race_high, 6), round(k5_high - race_low, 6))
    clearance = (round(hole_low - h6_high, 6), round(hole_high - h6_low, 6))
    assert interference == (0.001, 0.015)
    assert clearance == (0.0, 0.024)
    assert spec.DIMENSION_CALLOUTS["BearingDia"] == spec.BEARING_CALLOUT
    assert spec.DIMENSION_CALLOUTS["CarrierDia"] == spec.CARRIER_CALLOUT
    printed = limits(spec.BEARING_DIA, spec.FIT_PLACES, spec.BEARING_PRINT_BAND)
    assert printed == [round(k5_low, 12), round(k5_high, 12)]


def _mounted_clearance(shaft_interference: float, seat_interference: float) -> float:
    """C3 minimum less NTN's conservative take-up: 70 % of the shaft's
    interference after 7 µm smoothing, 60 % of the seat's."""
    shaft_loss = 0.7 * max(shaft_interference - 0.007, 0.0)
    return trammel.BEARING_RADIAL_PLAY[0] - shaft_loss - 0.6 * seat_interference


def test_presses_leave_the_pivot_free() -> None:
    """Codex (#1578), Main ruling 4: p6 with the N6 seat could preload the
    6200s by 24 µm at their tightest; k5 leaves play at mid-limits and at
    worst a light 12 µm preload."""
    seat = (block.INTERFERENCE_MIN, block.INTERFERENCE_MAX)
    assert seat == (0.002, 0.024)
    shaft = (spec.BEARING_INTERFERENCE_MIN, spec.BEARING_INTERFERENCE_MAX)
    worst = _mounted_clearance(shaft[1], seat[1])
    assert worst == pytest.approx(-0.012, abs=1e-6)
    middle = _mounted_clearance(sum(shaft) / 2.0, sum(seat) / 2.0)
    middle += sum(trammel.BEARING_RADIAL_PLAY) / 2.0 - trammel.BEARING_RADIAL_PLAY[0]
    assert middle > 0.0
    assert _mounted_clearance(0.032, seat[1]) == pytest.approx(-0.0239, abs=1e-6)


def test_mounted_play_stays_inside_the_calculator_bound() -> None:
    # Main ruling 4: the calculator's 0.041 on R is the unmounted bound; at
    # the presses' loosest limits the seat takes 0.0012 off (0.039 on R).
    seat_min = block.INTERFERENCE_MIN
    shaft_min = spec.BEARING_INTERFERENCE_MIN
    loosest = _mounted_clearance(shaft_min, seat_min) + (
        trammel.BEARING_RADIAL_PLAY[1] - trammel.BEARING_RADIAL_PLAY[0]
    )
    assert loosest == pytest.approx(0.0218, abs=1e-6)
    assert loosest <= trammel.BEARING_RADIAL_PLAY[1]
    radius = trammel.RADIUS_PER_SPACING * loosest
    assert f"{radius:.3f}" == "0.039"
    assert radius <= trammel.RADIUS_FROM_BEARING_PLAY


def test_collar_seats_on_the_inner_race_only() -> None:
    assert spec.STOCK_DIA == 38.1
    assert spec.COLLAR_DIA == 12.7 and spec.COLLAR_PLACES == 2
    assert spec.BEARING_DA_MIN <= spec.COLLAR_DIA - 0.51
    assert spec.STOCK_DIA > spec.FLANGE_DIA
    assert spec.SHOULDER_FILLET_RADIUS < spec.BEARING_BORE_CHAMFER_MIN


def test_every_marked_dimension_prints_once() -> None:
    assert set(drawing.PROFILE_KEEP) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set(drawing.PROFILE_KEEP)
    assert set(spec.DIMENSION_CALLOUTS) <= set(drawing.PROFILE_KEEP)
    assert set(spec.CALLOUTS_ABOVE) <= set(drawing.PROFILE_KEEP)


def test_both_narrow_bosses_export_the_same_driven_diameter() -> None:
    # One profile diameter drives both inner-race bosses.
    features = _features()
    assert features["lower_inner_race_boss"]["dia"] == features["collar"]["dia"]
    assert features["lower_inner_race_boss"]["dia_nominal"] == spec.COLLAR_DIA


def test_drilled_cross_hole_keeps_the_analysed_title_block_limits() -> None:
    assert drilled_limits(spec.CROSS_HOLE_DIA, 2) == [5.0, 5.1]
    assert limits(spec.CROSS_HOLE_DIA, 2, spec.CROSS_HOLE_BAND) == [5.0, 5.1]
    assert _features()["clevis_cross_hole"]["dia"] == [5.0, 5.1]


def test_every_exported_band_is_a_requirement() -> None:
    for name, feature in _features().items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list):
                assert key in feature["requirements"], (name, key)


def test_every_exported_nominal_lies_inside_its_band() -> None:
    for name, feature in _features().items():
        for key, nominal in feature.items():
            if not key.endswith("_nominal"):
                continue
            band = feature.get(key.removesuffix("_nominal"))
            if band is None:
                assert "note" in feature["requirements"], (name, key)
                continue
            low, high = band
            assert low <= nominal <= high, (name, key)


def test_every_printed_band_has_a_requirement_owner() -> None:
    owners = {
        "CarrierLength": ("collar_top", "station", None),
        "UpperBossHeight": ("collar", "length", None),
        "BearingLength": ("collar_seat", "station", None),
        "CollarDia": ("collar", "dia", None),
        "BearingDia": ("bearing_section", "dia", spec.BEARING_PRINT_BAND),
        "CarrierDia": ("carrier_section", "dia", spec.CARRIER_BAND),
        "FlangeDia": ("captive_flange", "dia", spec.FLANGE_DIA_BAND),
        "FlangeThick": ("captive_flange", "length", None),
        "CrossHoleDia": ("clevis_cross_hole", "dia", "drilled"),
        "CrossHoleFromEnd": ("clevis_cross_hole", "station", None),
    }
    exempt = {"BottomChamfer", "TopChamfer", "SeatFilletR", "CarrierFilletR", "LowerBossHeight", "PinLength"}
    assert set(owners) | exempt == set(spec.DRAWING_PRECISION_BY_NAME)
    features = _features()
    for printed, (name, key, band) in owners.items():
        feature = features[name]
        assert key in feature["requirements"], printed
        places = spec.DRAWING_PRECISION_BY_NAME[printed]
        nominal = feature[f"{key}_nominal"]
        assert round(nominal, places) == nominal, printed
        expected = drilled_limits(nominal, places) if band == "drilled" else limits(nominal, places, band)
        assert feature[key] == expected, printed
    assert features["bearing_section"]["note"] == spec.BEARING_NOTE
    assert features["carrier_section"]["note"] == spec.CARRIER_NOTE


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts(DASHED)["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-06-TL-23"
    assert _config.parts(DASHED)["quantity"] == 2


def test_finish_fits_one_title_block_line() -> None:
    finish = _config.parts(DASHED)["finish"]
    assert "\n" not in finish and len(finish) <= 40, finish


def test_drawing_script_meets_the_drawing_contract() -> None:
    filename = f"draw_{STEM}.py"
    assert filename in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    violations = _drawing_contract.drawing_specification_violations(
        inspect.getsource(drawing), filename=filename
    )
    assert not violations, violations


def test_captured_flange_and_raised_seat_are_the_actual_pin_profile() -> None:
    assert spec.FLANGE_DIA == 36.0 and spec.FLANGE_THICK == 3.0
    assert spec.FLANGE_DIA_BAND == (0.1, -0.1)
    assert spec.FLANGE_BOTTOM_STATION + trammel.BEARING_RECESS == pytest.approx(24.15)
    assert spec.FLANGE_TOP_STATION - spec.FLANGE_BOTTOM_STATION == 3.0
    assert spec.CARRIER_STATION - spec.FLANGE_TOP_STATION == pytest.approx(spec.UPPER_BOSS_HEIGHT)
    assert spec.UPPER_BOSS_HEIGHT == retention.PIN_UPPER_BOSS_HEIGHT
    assert spec.CARRIER_STATION + trammel.BEARING_RECESS == pytest.approx(
        trammel.PIVOT_BLOCK_HEIGHT + trammel.PIN_COLLAR_PROUD
    )
    assert spec.CROSS_HOLE_STATION - spec.CARRIER_STATION == retention.PIN_CROSS_HOLE_FROM_SEAT
    assert spec.CROSS_HOLE_DIA == 5.0
    assert spec.OVERALL_LENGTH - spec.CROSS_HOLE_STATION == 6.0


def test_carrier_end_lead_has_a_physical_maximum_for_the_cross_hole() -> None:
    assert spec.LEAD_CHAMFER_MAX == spec.LEAD_CHAMFER == 0.5
    end_gap = (
        min(limits(spec.CROSS_HOLE_FROM_END, spec.LENGTH_PLACES))
        - max(limits(spec.CROSS_HOLE_DIA, 2, spec.CROSS_HOLE_BAND)) / 2.0
        - spec.LEAD_CHAMFER_MAX
    )
    assert end_gap == pytest.approx(2.15)
    assert end_gap >= 2.0


def test_total_axial_runout_controls_both_real_faces_from_the_k5_cylinder() -> None:
    assert spec.STOP_FACE_VARIATION_MAX == retention.PIN_STOP_FACE_VARIATION_MAX == 0.05
    assert spec.STOP_FACE_MEASUREMENT_DIAMETER == retention.PIN_STOP_FACE_MEASUREMENT_DIAMETER == 35.0
    validate_part_pmi(spec.PART_DATUMS, spec.GEOMETRIC_CONTROLS)
    (datum,) = spec.PART_DATUMS
    assert datum.letter == "A"
    assert datum.face.diameter_mm == spec.BEARING_DIA == 10.001
    assert datum.face.contains_z_mm == spec.BEARING_LENGTH / 2.0
    assert 0.5 < datum.face.contains_z_mm < spec.BEARING_LENGTH
    declarations = requirements_for(drawing)
    exported = _features()
    assert exported["bearing_section"]["datum"] == datum.letter
    controls = {row.key: row for row in spec.GEOMETRIC_CONTROLS}
    assert set(controls) == set(drawing.STOP_FACE_FRAME_XY) == {
        "flange_lower_stop", "flange_upper_stop",
    }
    for name, normal, station in (
        ("flange_lower_stop", (0.0, 0.0, -1.0), spec.FLANGE_BOTTOM_STATION),
        ("flange_upper_stop", (0.0, 0.0, 1.0), spec.FLANGE_TOP_STATION),
    ):
        control = controls[name]
        assert control.characteristic == "total_runout"
        assert float(control.tolerance) == 0.05
        assert control.datums == ("A",)
        assert control.tolerance_zone == "linear"
        signature = gtol_frame_signature(control.frame_xml)
        assert signature.characteristic_symbol == "GTOL-TRUN"
        assert signature.tolerance_zone == "linear"
        (face,) = declarations[name].faces
        assert face == control.face
        assert face.normal == normal
        assert face.offset_mm == normal[2] * station
        assert exported[name]["normal"] == list(normal)
        assert exported[name]["plane"] == {
            "frame": "model", "axis": "z", "value": station
        }
    # The complete inspection circle stays on both broad annular stop lands,
    # clear of the narrow bosses and the flange's maximum outside edge break.
    radius = spec.STOP_FACE_MEASUREMENT_DIAMETER / 2.0
    assert spec.COLLAR_DIA / 2.0 + spec.SHOULDER_FILLET_RADIUS < radius
    assert radius < (
        min(limits(spec.FLANGE_DIA, 2, spec.FLANGE_DIA_BAND)) / 2.0
        - spec.FLANGE_EDGE_BREAK_MAX
    )


def test_full_face_runout_strengthens_the_existing_capture_angle(monkeypatch) -> None:
    # Total axial runout bounds one common high/low over the entire face.
    # Thus the difference on the Ø35 subset is <=0.05; for a tilted plane
    # z=x*tan(theta), opposite points differ by 35*tan(theta).
    diameter = spec.STOP_FACE_MEASUREMENT_DIAMETER
    runout = float(spec.GEOMETRIC_CONTROLS[0].tolerance)
    old_angle = atan(retention.PIN_STOP_FACE_VARIATION_MAX / diameter)
    assert diameter * tan(old_angle) == pytest.approx(runout)
    flat_diameter_min = (
        min(limits(spec.FLANGE_DIA, 2, spec.FLANGE_DIA_BAND))
        - 2.0 * spec.FLANGE_EDGE_BREAK_MAX
    )
    assert flat_diameter_min == pytest.approx(35.4)
    assert flat_diameter_min > diameter
    new_planar_angle = atan(runout / flat_diameter_min)
    assert new_planar_angle < old_angle
    bounds = retention.capture_bounds()
    monkeypatch.setattr(retention, "PIN_STOP_FACE_VARIATION_MAX", 0.0)
    square = retention.capture_bounds()
    # The current physical proof charges the same face bias twice as the pin
    # clocks; do not silently replace it with an assembled-bearing/C2 check.
    assert bounds.carrier_motion_tilt - square.carrier_motion_tilt == pytest.approx(2 * old_angle)


def test_full_face_runout_does_not_accept_radial_dish_hidden_by_one_circle() -> None:
    runout = float(spec.GEOMETRIC_CONTROLS[0].tolerance)
    # Axisymmetric dish reads zero TIR at every individual radius. It fails
    # total runout when readings share the required common zero across radii.
    readings_by_radius = ((0.0, 0.0, 0.0, 0.0), (0.06, 0.06, 0.06, 0.06))
    assert all(max(row) - min(row) <= runout for row in readings_by_radius)
    entire_face = [value for row in readings_by_radius for value in row]
    assert max(entire_face) - min(entire_face) > runout


def _nearest_on_journal_generatrix(symbol, axis, landing):
    """Independent perpendicular-foot oracle for a projected straight flank."""
    nx, ny = landing[0] - axis[0], landing[1] - axis[1]
    fraction = ((symbol[0] - landing[0]) * nx + (symbol[1] - landing[1]) * ny) / (
        nx * nx + ny * ny
    )
    return (symbol[0] - fraction * nx, symbol[1] - fraction * ny)


@pytest.mark.parametrize("view_scale", (1.0, 3.0, 7.5))
@pytest.mark.parametrize("angle", (0.0, 0.47, pi / 2.0))
def test_straight_datum_keeps_the_projected_landing_under_view_rotation_and_scale(
    view_scale, angle,
) -> None:
    axis = (0.2465, 0.164)
    radius = spec.BEARING_DIA * view_scale / 2000.0
    landing = (axis[0] + radius * sin(angle), axis[1] - radius * cos(angle))
    symbol = drawing._bearing_datum_symbol_xy(axis, landing)
    assert _nearest_on_journal_generatrix(symbol, axis, landing) == pytest.approx(
        landing, abs=1e-12
    )
    assert hypot(symbol[0] - landing[0], symbol[1] - landing[1]) == pytest.approx(0.004)
    # Normal alignment alone also admits an inward, body-crossing request.
    assert (
        (symbol[0] - landing[0]) * (landing[0] - axis[0])
        + (symbol[1] - landing[1]) * (landing[1] - axis[1])
    ) > 0.0


def test_requested_datum_clear_lane_preserves_the_literal_journal_generatrix() -> None:
    axis = (drawing._x(drawing.BEARING_DATUM_STATION_MM), drawing.PROFILE_CENTER[1])
    landing = (axis[0], axis[1] - spec.BEARING_DIA * drawing._S / 2.0)
    assert landing == pytest.approx((0.2615, 0.1489985), abs=1e-12)
    symbol = drawing._bearing_datum_symbol_xy(axis, landing)
    assert symbol == pytest.approx((0.2615, 0.1449985), abs=1e-12)
    assert _nearest_on_journal_generatrix(symbol, axis, landing) == pytest.approx(
        landing, abs=1e-12
    )


@pytest.fixture
def native_stop_controls(monkeypatch):
    """Distinct source/view topology; native attachment/XML guards stay live.

    Model selection returning the drawing-context counterpart, not the source
    object. The native log proves the identity mismatch, not which face the
    seat returned. Distinct contexts exercise the real pre-insertion guard.
    """
    keys = [row.key for row in (*spec.PART_DATUMS, *spec.GEOMETRIC_CONTROLS)]
    source_faces = {key: object() for key in keys}
    faces = {key: object() for key in keys}
    source_to_view = {source_faces[key]: faces[key] for key in keys}
    neighbour = object()
    state = SimpleNamespace(
        tag=None, frames={}, faces=faces, source_faces=source_faces,
        source_by_view={faces[key]: source_faces[key] for key in keys},
        view_faces=[neighbour, *reversed(tuple(faces.values()))],
        source_pin=object(), unknown_source_ids=set(),
    )
    state.source_by_view[neighbour] = object()
    state.view_pin = SimpleNamespace(GetFaces=lambda: tuple(state.view_faces))

    def selected_face(entity):
        # Model the native source/view remap, not identity across contexts.
        return source_to_view.get(entity, entity)

    def annotation(face, landing, leaders):
        item = SimpleNamespace(face=face, landing=landing, leaders=leaders, dangling=False)
        item.GetName = lambda: "test native annotation"
        item.GetAttachedEntities3 = lambda: (item.face,)
        item.GetAttachedEntityCount3 = lambda: 1
        item.GetAttachedEntityTypes = lambda: (2,)
        item.GetLeaderCount = lambda: item.leaders
        item.IsDangling = lambda: item.dangling
        item.GetLeaderPointsAtIndex = lambda _index: (0.0, 0.0, 0.0, *item.landing, 0.0)
        return item

    def datum(_adapter, _view, **kwargs):
        selected = selected_face(kwargs["entity"])
        expected = _drawing_gdt._expected_pick(
            _adapter, selected, kwargs["entity"], entity_type="FACE",
            what=f"datum {kwargs['datum']}", label=kwargs["label"],
        )
        item = SimpleNamespace(
            letter=kwargs["datum"],
            annotation=annotation(expected, kwargs["leader_attach_xy"], 0),
        )
        item.GetLabel = lambda: item.letter
        item.GetAnnotation = lambda: item.annotation
        state.tag = item
        return item

    def frame(_adapter, _view, **kwargs):
        item = SimpleNamespace(
            xml=gtol_frame_xml(
                kwargs["characteristic"], kwargs["tolerance"],
                datums=kwargs["datums"], diameter=kwargs["diameter"],
            ),
            annotation=annotation(selected_face(kwargs["entity"]), kwargs["leader_attach_xy"], 1),
        )
        item.GetFrameCount = lambda: 1
        item.GetFrame = lambda _index: SimpleNamespace(GetSymbolXml=lambda: item.xml)
        item.GetAnnotation = lambda: item.annotation
        state.frames[kwargs["label"]] = item
        return item

    def identity(item, *_interfaces):
        return item
    monkeypatch.setattr(drawing, "_early_bound", identity)
    monkeypatch.setattr(_drawing_gdt, "_early_bound", identity)
    monkeypatch.setattr(_drawing_gdt._sw_type_info, "early_bound_or_flag", identity)
    monkeypatch.setattr(drawing, "resolve_faces", lambda _model, _requests: source_faces)
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda _adapter, _view, points, **_kwargs: [
            (drawing._x(z * 1000), drawing.PROFILE_CENTER[1] + y * 3)
            for _x, y, z in points
        ],
    )
    monkeypatch.setattr(drawing, "add_datum_feature", datum)
    monkeypatch.setattr(drawing, "add_feature_control_frame", frame)
    monkeypatch.setattr(
        _drawing_layout_audit, "annotation_display",
        lambda _adapter, item: ({"arrows": [(*item.landing, 0.0)]}, []),
    )
    model = SimpleNamespace(
        FeatureByName=lambda name: state.source_pin if name == "Pin" else None,
        Extension=SimpleNamespace(
            GetCorrespondingEntity2=lambda face: state.source_by_view.get(face),
        ),
    )
    profile = SimpleNamespace(
        ReferencedDocument=model,
        GetCorresponding=lambda feature: state.view_pin if feature is state.source_pin else None,
        GetDatumTags=lambda: (state.tag,),
        GetGTols=lambda: tuple(state.frames.values()),
    )
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(
            IsSame=lambda left, right: (
                -1 if id(left) in state.unknown_source_ids else int(left is right)
            ),
        ),
    )
    state.add_controls = lambda: drawing._add_stop_face_controls(adapter, profile)
    state.settled = state.add_controls()
    return state


def test_settled_native_controls_accept_the_two_faces_and_reachable_datum(native_stop_controls) -> None:
    native_stop_controls.settled()


@pytest.mark.parametrize("key", _STOP_CONTROL_KEYS)
@pytest.mark.parametrize("correspondence", ("missing", "neighbour", "unknown"))
def test_native_controls_refuse_faces_without_exact_source_correspondence(
    native_stop_controls, key, correspondence,
) -> None:
    face = native_stop_controls.faces[key]
    if correspondence == "unknown":
        native_stop_controls.unknown_source_ids.add(id(native_stop_controls.source_faces[key]))
    else:
        native_stop_controls.source_by_view[face] = (
            None if correspondence == "missing" else object()
        )
    with pytest.raises(RuntimeError, match="expected one Pin profile-view face"):
        native_stop_controls.add_controls()


@pytest.mark.parametrize("key", _STOP_CONTROL_KEYS)
def test_native_controls_refuse_ambiguous_view_faces(native_stop_controls, key) -> None:
    duplicate = object()
    native_stop_controls.view_faces.append(duplicate)
    native_stop_controls.source_by_view[duplicate] = native_stop_controls.source_faces[key]
    with pytest.raises(RuntimeError, match="exact source face, found 2"):
        native_stop_controls.add_controls()


@pytest.mark.parametrize("feature", ("source_pin", "view_pin"))
def test_native_controls_require_the_actual_pin_feature_in_both_contexts(
    native_stop_controls, feature,
) -> None:
    setattr(native_stop_controls, feature, None)
    with pytest.raises(RuntimeError, match="source has no Pin|Pin has no profile-view"):
        native_stop_controls.add_controls()


@pytest.mark.parametrize("key", _STOP_CONTROL_KEYS)
def test_settled_controls_reprove_source_ownership_after_rebuild(native_stop_controls, key) -> None:
    native_stop_controls.source_by_view[native_stop_controls.faces[key]] = object()
    with pytest.raises(RuntimeError, match="settled face lost its exact source correspondence"):
        native_stop_controls.settled()


@pytest.mark.parametrize("key", ("datum", "flange_lower_stop", "flange_upper_stop"))
def test_settled_native_controls_refuse_wrong_face_attachment(native_stop_controls, key) -> None:
    item = native_stop_controls.tag if key == "datum" else native_stop_controls.frames[key]
    item.annotation.face = object()
    with pytest.raises(RuntimeError, match="lost its face attachment"):
        native_stop_controls.settled()


@pytest.mark.parametrize(
    "characteristic,tolerance,datums,diameter",
    (
        ("circular_runout", "0.05", ("A",), False),
        ("total_runout", "0.5", ("A",), False),
        ("total_runout", "0.05", (), False),
        ("total_runout", "0.05", ("A",), True),
    ),
)
def test_settled_native_controls_refuse_weakened_or_malformed_frames(
    native_stop_controls, characteristic, tolerance, datums, diameter,
) -> None:
    native_stop_controls.frames["flange_lower_stop"].xml = gtol_frame_xml(
        characteristic, tolerance, datums=datums, diameter=diameter,
    )
    with pytest.raises(RuntimeError, match="settled frame changed its control"):
        native_stop_controls.settled()


def test_settled_native_controls_refuse_a_missing_datum(native_stop_controls) -> None:
    native_stop_controls.tag.letter = "B"
    with pytest.raises(RuntimeError, match="no tag prints"):
        native_stop_controls.settled()


def test_settled_native_controls_refuse_a_moved_datum_triangle(native_stop_controls) -> None:
    annotation = native_stop_controls.tag.annotation
    annotation.landing = (annotation.landing[0] + 0.0002, annotation.landing[1])
    with pytest.raises(RuntimeError, match="datum landing moved"):
        native_stop_controls.settled()


@pytest.mark.parametrize("key", ("flange_lower_stop", "flange_upper_stop"))
def test_settled_native_controls_refuse_a_moved_or_lost_live_leader(native_stop_controls, key) -> None:
    annotation = native_stop_controls.frames[key].annotation
    annotation.landing = (annotation.landing[0] + 0.002, annotation.landing[1])
    with pytest.raises(RuntimeError, match="leader attachment moved"):
        native_stop_controls.settled()
    annotation.dangling = True
    with pytest.raises(RuntimeError, match="lost its face attachment"):
        native_stop_controls.settled()


# Actual d349b9930 sheet-metre data: pin-d349-layout.json's PDF ink spans and
# native display lines, recovered with pin-d349-drawing.pdf from worker
# swmaker00000a's 2026-10-21T05:32:39Z leaf. Translations/radial solves below
# are offline placement controls, NOT native after-fix evidence.
_D349_KEEP = {
    "UpperBossHeight": (0.182525, 0.210),
    "LowerBossHeight": (0.303, 0.118),
    "TopChamfer": (0.0785, 0.193),
    "BottomChamfer": (0.2915, 0.193),
    "CrossHoleDia": (0.0735, 0.209),
    "CrossHoleFromEnd": (0.0995, 0.192),
    "BearingDia": (0.2465, 0.101),
}
_D349_ROWS = {
    "upper_clearance": (0.1531055, 0.2081558, 0.2118372, 0.2117212),
    "bottom_lead": (0.2678295, 0.1883777, 0.3150679, 0.191943),
    "top_lead": (0.0548295, 0.1883777, 0.1020679, 0.191943),
    # This report box includes the stroked diameter glyph, not a PDF text span.
    "bearing_size": (0.2545, 0.1057, 0.2896, 0.1094),
    "cross_station": (0.0965801, 0.1901558, 0.1025832, 0.1937211),
    "clevis_pin": (0.0521284, 0.199852, 0.0948623, 0.2034173),
}
_D349_BLOCKS = {
    "UpperBossHeight": (0.1531055, 0.2025996, 0.2118372, 0.2172774),
    "LowerBossHeight": (0.277016, 0.1078214, 0.3288907, 0.1281208),
    "TopChamfer": (0.0548295, 0.1883777, 0.1020679, 0.1974993),
    "BottomChamfer": (0.2678295, 0.1883777, 0.3150679, 0.1974993),
    "CrossHoleDia": (0.0521284, 0.199852, 0.0948623, 0.2190555),
    "BearingDia": (0.2466494, 0.0890739, 0.2976926, 0.1138336),
}
_D349_BEARING_RIGHT = (0.2795, 0.165, 0.2795, 0.2402219)
_D349_PIN_RIGHT = (0.2795, 0.165, 0.2795, 0.2522219)
_D349_CARRIER_LEFT = (0.0905, 0.165, 0.0905, 0.2282219)
_D349_PIN_LEFT = (0.0905, 0.165, 0.0905, 0.2522219)
_D349_CROSS_LEFT = (0.0905, 0.165, 0.0905, 0.1902219)
_D349_CROSS_LEADER = (0.1061282, 0.1711151, 0.0968604, 0.1989181)
_D349_LOWER_LINE = (0.2135, 0.1068875, 0.3291333, 0.1068875)


def _d349_box_at(name, bounds) -> Box:
    x, y = drawing.PROFILE_KEEP[name]
    old_x, old_y = _D349_KEEP[name]
    return Box(
        bounds[0] + x - old_x, bounds[1] + y - old_y,
        bounds[2] + x - old_x, bounds[3] + y - old_y,
    )


def _cross_hole_leader_at(keep) -> Segment:
    """Retain the native elbow-to-text offset and the actual Ø5 circle.

    The bent leader lands on the underline end nearer the hole (the right
    end while the text sat upper-left, the left end now it sits right of the
    hole), and this recomputes its material landing. SolidWorks must still
    prove that route on the rebuilt associated diameter.
    """
    cx, cy, radius = drawing._x(spec.CROSS_HOLE_STATION), drawing.PROFILE_CENTER[1], 0.0075
    side = 1.0 if keep[0] < cx else -1.0
    x, y = keep[0] + side * 0.0233604, keep[1] - 0.0100819
    length = hypot(x - cx, y - cy)
    return Segment(
        cx + radius * (x - cx) / length,
        cy + radius * (y - cy) / length,
        x, y,
    )


# Surviving actual text-on-line records, not one representative union box.
# Names identify source owners; repeated witnesses remain separate findings.
@pytest.mark.parametrize("name,row,line", [
    ("UpperBossHeight", "upper_clearance", (0.164, 0.18, 0.164, 0.2282219)),
    ("UpperBossHeight", "upper_clearance", (0.20555, 0.11, 0.20555, 0.218)),
    ("UpperBossHeight", "upper_clearance", (0.21005, 0.212745, 0.21005, 0.2113783)),
    ("BottomChamfer", "bottom_lead", _D349_BEARING_RIGHT),
    ("BottomChamfer", "bottom_lead", _D349_PIN_RIGHT),
    ("BottomChamfer", "bottom_lead", (0.3398181, 0.2077823, 0.3061598, 0.1883518)),
    ("TopChamfer", "top_lead", _D349_CARRIER_LEFT),
    ("TopChamfer", "top_lead", _D349_PIN_LEFT),
    ("TopChamfer", "top_lead", _D349_CROSS_LEFT),
    ("TopChamfer", "top_lead", _D349_CROSS_LEADER),
    ("BearingDia", "bearing_size", _D349_LOWER_LINE),
    ("CrossHoleFromEnd", "cross_station", _D349_CROSS_LEADER),
    ("CrossHoleDia", "clevis_pin", _D349_CARRIER_LEFT),
    ("CrossHoleDia", "clevis_pin", _D349_PIN_LEFT),
])
def test_d349_text_strikes_clear_the_actual_rows_and_lines(name, row, line) -> None:
    bounds = _D349_ROWS[row]
    assert segment_box_overlap_length(Segment(*line), Box(*bounds)) > 0.0003
    current_line = Segment(*line)
    if line == _D349_CROSS_LEADER:
        current_line = _cross_hole_leader_at(drawing.PROFILE_KEEP["CrossHoleDia"])
    elif line == _D349_LOWER_LINE:
        x, y = drawing.PROFILE_KEEP["LowerBossHeight"]
        current_line = Segment(0.2135, y - 0.0111125, x + 0.0261333, y - 0.0111125)
    assert segment_box_distance(current_line, _d349_box_at(name, bounds)) >= 0.0035


def test_d349_two_text_overlaps_have_separate_complete_blocks() -> None:
    lower_row = Box(0.277016, 0.1130697, 0.3288907, 0.116943)
    bearing_tolerance = Box(0.2755826, 0.1102683, 0.2895825, 0.1138336)
    assert lower_row.overlaps(bearing_tolerance, tol=0.0003)
    top = Box(*_D349_ROWS["top_lead"])
    station = Box(*_D349_ROWS["cross_station"])
    assert top.overlaps(station, tol=0.0003)
    assert _d349_box_at("LowerBossHeight", _D349_BLOCKS["LowerBossHeight"]).gap(
        _d349_box_at("BearingDia", _D349_BLOCKS["BearingDia"])
    ) >= 0.0035
    assert _d349_box_at("TopChamfer", _D349_BLOCKS["TopChamfer"]).gap(
        _d349_box_at("CrossHoleFromEnd", _D349_ROWS["cross_station"])
    ) >= 0.0035


def test_upper_blocks_fit_between_witnesses_with_room_for_their_whole_rows() -> None:
    upper = _d349_box_at("UpperBossHeight", _D349_BLOCKS["UpperBossHeight"])
    lower = _d349_box_at("LowerBossHeight", _D349_BLOCKS["LowerBossHeight"])
    for box, left, right in (
        (upper, 0.0905, 0.164),
        (lower, 0.2135, 0.2795),
    ):
        assert box.xmin - left >= 0.0035
        assert right - box.xmax >= 0.0035
    assert 0.2272219 - upper.ymax >= 0.0035  # carrier-length dimension line


def test_lower_boss_witnesses_stop_above_both_native_radius_leader_runs() -> None:
    radius = (
        Segment(0.2140693, 0.1790023, 0.2117743, 0.1342219),
        Segment(0.2141, 0.1796015, 0.2140693, 0.1790023),
        Segment(0.2117743, 0.1342219, 0.2376382, 0.1342219),
    )
    old_witness = Segment(0.2135, 0.18205, 0.2135, 0.1058875)
    assert segment_box_distance(radius[0], old_witness.box()) == 0.0
    assert segment_box_distance(radius[2], old_witness.box()) == 0.0
    # Keep the material-arc radius exactly where it was proven natively.
    assert drawing.PROFILE_KEEP["SeatFilletR"] == (
        drawing._x(spec.COLLAR_STATION) + 0.012, 0.137
    )
    line_y = drawing.PROFILE_KEEP["LowerBossHeight"][1] - 0.0111125
    assert line_y > 0.18205
    # Include the old starts conservatively; an upward witness's 1 mm overrun
    # goes above the new dimension line, not below it as in the failed sheet.
    for x in (0.21005, 0.2135):
        witness = Segment(x, 0.18205, x, line_y + 0.001)
        for stroke in radius:
            assert segment_box_distance(stroke, witness.box()) >= 0.002


# Complete nearby native display lines from the 20261021T125148010Z pin
# audit. These annotation positions are unchanged; CrossHoleDia's relocated
# full chain is reconstructed separately from its native circle and shelf.
_PIN_NATIVE_NEIGHBOUR_LINES = (
    (0.2145, 0.1489985, 0.2475, 0.1489985),
    (0.2145, 0.1790015, 0.2475, 0.1790015),
    (0.2978139, 0.0911399, 0.2465, 0.0911399),
    (0.2465, 0.0911399, 0.2465, 0.1489985),
    (0.2465, 0.1489985, 0.2465, 0.1790015),
    (0.2795, 0.1765015, 0.2795, 0.1234438),
    (0.278, 0.1780015, 0.278, 0.1234438),
    (0.2795, 0.1244438, 0.3338292, 0.1244438),
    (0.2795, 0.1244438, 0.278, 0.1244438),
    (0.278, 0.1244438, 0.27165, 0.1244438),
    (0.2140693, 0.1790023, 0.2117743, 0.1342219),
    (0.2141, 0.1796015, 0.2140693, 0.1790023),
    (0.2117743, 0.1342219, 0.2376382, 0.1342219),
    (0.20205, 0.11, 0.20655, 0.11),
    (0.20205, 0.218, 0.20655, 0.218),
    (0.2865896, 0.0716962, 0.20555, 0.0716962),
    (0.20555, 0.0716962, 0.20555, 0.11),
    (0.20555, 0.11, 0.20555, 0.218),
    (0.093, 0.149, 0.0955, 0.149),
    (0.093, 0.179, 0.0955, 0.179),
    (0.1571743, 0.0691399, 0.0945, 0.0691399),
    (0.0945, 0.0691399, 0.0945, 0.149),
    (0.0945, 0.149, 0.0945, 0.179),
    (0.165, 0.14495, 0.18, 0.14495),
    (0.165, 0.18305, 0.18, 0.18305),
    (0.198502, 0.1241951, 0.179, 0.1241951),
    (0.179, 0.1241951, 0.179, 0.14495),
    (0.179, 0.14495, 0.179, 0.18305),
    (0.1634971, 0.1478079, 0.1657257, 0.1342219),
    (0.1634, 0.1484, 0.1634971, 0.1478079),
    (0.1657257, 0.1342219, 0.1398618, 0.1342219),
)
_PIN_NATIVE_NEIGHBOUR_ARROWS = (
    (0.2465, 0.1489985, 0.0, 1.0),
    (0.2465, 0.1790015, 0.0, -1.0),
    (0.2795, 0.1244438, 1.0, 0.0),
    (0.278, 0.1244438, -1.0, 0.0),
    (0.2140693, 0.1790023, -0.0511826, -0.9986893),
    (0.20555, 0.11, 0.0, 1.0),
    (0.20555, 0.218, 0.0, -1.0),
    (0.0945, 0.149, 0.0, 1.0),
    (0.0945, 0.179, 0.0, -1.0),
    (0.179, 0.14495, 0.0, 1.0),
    (0.179, 0.18305, 0.0, -1.0),
    (0.1634971, 0.1478079, 0.1618708, -0.986812),
)
# Measured PDF ink plus native stroke-glyph extents, not GetPosition points.
_PIN_NATIVE_NEIGHBOUR_GLYPHS = (
    Box(0.2150795, 0.1351558, 0.2360372, 0.1387211),
    Box(0.1415795, 0.1351558, 0.1625372, 0.1387211),
    Box(0.0945, 0.0691399, 0.1571743, 0.0948336),
    Box(0.179, 0.1241951, 0.198502, 0.1287479),
    Box(0.20555, 0.0716962, 0.2865896, 0.0862774),
    Box(0.3253594, 0.2484082, 0.3837131, 0.2519736),
)


def test_normal_datum_footprint_clears_complete_known_native_dimension_ink() -> None:
    # Native display data from the 20261021T125148010Z pin layout-audit JSON,
    # not just dimension text boxes. The 12 x 9 mm box allowance is deliberately
    # conservative, not an assertion that native glyph/box ink has been seen.
    # Final native triangle, box and literal-landing readbacks must still pass.
    station = drawing.BEARING_DATUM_STATION_MM
    assert spec.LEAD_CHAMFER < station < spec.BEARING_LENGTH - spec.SHOULDER_FILLET_RADIUS
    axis = (drawing._x(station), drawing.PROFILE_CENTER[1])
    landing = (axis[0], axis[1] - spec.BEARING_DIA * drawing._S / 2.0)
    symbol = drawing._bearing_datum_symbol_xy(axis, landing)
    box_allowance = Box(symbol[0] - 0.006, symbol[1] - 0.009, symbol[0] + 0.006, symbol[1])
    footprint = Box(
        box_allowance.xmin, box_allowance.ymin, box_allowance.xmax, landing[1] + 0.0005,
    )
    assert box_allowance.ymax < landing[1]  # box below body; only triangle touches flank
    assert 0.0127 < footprint.xmin < footprint.xmax < 0.4191
    assert 0.0127 < footprint.ymin < footprint.ymax < 0.2667
    for name in ("BearingDia", "BottomChamfer", "LowerBossHeight"):
        assert footprint.gap(_d349_box_at(name, _D349_BLOCKS[name])) >= 0.0035
    for line in _PIN_NATIVE_NEIGHBOUR_LINES:
        assert segment_box_distance(Segment(*line), footprint) >= 0.0035
    # A square of radius equal to the larger native arrow extent covers
    # either size/direction reading (the FCF regression also checks wings).
    for x, y, _dx, _dy in _PIN_NATIVE_NEIGHBOUR_ARROWS:
        arrow_allowance = Box(x - 0.003556, y - 0.003556, x + 0.003556, y + 0.003556)
        assert footprint.gap(arrow_allowance) >= 0.0035
    fillet_text_allowance = Box(0.2133618, 0.1307219, 0.2376382, 0.1377219)
    assert footprint.gap(fillet_text_allowance) >= 0.0035


def test_b9e4_actual_native_stop_leaders_reproduce_the_enforced_crossing() -> None:
    # Actual failing COM primitives from artifact://1284, not idealized
    # tip-to-frame-origin lines. The omitted shoulders cannot erase this.
    crossings = find_leader_leader_crossings([
        LeaderSegment("flange_lower_stop", "gtol", 0.2077, 0.1005, 0.2100, 0.1115),
        LeaderSegment("flange_upper_stop", "gtol", 0.2110, 0.1005, 0.2011, 0.1115),
    ])
    assert len(crossings) == 1
    # The diagnostic rounds its source coordinates and crossing to 0.1 mm.
    assert (crossings[0].x, crossings[0].y) == pytest.approx((0.2083, 0.1035), abs=0.0001)


# The captured knob-shaft 0.050 A frame supplies native 7 mm height,
# 6.35 mm shoulders and font/cell data, NOT the current pin's frame width.
_NATIVE_TRUN_0050_WIDTH = 0.0312764
_ESTIMATED_TRUN_005_WIDTH = _NATIVE_TRUN_0050_WIDTH - 0.0116375 + 0.0090514
# b9e4's rounded elbow plus requested-origin/6.35-shoulder assumptions imply
# about 28.65 +/- 0.05 mm; the native-font estimate is 28.6903 mm. Budget both
# with margin. This is derived, never a measured current pin rectangle.
_PIN_STOP_FRAME_WIDTH_BUDGET = (0.02855, 0.0288)
_PIN_NATIVE_BEARING_GLYPHS = (
    Box(0.2545, 0.1087, 0.2599, 0.1124),  # native stroked diameter glyph
    Box(0.2604673, 0.1087961, 0.2729638, 0.1123614),
    Box(0.2755826, 0.1138796, 0.2778889, 0.1162083),
    Box(0.2782997, 0.1132683, 0.2895825, 0.1168336),
    Box(0.2782997, 0.1087426, 0.2896385, 0.1123079),
    Box(0.2466494, 0.1031864, 0.2976926, 0.1067517),
    Box(0.252277, 0.0976301, 0.2919855, 0.1011954),
    Box(0.2484193, 0.0920739, 0.2960393, 0.0956392),
)


def _projected_pin_body():
    """Full turned-body envelope from the native builder's PinProfile.

    Keep the uncut lead-chamfer envelope and extend each narrow boss over
    its concave R0.2 blend: conservative material, not only annotation ink.
    """
    sections = (
        ("bearing", 0.0, spec.COLLAR_STATION, spec.BEARING_DIA),
        ("lower_boss", spec.COLLAR_STATION - spec.SHOULDER_FILLET_RADIUS,
         spec.FLANGE_BOTTOM_STATION, spec.COLLAR_DIA),
        ("flange", spec.FLANGE_BOTTOM_STATION, spec.FLANGE_TOP_STATION, spec.FLANGE_DIA),
        ("upper_boss", spec.FLANGE_TOP_STATION,
         spec.CARRIER_STATION + spec.SHOULDER_FILLET_RADIUS, spec.COLLAR_DIA),
        ("carrier", spec.CARRIER_STATION, spec.OVERALL_LENGTH, spec.FIT_DIA),
    )
    return {
        name: Box(
            min(drawing._x(lo), drawing._x(hi)),
            drawing.PROFILE_CENTER[1] - dia * drawing._S / 2.0,
            max(drawing._x(lo), drawing._x(hi)),
            drawing.PROFILE_CENTER[1] + dia * drawing._S / 2.0,
        )
        for name, lo, hi, dia in sections
    }


def _stop_control_tip(key):
    row = next(row for row in spec.GEOMETRIC_CONTROLS if row.key == key)
    return (
        drawing._x(row.face.offset_mm / row.face.normal[2]),
        drawing.PROFILE_CENTER[1] - spec.STOP_FACE_MEASUREMENT_DIAMETER * drawing._S / 2.0,
    )


def _body_intrusions(strokes, allowed_tip):
    """Only a zero-length contact at the intended flange-face tip is legal."""
    intrusions = []
    for name, body in _projected_pin_body().items():
        for stroke in strokes:
            span = clip_segment_to_box(stroke, body)
            if span is None:
                continue
            contacts = (stroke.point_at(span[0]), stroke.point_at(span[1]))
            if name == "flange" and all(
                hypot(x - allowed_tip[0], y - allowed_tip[1]) <= 1e-12
                for x, y in contacts
            ):
                continue
            intrusions.append((name, stroke, span))
    return intrusions


def _native_stop_frame_corridors(width, anchors=None):
    """Derived paper envelope, not a simulated native placement response."""
    if anchors is None:
        anchors = drawing.STOP_FACE_FRAME_XY
    frames, leaders, heads = {}, [], {}
    for row in spec.GEOMETRIC_CONTROLS:
        x, y = anchors[row.key]
        frame = Box(x, y - 0.007, x + width, y)
        tip = _stop_control_tip(row.key)
        if tip[0] < frame.xmin:
            start = (frame.xmin, y - 0.0035)
            elbow = (start[0] - 0.00635, start[1])
        else:
            assert tip[0] > frame.xmax
            start = (frame.xmax, y - 0.0035)
            elbow = (start[0] + 0.00635, start[1])
        frames[row.key] = frame
        leaders.extend((
            LeaderSegment(row.key, "gtol", *start, *elbow),
            LeaderSegment(row.key, "gtol", *elbow, *tip),
        ))
        # SDK GetArrowHeadAtIndex2: width ALONG dir; calibrated dir points
        # back toward the shaft. Reuse the actual native/PDF audit decoder,
        # not the older helper's unsupported swapped-axis interpretation.
        heads[row.key] = arrowhead_segments((
            *tip, 0.0, elbow[0] - tip[0], elbow[1] - tip[1], 0.0,
            0.003556, 0.000762, 3.0, 0.0, 0.0, 1.0,
        ))
    return frames, leaders, heads


def _stop_frame_glyphs(frame, width):
    """Native same-font glyph offsets, with 0.15 mm placement/font allowance."""
    x, y = frame.xmin, frame.ymax
    shift = width - _ESTIMATED_TRUN_005_WIDTH
    # Captured PDF 0.050/A spans, native ThreadBlankDia's exact 0.05 span,
    # and native TRUN cell extents. Removing one zero shifts only the A cell.
    return (
        Box(x + 0.0005, y - 0.0065, x + 0.0100, y - 0.0005),
        Box(x + 0.0120712 - 0.00015, y - 0.0053442 - 0.00015,
            x + 0.0207678 + 0.00015, y - 0.0017789 + 0.00015),
        Box(x + 0.0239289 + shift - 0.00015, y - 0.0052649 - 0.00015,
            x + 0.0271564 + shift + 0.00015, y - 0.0018629 + 0.00015),
    )


@pytest.mark.parametrize("bad_lower", ((0.213, 0.129), (0.2145, 0.1045)))
def test_projected_body_gate_rejects_lower_routes_entering_before_the_tip(bad_lower) -> None:
    # Both the previously proposed shoulder-through-body lane and the
    # review's below-body shortcut fail; the latter enters the bottom edge
    # before arriving at the right face despite its elbow being below it.
    anchors = {**drawing.STOP_FACE_FRAME_XY, "flange_lower_stop": bad_lower}
    _frames, leaders, _heads = _native_stop_frame_corridors(0.0288, anchors)
    lower = [
        Segment(row.x0, row.y0, row.x1, row.y1)
        for row in leaders if row.label == "flange_lower_stop"
    ]
    assert _body_intrusions(lower, _stop_control_tip("flange_lower_stop"))


@pytest.mark.parametrize("width", _PIN_STOP_FRAME_WIDTH_BUDGET)
def test_full_stop_routes_touch_the_complete_projected_body_only_at_their_tips(width) -> None:
    frames, leaders, heads = _native_stop_frame_corridors(width)
    assert find_leader_leader_crossings(leaders) == []
    for frame in frames.values():
        for body in _projected_pin_body().values():
            assert frame.gap(body) >= 0.0035
    for key in frames:
        tip = _stop_control_tip(key)
        route = [
            Segment(row.x0, row.y0, row.x1, row.y1)
            for row in leaders if row.label == key
        ]
        # Explicit face halfspaces supplement full-profile clipping: neither
        # a below-flange elbow nor a correct final point alone proves a route.
        xs = [x for stroke in route for x in (stroke.x0, stroke.x1)]
        if key == "flange_lower_stop":
            assert min(xs) >= tip[0]
            assert route[-1].x0 - tip[0] >= 0.00015
        else:
            assert max(xs) <= tip[0]
        assert _body_intrusions(route, tip) == []
        assert _body_intrusions(heads[key], tip) == []


@pytest.mark.parametrize("width", _PIN_STOP_FRAME_WIDTH_BUDGET)
def test_full_native_sized_stop_frames_and_bent_leaders_fit_separate_corridors(width) -> None:
    frames, leaders, heads = _native_stop_frame_corridors(width)
    assert find_leader_leader_crossings(leaders) == []
    glyphs = [
        *_PIN_NATIVE_NEIGHBOUR_GLYPHS, *_PIN_NATIVE_BEARING_GLYPHS,
        *(_d349_box_at(name, bounds) for name, bounds in _D349_BLOCKS.items() if name != "BearingDia"),
    ]
    datum_axis = (drawing._x(drawing.BEARING_DATUM_STATION_MM), drawing.PROFILE_CENTER[1])
    datum_landing = (datum_axis[0], datum_axis[1] - spec.BEARING_DIA * drawing._S / 2.0)
    datum_symbol = drawing._bearing_datum_symbol_xy(datum_axis, datum_landing)
    glyphs.append(Box(
        datum_symbol[0] - 0.006, datum_symbol[1] - 0.009,
        datum_symbol[0] + 0.006, datum_landing[1] + 0.0005,
    ))
    lines = [Segment(*line) for line in _PIN_NATIVE_NEIGHBOUR_LINES]
    callout = _cross_hole_leader_at(drawing.PROFILE_KEEP["CrossHoleDia"])
    cx, cy = drawing._x(spec.CROSS_HOLE_STATION), drawing.PROFILE_CENTER[1]
    shelf_direction = 1.0 if drawing.PROFILE_KEEP["CrossHoleDia"][0] > cx else -1.0
    lines.extend((
        callout,
        Segment(2 * cx - callout.x0, 2 * cy - callout.y0, callout.x0, callout.y0),
        Segment(callout.x1, callout.y1, callout.x1 + shelf_direction * 0.0451333, callout.y1),
    ))
    near = (callout.x0, callout.y0)
    arrow_records = (
        *_PIN_NATIVE_NEIGHBOUR_ARROWS,
        (*near, callout.x1 - near[0], callout.y1 - near[1]),
    )
    for x, y, dx, dy in arrow_records:
        lines.extend(arrowhead_segments((
            x, y, 0.0, dx, dy, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0,
        )))
    title_block = Box(0.216, 0.0, 0.4318, 0.066)
    for key, frame in frames.items():
        assert 0.0127 < frame.xmin < frame.xmax < 0.4191
        assert 0.0127 < frame.ymin < frame.ymax < 0.2667
        assert frame.gap(title_block) >= 0.0035
        # A full border must not strike foreign ink. Glyph spacing is a
        # separate, stricter constraint; white cell padding is not printed
        # lettering. No native audit threshold or landing guard is changed.
        for glyph in glyphs:
            assert frame.gap(glyph) >= 0.001
        for line in lines:
            assert segment_box_distance(line, frame) >= 0.001
        for ink in _stop_frame_glyphs(frame, width):
            for glyph in glyphs:
                assert ink.gap(glyph) >= 0.0035
            for line in lines:
                assert segment_box_distance(line, ink) >= 0.002
        for other_key, other in frames.items():
            if other_key != key:
                assert frame.gap(other) >= 0.0035
    for leader in leaders:
        stroke = Segment(leader.x0, leader.y0, leader.x1, leader.y1)
        for key, frame in frames.items():
            if key != leader.label:
                assert segment_box_distance(stroke, frame) >= 0.0035
        for glyph in glyphs:
            assert segment_box_distance(stroke, glyph) >= 0.002
        bend = (leader.x1, leader.y1)
        if bend != _stop_control_tip(leader.label):
            for line in lines:
                assert point_segment_distance(bend, line) >= 0.0035
    all_heads = [head for group in heads.values() for head in group]
    for head in all_heads:
        for frame in frames.values():
            assert segment_box_distance(head, frame) >= 0.002
    for stroke in (*all_heads, *(Segment(row.x0, row.y0, row.x1, row.y1) for row in leaders)):
        for glyph in glyphs:
            assert segment_box_distance(stroke, glyph) >= 0.002
        for line in lines:
            assert not segments_cross(
                ((stroke.x0, stroke.y0), (stroke.x1, stroke.y1)),
                ((line.x0, line.y0), (line.x1, line.y1)),
            )


def test_end_callouts_and_cross_hole_route_have_clear_paper_not_padded_view_boxes() -> None:
    top = _d349_box_at("TopChamfer", _D349_BLOCKS["TopChamfer"])
    bottom = _d349_box_at("BottomChamfer", _D349_BLOCKS["BottomChamfer"])
    # Actual PDF pictorial edge bounds, not the much larger GetOutline padding.
    iso = Box(0.3040883, 0.1705636, 0.4059124, 0.2446753)
    assert top.xmin >= 0.0127 + 0.0035
    assert 0.0905 - top.xmax >= 0.0035
    assert top.ymax <= 0.2667 - 0.0035
    assert bottom.xmin - 0.2795 >= 0.0035
    assert iso.ymin - bottom.ymax >= 0.0035
    top_x, top_y = drawing.PROFILE_KEEP["TopChamfer"]
    shoulder = Segment(top_x - 0.0238292, top_y - 0.0055562, 0.0905, top_y - 0.0055562)
    drill_leader = _cross_hole_leader_at(drawing.PROFILE_KEEP["CrossHoleDia"])
    assert segment_box_distance(drill_leader, shoulder.box()) >= 0.002


# Actual review-resume-88c6d sheet-metre data (input PDF sha256 dd56976a...):
# PDF vector lines and text spans. Every upper-left drill route crossed the
# 6.0 station and top-lead dimension lines (r1.clarity.3, r2.clarity.1,
# r3.clarity.1). Offline placement controls, NOT native after-fix evidence.
_R88_CROSS_KEEP = (0.050, 0.230)
_R88_CROSS_BLOCK = (0.0282, 0.2195, 0.0718, 0.2415)
_R88_CROSS_LEADER = (0.1045, 0.1704, 0.0734, 0.2199)
_R88_STATION_LINE = (0.0841, 0.1892, 0.1148, 0.1892)
_R88_TOP_LEAD_LINE = (0.0869, 0.1874, 0.0984, 0.1874)
_R88_CARRIER_DIA_LINE = (0.0945, 0.0691, 0.0945, 0.1790)
_R88_COLLAR_DIA_LINE = (0.1790, 0.1242, 0.1790, 0.1831)
_R88_CARRIER_FIT_BLOCK = (0.0945, 0.0687, 0.1572, 0.0963)
_R88_CARRIER_FILLET_ROW = (0.1399, 0.1338, 0.1641, 0.1402)
_R88_CARRIER_FILLET_LEADER = (0.1657, 0.1342, 0.1635, 0.1478)
_R88_JOURNAL_BOTTOM_Y = 0.1490


def _r88_cross_block_at(keep) -> Box:
    dx, dy = keep[0] - _R88_CROSS_KEEP[0], keep[1] - _R88_CROSS_KEEP[1]
    x0, y0, x1, y1 = _R88_CROSS_BLOCK
    return Box(x0 + dx, y0 + dy, x1 + dx, y1 + dy)


def test_r88_upper_left_cross_hole_leader_crossed_its_station_and_lead_lines() -> None:
    measured = Segment(*_R88_CROSS_LEADER)
    modelled = _cross_hole_leader_at(_R88_CROSS_KEEP)
    assert hypot(modelled.x1 - measured.x1, modelled.y1 - measured.y1) < 0.0003
    assert hypot(modelled.x0 - measured.x0, modelled.y0 - measured.y0) < 0.0003
    for line in (_R88_STATION_LINE, _R88_TOP_LEAD_LINE):
        assert segment_box_distance(measured, Segment(*line).box()) == 0.0


def test_r88_drill_callout_sits_on_clear_paper_under_the_journal() -> None:
    keep = drawing.PROFILE_KEEP["CrossHoleDia"]
    drill = _r88_cross_block_at(keep)
    assert _R88_JOURNAL_BOTTOM_Y - drill.ymax >= 0.0035
    for neighbour in (_R88_CARRIER_FIT_BLOCK, _R88_CARRIER_FILLET_ROW):
        assert drill.gap(Box(*neighbour)) >= 0.0035
    for line in (_R88_CARRIER_DIA_LINE, _R88_COLLAR_DIA_LINE, _R88_CARRIER_FILLET_LEADER):
        assert segment_box_distance(Segment(*line), drill) >= 0.0035
    leader = _cross_hole_leader_at(keep)
    # The leader rises from the block's near (left) underline end into the
    # hole, keeping the native 1.6 mm underline overhang clear of the text.
    assert leader.x1 < drill.xmin
    assert segment_box_distance(leader, drill) >= 0.0015
    for line in (
        _R88_STATION_LINE,
        _R88_TOP_LEAD_LINE,
        _R88_CARRIER_DIA_LINE,
        _R88_COLLAR_DIA_LINE,
        _R88_CARRIER_FILLET_LEADER,
    ):
        assert segment_box_distance(leader, Segment(*line).box()) >= 0.002
    for box in (_R88_CARRIER_FIT_BLOCK, _R88_CARRIER_FILLET_ROW):
        assert segment_box_distance(leader, Box(*box)) >= 0.0035


def test_fit_stack_uses_measured_native_extents() -> None:
    flange = Box(0.205802, 0.0726301, 0.2864216, 0.0862774)
    old_bearing = Box(*_D349_BLOCKS["BearingDia"])
    assert old_bearing.gap(flange) < 0.0035
    bearing = _d349_box_at("BearingDia", _D349_BLOCKS["BearingDia"])
    assert bearing.gap(flange) >= 0.0035


@pytest.fixture
def native_cross_hole_dimensions(monkeypatch):
    dimensions = {
        name: SimpleNamespace(SystemValue=value / 1000.0, DrivenState=1)
        for name, value in (
            ("CrossEndStation", spec.OVERALL_LENGTH),
            ("CrossHoleFromEnd", spec.CROSS_HOLE_FROM_END),
            ("CrossHoleDia", spec.CROSS_HOLE_DIA),
        )
    }
    monkeypatch.setattr(
        part,
        "_named_dimension",
        lambda _adapter, _feature, name: (None, dimensions[name]),
    )
    return dimensions


def test_cross_hole_geometry_accepts_a_measured_end_and_neutral_drivers(
    native_cross_hole_dimensions,
) -> None:
    part._require_cross_hole_geometry(object())
    # Equation-manager document-unit conversion changes only numerical noise.
    for dimension in native_cross_hole_dimensions.values():
        dimension.SystemValue += 2e-10
    part._require_cross_hole_geometry(object())


@pytest.mark.parametrize("state", (0, 2))
def test_cross_end_must_be_a_reference_without_coercing_native_state(
    native_cross_hole_dimensions, state,
) -> None:
    end = native_cross_hole_dimensions["CrossEndStation"]
    end.DrivenState = state
    with pytest.raises(RuntimeError, match="CrossEndStation@CrossHoleProfile"):
        part._require_cross_hole_geometry(object())
    assert end.DrivenState == state


@pytest.mark.parametrize(
    "name", ("CrossEndStation", "CrossHoleFromEnd", "CrossHoleDia")
)
def test_cross_hole_geometry_rejects_changed_end_offset_or_diameter(
    native_cross_hole_dimensions, name,
) -> None:
    native_cross_hole_dimensions[name].SystemValue += 0.25 / 1000.0
    with pytest.raises(
        RuntimeError, match=re.escape(f"{name}@CrossHoleProfile")
    ):
        part._require_cross_hole_geometry(object())
