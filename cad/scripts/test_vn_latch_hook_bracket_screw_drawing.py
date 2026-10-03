"""Offline contracts for the MHA-VN-043 latch-hook bracket screws (90280A108)."""

from __future__ import annotations

import pytest

import _config
import build_vn_latch_hook_bracket_screw as part
import vn_latch_hook_bracket_screw_spec as spec
import pd_support_bar_spec as bar
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _hole_spec import blind_cut_dia_mm
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_90280A108 as recipe

STEM = "vn-latch-hook-bracket-screw"
_DRILL = blind_cut_dia_mm(bar.BRACKET_TAP_SPEC)


def test_catalogue_row_is_the_foot_screw_sku() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert FASTENERS["vn-foot-screw"].skus == stock.skus
    assert row["number"] == "MHA-VN-043"
    assert row["quantity"] == 2
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.threaded is True


def test_engagement_in_the_bar_tap_passes_at_the_worst_case() -> None:
    """Each Ø3.1 MAX countersink takes thread to where its 45° leg meets the
    #43 tap drill (R9-63): 0.4195 a mouth, not the 0.1276 counted to the
    major, and the bar still holds 2.27 D."""
    worst_d = spec.checked_engagement(
        bar.BRACKET_TAP_CSK_DIA, _DRILL, bar.BAR_DEPTH, bar.BAR_DEPTH_BAND
    )
    assert worst_d == pytest.approx(6.4508 / spec.MAJOR_DIA, abs=1e-4)
    assert worst_d >= spec.ENGAGEMENT_FLOOR_D


def test_a_bigger_countersink_or_a_short_bar_is_refused() -> None:
    # Countersinks wide enough to eat the thread past 1.5 D.
    too_wide = _DRILL + (spec.ENGAGEMENT_NOMINAL - 1.4 * spec.MAJOR_DIA)
    with pytest.raises(AssertionError):
        spec.checked_engagement(too_wide, _DRILL, bar.BAR_DEPTH, bar.BAR_DEPTH_BAND)
    # A bar no thicker than the screw reaches: the tip stands proud.
    with pytest.raises(AssertionError):
        spec.checked_engagement(
            bar.BRACKET_TAP_CSK_DIA, _DRILL, spec.ENGAGEMENT_NOMINAL, 0.0
        )


def test_tip_stays_inside_the_bar_front_face() -> None:
    assert spec.tip_short_worst(bar.BAR_DEPTH, bar.BAR_DEPTH_BAND) > 0.0
    assert spec.tip_short_worst(bar.BAR_DEPTH, 0.0) > spec.tip_short_worst(
        bar.BAR_DEPTH, bar.BAR_DEPTH_BAND
    )


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_vn_latch_hook_bracket_screw as drawing

    sheet = DRAWINGS_BY_NAME["vn_latch_hook_bracket_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
