"""Offline source contracts for MHA-PD-VN-64; no native or load-family certificate."""
from __future__ import annotations

import math

import pytest

import _config
import build_pd_vn_transgear_arm_plate_locating_pin as part
import draw_pd_vn_transgear_arm_plate_locating_pin as drawing
import pd_vn_transgear_arm_plate_locating_pin_spec as spec
import _transgear_arm_plate_locating_interface as interface
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_93600A189 as recipe
from _mcmaster_93600a189 import DOWEL_SIZE


def test_live_sourced_identity_is_registered_end_to_end() -> None:
    stock = FASTENERS[spec.PART_STEM]
    row = _config.parts(spec.PART_STEM)
    assert part.PART_NAME == spec.PART_STEM
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.material == spec.MATERIAL == "AISI 304"
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert row["number"] == spec.PART_NUMBER == "MHA-PD-VN-64"
    assert row["quantity"] == spec.ASSEMBLY_QUANTITY == 2
    assert row["installation_notes"] == spec.PURCHASED_STOCK_NOTE
    lines = row["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines)
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_93600A189
    assert metadata.threaded is False
    from diagnostics.diag_build_mcmaster import REGISTRY
    assert REGISTRY[spec.SKU] is recipe.build_93600A189


def test_reference_model_is_nominal_not_an_unsourced_end_replica() -> None:
    assert DOWEL_SIZE == (spec.DIA, spec.LENGTH) == (2.0, 6.0)
    source = spec.nominal_material_properties()
    assert source["volume_mm3"] == pytest.approx(math.pi * 6.0)
    assert source["mass_kg"] == pytest.approx(source["volume_mm3"] * 8000.0e-9)
    assert source["centre_of_mass_local_mm"] == (0.0, 3.0, 0.0)
    assert "reference cylinder" in source["model_scope"]
    assert spec.LENGTH_LIMITS_MM == pytest.approx((5.75, 6.25))
    assert spec.END_FORM_REFERENCE_MM == pytest.approx(0.35)


def test_standard_press_slip_and_length_family_fit_the_custom_arm_and_plate() -> None:
    assert spec.PRESS_INTERFERENCE_MM == pytest.approx((0.002, 0.018))
    assert spec.SLIP_DIAMETRAL_CLEARANCE_MM == pytest.approx((0.002, 0.018))
    assert spec.INSERTION_LIMITS_MM == pytest.approx((4.02, 4.58))
    assert "PUNCH OUT FROM THE FRONT" in " ".join(spec.PURCHASED_STOCK_NOTE.split())
    assert interface.HOLE_MOUTH_BREAK_AXIAL_MAX_MM == interface.HOLE_MOUTH_BREAK_RADIAL_MAX_MM == 0.05




def test_purchased_sheet_has_the_actual_source_and_cli_stem(monkeypatch: pytest.MonkeyPatch) -> None:
    sheet = DRAWINGS_BY_NAME["pd_vn_transgear_arm_plate_locating_pin"]
    assert drawing.SPEC is sheet
    assert sheet.source.stem == sheet.artifact_stem == part.PART_NAME
    assert sheet.script.name == "draw_pd_vn_transgear_arm_plate_locating_pin.py"
    monkeypatch.setattr("sys.argv", [str(sheet.script), spec.PART_STEM])
    assert drawing._parse_args().part == spec.PART_STEM


