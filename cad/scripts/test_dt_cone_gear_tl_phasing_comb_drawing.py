"""Offline contracts for the cone tip gears' phasing comb (MHA-DT-03-TL-02)."""

from __future__ import annotations

import inspect

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


def test_registry_row_is_tooling_in_inch() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-03-TL-02"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    entry = DRAWINGS_BY_NAME["dt_cone_gear_tl_phasing_comb"]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_one_fork_per_gear_reference_keyed_the_rest_bonded() -> None:
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
    """Fork play (T030's and its own) plus the slots' centre bands, pitch arc."""
    assert set(spec.PHASE_ERROR_MM) == set(spec.BONDED_TEETH)
    for teeth, error in spec.PHASE_ERROR_MM.items():
        assert 0.0 < error <= spec.BOND_CLOCK_TOLERANCE_MM, teeth


def test_every_band_sits_at_its_shop_row_never_tighter() -> None:
    """drawing-guidelines.md "What the shop holds": milled slot and thickness
    +/-.001, milled-step location +/-.002; no feature-control frame."""
    rows = {
        spec.SLOT_DEVIATIONS_MM: 0.001,
        spec.THICKNESS_DEVIATIONS_MM: 0.001,
        spec.FORK_DEPTH_DEVIATIONS_MM: 0.002,
        spec.SLOT_FACE_DEVIATIONS_MM: 0.002,
    }
    for (low, high), row in rows.items():
        assert -low == high == pytest.approx(row * INCH)
    assert set(spec.MODEL_BANDS_MM.values()) <= set(rows)
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_IN")


def test_the_least_slot_clears_the_thickest_tooth() -> None:
    for teeth in spec.GEARS:
        least = spec.SLOT_WIDTH_MM[teeth] + spec.SLOT_DEVIATIONS_MM[0]
        assert (
            least >= spec.thickest_tooth_mm(teeth) + spec.SLOT_MIN_CLEARANCE_MM - 1e-9
        )


def test_fork_tips_stand_between_pitch_and_tip_at_every_limit() -> None:
    for teeth in spec.GEARS:
        low, high = spec.FORK_TIP_RADIUS_LIMITS_MM[teeth]
        assert spec.pitch_radius_mm(teeth) < low < high
        assert high + spec.ENGAGEMENT_MIN <= spec.tip_radius_limits_mm(teeth)[0]


def test_the_seat_bears_on_t030_and_every_step_clears_the_tips_under_it() -> None:
    assert spec.STEP_DEPTH_MM[spec.REFERENCE_TEETH] == 0.0
    assert spec.SEAT_RADIUS_MM == spec.tip_radius_limits_mm(30)[1]
    xx = 0.010 * INCH
    for south, north in zip(spec.GEARS[1:-1], spec.GEARS[2:]):
        lowest = (
            spec.SEAT_RADIUS_MM - spec.SEAT_DROP_MM - spec.STEP_DEPTH_MM[south] - xx
        )
        for teeth in (south, north):
            assert lowest - spec.BOND_FLOAT_MM > spec.tip_radius_limits_mm(teeth)[1]


def test_every_fork_fits_its_face_and_tines_its_neighbouring_spaces() -> None:
    assert spec.AXIAL_PLACEMENT_WINDOW_MM >= 0.1
    for teeth in spec.GEARS:
        assert (
            spec.face_reach_mm(teeth) + spec.TINE_AIR <= spec.NEIGHBOUR_REACH_MM[teeth]
        )
        assert spec.tine_min_mm(teeth) >= spec.TINE_MIN_MM
    # On the .XX grid; the owner's ~3 mm plate is too thick for T030's
    # 12-degree tooth spaces.
    assert (
        abs(spec.THICKNESS / INCH * 100.0 - round(spec.THICKNESS / INCH * 100.0)) < 1e-9
    )
    assert spec.THICKNESS < 3.0


def test_the_thin_tines_print_as_a_plain_fact_with_the_owner_ruling() -> None:
    """Rule 17's .060 floor is out of reach in a 48 DP tooth space; rule 20:
    the sheet states the worst tine, the part's exception row cites b1."""
    assert 0.25 < spec.TINE_MIN_MM < 0.060 * INCH
    assert (
        spec.TINE_WALL_TEXT
        == f"TINE WALL {spec.inch_text(spec.TINE_MIN_IN * INCH, 3)} MIN"
    )
    assert spec.TINE_MIN_IN * INCH <= spec.TINE_MIN_MM
    assert spec.TINE_WALL_TEXT in spec.CALLOUTS_BELOW["PlateThick"]
    rows = _config.parts(spec.PART_NAME)["machinist_exceptions"]
    assert len(rows) == 1
    assert spec.TINE_WALL_TEXT in rows[0]["where"]
    assert "pending owner confirmation" in rows[0]["reason"]
    assert "owner ruling 2026-11-09 (b1, PR #1992" in rows[0]["reason"]


def test_the_profile_is_rectilinear_and_closes_on_the_seat_origin() -> None:
    points = spec.profile_points_mm()
    assert points[3] == (0.0, 0.0)
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        assert (x0 == x1) != (y0 == y1)
    assert points[-1][0] - points[0][0] == spec.PLATE_LENGTH
    for teeth in spec.GEARS:
        south, north = spec.finger_x_mm(teeth)
        assert south < north
        x0, z0, x1, z1 = spec.slot_rectangle_mm(teeth)
        assert (x0, x1) == (south, north)
        # In line from the back face, inside the plate's thickness.
        assert z0 == spec.SLOT_FACE_MM
        assert 0.0 < z0 < z1 < spec.THICKNESS


