"""Offline contracts for the cylinder gears' cam turning fixture kit (MHA-DT-12-TL-00)."""

from __future__ import annotations

import re

import pytest

import _buildgraph as bg
import _config
import _dt_cylinder_gear_tl_cam_turning_interference as interference
import draw_dt_cylinder_gear_tl_cam_turning_assembly as sheet
import dt_cylinder_gear_tl_cam_fixture_spec as fixture
from _assembly_contract import assembly_contract
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout

KIT = "dt_cylinder_gear_tl_cam_turning"
MEMBERS = {
    "dt_cylinder_gear_tl_cam_fixture",
    "dt_cylinder_gear_tl_vn_cam_stub",
    "dt_cylinder_gear_tl_vn_cam_clock_pin",
    "dt_cylinder_gear_tl_vn_cam_clamp_screw",
    "dt_cylinder_gear_tl_vn_cam_clamp_washer",
}


def test_kit_is_a_shop_fixture_holding_every_member_and_no_gear() -> None:
    assert set(bg.references_of(KIT)) == MEMBERS
    assert KIT not in bg.MACHINE_ASSEMBLIES
    assert "dt_cylinder_gear" not in bg.references_of(KIT)
    contract = assembly_contract("dt-cylinder-gear-tl-cam-turning")
    assert contract.number == sheet.DRAWING_NUMBER == "MHA-DT-12-TL-00"
    assert contract.free_dof == 0
    assert contract.drawing_unit == "in"
    entry = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_cam_turning_assembly"]
    assert entry.source_kind == "assembly" and entry.part == KIT
    assert entry.layout is DrawingLayout.LANDSCAPE
    for machine in bg.MACHINE_ASSEMBLIES:
        assert not MEMBERS & set(bg.references_of(machine)), machine


def test_bom_lists_every_member_once_with_its_number() -> None:
    stems = {stem.replace("-", "_") for stem in sheet.BOM_COMPONENTS}
    assert stems == MEMBERS
    assert sorted(sheet.BOM_ITEMS.values()) == ["1", "2", "3", "4", "5"]
    assert set(sheet.BOM_DESCRIPTIONS) == set(sheet.BOM_COMPONENTS)
    for stem in sheet.BOM_COMPONENTS:
        assert sheet.BOM_PART_NUMBERS[stem] == str(_config.parts(stem)["number"])
    assert len(set(sheet.BOM_PART_NUMBERS.values())) == len(sheet.BOM_COMPONENTS)


def test_the_kit_places_each_bought_part_on_its_hole() -> None:
    # The stub and washer stand on the throw axis, the pin on its station;
    # the kit frame stands the body's +Z up (+Y) and its +Y away (-Z).
    assert fixture.kit_point((1.0, 2.0, 3.0)) == (1.0, 3.0, -2.0)
    assert (fixture.STUB_BASE[0], fixture.STUB_BASE[2]) == pytest.approx(
        (0.0, fixture.STUB_OFFSET)
    )
    assert (fixture.PIN_BASE[0], fixture.PIN_BASE[2]) == pytest.approx(
        (fixture.PIN_X, -fixture.PIN_Y)
    )
    assert fixture.PIN_BASE[1] == pytest.approx(
        fixture.THICKNESS - fixture.PIN_HOLE_DEPTH
    )
    assert fixture.WASHER_BASE[1] > fixture.STUB_BASE[1] + fixture.DOWEL_LENGTH
    assert fixture.SCREW_SEAT[1] == pytest.approx(
        fixture.WASHER_BASE[1] + fixture.WASHER_MODEL_THICKNESS
    )
    assert 0.0 < fixture.SCREW_ENGAGEMENT < fixture.DOWEL_THREAD_DEPTH_MIN


