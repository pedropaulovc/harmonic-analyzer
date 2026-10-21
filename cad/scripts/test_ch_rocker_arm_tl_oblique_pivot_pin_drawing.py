"""Offline contracts for the oblique trammel's pivot pin (MHA-CH-06-TL-23)."""

from __future__ import annotations

import ast
import asyncio
import inspect
import re
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
    assert spec.COLLAR_HEIGHT == trammel.PIN_COLLAR_HEIGHT == 15.5
    assert spec.COLLAR_HEIGHT == trammel.BEARING_RECESS + trammel.PIN_COLLAR_PROUD
    assert spec.CARRIER_LENGTH == 24.5 > trammel.CARRIER_THICK
    assert spec.CARRIER_LENGTH == spec.CROSS_HOLE_FROM_SEAT + spec.CROSS_HOLE_FROM_END
    assert spec.OVERALL_LENGTH == (
        spec.BEARING_LENGTH + spec.COLLAR_HEIGHT + spec.CARRIER_LENGTH
    )
    assert spec.OVERALL_LENGTH == 62.0
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


def test_inspection_note_stays_on_clear_paper_above_the_title_block() -> None:
    x, y = drawing.STOP_FACE_NOTE_XY
    height = drawing.INSPECTION_NOTE_CHAR_HEIGHT
    rows = spec.STOP_FACE_INSPECTION_NOTE.splitlines()
    right = x + max(map(len, rows)) * height * 0.68
    bottom = y - len(rows) * height * 1.6
    assert height >= 0.0035
    assert x > 0.303 + 0.010  # right of the lower-boss dimension's anchor
    assert right < 0.4191 - 0.003
    assert bottom > 0.065 + 0.003
    assert y + height < drawing.PROFILE_KEEP["LowerBossHeight"][1] - 0.003
