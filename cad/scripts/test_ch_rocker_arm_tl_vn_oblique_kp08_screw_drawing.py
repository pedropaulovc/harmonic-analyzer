"""Offline contracts for the MHA-CH-06-TL-VN-65 pillow block screw (McMaster 91255A150)."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import _mcmaster_91255a150 as dims
import build_ch_rocker_arm_tl_vn_oblique_kp08_screw as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_kp08_screw_spec as spec
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
from _button_head_dimensions import ButtonHeadScrew
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91255A150 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-kp08-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91255A150",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == "Black-Oxide Button Head Hex-Drive Screw"
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-65"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert "140,000 psi" in row["material_specification"]
    assert "installation_notes" not in row
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_91255A150)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91255A150
    assert metadata.threaded is True


def test_quantity_thread_and_length_are_the_fastener_tables() -> None:
    row = fasteners.KP08_TO_BRACKET
    assert spec.ROW is row
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == row.count == 4
    assert (dims.THREAD, dims.LENGTH_TEXT, fasteners.BHCS) == (
        row.thread,
        row.length,
        row.head,
    )
    assert dims.DIMS.length == pytest.approx(row.length_mm)
    assert dims.DIMS.major_dia == pytest.approx(row.major_mm, abs=1e-3)
    assert spec.CALLOUT == fasteners.callout(row) == "#6-32 X 5/8 BHCS"


def test_catalogue_head_and_drive() -> None:
    d = dims.DIMS
    assert type(d) is ButtonHeadScrew
    assert (d.head_dia, d.head_h, d.hex_af) == pytest.approx(
        (0.262 * IN, 0.073 * IN, 5 / 64 * IN)
    )
    # The 5/64 hex sits inside the flat top, above the head's band.
    assert d.flat_top_dia > 2.0 * d.hex_corner_r
    assert d.head_h - d.socket_depth > d.band_h


def test_head_covers_the_kp08_hole_at_full_float() -> None:
    # The listing's Ø5 hole floats the #6 by 0.747; the head OD still covers
    # it on the far side (0.827), where the SHCS's Ø.226 covered 0.37.
    assert spec.HOLE_FLOAT == pytest.approx((5.0 - 0.138 * IN) / 2.0)
    assert spec.HEAD_OVER_HOLE == pytest.approx((0.262 * IN - 5.0) / 2.0)
    assert spec.HEAD_OVER_HOLE > spec.HOLE_FLOAT
    assert (0.226 * IN - leadscrew.KP08_HOLE_DIA) / 2.0 < spec.HOLE_FLOAT
    # The flat bearing annulus is inside the band: it may not reach the far
    # edge at full float, and the spec says by how much.
    assert spec.HEAD_LAND_AT_FULL_FLOAT == pytest.approx(
        dims.DIMS.bearing_edge_r - 2.5 - spec.HOLE_FLOAT
    )


def test_engagement_in_the_tl28_tap_holds_rule_18() -> None:
    # The head on the UNVERIFIED 5 mm foot; 5/8 under the head, like the SHCS.
    full = leadscrew.full_thread_min(dims.LENGTH_TEXT, leadscrew.KP08_FOOT_THICK, dims.THREAD)
    assert full >= leadscrew.ENGAGEMENT_TARGET_D * dims.DIMS.major_dia
    assert fasteners.KP08_TO_BRACKET.protrusion_mm < 0.0


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_91255A150
    assert "91251A150" not in REGISTRY
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/91255A150*.SLDPRT"))


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_kp08_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_kp08_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
