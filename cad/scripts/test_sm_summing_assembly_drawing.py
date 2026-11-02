"""Offline contract for the summing-lever fitter package (MHA-SM-00)."""

from __future__ import annotations

import math
import re
from pathlib import Path

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
from _drawing_registry import DRAWINGS_BY_NAME
from _sm_summing_explode import station_of, summing_exploded_view_name
from _cone_axis_constants import SUMMING_Z
import sm_summing_lever_spec
import sm_vn_boss_hook_jam_nut_spec as jam_nut
from stock_anchor_geom import ANCHOR_9490T1


def test_package_keeps_registry_outputs_and_four_landscape_sheets() -> None:
    row = DRAWINGS_BY_NAME["sm_summing_assembly"]
    assert row.source_kind == "assembly"
    assert row.part == "sm_summing"
    assert drawing.SOURCE == row.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        row.outputs["slddrw"], row.outputs["pdf"], row.outputs["png"]
    )
    assert len(drawing.SHEET_NAMES) == 4
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
    assert set(drawing.BALLOON_ANCHORS) == set(notes.BOM_ORDER)
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


def test_dowels_leave_the_mounts_with_the_crossbar_not_with_the_mounts() -> None:
    # Owner ruling 2026-10-24 (T+H3): the dowels press into the crossbar, so
    # the explode lifts them out of the mounts' round hole and slot before any
    # station slides, and no station slide carries them.
    labels = [label for label, *_ in explode.EXPLODE_STEPS]
    dowel_steps = [
        (index, step)
        for index, step in enumerate(explode.EXPLODE_STEPS)
        if spec.DOWEL in step[1]
    ]
    assert len(dowel_steps) == 1
    index, (_label, stems, station, axis, distance) = dowel_steps[0]
    assert stems == (spec.DOWEL,) and station is None and axis == "y"
    assert index < labels.index("front station slides off")
    assert distance == explode.DOWEL_LIFT > builder.knife_dowel.PROUD_MAX
    dowel_top = builder.KNIFE_DOWEL_Y + explode.DOWEL_LIFT
    assert dowel_top < builder.HANGER_WASHER_Y


def test_jam_nut_explodes_threaded_on_the_eyebolt_shank() -> None:
    # Fitted, the nut's underside is on the boss top face, ANCHOR_H above the
    # eyebolt's cut end (flush with the boss underside).
    seated_above_cut_end = sm_summing_lever_spec.ANCHOR_H
    drop = explode.BOSS_HOOK_LIFT - explode.BOSS_JAM_NUT_LIFT
    assert drop > 0.0, "the nut moves down the shank, off its seat"
    # Still threaded: a full nut thickness of shank under it.
    assert seated_above_cut_end - drop > jam_nut.THICKNESS
    # The cut end itself clears the boss top face.
    assert explode.BOSS_HOOK_LIFT > sm_summing_lever_spec.ANCHOR_H


def test_eyebolt_balloon_lands_on_the_eye_facing_the_viewer() -> None:
    anchor = ANCHOR_9490T1
    point = drawing.EYEBOLT_BALLOON_POINT_MM
    offset = [p - c for p, c in zip(point, anchor.eye_open_tip_mm)]
    # On the eye tip's dome-root circle: in the cap plane, one wire radius out.
    assert sum(o * n for o, n in zip(offset, anchor.eye_open_tip_normal)) == (
        pytest.approx(0.0, abs=1e-9)
    )
    assert math.hypot(*offset) == pytest.approx(anchor.wire_radius_mm)
    # Its outward normal faces the +X+Y+Z isometric viewer.
    assert sum(offset) > 0.0
    assert drawing.BALLOON_ANCHORS[spec.BOSS_HOOK].point_mm == point


