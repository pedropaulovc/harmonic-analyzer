"""Offline contract of the T006 fly cutter as set up (MHA-DT-37-TL-00, #2358)."""

from __future__ import annotations

import math

import pytest

import _buildgraph as bg
import _config
import _dt_cone_tip_gear_tl_cutter_interference as interference
import draw_dt_cone_tip_gear_tl_cutter_assembly as drawing
import dt_cone_tip_gear_spec as tip
import dt_cone_tip_gear_tl_cutter_spec as fixture
import sh_vn_arbor_set_screw_spec as set_screw
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _interference_common import smooth_annulus_limit_mm3
from _machinist_review_mode import MachinistReviewMode

STEM = "dt_cone_tip_gear_tl_cutter"
SHEET_INNER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0, 0.4318, 0.066)


def test_the_fixture_is_a_registered_tooling_kit_outside_the_machine() -> None:
    assert fixture.CONTRACT.number == f"{tip.PART_NUMBER}-TL-00"
    assert STEM in bg.ASSEMBLY_ORDER and bg.is_shop_fixture(STEM)
    assert set(bg.references_of(STEM)) == {
        stem.replace("-", "_") for stem in fixture.BOM_COMPONENTS
    }
    for assembly in bg.ASSEMBLY_ORDER:
        if assembly == STEM:
            continue
        references = bg.references_of(assembly)
        assert "dt_cone_tip_gear_tl_form_cutter" not in references, assembly
        assert "dt_cone_tip_gear_tl_cutter_bar" not in references, assembly
        assert STEM not in references, assembly


def test_the_bit_runs_off_over_both_stems_and_clears_the_bar() -> None:
    # (a) the form never reaches the Ø.0625 stems; (b) the bit plunges its
    # full depth before the bar could touch the blank, at the shortest
    # stick-out the fitter may set.
    assert fixture.RUNOFF_OVER_STEMS > 0.0
    assert fixture.RUNOFF_OVER_STEMS >= tip.CUTTER_RUNOFF_MM - 1e-9
    assert fixture.BAR_CLEARANCE_MIN > 0.5
    assert fixture.STICK_OUT_WINDOW[0] < fixture.STICK_OUT < fixture.STICK_OUT_WINDOW[1]
    assert fixture.PLUNGE_DEPTH < fixture.STICK_OUT_WINDOW[0]


def test_the_trailing_relief_never_rubs_the_cut_at_any_setting() -> None:
    assert fixture.TRAILING_REACH_EXCESS < 0.0
    for stick_out in fixture.STICK_OUT_WINDOW:
        swing = fixture.bar.BAR_RADIUS + stick_out
        assert fixture.bit.trailing_reach_excess_mm(swing) < 0.0


def test_the_bit_tail_stays_inside_the_bar_at_every_setting() -> None:
    low, high = fixture.TAIL_X_RANGE
    assert -fixture.bar.BAR_RADIUS < low < high < 0.0


def test_the_poses_are_proper_rotations_and_the_screw_seats_on_the_bit() -> None:
    for rows in (fixture.BAR_ROWS, fixture.BIT_ROWS, fixture.SET_SCREW_ROWS):
        for i, a in enumerate(rows):
            assert math.isclose(math.hypot(*a), 1.0)
            for b in rows[i + 1 :]:
                assert abs(sum(x * y for x, y in zip(a, b))) < 1e-12
        (a, b, c) = rows
        cross = (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )
        assert cross == pytest.approx(c)
    # The bit's origin is P1, its tip: on the cross-hole axis at the swing
    # radius; the screw's cup end sits on the bit's top.
    assert fixture.BIT_POSITION == pytest.approx(
        (fixture.SWING_RADIUS, fixture.bar.CROSS_HOLE_STATION, 0.0)
    )
    assert fixture.SET_SCREW_POSITION[1] == pytest.approx(
        fixture.bar.CROSS_HOLE_STATION - fixture.bit.BIT_RADIUS
    )


def test_the_only_allowed_overlap_is_the_set_screw_thread_in_its_tap() -> None:
    thread = set_screw.THREAD
    assert interference.SET_SCREW_THREAD == pytest.approx(
        (THREAD_MAJOR_MM[thread], TAP_DRILL_MM[thread], set_screw.LENGTH), abs=1e-3
    )
    assert dict(interference.ALLOWED_PAIRS) == pytest.approx(
        {
            frozenset(
                ("sh-vn-arbor-set-screw-1", "dt-cone-tip-gear-tl-cutter-bar-1")
            ): smooth_annulus_limit_mm3(*interference.SET_SCREW_THREAD)
        }
    )


