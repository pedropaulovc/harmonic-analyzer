"""Offline source contracts for MHA-DT-VN-69; no native or load-family certificate."""
from __future__ import annotations

import pytest

import _config
import build_dt_vn_locating_pin as part
import draw_dt_vn_locating_pin as drawing
import dt_vn_locating_pin_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _fit_ream_h7 import REAM_H7
from _mcmaster_98381a417 import DOWEL_SIZE
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_98381A417 as recipe

_STEM = "dt-vn-locating-pin"
_IN = 25.4


def test_catalogue_identity_is_registered_end_to_end() -> None:
    stock = FASTENERS[_STEM]
    row = _config.parts(_STEM)
    assert part.PART_NAME == _STEM
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("98381A417",)
    assert stock.material == row["material"] == "Alloy Steel"
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert row["number"] == "MHA-DT-VN-69"
    assert row["quantity"] == 1
    assert row["drawing_unit"] == spec.UNIT == "in"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98381A417
    assert metadata.threaded is False


def test_the_pin_is_not_another_dowel_identitys_sku() -> None:
    """One SKU in two identities would force a Shared identity (AGENTS.md)."""
    for stem, stock in FASTENERS.items():
        if stem != _STEM:
            assert spec.SKU not in stock.skus, stem


def test_catalogue_size_and_supplier_reference() -> None:
    assert DOWEL_SIZE == (spec.DIA, spec.LENGTH) == pytest.approx((_IN / 16.0, 3.0 * _IN / 8.0))
    assert spec.DIA_BAND_IN == (0.0001, 0.0003)
    assert spec.LENGTH_GRADE == pytest.approx(0.010 * _IN)
    assert spec.LENGTH_LIMITS_MM == pytest.approx((0.365 * _IN, 0.385 * _IN))
    ref = spec.SUPPLIER_REFERENCE
    assert (ref.sku, ref.units, ref.sheet_unit) == (spec.SKU, "in", "in")
    assert (ref.diameter_mm, ref.length_mm) == (spec.DIA, spec.LENGTH)


def test_press_hole_contract_grips_at_both_extremes() -> None:
    assert spec.PRESS_HOLE_DIA == pytest.approx(0.0620 * _IN)
    assert spec.PRESS_HOLE_BAND == REAM_H7
    low, high = spec.PRESS_INTERFERENCE_MM
    assert low == pytest.approx(0.0001 * _IN)
    assert high == pytest.approx(0.0008 * _IN)


def test_purchased_sheet_has_the_actual_source_and_cli_stem(monkeypatch: pytest.MonkeyPatch) -> None:
    sheet = DRAWINGS_BY_NAME["dt_vn_locating_pin"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == "Ø1/16 x 3/8 DOWEL PIN"
    assert sheet.source.stem == sheet.artifact_stem == part.PART_NAME
    assert sheet.script.name == "draw_dt_vn_locating_pin.py"
    monkeypatch.setattr("sys.argv", [str(sheet.script), _STEM])
    assert drawing._parse_args().part == _STEM
