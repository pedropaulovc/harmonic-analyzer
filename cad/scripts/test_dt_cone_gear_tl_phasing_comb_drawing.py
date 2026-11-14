"""Offline contracts for the cone tip gears' phasing comb (MHA-DT-03-TL-02)."""

from __future__ import annotations

import inspect
import math

import pytest

import _config
import build_dt_cone_gear_tl_phasing_comb as part
import draw_dt_cone_gear_tl_phasing_comb as drawing
import dt_cone_gear_spec as family
import dt_cone_gear_tl_phasing_comb_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _machinist_review_mode import MachinistReviewMode

INCH = 25.4


def test_registry_row_is_sheet_tooling_in_inch_its_stock_a_one_line_change() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-03-TL-02"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    # Owner ruling 2026-11-13: one sheet, cut to shape, at the stock's
    # thickness; no thin-wall exception is left to carry. The stock is 1095
    # spring steel by default (pending the owner) and brass a drop-in: the
    # row names it and the model's material follows.
    assert ".020 in" in row["material_specification"]
    assert "1095" in row["material"]
    assert spec.MATERIAL == "Plain Carbon Steel"
    assert "machinist_exceptions" not in row
    assert "mill" not in row["process"]
    assert spec.SHEET_THICK == pytest.approx(0.020 * INCH)
    # The proof takes brass's wider +/-.002 so either stock serves.
    assert spec.SHEET_THICK_TOLERANCE_MM == pytest.approx(0.002 * INCH)
    assert "MATERIAL" not in vars(part) or part.MATERIAL == spec.MATERIAL
    assert "apply_material(adapter, MATERIAL)" in inspect.getsource(part.build)
    entry = DRAWINGS_BY_NAME["dt_cone_gear_tl_phasing_comb"]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_one_blade_per_gear_reference_keyed_the_rest_bonded() -> None:
    assert spec.GEARS == (30, 24, 18, 12, 6)
    assert family.keyed(spec.REFERENCE_TEETH)
    assert [spec.gear_number(t) for t in spec.GEARS] == [
        "MHA-DT-03-T030",
        "MHA-DT-03-T024",
        "MHA-DT-03-T018",
        "MHA-DT-03-T012",
        "MHA-DT-37",
    ]


def test_every_bonded_gear_phases_inside_the_booked_clock() -> None:
    """The comb on T030 at every seat, each gear's own space play about its
    blade at every printed limit, pitch arc."""
    assert set(spec.PHASE_ERROR_MM) == set(spec.BONDED_TEETH)
    for teeth, error in spec.PHASE_ERROR_MM.items():
        assert 0.0 < error <= spec.BOND_CLOCK_TOLERANCE_MM, teeth
    # The booking is the worst gear's, rounded up to the thousandth.
    assert spec.BOND_CLOCK_TOLERANCE_MM < max(spec.PHASE_ERROR_MM.values()) + 0.001


def test_t030s_blade_seats_in_its_space_at_every_limit() -> None:
    """The comb bottoms on T030's root or binds just above it; either way
    it holds T030 at its phase and slides only as far as T030's space lets
    it, about half a circular pitch off the radial plane."""
    assert len(spec.SEAT_CONDITIONS) >= 4 * len(spec.SHEET_LIMITS_MM)
    roots = [spec.root_radius_mm(30, c) for c in range(4)]
    for edge, mid, sheet in spec.SEAT_CONDITIONS:
        assert min(roots) <= math.hypot(edge, mid - sheet / 2.0)
        assert edge < spec.pitch_radius_mm(30)
    half_pitch = math.pi / 96.0 * INCH
    low, high = spec.COMB_SLIDE_MM
    assert 0.8 * half_pitch < low < high < 1.05 * half_pitch
    assert spec.SEAT_EDGE_MM[1] - spec.SEAT_EDGE_MM[0] < 0.010 * INCH


