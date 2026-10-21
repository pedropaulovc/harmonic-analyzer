"""Offline contract for the summing-lever fitter package (MHA-SM-00)."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_sm_summing_assembly as builder
import draw_sm_summing_assembly as drawing
import joint_retention
import sm_summing_assembly_sheet as notes
import sm_summing_assembly_spec as spec
import sm_summing_explode_spec as explode
from _assembly_contract import assembly_contract
from _buildgraph import module_deps_of
from _drawing_balloons import BalloonLanding
from _drawing_registry import DRAWINGS_BY_NAME
from _sm_summing_explode import station_of, summing_exploded_view_name
from _cone_axis_constants import SUMMING_Z


def test_package_keeps_registry_outputs_and_three_landscape_sheets() -> None:
    row = DRAWINGS_BY_NAME["sm_summing_assembly"]
    assert row.source_kind == "assembly"
    assert row.part == "sm_summing"
    assert drawing.SOURCE == row.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        row.outputs["slddrw"], row.outputs["pdf"], row.outputs["png"]
    )
    assert len(drawing.SHEET_NAMES) == 3
    assert (
        set(drawing.SHEET_LAYOUTS)
        == set(drawing.SHEET_SCALES)
        == set(drawing.SHEET_NAMES)
    )
    assert notes.DRAWING_NUMBER == assembly_contract(spec.ASM_NAME).number


def test_sheet_text_stays_out_of_the_assembly_recipe() -> None:
    # Recipe closures are file-granular: a wording edit in the sheet module
    # must re-key only the drawing, never the native summing assembly (code
    # review C03).
    def closure(module: object) -> set[str]:
        return {Path(path).name for path in module_deps_of(Path(module.__file__))}

    assembly = closure(builder)
    assert "sm_summing_assembly_spec.py" in assembly
    assert "sm_summing_explode_spec.py" in assembly
    assert "sm_summing_assembly_sheet.py" not in assembly
    assert "sm_summing_assembly_sheet.py" in closure(drawing)
    for name in (
        "DRAWING_NUMBER",
        "BOM_ORDER",
        "DRAWING_DIMENSIONS",
        "LEVEL_TOLERANCE_DEG",
        "BOM_DESCRIPTIONS",
        "DIMENSION_CALLOUTS",
        "ASSEMBLED_NOTES",
        "ASSEMBLY_STEPS",
        "ASSEMBLY_CHECKS",
        "EXPLODE_STEPS",
    ):
        assert not hasattr(spec, name), name


def test_bom_rows_come_from_the_part_registry() -> None:
    assert drawing.BOM_COMPONENTS == notes.BOM_ORDER == tuple(spec.QUANTITIES)
    for stem in notes.BOM_ORDER:
        row = _config.parts(stem)
        assert drawing.BOM_PART_NUMBERS[stem] == row["number"]
        skus = row.get("supplier_skus") or ()
        assert drawing.BOM_SKUS[stem] == (" / ".join(map(str, skus)) or "-")
    assert drawing.BOM_SKUS[spec.KNIFE_MOUNT] == "-"
    assert drawing.BOM_SKUS[spec.BOSS_HOOK] == "9490T1"
    assert spec.QUANTITIES[spec.DOWEL] == builder.knife_dowel.PER_MOUNT * 2


def test_every_bom_part_is_installed_by_a_numbered_step() -> None:
    steps = " ".join(notes.ASSEMBLY_STEPS)
    for stem in notes.BOM_ORDER:
        assert drawing.BOM_PART_NUMBERS[stem] in steps, stem
    numbers = [line.split(".", 1)[0] for line in notes.ASSEMBLY_STEPS]
    assert numbers == [str(index) for index in range(1, len(notes.ASSEMBLY_STEPS) + 1)]


def test_explode_moves_only_contracted_families_with_split_stations() -> None:
    for label, stems, station, axis, distance in explode.EXPLODE_STEPS:
        assert set(stems) <= set(spec.QUANTITIES), label
        assert station in (None, *explode.STATIONS), label
        assert axis in "xyz" and distance != 0.0, label
        if station is not None:
            assert all(
                spec.QUANTITIES[stem] % len(explode.STATIONS) == 0 for stem in stems
            )
    moved = {stem for _, stems, _, _, _ in explode.EXPLODE_STEPS for stem in stems}
    assert moved == set(spec.QUANTITIES) - {spec.LEVER}
    assert station_of(SUMMING_Z + builder.HEX_Z_MID) == "front"
    assert station_of(SUMMING_Z - builder.HEX_Z_MID) == "back"
    with pytest.raises(ValueError):
        station_of(SUMMING_Z)
    assert summing_exploded_view_name("Default") == explode.EXPLODED_VIEW_NAME
    assert summing_exploded_view_name("Default Simplified") == "SM_EXPLODED Simplified"


def test_station_slide_clears_the_hex_trunnion() -> None:
    slide = {station: d for _, _, station, axis, d in explode.EXPLODE_STEPS if station}
    assert slide["front"] > 0.0 > slide["back"]
    mount_inner_face = builder.HEX_Z_MID - builder.knife_mount.SUPPORT_Z_THICK / 2.0
    for distance in slide.values():
        assert abs(distance) > builder.HEX_Z_OUTER - mount_inner_face


def test_settings_are_derived_from_the_placed_geometry() -> None:
    assert spec.KNIFE_POINT == (builder.KNIFE[0], builder.KNIFE_CONTACT_Y)
    assert spec.COUNTER_SCREW_POINT[0] == builder.BOSS_HOOK_POS[0]
    _seat, gooseneck_y = builder.settled_spring_seats.counter_seat()
    assert spec.COUNTER_SCREW_POINT[1] == gooseneck_y + builder.sm_gooseneck_geom.ARM_Y
    assert spec.COUNTER_SCREW_RISE == pytest.approx(
        spec.COUNTER_SCREW_POINT[1] - spec.KNIFE_POINT[1]
    )
    # Exact boss-face travel each way at the free-rock floor, rounded up.
    arm = (
        spec.BOSS_FACE_POINT[0] - spec.KNIFE_POINT[0],
        spec.BOSS_FACE_POINT[1] - spec.KNIFE_POINT[1],
    )
    floor = math.radians(builder.KNIFE_FREE_ROCK_FLOOR_DEG)
    exact = min(
        abs(arm[0] * math.sin(a) + arm[1] * (math.cos(a) - 1.0))
        for a in (floor, -floor)
    )
    assert exact <= spec.BOSS_ROCK_TRAVEL < exact + 0.01
    assert spec.BOSS_ROCK_TRAVEL == pytest.approx(7.46)
    assert builder.KNIFE_FREE_ROCK_WORST_DEG >= spec.KNIFE_FREE_ROCK_FLOOR_DEG
    assert notes.LEVEL_TOLERANCE_DEG == _config.title_block("angular")["value_deg"]


def test_setting_drives_reproduce_the_sketch_values() -> None:
    g = builder._SETTING_GLOBALS
    assert g["SmCounterScrewX"] == spec.COUNTER_SCREW_POINT[0]
    assert spec.KNIFE_POINT[0] - g["SmCounterScrewX"] == pytest.approx(
        spec.COUNTER_SCREW_OFFSET_X
    )
    assert g["SmCounterScrewY"] - g["SmKnifeY"] == pytest.approx(
        spec.COUNTER_SCREW_RISE
    )
    assert g["SmBossRockTravel"] == spec.BOSS_ROCK_TRAVEL
    assert notes.DRAWING_DIMENSIONS == {
        spec.COUNTER_FEATURE: {spec.COUNTER_DIMENSION},
        spec.ROCK_FEATURE: {spec.ROCK_DIMENSION},
    }
    assert set(drawing.PRECISION) == set(notes.DIMENSION_CALLOUTS)


def test_layout_constants_stay_on_the_sheet() -> None:
    left, bottom, right, top = drawing.SHEET_INNER_BORDER
    radius = drawing.DETAIL_CROP_RADIUS
    cx, cy = drawing.DETAIL_CENTRE
    assert left < cx - radius and cx + radius < right
    assert drawing.TITLE_BLOCK[3] < cy - radius - drawing.DETAIL_LABEL_GAP - 0.012
    assert cy + radius < top
    assert drawing.FRONT_CENTER[0] < drawing.RIGHT_CENTER[0] < cx - radius
    bom_right = drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values())
    assert bom_right < right


def test_caption_tracks_native_bom_growth_without_entering_the_table() -> None:
    # Captured native table bounds before/after #1709. Full parent-scoped
    # vendor Numbers wrap without changing the 30 mm Number column or font.
    old_bottom = 0.179495
    current_bottom = 0.1586533
    old_xy = drawing.exploded_caption_xy(old_bottom)
    current_xy = drawing.exploded_caption_xy(current_bottom)
    assert old_xy[0] == current_xy[0] == drawing.BOM_ANCHOR[0]
    assert old_xy[1] - current_xy[1] == pytest.approx(old_bottom - current_bottom)
    # The unchanged native caption extends 0.3958 mm above its anchor.
    top_overhang = 0.0003958
    height = 0.0047657
    for bottom, xy in ((old_bottom, old_xy), (current_bottom, current_xy)):
        top = xy[1] + top_overhang
        assert bottom - top >= drawing.EXPLODED_CAPTION_MIN_GAP
        drawing._assert_box_on_sheet(
            (xy[0], top - height, xy[0] + 0.1148531, top),
            label="captured exploded caption",
        )


def test_a_caption_pushed_into_the_title_block_is_refused() -> None:
    # Retain complete rows and normal text size: insufficient paper must fail,
    # not truncate the BOM or silently reduce the caption clearance.
    xy = drawing.exploded_caption_xy(drawing.TITLE_BLOCK[3])
    with pytest.raises(RuntimeError, match="title block"):
        drawing._assert_box_on_sheet(
            (xy[0], xy[1] - 0.0047657, xy[0] + 0.1148531, xy[1]),
            label="captured exploded caption",
        )


@pytest.fixture
def native_exploded_bounds():
    # Synthetic native readbacks: no geometry/layout acceptance is implied.
    state = SimpleNamespace(
        sheet=drawing.SHEET_NAMES[0],
        left=0.226,
        top=0.258,
        heights=[0.009] * 11,
        widths=[0.012, 0.030, 0.070, 0.028, 0.012],
    )
    model = SimpleNamespace()
    model.ActivateSheet = lambda name: setattr(state, "sheet", name) or True
    model.GetCurrentSheet = lambda: SimpleNamespace(GetName=lambda: state.sheet)
    state.adapter = SimpleNamespace(currentModel=model)
    state.table = SimpleNamespace(
        RowCount=len(state.heights),
        ColumnCount=len(state.widths),
        GetAnnotation=lambda: SimpleNamespace(
            GetPosition=lambda: (state.left, state.top, 0.0)
        ),
        GetRowHeight=lambda row: state.heights[row],
        GetColumnWidth=lambda column: state.widths[column],
    )
    state.caption = SimpleNamespace(box=(0.226, 0.110, 0.34, 0.115))
    state.caption.GetExtent = lambda: (
        *state.caption.box[:2],
        0.0,
        *state.caption.box[2:],
        0.0,
    )
    state.landings = []
    for index, stem in enumerate(drawing.BOM_COMPONENTS, start=1):
        note = SimpleNamespace(circle=(0.100, 0.150, 0.0047))
        note.GetBomBalloonText = lambda _upper, item=str(index): item
        note.GetAnnotation = lambda note=note: note
        note.GetDisplayData = lambda note=note: note
        note.GetArcCount = lambda: 1

        def arc(_index, note=note):
            x, y, radius = note.circle
            point = (x + radius, y, 0.0)
            return (0, 0, -1, -1, *point, *point, x, y, 0.0, 0.0, 0.0, 1.0, 1.0)

        note.GetArcAtIndex2 = arc
        state.landings.append(
            BalloonLanding(stem, f"{stem}-1", note, None, "summing bounds")
        )
    return state


def _check_native_exploded_bounds(fixture) -> None:
    caption_box = drawing._assert_exploded_caption(
        fixture.adapter, fixture.table, fixture.caption
    )
    drawing._assert_exploded_balloon_bounds(
        fixture.adapter, fixture.table, fixture.landings, caption_box
    )


def test_native_summing_bounds_leave_the_rendered_positions_unchanged(
    native_exploded_bounds,
) -> None:
    fixture = native_exploded_bounds
    before = [landing.note.circle for landing in fixture.landings]
    _check_native_exploded_bounds(fixture)
    assert [landing.note.circle for landing in fixture.landings] == before
    assert fixture.sheet == drawing.SHEET_NAMES[1]


@pytest.mark.parametrize("boundary", ["left", "bottom", "right", "top", "title block"])
def test_native_summing_rejects_rendered_circle_outside_usable_sheet(
    native_exploded_bounds,
    boundary,
) -> None:
    fixture = native_exploded_bounds
    left, bottom, right, top = drawing.SHEET_INNER_BORDER
    radius = 0.0047
    mid_x, mid_y = (left + right) / 2.0, (bottom + top) / 2.0
    x, y = {
        "left": (left + radius / 2.0, mid_y),
        "bottom": (mid_x, bottom + radius / 2.0),
        "right": (right - radius / 2.0, mid_y),
        "top": (mid_x, top - radius / 2.0),
        "title block": (
            (drawing.TITLE_BLOCK[0] + drawing.TITLE_BLOCK[2]) / 2.0,
            drawing.TITLE_BLOCK[3] + radius / 2.0,
        ),
    }[boundary]
    landing = fixture.landings[-1]
    landing.note.circle = (x, y, radius)
    with pytest.raises(RuntimeError, match="inner border|title block") as error:
        _check_native_exploded_bounds(fixture)
    assert landing.stem in str(error.value)
    assert f"item {landing.note.GetBomBalloonText(True)}" in str(error.value)


@pytest.mark.parametrize("keepout", ["BOM", "caption"])
@pytest.mark.parametrize("gap", [-0.000001, 0.0, 0.000001])
def test_native_summing_circle_must_clear_native_bom_and_caption(
    native_exploded_bounds,
    keepout,
    gap,
) -> None:
    fixture = native_exploded_bounds
    radius = 1.0 / 256.0
    left = fixture.left if keepout == "BOM" else fixture.caption.box[0]
    y = 0.2 if keepout == "BOM" else 0.1125
    fixture.landings[-1].note.circle = (left - radius - gap, y, radius)
    if gap > 0.0:
        _check_native_exploded_bounds(fixture)
    else:
        with pytest.raises(RuntimeError, match=f"intersects {keepout}"):
            _check_native_exploded_bounds(fixture)


@pytest.mark.parametrize("changed", ["circle", "BOM rows", "BOM columns", "caption"])
def test_native_summing_bounds_reread_settled_ink_table_and_caption(
    native_exploded_bounds,
    changed,
) -> None:
    fixture = native_exploded_bounds
    if changed == "BOM rows":
        fixture.landings[-1].note.circle = (0.37, 0.15, 1.0 / 256.0)
    elif changed == "BOM columns":
        fixture.landings[-1].note.circle = (0.39, 0.20, 1.0 / 256.0)
    _check_native_exploded_bounds(fixture)
    # The final rebuild can move ink or grow native table/caption extents.
    if changed == "circle":
        fixture.landings[-1].note.circle = (0.25, 0.20, 0.0047)
    elif changed == "BOM rows":
        fixture.heights[-1] += 0.01
    elif changed == "BOM columns":
        fixture.widths[-1] += 0.02
    else:
        fixture.caption.box = (0.09, 0.14, 0.11, 0.154)
    with pytest.raises(RuntimeError, match="intersects BOM|intersects caption"):
        _check_native_exploded_bounds(fixture)


def test_retention_rows_cite_the_package_steps() -> None:
    rows = {
        joint.id: joint
        for joint in joint_retention.JOINTS
        if joint.assembly == "sm_summing"
    }
    hanger = rows["sm-summing/knife-hanger-in-mount"]
    assert hanger.installed_at == "MHA-SM-00 STEP 6"
    assert hanger.exposure is joint_retention.Exposure.STATIC_CLAMP
    assert hanger.lock is joint_retention.Lock.NONE
    assert rows["sm-summing/boss-hook-in-lever"].installed_at == "MHA-SM-00 STEP 2"
    assert rows["sm-summing/gooseneck-spring-screw"].installed_at == "MHA-SM-00 STEP 8"
    hook = rows["sm-summing/boss-hook-in-lever"]
    assert hook.lock is joint_retention.Lock.JAM_NUT
    assert hook.lock_part == "sm_vn_boss_hook_jam_nut"
    assert hook.lock_step == "MHA-SM-00 STEP 2"
    nut = rows["sm-summing/boss-hook-jam-nut-on-hook"]
    assert nut.installed_at == "MHA-SM-00 STEP 2"


def test_hanger_fit_up_reach_matches_the_builder_band() -> None:
    assert builder.HANGER_REACH_MIN == pytest.approx(
        spec.HANGER_FIT_REACH - spec.HANGER_FIT_REACH_TOL
    )
    assert builder.HANGER_REACH_MAX == pytest.approx(
        spec.HANGER_FIT_REACH + spec.HANGER_FIT_REACH_TOL
    )


def test_steps_and_checks_stay_above_the_inner_border() -> None:
    lines = drawing.STEPS_AND_CHECKS.splitlines()
    assert max(map(len, lines)) <= drawing.STEPS_LINE_WIDTH
    bottom = drawing.STEPS_XY[1] - len(lines) * drawing.NOTE_LINE_PITCH
    assert bottom > drawing.SHEET_INNER_BORDER[1] + 0.004
    assert drawing.STEPS_XY[0] > drawing.SHEET_INNER_BORDER[0]
    assert drawing.STEPS_XY[1] < drawing.SHEET_INNER_BORDER[3]
    assert drawing.STEPS_RIGHT < drawing.TITLE_BLOCK[0]
    assert drawing.STEPS_AND_CHECKS.split() == " ".join(
        ("ASSEMBLY SEQUENCE", *notes.ASSEMBLY_STEPS, *notes.ASSEMBLY_CHECKS)
    ).split()
    for number in drawing.BOM_PART_NUMBERS.values():
        if any(number in step for step in notes.ASSEMBLY_STEPS):
            assert number in drawing.STEPS_AND_CHECKS
