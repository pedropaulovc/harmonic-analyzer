"""Offline contracts for the oblique trammel's pivot pin (MHA-CH-06-TL-23)."""

from __future__ import annotations

import ast
import asyncio
import inspect
import re
from math import hypot
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import _config
import _drawing_contract
import _drawing_marks
import build_ch_rocker_arm_tl_oblique_pivot_pin as part
import ch_rocker_arm_tl_oblique_pivot_block_spec as block
import ch_rocker_arm_tl_oblique_pivot_pin_spec as spec
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_pivot_pin as drawing
import export_features
from _fit_deviations import deviations
from _feature_requirements import requirements_for
from _layout_geometry import Box, Segment, segment_box_distance, segment_box_overlap_length
from _printed_limits import limits
from prechips.model import TOLERANCE_REQUIREMENTS

STEM = "ch_rocker_arm_tl_oblique_pivot_pin"
DASHED = "ch-rocker-arm-tl-oblique-pivot-pin"


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
    race_low, race_high = (spec.FIT_DIA + d for d in deviations(spec.RACE_BORE_BAND))
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
        "CrossHoleDia": ("clevis_cross_hole", "dia", spec.CROSS_HOLE_BAND),
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
        assert feature[key] == limits(nominal, places, band), printed
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


def test_callouts_are_short_below_lane_lines() -> None:
    for name, text in spec.DIMENSION_CALLOUTS.items():
        for line in text.splitlines():
            assert len(line) <= 30, (name, line)


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


def test_both_real_flange_faces_own_the_direct_inspection() -> None:
    assert (
        spec.STOP_FACE_VARIATION_MAX
        == retention.PIN_STOP_FACE_VARIATION_MAX
        == 0.05
    )
    assert (
        spec.STOP_FACE_MEASUREMENT_DIAMETER
        == retention.PIN_STOP_FACE_MEASUREMENT_DIAMETER
        == 35.0
    )
    declarations = requirements_for(drawing)
    exported = _features()
    for name, normal, station in (
        ("flange_lower_stop", (0.0, 0.0, -1.0), spec.FLANGE_BOTTOM_STATION),
        ("flange_upper_stop", (0.0, 0.0, 1.0), spec.FLANGE_TOP_STATION),
    ):
        (face,) = declarations[name].faces
        assert face.normal == normal
        assert face.offset_mm == normal[2] * station
        assert exported[name]["normal"] == list(normal)
        assert exported[name]["plane"] == {
            "frame": "model", "axis": "z", "value": station
        }
        assert exported[name]["requirements"] == ["note"]
        assert exported[name]["note"] == " ".join(
            spec.STOP_FACE_INSPECTION_NOTE.splitlines()
        )
    # The complete inspection circle stays on both broad annular stop lands,
    # clear of the narrow bosses and the flange's maximum outside edge break.
    radius = spec.STOP_FACE_MEASUREMENT_DIAMETER / 2.0
    assert spec.COLLAR_DIA / 2.0 + spec.SHOULDER_FILLET_RADIUS < radius
    assert radius < (
        min(limits(spec.FLANGE_DIA, 2, spec.FLANGE_DIA_BAND)) / 2.0
        - spec.FLANGE_EDGE_BREAK_MAX
    )


def test_native_part_writes_and_guards_the_inspection_property(monkeypatch) -> None:
    """Exercise the actual property-write call without executing geometry."""
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "apply_drawing_properties"
    )
    written = {}
    adapter = object()

    def capture(actual_adapter, properties):
        assert actual_adapter is adapter
        written.update(properties)

    monkeypatch.setattr(_drawing_marks, "apply_custom_properties", capture)
    eval(
        compile(ast.Expression(call), part.__file__, "eval"),
        vars(part),
        {"adapter": adapter},
    )
    assert written["Stop Face Inspection"] == spec.STOP_FACE_INSPECTION_NOTE
    assert "Stop Face Inspection" in part._SAVED_DRAWING_PROPERTIES


