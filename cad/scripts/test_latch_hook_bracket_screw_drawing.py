"""Offline contracts for the MHA-171 latch-hook bracket screws (90280A108)."""

from __future__ import annotations

import pytest

import _config
import build_latch_hook_bracket_screw as part
import latch_hook_bracket_screw_spec as spec
import support_bar_spec as bar
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_90280A108 as recipe

STEM = "latch-hook-bracket-screw"


def test_catalogue_row_is_the_foot_screw_sku() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert FASTENERS["foot-screw"].skus == stock.skus
    assert row["number"] == "MHA-171"
    assert row["quantity"] == 2
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.threaded is True


def test_engagement_in_the_bar_tap_passes_at_the_worst_case() -> None:
    worst_d = spec.checked_engagement(
        bar.BRACKET_TAP_CSK_DIA, bar.BAR_DEPTH, bar.BAR_DEPTH_BAND
    )
    assert worst_d >= spec.ENGAGEMENT_FLOOR_D
    assert spec.engagement_worst(bar.BRACKET_TAP_CSK_DIA) < spec.ENGAGEMENT_NOMINAL


def test_a_bigger_countersink_or_a_short_bar_is_refused() -> None:
    # Countersinks wide enough to eat the thread past 1.5 D.
    too_wide = spec.MAJOR_DIA + (spec.ENGAGEMENT_NOMINAL - 1.4 * spec.MAJOR_DIA)
    with pytest.raises(AssertionError):
        spec.checked_engagement(too_wide, bar.BAR_DEPTH, bar.BAR_DEPTH_BAND)
    # A bar no thicker than the screw reaches: the tip stands proud.
    with pytest.raises(AssertionError):
        spec.checked_engagement(bar.BRACKET_TAP_CSK_DIA, spec.ENGAGEMENT_NOMINAL, 0.0)


def test_tip_stays_inside_the_bar_front_face() -> None:
    assert spec.tip_short_worst(bar.BAR_DEPTH, bar.BAR_DEPTH_BAND) > 0.0
    assert spec.tip_short_worst(bar.BAR_DEPTH, 0.0) > spec.tip_short_worst(
        bar.BAR_DEPTH, bar.BAR_DEPTH_BAND
    )


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_latch_hook_bracket_screw as drawing

    sheet = DRAWINGS_BY_NAME["latch_hook_bracket_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
