"""Offline contract for the summing-lever fitter package (MHA-SM-00)."""

from __future__ import annotations

import math
import re
from pathlib import Path
import tomllib

import pytest

import _config
import build_sm_summing_assembly as builder
import draw_sm_summing_assembly as drawing
import sm_summing_assembly_sheet as notes
import sm_summing_assembly_spec as spec
import sm_summing_explode_spec as explode
from _assembly_contract import assembly_contract
from _paths import CAD_ROOT
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
from _general_table import table_column_widths
from _sm_summing_explode import station_of
from _cone_axis_constants import SUMMING_Z
import sm_summing_lever_spec
from stock_anchor_geom import ANCHOR_9490T1


def test_package_keeps_registry_outputs_and_three_landscape_sheets() -> None:
    row = DRAWINGS_BY_NAME["sm_summing_assembly"]
    assert row.source_kind == "assembly"
    assert row.part == "sm_summing"
    assert drawing.SOURCE == row.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        row.outputs["slddrw"], row.outputs["pdf"], row.outputs["png"]
    )
    assert drawing.SHEET_NAMES == ("ASSEMBLED + SETTINGS", "EXPLODED VIEW + BOM", "FINISHED ASSEMBLY")
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
    assert station_of(builder.KNIFE_MOUNT_Z_PLUS) == "front"
    assert station_of(builder.KNIFE_MOUNT_Z_MINUS) == "back"
    with pytest.raises(ValueError):
        station_of(SUMMING_Z)


def test_station_slide_clears_the_hex_trunnion() -> None:
    slide = {station: d for _, _, station, axis, d in explode.EXPLODE_STEPS if station}
    assert slide["front"] > 0.0 > slide["back"]
    # Each mount's inner face to its own stub's outer end (the -Z stub
    # stands .25 in farther out with the lever body's -Z end, #1038).
    half_mount = builder.knife_mount.SUPPORT_Z_THICK / 2.0
    lever = sm_summing_lever_spec
    engaged = {
        "front": lever.HEX_Z_OUTER_PLUS - (lever.KNIFE_SEAT_Z_PLUS - half_mount),
        "back": (lever.KNIFE_SEAT_Z_MINUS + half_mount) - lever.HEX_Z_OUTER_MINUS,
    }
    for station, distance in slide.items():
        assert abs(distance) > engaged[station] > 0.0


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


def test_boss_hook_unscrews_clear_of_the_boss() -> None:
    # The cut end, flush with the boss underside when fitted, clears the boss
    # top face.
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
    assert g["SmHangerReach"] == spec.HANGER_FIT_REACH
    assert g["SmHangerSeatY"] - g["SmHangerReach"] == spec.HANGER_TIP_POINT[1]
    assert notes.DRAWING_DIMENSIONS == {
        spec.COUNTER_FEATURE: {spec.COUNTER_DIMENSION},
        spec.ROCK_FEATURE: {spec.ROCK_DIMENSION},
        spec.HANGER_FEATURE: {spec.HANGER_DIMENSION},
    }
    assert set(drawing.PRECISION) == set(notes.DIMENSION_CALLOUTS)


def test_hanger_reach_setting_runs_down_the_bolt_from_the_clamped_top_seat() -> None:
    # Rule 22 (machinist review of R5, main 67ba11bf1a): step 4A's cut reach
    # prints as DETAIL A's own model dimension, from the mount's top seat
    # (clamped to the crossbar underside) down the bolt axis.
    assert spec.HANGER_SEAT_POINT == (builder.KNIFE[0], builder.KNIFE_MOUNT_TOP_Y)
    assert spec.HANGER_TIP_POINT[1] == pytest.approx(
        builder.KNIFE_MOUNT_TOP_Y - spec.HANGER_FIT_REACH
    )
    # The modelled cut tip sits inside the printed band about the setting.
    assert abs(builder.HANGER_REACH - spec.HANGER_FIT_REACH) <= spec.HANGER_FIT_REACH_TOL
    assert drawing.PRECISION[spec.HANGER_DIMENSION] == spec.HANGER_FIT_REACH_PLACES
    cut = next(s for s in notes.ASSEMBLY_STEPS if s.startswith("4A. "))
    assert f"PLUS {notes.HANGER_FIT_CUT} UNDER THE HEAD" in cut
    assert f"DETAIL {notes.DETAIL_LETTER}, SHEET 1" in cut


def test_setting_table_carries_the_non_dimension_acceptances_the_steps_cite() -> None:
    # Rule 22: the bracket transfer band and the top-seat feeler are no model
    # dimension, so they print in the sheet 1 setting table; step 3 and
    # check 1 cite the row that carries their value.
    header = notes.SETTING_TABLE_HEADER
    rows = {cells[0]: dict(zip(header, cells, strict=True)) for cells in notes.SETTING_TABLE_ROWS}
    assert list(rows) == [notes.BRACKET_ROW, notes.SEAT_ROW]
    band = f"±{notes._length(notes.BRACKET_STATION_TOL_MM, 3)}"
    assert band == "±.005"
    assert band in rows[notes.BRACKET_ROW]["SET TO / ACCEPT"]
    feeler = notes._length(notes.SEAT_FEELER_MM, 3)
    assert feeler == ".002"
    assert rows[notes.SEAT_ROW]["SET TO / ACCEPT"].startswith(f"{feeler} FEELER")
    bracket = next(s for s in notes.ASSEMBLY_STEPS if s.startswith("3. "))
    assert band in bracket and notes.setting_row(notes.BRACKET_ROW) in bracket
    check = next(c for c in notes.ASSEMBLY_CHECKS if c.startswith("1. "))
    assert feeler in check and notes.setting_row(notes.SEAT_ROW) in check
    # The steps that draw each top seat flat send the fitter to check 1.
    for label in ("5C. ", "6H. "):
        step = next(s for s in notes.ASSEMBLY_STEPS if s.startswith(label))
        assert "(CHECK 1" in step
    with pytest.raises(KeyError):
        notes.setting_row("9")