def test_drawing_consumes_the_required_native_inspection_property(
    monkeypatch, tmp_path
) -> None:
    source = tmp_path / "pin.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    adapter = SimpleNamespace(currentModel=object(), open_model=AsyncMock())
    read_properties = Mock()
    add_note = Mock()
    monkeypatch.setattr(drawing, "check", lambda _label, result: result)
    monkeypatch.setattr(drawing, "read_required_properties", read_properties)
    monkeypatch.setattr(
        drawing, "new_project_drawing", Mock(return_value=(object(), object()))
    )
    monkeypatch.setattr(drawing, "place_view", Mock(return_value=object()))
    monkeypatch.setattr(drawing, "curate_view_dimensions", Mock(return_value=[]))
    for name in (
        "stamp_drawing_summary",
        "set_hidden_lines_removed",
        "assert_imported_precision",
        "set_dimension_callouts",
        "add_view_centerline",
    ):
        monkeypatch.setattr(drawing, name, Mock())
    monkeypatch.setattr(drawing, "add_property_linked_note", add_note)
    outputs = {"drawing": "pin"}
    monkeypatch.setattr(drawing, "finalize_drawing", AsyncMock(return_value=outputs))
    assert asyncio.run(drawing.build(adapter)) == outputs
    assert "Stop Face Inspection" in read_properties.call_args.kwargs["required"]
    add_note.assert_any_call(
        adapter,
        "Stop Face Inspection",
        *drawing.STOP_FACE_NOTE_XY,
        char_height=drawing.INSPECTION_NOTE_CHAR_HEIGHT,
    )


# Actual d349b9930 sheet-metre data: pin-d349-layout.json's PDF ink spans and
# native display lines, recovered with pin-d349-drawing.pdf from worker
# swmaker00000a's 2026-10-21T05:32:39Z leaf. Translations/radial solves below
# are offline placement controls, NOT native after-fix evidence.
_D349_KEEP = {
    "FlangeThick": (0.20555, 0.229),
    "UpperBossHeight": (0.182525, 0.210),
    "LowerBossHeight": (0.303, 0.118),
    "TopChamfer": (0.0785, 0.193),
    "BottomChamfer": (0.2915, 0.193),
    "CrossHoleDia": (0.0735, 0.209),
    "CrossHoleFromEnd": (0.0995, 0.192),
    "BearingDia": (0.2465, 0.101),
    "Inspection": (0.315, 0.096),
}
_D349_ROWS = {
    "flange_edge_break": (0.180819, 0.2271558, 0.2305377, 0.2307211),
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
    "FlangeThick": (0.180819, 0.2215996, 0.2305377, 0.2362774),
    "LowerBossHeight": (0.277016, 0.1078214, 0.3288907, 0.1281208),
    "TopChamfer": (0.0548295, 0.1883777, 0.1020679, 0.1974993),
    "BottomChamfer": (0.2678295, 0.1883777, 0.3150679, 0.1974993),
    "CrossHoleDia": (0.0521284, 0.199852, 0.0948623, 0.2190555),
    "BearingDia": (0.2466494, 0.0890739, 0.2976926, 0.1138336),
}
_D349_BEARING_LEFT = (0.2135, 0.1800015, 0.2135, 0.2402219)
_D349_BEARING_RIGHT = (0.2795, 0.165, 0.2795, 0.2402219)
_D349_PIN_RIGHT = (0.2795, 0.165, 0.2795, 0.2522219)
_D349_CARRIER_LEFT = (0.0905, 0.165, 0.0905, 0.2282219)
_D349_PIN_LEFT = (0.0905, 0.165, 0.0905, 0.2522219)
_D349_CROSS_LEFT = (0.0905, 0.165, 0.0905, 0.1902219)
_D349_CROSS_LEADER = (0.1061282, 0.1711151, 0.0968604, 0.1989181)
_D349_LOWER_LINE = (0.2135, 0.1068875, 0.3291333, 0.1068875)


def _d349_box_at(name, bounds, *, keep=None) -> Box:
    x, y = drawing.PROFILE_KEEP[name] if keep is None else keep
    old_x, old_y = _D349_KEEP[name]
    return Box(
        bounds[0] + x - old_x, bounds[1] + y - old_y,
        bounds[2] + x - old_x, bounds[3] + y - old_y,
    )


def _cross_hole_leader_at(keep) -> Segment:
    """Retain the native elbow-to-text offset and the actual Ø5 circle.

    Unlike translating the old diagonal, this recomputes its material landing.
    SolidWorks must still prove that route on the rebuilt associated diameter.
    """
    x, y = keep[0] + 0.0233604, keep[1] - 0.0100819
    cx, cy, radius = drawing._x(spec.CROSS_HOLE_STATION), drawing.PROFILE_CENTER[1], 0.0075
    length = hypot(x - cx, y - cy)
    return Segment(
        cx + radius * (x - cx) / length,
        cy + radius * (y - cy) / length,
        x, y,
    )


