"""Offline part, recipe and joint contracts for pd-vn-transgear-knob-cup-screw.

MHA-PD-VN-71 (#2425, owner ruling 2026-11-20 (Pedro)) replaces the retired
MHA-PD-VN-62 cup pin: one #2-56 x 3/8 fillister through the MHA-PD-16 cup's
web into the MHA-PD-08 journal's rear tap.
"""

from __future__ import annotations

import pytest

import _config
import build_pd_vn_transgear_knob_cup_screw as part
import pd_transgear_knob_cup_spec as cup
import pd_vn_transgear_knob_cup_screw_spec as spec
from _fastener_catalog import FASTENERS
from _hole_spec import THREAD_MAJOR_MM
from _mcmaster_91794a079 import FILLISTER_SIZE
from _stock_fastener import RigidTransform
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91794A079 as recipe

STEM = "pd-vn-transgear-knob-cup-screw"
IN = 25.4


def test_catalogue_and_recipe_are_the_verified_stock_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.skus == ("91794A079",)
    assert (
        stock.stock_name
        == row["stock_name"]
        == row["title"]
        == "18-8 Stainless Steel Fillister Head Slotted Screw"
    )
    assert stock.material == row["material"] == "AISI 304"
    assert row["number"] == "MHA-PD-VN-71"
    assert int(row["quantity"]) == 1
    assert row["finish"] == "passivated"
    assert row["process"] == "purchased"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == "build_91794A079"
    assert metadata.threaded is True


def test_nominals_are_the_catalogue_size() -> None:
    assert spec.THREAD == "#2-56"
    assert FILLISTER_SIZE == (
        spec.MAJOR_DIA,
        spec.LENGTH,
        spec.HEAD_H,
        spec.HEAD_DIA,
        spec.PITCH,
    )
    assert spec.LENGTH == pytest.approx(0.375 * IN)
    assert spec.HEAD_DIA == pytest.approx(0.140 * IN)
    assert spec.HEAD_H == pytest.approx(0.083 * IN)
    assert spec.PITCH == pytest.approx(IN / 56.0)
    assert spec.MAJOR_DIA == pytest.approx(THREAD_MAJOR_MM["#2-56"], abs=1e-3)
    # ASME B18.6.3: -.03 on length, R .15D under-head fillet, 2P point.
    assert spec.LENGTH_MIN == pytest.approx((0.375 - 0.03) * IN)
    assert spec.UNDER_HEAD_FILLET_ENVELOPE_DIA == pytest.approx(1.3 * spec.MAJOR_DIA)
    assert spec.POINT_CHAMFER_LENGTH_MAX == pytest.approx(2.0 * spec.PITCH)


def test_the_cup_joint_reads_this_spec() -> None:
    """The joint's checks live in the cup spec, which imports this one (the
    screw spec reads no part, so no import cycle)."""
    assert cup.SCREW is spec
    assert cup.SCREW_ENGAGEMENT_MIN_D >= 1.5
    assert cup.SCREW_TIP_SHORT_OF_FULL_THREAD_MIN > 0.0
    assert cup.HEAD_BELOW_REAR_FACE_MIN >= 0.0


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
    assert components[0].author is recipe.build_91794A079
    assert components[0].transform == RigidTransform()
    assert captured["screw_axis_planes"] == ("Front Plane", "Right Plane")
    assert captured["material"] == part.SPEC.material
