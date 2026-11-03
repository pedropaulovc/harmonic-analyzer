"""Offline contracts for the MHA-CH-06-TL-VN-66 feed nut screw (McMaster 91355A581)."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import _mcmaster_91355a581 as dims
import build_ch_rocker_arm_tl_vn_oblique_nut_screw as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_oblique_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as spec
from _button_head_dimensions import ButtonHeadScrew
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91355A581 as recipe
from diagnostics.diag_mcmaster_button_head import revolved_volume

STEM = "ch-rocker-arm-tl-vn-oblique-nut-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91355A581",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-66"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert "installation_notes" not in row
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_91355A581)
    assert discovered_recipes()[spec.SKU] == metadata
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91355A581
    assert metadata.threaded is True


def test_quantity_thread_and_length_are_the_fastener_tables() -> None:
    row = fasteners.NUT_TO_FEED_BLOCK
    assert spec.ROW is row
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == row.count == 2
    assert (dims.THREAD, dims.LENGTH_TEXT, fasteners.FLANGED_BHCS) == (
        row.thread,
        row.length,
        row.head,
    )
    assert dims.DIMS.length == pytest.approx(row.length_mm)
    assert dims.DIMS.major_dia == pytest.approx(row.major_mm, abs=1e-3)
    assert spec.CALLOUT == fasteners.callout(row) == "#4-40 X 3/4 FLANGED BHCS"
    # The flange on the nut's outer face; the thread into the lug's THRU tap.
    assert row.grip_mm == feed_nut.LENGTH
    assert row.thread_depth_mm == feed_block.LUG_WIDTH


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_91355A581
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*"))


def test_dimension_record_is_the_live_page_and_vendor_step() -> None:
    d = dims.DIMS
    assert type(d) is ButtonHeadScrew
    assert d.major_dia == pytest.approx(0.112 * IN)
    assert d.length == pytest.approx(0.75 * IN)
    assert d.head_dia == pytest.approx(0.193 * IN)
    assert d.head_h == pytest.approx(0.059 * IN)
    assert d.hex_af == pytest.approx(1.0 / 16.0 * IN)
    assert d.flange_dia == pytest.approx(0.234 * IN)
    assert (dims.PACK_QUANTITY, dims.PACK_PRICE_USD) == (100, 15.93)
    # Vendor STEP: a .024 flange whose flat face ends at Ø.222.
    assert d.flange_h == pytest.approx(0.024 * IN)
    assert d.band_h == d.flange_h
    assert d.bearing_edge_r == pytest.approx(d.flange_dia / 2.0)
    assert spec.BEARING_DIA_MIN == pytest.approx(0.222 * IN)
    # ASME B18.3 Table 1's #4 SHCS transition bound, assumed for this head.
    assert spec.FILLET_DIA_MAX == pytest.approx(0.141 * IN)
    assert dims.LENGTH_MIN == pytest.approx((0.75 - 0.03) * IN)


def test_flanged_revolve_is_dome_flange_and_shank() -> None:
    d = dims.DIMS
    plain = ButtonHeadScrew(
        part_no=d.part_no,
        major_dia=d.major_dia,
        pitch=d.pitch,
        length=d.length,
        head_dia=d.head_dia,
        head_h=d.head_h,
        hex_af=d.hex_af,
    )
    assert plain.band_h != d.band_h
    # The flange disc replaces the plain head's band cone.
    assert revolved_volume(d) > revolved_volume(plain)


def test_supplier_references_name_the_flange() -> None:
    names = [name for name, _value, _orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS]
    assert names == [
        "SupplierLength",
        "SupplierFlangeDiameter",
        "SupplierHeadDiameter",
        "SupplierHeadHeight",
        "SupplierThreadDiameter",
        "SupplierDriveWidth",
    ]
    values = {name: value for name, value, _orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert values["SupplierLength"] == pytest.approx(-spec.ROW.length_mm)
    assert values["SupplierFlangeDiameter"] == pytest.approx(0.234 * IN)
    assert spec.SUPPLIER_REFERENCE_FORMATS["SupplierDriveWidth"] == (0, "length", 16, None)


def test_head_seats_flat_on_the_brass_nut() -> None:
    # At the fit-up's eccentricity the fillet clears the least hole's mouth
    # and the flange's least flat face covers the largest drilled hole.
    assert feed_block.HEAD_FILLET_CLEARANCE > 0.0
    assert feed_block.HEAD_BEARING_LAND_MIN > 0.0
    assert spec.FILLET_DIA_MAX < feed_nut.HOLE_DIA < spec.BEARING_DIA_MIN


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_nut_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_nut_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
