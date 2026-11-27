"""Every taped hold declares the one accepted bond the shop records.

Owner ruling 2026-11-23: the taped parts hold on blue painter's tape on both
faces with CA glue between, and the hold is taken as given. Its strength is
therefore accepted, not read from a data sheet:
``consumables.hold-painters-tape-ca`` carries the accepted stresses and the
tape stack, and each plan repeats them. A plan that types its own figure, or
keeps a data-sheet derating, would have prechips' bond check judge its cuts
against something the record does not say.
"""

from __future__ import annotations

import tomllib

import pytest

import _process_plans
import _shop_equipment

HOLD = _shop_equipment.load()["consumables"]["hold-painters-tape-ca"]
STEMS = (
    "ch_rocker_strap",
    "dt_cone_gear_tl_phasing_comb",
    "dt_pinion_spring",
    "ms_stick",
    "pd_platen",
    "pd_platen_clip",
    "pd_transgear_arm_plate",
)


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


def _bonds(plan: dict) -> list[dict]:
    holders = [
        holder for setup in plan["setups"] for holder in (setup, *setup["operations"])
    ]
    beams = [holder.get("beam") for holder in holders]
    return [beam["bond"] for beam in beams if isinstance(beam, dict) and "bond" in beam]


def test_the_record_accepts_a_strength_and_a_measurable_stack() -> None:
    consumables = _shop_equipment.load()["consumables"]
    for part in ("tape", "adhesive", "accelerator"):
        assert consumables[HOLD[part]]["status"] == "on_hand"
    assert HOLD["accepted_shear_kpa"] > 0 and HOLD["accepted_tensile_kpa"] > 0
    assert HOLD["accepted_by"].strip()
    assert HOLD["stack_min_mm"] < HOLD["stack_thickness_mm"] < HOLD["stack_max_mm"]
    # Two tapes at the listing's thickness; the glue line is what is over.
    two_tapes = 2 * consumables[HOLD["tape"]]["thickness_mm"]
    assert HOLD["stack_min_mm"] < two_tapes <= HOLD["stack_thickness_mm"]
    assert "tape-3m-vhb-5906" not in consumables


@pytest.mark.parametrize("stem", STEMS)
def test_a_taped_plan_repeats_the_record(stem: str) -> None:
    plan = _plan(stem)
    p = plan["parameters"]
    assert p["tape_stack_mm"] == HOLD["stack_thickness_mm"]
    assert p["tape_stack_min_mm"] == HOLD["stack_min_mm"]
    assert p["tape_stack_max_mm"] == HOLD["stack_max_mm"]
    assert p["bond_accepted_shear_mpa"] * 1000 == pytest.approx(
        HOLD["accepted_shear_kpa"]
    )
    assert p["bond_accepted_tensile_mpa"] * 1000 == pytest.approx(
        HOLD["accepted_tensile_kpa"]
    )
    stale = {"tape_shear_mpa", "tape_tensile_mpa", "bond_derating"}
    assert not stale & p.keys()
    # A prechips adapter's own name for the stack under the blank (arc_strap).
    assert p.get("tape_thickness_mm", p["tape_stack_mm"]) == p["tape_stack_mm"]
    bonds = _bonds(plan)
    assert bonds
    for bond in bonds:
        assert bond["shear_mpa"] == "{{process.bond_accepted_shear_mpa}}"
        assert bond["tensile_mpa"] == "{{process.bond_accepted_tensile_mpa}}"
        assert bond["accepted_by"] == HOLD["accepted_by"]
        assert "derating" not in bond
    refs = {tool.get("ref") for tool in plan["tools"]}
    assert {HOLD["tape"], HOLD["adhesive"], HOLD["accelerator"]} <= refs
    text = _process_plans.plan_path(stem).read_text(encoding="utf-8")
    assert "VHB" not in text and "5906" not in text
