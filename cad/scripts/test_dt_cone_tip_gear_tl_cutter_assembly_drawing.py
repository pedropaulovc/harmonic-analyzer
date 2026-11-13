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


def _steps() -> list[str]:
    """Each numbered step with its continuation lines, as printed."""
    steps: list[str] = []
    for line in fixture.ASSEMBLY_STEPS.splitlines()[1:]:
        if line[:1].isdigit():
            steps.append(line)
        else:
            assert line.startswith("   "), line
            steps[-1] += "\n" + line
    return steps


def test_the_sheet_is_bom_balloons_and_one_action_steps() -> None:
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert set(drawing.FRONT_ITEMS) | set(drawing.BOTTOM_ITEMS) == set(
        fixture.BOM_COMPONENTS
    )
    assert sorted(fixture.BOM_ITEMS.values()) == ["1", "2", "3"]
    for stem in fixture.BOM_COMPONENTS:
        assert fixture.QUANTITIES[stem] == 1
        assert _config.parts(stem)["number"]
    steps = _steps()
    assert [step.split(".", 1)[0] for step in steps] == [
        str(number) for number in range(1, len(steps) + 1)
    ]
    # Rule 22: at most six printed lines a step.
    assert all(len(step.splitlines()) <= 6 for step in steps)
    window = fixture._window_text()
    # Setting the stick-out and squaring the face are separate steps; each
    # names the tool it is read with and its acceptance.
    (setting,) = (step for step in steps if "SET THE STICK-OUT" in step)
    assert window in setting and "(CALIPER)" in setting and "FACE" not in setting
    (squaring,) = (step for step in steps if "PARALLEL" in step)
    assert "SQUARE" in squaring and "NO LIGHT" in squaring
    assert "STICK-OUT" not in squaring
    # Item 3 clamps item 2's plain round at an adjustable setting (rule 23's
    # adjustable-clamp row): the step names what it bears on, and later steps
    # check the clamp holds and the setting survived it, each on its own.
    (clamp,) = (step for step in steps if "TIGHTEN ITEM 3" in step)
    assert "ITEM 2'S ROUND" in clamp
    after = steps[steps.index(clamp) + 1 :]
    assert any("DOES NOT TURN OR SLIDE BY HAND" in step for step in after)
    assert any(window in step and "(CALIPER)" in step for step in after)


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


def _box(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float, float]:
    (x0, y0), (x1, y1) = drawing.nominal_sheet_point(a), drawing.nominal_sheet_point(b)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _exploded_part_boxes() -> dict[str, tuple[float, float, float, float]]:
    """Each item's front-view outline on sheet 2, nominal, as exploded."""
    radius, length = fixture.bar.BAR_RADIUS, fixture.bar.BAR_LENGTH
    bit_dx = drawing.EXPLODE_OFFSETS_MM[fixture.BIT][0]
    screw_dy = drawing.EXPLODE_OFFSETS_MM[fixture.SET_SCREW][1]
    station, bit_r = fixture.bar.CROSS_HOLE_STATION, fixture.bit.BIT_RADIUS
    tip_x = fixture.BIT_POSITION[0]
    cup_y = fixture.SET_SCREW_POSITION[1]
    screw_r = set_screw.MAJOR_DIA / 2.0
    return {
        fixture.BAR: _box((-radius, 0.0, 0.0), (radius, length, 0.0)),
        fixture.BIT: _box(
            (tip_x - fixture.bit.BIT_LENGTH + bit_dx, station - bit_r, 0.0),
            (tip_x + bit_dx, station + bit_r, 0.0),
        ),
        fixture.SET_SCREW: _box(
            (-screw_r, cup_y - set_screw.LENGTH + screw_dy, 0.0),
            (screw_r, cup_y + screw_dy, 0.0),
        ),
    }