def test_the_sheet_is_bom_balloons_and_at_most_three_steps() -> None:
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert set(drawing.FRONT_ITEMS) | set(drawing.BOTTOM_ITEMS) == set(
        fixture.BOM_COMPONENTS
    )
    assert sorted(fixture.BOM_ITEMS.values()) == ["1", "2", "3"]
    for stem in fixture.BOM_COMPONENTS:
        assert fixture.QUANTITIES[stem] == 1
        assert _config.parts(stem)["number"]
    steps = [line for line in fixture.ASSEMBLY_STEPS.splitlines() if line[:1].isdigit()]
    assert 1 <= len(steps) <= 3
    # The fitter's setting names the window it is read against.
    assert "STICK-OUT" in fixture.ASSEMBLY_STEPS.upper()


def test_the_references_are_the_spec_values_at_the_spec_places() -> None:
    assert fixture.SWING_RADIUS == pytest.approx(
        fixture.bar.BAR_RADIUS + fixture.STICK_OUT
    )
    assert fixture.DRAWING_PRECISION == {
        fixture.SETTINGS_SKETCH: {
            fixture.STICK_OUT_DIMENSION: 3,
            fixture.SWING_RADIUS_DIMENSION: 3,
        }
    }
    assert (
        set(fixture.DIMENSION_CALLOUTS)
        == fixture.DRAWING_DIMENSIONS[fixture.SETTINGS_SKETCH]
    )
    left, bottom, right, top = SHEET_INNER
    for name, (x, y) in {
        **drawing.SETTINGS_TEXT_XY,
        "bom": drawing.BOM_ANCHOR,
        "steps": drawing.STEPS_XY,
        "iso": drawing.ISO_CENTER,
        "iso note": drawing.ISO_NOTE_XY,
        "bottom view": drawing.BOTTOM_ORIGIN,
    }.items():
        assert left < x < right and bottom < y < top, name
        assert not (TITLE_BLOCK[0] < x and y < TITLE_BLOCK[3]), name
    # The front view's bar stays inside the border.
    assert drawing.FRONT_ORIGIN[1] + fixture.bar.BAR_LENGTH * drawing._S < top


def test_the_settings_chain_runs_from_the_bar_axis_to_p1() -> None:
    """Both references end on the assembly's own settings sketch, never on
    the bit's form edges (equation-curve topology the farm could not find)."""
    axis, surface, tip_point = fixture.SETTINGS_CHAIN
    station = fixture.bar.CROSS_HOLE_STATION
    assert axis == pytest.approx((0.0, station))
    assert surface == pytest.approx((fixture.bar.BAR_RADIUS, station))
    # P1, the bit's origin as placed.
    assert (*tip_point, 0.0) == pytest.approx(fixture.BIT_POSITION)
    assert tip_point[0] - surface[0] == pytest.approx(fixture.STICK_OUT)
    assert tip_point[0] - axis[0] == pytest.approx(fixture.SWING_RADIUS)
    assert drawing.SETTINGS_EXPECTED_MM == {
        fixture.STICK_OUT_DIMENSION: fixture.STICK_OUT,
        fixture.SWING_RADIUS_DIMENSION: fixture.SWING_RADIUS,
    }


def test_the_settings_texts_clear_every_extension_line_and_the_bar() -> None:
    """Texts sit right of P1, outside both references' extension lines; the
    stick-out's (lower) row is the one the swing radius's P1 extension line
    passes, so its text must start right of that line."""
    tip_x = drawing.FRONT_ORIGIN[0] + fixture.SWING_RADIUS * drawing._S
    stick = drawing.SETTINGS_TEXT_XY[fixture.STICK_OUT_DIMENSION]
    swing = drawing.SETTINGS_TEXT_XY[fixture.SWING_RADIUS_DIMENSION]
    assert stick[1] < swing[1]
    char_width = 0.0025  # ~3.5 mm text, generous
    widest = max(len(text) for text in fixture.DIMENSION_CALLOUTS.values())
    for x, _y in (stick, swing):
        assert x - widest * char_width / 2.0 > tip_x
        assert x + widest * char_width / 2.0 < drawing.ISO_CENTER[0] - 0.015
    # Both rows clear the bit's top edge at the station.
    bit_top = (
        drawing.FRONT_ORIGIN[1]
        + (fixture.bar.CROSS_HOLE_STATION + fixture.bit.BIT_RADIUS) * drawing._S
    )
    assert stick[1] - bit_top > 0.008
