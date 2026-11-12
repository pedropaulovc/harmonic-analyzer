"""Offline source contracts for MHA-PD-VN-70; no native or load-family certificate."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import math
from pathlib import Path

import pytest

import _config
import build_pd_vn_transgear_collar_flat_pin as part
import draw_pd_vn_transgear_collar_flat_pin as drawing
import pd_transgear_drive_collar_spec as collar
import pd_vn_transgear_collar_flat_pin_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _fit_ream_h7 import REAM_H7
from _mcmaster_90145a414 import DOWEL_SIZE
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_90145A414 as recipe

_STEM = "pd-vn-transgear-collar-flat-pin"
_IN = 25.4


def test_catalogue_identity_is_registered_end_to_end() -> None:
    stock = FASTENERS[_STEM]
    row = _config.parts(_STEM)
    assert part.PART_NAME == _STEM
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.material == row["material"]
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert row["number"] == collar.FLAT_PIN_NUMBER
    assert row["quantity"] == 1
    assert row["process"] == "purchased"
    assert row["drawing_unit"] == spec.UNIT == "in"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_90145A414
    assert metadata.threaded is False


def test_the_pin_is_not_another_identitys_sku() -> None:
    """One SKU in two identities would force a Shared identity (AGENTS.md)."""
    for stem, stock in FASTENERS.items():
        if stem != _STEM:
            assert spec.SKU not in stock.skus, stem


def test_standalone_recipe_run_is_catalog_only(monkeypatch) -> None:
    """No vendor model is tracked: the standalone run builds and saves the
    nominal catalogue cylinder and never enters a replica path."""
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert spec.SKU not in REGISTRY
    assert not list(
        Path(__file__)
        .resolve()
        .parents[2]
        .glob(f"cad/references/**/{spec.SKU}*.SLDPRT")
    )
    seen: list = []

    async def fake_catalog(adapter, part_no, size, ends):
        seen.append((part_no, size, ends))
        return {}

    monkeypatch.setattr(recipe, "build_catalog", fake_catalog)
    asyncio.run(recipe._catalog(None))
    assert seen == [(spec.SKU, (spec.DIA, spec.LENGTH), None)]


def test_catalogue_size_and_supplier_reference() -> None:
    assert (
        DOWEL_SIZE
        == (spec.DIA, spec.LENGTH)
        == pytest.approx((_IN / 16.0, 3.0 * _IN / 16.0))
    )
    # The stainless dowel's own band, never undersize.
    assert min(spec.DIA_BAND_IN) >= 0.0
    assert spec.DIA_LIMITS_MM[0] == pytest.approx(spec.DIA)
    assert spec.DIA_LIMITS_MM[1] > spec.DIA
    assert spec.LENGTH_LIMITS_MM[0] < spec.LENGTH < spec.LENGTH_LIMITS_MM[1]
    ref = spec.SUPPLIER_REFERENCE
    assert (ref.sku, ref.units, ref.sheet_unit) == (spec.SKU, "in", "in")
    assert (ref.diameter_mm, ref.length_mm) == (spec.DIA, spec.LENGTH)


def test_press_hole_grips_at_both_extremes_and_is_the_collars_hole() -> None:
    assert spec.PRESS_HOLE_BAND == REAM_H7
    low, high = spec.PRESS_INTERFERENCE_MM
    assert 0.0 < low < high
    # Smallest pin in the largest hole, largest pin in the smallest hole.
    assert low == pytest.approx(
        min(spec.DIA_LIMITS_MM) - spec.PRESS_HOLE_DIA - max(REAM_H7)
    )
    assert high == pytest.approx(max(spec.DIA_LIMITS_MM) - spec.PRESS_HOLE_DIA)
    assert collar.FLAT_PIN_HOLE_DIA == spec.PRESS_HOLE_DIA
    assert collar.FLAT_PIN_HOLE_BAND == spec.PRESS_HOLE_BAND
    # Negative control: the pin's own nominal size reamed would not grip.
    assert spec.DIA - (spec.DIA + max(REAM_H7)) < 0.0


def test_the_model_is_the_nominal_cylinder() -> None:
    from diagnostics.diag_mcmaster_dowel import dowel_volume

    assert recipe.ENDS is None
    assert dowel_volume(DOWEL_SIZE) == pytest.approx(
        math.pi * (spec.DIA / 2.0) ** 2 * spec.LENGTH
    )


def test_purchased_sheet_has_the_actual_source_and_cli_stem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sheet = DRAWINGS_BY_NAME["pd_vn_transgear_collar_flat_pin"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == "Ø1/16 x 3/16 DOWEL PIN"
    assert sheet.source.stem == sheet.artifact_stem == part.PART_NAME
    assert sheet.script.name == "draw_pd_vn_transgear_collar_flat_pin.py"
    monkeypatch.setattr("sys.argv", [str(sheet.script), _STEM])
    assert drawing._parse_args().part == _STEM


def test_the_assembled_pin_is_faced_flush_and_crest_broken_with_the_collar() -> None:
    """The default configuration is the stock pin faced to the collar's
    modelled pin length with the collar's rear break through its crest;
    suppressing both cuts restores the catalogue pin."""
    assert part.FACED_LENGTH == collar.FLAT_PIN_LENGTH
    assert collar.FLAT_PIN_FLOOR + part.FACED_LENGTH <= collar.LENGTH + 1e-9
    assert part.V_FACED == pytest.approx(part.V_STOCK * part.FACED_LENGTH / spec.LENGTH)
    assert part.V_FACED < part.V_STOCK
    assert spec.SUPPLIER_STOCK_SUPPRESSED_FEATURES == ("StockFacing", "CrestBreak")
    assert spec.SUPPLIER_STOCK_CONFIGURATION != "Default"
    named = {
        node.args[1].value
        for node in ast.walk(ast.parse(Path(part.__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "name_last_feature"
        and isinstance(node.args[1], ast.Constant)
    }
    assert set(spec.SUPPLIER_STOCK_SUPPRESSED_FEATURES) <= named


def test_the_crest_break_is_the_collars_rear_break_cone() -> None:
    """The cone opens to the collar bore's radius plus the break's leg at the
    faced end and closes at 45°; at the nominal centre it reaches the crest
    and cuts only a sliver of the pin."""
    face_r = collar.BORE_DIA / 2.0 + collar.REAR_BREAK
    crest = collar.FLAT_PIN_CENTRE - spec.DIA / 2.0
    assert face_r > crest
    # A full-length cut of the cone's cross-section over its reach.
    step = face_r / 400
    riemann = step * sum(
        collar.circle_overlap_area(
            face_r - (i + 0.5) * step, spec.DIA / 2.0, collar.FLAT_PIN_CENTRE
        )
        for i in range(400)
    )
    assert part.V_CREST_BREAK == pytest.approx(riemann, rel=0.01)
    assert 0.0 < part.V_CREST_BREAK < 0.02 * part.V_FACED
    assert part.V_FACED_BROKEN == pytest.approx(part.V_FACED - part.V_CREST_BREAK)
    # Negative control: a cone no wider than the crest's radius cuts nothing.
    assert collar.cone_cylinder_volume(
        crest, crest, spec.DIA / 2.0, collar.FLAT_PIN_CENTRE
    ) == (pytest.approx(0.0, abs=1e-6))


def test_a_faced_length_past_the_stock_pin_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(collar, "FLAT_PIN_LENGTH", spec.LENGTH + 0.1)
    module = importlib.util.spec_from_file_location(
        "_flat_pin_perturbed", part.__file__
    )
    with pytest.raises(AssertionError, match="not a length of the stock pin"):
        module.loader.exec_module(importlib.util.module_from_spec(module))


def test_the_purchased_sheet_draws_the_as_supplied_configuration() -> None:
    """The sheet's supplier length dimension measures the catalogue pin, so
    its views reference the unfaced configuration."""
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    (call,) = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_purchased_fastener_drawing"
    ]
    keywords = {k.arg: ast.unparse(k.value) for k in call.keywords}
    assert keywords["configuration"] == "SUPPLIER_STOCK_CONFIGURATION"
    assert drawing.SUPPLIER_STOCK_CONFIGURATION == spec.SUPPLIER_STOCK_CONFIGURATION
