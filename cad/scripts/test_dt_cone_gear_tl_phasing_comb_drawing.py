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
    """The comb's slide on T030, both blades' centre bands and each gear's
    own blade play, pitch arc."""
    assert set(spec.PHASE_ERROR_MM) == set(spec.BONDED_TEETH)
    for teeth, error in spec.PHASE_ERROR_MM.items():
        assert 0.0 < error <= spec.BOND_CLOCK_TOLERANCE_MM, teeth
    # The booking is the worst gear's, rounded up to the thousandth.
    assert spec.BOND_CLOCK_TOLERANCE_MM < max(spec.PHASE_ERROR_MM.values()) + 0.001


def test_every_band_sits_at_its_shop_row_never_tighter() -> None:
    """drawing-guidelines.md "What the shop holds": a milled width +/-.001, a
    milled-step location or depth +/-.002; no feature-control frame."""
    rows = {
        spec.BLADE_WIDTH_DEVIATIONS_MM: 0.001,
        spec.BLADE_DEPTH_DEVIATIONS_MM: 0.002,
        spec.BLADE_FACE_DEVIATIONS_MM: 0.002,
    }
    for (low, high), row in rows.items():
        assert -low == high == pytest.approx(row * INCH)
    assert set(spec.MODEL_BANDS_MM.values()) <= set(rows)
    assert spec.BLADE_CENTRE_BAND_MM == pytest.approx(0.0025 * INCH)


def test_each_blade_sits_in_the_space_beside_its_phase_tooth() -> None:
    """The space centred +180/N deg from the phase-0 tooth, the same sense on
    every gear; each blade's centre is that space centre's offset at its
    working radius, derived per gear."""
    for teeth in spec.GEARS:
        assert spec.space_angle_rad(teeth) == pytest.approx(3.141592653589793 / teeth)
        radius = spec.WORKING_RADIUS_MM[teeth]
        root = spec.root_radius_max_mm(teeth)
        assert root < radius < spec.tip_radius_limits_mm(teeth)[0]
        assert abs(spec.BLADE_OFFSET_MM[teeth]) <= 0.0005 * INCH + 1e-9
    assert spec.BLADE_OFFSET_MM[spec.REFERENCE_TEETH] == pytest.approx(0.0)
    assert len(set(spec.BLADE_CENTRE_MM.values())) == len(spec.GEARS)


def test_each_blade_clears_its_space_at_every_limit() -> None:
    """The thickest blade turns its gear through the clearance on every
    printed tooth corner at both tip limits; the thinnest still holds it."""
    for teeth in spec.GEARS:
        centre = spec.BLADE_CENTRE_MM[teeth]
        for corner, tip, width in spec._conditions(
            teeth, spec.BLADE_TIP_DEPTH_MM[teeth], spec.BLADE_WIDTH_MM[teeth]
        ):
            low, high = spec.play_window_rad(
                teeth, corner, tip, centre - width / 2.0, centre + width / 2.0
            )
            play = (high - low) * (tip**2 + centre**2) ** 0.5
            assert play >= spec.BLADE_CLEARANCE_MM - 1e-9, (teeth, corner, tip)
        # On the .001 grid, no thicker than the narrowest space allows.
        width_in = spec.BLADE_WIDTH_MM[teeth] / INCH
        assert abs(width_in * 1000.0 - round(width_in * 1000.0)) < 1e-9


def test_each_blade_tip_stands_between_root_and_pitch_at_every_limit() -> None:
    for teeth in spec.GEARS:
        low, high = spec.BLADE_TIP_LIMITS_MM[teeth]
        centre = spec.BLADE_CENTRE_MM[teeth]
        near = centre - (spec.BLADE_WIDTH_MM[teeth] + spec.BLADE_WIDTH_BAND_MM) / 2.0
        assert (low**2 + near**2) ** 0.5 >= spec.root_radius_max_mm(
            teeth
        ) + spec.ROOT_AIR
        assert (high**2 + centre**2) ** 0.5 <= spec.pitch_radius_mm(teeth) + 1e-6


def test_the_comb_seats_on_t030s_tip_land() -> None:
    """The plate's edge over T030 covers the phase-0 tooth's whole tip land at
    the comb's farthest slide; every step clears the tips beneath it."""
    assert spec.STEP_DEPTH_MM[spec.REFERENCE_TEETH] == 0.0
    assert spec.SEAT_RADIUS_MM == spec.tip_radius_limits_mm(30)[1]
    low, high = spec.COMB_SLIDE_MM
    assert low < 0.0 < high
    assert (
        spec.BACK_FACE_MM + high + spec.BLADE_FACE_BAND_MM + spec.SEAT_COVER
        <= -spec.SEAT_LAND_HALF_MM + 1e-9
    )
    xx = 0.010 * INCH
    for south, north in zip(spec.GEARS[1:-1], spec.GEARS[2:], strict=True):
        lowest = (
            spec.SEAT_RADIUS_MM - spec.SEAT_DROP_MM - spec.STEP_DEPTH_MM[south] - xx
        )
        for teeth in (south, north):
            assert lowest - spec.BOND_FLOAT_MM > spec.tip_radius_limits_mm(teeth)[1]
    # A blade leaves the plate at the step south of it, which clears its gear.
    for teeth in spec.BONDED_TEETH:
        root = spec.SEAT_RADIUS_MM - spec.SEAT_DROP_MM - spec.blade_root_depth_mm(teeth)
        assert root - xx - spec.BOND_FLOAT_MM > spec.tip_radius_limits_mm(teeth)[1]


