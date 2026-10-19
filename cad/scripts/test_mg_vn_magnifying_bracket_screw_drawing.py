"""Offline stock and purchased-sheet contracts for MHA-MG-VN-53."""

from __future__ import annotations

import asyncio
from fractions import Fraction
import re

import pytest

import _config
import build_mg_vn_magnifying_bracket_screw as part
import magnifying_bracket_joint_layout as joint
import mg_vn_magnifying_bracket_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import RigidTransform
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91794A078 as recipe
from _mcmaster_91794a078 import FILLISTER_SIZE

STEM = "mg-vn-magnifying-bracket-screw"


def test_catalogue_and_recipe_are_the_verified_stock_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.skus == ("91794A078",)
    assert stock.stock_name == row["stock_name"] == row["title"] == (
        "18-8 Stainless Steel Fillister Head Slotted Screw"
    )
    assert stock.material == row["material"] == "AISI 304"
    assert row["number"] == "MHA-MG-VN-53"
    assert row["quantity"] == len(joint.SCREW_POSITIONS) == 2
    assert row["finish"] == "passivated"
    assert row["process"] == "purchased"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == "build_91794A078"
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
    assert components[0].author is recipe.build_91794A078
    assert components[0].transform == RigidTransform()
    assert captured["screw_axis_planes"] == ("Front Plane", "Right Plane")
    assert captured["material"] == part.SPEC.material


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_mg_vn_magnifying_bracket_screw as drawing

    sheet = DRAWINGS_BY_NAME["mg_vn_magnifying_bracket_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES


def test_sheet_item_names_the_sku_thread_and_catalogue_length() -> None:
    """91794A078 replaced the 1/4 in 91794A077, but the ITEM row kept 1/4."""
    import draw_mg_vn_magnifying_bracket_screw as drawing

    assert drawing.ITEM == "#2-56 x 5/16 FILLISTER HEAD SLOTTED SCREW"
    match = re.fullmatch(r"(#\d+-\d+) x (\d+/\d+) FILLISTER HEAD SLOTTED SCREW", drawing.ITEM)
    assert match, drawing.ITEM
    assert match[1] == spec.THREAD
    assert float(Fraction(match[2])) * 25.4 == pytest.approx(FILLISTER_SIZE[1])
