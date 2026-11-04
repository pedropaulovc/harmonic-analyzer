"""Offline source contracts for MHA-PD-VN-64; no native or load-family certificate."""
from __future__ import annotations

import math

import pytest

import _config
import build_pd_vn_transgear_arm_plate_locating_pin as part
import draw_pd_vn_transgear_arm_plate_locating_pin as drawing
import pd_vn_transgear_arm_plate_locating_pin_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_98381A435 as recipe
from _mcmaster_98381a435 import DOWEL_SIZE


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
    assert row["installation_notes"] == spec.PURCHASED_STOCK_NOTE
    lines = row["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines)
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98381A435
    assert metadata.threaded is False
    from diagnostics.diag_build_mcmaster import REGISTRY
    assert REGISTRY[spec.SKU] is recipe.build_98381A435


def test_the_dowel_is_not_the_crank_seat_drive_pin_sku() -> None:
    """One SKU in two assemblies would force a Shared identity (AGENTS.md)."""
    assert spec.SKU not in _config.parts("dt-vn-crank-seat-drive-pin")["supplier_skus"]


def test_reference_model_is_nominal_not_an_unsourced_end_replica() -> None:
    assert DOWEL_SIZE == (spec.DIA, spec.LENGTH) == pytest.approx((2.38125, 7.9375))
    source = spec.nominal_material_properties()
    assert source["volume_mm3"] == pytest.approx(math.pi * (spec.DIA / 2.0)**2 * spec.LENGTH)
    assert source["centre_of_mass_local_mm"] == (0.0, spec.LENGTH / 2.0, 0.0)
    assert "reference cylinder" in source["model_scope"]


def test_standard_press_slip_and_length_family_fit_the_custom_arm_and_plate() -> None:
    assert min(spec.PRESS_INTERFERENCE_MM) > 0.0
    assert min(spec.SLIP_DIAMETRAL_CLEARANCE_MM) > 0.0
    # The longest pin, pressed to the lowest proud set, stays inside the
    # arm's through hole (pd_transgear_arm_spec.LOCATOR_PUNCH_AIR_MIN_MM).
    assert max(spec.INSERTION_LIMITS_MM) < 7.9375 - 0.0254




def test_purchased_sheet_has_the_actual_source_and_cli_stem(monkeypatch: pytest.MonkeyPatch) -> None:
    sheet = DRAWINGS_BY_NAME["pd_vn_transgear_arm_plate_locating_pin"]
    assert drawing.SPEC is sheet
    assert sheet.source.stem == sheet.artifact_stem == part.PART_NAME
    assert sheet.script.name == "draw_pd_vn_transgear_arm_plate_locating_pin.py"
    monkeypatch.setattr("sys.argv", [str(sheet.script), spec.PART_STEM])
    assert drawing._parse_args().part == spec.PART_STEM


