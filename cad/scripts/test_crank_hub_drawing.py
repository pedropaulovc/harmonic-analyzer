"""Offline release contracts for separate through hub MHA-137."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import crank_hub_geometry as geometry
import crank_hub_spec
import draw_crank_hub as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_outboard_proportions_are_scaled_not_millimetre_literals() -> None:
    scale = geometry.SHAFT_DIA / 1.65
    assert geometry.ARM_WIDTH == pytest.approx(3.14 * scale, abs=0.05)
    assert geometry.HUB_SEAT_DIA == pytest.approx(2.60 * scale, abs=0.02)
    assert geometry.AXIAL_PIN_DIA == pytest.approx(0.59 * scale, abs=0.01)


def test_named_shaft_fit_class_bounds_the_through_bore() -> None:
    shaft_limits = (
        geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[1],
        geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[0],
    )
    bore_limits = (
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[1],
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[0],
    )
    clearances = (bore_limits[0] - shaft_limits[1], bore_limits[1] - shaft_limits[0])
    assert clearances == pytest.approx(
        tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    )


def test_hub_shoulder_and_pin_stations_preserve_removal_topology() -> None:
    assert geometry.HUB_SEAT_LENGTH == geometry.ARM_THICKNESS
    assert geometry.HUB_SHOULDER_STATION < geometry.SERVICE_PIN_STATION
    assert geometry.SERVICE_PIN_STATION < geometry.HUB_LENGTH
    assert geometry.AXIAL_PIN_LENGTH == geometry.ARM_THICKNESS / 2.0


def test_drawing_registry_and_marks_are_complete() -> None:
    assert DRAWINGS_BY_NAME["crank_hub"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-hub.SLDDRW")
    marked = set().union(*crank_hub_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_matched_fit_and_distinct_pins_are_unambiguous() -> None:
    notes = crank_hub_spec.DRAWING_NOTES
    cross_hole = crank_hub_spec.CROSS_HOLE_CALLOUT
    assert "MATCHED ASSEMBLY" in notes
    assert "MHA-138" in notes and "SIX O'CLOCK" in notes
    assert "LIGHT DRIVE FIT" in notes
    # The taper-pin cross-hole names both mates and the fit on its callout.
    assert "MHA-024" in cross_hole and "MHA-026" in cross_hole
    assert "LIGHT DRIVE FIT" in cross_hole
    assert "RADIAL" not in notes
    assert "SHOULDER SEATED" in notes and "FACES FLUSH" in notes
    assert "0.50 MIN HUB WALL" in notes and "AFTER EDGE BREAK" in notes


def test_notes_obey_the_four_line_rule_and_clear_the_title_block() -> None:
    lines = crank_hub_spec.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4
    assert max(len(line) for line in lines) <= 72


def test_side_view_lies_as_in_the_lathe_with_one_outboard_baseline() -> None:
    # Axis horizontal, faced outboard end on the right, seam (+Z) at the bottom.
    assert drawing.OUTBOARD_X > drawing.SHOULDER_X > drawing.INBOARD_X
    assert drawing._sheet_y(geometry.AXIAL_PIN_RADIUS_FROM_AXIS) < drawing.SIDE_CENTER[1]
    assert drawing.END_CENTER[0] > drawing.OUTBOARD_X  # third-angle right view
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    lengths = ("SeatLength", "ServicePinStation", "HubLength")
    rows = [drawing.SIDE_KEEP[name][1] for name in lengths]
    assert rows == sorted(rows, reverse=True) and rows[0] < drawing.BARREL_BOTTOM
    assert all(upper - lower >= 0.010 for lower, upper in zip(rows[1:], rows[:-1]))


def test_callouts_stand_clear_of_views_and_each_other() -> None:
    # ~2.5 mm per character at the sheet's text height; callout lines are
    # centred on their value, so the widest line sets each block's extent.
    char_w = 0.0025

    def half(text: str) -> float:
        return max(len(line) for line in text.splitlines()) * char_w / 2.0

    seat_x, seat_y = drawing.SIDE_KEEP["SeatDia"]
    seat_half = half(crank_hub_spec.SEAT_CALLOUT)
    seat_block = (seat_x - seat_half, seat_x + seat_half)
    hole_x, hole_y = drawing.HOLE_CALLOUT_XY
    hole_text = f"{crank_hub_spec.CROSS_HOLE_CALLOUT}\n#14 DRILL 0 4.62 THRU ALL"
    hole_block = (hole_x - half(hole_text), hole_x + half(hole_text))
    # The cross-hole leader rises from the hole's top rim to the block's
    # right end; the seat callout must start right of that leader.
    assert hole_block[1] < drawing.SERVICE_PIN_TOP_RIM[0] < seat_block[0]
    assert seat_y - 4 * 0.006 > drawing.BARREL_TOP
    assert hole_y - 5 * 0.006 > drawing.BARREL_TOP
    end_left = drawing.END_CENTER[0] - geometry.HUB_BARREL_DIA / 2.0 * drawing._S
    bore_x, bore_y = drawing.END_KEEP["BoreDia"]
    assert bore_x - half(crank_hub_spec.BORE_CALLOUT) > drawing.OUTBOARD_X
    assert bore_y < drawing.END_CENTER[1] - geometry.HUB_BARREL_DIA / 2.0 * drawing._S
    assert seat_block[1] < drawing.ISO_NOTE_XY[0] and end_left > drawing.OUTBOARD_X
    assert drawing.SIDE_KEEP["BarrelDia"][0] < drawing.INBOARD_X


def test_station_reference_sketch_lies_in_the_side_view_plane() -> None:
    # A standalone reference sketch imports its dimension natively only on the
    # plane of the view that prints it; on Front, the *Right side view got the
    # sketch but no ServicePinStation (run 20260922T020620997Z-4a7ef16e).
    source = Path(drawing.__file__).with_name("build_crank_hub.py").read_text(
        encoding="utf-8"
    )
    head = source[: source.index('name_last_feature(adapter, "ServicePinStationReference")')]
    last_sketch = head[head.rindex("create_sketch(") :].split(")", 1)[0]
    assert last_sketch == 'create_sketch("Right"'
    assert "ServicePinStation" in drawing.SIDE_KEEP
    assert '"*Right", *SIDE_CENTER' in Path(drawing.__file__).read_text(encoding="utf-8")


def test_centerline_pick_hits_barrel_face_not_the_cross_hole() -> None:
    x, y = drawing.BARREL_FACE_PICK
    assert drawing.INBOARD_X < x < drawing.SHOULDER_X
    assert drawing.BARREL_BOTTOM < y < drawing.BARREL_TOP
    hole_x, hole_y = drawing.SERVICE_PIN_CENTER
    hole_r = drawing.SERVICE_PIN_DIA / 2.0 * drawing._S
    assert (x - hole_x) ** 2 + (y - hole_y) ** 2 > hole_r**2