def test_each_bonded_blade_enters_without_bottoming_or_binding() -> None:
    """At the printed depth every limit leaves play and root clearance; one
    thousandth deeper some limit does not (the deepest such depth)."""
    mil = 0.001 * INCH
    for teeth in spec.BONDED_TEETH:
        depth = spec.BLADE_DEPTH_MM[teeth]
        assert spec._enters(teeth, depth), teeth
        assert not spec._enters(teeth, depth + mil), teeth
        assert abs(depth / mil - round(depth / mil)) < 1e-9
    depths = [spec.blade_depth_mm(t) for t in spec.GEARS]
    assert depths == sorted(depths) and depths[0] == 0.0


def test_every_level_clears_the_smaller_gear_beyond_it() -> None:
    band = 0.005 * INCH
    for south, north in zip(spec.GEARS, spec.GEARS[1:], strict=False):
        lowest = spec.SEAT_EDGE_MM[0] - spec.blade_depth_mm(south)
        if south != spec.REFERENCE_TEETH:
            lowest -= band + spec.FLEX_MM[south]
        assert lowest > spec.tip_radius_limits_mm(north)[1] + spec.BOND_FLOAT_MM


def test_the_comb_stands_on_t036_and_every_step_fits_the_stack() -> None:
    assert spec.BLADE_START_MM[spec.REFERENCE_TEETH] == 0.0
    assert spec.AXIAL_MARGIN_MM > 0.0
    assert set(spec.axial_margins_mm()) == {
        *(spec.gear_tag(t) for t in spec.BONDED_TEETH),
        "end",
    }
    assert spec.LEVEL_END_MM == spec.BLADE_START_MM[6] + spec.BLADE_LENGTH


def test_the_u_clears_the_tip_and_grips_t030() -> None:
    """The bridge clears MHA-DT-37's pivot and the near arm MHA-DT-38 at
    every limit; the span is under T030's root diameter at every limit, so
    the spring arm holds both T030 blades on their seats; both arms hold
    rule 17's .060 floor at their narrowest print."""
    xx = 0.01 * INCH
    # The slot's full round reaches the axis past the pivot's end; its straight
    # sides, the spring's cantilever, end at the round's centre.
    assert spec.SLOT_END_RADIUS_MM == pytest.approx(spec.GRIP_SPAN / 2.0)
    assert spec.SLOT_END_MM - xx > spec.PIVOT_END_MAX_MM
    assert spec.SHEET_LENGTH - xx - (spec.SLOT_END_MM + xx) >= 0.23 * INCH
    # At its widest print the span still preloads both T030 blades.
    assert spec.GRIP_SPAN + 0.005 * INCH + spec.GRIP_PRELOAD_MIN_MM <= (
        2.0 * spec.SEAT_EDGE_MM[0] + 1e-9
    )
    flexed = spec._flex_share(spec.SLOT_LENGTH) * spec.SPREAD_MAX_MM
    assert spec.SEAT_EDGE_MM[0] - flexed > spec.BUSHING_REACH_MM
    assert spec.SPRING_WIDTH == pytest.approx(0.080 * INCH)
    assert spec.SPRING_WIDTH - xx >= 0.060 * INCH - 1e-9
    assert spec.ARM_WIDTH_MIN_MM > 0.2 * INCH
    assert spec.GRIP_SPAN + 0.005 * INCH <= 2.0 * spec.SEAT_EDGE_MM[0]
    assert 0.0 < spec.SPREAD_MAX_MM < 1.0
    # Opened to pass MHA-DT-38, the spring arm stays elastic in either stock.
    assert spec.INSTALL_SPREAD_MM > spec.SPREAD_MAX_MM
    assert spec.SPRING_STRAIN < spec.SPRING_YIELD_STRAIN
    # The near arm bends little under the spread: a few hundredths at most.
    assert all(0.0 < flex < 0.05 for flex in spec.FLEX_MM.values())


