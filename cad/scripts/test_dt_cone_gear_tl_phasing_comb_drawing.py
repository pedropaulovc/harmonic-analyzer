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


def test_registry_row_is_brass_sheet_tooling_in_inch() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-03-TL-02"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    # Owner ruling 2026-11-13: one sheet, cut to shape, at the stock's
    # thickness; no thin-wall exception is left to carry.
    assert ".020 in" in row["material_specification"]
    assert "brass" in row["material_specification"].lower()
    assert "machinist_exceptions" not in row
    assert "mill" not in row["process"]
    assert spec.SHEET_THICK == pytest.approx(0.020 * INCH)
    assert spec.SHEET_THICK_TOLERANCE_MM == pytest.approx(0.002 * INCH)
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
        lowest = (
            spec.SEAT_EDGE_MM[0]
            - spec.blade_depth_mm(south)
            - (band if south != spec.REFERENCE_TEETH else 0.0)
        )
        assert lowest > spec.tip_radius_limits_mm(north)[1] + spec.BOND_FLOAT_MM


def test_every_step_fits_the_stack_axially() -> None:
    assert spec.AXIAL_PLACEMENT_WINDOW_MM > 0.0
    assert spec.SHEET_LENGTH == spec.BLADE_START_MM[6] + spec.BLADE_LENGTH


def test_the_profile_is_a_rectilinear_staircase_on_the_seat_origin() -> None:
    points = spec.profile_points_mm()
    assert points[1] == (0.0, 0.0)
    assert len(points) == 2 * len(spec.GEARS) + 2
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        assert (x0 == x1) != (y0 == y1)
    assert points[-1][0] - points[0][0] == spec.SHEET_LENGTH
    for teeth in spec.BONDED_TEETH:
        assert points[spec.step_corner_index(teeth)] == (
            spec.BLADE_START_MM[teeth],
            -spec.BLADE_DEPTH_MM[teeth],
        )
    assert spec.SHEET_VOLUME == pytest.approx(spec._area(points) * spec.SHEET_THICK)


def test_every_dimension_prints_at_the_title_block() -> None:
    """No band tighter than the title block, none set on the model; the
    depths and the stock's thickness .XXX, every length .XX (rule 3)."""
    assert model_toleranced_dimensions(part) == {}
    marked = drawing.sheet_dimension_names()
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.FRONT_KEEP) | set(drawing.BOTTOM_KEEP) == marked
    for name in marked:
        assert name in spec.GLOBALS, name
        places = 3 if name == "SheetThick" or name.startswith("BladeDepth") else 2
        assert spec.DRAWING_PRECISION_BY_NAME[name] == places, name
    assert spec.CALLOUTS_BELOW == {"SheetThick": "SHEET STOCK"}


def test_note_one_names_every_gear_once_with_words_only() -> None:
    notes = spec.SHEET_NOTES.splitlines()
    assert 1 <= len(notes) <= 4
    text = " ".join(notes)
    for teeth in spec.GEARS:
        assert text.count(spec.gear_number(teeth)) == 1, teeth
    positions = [text.index(spec.gear_number(t)) for t in spec.GEARS]
    assert positions == sorted(positions)
    # No method, no dimension (rule 7).
    for word in ("MILL", "SAW", "FILE", "SNIP", "PHASE"):
        assert word not in spec.SHEET_NOTES


def test_no_old_plate_wording_survives() -> None:
    for module in (spec, part, drawing):
        source = inspect.getsource(module).lower()
        for word in ("fork", "tine", "relief", "back face", "both faces", "1018"):
            assert word not in source, (module, word)


def _apart(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def test_sheet_text_stands_apart_inside_the_border_and_off_the_title_block() -> None:
    left, bottom, right, top = 0.0127, 0.0127, 0.4191, 0.2667
    title = (0.216, 0.0, right, 0.066 + 0.003)
    blocks = drawing.text_blocks()
    names = list(blocks)
    for i, a in enumerate(names):
        box = blocks[a]
        assert left < box[0] and box[2] < right and bottom < box[1] and box[3] < top, a
        assert _apart(box, title), a
        assert _apart(box, drawing.SHEET_BOX) or a == "SheetLength", a
        for b in names[i + 1 :]:
            assert _apart(box, blocks[b]), (a, b)
    # Each depth's text runs right of its line, the next line clear of it.
    row = sorted(
        x
        for name, (x, y) in drawing.FRONT_KEEP.items()
        if name.startswith("BladeDepth")
    )
    for x0, x1 in zip(row, row[1:], strict=False):
        assert x1 - (x0 + drawing.DEPTH_TEXT_WIDTH) >= drawing.TEXT_GAP - 1e-9
    # The bottom view's text stands clear of the front view's start rows.
    lowest_start = min(
        y for name, (_x, y) in drawing.FRONT_KEEP.items() if name.startswith("Start")
    )
    assert blocks["SheetThick"][3] < lowest_start - 0.004
    # The notes sit left of the title block, inside the border.
    width = max(len(line) for line in spec.SHEET_NOTES.splitlines()) * 0.0026
    assert drawing.NOTES_XY[0] + width < title[0]
    lines = len(spec.SHEET_NOTES.splitlines())
    assert drawing.NOTES_XY[1] - lines * 0.0046 > bottom


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
    assert -rim - top >= 12.0  # a balloon between the rim and the comb
    iso_top = kit.ISO_CENTER[1] + rim / 2000.0
    assert kit.FRONT_CENTER[1] + bottom / 1000.0 > iso_top + 0.005
