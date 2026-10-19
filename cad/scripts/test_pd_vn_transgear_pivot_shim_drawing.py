"""Offline contracts for the MHA-PD-VN-67 transgear pivot shim (McMaster 98055A098)."""

from __future__ import annotations

import asyncio
import math

import pytest

import _config
import build_pd_vn_transgear_pivot_shim as part
import pd_vn_transgear_pivot_shim_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_98055A098 as recipe

STEM = "pd-vn-transgear-pivot-shim"


def test_catalogue_row_is_the_registered_mcmaster_shim() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("98055A098",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert row["number"] == "MHA-PD-VN-67"
    assert int(row["quantity"]) == spec.COUNT == 1
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98055A098
    assert metadata.threaded is False


def test_title_block_material_is_the_catalogue_spring_steel() -> None:
    """The MATERIAL cell names what McMaster sells (stress-resistant spring
    steel), not the SOLIDWORKS library stand-in used for mass properties."""
    row = _config.parts(STEM)
    assert "spring steel" in spec.CATALOG_MATERIAL.lower()
    assert "SPRING STEEL" in str(row["material"]).upper()
    assert "spring steel" in str(row["material_specification"]).lower()
    assert spec.SKU in str(row["material_specification"])
    assert FASTENERS[STEM].material == part.MATERIAL


def test_spec_carries_the_catalogue_bands() -> None:
    """DIN 988 5 x 10 x 0.5: thickness -0.05/0, ID +0.03/+0.4, OD -0.47/-0.04."""
    assert spec.THICKNESS == pytest.approx(0.5)
    assert (spec.THICKNESS_MIN, spec.THICKNESS_MAX) == pytest.approx((0.45, 0.50))
    assert (spec.ID_MIN, spec.ID_MAX) == pytest.approx((5.03, 5.40))
    assert (spec.OD_MIN, spec.OD_MAX) == pytest.approx((9.53, 9.96))
    assert spec.TOP_Y - spec.BOTTOM_Y == pytest.approx(spec.THICKNESS)
    assert spec.shim_volume() == pytest.approx(
        math.pi / 4 * (spec.OD**2 - spec.ID**2) * spec.THICKNESS
    )


def test_stock_build_uses_the_catalogue_recipe(monkeypatch) -> None:
    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is recipe.build_98055A098
    assert seen["material"] == part.SPEC.material


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_pd_vn_transgear_pivot_shim as drawing

    sheet = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_shim"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )


def test_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
