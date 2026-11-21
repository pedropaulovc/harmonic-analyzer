"""The sawn-and-faced pins' lathe travelers agree with their models and stock.

``dt_crank_pinion_pin`` and ``dt_pinion_handle`` are cut from rod used as
supplied on the diameter: a piece is sawn and each end faced in the 3-jaw.
prechips binds the sizes and screens the stickout; these tests hold what it
cannot see: the sawn piece leaves the facing allowances over the drawing's
length, and the rod is a stock record of the drawing's reference diameter.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import _process_plans
import export_features

ROOT = Path(__file__).resolve().parents[2]
EQUIPMENT = ROOT / "cad" / "config" / "shop-equipment"
IN = 25.4
# The ends sawn before facing: the handle's piece is sawn at both ends, the
# pin's off a rod end faced first (Setup 1).
SAWN_ENDS = {"dt_crank_pinion_pin": 1, "dt_pinion_handle": 2}


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


def _stock() -> dict:
    records: dict = {}
    for name in ("stock-bought.toml", "stock-to-order.toml"):
        records |= tomllib.loads((EQUIPMENT / name).read_text(encoding="utf-8"))[
            "stock"
        ]
    return records


@pytest.mark.parametrize("stem", sorted(SAWN_ENDS))
def test_the_pins_are_enrolled_on_turned_bush(stem: str) -> None:
    assert stem in _process_plans.TRAVELER_STEMS
    assert _plan(stem)["cad"]["adapter"] == "turned_bush"


@pytest.mark.parametrize("stem", sorted(SAWN_ENDS))
def test_the_sawn_piece_leaves_each_sawn_end_its_facing(stem: str) -> None:
    parameters = _plan(stem)["parameters"]
    far = export_features.requirement_manifest(stem)["features"]["far_end"]
    allowance = parameters["regrip_allowance_in"]
    if SAWN_ENDS[stem] == 2:
        allowance += parameters["face_allowance_in"]
    assert parameters["saw_length_in"] == pytest.approx(
        far["length_nominal"] / IN + allowance, abs=1e-3
    )
    assert parameters["saw_length_in"] * IN > far["length"][1]


@pytest.mark.parametrize("stem", sorted(SAWN_ENDS))
def test_the_rod_is_a_stock_record_of_the_drawings_diameter(stem: str) -> None:
    plan = _plan(stem)
    (ref,) = plan["stock_refs"]
    record = _stock()[ref]
    outer = export_features.requirement_manifest(stem)["features"]["outer"]
    assert record["form"] == "round_bar"
    assert record["dia_in"] == [plan["parameters"]["stock_dia_in"]]
    assert plan["parameters"]["stock_dia_in"] * IN == pytest.approx(outer["dia_ref"])
