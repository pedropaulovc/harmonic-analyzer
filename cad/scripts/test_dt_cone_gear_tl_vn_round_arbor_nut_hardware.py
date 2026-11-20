"""Offline part, recipe and fit contracts for dt-cone-gear-tl-vn-round-arbor-nut.

Delivered as its HARDWARE.md row (tier 1, no sheet, like MHA-DT-03-TL-VN-50);
these checks pin the part, its catalogue facts and its fit on the round arbor.
"""

from __future__ import annotations

import math

import pytest

import _config
import build_dt_cone_gear_tl_vn_round_arbor_nut as part
import dt_cone_gear_tl_vn_round_arbor_nut_spec as spec
import hardware_schedule
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_90480A009 as recipe

STEM = "dt-cone-gear-tl-vn-round-arbor-nut"
NUMBER = "MHA-DT-03-TL-VN-51"
STOCK_NAME = "Low-Strength Zinc-Plated Steel Hex Nut"
BUILD = "build_90480A009"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_part() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.PART_NAME == STEM
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("90480A009",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == STOCK_NAME
    assert stock.material == row["material"] == part.MATERIAL == "Plain Carbon Steel"
    assert row["finish"] == "zinc plated"
    assert row["number"] == NUMBER
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == 1
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is getattr(recipe, BUILD)
    assert metadata.threaded is False


def test_it_ships_as_a_tier_1_hardware_row_without_a_sheet() -> None:
    row = hardware_schedule.SCHEDULE[STEM]
    pen_nut = hardware_schedule.SCHEDULE["pn-vn-pen-hanger-nut"]
    for field in ("why", "designation", "standard", "envelope"):
        assert row[field] == pen_nut[field], field
    assert row["standard"] == "ASME B18.6.3"
    assert row["designation"].startswith("#8-32 UNC-2B hex machine screw nut")
    assert set(row["envelope"]) == {"AC", "T"}
    assert hardware_schedule.envelope_mm(row["envelope"]["AC"]) == pytest.approx(
        spec.ACROSS_CORNERS
    )
    assert hardware_schedule.envelope_mm(row["envelope"]["T"]) == pytest.approx(
        spec.THICKNESS
    )
    assert STEM.replace("-", "_") not in DRAWINGS_BY_NAME


def test_spec_carries_the_catalogue_facts() -> None:
    """McMaster 90480A009 (``_mcmaster_90480a009``): ASME B18.6.3 #8-32
    machine screw nut, 11/32 wide, 1/8 high."""
    assert spec.THREAD == "#8-32"
    assert spec.ACROSS_FLATS == pytest.approx(11.0 / 32.0 * IN)
    assert spec.THICKNESS == pytest.approx(1.0 / 8.0 * IN)
    # The thread is not modelled: the bore is the rounded #8-32 major.
    assert spec.BORE_DIA == pytest.approx(0.164 * IN, abs=1e-3)
    assert spec.ACROSS_CORNERS == pytest.approx(
        spec.ACROSS_FLATS / math.cos(math.pi / 6)
    )
    assert spec.MASS_G == pytest.approx(spec.nut_volume() * 7.8e-3)


def test_stock_build_turns_the_recipe_axis_onto_part_z(monkeypatch) -> None:
    seen: dict = {}

    def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    part.build(None)
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is getattr(recipe, BUILD)
    assert component.transform.rotation_radians == pytest.approx(
        (math.pi / 2.0, 0.0, 0.0)
    )
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert seen["part_name"] == STEM
    assert seen["material"] == part.SPEC.material
    assert seen.get("color") is None
    assert seen["screw_axis_planes"] == ("Top Plane", "Right Plane")


def test_the_nut_clamps_the_collar_on_full_thread_under_t024s_root() -> None:
    """The nut matches the arbor's #8-32 schematic thread, bears on the
    collar's face, and its corners stand under T024's root by the air."""
    import dt_cone_gear_tl_round_arbor_spec as arbor

    assert spec.THREAD == arbor.THREAD
    assert spec.BORE_DIA == pytest.approx(arbor.THREAD_MAJOR, abs=1e-3)
    assert spec.ACROSS_FLATS == pytest.approx(arbor.NUT_ACROSS_FLATS)
    assert spec.THICKNESS <= arbor.NUT_THICKNESS_MAX
    assert spec.ACROSS_CORNERS / 2.0 + arbor.AIR_MIN <= arbor.BLANK.root_min_dia / 2.0
    assert spec.ACROSS_FLATS > arbor.COLLAR_BORE
    assert arbor.THREAD_PAST_NUT_MIN >= 1.5 * arbor.THREAD_PITCH
    assert arbor.NUT_THREAD_MARGIN > 0.0
