"""Offline contracts for the MHA-CH-06-TL-VN-85 hub screw (McMaster 92220A163)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import _config
import _mcmaster_92220a163 as dims
import build_ch_rocker_arm_tl_vn_oblique_hub_screw as part
import ch_rocker_arm_tl_oblique_hub_stud_spec as stud
import ch_rocker_arm_tl_vn_oblique_hub_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _socket_head_dimensions import SocketHeadScrew
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_92220A163 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-hub-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("92220A163",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-85"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_92220A163)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_92220A163
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
    assert component.author is recipe.build_92220A163
    assert component.parameters is None
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_92220A163
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "build_socket_head(adapter, DIMS)" in source
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/92220A163*.SLDPRT"))


def test_recipe_is_the_catalogue_low_head_screw() -> None:
    d = dims.DIMS
    assert type(d) is SocketHeadScrew
    assert d.part_no == spec.SKU
    assert d.major_dia == pytest.approx(0.19 * IN)
    assert d.pitch == pytest.approx(IN / 24.0)
    assert d.length == pytest.approx(0.5 * IN)
    assert d.head_dia == pytest.approx(5.0 / 16.0 * IN)
    assert d.head_h == pytest.approx(3.0 / 32.0 * IN)
    assert d.socket_af == pytest.approx(3.0 / 32.0 * IN)
    # ASME B18.3's minimum key engagement for the #10 low head (Brighton-Best).
    assert d.socket_depth == pytest.approx(0.072 * IN)
    assert d.fully_threaded
    assert d.underside_y == 0.0
    assert d.tip_y == pytest.approx(-spec.ROW.length_mm)


def test_full_thread_in_the_stud_without_bottoming() -> None:
    # Rule 18: 1.5D of full thread at the worst grip; the longest screw through
    # the thinnest grip still stops inside the stud's guaranteed full thread.
    assert spec.ENGAGEMENT_MIN >= 1.5 * dims.DIMS.major_dia
    assert spec.ENGAGEMENT_MIN == pytest.approx(
        min(
            spec.LENGTH_MIN - spec.GRIP_MAX - spec.TAP_MOUTH_BREAK - 1.5 * dims.DIMS.pitch,
            stud.TAP_FULL_DEPTH_MIN - spec.TAP_MOUTH_BREAK,
        )
    )
    assert spec.INSERTION_MAX == pytest.approx(spec.LENGTH - spec.GRIP_MIN)
    assert spec.INSERTION_MAX < stud.TAP_FULL_DEPTH_MIN
    assert spec.GRIP_MIN < spec.ROW.grip_mm < spec.GRIP_MAX


def test_thread_chord_lies_on_the_bearing_face_edge() -> None:
    assert spec.SUPPLIER_REFERENCE_STARTS["SupplierThreadDiameter"] == (
        -dims.DIMS.major_dia / 2.0,
        0.0,
    )
    assert spec.SUPPLIER_PRODUCT_URL.endswith("/92220A163/")


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_hub_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_hub_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT == "#10-24 X 1/2 LOW-HEAD SHCS"
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
