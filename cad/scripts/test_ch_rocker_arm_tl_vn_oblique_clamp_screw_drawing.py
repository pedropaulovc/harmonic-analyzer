"""Offline contracts for the MHA-CH-06-TL-VN-68 clamp screw (McMaster 91251A541)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import _config
import _mcmaster_91251a541 as dims
import build_ch_rocker_arm_tl_vn_oblique_clamp_screw as part
import ch_rocker_arm_tl_vn_oblique_clamp_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _socket_head_dimensions import SocketHeadScrew
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91251A541 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-clamp-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91251A541",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-68"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_91251A541)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91251A541
    assert metadata.threaded is True


def test_production_build_is_the_supplied_screw(monkeypatch) -> None:
    seen: dict = {}

    async def stock_fastener(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", stock_fastener)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is recipe.build_91251A541
    assert component.parameters is None
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_dimension_record_is_the_91251a_familys() -> None:
    assert type(dims.DIMS) is SocketHeadScrew
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "build_socket_head(adapter, DIMS)" in source
    assert "build_socket_head_catalog(adapter, DIMS)" in source


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_91251A541
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/91251A541*.SLDPRT"))


def test_recipe_is_the_catalogue_screw() -> None:
    d = dims.DIMS
    assert type(d) is SocketHeadScrew
    assert d.part_no == spec.SKU
    assert d.major_dia == pytest.approx(0.25 * IN)
    assert d.pitch == pytest.approx(IN / 20.0)
    assert d.length == pytest.approx(0.875 * IN)
    assert d.head_dia == pytest.approx(0.375 * IN)
    assert d.head_h == pytest.approx(0.25 * IN)
    assert d.socket_af == pytest.approx(3.0 / 16.0 * IN)
    assert d.socket_depth == pytest.approx(
        0.120 * IN
    )  # standard minimum key engagement
    assert d.fully_threaded


def test_frame_puts_the_bearing_face_at_y0() -> None:
    d = dims.DIMS
    assert d.underside_y == 0.0
    assert d.top_y == pytest.approx(d.head_h)
    assert d.tip_y == pytest.approx(-spec.ROW.length_mm)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'screw_axis_planes=("Front Plane", "Right Plane")' in source


def test_thread_chord_lies_on_the_bearing_face_edge() -> None:
    # The thread Ø's line runs under the head's bearing-face edge (y = 0), not
    # across the threaded shank.
    assert spec.SUPPLIER_REFERENCE_STARTS["SupplierThreadDiameter"] == (
        -dims.DIMS.major_dia / 2.0,
        0.0,
    )
    assert dims.DIMS.head_dia > dims.DIMS.major_dia


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_clamp_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_clamp_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
