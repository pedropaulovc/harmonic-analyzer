"""The turned parts' lathe travelers agree with their models and shop records.

Each ``cad/process/<stem>/plan.toml`` here is a prechips ``turned_bush``
adapter plan: the adapter binds every printed size, band and station, the
drawing number and revision from the part's feature export (prechips is not
an HA dependency; the adapter's own tests hold its bindings). Here each plan
is held to what prechips cannot see: the drill it names lands inside the
drawing's hole band (from the drawing's requirement manifest, so no
SolidWorks seat), and every bar it turns from is a stock record of that
diameter.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import _process_plans
import export_features

ROOT = Path(__file__).resolve().parents[2]
EQUIPMENT = ROOT / "cad" / "config" / "shop-equipment"
STEMS = tuple(
    stem
    for stem in _process_plans.TRAVELER_STEMS
    if tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))[
        "cad"
    ].get("adapter")
    == "turned_bush"
)
SHOP = _process_plans.load_shop()


def _stock() -> dict:
    records: dict = {}
    for name in ("stock-bought.toml", "stock-to-order.toml"):
        data = tomllib.loads((EQUIPMENT / name).read_text(encoding="utf-8"))
        records |= data.get("stock", {})
    return records


STOCK = _stock()


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


def _drills(plan: dict) -> list[str]:
    tools = {tool["id"]: tool for tool in plan["tools"]}
    return [
        tools[op["tool"]]["ref"]
        for setup in plan["setups"]
        for op in setup.get("operations", ())
        if op.get("drilling") == "twist_drill"
    ]


# A plan that drills must land its drill in the drawing's bore band; the
# sawn-and-faced pins drill nothing.
DRILLED = tuple(stem for stem in STEMS if _drills(_plan(stem)))


def test_the_turned_parts_are_enrolled() -> None:
    assert set(STEMS) >= {
        "ch_rocker_hub",
        "ch_rocker_strap_tl_hub_washer",
        "dt_cone_gear_tl_arbor_collar",
        "dt_crank_handle_ferrule",
    }


@pytest.mark.parametrize("stem", STEMS)
def test_plan_binds_the_part_from_its_feature_export(stem: str) -> None:
    plan = _plan(stem)
    assert plan["cad"] == {
        "file": f"../../out/features/{stem}/features.toml",
        "adapter": "turned_bush",
        "part": stem.replace("_", "-"),
    }
    assert (plan["part"], plan["revision"]) == (
        "{{cad.drawing_number}}",
        "{{cad.revision}}",
    )


@pytest.mark.parametrize("stem", DRILLED)
def test_the_drill_lands_in_the_drawings_hole_band(stem: str) -> None:
    band = export_features.requirement_manifest(stem)["features"]["bore"]["dia"]
    for ref in _drills(_plan(stem)):
        assert band[0] <= SHOP["tools"][ref]["diameter_mm"] <= band[1], ref


@pytest.mark.parametrize("stem", STEMS)
def test_every_bar_is_a_stock_record_of_its_diameter(stem: str) -> None:
    plan = _plan(stem)
    bars = {
        value
        for key, value in plan["parameters"].items()
        if key.startswith("stock_dia") and key.endswith("_in")
    }
    recorded = {STOCK[ref]["dia_in"][0] for ref in plan["stock_refs"]}
    for ref in plan["stock_refs"]:
        assert STOCK[ref]["form"] == "round_bar", ref
    assert bars == recorded
