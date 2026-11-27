"""The small lathe parts are held in brass split bushes, never in the jaws.

The 3-jaw closes no smaller than Ø.175 and the 4-jaw no smaller than Ø.2865
(the owner's least grips, 2026-11-24; ``cad/process/shop/common.toml``
``workholding.chuck-3jaw-6`` and ``chuck-4jaw-6``). The crank pinion pin's
Ø.125 rod (#3498), the pinion cam pin's Ø.156 rod (#3499) and the cone tip
end screw's .249 crests (#3496) are under them, so each plan makes a split
bush of the 1/2 in brass bar on hand and holds the part in it (delegated
ruling 2026-11-27 (Main), no precedent (pattern: the transgear pin's split
bush, #3494); owner review #2144 (D57)). These tests hold the plans to that: no lathe
setup grips the part, the bush lies in its chuck's range, and its hole takes
the part with a clearance the slit closes.
"""

from __future__ import annotations

import tomllib

import pytest

import _mcmaster_91794a559
import _process_plans
import _shop_equipment
import export_features

IN = 25.4
SHOP = _process_plans.load_shop()
STOCK = _shop_equipment.load()["stock"]
BUSH_STOCK = "c360-round-1-2"
# The chuck each plan holds its bush in.
HELD = {
    "dt_crank_pinion_pin": "chuck-3jaw-6",
    "dt_pinion_cam_pin": "chuck-3jaw-6",
    "dt_cone_tip_end_screw": "chuck-4jaw-6",
}
# The bought screw keeps its registry SKU on the stock BOM: a stock_refs entry
# would replace it, so its plan names the bush's bar in its stock line only.
BOUGHT = {"dt_cone_tip_end_screw"}


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


def _largest_dia_mm(stem: str) -> float:
    """The part's largest diameter where the bush closes on it."""
    if stem == "dt_cone_tip_end_screw":
        return _mcmaster_91794a559.THREAD_MAJOR_MAX_MM
    outer = export_features.requirement_manifest(stem)["features"]["outer"]
    return outer["dia"][1] if "dia" in outer else outer["dia_ref"]


def _bush_setup(plan: dict) -> dict:
    (setup,) = [
        setup for setup in plan["setups"] if setup["title"].startswith("Split bush")
    ]
    return setup


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
    assert STOCK[BUSH_STOCK]["status"] == "on_hand"
    assert STOCK[BUSH_STOCK]["dia_in"] == [plan["parameters"]["bush_dia_in"]]
    if stem in BOUGHT:
        assert "stock_refs" not in plan
        assert "C360 brass bar on hand" in plan["stock"]
    else:
        assert BUSH_STOCK in plan["stock_refs"]


@pytest.mark.parametrize("stem", sorted(HELD))
def test_the_bush_hole_takes_the_part_with_a_clearance_the_slit_closes(
    stem: str,
) -> None:
    plan = _plan(stem)
    tools = {tool["id"]: tool["ref"] for tool in plan["tools"]}
    ops = _bush_setup(plan)["operations"]
    refs = [
        tools[op["tool"]]
        for op in ops
        if "tool" in op
        and (
            op.get("drilling") == "twist_drill"
            or tools[op["tool"]].startswith("reamer-")
        )
    ]
    # The last tool through sizes the hole; it goes through the whole bush.
    hole = SHOP["tools"][refs[-1]]["diameter_mm"]
    clearance = hole - _largest_dia_mm(stem)
    assert 0 < clearance <= 0.005 * IN, refs[-1]
    slit = [op for op in ops if tools.get(op.get("tool")) == "junior-hacksaw"]
    assert len(slit) == 1 and "slit" in slit[0]["instruction"]


@pytest.mark.parametrize(
    "stem", sorted(stem for stem, chuck in HELD.items() if chuck == "chuck-3jaw-6")
)
def test_the_3jaw_never_grips_the_part(stem: str) -> None:
    plan = _plan(stem)
    lathe = [setup for setup in plan["setups"] if setup["machine_kind"] == "lathe"]
    assert len(lathe) >= 3
    for setup in lathe:
        hold = setup["lathe_hold"]
        assert hold["chuck"] == "chuck-3jaw-6", setup["title"]
        assert hold["grip_diameter_mm"] == "{{process.bush_dia_mm}}", setup["title"]
        assert "split bush" in setup["holding"] or setup is _bush_setup(plan)


def test_the_screw_is_dialled_in_the_bush_in_the_4jaw() -> None:
    plan = _plan("dt_cone_tip_end_screw")
    bush = _bush_setup(plan)
    (held,) = [
        setup
        for setup in plan["setups"]
        if setup["machine_kind"] == "lathe" and setup is not bush
    ]
    assert "split bush" in held["holding"]
    assert "never touch the thread" in held["holding"]
    dial = held["operations"][0]
    assert ".0005" in dial["inspection"] and "gauge block" in dial["instruction"]


def test_the_screw_bush_is_faced_clear_of_the_jaws() -> None:
    plan = _plan("dt_cone_tip_end_screw")
    bush = _bush_setup(plan)
    assert plan["parameters"]["bush_face_out_in"] > 0
    assert (
        "{{process.bush_face_out_in:.2dot}} in out of the jaw fronts"
        in (bush["holding"])
    )
