"""Offline purchased-stock and reference-sheet contracts for MHA-VN-054."""

from __future__ import annotations

import pytest

import _config
import vn_gooseneck_spring_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _fastener_catalog import FASTENERS
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

STEM = "vn-gooseneck-spring-screw"


def test_stock_identity_is_the_selected_zinc_plated_one_inch_fillister() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert stock.skus == tuple(row["supplier_skus"]) == ("90280A583",)
    assert spec.SKU == "90280A583"
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == row["title"] == (
        "Zinc-Plated Steel Fillister Head Slotted Screw"
    )
    assert stock.material == row["material"] == "Plain Carbon Steel"
    assert row["number"] == "MHA-VN-054"
    assert row["quantity"] == 1
    assert row["finish"] == "zinc plated"
    assert row["process"] == "purchased"


def test_stock_and_native_family_use_the_catalog_sizes() -> None:
    # Inches from the live product table. The rejected 3/4 inch screw must
    # never return through either the stock spec or the native family row.
    catalog_sizes = (
        5.0 / 16.0 * 25.4,
        1.0 * 25.4,
        0.295 * 25.4,
        0.518 * 25.4,
        25.4 / 18.0,
    )
    assert spec.THREAD == "5/16-18 UNC"
    assert (spec.MAJOR_DIA, spec.LENGTH, spec.HEAD_H, spec.HEAD_DIA, spec.PITCH) == (
        pytest.approx(catalog_sizes)
    )
    assert FILLISTER_SIZES[spec.SKU] == pytest.approx(catalog_sizes)


def test_reference_sheet_targets_the_purchased_stock_not_the_gooseneck() -> None:
    sheet = DRAWINGS_BY_NAME["vn_gooseneck_spring_screw"]
    assert sheet.source_kind == "part"
    assert sheet.source.name == "vn-gooseneck-spring-screw.SLDPRT"
    assert sheet.layout == DrawingLayout.LANDSCAPE
    template = DRAWING_TEMPLATES[sheet.layout]
    assert template.width_m > template.height_m
    assert sheet.outputs["pdf"].name == "vn-gooseneck-spring-screw.pdf"
