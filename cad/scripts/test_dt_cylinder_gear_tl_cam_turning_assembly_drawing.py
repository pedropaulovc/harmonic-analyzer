"""Offline contracts for the cylinder gears' cam turning fixture kit (MHA-DT-12-TL-00)."""

from __future__ import annotations

import math
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


def test_bought_items_balloon_on_a_real_rim_just_short_of_its_lines_end() -> None:
    # The right view draws each bought item's rims as lines across its axis;
    # a leader asked near a line's end lands on the end. Each anchor is a
    # point of a real rim of its builder (radius, end face), on the viewer's
    # half (+X), RIM_END_GAP_MM short of the line's end: landing on the end
    # costs at most a quarter of the leader landing limit.
    from _drawing_balloons import _BALLOON_LANDING_TOLERANCE_M

    bought = set(sheet.BOM_COMPONENTS) - {sheet.BODY}
    assert set(sheet.BALLOON_RIMS_MM) == bought
    assert sheet.BALLOON_ANCHORS[sheet.BODY].point_mm is None
    rims = {
        sheet.STUB: (fixture.DOWEL_DIA / 2.0, (0.0, fixture.DOWEL_LENGTH)),
        sheet.CLOCK_PIN: (fixture.PIN_DIA / 2.0, (0.0, fixture.PIN_LENGTH)),
        sheet.WASHER: (fixture.WASHER_OD / 2.0, (0.0, fixture.WASHER_MODEL_THICKNESS)),
        sheet.SCREW_STEM: (fixture.SCREW.head_dia / 2.0, (fixture.SCREW.head_h,)),
    }
    scale = sheet.DETAIL_SCALE[0] / sheet.DETAIL_SCALE[1]
    end_miss_m = sheet.RIM_END_GAP_MM * scale / 1000.0
    assert 0.0 < end_miss_m <= _BALLOON_LANDING_TOLERANCE_M / 4.0
    for stem in bought:
        radius, heights = rims[stem]
        x, y, z = sheet.BALLOON_ANCHORS[stem].point_mm
        assert sheet.BALLOON_RIMS_MM[stem][:2] == (radius, y), stem
        assert y in heights, stem
        assert math.hypot(x, z) == pytest.approx(radius, abs=1e-9), stem
        assert x > 0.0, stem
        assert radius - abs(z) == pytest.approx(sheet.RIM_END_GAP_MM), stem
    # Clear of the screw's hex socket mouth in the head top.
    screw_z = sheet.BALLOON_ANCHORS[sheet.SCREW_STEM].point_mm[2]
    assert abs(screw_z) > fixture.SCREW.socket_corner_r


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


def test_at_most_three_fitting_steps_and_the_gear_turns_clockwise_onto_the_pin() -> (
    None
):
    numbered = [
        line for line in sheet.FITTING_STEPS.splitlines() if re.match(r"^\d+\. ", line)
    ]
    assert len(numbered) <= 3
    assert fixture.CUT_TURNS_GEAR_CLOCKWISE
    turning = [line for line in numbered if "CLOCKWISE" in line]
    assert len(turning) == 1 and "TOP VIEW" in turning[0]
    tighten = next(i for i, line in enumerate(numbered) if "TIGHTEN" in line)
    assert numbered.index(turning[0]) < tighten


def test_every_step_and_check_is_at_most_six_lines() -> None:
    for block in (sheet.KIT_STEPS, sheet.FITTING_STEPS, sheet.ASSEMBLY_CHECKS):
        steps: list[list[str]] = []
        for line in block.splitlines()[1:]:
            if re.match(r"^(K?\d+)\. ", line):
                steps.append([line])
            elif steps:
                steps[-1].append(line)
        assert steps and all(len(step) <= 6 for step in steps)


def test_the_sheet_states_the_engagement_shortfall_and_the_runout_window() -> None:
    assert fixture.SCREW_ENGAGEMENT_TEXT in sheet.FITTING_STEPS
    assert f"{fixture.SCREW_ENGAGEMENT_DIAMETERS:.2f}D" in fixture.SCREW_ENGAGEMENT_TEXT
    assert fixture.STUB_STAND_TEXT in sheet.KIT_STEPS
    assert fixture.STUB_RUNOUT_TEXT in sheet.ASSEMBLY_CHECKS
    low, high = (float(value) for value in fixture.STUB_RUNOUT_TEXT.split(" TO "))
    assert low < 2.0 * fixture.STUB_OFFSET / 25.4 < high


def test_reference_dimensions_are_the_throw_and_the_pin_station() -> None:
    expected = {
        name: value for name, (_p, _o, value, _t) in sheet.REFERENCE_DIMENSIONS.items()
    }
    assert expected == pytest.approx(
        {
            "cam throw": fixture.STUB_OFFSET,
            "clock pin height": fixture.PIN_Y,
            "clock pin offset": -fixture.PIN_X,
        }
    )
    assert sheet.REFERENCE_PLACES == 4


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