def test_every_item_balloons_by_walking_its_own_body() -> None:
    # A side view draws each bought item's rims edge-on, where computed
    # anchors failed (runs 20261113T012650242Z, 20261113T042822797Z); item 2
    # walked in the isometric landed beside item 4 (run 20261114T221042598Z),
    # so items 1 and 2 walk in the front view, items 3-5 in the isometric.
    # No anchor is computed.
    assert sheet.FRONT_ITEMS == (sheet.BODY, sheet.STUB)
    assert set(sheet.ISO_ITEMS) == set(sheet.BOM_COMPONENTS) - set(sheet.FRONT_ITEMS)
    assert sheet.FRONT_ITEMS + sheet.ISO_ITEMS == sheet.BOM_COMPONENTS
    assert set(sheet.BALLOON_ANCHORS) == set(sheet.BOM_COMPONENTS)
    for stem, anchor in sheet.BALLOON_ANCHORS.items():
        assert anchor.point_mm is None, stem
        assert anchor.instance is None, stem


def test_top_and_front_views_are_one_projected_pair_and_labels_omit_the_sheet_scale() -> (
    None
):
    # Both views are placed by the register's face centre: one x, the top
    # view above, both at the sheet's own scale (run 20261113T085510850Z's
    # review: a 1:1 top view over a 2:1 right view turned 90 deg).
    assert sheet.TOP_CENTER[0] == sheet.FRONT_CENTER[0]
    assert sheet.TOP_CENTER[1] > sheet.FRONT_CENTER[1]
    for caption in (sheet.TOP_CAPTION, sheet.FRONT_CAPTION, sheet.EXPLODED_CAPTION):
        assert not re.search(r"\d:\d", caption), caption
    # Both views hide items 4 and 5 and say so; the front caption sits under
    # its view (item 1's back face at FRONT_CENTER y - THICKNESS).
    for caption in (sheet.TOP_CAPTION, sheet.FRONT_CAPTION):
        assert "ITEMS 4 AND 5 OFF" in caption
    assert sheet.FRONT_CAPTION_XY[1] < sheet.FRONT_CENTER[1] - fixture.THICKNESS / 1000.0
    # Item 2's balloon circle stands right of the stub, above item 1's face
    # and under the top view's outline, each by more than a balloon radius.
    x, y = sheet.STUB_BALLOON_XY
    radius = 0.005
    assert y - radius > sheet.FRONT_CENTER[1] + fixture.STUB_STAND / 1000.0
    top_r = fixture.BODY_DIA / 2000.0
    dx = x - sheet.TOP_CENTER[0]
    assert y + radius < sheet.TOP_CENTER[1] - (top_r**2 - dx**2) ** 0.5
    assert x - radius > sheet.TOP_CENTER[0] + fixture.DOWEL_DIA / 2000.0
    # The steps start below the BOM and end above the title block (y <= .066
    # m at x >= .216 m).
    assert sheet.STEPS_XY[1] < sheet.BOM_ANCHOR[1] - 0.070
    lines = sheet.ASSEMBLY_STEPS.splitlines()
    assert sheet.STEPS_XY[1] - len(lines) * sheet.LINE_PITCH > 0.066
    assert max(map(len, lines)) <= sheet.STEP_WIDTH


def _step(number: int) -> str:
    return sheet.STEPS[number - 1]


