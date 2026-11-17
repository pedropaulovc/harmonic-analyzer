"""Offline contract for the rocker-strap sub-plate fixture (MHA-CH-13-TL-00).

The kit spec mirrors a few strap-plan values (tape, clamp torque, the 1 in
parallels) and the strap's thickness, so no COM leaf reads the plan or the
rocker arm's spec; these tests hold the mirrors to their sources. They also
pin the interference table's literal thread annuli to the part specs and the
sheet's words to the BOM.
"""

from __future__ import annotations

import ast
import math
import tomllib
from pathlib import Path

import pytest

import _ch_rocker_strap_tl_fixture_interference as interference
import ch_rocker_arm_spec as arm
import ch_rocker_strap_tl_fixture_spec as spec
import draw_ch_rocker_strap_tl_fixture_assembly as drawing
from _machinist_review_mode import MachinistReviewMode, mode_for_drawing

SCRIPTS = Path(__file__).resolve().parent
PLAN = SCRIPTS.parent / "process" / "ch_rocker_strap" / "plan.toml"
BUILDER = SCRIPTS / "build_ch_rocker_strap_tl_fixture_assembly.py"
INCH = 25.4


@pytest.fixture(scope="module")
def plan() -> dict:
    with PLAN.open("rb") as handle:
        return tomllib.load(handle)["parameters"]


def test_mirrors_agree_with_the_strap_plan_and_the_rocker_arm(plan: dict) -> None:
    assert spec.TAPE == plan["tape_thickness_mm"]
    assert spec.CLAMP_TORQUE_FT_LB == plan["clamp_torque_ft_lb"]
    assert plan["parallel_height_mm"] == pytest.approx(1.0 * INCH)
    assert "ON 1 IN PARALLELS" in spec.ASSEMBLY_STEPS.replace("\n", " ")
    assert spec.STRAP_THICKNESS == pytest.approx(arm.ARM_THICKNESS)


def test_kit_poses_put_the_hub_and_the_clamps_on_the_plan_stations(plan: dict) -> None:
    # The plan states the hub's Y as a distance toward the operator from Y0.
    assert spec.HUB == pytest.approx((plan["hub_x_mm"], -plan["hub_y_mm"]))
    assert tuple(p[0] for p in spec.CLAMP_POSITIONS) == pytest.approx(
        tuple(plan[f"clamp_{i}_x_mm"] for i in range(1, 5))
    )


def test_builder_inserts_the_parts_in_bom_order() -> None:
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    inserted = [
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "place_component"
        and isinstance(node.args[1], ast.Constant)
    ]
    # ast.walk visits in breadth-first order within one function body, which
    # keeps source order for these sibling statements (the loop's call last
    # among them is the clamp's).
    assert sorted(inserted, key=spec.BOM_ORDER.index) == list(spec.BOM_ORDER)
    assert set(inserted) == set(spec.BOM_ORDER)


def test_interference_literals_match_the_parts() -> None:
    plate = spec.plate
    under_pocket = plate.POCKET_FLOOR_Z - plate.UNDERSIDE_Z
    under_counterbore = plate.COUNTERBORE_FLOOR_Z - plate.UNDERSIDE_Z
    assert interference.CLAMP_SCREW_THREAD[2] == pytest.approx(under_pocket, abs=1e-4)
    assert interference.HUB_SCREW_THREAD[2] == pytest.approx(
        under_counterbore, abs=1e-4
    )
    assert interference.HUB_SCREW_THREAD[0] == pytest.approx(0.25 * INCH)
    assert interference.HUB_SCREW_THREAD[1] == pytest.approx(0.201 * INCH)
    assert interference.CLAMP_SCREW_THREAD[1] == pytest.approx(0.089 * INCH)
    # Each screw reaches through the plate's underside, so its engaged length
    # is the plate's whole thickness there.
    assert spec.clamp.SCREW_TIP_DEPTH > under_pocket
    screw_tip_z = spec.SCREW_POSITION[2] - spec.HUB_SCREW_LENGTH
    assert screw_tip_z < plate.UNDERSIDE_Z
    assert len(interference.ALLOWED_PAIRS) == 5


def test_stack_stays_inside_the_strap_programs_hub_keep_out(plan: dict) -> None:
    assert spec.washer.OUTER_DIA + 0.01 * INCH <= plan["bushing_flange_dia_mm"]
    stack = spec.washer.THICKNESS + spec.HUB_SCREW_HEAD_HEIGHT
    assert stack <= plan["bushing_stack_height_mm"]


def test_sheet_words_cite_real_items() -> None:
    assert mode_for_drawing(Path(drawing.__file__)) is MachinistReviewMode.LEARN
    for row in spec.SCREW_TABLE_ROWS:
        assert len(row) == len(spec.SCREW_TABLE_HEADER)
        assert row[0] in spec.BOM_ITEMS.values()
    cited = {
        word.rstrip(".,;:'S")
        for line in spec.ASSEMBLY_STEPS.splitlines()
        for word in line.split("ITEM ")[1:]
    }
    assert {c.split()[0].rstrip(".,;:'S") for c in cited} <= set(
        spec.BOM_ITEMS.values()
    )
    for line in spec.ASSEMBLY_STEPS.splitlines():
        assert len(line) <= spec.STEP_WIDTH


def test_every_step_prints_in_at_most_six_lines() -> None:
    steps: list[int] = []
    for line in spec.ASSEMBLY_STEPS.splitlines()[1:]:
        if line[:1].isdigit():
            steps.append(1)
        else:
            steps[-1] += 1
    assert steps and max(steps) <= 6


def test_exploded_items_clear_what_they_go_on() -> None:
    offsets = drawing.EXPLODE_OFFSETS_MM
    plug_bottom = spec.PLUG_POSITION[2] + offsets[spec.PLUG][2]
    assert plug_bottom >= spec.plate.FENCE_HEIGHT
    plug_top = plug_bottom + spec.plug.OVERALL_LENGTH
    washer_bottom = spec.WASHER_POSITION[2] + offsets[spec.WASHER][2]
    assert washer_bottom > plug_top
    screw_tip = spec.SCREW_POSITION[2] + offsets[spec.SCREW][2] - spec.HUB_SCREW_LENGTH
    assert screw_tip > washer_bottom + spec.washer.THICKNESS
    clamp_tip = (
        spec.CLAMP_POSITIONS[0][2] + offsets[spec.CLAMP][2] - spec.clamp.SCREW_TIP_DEPTH
    )
    assert clamp_tip > spec.plate.FENCE_HEIGHT
    assert math.isclose(offsets[spec.PLATE][2], 0.0)
