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
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
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


def test_side_view_lengths_baseline_left_and_clear_the_callout_side() -> None:
    lengths = ("SeatLength", "ServicePinStation", "HubLength")
    xs = [drawing.RIGHT_KEEP[name][0] for name in lengths]
    left_edge = drawing.RIGHT_CENTER[0] - geometry.HUB_BARREL_DIA / 2.0 * (
        drawing.VIEW_SCALE[0] / 1000.0
    )
    assert xs == sorted(xs, reverse=True) and xs[0] < left_edge
    assert all(b - a >= 0.010 for a, b in zip(xs[1:], xs[:-1]))
    assert drawing.HOLE_CALLOUT_XY[0] > drawing.RIGHT_CENTER[0]
    assert drawing.RIGHT_KEEP["SeatDia"][1] < drawing.SIDE_BOTTOM
    assert drawing.RIGHT_KEEP["BarrelDia"][1] > drawing.SIDE_TOP


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
    assert "ServicePinStation" in drawing.RIGHT_KEEP
    assert '"*Right", *RIGHT_CENTER' in Path(drawing.__file__).read_text(encoding="utf-8")


def test_centerline_pick_hits_barrel_face_not_the_cross_hole() -> None:
    scale = drawing.VIEW_SCALE[0] / 1000.0
    x, y = drawing.BARREL_FACE_PICK
    barrel_bottom = drawing.SIDE_BOTTOM + geometry.HUB_SEAT_LENGTH * scale
    barrel_top = drawing.SIDE_BOTTOM + geometry.HUB_LENGTH * scale
    assert barrel_bottom < y < barrel_top
    assert abs(x - drawing.RIGHT_CENTER[0]) < geometry.HUB_BARREL_DIA / 2.0 * scale
    hole_x, hole_y = drawing.SERVICE_PIN_CENTER
    hole_r = drawing.SERVICE_PIN_DIA / 2.0 * scale
    assert (x - hole_x) ** 2 + (y - hole_y) ** 2 > hole_r**2


def test_seat_callout_stands_clear_of_the_seat_extension_lines() -> None:
    # ~2.5 mm per character at the sheet's text height; the callout is
    # centred under its value, so its widest line must end left of the
    # seat's left extension line instead of printing across it.
    char_w = 0.0025
    x = drawing.RIGHT_KEEP["SeatDia"][0]
    half = max(len(line) for line in crank_hub_spec.SEAT_CALLOUT.splitlines()) * char_w / 2
    seat_left = drawing.RIGHT_CENTER[0] - geometry.HUB_SEAT_DIA / 2.0 * (
        drawing.VIEW_SCALE[0] / 1000.0
    )
    assert x + half < seat_left
    assert x - half > drawing.FRONT_CENTER[0]
