"""SolidWorks-free physical and registry contracts for TL-VN-80."""
from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import _config
import build_ch_rocker_arm_tl_vn_oblique_hub_pin as part
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_hub_pin_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS

STEM = "ch-rocker-arm-tl-vn-oblique-hub-pin"
INCH = 25.4


def test_envelope_volume_uses_cut_not_supply_length():
    assert part.MODEL_VOLUME == pytest.approx(math.pi / 4.0 * spec.DIA**2 * spec.CUT_LENGTH)
    assert spec.CUT_LENGTH < spec.SUPPLY_LENGTH


def test_native_pin_is_a_straight_unstepped_cut_blank(monkeypatch):
    circles = AsyncMock()
    monkeypatch.setattr(part, "define_circle", circles)
    monkeypatch.setattr(part, "ensure_fully_defined", AsyncMock())
    monkeypatch.setattr(part, "check", lambda label, value: value)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    adapter = SimpleNamespace(
        create_sketch=AsyncMock(), exit_sketch=AsyncMock(), create_extrusion=AsyncMock(),
    )
    asyncio.run(part._ring(adapter, "Pin", spec.DIA, 0.0, spec.CUT_LENGTH))
    adapter.create_sketch.assert_awaited_once_with("Front")
    circles.assert_awaited_once_with(adapter, 0.0, 0.0, spec.DIA / 2.0, "Pin OD")
    extrusion = adapter.create_extrusion.call_args.args[0]
    assert extrusion.depth == spec.CUT_LENGTH
    assert not extrusion.reverse_direction


def test_catalogue_and_current_identity():
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert row["number"] == "MHA-CH-06-TL-VN-80"
    assert row["process"] == "purchased"
    assert row["supplier"] == stock.supplier == "McMaster-Carr"
    assert tuple(row["supplier_skus"]) == stock.skus == (spec.CONFIGURED_SKU,)
    assert row["stock_name"] == stock.stock_name
    assert row["material"] == stock.material == part.MATERIAL
    assert row["quantity"] == spec.QUANTITY == 1


def test_supplier_dimensions_and_physical_contract():
    # The .4000 -.0001/0 Class Z NO-GO gauge, 2 in stock.
    assert spec.CONFIGURED_SKU.startswith(spec.SKU + "-")
    assert spec.DIA + max(spec.DIA_BAND) == pytest.approx(0.4000 * INCH)
    assert spec.DIA + min(spec.DIA_BAND) == pytest.approx(0.3999 * INCH)
    assert spec.SUPPLY_LENGTH == pytest.approx(2.0 * INCH)
    assert spec.BOND == "Loctite 638"
    # Fit doc F16: the bonded pin in the carrier's .4000-.4005 REAM_H7 hole
    # leaves a 0 to .0006 diametral bond gap.
    assert (carrier.HUB_BOND_CLEARANCE_MIN, carrier.HUB_BOND_CLEARANCE_MAX) == pytest.approx(
        (0.0, 0.0006 * INCH)
    )


def test_cut_length_closes_the_inch_stack():
    # Bottom flush with the carrier underside, factory top TIP_SET above the
    # riser: the bond runs the whole carrier and the length prints on .XX.
    assert spec.CUT_LENGTH == pytest.approx(
        trammel.CARRIER_THICK + trammel.RISER_THICK + spec.TIP_SET
    )
    cut_in = spec.CUT_LENGTH / INCH
    assert cut_in == pytest.approx(round(cut_in, spec.CUT_PLACES), abs=1e-9)
    assert jig.HUB_PIN_BOTTOM_Z == pytest.approx(trammel.CARRIER_UNDERSIDE_Z)
    # The set band keeps the factory top inside the strap's thinnest and the
    # pin in the strap's hub hole.
    assert spec.TIP_SET - spec.TIP_SET_BAND > 0.0
    assert spec.TIP_SET + spec.TIP_SET_BAND < rocker.ARM_THICKNESS + min(
        rocker.ARM_THICKNESS_BAND
    )


def test_native_supplier_witness_inventory():
    names = {name for name, _, _ in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert len(names) == len(spec.SUPPLIER_REFERENCE_DIMENSIONS)
    assert names == set(spec.SUPPLIER_REFERENCE_STARTS) == set(spec.SUPPLIER_REFERENCE_PLANES)
    assert names == set(spec.SUPPLIER_REFERENCE_FORMATS) == set(spec.SUPPLIER_REFERENCE_UNITS)
    assert names == set(spec.SUPPLIER_REFERENCE_SIDES)
    assert set(spec.SUPPLIER_REFERENCE_TOLERANCES_MM) <= names
    for name, value, orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS:
        assert value > 0
        assert spec.SUPPLIER_REFERENCE_PLANES[name] == "Top"
        assert orientation == "horizontal"
        assert spec.SUPPLIER_REFERENCE_UNITS[name] == spec.UNIT == "in"
    assert all(lower <= upper for lower, upper in spec.SUPPLIER_REFERENCE_TOLERANCES_MM.values())
    # The diameter's line lies on the Top view's far end-face edge (Top sketch
    # y is -z; the pin spans z 0..cut). The cut length is the extrusion's own
    # depth, a shop dimension with no construction line.
    assert spec.SUPPLIER_REFERENCE_STARTS == {
        "SupplierPinDiameter": (-spec.DIA / 2.0, -spec.CUT_LENGTH),
    }
    assert spec.CUT_FEATURE == "Pin" and spec.CUT_DIMENSION not in names


def test_build_uses_contract_dimensions_and_publishes_z_axis(monkeypatch):
    calls = []

    async def ring(adapter, name, od, bore, length, **kwargs):
        calls.append((name, od, bore, length, kwargs))

    monkeypatch.setattr(part, "_ring", ring)
    monkeypatch.setattr(part, "check", lambda label, value: value)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    monkeypatch.setattr(part, "blank_reference_geometry", lambda *args: None)
    monkeypatch.setattr(part, "apply_custom_properties", lambda *args: None)
    monkeypatch.setattr(part, "apply_package_model_units", lambda *args, **kwargs: None)
    for name in ("volume_check", "bbox_extent_check", "apply_material", "apply_color",
                 "_supplier_references", "report_mass_properties"):
        monkeypatch.setattr(part, name, AsyncMock())
    saved = AsyncMock(return_value={"part": STEM})
    monkeypatch.setattr(part, "save_part_and_images", saved)
    cut = []
    monkeypatch.setattr(part, "_shop_cut_dimension", cut.append)
    adapter = SimpleNamespace(create_part=AsyncMock(), create_axis=AsyncMock())
    assert asyncio.run(part.build(adapter)) == {"part": STEM}
    assert calls == [(spec.CUT_FEATURE, spec.DIA, 0.0, spec.CUT_LENGTH, {})]
    assert cut == [adapter]
    axis = adapter.create_axis.call_args.args[0]
    assert axis.mode == "two_planes"
    assert set(axis.planes) == {"Top Plane", "Right Plane"}
    part.volume_check.assert_awaited_once()
    assert part.MODEL_VOLUME > 0.0
    saved.assert_awaited_once_with(adapter, STEM)


def test_purchased_sheet_documents_built_part():
    import draw_ch_rocker_arm_tl_vn_oblique_hub_pin as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_hub_pin"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
