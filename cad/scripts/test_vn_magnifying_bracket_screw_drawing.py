"""Offline stock and purchased-sheet contracts for MHA-VN-050."""

from __future__ import annotations

import asyncio

import pytest

import _config
import build_vn_magnifying_bracket_screw as part
import magnifying_bracket_joint_layout as joint
import vn_magnifying_bracket_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import RigidTransform
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91794A077 as recipe
from _mcmaster_91794a077 import FILLISTER_SIZE

STEM = "vn-magnifying-bracket-screw"


def test_catalogue_and_recipe_are_the_verified_stock_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.skus == ("91794A077",)
    assert stock.stock_name == row["stock_name"] == row["title"] == (
        "18-8 Stainless Steel Fillister Head Slotted Screw"
    )
    assert stock.material == row["material"] == "AISI 304"
    assert row["number"] == "MHA-VN-050"
    assert row["quantity"] == len(joint.SCREW_POSITIONS) == 2
    assert row["finish"] == "passivated"
    assert row["process"] == "purchased"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == "build_91794A077"
    assert metadata.threaded is True


def test_joint_nominals_match_the_stock_family() -> None:
    assert spec.THREAD == joint.SCREW_THREAD
    assert (spec.MAJOR_DIA, spec.LENGTH, spec.HEAD_H, spec.HEAD_DIA, spec.PITCH) == (
        joint.SCREW_MAJOR_DIA,
        joint.SCREW_LENGTH,
        joint.SCREW_HEAD_HEIGHT,
        joint.SCREW_HEAD_DIA,
        joint.SCREW_PITCH,
    )
    assert FILLISTER_SIZE == pytest.approx(
        (spec.MAJOR_DIA, spec.LENGTH, spec.HEAD_H, spec.HEAD_DIA, spec.PITCH)
    )
    assert spec.ENGAGEMENT_NOMINAL == joint.ENGAGEMENT
    assert spec.ENGAGEMENT_NOMINAL == spec.LENGTH - joint.GRIP


def test_builder_preserves_the_supplied_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    adapter = object()
    outputs = {"sldprt": "stock-part"}

    async def capture_stock(actual_adapter, **kwargs):
        assert actual_adapter is adapter
        captured.update(kwargs)
        return outputs

    monkeypatch.setattr(part, "build_stock_fastener", capture_stock)
    assert asyncio.run(part.build(adapter)) is outputs
    assert captured["part_name"] == STEM
    components = captured["components"]
    assert len(components) == 1
    assert components[0].sku == spec.SKU
    assert components[0].author is recipe.build_91794A077
    assert components[0].transform == RigidTransform()
    assert captured["screw_axis_planes"] == ("Front Plane", "Right Plane")
    assert captured["material"] == part.SPEC.material


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_vn_magnifying_bracket_screw as drawing

    sheet = DRAWINGS_BY_NAME["vn_magnifying_bracket_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
