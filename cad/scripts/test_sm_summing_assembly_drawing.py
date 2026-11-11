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
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: one dowel per mount.
    assert builder.knife_dowel.PER_MOUNT == 1
    assert spec.QUANTITIES[spec.DOWEL] == builder.knife_dowel.PER_MOUNT * 2 == 2


def test_every_bom_part_is_installed_by_a_numbered_step() -> None:
    steps = " ".join(notes.ASSEMBLY_STEPS)
    for stem in notes.BOM_ORDER:
        assert drawing.BOM_PART_NUMBERS[stem] in steps, stem
    # Numbered steps run 1..n; a step's own sub-steps follow it lettered
    # A, B, ... (no I or O), so other sheets' step citations stay put.
    labels = [line.split(". ", 1)[0] for line in notes.ASSEMBLY_STEPS]
    numbers = [label for label in labels if label.isdigit()]
    assert numbers == [str(index) for index in range(1, len(numbers) + 1)]
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    expected = []
    for label in labels:
        if label.isdigit():
            group, index = label, 0
        else:
            expected.append(f"{group}{letters[index]}")
            index += 1
    assert [label for label in labels if not label.isdigit()] == expected


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
    # the explode lifts them out of the mounts' round holes before any
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


def test_jam_nut_balloon_lands_high_on_the_hex_corner_facing_the_viewer() -> None:
    x, y, z = drawing.JAM_NUT_BALLOON_POINT_MM
    # A hex corner (corners at 0, 60, ... deg from part +Y), in the nut's
    # upper half, clear of its lower outline and the shank's cut end below.
    assert math.hypot(x, y) == pytest.approx(jam_nut.ACROSS_CORNERS / 2.0)
    sixths = math.degrees(math.atan2(x, y)) / 60.0
    assert sixths == pytest.approx(round(sixths), abs=1e-9)
    assert 0.75 * jam_nut.THICKNESS <= z < jam_nut.THICKNESS

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
    # Exact boss-face travel each way at the free-rock floor; the one gauge
    # is read both ways, so it rounds up the larger.
    arm = (
        spec.BOSS_FACE_POINT[0] - spec.KNIFE_POINT[0],
        spec.BOSS_FACE_POINT[1] - spec.KNIFE_POINT[1],
    )
    floor = math.radians(builder.KNIFE_FREE_ROCK_FLOOR_DEG)
    up, down = (
        abs(arm[0] * math.sin(a) + arm[1] * (math.cos(a) - 1.0))
        for a in (floor, -floor)
    )
    assert (up, down) == pytest.approx((7.488135, 7.454717), abs=5e-6)
    for exact in (up, down):
        assert exact <= spec.BOSS_ROCK_TRAVEL
    assert spec.BOSS_ROCK_TRAVEL < max(up, down) + 0.0254  # one .001 in step
    assert spec.BOSS_ROCK_TRAVEL == pytest.approx(7.493)  # .295
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
    # Owner rulings 2026-11-08 (Pedro), #2315: step 8 bonds the end plug per
    # sheet 1 note 5, so the shoulder screw goes in at 8A-8B.
    assert rows["sm-summing/gooseneck-shoulder-screw"].installed_at == "MHA-SM-00 STEP 8B"
    steps = {step.split(". ", 1)[0]: step for step in notes.ASSEMBLY_STEPS}
    assert steps["8"].startswith("8. BOND MHA-SM-05 INTO MHA-SM-01 PER SHEET 1 NOTE 5")
    assert steps["8A"].startswith("8A. PASS MHA-SM-VN-56")
    assert steps["8B"].startswith("8B. TURN MHA-SM-VN-56 INTO MHA-SM-05")
    assert steps["10A"].startswith("10A. TIGHTEN THE HUB SET SCREW MHA-FR-VN-52")
    assert "SNUG, 9 IN-LB MAX" in steps["10A"]
    (bond_note,) = [n for n in notes.ASSEMBLED_NOTES if n.startswith("5. LOCTITE 638")]
    assert "CURE 24 H BEFORE STEP 8A" in bond_note
    # Bench acceptance, as note 4's dowel bond (machinist review, run
    # 20261109T142156827Z, rule 23).
    assert bond_note.endswith("ACCEPT: IT DOES NOT TURN OR PULL OUT BY HAND.")
    hook = rows["sm-summing/boss-hook-in-lever"]
    assert hook.lock is joint_retention.Lock.JAM_NUT
    assert hook.lock_part == "sm_vn_boss_hook_jam_nut"
    assert hook.lock_step == "MHA-SM-00 STEP 2"
    nut = rows["sm-summing/boss-hook-jam-nut-on-hook"]
    assert nut.installed_at == "MHA-SM-00 STEP 2"


