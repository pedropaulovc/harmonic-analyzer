"""Offline stock and purchased-sheet contracts for MHA-DT-VN-70."""

from __future__ import annotations


import pytest

import _config
import build_dt_vn_keeper_chain_screw as part
import dt_vn_keeper_chain_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_92443A077 as recipe
import _mcmaster_92443a077 as catalogue

STEM = "dt-vn-keeper-chain-screw"
IN = 25.4


def test_catalogue_and_recipe_are_the_verified_stock_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.PART_NO,)
    assert stock.skus == ("92443A077",)
    assert (
        stock.stock_name
        == row["stock_name"]
        == row["title"]
        == "Brass Binding Head Slotted Screw"
    )
    assert stock.material == row["material"] == "Brass"
    # Owner ruling 2026-11-08 (#2144 item 9.2): one screw clamps the chain's
    # end link; DT-VN-69 went to the locating pin on the integration line.
    assert row["number"] == "MHA-DT-VN-70"
    assert row["quantity"] == 1
    assert row["finish"] == "plain"
    assert row["process"] == "purchased"
    metadata = discovered_recipes()[spec.PART_NO]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == "build_92443A077"
    assert metadata.threaded is True


def test_spec_nominals_are_the_catalogue_row() -> None:
    assert spec.THREAD == catalogue.THREAD == "#2-56"
    assert (
        spec.SHANK_DIA,
        spec.SHANK_LEN,
        spec.HEAD_H,
        spec.HEAD_DIA,
    ) == catalogue.BINDING_HEAD_SIZE[:4]
    # McMaster 92443A077: 0.086 major, 1/4 under head, Ø0.181 x 0.05 binding
    # head, 56 TPI; the no-threads STEP measures the head Ø0.1797.
    assert catalogue.BINDING_HEAD_SIZE == pytest.approx(
        (0.086 * IN, 0.25 * IN, 0.05 * IN, 0.181 * IN, IN / 56.0)
    )
    assert spec.HEAD_DIA_MIN == catalogue.HEAD_DIA_MIN == pytest.approx(0.1797 * IN)
    assert spec.HEAD_DIA_MIN < spec.HEAD_DIA


def test_supplier_reference_dimensions_are_the_catalogue_row() -> None:
    dimensions = {
        name: (value, orientation)
        for name, value, orientation in catalogue.SUPPLIER_REFERENCE_DIMENSIONS
    }
    assert dimensions == {
        "SupplierLength": (-catalogue.LENGTH, "vertical"),
        "SupplierHeadHeight": (catalogue.HEAD_H, "vertical"),
        "SupplierHeadDiameter": (catalogue.HEAD_DIA, "horizontal"),
        "SupplierThreadDiameter": (catalogue.MAJOR_DIA, "horizontal"),
    }
    names = set(dimensions)
    for table in (
        catalogue.SUPPLIER_REFERENCE_STARTS,
        catalogue.SUPPLIER_REFERENCE_PLANES,
        catalogue.SUPPLIER_REFERENCE_SIDES,
    ):
        assert set(table) <= names
    assert set(catalogue.SUPPLIER_REFERENCE_FORMATS) == names
    # The thread witness carries the catalogue thread designation.
    assert catalogue.SUPPLIER_REFERENCE_FORMATS["SupplierThreadDiameter"][3] == spec.THREAD


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_dt_vn_keeper_chain_screw as drawing

    sheet = DRAWINGS_BY_NAME["dt_vn_keeper_chain_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
