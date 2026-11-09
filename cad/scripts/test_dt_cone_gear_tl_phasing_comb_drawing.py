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
    """Fork play (T030's and its own) plus the slot position zone, pitch arc."""
    assert set(spec.PHASE_ERROR_MM) == set(spec.BONDED_TEETH)
    for teeth, error in spec.PHASE_ERROR_MM.items():
        assert 0.0 < error <= spec.BOND_CLOCK_TOLERANCE_MM, teeth


def test_every_band_sits_at_its_shop_row_never_tighter() -> None:
    """drawing-guidelines.md "What the shop holds": milled slot and thickness
    +/-.001, milled-step location +/-.002 (a .004 position zone)."""
    rows = {
        spec.SLOT_DEVIATIONS_MM: 0.001,
        spec.THICKNESS_DEVIATIONS_MM: 0.001,
        spec.FORK_DEPTH_DEVIATIONS_MM: 0.002,
    }
    for (low, high), row in rows.items():
        assert -low == high == pytest.approx(row * INCH)
    assert spec.SLOT_POSITION_MM == pytest.approx(0.004 * INCH)
    assert set(spec.MODEL_BANDS_MM.values()) <= set(rows)


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


def test_the_seat_bears_on_t030_and_every_other_slot_clears_its_tip() -> None:
    assert spec.SLOT_BOTTOM_DEPTH_MM[spec.REFERENCE_TEETH] == 0.0
    assert spec.SEAT_RADIUS_MM == spec.tip_radius_limits_mm(30)[1]
    for teeth in spec.BONDED_TEETH:
        bottom = (
            spec.SEAT_RADIUS_MM - spec.SEAT_DROP_MM - spec.SLOT_BOTTOM_DEPTH_MM[teeth]
        )
        assert bottom - 0.127 - spec.BOND_FLOAT_MM > spec.tip_radius_limits_mm(teeth)[1]


def test_every_fork_fits_its_face_and_tines_its_neighbouring_spaces() -> None:
    assert spec.AXIAL_PLACEMENT_WINDOW_MM >= 0.1
    assert spec.TINE_MIN_MM > 0.25
    outer = (spec.THICKNESS + spec.THICKNESS_BAND_MM + spec.SLOT_POSITION_MM) / 2.0
    for teeth in spec.GEARS:
        assert outer + spec.TINE_AIR <= spec.NEIGHBOUR_REACH_MM[teeth]
    # On the .XX grid; the owner's ~3 mm plate is too thick for T030's
    # 12-degree tooth spaces.
    assert (
        abs(spec.THICKNESS / INCH * 100.0 - round(spec.THICKNESS / INCH * 100.0)) < 1e-9
    )
    assert spec.THICKNESS < 3.0


def test_the_profile_is_rectilinear_and_closes_on_the_seat_origin() -> None:
    points = spec.profile_points_mm()
    assert points[3] == (0.0, 0.0)
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        assert (x0 == x1) != (y0 == y1)
    assert points[-1][0] - points[0][0] == spec.PLATE_LENGTH
    for teeth in spec.GEARS:
        south, north = spec.finger_x_mm(teeth)
        assert south < north
        x0, y0, x1, y1 = spec.slot_rectangle_mm(teeth)
        assert (x0, x1) == (south, north)
        assert y0 < -spec.FORK_TIP_DEPTH_MM[teeth] < y1


def test_the_shop_row_bands_live_on_the_model_dimensions() -> None:
    bands = model_toleranced_dimensions(part)
    assert bands == {("feature_name", "dimension_name"): "*deviations"}
    marked = drawing.sheet_dimension_names()
    for feature, name in spec.MODEL_BANDS_MM:
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 3
    assert set(drawing.FRONT_KEEP) | set(drawing.BOTTOM_KEEP) == marked
    assert set(spec.CALLOUTS_BELOW) | set(spec.CALLOUTS_ABOVE) <= marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    for name in marked:
        assert name in spec.GLOBALS, name


def test_callouts_name_each_gear_and_the_note_names_the_mates() -> None:
    for teeth in spec.GEARS:
        callout = spec.CALLOUTS_BELOW[spec.slot_width_name(teeth)]
        assert callout.splitlines() == [
            f"{spec.gear_number(teeth)} TOOTH",
            spec.SLOT_NOTE_FLAG,
        ]
    assert spec.CALLOUTS_BELOW["PlateThick"] == spec.SLOT_NOTE_FLAG
    notes = spec.SHEET_NOTES.splitlines()
    assert len(notes) <= 4
    assert notes[0].startswith("1. EACH SLOT, ITS FORK TIP AND THE PLATE THICKNESS")
    assert not any(char.isdigit() for line in notes for char in line[2:])


def test_builder_drives_every_global_and_names_the_slots() -> None:
    source = inspect.getsource(part)
    assert "both_directions=True" in source
    for teeth in spec.GEARS:
        names, drives = part._slot_drives(teeth)
        assert len(names) == len(drives)
        assert names[0] == f"SlotSpan{spec.gear_tag(teeth)}"
    assert spec.FINISHED_VOLUME < spec.PLATE_VOLUME


def test_sheet_text_stands_inside_the_border_and_off_the_title_block() -> None:
    for name, (x, y) in {**drawing.FRONT_KEEP, **drawing.BOTTOM_KEEP}.items():
        assert 0.015 < x < 0.415 and 0.015 < y < 0.262, name
        if x > 0.216:
            assert y > 0.075, name
    xs = sorted(
        x for name, (x, _y) in drawing.FRONT_KEEP.items() if x > drawing.PLATE_BOX[2]
    )
    assert all(b - a >= drawing.BASELINE_PITCH - 1e-9 for a, b in zip(xs, xs[1:]))


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
    assert '"dt-cone-gear-tl-phasing-comb"' in inspect.getsource(kit_build)
