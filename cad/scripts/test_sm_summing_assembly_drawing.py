"""Offline contract for the summing-lever fitter package (MHA-SM-00)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import build_sm_summing_assembly as builder
import draw_sm_summing_assembly as drawing
import sm_summing_assembly_sheet as notes
import sm_summing_assembly_spec as spec
import sm_summing_explode_spec as explode
from _assembly_contract import assembly_contract
import _shop_equipment
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
from _general_table import TABLE_TITLE_DROP, table_column_widths
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
    assert g["SmDowelTopY"] - g["SmDowelEndY"] == pytest.approx(
        spec.knife_dowel.PROUD
    )
    assert notes.DRAWING_DIMENSIONS == {
        spec.COUNTER_FEATURE: {spec.COUNTER_DIMENSION},
        spec.DOWEL_PROUD_FEATURE: {spec.DOWEL_PROUD_DIMENSION},
    }
    assert set(drawing.PRECISION) == set(notes.DIMENSION_CALLOUTS)


def test_setting_table_carries_the_settings_no_visible_dimension_does() -> None:
    # Rule 22 (machinist review of R5 and of farm run
    # 20261117T143446475Z-fdea6028; delegated ruling 2026-11-17 (MainBuild),
    # no precedent; owner review #2144): the bracket
    # station band, the hanger bolt's cut-to-fit length, the top-seat feeler
    # and the free-rock travel print in the sheet 1 setting table, and the
    # steps and checks cite the row that carries their value.
    header = notes.SETTING_TABLE_HEADER
    rows = {
        cells[0]: dict(zip(header, cells, strict=True))
        for cells in notes.SETTING_TABLE_ROWS
    }
    assert list(rows) == [
        notes.BRACKET_ROW,
        notes.CUT_ROW,
        notes.SEAT_ROW,
        notes.ROCK_ROW,
        notes.LEVEL_ROW,
    ]
    band = f"±{notes._length(notes.BRACKET_STATION_TOL_MM, 3)}"
    assert band == "±.005"
    assert band in rows[notes.BRACKET_ROW]["SET TO / ACCEPT"]
    assert notes.HANGER_FIT_CUT == ".351"
    cut = rows[notes.CUT_ROW]
    assert cut["SET TO / ACCEPT"] == f"{notes.HANGER_STACK} + {notes.HANGER_FIT_CUT}"
    assert cut["MEASURE FIRST"].startswith(f"{notes.HANGER_STACK} = ")
    feeler = notes._length(notes.SEAT_FEELER_MM, 3)
    assert feeler == ".002"
    assert rows[notes.SEAT_ROW]["SET TO / ACCEPT"] == f"NO {feeler} FEELER ENTERS"
    assert notes.ROCK_TRAVEL_MIN == ".295 MIN"
    assert rows[notes.ROCK_ROW]["SET TO / ACCEPT"].startswith(notes.ROCK_TRAVEL_MIN)

    def step(label: str) -> str:
        return next(s for s in notes.ASSEMBLY_STEPS if s.startswith(label))

    assert band in step("3. ") and notes.setting_row(notes.BRACKET_ROW) in step("3. ")
    for label in ("4. ", "4A. "):
        assert notes.setting_row(notes.CUT_ROW) in step(label)
    assert f"PLUS {notes.HANGER_FIT_CUT} UNDER THE HEAD" in step("4A. ")
    check = next(c for c in notes.ASSEMBLY_CHECKS if c.startswith("1. "))
    assert feeler in check and notes.setting_row(notes.SEAT_ROW) in check
    # Check 1 tries EACH mount's seat, so it runs once both bolts are
    # tightened (6H), not at 5C while the rear mount is finger-tight.
    assert "(CHECK 1" in step("6H. ") and "CHECK 1" not in step("5C. ")
    assert notes.setting_row(notes.ROCK_ROW) in step("6G. ")
    rock = next(c for c in notes.ASSEMBLY_CHECKS if c.startswith("2. "))
    assert notes.ROCK_TRAVEL_MIN in rock and notes.setting_row(notes.ROCK_ROW) in rock
    # The lever level is a row too (#3124 machinist review): step 10 and
    # check 4 cite it, and no sheet note restates it.
    assert rows[notes.LEVEL_ROW]["SET TO / ACCEPT"] == notes.LEVEL_CRITERION
    # One name for the instrument in the row and in step 10 (codjiflo #3128).
    assert rows[notes.LEVEL_ROW]["CHECK WITH"] == "DIGITAL ANGLE GAUGE"
    assert f"({notes.LEVEL_GAUGE} ACROSS THE PLATE" in step("10. ")
    assert notes.setting_row(notes.LEVEL_ROW) in step("10. ")
    level = next(c for c in notes.ASSEMBLY_CHECKS if c.startswith("4. "))
    assert notes.setting_row(notes.LEVEL_ROW) in level
    assert not any(notes.LEVEL_CRITERION in n for n in notes.ASSEMBLED_NOTES)
    with pytest.raises(KeyError):
        notes.setting_row("9")


def test_setting_table_fits_the_top_border() -> None:
    left, _bottom, right, _top = drawing.SHEET_INNER_BORDER
    widths = table_column_widths(notes.SETTING_TABLE_HEADER, notes.SETTING_TABLE_ROWS)
    # Cells never wrap: each column is cut to its longest cell, so the whole
    # table must fit with room to spare.
    assert left + drawing.SETTING_TABLE_INSET + sum(widths) < right - 0.005


def test_setting_table_rows_keep_their_top_whatever_the_title_drop() -> None:
    """The rows' bottom read 228.55 mm, 0.55 mm over the DETAIL A guard (run
    20261117T155408788Z): the table's top stays 10.525 mm under the inner
    border, where 1.5 mm title gaps put it, and the title rides above it,
    its top still under the border."""
    border_top = drawing.SHEET_INNER_BORDER[3]
    title_top = drawing.setting_table_title_top()
    assert title_top - TABLE_TITLE_DROP == pytest.approx(border_top - 0.010525)
    assert border_top - title_top >= 0.002


# The finished isometric's native outline at 1:3 (run
# 20261117T150253462Z-123d40fd's layout report), metres.
_FINISHED_OUTLINE_1_3 = (0.1137, 0.2062)
_STANDARD_SCALES = ((1.0, 2.0), (1.0, 2.5), (1.0, 3.0), (1.0, 4.0), (1.0, 5.0))


def _finished_box(scale: tuple[float, float]) -> tuple[float, float, float, float]:
    grow = 3.0 * scale[0] / scale[1]
    half_w = _FINISHED_OUTLINE_1_3[0] * grow / 2.0 + drawing.FINISHED_CLEARANCE
    half_h = _FINISHED_OUTLINE_1_3[1] * grow / 2.0 + drawing.FINISHED_CLEARANCE
    cx, cy = drawing.ASSEMBLY_ISO_CENTER
    return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def test_finished_isometric_is_centred_at_the_largest_scale_that_fits() -> None:
    # Machinist review of farm runs 20261117T143446475Z-fdea6028 (1:5: too
    # small) and 20261117T150253462Z-123d40fd (1:3 left of the title block:
    # bunched against one edge): centred over the field above the title
    # block, at the largest standard scale whose outline, grown by the
    # clearance, stays inside the border and clear of the title block.
    assert drawing.SHEET_SCALES[drawing.SHEET_NAMES[2]] == drawing.FINISHED_SCALE
    x0, y0, x1, y1 = drawing.FINISHED_FIELD
    assert drawing.ASSEMBLY_ISO_CENTER == pytest.approx(((x0 + x1) / 2, (y0 + y1) / 2))
    assert y0 == drawing.TITLE_BLOCK[3]

    def fits(scale: tuple[float, float]) -> bool:
        try:
            drawing._assert_box_on_sheet(_finished_box(scale), label="finished iso")
        except RuntimeError:
            return False
        return True

    fitting = [scale for scale in _STANDARD_SCALES if fits(scale)]
    assert fitting and fitting[0] == drawing.FINISHED_SCALE


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
    # bond note B, so the shoulder screw goes in at 8A-8B; the cured plug is
    # accepted at 8C, with its remedy at 8D (#3646, D54).
    steps = {step.split(". ", 1)[0]: step for step in notes.ASSEMBLY_STEPS}
    assert steps["8"].startswith("8. BOND MHA-SM-05 INTO MHA-SM-01 PER BOND NOTE B")
    assert steps["8A"].startswith("8A. PASS MHA-SM-VN-56")
    assert steps["8B"].startswith("8B. TURN MHA-SM-VN-56 INTO MHA-SM-05")
    assert steps["8C"] == (
        "8C. CHECK THAT MHA-SM-05 DOES NOT TURN OR PULL OUT OF MHA-SM-01 BY HAND."
    )
    assert steps["8D"].startswith(
        "8D. IF IT DOES, TAKE MHA-SM-VN-56 OUT, PULL MHA-SM-05"
    )
    assert steps["8D"].endswith("REDO FROM STEP 8.")
    assert steps["10A"].startswith("10A. TIGHTEN THE HUB SET SCREW MHA-FR-VN-52")
    assert "SNUG, 9 IN-LB MAX" in steps["10A"]
    bond_note = notes.BOND_NOTE_B
    assert bond_note in notes.ASSEMBLY_CHECKS
    assert "CURE 24 H AT ROOM TEMPERATURE BEFORE STEP 8A" in bond_note
    # Bench acceptance, as bond note A's dowel bond (machinist review, run
    # 20261109T142156827Z, rule 23), made a step with its remedy (#3646).
    assert bond_note.endswith("ACCEPT AT STEP 8C.")


def test_a_bonded_loose_dowel_is_held_at_its_proud_and_re_read_after_cure() -> None:
    # Codjiflo #3128: the ream ends in a drill point, so a dowel that slid in
    # by hand has no floor to stop it. Steps 1B-1G hold its proud on a named
    # support (frame upright on parallels, dowel on gauge blocks) while the
    # bond cures and 1H accepts it, proud re-read. One action a step and only
    # degrease, apply and cure rules in the note (rules 22-23, r11 and r12
    # machinist reviews).
    steps = {step.split(". ", 1)[0]: step for step in notes.ASSEMBLY_STEPS}
    assert notes.DOWEL_PROUD == ".280"
    assert "TOP FRAME UPRIGHT" in steps["1B"]
    assert "FACED UNDERSIDE DOWN ON A PAIR OF EQUAL PARALLELS" in steps["1B"]
    assert steps["1C"].endswith(
        f"GAUGE BLOCKS TO THE PARALLELS' HEIGHT LESS {notes.DOWEL_PROUD}."
    )
    assert steps["1D"] == "1D. LIFT THE TOP FRAME OFF THE PARALLELS AND TAKE THAT DOWEL OUT."
    assert steps["1E"] == f"1E. COAT THE DOWEL WITH {notes.BOND_GRADE} PER BOND NOTE A."
    assert steps["1F"] == "1F. STAND THE COATED DOWEL CHAMFER UP ON ITS GAUGE BLOCKS."
    assert "LOWER THE TOP FRAME BACK OVER IT ONTO THE PARALLELS" in steps["1G"]
    assert "DOES NOT TURN OR SLIDE BY HAND" in steps["1H"]
    assert f"DOWEL PROUD SET ON {notes.DETAIL_TITLE}" in steps["1H"]
    assert steps["1J"].startswith("1J. AT EACH HANGER HOLE SEAT AN MHA-SM-VN-54")
    for label in ("1B", "1C", "1D", "1E", "1F", "1G", "1H", "1J"):
        assert steps[label].count(". ") == 1, steps[label]
    bond_note = notes.BOND_NOTE_A
    assert bond_note in notes.ASSEMBLY_CHECKS
    assert "(STEPS 1E-1G)" in bond_note
    for action in ("PRESS", "LIFT", "STAND", "LOWER", "GAUGE BLOCKS", "PARALLELS"):
        assert action not in bond_note, action
    assert bond_note.endswith(
        "CURE 24 H AT ROOM TEMPERATURE BEFORE STEP 5. ACCEPT AT STEP 1H."
    )


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


def test_steps_name_the_front_and_rear_mounts_by_what_the_fitter_sees() -> None:
    # Machinist review of the #2499 head (clarity, r1+r2): FRONT and REAR
    # mounts and trunnions were never tied to anything on the sheets.  Step
    # 5 names the mounts by the hanger hole nearer the gooseneck hub (the hub
    # stands at the summing station) and 6B the rear trunnion by MHA-SM-03's
    # printed datum B end; both cues must match the model's rear (+Z) side.
    import fr_top_frame_spec as top_frame

    (step5,) = [line for line in notes.ASSEMBLY_STEPS if line.startswith("5. ")]
    assert "NEARER THE GOOSENECK HUB IS THE REAR MOUNT" in step5
    assert top_frame.STUD_Z_REAR - SUMMING_Z < SUMMING_Z - top_frame.STUD_Z_FRONT
    (step6b,) = [line for line in notes.ASSEMBLY_STEPS if line.startswith("6B. ")]
    assert "DATUM B END OF MHA-SM-03 (THE REAR TRUNNION)" in step6b
    # Datum B is the lever's +Z body end, the side of the rear hanger hole.
    assert sm_summing_lever_spec.PLATE_Z_PLUS > 0
    assert top_frame.STUD_Z_REAR > SUMMING_Z > top_frame.STUD_Z_FRONT


def test_step_five_runs_each_hanger_bolt_home_by_hand_then_sets_the_gauge_bar() -> None:
    # Owner ruling 2026-10-27 (#2018 option C): accepted as is.  Each cut
    # bolt is run in by hand to its washer before it draws the mount's top
    # seat flat to the crossbar underside.  Owner ruling 2026-11-08 (Pedro),
    # #2144 item 11.3: with both bolts finger-tight the gauge bar through
    # both bores sets the front mount's yaw before its bolt is tightened, and
    # it must slide back out (check 5).  Owner ruling 2026-11-10 (Pedro), #2334, S2:
    # the tool is an 8.0 in bar that spans both mounts, not a class ZZ pin,
    # with a fit route (rule 4): made to the bores it gauges.  Owner ruling
    # 2026-11-24, fit audit S6: its make record reads "TURN THE BAR UNTIL IT
    # SLIDES THROUGH BOTH MOUNTS; DIA .496 MIN", the floor capping the play
    # the rock budget charges; the step states only the fitter's hand check
    # (rule 22, PR #2717; owner, #3203: "Accepted when the bar is made; the
    # assembly sheet says nothing more").  Such a bar shakes, so the hand
    # check is that it slides, and its reference size is the two places
    # every such bar rounds to.
    step = " ".join(_step_group("5"))
    assert step.startswith("5. ")
    assert "MHA-SM-VN-52" in step
    assert "WASHER" in step
    assert "WITHOUT THE LEVER" in step
    assert step.index("BY HAND") < step.index(notes.KNIFE_GAUGE_BAR) < step.index("TIGHTEN")
    assert step.index("TIGHTEN") < step.index("WITHDRAW THE BAR")
    assert notes.KNIFE_GAUGE_BAR == "(Ø.49) X 8.0 LONG GAUGE BAR"
    assert "PIN" not in notes.KNIFE_GAUGE_BAR and "ZZ" not in notes.KNIFE_GAUGE_BAR
    (bar_step,) = [
        line for line in notes.ASSEMBLY_STEPS if notes.KNIFE_GAUGE_BAR in line
    ]
    assert notes.KNIFE_GAUGE_BAR_FEEL in bar_step and "BY HAND" in bar_step
    assert "SHAKE" not in bar_step
    # Rule 4: the matched fit names its mate by drawing number.
    assert "MADE TO THE MHA-SM-02 BORES" in bar_step
    # No four-place size is left in the step for an instrument to read.
    assert re.search(r"\.\d{4}\b", bar_step.replace(notes.KNIFE_GAUGE_BAR, "")) is None
    record = _shop_equipment.load()["gauges"]["gauge-bar-0472x8"]
    assert "(Ø.49) x 8.0 in" in record["name"]
    assert (
        "TURN THE BAR UNTIL IT SLIDES THROUGH BOTH MOUNTS; DIA .496 MIN"
        in record["purchase"]
    )
    assert builder.knife_mount.KNIFE_GAUGE_BAR_DIA_MIN_IN == 0.496
    assert not hasattr(builder.knife_mount, "KNIFE_GAUGE_BAR_CLEARANCE_IN")
    # Every bar from the .496 floor up to just under the largest Ø.5000 bore
    # (owner ruling 2026-11-23, tool audit Q13) floors to the printed
    # (Ø.49), which stays under the bores' smallest Ø (no stock 1/2 in rod
    # reading).
    assert notes.KNIFE_GAUGE_BAR_SIZES_IN == pytest.approx((0.4960, 0.5000))
    assert notes.KNIFE_GAUGE_BAR_REF_DIA_IN == 0.49
    # The floor's play in the largest bore is the clearance every stack
    # charges.
    assert builder.KNIFE_BAR_CLEARANCE == pytest.approx(0.0040 * 25.4)
    # The recorded corner: the floor stands .00005 over the largest straight
    # bar the smallest conforming pair passes, under the .001 reading unit.
    assert builder.KNIFE_BAR_CORNER_SHORTFALL_IN == pytest.approx(0.0000517, abs=5e-8)
    assert builder.KNIFE_BAR_CORNER_SHORTFALL_IN < builder.KNIFE_BAR_READING_UNIT_IN
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