def test_one_sequence_each_check_follows_the_work_it_verifies() -> None:
    # Run 20261114T231845023Z's review (rule 22): a separate CHECKS block was
    # out of step with the work; one numbered sequence as the arbor kit has.
    for name in ("KIT_STEPS", "FITTING_STEPS", "ASSEMBLY_CHECKS", "CHECKS_XY"):
        assert not hasattr(sheet, name), name
    numbered = [
        line for line in sheet.ASSEMBLY_STEPS.splitlines() if re.match(r"^\d+\. ", line)
    ]
    assert [int(line.split(".")[0]) for line in numbered] == list(
        range(1, len(sheet.STEPS) + 1)
    )
    # Each press, its slip-fit bond at the same seat, then its check.
    for item, first in (("2", 1), ("3", 4)):
        assert _step(first).startswith(f"PRESS ITEM {item} ")
        bond = _step(first + 1)
        assert bond.startswith(f"IF ITEM {item} SLID IN BY HAND, BOND IT AT ")
        assert f"{sheet.BOND}, CURE 24 H." in bond
        assert _step(first + 2) == f"CHECK: ITEM {item} DOES NOT MOVE BY HAND."
    assert fixture.STUB_STAND_TEXT in _step(1)
    # The register set-up, then its check.
    indicate = _step(sheet.INDICATE_STEP)
    assert f"Ø{fixture.BODY_DIA_TEXT} OD" in indicate
    assert f"{fixture.REGISTER_TIR_TEXT} TIR" in indicate
    assert "DIAL TEST INDICATOR" in indicate
    assert sheet.RUNOUT_STEP == sheet.INDICATE_STEP + 1
    assert _step(sheet.RUNOUT_STEP).startswith("CHECK: ")
    assert fixture.STUB_RUNOUT_TEXT in _step(sheet.RUNOUT_STEP)
    # Each gear: slide on, check; turn onto the pin, clamp, check.
    gear_steps = sheet.STEPS[sheet.FIRST_GEAR_STEP - 1 : sheet.FIRST_CAM_STEP - 1]
    assert gear_steps[0].startswith("SLIDE THE GEAR")
    assert gear_steps[1].startswith("CHECK: ")
    turning = [i for i, step in enumerate(gear_steps) if "CLOCKWISE" in step]
    tighten = [i for i, step in enumerate(gear_steps) if "TIGHTEN" in step]
    assert fixture.CUT_TURNS_GEAR_CLOCKWISE
    assert turning == [2] and "TOP VIEW" in gear_steps[2] and tighten == [3]
    assert gear_steps[-1] == "CHECK: THE GEAR DOES NOT TURN BY HAND."
    # The first cam's check, then one action per remedy step, last of all.
    first_cam = sheet.STEPS[sheet.FIRST_CAM_STEP - 1 :]
    assert first_cam[0] == f"CHECK: ONCE TURNED, {fixture.FIRST_CAM_CHECK_TEXT}"
    assert first_cam[1].startswith(f"IF STEP {sheet.FIRST_CAM_STEP} FAILS, RE-INDICATE")
    assert f"(STEP {sheet.INDICATE_STEP})" in first_cam[1]
    assert first_cam[2] == (
        f"IF STEP {sheet.FIRST_CAM_STEP} STILL FAILS, REWORK ITEM 1 TO "
        f"{fixture.PART_NUMBER}."
    )
    assert first_cam[3].startswith("CUT THE OTHER 19 GEARS ONLY AFTER STEP")
    assert len(first_cam) == 4


def test_the_register_tir_is_the_budgets_and_a_4_jaw_setting() -> None:
    # .001: no tighter than the shop's runout row (run 20261114T231845023Z's
    # review); the throw and phase budgets and the runout window carry it.
    assert fixture.REGISTER_TIR_TEXT == ".001"
    assert fixture.REGISTER_OFFSET == fixture.REGISTER_TIR / 2.0
    low, high = (float(value) for value in fixture.STUB_RUNOUT_TEXT.split(" TO "))
    band = 2.0 * (fixture.POSITION_BAND + fixture.REGISTER_OFFSET) / 25.4
    assert high - low == pytest.approx(2.0 * band, abs=1e-4)