def test_jam_nut_balloon_lands_on_the_hex_corner_facing_the_viewer() -> None:
    x, y, z = drawing.JAM_NUT_BALLOON_POINT_MM
    # A hex corner (corners at 0, 60, ... deg from part +Y), at half height.
    assert math.hypot(x, y) == pytest.approx(jam_nut.ACROSS_CORNERS / 2.0)
    sixths = math.degrees(math.atan2(x, y)) / 60.0
    assert sixths == pytest.approx(round(sixths), abs=1e-9)
    assert z == pytest.approx(jam_nut.THICKNESS / 2.0)

    def toward_viewer(px: float, py: float) -> float:
        # Row-vector placement (the builder's JAM_NUT_ROWS), dotted with the
        # +X+Y+Z isometric view direction in the horizontal plane.
        rows = builder.JAM_NUT_ROWS
        machine = [px * rows[0][i] + py * rows[1][i] for i in range(3)]
        return machine[0] + machine[2]

    corners = [
        (
            jam_nut.ACROSS_CORNERS / 2.0 * math.sin(math.radians(60.0 * k)),
            jam_nut.ACROSS_CORNERS / 2.0 * math.cos(math.radians(60.0 * k)),
        )
        for k in range(6)
    ]
    assert toward_viewer(x, y) == pytest.approx(
        max(toward_viewer(*corner) for corner in corners)
    )
    assert drawing.BALLOON_ANCHORS[spec.BOSS_JAM_NUT].point_mm == (x, y, z)
    assert drawing.BALLOON_ANCHORS[spec.BOSS_JAM_NUT].instance is None


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
    assert exact <= spec.BOSS_ROCK_TRAVEL < exact + 0.0254  # one .001 in step
    assert spec.BOSS_ROCK_TRAVEL == pytest.approx(7.4676)  # .294
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


def test_step_six_runs_each_hanger_bolt_home_by_hand_before_drawing_up() -> None:
    # Owner ruling 2026-10-27 (#2018 option C): accepted as is.  Each cut
    # bolt is run in by hand to its washer before it draws the mount's top
    # seat flat to the crossbar underside.
    step = notes.ASSEMBLY_STEPS[5]
    assert step.startswith("6. ")
    assert "MHA-SM-VN-52" in step
    assert "WASHER" in step
    assert step.index("BY HAND") < step.index("TIGHTEN")


def test_hanger_fit_up_reach_matches_the_builder_band() -> None:
    assert builder.HANGER_REACH_MIN == pytest.approx(
        spec.HANGER_FIT_REACH - spec.HANGER_FIT_REACH_TOL
    )
    assert builder.HANGER_REACH_MAX == pytest.approx(
        spec.HANGER_FIT_REACH + spec.HANGER_FIT_REACH_TOL
    )


def test_steps_and_checks_stay_above_the_inner_border() -> None:
    for text in (drawing.STEPS_NOTE, drawing.CHECKS_NOTE):
        lines = text.splitlines()
        assert max(map(len, lines)) <= drawing.STEPS_LINE_WIDTH
        bottom = drawing.STEPS_XY[1] - len(lines) * drawing.NOTE_LINE_PITCH
        assert bottom > drawing.SHEET_INNER_BORDER[1] + 0.004
    assert drawing.STEPS_XY[0] > drawing.SHEET_INNER_BORDER[0]
    assert drawing.STEPS_XY[1] < drawing.SHEET_INNER_BORDER[3]
    assert drawing.STEPS_RIGHT < drawing.TITLE_BLOCK[0]
    assert (
        drawing.STEPS_NOTE.split()
        == " ".join(("ASSEMBLY SEQUENCE", *notes.ASSEMBLY_STEPS)).split()
    )
    assert (
        drawing.CHECKS_NOTE.split()
        == " ".join(("ASSEMBLY SEQUENCE (CONT.)", *notes.ASSEMBLY_CHECKS)).split()
    )
    for number in drawing.BOM_PART_NUMBERS.values():
        if any(number in step for step in notes.ASSEMBLY_STEPS):
            assert number in drawing.STEPS_NOTE


def test_one_blank_line_separates_consecutive_numbered_steps() -> None:
    for text in (drawing.STEPS_NOTE, drawing.CHECKS_NOTE):
        lines = text.splitlines()
        starts = [i for i, line in enumerate(lines) if re.match(r"\d+\. ", line)]
        assert len(starts) > 1
        for previous, start in zip(starts, starts[1:]):
            assert lines[start - 1] == ""
            assert "" not in lines[previous : start - 1]
        # The heading runs straight into step 1.
        assert lines[starts[0] - 1].endswith(("SEQUENCE", "CHECKS:"))