def test_the_yaw_is_bounded_by_t030s_face_and_every_blade_keeps_its_margins() -> None:
    assert spec.YAW_MAX_RAD == pytest.approx(spec.SLIDE_WIDTH_MM / spec.T030_FACE_MM)
    yawed = [line for line in spec.SEAT_LINES if line[1] != line[2]]
    assert yawed and all(
        abs(end - start) <= spec.SLIDE_WIDTH_MM + 1e-12 for _e, start, end, _s in yawed
    )
    assert spec.BLADE_PLAY_MM == pytest.approx(0.0005 * INCH)
    assert spec.ROOT_AIR_MM == pytest.approx(0.002 * INCH)
    mil = 0.001 * INCH
    for teeth in spec.BONDED_TEETH:
        assert spec._enters(teeth, spec.BLADE_DEPTH_MM[teeth])
        assert not spec._enters(teeth, spec.BLADE_DEPTH_MM[teeth] + mil)


def test_both_t030_blades_hold_the_lean_under_half_a_degree() -> None:
    assert 0.0 < spec.SLIDE_WIDTH_MM < 0.15
    assert spec.LEAN_MAX_RAD == pytest.approx(
        spec.SLIDE_WIDTH_MM / (2.0 * spec.SEAT_EDGE_MM[0])
    )
    assert math.degrees(spec.LEAN_MAX_RAD) < 0.5


def test_the_profile_is_a_rectilinear_u_on_the_seat_origin() -> None:
    points = spec.profile_points_mm()
    assert points[1] == (0.0, 0.0)
    assert len(points) == 2 * len(spec.GEARS) + 8
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        assert (x0 == x1) != (y0 == y1)
    assert max(x for x, _ in points) == spec.SHEET_LENGTH
    assert points[spec.GRIP_POINT] == (0.0, -spec.GRIP_SPAN)
    # Past T006's level the near arm's edge is the seat line again.
    assert points[spec.RETURN_POINT] == (spec.LEVEL_END_MM, 0.0)
    assert points[spec.SLOT_POINT] == (spec.SLOT_LENGTH, 0.0)
    assert spec.SHEET_HEIGHT == pytest.approx(
        spec.ARM_WIDTH + spec.GRIP_SPAN + spec.SPRING_WIDTH
    )
    for teeth in spec.BONDED_TEETH:
        assert points[spec.step_corner_index(teeth)] == (
            spec.BLADE_START_MM[teeth],
            -spec.BLADE_DEPTH_MM[teeth],
        )
    half_disc = math.pi * spec.SLOT_END_RADIUS_MM**2 / 2.0
    assert spec.SHEET_VOLUME == pytest.approx(
        (spec._area(points) - half_disc) * spec.SHEET_THICK
    )
    assert {name for name, *_ in spec.SKETCH_DIMENSIONS} == spec.PROFILE_DIMENSIONS


def test_every_dimension_prints_at_the_title_block() -> None:
    """No band tighter than the title block, none set on the model; the
    depths .XXX, every length .XX (rule 3); the stock's thickness a
    reference over SHEET STOCK, whose ±.002 the registry row states."""
    assert model_toleranced_dimensions(part) == {}
    marked = drawing.sheet_dimension_names()
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.FRONT_KEEP) | set(drawing.BOTTOM_KEEP) == marked
    for name in marked:
        assert name in spec.GLOBALS, name
        three = name in ("SheetThick", "GripSpan") or name.startswith("BladeDepth")
        places = 3 if three else 2
        assert spec.DRAWING_PRECISION_BY_NAME[name] == places, name
    assert spec.REFERENCE_DIMENSIONS == {"SheetThick"}
    assert spec.CALLOUTS_BELOW["SheetThick"] == "SHEET STOCK"
    assert "set_reference_dimension" in inspect.getsource(drawing.build)
    assert ".020 in" in _config.parts(spec.PART_NAME)["material_specification"]


