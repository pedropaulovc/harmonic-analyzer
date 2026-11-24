"""Offline part, recipe and fit contracts for pd-vn-transgear-arm-plate-locating-pin.

Its purchase sheet retired for a HARDWARE.md row (#2886); these checks pin
the part the assemblies still build.
"""

from __future__ import annotations

import math

import pytest

import _config
import build_pd_vn_transgear_arm_plate_locating_pin as part
import pd_vn_transgear_arm_plate_locating_pin_spec as spec
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_98381A216 as recipe
from _mcmaster_98381a216 import DOWEL_SIZE


def test_live_sourced_identity_is_registered_end_to_end() -> None:
    stock = FASTENERS[spec.PART_STEM]
    row = _config.parts(spec.PART_STEM)
    assert part.PART_NAME == spec.PART_STEM
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.material == row["material"] == "Alloy Steel"
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert row["number"] == spec.PART_NUMBER == "MHA-PD-VN-64"
    assert row["quantity"] == spec.ASSEMBLY_QUANTITY == 2
    # Where the dowels go is MHA-PD-00's arm-plate-located step, not a part fact.
    assert "installation_notes" not in row
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98381A216
    assert metadata.threaded is False
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_98381A216


def test_the_dowel_sku_is_in_no_other_registered_part() -> None:
    """One SKU in two assemblies would force a Shared identity (AGENTS.md):
    the 1/8 latch pin and knife-mount dowels are other lengths, other SKUs."""
    assert spec.SKU == "98381A216"
    for stem, stock in FASTENERS.items():
        if stem != spec.PART_STEM:
            assert spec.SKU not in stock.skus, stem


def test_reference_model_is_nominal_not_an_unsourced_end_replica() -> None:
    # 1/8 x 5/16 (fit audit 2026-11-23): the over/under reamer set's .1240
    # and .1260 members cut its press and slip holes.
    assert DOWEL_SIZE == (spec.DIA, spec.LENGTH) == pytest.approx((3.175, 7.9375))
    source = spec.nominal_material_properties()
    assert source["volume_mm3"] == pytest.approx(
        math.pi * (spec.DIA / 2.0) ** 2 * spec.LENGTH
    )
    assert source["centre_of_mass_local_mm"] == (0.0, spec.LENGTH / 2.0, 0.0)
    assert "reference cylinder" in source["model_scope"]


def test_standard_press_slip_and_length_family_fit_the_custom_arm_and_plate() -> None:
    inch = 25.4
    # What the two set reamers are modelled to cut (+.0005/0) against the
    # catalogue dowel (+.0001/+.0003): analysis, not printed limits.
    assert spec.PRESS_INTERFERENCE_MM == pytest.approx((0.0006 * inch, 0.0013 * inch))
    assert spec.SLIP_DIAMETRAL_CLEARANCE_MM == pytest.approx(
        (0.0007 * inch, 0.0014 * inch)
    )
    # A dowel that slides into the arm by hand is bonded (MHA-PD-00 13G):
    # even an arm hole cut as large as the plate's stays inside LOCTITE 638's
    # gap.
    assert spec.BOND_GAP_MAX_MM == pytest.approx(0.0014 * inch)
    assert spec.BOND_GAP_MAX_MM <= spec.INTERFACE.BOND_GAP_LIMIT_MM == 0.25
    # The longest pin, pressed to the lowest proud set, stays inside the
    # arm's through hole (pd_transgear_arm_spec.LOCATOR_PUNCH_AIR_MIN_MM).
    assert max(spec.INSERTION_LIMITS_MM) < 7.9375 - 0.0254
