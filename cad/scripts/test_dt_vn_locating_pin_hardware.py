"""Offline part, recipe and fit contracts for dt-vn-locating-pin.

Its purchase sheet retired for a HARDWARE.md row (#2886); these checks pin
the part the assemblies still build.
"""

from __future__ import annotations

import pytest

import _config
import build_dt_vn_locating_pin as part
import dt_vn_locating_pin_spec as spec
from _fastener_catalog import FASTENERS
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
    assert (
        DOWEL_SIZE
        == (spec.DIA, spec.LENGTH)
        == pytest.approx((_IN / 16.0, 3.0 * _IN / 8.0))
    )
    assert spec.DIA_BAND_IN == (0.0001, 0.0003)
    assert spec.LENGTH_GRADE == pytest.approx(0.010 * _IN)
    assert spec.LENGTH_LIMITS_MM == pytest.approx((0.365 * _IN, 0.385 * _IN))
    ref = spec.SUPPLIER_REFERENCE
    assert (ref.sku, ref.units, ref.sheet_unit) == (spec.SKU, "in", "in")
    assert (ref.diameter_mm, ref.length_mm) == (spec.DIA, spec.LENGTH)
