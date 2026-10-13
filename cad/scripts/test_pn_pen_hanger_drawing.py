"""Offline contracts for the pen hanger and its drawing."""

from __future__ import annotations

import math
import re

import pytest

import draw_pn_pen_hanger as draw
import pn_pen_hanger_spec as spec


def test_hanger_tap_lands_on_the_bar_screw_axis() -> None:
    import build_mg_magnifier_assembly as magnifier
    import build_mg_wheel_bar as bar
    import build_pn_pen_assembly as pen

    assert pen.HANGER_POS == spec.HANGER_POS
    tap_axis = (
        spec.HANGER_POS[0] + spec.SCREW_HOLE_XY[0],
        spec.HANGER_POS[1] + spec.SCREW_HOLE_XY[1],
    )
    bar_axis = (
        magnifier.WHEEL_BAR_X0 + bar.SCREW_HOLE_X,
        magnifier.WHEEL_BAR_Y,
    )
    assert tap_axis == pytest.approx(bar_axis)
    # The strap seats on the bar front face, its top flush with the bar top.
    assert spec.HANGER_POS[2] + spec.STRAP_Z[1] == pytest.approx(magnifier.BAR_FRONT_Z)
    assert spec.HANGER_POS[1] == pytest.approx(
        magnifier.WHEEL_BAR_Y + bar.BAR_SIDE / 2.0
    )
    # Receiver thickness and the rear-entry stock-screw stack are unchanged.
    assert spec.STRAP_Z[1] - spec.STRAP_Z[0] == pytest.approx(3.0)
    assert pen.HANGER_THREAD_PROTRUSION == pytest.approx(0.7)


def test_hanger_thread_envelope_fits_all_four_tapered_strap_edges() -> None:
    point = spec.SCREW_HOLE_XY
    vertices = spec.STRAP_OUTLINE
    # Signed point-to-edge distances in the CCW outline measure the complete
    # circular thread envelope, including the top edge and inclined sides.
    walls = []
    for start, end in zip(vertices, vertices[1:] + vertices[:1]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        distance = (
            dx * (point[1] - start[1]) - dy * (point[0] - start[0])
        ) / math.hypot(dx, dy)
        walls.append(distance - spec.HANGER_SCREW_DIA / 2.0)
    # The top edge governs: 5.0 below it less the #8 major radius.
    assert min(walls) == pytest.approx(5.0 - spec.HANGER_SCREW_DIA / 2.0)
    assert min(walls) == pytest.approx(spec.HANGER_THREAD_STRAP_WALL)


def test_slots_centre_on_the_rod_line_with_a_running_fit() -> None:
    import paper_drive_geom as paper
    import pn_pen_rod_spec as rod

    # Local x 0 is the rod line; local z ROD_AXIS_Z is the rod axis.
    assert spec.HANGER_POS[0] == paper.PEN_ROD_X
    assert spec.HANGER_POS[2] + spec.ROD_AXIS_Z == pytest.approx(paper.PEN_Z_MID)
    rod_max = rod.ROD_SECTION + rod.SECTION_BAND[0]
    rod_min = rod.ROD_SECTION + rod.SECTION_BAND[1]
    narrow = spec.SLOT_WIDTH + spec.SLOT_WIDTH_BAND[1]
    wide = spec.SLOT_WIDTH + spec.SLOT_WIDTH_BAND[0]
    assert narrow - rod_max == pytest.approx(0.05)
    assert wide - rod_min == pytest.approx(0.15)
    # Worst lean between the two slots' outer faces stays under 0.25 deg.
    span = spec.GUIDE_PITCH + spec.GUIDE_PLATE_T
    assert math.degrees(math.atan((wide - rod_min) / span)) < 0.25
    # Slot bottom behind the largest rod's back face at its band's low limit.
    back_face = spec.ROD_AXIS_Z + rod_max / 2.0
    slot_bottom_near = -(spec.SLOT_BOTTOM + spec.SLOT_BOTTOM_BAND[0])
    assert slot_bottom_near - back_face == pytest.approx(0.4)
    # The arms reach past the rod's front face.
    assert spec.ROD_AXIS_Z - rod_max / 2.0 - spec.PLATE_FRONT_Z == pytest.approx(1.5)


def test_strap_foot_stays_above_the_platen() -> None:
    import paper_drive_geom as paper
    import pd_platen_spec as platen

    platen_top = paper.PLATEN_BOTTOM_Y + platen.PLATE_HEIGHT
    foot = spec.HANGER_POS[1] + spec.STRAP_BOT_Y
    assert foot == pytest.approx(spec.GUIDE_SPAN_Y[0])
    assert foot - platen_top >= 2.0


def test_both_guides_engage_the_rod_square_over_the_full_travel() -> None:
    import pn_pen_carriage_geom as carriage

    lower, upper = spec.GUIDE_SPAN_Y
    margin = spec.GUIDE_ENGAGE_MARGIN
    # At the lowest pen the square's top still clears the upper plate's top.
    assert min(carriage.ROD_SQUARE_TOP_Y) >= upper + margin
    # At the highest pen the square's bottom and every carriage rider stay
    # below the lower plate's bottom.
    assert max(carriage.ROD_SQUARE_BOTTOM_Y) <= lower - margin
    assert max(carriage.CARRIAGE_TOP_Y) <= lower - margin


def test_drawing_keeps_exactly_the_marked_dimensions() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(draw.FRONT_KEEP) | set(draw.TOP_KEEP)
    assert not set(draw.FRONT_KEEP) & set(draw.TOP_KEEP)
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    for feature, name in spec.DRAWING_BANDS:
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert name in spec.DIMENSION_CALLOUTS


def test_notes_carry_no_dimensions() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert len([line for line in lines if not line.startswith(" ")]) <= 4
    for line in lines:
        assert not re.search(r"\d\.\d|\+/-|±", line), line