def test_every_blade_fits_its_face_and_the_plate_holds_every_blade() -> None:
    assert spec.AXIAL_PLACEMENT_WINDOW_MM >= 0.1
    for teeth in spec.GEARS:
        near = spec.BLADE_FACE_MM[teeth] - spec.BLADE_FACE_BAND_MM
        far = (
            spec.THICKNESS
            - 0.010 * INCH
            - spec.BLADE_FACE_MM[teeth]
            - spec.BLADE_FACE_BAND_MM
            - spec.BLADE_WIDTH_MM[teeth]
            - spec.BLADE_WIDTH_BAND_MM
        )
        assert min(near, far) >= spec.RELIEF_MIN - 1e-9, teeth
    # From the 3/32 in flat the registry row names.
    assert spec.THICKNESS < 3.0 / 32.0 * INCH


def test_the_thin_blades_print_as_a_plain_fact_with_the_owner_ruling() -> None:
    """Rule 17's .060 floor is out of reach in a 48 DP tooth space; rule 20:
    the sheet states the thinnest blade, the part's exception row cites the
    2026-11-10 single-blade ruling."""
    assert 0.25 < spec.BLADE_MIN_MM < 0.060 * INCH
    assert spec.BLADE_WALL_TEXT == (
        f"BLADE WALL {spec.inch_text(spec.BLADE_MIN_IN * INCH, 3)} MIN"
    )
    assert spec.BLADE_MIN_IN * INCH <= spec.BLADE_MIN_MM
    assert spec.CALLOUTS_BELOW["PlateThick"] == spec.BLADE_WALL_TEXT
    rows = _config.parts(spec.PART_NAME)["machinist_exceptions"]
    assert [row["id"] for row in rows] == ["RV-01"]
    assert spec.BLADE_WALL_TEXT in rows[0]["where"]
    assert rows[0]["reason"].startswith(
        "owner ruling 2026-11-10 via PR #1992 "
        "(https://github.com/pedropaulovc/harmonic-analyzer/pull/1992): "
        "single blade per gear"
    )
    assert "pending" not in rows[0]["reason"]


def test_the_profile_is_rectilinear_and_closes_on_the_seat_origin() -> None:
    points = spec.profile_points_mm()
    assert points[3] == (0.0, 0.0)
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        assert (x0 == x1) != (y0 == y1)
    assert points[-1][0] - points[0][0] == spec.PLATE_LENGTH
    for teeth in spec.GEARS:
        south, north = spec.blade_x_mm(teeth)
        assert south < north
        outline = spec.relief_outline_mm(teeth)
        for (x0, y0), (x1, y1) in zip(outline, outline[1:] + outline[:1], strict=True):
            assert (x0 == x1) != (y0 == y1)
        # Anchored on the blade's near face at its north end; its width next.
        assert outline[0] == (north, spec.BLADE_FACE_MM[teeth])
        assert outline[2][1] - outline[1][1] == pytest.approx(
            spec.BLADE_WIDTH_MM[teeth]
        )
        assert outline[1][0] < south


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


def test_each_blade_names_its_gear_once_and_every_band_points_at_note_one() -> None:
    """Each blade names its gear once, at its thickness; its location and tip
    depth point at note 1, which ties them to the gear named there."""
    for teeth in spec.GEARS:
        assert spec.CALLOUTS_BELOW[spec.blade_width_name(teeth)].splitlines() == [
            spec.gear_number(teeth),
            spec.BLADE_NOTE_FLAG,
        ]
        assert spec.CALLOUTS_BELOW[spec.blade_face_name(teeth)] == spec.BLADE_NOTE_FLAG
        assert spec.CALLOUTS_BELOW[spec.blade_tip_name(teeth)] == spec.BLADE_NOTE_FLAG
    named = "\n".join(spec.CALLOUTS_BELOW.values())
    for teeth in spec.GEARS:
        assert named.count(spec.gear_number(teeth)) == 1, teeth
    notes = spec.SHEET_NOTES.splitlines()
    assert len(notes) <= 4
    assert notes[0].startswith("1. EACH BLADE: CLEARANCE FIT IN ONE TOOTH SPACE")
    assert "NAMED AT ITS THICKNESS" in notes[1]
    # Words only: no dimension, no method, no narration (rule 7).
    assert not any(char.isdigit() for line in notes for char in line[2:])
    assert "PHASE" not in spec.SHEET_NOTES


