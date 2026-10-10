"""Offline stock identity and catalogue-envelope contracts for MHA-VN-054."""

from __future__ import annotations

import pytest

import _config
import build_vn_ms_stop_plate_screw as part
import vn_ms_stop_plate_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_90114A124 as recipe
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

STEM = "vn-ms-stop-plate-screw"


def test_catalogue_and_native_recipe_share_the_small_brass_identity() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("90114A124",)
    assert stock.material == row["material"] == "Brass"
    assert stock.stock_name == row["stock_name"] == "Brass Fillister Head Slotted Screw"
    assert row["number"] == "MHA-VN-054"
    assert row["quantity"] == 2
    assert row["process"] == "purchased"
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == "build_90114A124"
    assert metadata.threaded


def test_catalogue_envelope_is_the_live_smallest_brass_fillister() -> None:
    assert spec.THREAD == "#2-56"
    assert FILLISTER_SIZES[spec.SKU] == pytest.approx(
        (spec.MAJOR_DIA, spec.LENGTH, spec.HEAD_H, spec.HEAD_DIA, spec.PITCH)
    )
    assert (spec.MAJOR_DIA, spec.LENGTH, spec.HEAD_H, spec.HEAD_DIA) == pytest.approx(
        (2.1844, 6.35, 2.1082, 3.556)
    )
    assert spec.PITCH == pytest.approx(25.4 / 56.0)
    assert spec.HEAD_DIA < 4.0


def test_purchased_sheet_points_to_the_built_brass_part() -> None:
    import draw_vn_ms_stop_plate_screw as drawing

    sheet = DRAWINGS_BY_NAME["vn_ms_stop_plate_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem


def test_stop_plate_threads_have_clearance_and_full_engagement() -> None:
    import ms_stop_spec as joint

    assert joint.PLATE_CLEARANCE_DIA > spec.MAJOR_DIA
    penetration = spec.LENGTH - joint.PLATE_THICKNESS
    assert penetration > 1.5 * spec.MAJOR_DIA + spec.PITCH
    assert joint.PLATE_TAP_THREAD_DEPTH > penetration
    assert joint.PLATE_TAP_DRILL_DEPTH > joint.PLATE_TAP_THREAD_DEPTH
    assert joint.BLOCK_DEPTH > joint.PLATE_TAP_DRILL_DEPTH