def test_the_exploded_view_pulls_each_loose_item_clear_along_its_way_in() -> None:
    """Rule 22: item 2 out along the cross-hole axis, its tail clear of item
    1's surface; item 3 down the bar's axis, its cup clear of the cutting
    end; item 1 stays put."""
    gap = drawing.EXPLODE_GAP
    assert gap > 0.0
    assert drawing.SHEET_NAMES == ("ASSEMBLY", "EXPLODED VIEW")
    assert drawing.SHEET_SCALES == {
        name: drawing.SHEET_SCALE for name in drawing.SHEET_NAMES
    }
    offsets = drawing.EXPLODE_OFFSETS_MM
    assert offsets[fixture.BAR] == (0.0, 0.0, 0.0)
    bit_dx, bit_dy, bit_dz = offsets[fixture.BIT]
    assert (bit_dy, bit_dz) == (0.0, 0.0)
    tail_x = fixture.BIT_POSITION[0] - fixture.bit.BIT_LENGTH + bit_dx
    assert tail_x - fixture.bar.BAR_RADIUS == pytest.approx(gap)
    screw_dx, screw_dy, screw_dz = offsets[fixture.SET_SCREW]
    assert (screw_dx, screw_dz) == (0.0, 0.0)
    assert fixture.SET_SCREW_POSITION[1] + screw_dy == pytest.approx(-gap)
    # Each axis runs the full length of the items it guides, through them.
    boxes = _exploded_part_boxes()
    bar_axis, cross_axis = (
        _box(*drawing.EXPLODED_AXES_MM[name])
        for name in ("bar axis", "cross-hole axis")
    )
    assert bar_axis[0] == bar_axis[2] and cross_axis[1] == cross_axis[3]
    for stem in (fixture.BAR, fixture.SET_SCREW):
        box = boxes[stem]
        assert box[0] < bar_axis[0] < box[2], stem
        assert bar_axis[1] < box[1] and box[3] < bar_axis[3], stem
    for stem in (fixture.BAR, fixture.BIT):
        box = boxes[stem]
        assert box[1] < cross_axis[1] < box[3], stem
        assert cross_axis[0] < box[0] and box[2] < cross_axis[2], stem


def test_the_exploded_labels_name_every_item_clear_of_the_ink() -> None:
    labels = drawing.EXPLODED_LABELS
    assert set(labels) == set(fixture.BOM_COMPONENTS)
    for stem, text in labels.items():
        assert text.startswith(f"ITEM {fixture.BOM_ITEMS[stem]}")
    assert "FACE TOWARD THE VIEWER" in labels[fixture.BIT]
    assert "CUP END UP" in labels[fixture.SET_SCREW]
    parts = _exploded_part_boxes()
    # Each tip lies on its own item's outline, seated + explode offset.
    tips = {}
    for stem, point in drawing.LABEL_TIPS_MM.items():
        offset = drawing.EXPLODE_OFFSETS_MM[stem]
        tips[stem] = drawing.nominal_sheet_point(
            tuple(p + o for p, o in zip(point, offset, strict=True))
        )
        x0, y0, x1, y1 = parts[stem]
        assert x0 < tips[stem][0] < x1 and y0 < tips[stem][1] < y1, stem
    # Item 2's tip is on its face, full width: behind the form's shoulders,
    # ahead of the flat's end.
    back = fixture.BIT_POSITION[0] - drawing.LABEL_TIPS_MM[fixture.BIT][0]
    assert -fixture.bit.SHOULDER_X < back < fixture.bit.FLAT_LENGTH
    boxes = {
        stem: drawing.label_box(text, drawing.label_position(stem, tips[stem]))
        for stem, text in labels.items()
    }
    boxes["caption"] = drawing.label_box(drawing.EXPLODED_CAPTION, drawing.CAPTION_XY)
    axes = [_box(*ends) for ends in drawing.EXPLODED_AXES_MM.values()]
    left, bottom, right, top = SHEET_INNER
    names = list(boxes)
    for i, name in enumerate(names):
        x0, y0, x1, y1 = boxes[name]
        assert left < x0 and x1 < right and bottom < y0 and y1 < top, name
        assert not _overlap(boxes[name], TITLE_BLOCK), name
        for other in names[i + 1 :]:
            assert not _overlap(boxes[name], boxes[other]), (name, other)
        for part in parts.values():
            assert not _overlap(boxes[name], part), name
        for axis in axes:
            assert not _overlap(boxes[name], axis), name
