"""Offline contracts for the MHA-CH-06-TL-VN-86 left clamp screw (McMaster 92220A165)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import _config
import _mcmaster_92220a165 as dims
import build_ch_rocker_arm_tl_vn_oblique_left_clamp_screw as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_vn_oblique_left_clamp_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _socket_head_dimensions import SocketHeadScrew
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_92220A165 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-left-clamp-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("92220A165",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-86"
    assert "cut to fit" in row["process"]
    assert spec.SKU in row["material_specification"]
    metadata = recipe_declaration(spec.SKU, recipe.build_92220A165)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_92220A165
    assert metadata.threaded is True


def test_production_build_is_the_cut_screw(monkeypatch) -> None:
    seen: dict = {}

    async def stock_fastener(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", stock_fastener)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is recipe.build_92220A165
    assert component.parameters == {"cut_length": spec.CUT_LENGTH}
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_recipe_refuses_a_cut_outside_the_bought_screw() -> None:
    for cut in (0.0, dims.DIMS.length):
        with pytest.raises(ValueError):
            asyncio.run(recipe.build_92220A165(None, cut_length=cut))


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_92220A165
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/92220A165*.SLDPRT"))


def test_recipe_is_the_catalogue_low_head_screw() -> None:
    d = dims.DIMS
    assert type(d) is SocketHeadScrew
    assert d.part_no == spec.SKU
    assert d.major_dia == pytest.approx(0.19 * IN)
    assert d.pitch == pytest.approx(IN / 24.0)
    assert d.length == pytest.approx(0.75 * IN)
    assert d.head_dia == pytest.approx(5.0 / 16.0 * IN)
    assert d.head_h == pytest.approx(3.0 / 32.0 * IN)
    assert d.socket_af == pytest.approx(3.0 / 32.0 * IN)
    assert d.socket_depth == pytest.approx(0.072 * IN)
    assert d.fully_threaded


def test_cut_screw_engages_the_blind_tap_and_clears_its_floor() -> None:
    low, high = spec.CUT_INSERTION
    assert 0.0 < low < high
    assert 0.0 < spec.CUT_LENGTH < dims.DIMS.length
    assert spec.CUT_LENGTH == spec.ROW.cut_length_mm
    assert spec.ENGAGEMENT_MIN >= 1.5 * dims.DIMS.major_dia
    assert high - dims.DIMS.pitch <= carrier.LEFT_CLAMP_THREAD_DEPTH
    assert high < spec.PILOT_DEPTH_MIN


def test_cut_length_is_a_reference_beside_the_stock_witness() -> None:
    names = [name for name, _value, _orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS]
    assert names[:2] == ["CutLength", "SupplierLength"]
    assert spec.SUPPLIER_REFERENCE_FORMATS["CutLength"][3] == "CUT TO FIT"
    assert spec.SUPPLIER_REFERENCE_FORMATS["SupplierLength"][3] == (
        "AS-SUPPLIED STOCK LENGTH"
    )
    assert spec.SUPPLIER_REFERENCE_STARTS["SupplierThreadDiameter"] == (
        -dims.DIMS.major_dia / 2.0,
        -spec.CUT_LENGTH,
    )


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_left_clamp_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_left_clamp_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT == "#10-24 X 3/4 LOW-HEAD SHCS"
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