def test_only_the_two_presses_and_the_screw_thread_may_overlap() -> None:
    pairs = {
        frozenset(name.rsplit("-", 1)[0] for name in pair)
        for pair in interference.ALLOWED_PAIRS
    }
    assert pairs == {
        frozenset(
            {"dt-cylinder-gear-tl-vn-cam-stub", "dt-cylinder-gear-tl-cam-fixture"}
        ),
        frozenset(
            {"dt-cylinder-gear-tl-vn-cam-clock-pin", "dt-cylinder-gear-tl-cam-fixture"}
        ),
        frozenset(
            {
                "dt-cylinder-gear-tl-vn-cam-clamp-screw",
                "dt-cylinder-gear-tl-vn-cam-stub",
            }
        ),
    }
    for pin, hole, length in (
        interference.STUB_PRESS,
        interference.PIN_PRESS,
        interference.SCREW_THREAD,
    ):
        assert pin > hole and length > 0.0
    assert all(limit > 0.0 for limit in interference.ALLOWED_PAIRS.values())


def test_every_step_is_at_most_three_printed_lines() -> None:
    steps: list[list[str]] = []
    for line in sheet.ASSEMBLY_STEPS.splitlines()[1:]:
        if re.match(r"^\d+\. ", line):
            steps.append([line])
        else:
            steps[-1].append(line)
    assert len(steps) == len(sheet.STEPS) and all(len(step) <= 3 for step in steps)


def test_the_sheet_states_the_engagement_value_and_the_runout_window() -> None:
    # The value only: the reviewer objected to pointing at rule 18's floor.
    assert fixture.SCREW_ENGAGEMENT_TEXT in sheet.ASSEMBLY_STEPS
    assert "1.5D" not in sheet.ASSEMBLY_STEPS
    low, high = (float(value) for value in fixture.STUB_RUNOUT_TEXT.split(" TO "))
    assert low < 2.0 * fixture.STUB_OFFSET / 25.4 < high
    # The exception names the step that prints the engagement.
    engage = next(
        number
        for number, step in enumerate(sheet.STEPS, start=1)
        if fixture.SCREW_ENGAGEMENT_TEXT in step
    )
    assert engage == 13


def test_the_short_screw_engagement_is_a_delegated_rule_18_exception() -> None:
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    name = "dt_cylinder_gear_tl_cam_turning_assembly"
    entries = {
        entry.id: entry for entry in load_exceptions(CAD_ROOT / "config", name, "assembly")
    }
    entry = entries["RV-01"]
    assert entry.kind == "accept"
    assert "rule 18" in entry.finding
    assert fixture.SCREW_ENGAGEMENT_TEXT in entry.where
    assert entry.reason.startswith(
        "Delegated ruling 2026-11-14 (Main), pending owner confirmation: the screw "
        "only holds a brass gear against a light finishing cut"
    )
    assert (
        "https://github.com/pedropaulovc/harmonic-analyzer/issues/2356#issuecomment-6843970923"
        in entry.reason
    )


def test_the_top_view_carries_no_part_dimensions() -> None:
    # The throw and pin station are item 1's geometry, printed on its sheet;
    # check 1 accepts the throw by indicator (run 20261113T204849556Z).
    for name in ("REFERENCE_DIMENSIONS", "REFERENCE_PLACES", "_reference_dimensions"):
        assert not hasattr(sheet, name), name


def test_exploded_view_stacks_in_fitting_order_and_labels_stay_inside() -> None:
    assert sheet.GEAR_Y0 > fixture.THICKNESS + fixture.STUB_STAND
    assert sheet.WASHER_Y0 > sheet.GEAR_TOP
    assert sheet.SCREW_TIP_Y > sheet.WASHER_TOP
    lines = sheet.exploded_lines()
    assert set(lines) == {"phantom", "item", "axis"}
    for group in lines.values():
        for start, end in group.values():
            assert start != end
    tips = {text: (0.200, 0.100 + 0.010 * i) for i, text in enumerate(sheet.LABEL_TIPS)}
    positions = sheet.exploded_label_positions(tips)
    boxes = sheet.label_boxes(positions)
    ordered = sorted(
        (box for text, box in boxes.items() if text != sheet.EXPLODED_CAPTION),
        key=lambda box: -box[3],
    )
    for upper, lower in zip(ordered, ordered[1:]):
        assert lower[3] <= upper[1]