def test_each_depth_states_its_function_and_each_gear_is_named_once() -> None:
    """Rules 3 and 4: each bonded blade's depth says, after its value, the
    root it clears and names that gear; the grip span names T030, whose
    blades it spans. Rule 7: each reason at most six words, no note."""
    for teeth in spec.BONDED_TEETH:
        assert spec.DEPTH_SUFFIX[spec.blade_depth_name(teeth)] == (
            f", CLEARS {spec.gear_number(teeth)} ROOT"
        )
    low, high = spec.GRIP_INTERFERENCE_IN
    assert (
        0.002 <= low < 0.004
        and high * INCH >= spec.SPREAD_MAX_MM > (high - 0.001) * INCH
    )
    assert spec.CALLOUTS_BELOW["GripSpan"].splitlines() == [
        f"{low:.3f}-{high:.3f} INTERFERENCE".replace("0.", "."),
        f"ON {spec.gear_number(spec.REFERENCE_TEETH)} ROOTS",
    ]
    words = (*spec.DEPTH_SUFFIX.values(), spec.GRIP_TEXT)
    for text in words:
        assert len([w for w in text.split() if not w.startswith("MHA-")]) <= 6, text
    named = "\n".join((*spec.CALLOUTS_BELOW.values(), *spec.DEPTH_SUFFIX.values()))
    for teeth in spec.GEARS:
        assert named.count(spec.gear_number(teeth)) == 1, teeth
    assert not hasattr(spec, "SHEET_NOTES")
    assert "add_note(" not in inspect.getsource(drawing.build)
    # No method (rule 7).
    for word in ("MILL", "SAW", "FILE", "SNIP", "PHASE", "BEND"):
        assert word not in named


def test_no_old_plate_wording_survives() -> None:
    for module in (spec, part, drawing):
        source = inspect.getsource(module).lower()
        for word in ("fork", "tine", "relief", "back face", "both faces", "1018"):
            assert word not in source, (module, word)