def _step_group(number: str) -> list[str]:
    """The numbered step and its lettered sub-steps, in order."""
    return [s for s in notes.ASSEMBLY_STEPS if drawing._step_group(s) == number]


def test_steps_five_and_six_do_one_thing_a_sub_step() -> None:
    # Rule 22 (integration review at 8fb7fb46f7): each sub-step of the
    # hanger fit-up does one thing; its label is its only ". ".
    for number in ("5", "6"):
        group = _step_group(number)
        assert len(group) > 1
        for line in group:
            assert line.count(". ") == 1, line


def test_step_five_runs_each_hanger_bolt_home_by_hand_then_sets_the_gauge_bar() -> None:
    # Owner ruling 2026-10-27 (#2018 option C): accepted as is.  Each cut
    # bolt is run in by hand to its washer before it draws the mount's top
    # seat flat to the crossbar underside.  Owner ruling 2026-11-08 (Pedro),
    # #2144 item 11.3: with both bolts finger-tight the gauge bar through
    # both bores sets the front mount's yaw before its bolt is tightened, and
    # it must slide back out (check 6).  Owner ruling 2026-11-10 (Pedro), #2334, S2:
    # the tool is an 8.0 in bar that spans both mounts, not a class ZZ pin,
    # with a fit route (rule 4): a matched fit to the bores it gauges, whose
    # maximum is the clearance the rock budget charges.
    step = " ".join(_step_group("5"))
    assert step.startswith("5. ")
    assert "MHA-SM-VN-52" in step
    assert "WASHER" in step
    assert "WITHOUT THE LEVER" in step
    assert step.index("BY HAND") < step.index(notes.KNIFE_GAUGE_BAR) < step.index("TIGHTEN")
    assert step.index("TIGHTEN") < step.index("WITHDRAW THE BAR")
    assert notes.KNIFE_GAUGE_BAR == (
        "(Ø.4720) X 8.0 LONG GAUGE BAR, "
        ".0002-.0017 DIAMETRAL CLEARANCE IN EACH MHA-SM-02 BORE"
    )
    assert "PIN" not in notes.KNIFE_GAUGE_BAR and "ZZ" not in notes.KNIFE_GAUGE_BAR
    assert builder.knife_mount.KNIFE_GAUGE_BAR_DIA == pytest.approx(2.0 * builder.knife_mount.BORE_R_MIN)
    assert max(builder.knife_mount.KNIFE_GAUGE_BAR_CLEARANCE_IN) * 25.4 == pytest.approx(
        builder.KNIFE_BAR_CLEARANCE
    )
    assert min(builder.knife_mount.KNIFE_GAUGE_BAR_CLEARANCE_IN) > 0.0
    assert builder.KNIFE_GAUGE_BAR_LENGTH > builder.KNIFE_MOUNT_OUTER_SPAN_MAX
    assert builder.KNIFE_MOUNT_OUTER_SPAN_MAX / 25.4 == pytest.approx(7.415, abs=1e-3)
    assert notes.KNIFE_GAUGE_BAR not in " ".join(notes.BOM_DESCRIPTIONS.values())
    # The bar is defined once, at 5B; check 6 names it.
    assert sum(notes.KNIFE_GAUGE_BAR in line for line in notes.ASSEMBLY_STEPS) == 1
    assert any(
        check.startswith("6. AFTER STEP 5 THE GAUGE BAR SLIDES OUT")
        for check in notes.ASSEMBLY_CHECKS
    )