def test_sizes_no_fit_depends_on_print_at_two_places() -> None:
    """Rule 3: the lengths, starts, steps, height and thickness are .XX; the
    blades still sit inside their gears' faces at the .XX band."""
    for name in (
        "PlateLength",
        "PlateHeight",
        "PlateThick",
        "BladeLength",
        *(f"Start{spec.gear_tag(t)}" for t in spec.BONDED_TEETH),
        *(f"Step{spec.gear_tag(t)}" for t in spec.BONDED_TEETH[:-1]),
    ):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 2, name
    assert spec.AXIAL_PLACEMENT_WINDOW_MM >= 0.1


def test_no_fork_wording_survives() -> None:
    for module in (spec, part, drawing):
        source = inspect.getsource(module).lower()
        for word in ("fork", "tine", "slot"):
            assert word not in source.replace("milled-slot", ""), (module, word)


def test_builder_drives_every_global_and_names_the_blades() -> None:
    source = inspect.getsource(part)
    assert "both_directions=True" not in source
    for teeth in spec.GEARS:
        names, drives = part._relief_drives(teeth)
        assert len(names) == len(drives) == (7 if teeth == spec.GEARS[0] else 8)
        assert names[1] == spec.blade_width_name(teeth)
        assert names[-1] == spec.blade_face_name(teeth)
        assert drives[-1] == f'"{spec.blade_face_name(teeth)}"'
        assert (spec.root_plane(teeth) is None) == (
            spec.blade_root_depth_mm(teeth) == 0
        )
    expected = sum(spec.RELIEF_VOLUME_MM3.values())
    assert spec.PLATE_VOLUME - spec.FINISHED_VOLUME == pytest.approx(expected)


def _apart(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def test_sheet_text_stands_apart_inside_the_border_and_off_the_title_block() -> None:
    """On the measured text sides (round 2 farm layout audit)."""
    left, bottom, right, top = 0.0127, 0.0127, 0.4191, 0.2667
    title = (0.216, 0.0, right, 0.066 + 0.003)
    # Front: each depth's text runs right of its line, the next line clear.
    row = sorted(
        (x, drawing.depth_text_width(name))
        for name, (x, y) in drawing.FRONT_KEEP.items()
        if y == drawing.DEPTH_TEXT_Y
    )
    assert len(row) == len(spec.GEARS) + len(spec.BONDED_TEETH) - 1
    for (x0, w0), (x1, _w1) in zip(row, row[1:], strict=False):
        assert x1 - (x0 + w0) >= drawing.TEXT_GAP - 1e-9
    assert row[-1][0] + row[-1][1] < right
    assert drawing.DEPTH_TEXT_Y + 0.008 < drawing.PLATE_BOX[1]
    # Bottom: no block on another, the border, or the title block.
    blocks = drawing.bottom_blocks()
    names = list(blocks)
    for i, a in enumerate(names):
        box = blocks[a]
        assert left < box[0] and box[2] < right and bottom < box[1] and box[3] < top, a
        assert _apart(box, title), a
        for b in names[i + 1 :]:
            assert _apart(box, blocks[b]), (a, b)
    # No line from the edge view to an outer-row block runs through an
    # inner-row block (rule 14).
    for name, (x, y) in drawing.BOTTOM_KEEP.items():
        if y not in (drawing.OVER_Y[1], drawing.UNDER_Y[1]):
            continue
        inner = drawing.OVER_Y[0] if y == drawing.OVER_Y[1] else drawing.UNDER_Y[0]
        for other, box in blocks.items():
            if drawing.BOTTOM_KEEP[other][1] == inner:
                assert not box[0] - 0.002 <= x <= box[2] + 0.002, (name, other)
    # T006's thickness stands over the edge view, off the title block.
    assert drawing.width_over(6)
    # The bottom view's rows stand clear of the front view's start rows.
    lowest_start = min(
        y for name, (_x, y) in drawing.FRONT_KEEP.items() if name.startswith("Start")
    )
    assert max(box[3] for box in blocks.values()) < lowest_start - 0.004
    # The notes sit left of the title block, under the bottom view's blocks.
    width = max(len(line) for line in spec.SHEET_NOTES.splitlines()) * 0.0026
    assert drawing.NOTES_XY[0] + width < title[0]
    lines = len(spec.SHEET_NOTES.splitlines())
    assert drawing.NOTES_XY[1] < min(box[1] for box in blocks.values()) - 0.002
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
    # A loose kit item in its own view: titled with its scale, no letter (no
    # parent view carries a viewing mark for it).
    assert kit.BOM_DESCRIPTIONS[spec.PART_NAME] == "CONE TIP GEAR PHASING COMB"
    assert kit.COMB_VIEW_LABEL.splitlines()[0] == "ITEM 2 SHOWN ALONE, SCALE 2:1"
    assert "VIEW" not in kit.COMB_VIEW_LABEL