def _apart(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def _off_the_u(box: tuple[float, ...]) -> bool:
    """No edge of the drawn U runs through ``box`` and ``box`` is not inside
    it (its centre outside the outline)."""
    points = [drawing.front_xy(x, y) for x, y in spec.profile_points_mm()]
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        if (
            x0 == x1
            and box[0] < x0 < box[2]
            and min(y0, y1) < box[3]
            and max(y0, y1) > box[1]
        ):
            return False
        if (
            y0 == y1
            and box[1] < y0 < box[3]
            and min(x0, x1) < box[2]
            and max(x0, x1) > box[0]
        ):
            return False
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    inside = False
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        if (y0 > cy) != (y1 > cy) and cx < x0 + (cy - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return not inside


def test_sheet_text_stands_apart_inside_the_border_and_off_the_title_block() -> None:
    left, bottom, right, top = 0.0127, 0.0127, 0.4191, 0.2667
    title = (0.216, 0.0, right, 0.066 + 0.003)
    blocks = drawing.text_blocks()
    names = list(blocks)
    assert drawing.SHEET_BOX[0] > left and drawing.SHEET_BOX[2] < right - 0.005
    for i, a in enumerate(names):
        box = blocks[a]
        assert left < box[0] and box[2] < right and bottom < box[1] and box[3] < top, a
        assert _apart(box, title), a
        assert _off_the_u(box), a
        for b in names[i + 1 :]:
            assert _apart(box, blocks[b]), (a, b)
    # Each depth's text stands left of its own line, under its own extension
    # line: every depth line further out (shallower) ends above it, every one
    # nearer (deeper) and the grip span's stand right of it.
    for teeth in spec.BONDED_TEETH:
        box = blocks[spec.blade_depth_name(teeth)]
        line = drawing.depth_line_x(teeth)
        own = drawing.front_xy(0.0, -spec.BLADE_DEPTH_MM[teeth])[1]
        assert box[2] == pytest.approx(line)
        assert box[3] < own
        for other in spec.BONDED_TEETH:
            other_y = drawing.front_xy(0.0, -spec.BLADE_DEPTH_MM[other])[1]
            if other < teeth:
                assert drawing.depth_line_x(other) > line
            elif other > teeth:
                assert drawing.depth_line_x(other) < line and other_y > box[3]
        assert drawing.GRIP_X > line
    # The grip span's text stands under the U left of its line; the spring
    # arm's inside its own span, further out; the rows over the U.
    grip = blocks["GripSpan"]
    assert grip[3] < drawing.SHEET_BOX[1] - 0.002
    assert grip[2] == pytest.approx(drawing.GRIP_X)
    spring = blocks["SpringWidth"]
    assert spring[2] < drawing.GRIP_X - 0.001
    assert drawing.SPRING_X < drawing.GRIP_X
    rows = [blocks[name] for name in drawing.ROWS]
    assert min(r[1] for r in rows) > drawing.SHEET_BOX[3] + 0.002
    assert [r[1] for r in rows] == sorted(r[1] for r in rows)
    assert blocks["SheetHeight"][0] > drawing.SHEET_BOX[2] + 0.002
    # The thickness's text stands off its arrows on a leader, below both
    # extension lines and left of its dimension line.
    edge_half = spec.SHEET_THICK * drawing.RATIO / 2000.0
    thick = blocks["SheetThick"]
    assert set(drawing.OFFSET_TEXT) == {"SheetThick"}
    assert thick[3] < drawing.BOTTOM_CENTER_Y - edge_half - 0.003
    assert thick[2] < drawing.SHEET_THICK_X - 0.002
    assert "offset_dimension_text" in inspect.getsource(drawing.build)
    assert "_set_suffixes" in inspect.getsource(drawing.build)
    # The isometric's label sits left of the title block, under it.
    assert drawing.ISO_NOTE_XY[0] + len(spec.ISOMETRIC_VIEW_NOTE) * 0.0026 < title[0]
    assert drawing.ISO_NOTE_XY[1] < drawing.ISO_CENTER[1]


def test_the_shop_kit_holds_the_comb() -> None:
    import _buildgraph as bg
    import build_dt_cone_gear_tl_indexing_assembly as kit_build
    import draw_dt_cone_gear_tl_indexing_assembly as kit

    assert "dt_cone_gear_tl_phasing_comb" in bg.references_of(
        "dt_cone_gear_tl_indexing"
    )
    assert bg.is_shop_fixture("dt_cone_gear_tl_phasing_comb")
    assert kit.BOM_COMPONENTS == (kit.PLATE, spec.PART_NAME)
    assert kit.BOM_ITEMS[spec.PART_NAME] == "2"
    assert "KIT_POSITION_MM" in inspect.getsource(kit_build)
    # No view of its own: item 2 shows under item 1 in the plate's face view
    # at its kit pose, a balloon's room below the rim and above the
    # isometric (1:2, plate radius half size); the steps say where it fits.
    assert kit.BOM_DESCRIPTIONS[spec.PART_NAME] == "CONE TIP GEAR PHASING COMB"
    assert not any(name.startswith("COMB_VIEW") for name in vars(kit))
    assert kit.COMB_FITTING_LINE in kit.ASSEMBLY_STEPS.splitlines()
    points = spec.profile_points_mm()
    top = spec.KIT_POSITION_MM[1] + max(y for _, y in points)
    bottom = spec.KIT_POSITION_MM[1] + min(y for _, y in points)
    rim = kit.plate.PLATE_DIA / 2.0
    # Clear of the rim; its balloon lands beside it, past the isometric.
    assert -rim - top >= 7.0
    iso_top = kit.ISO_CENTER[1] + rim / 2000.0
    assert kit.FRONT_CENTER[1] + bottom / 1000.0 > iso_top + 0.005