def test_rear_mount_bolt_is_first_tightened_after_its_rock_swing() -> None:
    # #2400: step 6 lifts the rear mount off and 6G sets it by the rock
    # gauge, so step 5 tightens only the front mount; a rear bolt tightened
    # at step 5 would be undone at step 6.
    tightens = [
        line for line in notes.ASSEMBLY_STEPS if "TIGHTEN" in line and "MOUNT" in line
    ]
    step_five = [line for line in tightens if drawing._step_group(line) == "5"]
    assert len(step_five) == 1
    assert "FRONT MOUNT" in step_five[0] and "BOTH" not in step_five[0]
    rear = [line for line in tightens if "TIGHTEN THE REAR" in line]
    assert len(rear) == 1 and drawing._step_group(rear[0]) == "6"
    steps = notes.ASSEMBLY_STEPS
    assert steps.index(rear[0]) > next(
        i for i, line in enumerate(steps) if "SWING THE REAR MOUNT" in line
    )


def test_bracket_transfer_is_its_own_step_and_check_one_holds_the_mounts() -> None:
    # Machinist review of farm build 20261110T204245.238203Z: the MHA-MG-01
    # tap transfer was buried under step 1, and nothing accepted that a
    # mount clamped by one bolt does not turn about its dowel.
    assert all("MHA-MG-01" not in line for line in _step_group("1"))
    assert all("MHA-MG-01" in line for line in _step_group("3"))
    assert any("WASHER" in line for line in _step_group("1"))
    check = next(c for c in notes.ASSEMBLY_CHECKS if c.startswith("1. "))
    assert "DOES NOT TURN ABOUT ITS DOWEL BY HAND" in check


def test_rear_mount_is_rehung_on_the_lever_and_swung_to_the_rock_gauge() -> None:
    # Coordinator ruling on the SM-00 order for #2144 item 11.3: the lever's
    # rigid stubs cannot enter two fixed bores, so the rear mount comes off,
    # takes its stub, is re-hung finger-tight and swung until check 2 passes.
    step = " ".join(_step_group("6"))
    assert step.startswith("6. ") and "REAR MOUNT" in step
    assert (
        step.index("LIFT THE REAR MOUNT OFF")
        < step.index("RE-HANG")
        < step.index("BY HAND")
        < step.index("SWING THE REAR MOUNT ABOUT ITS DOWEL")
        < step.index("(CHECK 2)")
        < step.index("TIGHTEN")
    )
    # The cut stays at step 4 and the hanger joint completes at step 6, the
    # steps the purchased-part sheets and joint_retention cite.
    cut = " ".join(_step_group("4"))
    assert cut.startswith("4. ") and "CUT AN" in cut
    assert builder.KNIFE_REAR_YAW_RANGE_DEG > builder.KNIFE_BAR_YAW_DEG


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
    split = notes.ASSEMBLY_STEPS.index(
        next(
            s
            for s in notes.ASSEMBLY_STEPS
            if s.startswith(f"{drawing.STEPS_CONTINUED_FROM}. ")
        )
    )
    assert (
        drawing.STEPS_NOTE.split()
        == " ".join(("ASSEMBLY SEQUENCE", *notes.ASSEMBLY_STEPS[:split])).split()
    )
    assert (
        drawing.CHECKS_NOTE.split()
        == " ".join(
            (
                "ASSEMBLY SEQUENCE (CONT.)",
                *notes.ASSEMBLY_STEPS[split:],
                *notes.ASSEMBLY_CHECKS,
            )
        ).split()
    )
    for number in drawing.BOM_PART_NUMBERS.values():
        if any(number in step for step in notes.ASSEMBLY_STEPS):
            assert number in drawing.STEPS_NOTE + drawing.CHECKS_NOTE


def test_one_blank_line_separates_consecutive_numbered_steps() -> None:
    for text in (drawing.STEPS_NOTE, drawing.CHECKS_NOTE):
        lines = text.splitlines()
        starts = [i for i, line in enumerate(lines) if re.match(r"\d+\. ", line)]
        assert len(starts) > 1
        for previous, start in zip(starts, starts[1:]):
            # A blank line, or the CHECKS heading after its own blank line.
            gap = lines[previous + 1 : start]
            assert gap.count("") == 1
            assert lines[start - 1] in ("", "CHECKS:")
        # A lettered sub-step runs straight on from its step.
        for index, line in enumerate(lines):
            if re.match(r"\d+[A-Z]\. ", line):
                assert lines[index - 1] != ""
        # The heading runs straight into the first step.
        assert lines[starts[0] - 1].endswith(("SEQUENCE", "(CONT.)", "CHECKS:"))
