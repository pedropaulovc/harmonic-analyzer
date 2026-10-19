"""Offline contract for the summing-lever fitter package (MHA-SM-000)."""

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
import vn_knife_hanger_stud_spec as hanger_bolt
from _assembly_contract import assembly_contract
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
from _sm_summing_explode import station_of, summing_exploded_view_name
from dt_cone_pivot_post_installation import SUMMING_Z


def _printed_text() -> str:
    return "\n".join(
        (
            drawing.ASSEMBLED_NOTES,
            drawing.STEPS_AND_CHECKS,
            drawing.DETAIL_LABEL,
            notes.EXPLODED_CAPTION,
            *notes.DIMENSION_CALLOUTS.values(),
            *notes.BOM_DESCRIPTIONS.values(),
        )
    )


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


def test_printed_text_carries_no_rule_numbers_or_rulings() -> None:
    text = _printed_text()
    assert not re.search(r"\bRULE\b|EXCEPTION|RULING|TODO", text)
    assert text == text.upper()
    assert f"±{notes.LEVEL_TOLERANCE_DEG:g}°" in text


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
    assert drawing.EXPLODED_CAPTION_XY[1] > drawing.TITLE_BLOCK[3]


def test_retention_rows_cite_the_package_steps() -> None:
    rows = {
        joint.id: joint
        for joint in joint_retention.JOINTS
        if joint.assembly == "sm_summing"
    }
    hanger = rows["sm-summing/knife-hanger-in-mount"]
    assert hanger.installed_at == "MHA-SM-000 STEP 6"
    assert hanger.exposure is joint_retention.Exposure.STATIC_CLAMP
    assert hanger.lock is joint_retention.Lock.NONE
    assert rows["sm-summing/boss-hook-in-lever"].installed_at == "MHA-SM-000 STEP 2"
    assert rows["sm-summing/gooseneck-spring-screw"].installed_at == "MHA-SM-000 STEP 8"
    hook = rows["sm-summing/boss-hook-in-lever"]
    assert hook.lock is joint_retention.Lock.JAM_NUT
    assert hook.lock_part == "vn_boss_hook_jam_nut"
    assert hook.lock_step == "MHA-SM-000 STEP 2"
    nut = rows["sm-summing/boss-hook-jam-nut-on-hook"]
    assert nut.installed_at == "MHA-SM-000 STEP 2"
    steps = {line.split(".", 1)[0]: line for line in notes.ASSEMBLY_STEPS}
    assert "MHA-VN-024" in steps["6"]
    assert "MHA-VN-001" in steps["2"] and "MHA-VN-072" in steps["2"]
    assert "MHA-SM-004" in steps["8"]
    # Period hardware: no step leans on a threadlocker, or even names one.
    banned = ("THREADLOCK", "LOCTITE", "NYLON", "NYLOC", "PATCH")
    printed = (*notes.ASSEMBLY_STEPS, *notes.ASSEMBLY_CHECKS)
    assert not [line for line in printed for word in banned if word in line]


def test_hanger_bolts_are_cut_to_the_measured_stack_at_step_4() -> None:
    """Each MHA-VN-024 is cut to its own hole's measured stack plus the
    fit-up reach, the band the builder's reach worst case charges."""
    steps = {line.split(".", 1)[0]: line for line in notes.ASSEMBLY_STEPS}
    fit_up = steps["4"]
    assert f"{spec.HANGER_FIT_REACH:.2f} ±{spec.HANGER_FIT_REACH_TOL:.2f}" in fit_up
    assert "8.92 ±0.15" in fit_up
    assert "MHA-VN-060" in fit_up and "MHA-VN-024" in fit_up
    assert "MEASURE CROSSBAR UNDERSIDE TO WASHER TOP" in fit_up
    # The band is tighter than .XX, so the step names the tap it serves and
    # what both limits keep (assembly machinist review, fr-top-frame r2).
    assert "(REACH INTO MHA-SM-002 TAP: FULL THREAD, TIP CLEAR OF TAP BOTTOM)" in fit_up
    assert builder.HANGER_REACH_MIN == pytest.approx(
        spec.HANGER_FIT_REACH - spec.HANGER_FIT_REACH_TOL
    )
    assert builder.HANGER_REACH_MAX == pytest.approx(
        spec.HANGER_FIT_REACH + spec.HANGER_FIT_REACH_TOL
    )
    # The bolt sheet's reference length names this step.
    bolt_callout = hanger_bolt.DIMENSION_CALLOUTS["CutLength"]
    assert "CUT AT ASSEMBLY" in bolt_callout
    assert f"{notes.DRAWING_NUMBER} STEP 4" in bolt_callout
    # The notes that cite later steps follow the renumbering.
    assert "SHEET 3 STEP 10." in notes.ASSEMBLED_NOTES[-1]
    assert notes.ASSEMBLY_CHECKS[4].startswith("4. AFTER STEP 10 ")
    assert steps["10"].startswith("10. LEVEL SETTING")


def test_steps_and_checks_stay_above_the_inner_border() -> None:
    # Default-format note pitch, as measured for MHA-MG-000 (0.0046).
    lines = drawing.STEPS_AND_CHECKS.splitlines()
    assert max(map(len, lines)) <= drawing.STEPS_LINE_WIDTH
    bottom = drawing.STEPS_XY[1] - len(lines) * 0.0046
    assert bottom > drawing.SHEET_INNER_BORDER[1]
