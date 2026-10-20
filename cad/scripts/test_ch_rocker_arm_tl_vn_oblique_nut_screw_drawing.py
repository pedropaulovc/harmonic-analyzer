"""Offline contracts for the MHA-CH-06-TL-VN-66 leadscrew nut screw (Olander 4C50BHCA)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import _olander_4c50bhca as dims
import build_ch_rocker_arm_tl_vn_oblique_nut_screw as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as spec
from _button_head_dimensions import ButtonHeadScrew
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_4C50BHCA as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-nut-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_olander_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("4C50BHCA",)
    assert stock.supplier == row["supplier"] == "Olander"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-66"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    # McMaster is a cross-reference only, never the supplier.
    assert spec.MCMASTER_XREF == "91255A110"
    assert spec.MCMASTER_XREF in row["material_specification"]
    assert "installation_notes" not in row
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_4C50BHCA)
    assert discovered_recipes()[spec.SKU] == metadata
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_4C50BHCA
    assert metadata.threaded is True


def test_quantity_thread_and_length_are_the_fastener_tables() -> None:
    row = fasteners.NUT_TO_NUT_BRACKET
    assert spec.ROW is row
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == row.count
    assert (dims.THREAD, dims.LENGTH_TEXT, fasteners.BHCS) == (
        row.thread,
        row.length,
        row.head,
    )
    assert dims.DIMS.length == pytest.approx(row.length_mm)
    assert dims.DIMS.major_dia == pytest.approx(row.major_mm, abs=1e-3)
    assert spec.CALLOUT == fasteners.callout(row) == "#4-40 X 1/2 BHCS"
    # The head bears on the flange: no washer in the grip.
    assert row.grip_mm == leadscrew.NUT_FLANGE_THICK


def test_standalone_recipe_run_is_catalog_only() -> None:
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    for code in (spec.SKU, spec.MCMASTER_XREF):
        assert not list(root.glob(f"cad/references/**/{code}*.SLDPRT"))


def test_dimension_record_is_the_listings_maximum_head() -> None:
    d = dims.DIMS
    assert type(d) is ButtonHeadScrew
    assert d.head_dia == pytest.approx(0.213 * IN)
    assert d.head_h == pytest.approx(0.059 * IN)
    assert spec.HEAD_DIA_MIN == pytest.approx(0.201 * IN)
    assert d.hex_af == pytest.approx(0.0625 * IN)


def test_socket_is_at_the_standards_minimum_key_engagement() -> None:
    # ASME B18.3 Table 11, #4 button head: T 0.035 min; the family law's
    # 0.55 H (0.0325) would sit under it. The law's other SKU keeps it.
    import _mcmaster_91255a106

    assert dims.DIMS.socket_depth == pytest.approx(0.035 * IN)
    assert 0.55 * dims.DIMS.head_h < dims.DIMS.socket_depth
    legacy = _mcmaster_91255a106.DIMS
    assert legacy.key_engagement is None
    assert legacy.socket_depth == pytest.approx(0.55 * legacy.head_h)


def test_underhead_fillet_is_a_standard_concave_quarter_at_f_max() -> None:
    start, end, mid, chain = recipe.underhead_fillet_profile()
    major_r = dims.DIMS.major_dia / 2.0
    # Tangent to the bearing face at F max, to the major diameter R below it.
    assert start == pytest.approx((spec.FILLET_DIA_MAX / 2.0, 0.0))
    assert end == pytest.approx((major_r, -dims.FILLET_R))
    centre = (major_r + dims.FILLET_R, -dims.FILLET_R)
    for point in (start, end, mid):
        assert math.dist(point, centre) == pytest.approx(dims.FILLET_R)
    # Concave: the arc bows toward the shank-to-face corner, inside its chord.
    corner = (major_r, 0.0)
    chord_mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    assert math.dist(mid, corner) < math.dist(chord_mid, corner)
    assert dims.FILLET_R >= 0.004 * IN
    assert spec.FILLET_DIA_MAX == pytest.approx(0.132 * IN)
    # The closing chain starts at the arc's end and returns to its start.
    assert chain[0] == end and chain[-1] == start
    runout = chain[1]
    assert runout[0] == pytest.approx(dims.DIMS.root_r)
    assert end[1] - runout[1] == pytest.approx(end[0] - runout[0])  # 45 deg
    # Within B18.3 note 4's two pitches of unthreaded length under the head.
    assert -runout[1] < 2.0 * dims.DIMS.pitch


def test_underhead_fillet_contains_the_recipes_thread_neck() -> None:
    _start, _end, _mid, chain = recipe.underhead_fillet_profile()
    d = dims.DIMS
    neck_r = d.neck_dia / 2.0
    neck_h = neck_r - d.root_r
    runout_y = chain[1][1]
    assert runout_y <= -neck_h

    def envelope(y: float) -> float:  # fillet revolve's radius at depth y <= 0
        if y >= -dims.FILLET_R:
            dy = y + dims.FILLET_R
            return (
                d.major_dia / 2.0 + dims.FILLET_R - math.sqrt(dims.FILLET_R**2 - dy**2)
            )
        return d.major_dia / 2.0 - (-dims.FILLET_R - y)

    for step in range(11):
        y = -neck_h * step / 10.0
        assert envelope(y) >= neck_r + y - 1e-9  # the 45 deg neck cone


def test_underhead_fillet_clears_the_nut_flange_hole() -> None:
    # The fillet seats inside the flange's plain hole, so the head bears flat.
    assert spec.FILLET_DIA_MAX < leadscrew.NUT_HOLE_DIA
    assert spec.FILLET_DIA_MAX / 2.0 < dims.DIMS.bearing_edge_r


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_nut_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_nut_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
