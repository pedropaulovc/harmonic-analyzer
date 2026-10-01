"""Offline contracts for the transgear drive collar (MHA-177) and its drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_transgear_drive_collar as part
import draw_transgear_drive_collar as drawing
import transgear_collar_cross_pin_spec as cross_pin
import transgear_drive_collar_spec as spec
import transgear_knob_shaft_spec as shaft
import transgear_removable_spec as removable
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _printed_tolerance import printed_band_mm

# Default-format note text, measured on r743-rocker-fix3's render, as
# test_paper_drive_assembly_drawing and test_channel_assembly_drawing use them.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045
BORDER = 0.0127


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-drive-collar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-drive-collar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-drive-collar_drawing.png")
    row = DRAWINGS_BY_NAME["transgear_drive_collar"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert row.artifact_stem == part.PART_NAME
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_prints_in_exactly_one_view() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.SIDE_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS_BELOW) <= set(drawing.END_KEEP)


def test_fits_carry_named_bands_and_the_lengths_print_their_places() -> None:
    assert model_toleranced_dimensions(part) == {
        ("CollarProfile", "CollarDia"): "*deviations(OD_BAND)",
        ("PilotProfile", "PilotDia"): "*deviations(PILOT_DIA_BAND)",
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
        ("SlotProfile", "SlotWidth"): "*deviations(SLOT_WIDTH_BAND)",
        ("SlotProfile", "SlotDepth"): "*deviations(SLOT_DEPTH_BAND)",
        ("PinHoleProfile", "PinPosDia"): "*deviations(PIN_HOLE_BAND)",
        ("PinHoleProfile", "PinPosY"): "PIN_OFFSET_TOL",
        ("PinHoleProfile", "PinNegY"): "PIN_OFFSET_TOL",
    }
    # The seat O.D. and the drive-pin layout are the crank spigot's, so the
    # removable T24 fits either shaft.
    assert spec.OD == removable.SEAT_SPIGOT_DIA
    assert spec.PIN_CIRCLE_RADIUS == removable.PIN_CIRCLE_RADIUS
    assert spec.PIN_HOLE_DIA == removable.DRIVE_PIN_HOLE_DIA
    assert spec.DRAWING_PRECISION_BY_NAME["CollarLength"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosY"] == 3


def test_drive_pin_rim_is_the_seat_shortfall_and_needs_three_place_offsets() -> None:
    # 17.5 / 2 - 7.0 - 2.38 / 2 = 0.56, the seat interface's recorded rim.
    assert spec.DRIVE_PIN_COLLAR_RIM == pytest.approx(removable.SEAT_SPIGOT_RIM)
    # 8.70 - 7.0 - 0.025 - 1.19 = 0.485, printed 0.48.
    assert spec.DRIVE_PIN_COLLAR_RIM_WORST == pytest.approx(0.48)
    assert spec.DRIVE_PIN_COLLAR_RIM_WORST > 0.0
    # Negative control: the offsets at the .XX row (±0.51) leave no rim.
    at_xx = 8.70 - 7.0 - printed_band_mm(2) - 1.19
    assert at_xx <= 1e-9


def test_pilot_wall_worst_and_the_one_decimal_control() -> None:
    # (9.90 - 6.36) / 2 = 1.77.
    assert spec.PILOT_WALL == pytest.approx(1.825)
    assert spec.PILOT_WALL_WORST == pytest.approx(1.77)
    assert spec.PILOT_WALL_WORST >= spec.WALL_FLOOR
    # Negative control: a pilot left at the .X row (-0.8): (9.2 - 6.36) / 2.
    at_x = (spec.PILOT_DIA - printed_band_mm(1) - 6.36) / 2.0
    assert at_x == pytest.approx(1.42)
    assert at_x < spec.WALL_FLOOR


def test_slot_floor_to_front_face_worst_and_the_one_decimal_control() -> None:
    # 3.87 - (1.8 + 0.10) = 1.97.
    assert spec.SLOT_FLOOR_WALL == pytest.approx(2.2)
    assert spec.SLOT_FLOOR_WALL_WORST == pytest.approx(1.97)
    assert spec.SLOT_FLOOR_WALL_WORST >= spec.WALL_FLOOR
    # Negative control: the collar length at the .X row: 3.2 - 1.9 = 1.3.
    at_x = spec.LENGTH - printed_band_mm(1) - 1.9
    assert at_x < spec.WALL_FLOOR


def test_slot_runs_between_the_drive_pins_not_through_them() -> None:
    # Slot along X, pins on ±Y: 7.0 - 0.025 - 1.19 - 0.95 - 0.065 = 4.77.
    assert spec.SLOT_PIN_WALL_WORST == pytest.approx(4.77)
    assert spec.SLOT_PIN_WALL_WORST >= spec.WALL_FLOOR
    # Negative control: a slot cut along the pins' line puts them in it.
    along_pins = 0.0 - 0.025 - 1.19 - 0.95 - 0.065
    assert along_pins < 0.0


def test_drive_pin_holes_clear_the_bore_and_the_pilot() -> None:
    # 7.0 - 0.025 - 1.19 - 3.18 = 2.605 of wall to the bore; the holes'
    # inner edge r 5.785 lies outside the pilot's r 5.0.
    assert spec.BORE_PIN_WALL_WORST == pytest.approx(2.605)
    assert spec.BORE_PIN_WALL_WORST >= spec.WALL_FLOOR
    assert spec.PIN_HOLE_INNER_R_MIN == pytest.approx(5.785)
    assert spec.PIN_HOLE_INNER_R_MIN > spec.PILOT_R_MAX
    # Negative controls: holes on a 6.0 radius break into the pilot; on the
    # pilot's own 5.0 radius they leave 0.605 to the bore.
    assert 6.0 - 0.025 - 1.19 < spec.PILOT_R_MAX
    assert 5.0 - 0.025 - 1.19 - 3.18 < spec.WALL_FLOOR


def test_bore_slides_on_the_core_and_the_pilot_in_the_wheel() -> None:
    # 6.350..6.360 over 6.335..6.345.
    assert spec.BORE_CORE_CLEARANCE == pytest.approx((0.005, 0.025))
    # Radial: (10.3 - 10.0) / 2 and (10.3 + 0.10 - 9.90) / 2.
    assert spec.PILOT_BORE_CLEARANCE == pytest.approx((0.15, 0.25))
    # Negative controls: a press-type bore band binds on the core; a pilot
    # at the wheel's bore size has no air.
    press_bore = spec.BORE_DIA - 0.010 - (shaft.CORE_DIA + max(shaft.CORE_DIA_BAND))
    assert press_bore < 0.0
    assert (removable.BORE_DIA - removable.BORE_DIA) / 2.0 <= 0.0


def test_pilot_stays_behind_the_wheel_front_face() -> None:
    # 2.8 - 1.9 = 0.9; the thinnest plate 2.7 less the pilot at .XX 2.41.
    assert spec.PILOT_FACE_INSET == pytest.approx(0.9)
    assert spec.PILOT_FACE_INSET_WORST == pytest.approx(0.29)
    assert spec.PILOT_FACE_INSET_WORST > 0.0
    # Negative control: the pilot length at the .X row reaches the face.
    assert 2.7 - (spec.PILOT_LENGTH + printed_band_mm(1)) <= 0.0


def test_setting_and_rearward_travel() -> None:
    # The forward travel stops where the cross hole would meet the relief.
    assert spec.SEAT_MAX_FROM_F == pytest.approx(6.90)
    assert spec.SEAT_MAX_FROM_F == pytest.approx(
        spec.SET_NOMINAL + spec.FORWARD_TRAVEL_MAX
    )
    # 6.2 - 4.0 = 2.2; the .XXX length moves it 2.07 .. 2.33.
    assert spec.REARWARD_TRAVEL_NOMINAL == pytest.approx(2.2)
    assert spec.REARWARD_TRAVEL_RANGE == pytest.approx((2.07, 2.33))
    assert min(spec.REARWARD_TRAVEL_RANGE) > 0.0
    # Negative control: a collar as long as the plain core cannot move back.
    assert spec.SET_NOMINAL - shaft.PLAIN_CORE < 0.0


def test_sheet_notes_print_the_floored_worst_walls_then_the_fit_up() -> None:
    notes = spec.DRAWING_NOTES.splitlines()
    assert notes[:3] == [
        f"DRIVE-PIN HOLE TO COLLAR RIM {spec.DRIVE_PIN_COLLAR_RIM_WORST:.2f} MIN.",
        f"PILOT WALL {spec.PILOT_WALL_WORST:.2f} MIN.",
        f"SLOT FLOOR TO FRONT FACE {spec.SLOT_FLOOR_WALL_WORST:.2f} MIN.",
    ]
    # A MIN never rounds up past the arithmetic; control: rounding would.
    assert spec.floor_2(0.489) == pytest.approx(0.48)
    assert round(0.489, 2) > spec.floor_2(0.489)
    assert spec.floor_2(1.97) == pytest.approx(1.97)
    # R9-29: the collar ships unpinned, so its sheet carries the whole fit-up
    # instruction the assembly prints, with the spec's seat maximum and drill.
    assert notes[3:] == spec.FIT_UP_NOTE.splitlines()
    assert f"T24 SEAT {spec.SEAT_MAX_FROM_F:.2f}" in spec.DRAWING_NOTES
    assert (
        f"\u00d8{cross_pin.HOLE_DIA:.1f} +{cross_pin.HOLE_BAND[0]:.2f}/0 THROUGH"
        in spec.CROSS_PIN_DRILL_PHRASE
    )
    flowed = " ".join(spec.FIT_UP_NOTE.split())
    for phrase in (
        spec.FIT_UP_OFFSET_SET_TEXT,
        spec.CROSS_PIN_DRILL_PHRASE,
        spec.STUD_CUT_PHRASE,
    ):
        assert phrase in flowed, phrase


def _notes_box(text: str, left: float, top: float) -> tuple[float, float, float]:
    """(right, bottom, top) of a top-left anchored default-format note."""
    lines = text.splitlines()
    return (
        left + max(map(len, lines)) * NOTE_CHAR_WIDTH,
        top - len(lines) * NOTE_LINE_PITCH,
        top,
    )


def test_the_notes_fit_left_of_the_title_block_and_under_the_views() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    left, top = drawing.NOTES_XY
    right, bottom, top = _notes_box(spec.DRAWING_NOTES, left, top)
    assert left > BORDER and right < template.title_block_left_m
    assert bottom > BORDER
    # The notes stay below both orthographic views' silhouettes.
    assert top < min(drawing.END_CENTER[1], drawing.SIDE_CENTER[1]) - drawing.HALF_OD
    # Negative control: two more fit-up lines run the block into the border.
    _, longer, _ = _notes_box(spec.DRAWING_NOTES + "\nX\nX", left, top)
    assert longer < BORDER


def test_volume_gate_strip_area_is_a_disc_band() -> None:
    radius = spec.OD / 2.0
    assert part._strip_area(radius, radius) == pytest.approx(math.pi * radius**2)
    # The thin-band limit is the chord's rectangle, 2r wide.
    assert part._strip_area(radius, 1e-4) == pytest.approx(
        2.0 * radius * 2e-4, rel=1e-6
    )
    assert 0.0 < part.V_TOTAL < part.V_COLLAR + part.V_PILOT


def test_registry_row_is_the_turned_brass_mha_152() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-177"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = {
        ast.literal_eval(key): getattr(part, value.id)
        for key, value in zip(stamp.args[2].keys, stamp.args[2].values, strict=True)
    }
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
    assert carried["Manufacturing Notes"] == spec.DRAWING_NOTES
    assert carried["Isometric View Note"] == spec.ISOMETRIC_VIEW_NOTE
