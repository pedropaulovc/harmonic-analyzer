"""Offline contracts for the MHA-PD-VN-68 transgear cluster shim (McMaster 94773A606)."""

from __future__ import annotations

import math

import pytest

import _config
import build_pd_vn_transgear_cluster_shim as part
import pd_transgear_rear_bushing_spec as rear_bushing
import pd_vn_transgear_cluster_shim_spec as spec
import transgear_cluster_fit as fit
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_94773A606 as recipe

STEM = "pd-vn-transgear-cluster-shim"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_shim() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("94773A606",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert row["number"] == "MHA-PD-VN-68"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == fit.SHIM_COUNT_MODEL
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_94773A606
    assert metadata.threaded is False


def test_spec_carries_the_catalogue_bands() -> None:
    """94773A606: .005 +/-.0005 thick; ID 1/8 0/+.012; OD 1/4 -.005/+.002."""
    assert spec.THICKNESS == pytest.approx(0.005 * IN)
    assert (spec.THICKNESS_MIN, spec.THICKNESS_MAX) == pytest.approx(
        (0.0045 * IN, 0.0055 * IN)
    )
    assert (spec.ID_MIN, spec.ID_MAX) == pytest.approx((0.125 * IN, 0.137 * IN))
    assert (spec.OD_MIN, spec.OD_MAX) == pytest.approx((0.245 * IN, 0.252 * IN))
    assert spec.ID_MIN < spec.ID < spec.ID_MAX
    assert spec.TOP_Y - spec.BOTTOM_Y == pytest.approx(spec.THICKNESS)
    assert spec.shim_volume() == pytest.approx(
        math.pi / 4 * (spec.OD**2 - spec.ID**2) * spec.THICKNESS
    )


def test_the_shim_sits_inside_the_rear_bushing_face() -> None:
    """The largest shim stays inside the smallest rear bushing's face."""
    assert spec.OD_MAX < rear_bushing.OD - 0.254  # the .35 O.D. at .XX


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_pd_vn_transgear_cluster_shim as drawing

    sheet = DRAWINGS_BY_NAME["pd_vn_transgear_cluster_shim"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )


def test_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
