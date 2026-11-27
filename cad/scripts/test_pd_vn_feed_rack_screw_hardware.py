"""Offline part, recipe and joint contracts for pd-vn-feed-rack-screw.

MHA-PD-VN-72 (#3738, owner ruling 2026-11-26) moves the four feed-rack
screws from 1/4 in 91794A055 to 1/2 in McMaster 91794A060 so MHA-PD-27's
counterbores drop from .469 in to .219 in deep and cut with a 1/8 in end mill.
"""

from __future__ import annotations

import pytest

import _config
import build_pd_vn_feed_rack_screw as part
import pd_feed_rack_screw_spec as spec
import pd_feed_rack_spec as rack
import pd_platen_bottom_guide_spec as guide
from _fastener_catalog import FASTENERS
from _hole_spec import THREAD_MAJOR_MM
from _mcmaster_91794a060 import FILLISTER_SIZE
from _stock_fastener import RigidTransform
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91794A060 as recipe

STEM = "pd-vn-feed-rack-screw"
IN = 25.4


def test_catalogue_and_recipe_are_the_verified_stock_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.skus == ("91794A060",)
    assert (
        stock.stock_name
        == row["stock_name"]
        == row["title"]
        == "18-8 Stainless Steel Fillister Head Slotted Screw"
    )
    assert stock.material == row["material"] == "AISI 304"
    assert row["number"] == "MHA-PD-VN-72"
    assert int(row["quantity"]) == 4
    assert row["finish"] == "passivated"
    assert row["process"] == "purchased"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == "build_91794A060"
    # #2886: a new purchased SKU models a plain shank at the thread major.
    assert metadata.threaded is False


def test_nominals_are_the_catalogue_size() -> None:
    assert spec.STEM == STEM
    assert spec.CONFIGURATION is None
    assert spec.THREAD == "#0-80"
    assert FILLISTER_SIZE == (
        spec.MAJOR_DIA,
        spec.LENGTH,
        spec.HEAD_H,
        spec.HEAD_DIA,
        spec.PITCH,
    )
    assert spec.LENGTH == pytest.approx(0.500 * IN)
    assert spec.HEAD_DIA == pytest.approx(0.096 * IN)
    assert spec.HEAD_H == pytest.approx(0.055 * IN)
    assert spec.PITCH == pytest.approx(IN / 80.0)
    assert spec.MAJOR_DIA == pytest.approx(THREAD_MAJOR_MM["#0-80"], abs=1e-3)
    assert spec.LENGTH_MIN == pytest.approx((0.500 - 0.03) * IN)
    assert (spec.UNDER_HEAD_Y, spec.TIP_Y) == pytest.approx((0.0, -0.500 * IN))
    assert spec.AXIS == (0.0, 1.0, 0.0)


def test_the_rack_and_guide_joints_read_the_half_inch_screw() -> None:
    assert rack.SCREW_LENGTH == pytest.approx(spec.LENGTH)
    assert rack.SCREW_LENGTH_MIN == pytest.approx(spec.LENGTH_MIN)
    assert rack.SCREW_FLOOR == pytest.approx(0.405 * IN)
    assert guide.SCREW_CBORE_DEPTH == pytest.approx(0.219 * IN)
    assert rack.SCREW_TIP_MARGIN == pytest.approx(0.0, abs=1e-12)
    assert rack.ENGAGEMENT_STATEMENT == "ENGAGEMENT .032 MIN (0.54D)"


def test_builder_preserves_the_supplied_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    adapter = object()
    outputs = {"sldprt": "stock-part"}

    def capture_stock(actual_adapter, **kwargs):
        assert actual_adapter is adapter
        captured.update(kwargs)
        return outputs

    monkeypatch.setattr(part, "build_stock_fastener", capture_stock)
    assert part.build(adapter) is outputs
    assert captured["part_name"] == STEM
    components = captured["components"]
    assert len(components) == 1
    assert components[0].sku == spec.SKU
    assert components[0].author is recipe.build_91794A060
    assert components[0].transform == RigidTransform()
    assert captured["screw_axis_planes"] == ("Front Plane", "Right Plane")
    assert captured["material"] == part.SPEC.material
    assert "save_threaded_part" not in captured
