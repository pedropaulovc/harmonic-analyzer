"""Offline contracts for the guide-lock drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_guide_lock as lock
import draw_guide_lock as drawing
import guide_lock_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/guide-lock.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/guide-lock.pdf")
    assert drawing.PNG.as_posix().endswith("/png/guide-lock_drawing.png")
    assert DRAWINGS_BY_NAME["guide_lock"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map, and the drawing's view math reads the spec's
    # nominal spans, not a divergent copy.
    assert lock.DRAWING_DIMENSIONS is guide_lock_spec.DRAWING_DIMENSIONS
    marked = set().union(*guide_lock_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.LOCK_WIDTH, drawing.LOCK_HEIGHT) == (
        guide_lock_spec.LOCK_WIDTH,
        guide_lock_spec.LOCK_HEIGHT,
    )
    assert lock.HOLE_XY is guide_lock_spec.HOLE_XY


def test_hole_contract_is_part_owned_and_resolved() -> None:
    spec = guide_lock_spec.HOLE_SPEC
    assert lock.HOLE_SPEC is spec
    assert drawing.HOLE_SPEC is spec
    # R9-49: the fractional 1/8 drill carries both printed hole positions over
    # the screw majors (guide_lock_screw_spec.LOCK_SET_OFFSET).
    assert spec.kind == "drilled_fractional"
    assert spec.size == "1/8"
    assert lock.HOLE_DIA == blind_cut_dia_mm(spec)
    assert drawing.HOLE_R_SHEET == (
        blind_cut_dia_mm(spec) * drawing.SHEET_SCALE[0] / 2000.0
    )


def test_sheet_runs_at_4_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    assert guide_lock_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"


# Title block: .X ±0.8; drilled holes +0.10/-0.
_ONE_PLACE = 0.8
_DRILLED_PLUS = 0.10
_CHAR_WIDTH = 0.00276  # sheet m per character of 3.5-mm note text


def _ligaments(hole_y: float) -> dict[str, float]:
    r_max = (0.125 * 25.4 + _DRILLED_PLUS) / 2.0
    band = 0.035
    xs = [x for x, _ in guide_lock_spec.HOLE_XY]
    return {
        "guide-side edge": hole_y - band - r_max,
        "far edge": (16.0 - 0.50) - hole_y - band - r_max,
        "left edge": min(xs) - band - r_max,
        "right edge": (22.0 - _ONE_PLACE) - max(xs) - band - r_max,
    }


def test_screw_holes_keep_the_ligament_floor_at_the_printed_worst_case() -> None:
    """Review of 19e33c6c2 (blocker): 2.5 from the guide-side edge left 0.81
    of ligament under the largest drilled 1/8 hole.  R9-59 laps the plate 1.0
    past the rail, so the holes stand 3.5 from that edge."""
    assert min(_ligaments(2.5).values()) < 1.0
    (hole_y,) = {y for _, y in guide_lock_spec.HOLE_XY}
    assert hole_y == pytest.approx(3.5)
    worst = _ligaments(hole_y)
    assert min(worst.values()) >= 1.5
    assert guide_lock_spec.HOLE_LIGAMENTS_WORST == pytest.approx(worst)
    assert guide_lock_spec.LOCK_HEIGHT_BAND == (0.0, -0.50)
    assert guide_lock_spec.DRAWING_PRECISION_BY_NAME["Width"] == 1


def test_hole_coordinates_print_from_the_corner_without_a_frame() -> None:
    """Rule 3: no frame on this plate; each hole coordinate prints from the
    plate's corner at .XXX under its own band, and the shared Y once, 2X."""
    holes = guide_lock_spec.DRAWING_DIMENSIONS["ScrewHoles"]
    assert holes == {"Hole1X", "Hole2X", "Hole1Y"} <= set(drawing.FRONT_KEEP)
    assert {guide_lock_spec.DRAWING_PRECISION_BY_NAME[name] for name in holes} == {3}
    assert drawing.DIMENSION_PREFIXES == {"Hole1Y": "2X "}
    assert len({y for _, y in guide_lock_spec.HOLE_XY}) == 1


def test_the_drill_callout_stands_between_the_plate_and_the_right_view() -> None:
    text = f"2X {drawing.HOLE_CALLOUT_PROCESS} Ø3.18 THRU ALL"
    assert text.split()[1] == "DRILL"
    half = len(text) * _CHAR_WIDTH / 2.0
    left, right = (
        drawing.HOLE_CALLOUT_XY[0] - half,
        drawing.HOLE_CALLOUT_XY[0] + half,
    )
    right_view_left = (
        drawing.RIGHT_CENTER[0]
        - guide_lock_spec.LOCK_THICK * drawing.SHEET_SCALE[0] / 2000.0
    )
    assert drawing.RIGHT_EDGE_X < left and right < right_view_left


def test_the_hole_y_text_stays_inside_the_border_and_under_the_plate() -> None:
    x, y = drawing.FRONT_KEEP["Hole1Y"]
    half = len("2X 3.500±0.035") * _CHAR_WIDTH / 2.0
    assert x - 2.0 * half > 0.0127  # right-aligned or centred, inside
    assert y < drawing.BOTTOM_EDGE_Y - 0.004
    assert x + half < drawing.LEFT_EDGE_X  # clear of Hole1X's extension


def test_part_registry_row_carries_the_title_block_facts() -> None:
    """Stock, finish and quantity live in the title block, not in notes."""
    import _config

    spec = _config.parts("guide-lock")
    assert spec["material_specification"]
    assert "black oxide" in str(spec["finish"]).lower()
    assert int(spec["quantity"]) == 4