def test_setting_table_fits_the_top_border() -> None:
    left, _bottom, right, _top = drawing.SHEET_INNER_BORDER
    widths = table_column_widths(notes.SETTING_TABLE_HEADER, notes.SETTING_TABLE_ROWS)
    assert left + drawing.SETTING_TABLE_INSET + sum(widths) < right


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


def test_the_shoulder_screw_goes_in_after_the_end_plug_bond() -> None:
    # Owner rulings 2026-11-08 (Pedro), #2315: step 8 bonds the end plug per
    # bond note B, so the shoulder screw goes in at 8A-8B.
    steps = {step.split(". ", 1)[0]: step for step in notes.ASSEMBLY_STEPS}
    assert steps["8"].startswith("8. BOND MHA-SM-05 INTO MHA-SM-01 PER BOND NOTE B")
    assert steps["8A"].startswith("8A. PASS MHA-SM-VN-56")
    assert steps["8B"].startswith("8B. TURN MHA-SM-VN-56 INTO MHA-SM-05")
    assert steps["10A"].startswith("10A. TIGHTEN THE HUB SET SCREW MHA-FR-VN-52")
    assert "SNUG, 9 IN-LB MAX" in steps["10A"]
    bond_note = notes.BOND_NOTE_B
    assert bond_note in notes.ASSEMBLY_CHECKS
    assert "CURE 24 H BEFORE STEP 8A" in bond_note
    # Bench acceptance, as bond note A's dowel bond (machinist review, run
    # 20261109T142156827Z, rule 23).
    assert bond_note.endswith("ACCEPT: IT DOES NOT TURN OR PULL OUT BY HAND.")


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
    # it must slide back out (check 5).  Owner ruling 2026-11-10 (Pedro), #2334, S2:
    # the tool is an 8.0 in bar that spans both mounts, not a class ZZ pin,
    # with a fit route (rule 4): a matched fit to the bores it gauges, whose
    # maximum is the clearance the rock budget charges.  That fit is the
    # bar's own make record; the step states only the fitter's hand check
    # (rule 22, PR #2717: no number that needs an instrument).
    step = " ".join(_step_group("5"))
    assert step.startswith("5. ")
    assert "MHA-SM-VN-52" in step
    assert "WASHER" in step
    assert "WITHOUT THE LEVER" in step
    assert step.index("BY HAND") < step.index(notes.KNIFE_GAUGE_BAR) < step.index("TIGHTEN")
    assert step.index("TIGHTEN") < step.index("WITHDRAW THE BAR")
    assert notes.KNIFE_GAUGE_BAR == "(Ø.4720) X 8.0 LONG GAUGE BAR"
    assert "PIN" not in notes.KNIFE_GAUGE_BAR and "ZZ" not in notes.KNIFE_GAUGE_BAR
    (bar_step,) = [
        line for line in notes.ASSEMBLY_STEPS if notes.KNIFE_GAUGE_BAR in line
    ]
    assert notes.KNIFE_GAUGE_BAR_FEEL in bar_step and "BY HAND" in bar_step
    # Rule 4: the matched fit names its mate by drawing number.
    assert "MADE TO THE MHA-SM-02 BORES" in bar_step
    # No four-place size is left in the step for an instrument to read.
    assert re.search(r"\.\d{4}\b", bar_step.replace(notes.KNIFE_GAUGE_BAR, "")) is None
    record = tomllib.loads(
        (CAD_ROOT / "config" / "shop-equipment.toml").read_text(encoding="utf-8")
    )["gauges"]["gauge-bar-0472x8"]
    low, high = builder.knife_mount.KNIFE_GAUGE_BAR_CLEARANCE_IN
    assert f"{low:.4f}".lstrip("0") in record["purchase"]
    assert f"{high:.4f}".lstrip("0") in record["purchase"]
    assert builder.knife_mount.KNIFE_GAUGE_BAR_DIA == pytest.approx(2.0 * builder.knife_mount.BORE_R_MIN)
    assert max(builder.knife_mount.KNIFE_GAUGE_BAR_CLEARANCE_IN) * 25.4 == pytest.approx(
        builder.KNIFE_BAR_CLEARANCE
    )
    assert min(builder.knife_mount.KNIFE_GAUGE_BAR_CLEARANCE_IN) > 0.0
    assert builder.KNIFE_GAUGE_BAR_LENGTH > builder.KNIFE_MOUNT_OUTER_SPAN_MAX
    # The mounts' outer span grew .25 in with the front station (#1038).
    assert builder.KNIFE_MOUNT_OUTER_SPAN_MAX / 25.4 == pytest.approx(7.665, abs=1e-3)
    assert notes.KNIFE_GAUGE_BAR not in " ".join(notes.BOM_DESCRIPTIONS.values())
    # The bar is defined once, at 5B; check 5 names it.
    assert sum(notes.KNIFE_GAUGE_BAR in line for line in notes.ASSEMBLY_STEPS) == 1
    assert any(
        check.startswith("5. AFTER STEP 5 THE GAUGE BAR SLIDES OUT")
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
    action = step_five[0].partition("(")[0]
    assert "FRONT MOUNT" in action
    assert "REAR" not in action and "BOTH" not in action and "EACH" not in action
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
    # steps the purchased-part sheets and the joint-retention table cite.
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
