"""The small lathe parts are held in brass split bushes, never in the jaws.

The 3-jaw closes no smaller than Ø.175 and the 4-jaw no smaller than Ø.2865
(the owner's least grips, 2026-11-24; ``cad/process/shop/common.toml``
``workholding.chuck-3jaw-6`` and ``chuck-4jaw-6``). The crank pinion pin's
Ø.125 rod (#3498), the pinion cam pin's Ø.156 rod (#3499) and the cone tip
end screw's .249 crests (#3496) are under them, so each plan makes a split
bush of the 1/2 in brass bar on hand, as the transgear pin's does (#3494),
and holds the part in it (delegated ruling 2026-11-27 (Main); owner review
#2144 (D57)). These tests hold the plans to that: every lathe setup after the
bush grips the bush, the bush lies in its chuck's range, and its hole takes
the part with a clearance the slit closes.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import _mcmaster_91794a559
import _process_plans
import export_features

IN = 25.4
EQUIPMENT = Path(__file__).resolve().parents[2] / "cad" / "config" / "shop-equipment"
SHOP = _process_plans.load_shop()
STOCK = tomllib.loads((EQUIPMENT / "stock-bought.toml").read_text(encoding="utf-8"))[
    "stock"
]
BUSH_STOCK = "c360-round-1-2"
# The plan's chuck, and the part's largest diameter where the bush closes.
HELD = {
    "dt_crank_pinion_pin": "chuck-3jaw-6",
    "dt_pinion_cam_pin": "chuck-3jaw-6",
    "dt_cone_tip_end_screw": "chuck-4jaw-6",
}


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


def _largest_dia_mm(stem: str) -> float:
    if stem == "dt_cone_tip_end_screw":
        return _mcmaster_91794a559.THREAD_MAJOR_MAX_MM
    outer = export_features.requirement_manifest(stem)["features"]["outer"]
    return outer["dia"][1] if "dia" in outer else outer["dia_ref"]


def _bush_setup_index(plan: dict) -> int:
    (index,) = [
        i
        for i, setup in enumerate(plan["setups"])
        if setup["title"].startswith("Split bush")
    ]
    return index


@pytest.mark.parametrize("stem", sorted(HELD))
def test_the_part_is_under_its_chucks_least_grip_and_the_bush_inside_it(
    stem: str,
) -> None:
    grip = SHOP["workholding"][HELD[stem]]["grip_range_mm"]
    parameters = _plan(stem)["parameters"]
    assert _largest_dia_mm(stem) < grip[0]
    assert grip[0] <= parameters["bush_dia_mm"] <= grip[1]
    assert parameters["bush_dia_mm"] == pytest.approx(parameters["bush_dia_in"] * IN)
    assert parameters["bush_length_mm"] == pytest.approx(
        parameters["bush_length_in"] * IN
    )


@pytest.mark.parametrize("stem", sorted(HELD))
def test_the_bush_is_cut_from_the_brass_bar_on_hand(stem: str) -> None:
    plan = _plan(stem)
    assert BUSH_STOCK in plan["stock_refs"]
    assert STOCK[BUSH_STOCK]["status"] == "on_hand"
    assert STOCK[BUSH_STOCK]["dia_in"] == [plan["parameters"]["bush_dia_in"]]


@pytest.mark.parametrize("stem", sorted(HELD))
def test_the_bush_hole_takes_the_part_with_a_clearance_the_slit_closes(
    stem: str,
) -> None:
    plan = _plan(stem)
    tools = {tool["id"]: tool["ref"] for tool in plan["tools"]}
    setup = plan["setups"][_bush_setup_index(plan)]
    refs = [
        tools[op["tool"]]
        for op in setup["operations"]
        if op.get("drilling") == "twist_drill"
        or tools[op["tool"]].startswith("reamer-")
    ]
    # The last tool through sizes the hole; it goes through the whole bush.
    hole = SHOP["tools"][refs[-1]]["diameter_mm"]
    clearance = hole - _largest_dia_mm(stem)
    assert 0 < clearance <= 0.005 * IN, refs[-1]
    slit = [op for op in setup["operations"] if tools[op["tool"]] == "junior-hacksaw"]
    assert len(slit) == 1 and "slit" in slit[0]["instruction"]


@pytest.mark.parametrize(
    "stem", sorted(stem for stem, chuck in HELD.items() if chuck == "chuck-3jaw-6")
)
def test_the_3jaw_never_grips_the_part(stem: str) -> None:
    plan = _plan(stem)
    lathe = [
        setup
        for setup in plan["setups"][_bush_setup_index(plan) :]
        if setup["machine_kind"] == "lathe"
    ]
    assert len(lathe) >= 3
    for setup in lathe:
        hold = setup["lathe_hold"]
        assert hold["chuck"] == "chuck-3jaw-6", setup["title"]
        assert hold["grip_diameter_mm"] == "{{process.bush_dia_mm}}", setup["title"]
        assert "split bush" in setup["holding"] or setup["title"].startswith(
            "Split bush"
        )


def test_the_screw_is_dialled_in_the_bush_in_the_4jaw() -> None:
    plan = _plan("dt_cone_tip_end_screw")
    bush = _bush_setup_index(plan)
    (held,) = [
        setup
        for setup in plan["setups"][bush + 1 :]
        if setup["machine_kind"] == "lathe"
    ]
    assert "split bush" in held["holding"]
    assert "never touch the thread" in held["holding"]
    dial = held["operations"][0]
    assert ".0005" in dial["inspection"] and "gauge block" in dial["instruction"]
