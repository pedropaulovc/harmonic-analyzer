"""The MHA-PN-04 pen rod's 4-jaw packing brings its square inside the chuck.

The 6 in 4-jaw closes no smaller than Ø.2865 (the owner's least grip,
2026-11-24; ``cad/process/shop/common.toml`` ``workholding.chuck-4jaw-6``)
and the rod's square is .1950-.1970 across its flats (#3495), so each jaw
bears on a soft packing strip on its flat (delegated ruling 2026-11-27
(Main), precedent: the transgear pin's split bush, #3494; owner review
#2144 (D57)). These tests hold the plan's strip thickness and width to the
chuck and the drawing's square.
"""

from __future__ import annotations

import tomllib

import pytest

import _process_plans
import _shop_equipment
import export_features

STEM = "pn_pen_rod"
IN = 25.4


@pytest.fixture(scope="module")
def plan() -> dict:
    return tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def square_in() -> list[float]:
    flats = export_features.requirement_manifest(STEM)["features"]["flat_x_pos"]
    return [across / IN for across in flats["across"]]


def test_the_thinnest_strips_bring_the_smallest_square_over_the_least_grip(
    plan: dict, square_in: list[float]
) -> None:
    least_grip_in = (
        _process_plans.load_shop()["workholding"]["chuck-4jaw-6"]["grip_range_mm"][0]
        / IN
    )
    parameters = plan["parameters"]
    assert square_in[0] < least_grip_in
    # .1950 + 2 x .050 = .295: .0085 over the .2865 least grip.
    assert square_in[0] + 2 * parameters["packing_min_in"] - least_grip_in > 0.005


def test_a_strip_is_narrower_than_a_flat_and_lies_flat(
    plan: dict, square_in: list[float]
) -> None:
    parameters = plan["parameters"]
    # Narrower than the smallest flat: strips on neighbouring flats never meet.
    assert parameters["packing_width_max_in"] < square_in[0]
    # No thicker than about 2/3 of the widest strip, so it does not roll.
    assert parameters["packing_max_in"] <= parameters["packing_width_max_in"] * 0.7
    assert parameters["packing_min_in"] < parameters["packing_max_in"]


def test_the_offcut_example_lies_in_the_range(plan: dict) -> None:
    stock = _shop_equipment.load()["stock"]["c260-sheet-063-6x6"]
    thickness_in = stock["section_mm"][1] / IN
    parameters = plan["parameters"]
    assert parameters["packing_min_in"] <= thickness_in <= parameters["packing_max_in"]
    # A strip from the offcut, not an allocation of the sheet.
    assert plan["stock_refs"] == ["c360-square-5mm-key"]


def test_both_4jaw_setups_hold_over_the_strips_and_are_indicated(plan: dict) -> None:
    lathe = [setup for setup in plan["setups"] if setup["machine_kind"] == "lathe"]
    assert len(lathe) == 2
    for setup in lathe:
        assert "packing strip" in setup["holding"]
        assert "shim" not in setup["holding"]
        assert (
            "{{process.indicate_tir_in:.3dot}} TIR"
            in setup["operations"][0]["inspection"]
        )