# All fifteen actual text-on-line records, not one representative union box.
# Names identify source owners; repeated witnesses remain separate findings.
@pytest.mark.parametrize("name,row,line", [
    ("FlangeThick", "flange_edge_break", _D349_BEARING_LEFT),
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
    flange = _d349_box_at("FlangeThick", _D349_BLOCKS["FlangeThick"])
    lower = _d349_box_at("LowerBossHeight", _D349_BLOCKS["LowerBossHeight"])
    for box, left, right in (
        (upper, 0.0905, 0.164),
        (flange, 0.2135, 0.2795),
        (lower, 0.2135, 0.2795),
    ):
        assert box.xmin - left >= 0.0035
        assert right - box.xmax >= 0.0035
    assert 0.2272219 - upper.ymax >= 0.0035  # carrier-length dimension line
    assert 0.2392219 - flange.ymax >= 0.0035  # bearing-length dimension line
    # The old outside-arrow tail crossed X213.5 directly under BOTH STOP FACES.
    # Its intersection is now well left of every row, not merely above/below 3.0.
    assert Box(*_D349_BLOCKS["FlangeThick"]).xmin < 0.2135 < Box(*_D349_BLOCKS["FlangeThick"]).xmax
    flange_line_y = drawing.PROFILE_KEEP["FlangeThick"][1] - 0.0083344
    tail = Segment(0.21005, flange_line_y, 0.2164, flange_line_y)
    assert segment_box_distance(tail, flange) >= 0.0035
    assert flange_line_y - lower.ymax >= 0.0035
    assert flange.gap(lower) >= 0.0035


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


def test_end_callouts_and_cross_hole_route_have_clear_paper_not_padded_view_boxes() -> None:
    top = _d349_box_at("TopChamfer", _D349_BLOCKS["TopChamfer"])
    drill = _d349_box_at("CrossHoleDia", _D349_BLOCKS["CrossHoleDia"])
    bottom = _d349_box_at("BottomChamfer", _D349_BLOCKS["BottomChamfer"])
    # Actual PDF pictorial edge bounds, not the much larger GetOutline padding.
    iso = Box(0.3040883, 0.1705636, 0.4059124, 0.2446753)
    for box in (top, drill):
        assert box.xmin >= 0.0127 + 0.0035
        assert 0.0905 - box.xmax >= 0.0035
        assert box.ymax <= 0.2667 - 0.0035
    assert drill.gap(top) >= 0.0035
    assert bottom.xmin - 0.2795 >= 0.0035
    assert iso.ymin - bottom.ymax >= 0.0035
    # Moving the whole drill callout left rotates its diagonal. Check the whole
    # new diagonal against the unchanged chamfer shoulder, not its old endpoint.
    top_x, top_y = drawing.PROFILE_KEEP["TopChamfer"]
    shoulder = Segment(top_x - 0.0238292, top_y - 0.0055562, 0.0905, top_y - 0.0055562)
    drill_leader = _cross_hole_leader_at(drawing.PROFILE_KEEP["CrossHoleDia"])
    assert segment_box_distance(drill_leader, shoulder.box()) >= 0.002


def test_fit_stack_and_inspection_note_use_measured_native_extents() -> None:
    flange = Box(0.205802, 0.0726301, 0.2864216, 0.0862774)
    old_bearing = Box(*_D349_BLOCKS["BearingDia"])
    assert old_bearing.gap(flange) < 0.0035
    bearing = _d349_box_at("BearingDia", _D349_BLOCKS["BearingDia"])
    assert bearing.gap(flange) >= 0.0035
    # INote.GetExtent includes the complete four rows and glyph bearings.
    extent = (0.3145497, 0.0782227, 0.4222542, 0.0963323)
    assert extent[2] > 0.4191
    note = _d349_box_at("Inspection", extent, keep=drawing.STOP_FACE_NOTE_XY)
    assert drawing.INSPECTION_NOTE_CHAR_HEIGHT >= 0.0035
    assert 0.4191 - note.xmax >= 0.0035
    assert note.ymin - 0.066 >= 0.0035
    assert note.gap(bearing) >= 0.0035


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
