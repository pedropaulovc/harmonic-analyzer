"""Offline contracts for the MHA-CH-06-TL-VN-66 feed nut screw (McMaster 91251A113)."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import _mcmaster_91251a113 as dims
import build_ch_rocker_arm_tl_vn_oblique_nut_screw as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_oblique_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _socket_head_dimensions import SocketHeadScrew
from _stock_recipe import recipe_declaration
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91251A113 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-nut-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91251A113",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-66"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert "installation_notes" not in row
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_91251A113)
    assert discovered_recipes()[spec.SKU] == metadata
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91251A113
    assert metadata.threaded is True


def test_quantity_thread_and_length_are_the_fastener_tables() -> None:
    row = fasteners.NUT_TO_FEED_BLOCK
    assert spec.ROW is row
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == row.count == 2
    assert (dims.THREAD, dims.LENGTH_TEXT, fasteners.SHCS) == (
        row.thread,
        row.length,
        row.head,
    )
    assert dims.DIMS.length == pytest.approx(row.length_mm)
    assert dims.DIMS.major_dia == pytest.approx(row.major_mm, abs=1e-3)
    assert spec.CALLOUT == fasteners.callout(row) == "#4-40 X 3/4 SHCS"
    # The head on the nut's outer face; the thread into the lug's THRU tap.
    assert row.grip_mm == feed_nut.LENGTH
    assert row.thread_depth_mm == feed_block.LUG_WIDTH


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_91251A113
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*.SLDPRT"))


def test_dimension_record_is_the_live_listings() -> None:
    d = dims.DIMS
    assert type(d) is SocketHeadScrew
    assert d.major_dia == pytest.approx(0.112 * IN)
    assert d.length == pytest.approx(0.75 * IN)
    assert d.head_dia == pytest.approx(0.183 * IN)
    assert d.head_h == pytest.approx(0.112 * IN)
    assert d.socket_af == pytest.approx(3.0 / 32.0 * IN)
    assert (dims.PACK_QUANTITY, dims.PACK_PRICE_USD) == (100, 12.19)
    # ASME B18.3 Table 1, #4: A min .176, transition diameter max .141.
    assert spec.HEAD_DIA_MIN == pytest.approx(0.176 * IN)
    assert spec.FILLET_DIA_MAX == pytest.approx(0.141 * IN)


def test_frame_puts_the_bearing_face_at_y0() -> None:
    d = dims.DIMS
    assert d.underside_y == 0.0
    assert d.top_y == pytest.approx(d.head_h)
    assert d.tip_y == pytest.approx(-spec.ROW.length_mm)


def test_head_seats_flat_on_the_brass_nut() -> None:
    # The transition seats inside the loose hole; the least head covers the
    # largest drilled hole with land to bear on.
    assert spec.FILLET_DIA_MAX < feed_nut.HOLE_DIA
    land = (spec.HEAD_DIA_MIN - feed_nut.HOLE_DIA - feed_nut.DRILLED_OVERSIZE) / 2.0
    assert feed_nut.HEAD_BEARING_LAND_MIN == pytest.approx(land)
    assert land > 0.3


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_nut_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_nut_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
