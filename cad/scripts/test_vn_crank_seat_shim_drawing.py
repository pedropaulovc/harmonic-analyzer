"""Offline contracts for the MHA-VN-071 crank seat shim pack (McMaster 3088A)."""

from __future__ import annotations

import asyncio
import importlib
import math

import pytest

import _config
import build_vn_crank_seat_shim as part
import dt_crank_seat_gap as gap
import vn_crank_seat_shim_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _mcmaster_3088a_12x18 import SHIMS, THICKNESS_ROWS
from _test_stock_recipes import discovered_recipes

STEM = "vn-crank-seat-shim"
SKUS = ("3088A006", "3088A026", "3088A066", "3088A086", "3088A106", "3088A207")


def test_catalogue_row_is_the_registered_mcmaster_shim_series() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == spec.SKUS == SKUS
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert row["number"] == "MHA-VN-071"
    assert int(row["quantity"]) == spec.COUNT == 1
    recipes = discovered_recipes()
    for sku in SKUS:
        metadata = recipes[sku]
        recipe = importlib.import_module(metadata.module)
        assert metadata.module == f"diagnostics.diag_build_{sku}"
        assert callable(getattr(recipe, metadata.callable_name))
        assert metadata.threaded is False


def test_title_block_material_is_the_catalogue_carbon_steel() -> None:
    row = _config.parts(STEM)
    assert "carbon steel" in spec.CATALOG_MATERIAL.lower()
    assert "CARBON STEEL" in str(row["material"]).upper()
    assert "3088A" in str(row["material_specification"])
    assert FASTENERS[STEM].material == part.MATERIAL


def test_catalogue_carries_the_family_table_bands() -> None:
    """Read 2026-10-15: 12 ID +/-0.3, 18 OD +/-0.5, each row's thickness band."""
    assert {sku: row[0] for sku, row in THICKNESS_ROWS.items()} == {
        "3088A006": 0.1,
        "3088A026": 0.2,
        "3088A066": 0.5,
        "3088A086": 1.0,
        "3088A106": 1.5,
        "3088A207": 2.0,
    }
    assert (spec.ID_MIN, spec.ID_MAX) == pytest.approx((11.7, 12.3))
    assert (spec.OD_MIN, spec.OD_MAX) == pytest.approx((17.5, 18.5))
    assert (SHIMS["3088A006"].thickness_min, SHIMS["3088A006"].thickness_max) == (
        pytest.approx((0.087, 0.113))
    )
    assert (SHIMS["3088A207"].thickness_min, SHIMS["3088A207"].thickness_max) == (
        pytest.approx((1.79, 2.21))
    )


def test_every_accepted_gap_takes_a_pack_of_at_most_four() -> None:
    assert spec.STACK_MAX == 4
    assert spec.FIT_RESIDUAL_MAX == pytest.approx(0.10)
    assert spec.worst_residual(gap.GAP_MIN, gap.GAP_MAX) <= spec.FIT_RESIDUAL_MAX + 1e-9
    # Sampled independently of the step proof: every gap in the range.
    steps = 2000
    for index in range(steps + 1):
        g = gap.GAP_MIN + (gap.GAP_MAX - gap.GAP_MIN) * index / steps
        pack = spec.pack_for(g)
        assert 1 <= len(pack) <= spec.STACK_MAX, g
        residual = g - spec.pack_thickness(pack)
        assert -1e-9 <= residual < spec.FIT_RESIDUAL_MAX + 1e-9, g


def test_pack_selection_prefers_fewest_then_thickest() -> None:
    assert spec.pack_for(2.0) == ("3088A207",)
    assert spec.pack_for(2.05) == ("3088A207",)
    assert spec.pack_for(0.4) == ("3088A026", "3088A026")
    assert spec.pack_for(3.0) == ("3088A207", "3088A086")
    assert spec.pack_for(0.05) == ()


def test_the_model_is_the_nominal_gap_pack() -> None:
    assert spec.PACK == ("3088A207", "3088A066", "3088A026", "3088A006")
    assert spec.pack_for(gap.GAP_NOMINAL) == spec.PACK
    assert spec.THICKNESS == pytest.approx(2.8)
    assert spec.LAYER_Y == pytest.approx((0.0, 2.0, 2.5, 2.7))
    assert 0.0 <= gap.FLOAT_NOMINAL <= spec.FIT_RESIDUAL_MAX
    assert spec.pack_volume() == pytest.approx(
        math.pi / 4 * (spec.OD**2 - spec.ID**2) * spec.THICKNESS
    )


def test_the_pack_passes_the_journal_land() -> None:
    import dt_crankshaft_spec as cs

    assert gap.JOURNAL_PASS_CLEARANCE_WORST == pytest.approx(
        spec.ID_MIN - (cs.JOURNAL_DIA + max(cs.JOURNAL_DIA_BAND))
    )
    assert gap.JOURNAL_PASS_CLEARANCE_WORST > 0.0


def test_coverage_check_refuses_a_series_without_the_thinnest_shim(monkeypatch) -> None:
    """Negative control: without 3088A006 the odd tenths above 0.3 need a
    0.1 step the 0.2 shims cannot make, so a 0.2 hole opens in the range."""
    reduced = {
        total: pack
        for total, pack in spec.PACKS.items()
        if "3088A006" not in pack
    }
    monkeypatch.setattr(spec, "PACKS", reduced)
    assert spec.worst_residual(gap.GAP_MIN, gap.GAP_MAX) > spec.FIT_RESIDUAL_MAX
    with pytest.raises(AssertionError, match="fit residual"):
        spec.check_coverage(gap.GAP_MIN, gap.GAP_MAX)


def test_coverage_check_refuses_a_range_past_four_shims() -> None:
    """Negative control: 4.8 is the first tenth four shims cannot make."""
    with pytest.raises(AssertionError, match="fit residual"):
        spec.check_coverage(gap.GAP_MIN, 4.95)


def test_stock_build_stacks_the_model_pack_from_the_collar(monkeypatch) -> None:
    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    components = seen["components"]
    assert tuple(component.sku for component in components) == spec.PACK
    below = 0.0
    for component, layer_y in zip(components, spec.LAYER_Y, strict=True):
        assert component.transform.translation_mm == pytest.approx((0.0, layer_y, 0.0))
        assert not any(component.transform.rotation_radians)
        assert component.parameters["stacked_volume_mm3"] == pytest.approx(below)
        recipe = importlib.import_module(f"diagnostics.diag_build_{component.sku}")
        assert component.author is getattr(recipe, f"build_{component.sku}")
        below += spec.shim_volume(component.sku)
    assert below == pytest.approx(spec.pack_volume())
    assert seen["material"] == part.SPEC.material
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_vn_crank_seat_shim as drawing

    sheet = DRAWINGS_BY_NAME["vn_crank_seat_shim"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )


def test_installation_note_is_quantity_and_sizes_only() -> None:
    notes = _config.parts(STEM)["installation_notes"]
    lines = notes.splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
    assert "QTY AS REQUIRED" in notes
    for sku, (thickness, _tol) in THICKNESS_ROWS.items():
        assert f"{thickness:g} {sku}" in notes, sku