def test_the_shop_row_bands_live_on_the_model_dimensions() -> None:
    bands = model_toleranced_dimensions(part)
    assert bands == {("feature_name", "dimension_name"): "*deviations"}
    marked = drawing.sheet_dimension_names()
    for feature, name in spec.MODEL_BANDS_MM:
        if name in marked:
            assert name in spec.DRAWING_DIMENSIONS[feature]
            assert spec.DRAWING_PRECISION_BY_NAME[name] == 3
    # Only T006's slot location prints (5X); every slot's carries the band.
    faces = {name for _, name in spec.MODEL_BANDS_MM if name.startswith("SlotFace")}
    assert faces == {spec.slot_face_name(t) for t in spec.GEARS}
    assert faces & marked == {spec.SLOT_FACE_PRINTED}
    assert set(drawing.FRONT_KEEP) | set(drawing.BOTTOM_KEEP) == marked
    assert set(spec.CALLOUTS_BELOW) | set(spec.CALLOUTS_ABOVE) <= marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    for name in marked - {spec.SLOT_FACE_PRINTED}:
        assert name in spec.GLOBALS, name


def test_every_banded_dimension_points_at_note_one() -> None:
    flagged = {
        name
        for name in (*spec.CALLOUTS_BELOW, *spec.CALLOUTS_ABOVE)
        if spec.SLOT_NOTE_FLAG in spec.CALLOUTS_BELOW.get(name, "")
    }
    assert {
        name for _, name in spec.MODEL_BANDS_MM
    } & drawing.sheet_dimension_names() <= flagged
    for teeth in spec.GEARS:
        callout = spec.CALLOUTS_BELOW[spec.slot_width_name(teeth)]
        assert callout.splitlines() == [
            f"{spec.gear_number(teeth)} TOOTH",
            spec.SLOT_NOTE_FLAG,
        ]
    assert spec.CALLOUTS_ABOVE[spec.SLOT_FACE_PRINTED] == "5X"
    notes = spec.SHEET_NOTES.splitlines()
    assert len(notes) <= 4
    assert notes[0].startswith("1. EACH SLOT: CLEARANCE FIT ON ONE TOOTH")
    # Words only: no dimension, no method (rule 7).
    assert not any(char.isdigit() for line in notes for char in line[2:])


def test_builder_drives_every_global_and_names_the_slots() -> None:
    source = inspect.getsource(part)
    assert "both_directions=True" not in source
    assert 'create_sketch("Top")' in source
    for teeth in spec.GEARS:
        names, drives = part._slot_drives(teeth)
        assert len(names) == len(drives) == 4
        assert names[1:] == [
            spec.slot_width_name(teeth),
            f"SlotX{spec.gear_tag(teeth)}",
            spec.slot_face_name(teeth),
        ]
        assert drives[3] == '"SlotFace"'
    assert spec.FINISHED_VOLUME < spec.PLATE_VOLUME


CHAR = 0.0026  # measured: a capital of the 3.5 mm dimension font


def _block(text_lines: list[str], right: float, y: float) -> tuple[float, ...]:
    width = max(len(line) for line in text_lines) * CHAR
    return (right - width, y - 0.010, right, y + 0.010)


def _apart(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def test_sheet_text_stands_apart_inside_the_border_and_off_the_title_block() -> None:
    left, bottom, right, top = 0.0127, 0.0127, 0.4191, 0.2667
    title = (0.216, 0.0127, right, 0.069)
    # Front: the depth texts in one row, banded ones 25 mm wide, centred.
    row = sorted(
        (x, drawing._half_width(name))
        for name, (x, y) in drawing.FRONT_KEEP.items()
        if y == drawing.DEPTH_TEXT_Y or name == "PlateHeight"
    )
    for (x0, h0), (x1, h1) in zip(row, row[1:]):
        assert x1 - h1 - (x0 + h0) >= drawing.TEXT_GAP - 1e-9
    assert row[-1][0] + row[-1][1] < right
    assert drawing.DEPTH_TEXT_Y + 0.010 < drawing.PLATE_BOX[1]
    # Bottom: each block ends at its dimension line and runs left.
    blocks = {}
    for name, (x, y) in drawing.BOTTOM_KEEP.items():
        lines = [".000 +.000", *spec.CALLOUTS_BELOW.get(name, "").splitlines()]
        blocks[name] = _block(lines, x, y)
    names = list(blocks)
    for i, a in enumerate(names):
        box = blocks[a]
        assert left < box[0] and box[2] < right and bottom < box[1] and box[3] < top, a
        assert _apart(box, title), a
        for b in names[i + 1 :]:
            assert _apart(box, blocks[b]), (a, b)
    # The bottom view's rows stand clear of the front view's start rows.
    lowest_start = min(
        y for name, (_x, y) in drawing.FRONT_KEEP.items() if name.startswith("Start")
    )
    assert drawing.OVER_Y + 0.010 < lowest_start - 0.004
    # The notes sit left of the title block, under the bottom view's blocks.
    width = max(len(line) for line in spec.SHEET_NOTES.splitlines()) * CHAR
    assert drawing.NOTES_XY[0] + width < title[0]
    assert drawing.NOTES_XY[1] < drawing.UNDER_Y - 0.010


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
    # A loose kit item: its own view, never drawn in the assembled views.
    assert kit.BOM_DESCRIPTIONS[spec.PART_NAME] == "CONE TIP GEAR PHASING COMB"
    assert "LOOSE KIT ITEM" in kit.COMB_VIEW_LABEL
