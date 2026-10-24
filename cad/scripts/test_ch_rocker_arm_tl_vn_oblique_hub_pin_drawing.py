"""SolidWorks-free physical and registry contracts for TL-VN-80."""
from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import _config
import build_ch_rocker_arm_tl_vn_oblique_hub_pin as part
import ch_rocker_arm_tl_vn_oblique_hub_pin_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _supplier_screw_reference_names import FEATURE_BY_PLANE

STEM = "ch-rocker-arm-tl-vn-oblique-hub-pin"


def test_envelope_volume_uses_cut_not_supply_length():
    assert part.MODEL_VOLUME == pytest.approx(math.pi / 4.0 * 10.2**2 * 20.0)


def test_native_pin_is_a_straight_unstepped_cut_blank(monkeypatch):
    circles = AsyncMock()
    monkeypatch.setattr(part, "define_circle", circles)
    monkeypatch.setattr(part, "ensure_fully_defined", AsyncMock())
    monkeypatch.setattr(part, "check", lambda label, value: value)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    adapter = SimpleNamespace(
        create_sketch=AsyncMock(), exit_sketch=AsyncMock(), create_extrusion=AsyncMock(),
    )
    asyncio.run(part._ring(adapter, "Pin", 10.2, 0.0, 20.0))
    adapter.create_sketch.assert_awaited_once_with("Front")
    circles.assert_awaited_once_with(adapter, 0.0, 0.0, 5.1, "Pin OD")
    extrusion = adapter.create_extrusion.call_args.args[0]
    assert extrusion.depth == 20.0
    assert not extrusion.reverse_direction


def test_catalogue_and_current_identity():
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert row["number"] == "MHA-CH-06-TL-VN-80"
    assert row["process"] == "purchased"
    assert row["supplier"] == stock.supplier == "McMaster-Carr"
    assert tuple(row["supplier_skus"]) == stock.skus == ('2281A11-6410N695',)
    assert row["stock_name"] == stock.stock_name
    assert row["material"] == stock.material == part.MATERIAL
    assert row["quantity"] == spec.QUANTITY == 1


def test_supplier_dimensions_and_physical_contract():
    assert spec.SKU == "2281A11"
    assert spec.CONFIGURED_SKU == "2281A11-6410N695"
    assert (spec.DIA, spec.DIA_BAND) == (10.2, (0.0, -0.00254))
    assert spec.SUPPLY_LENGTH == 50.8
    assert spec.CUT_LENGTH == 20.0 < spec.SUPPLY_LENGTH
    assert spec.BOND == "Loctite 638"
    assert (spec.TIP_SET, spec.TIP_SET_BAND) == (2.0, 0.2)
    assert (10.2 - (spec.DIA + max(spec.DIA_BAND)),
            10.218 - (spec.DIA + min(spec.DIA_BAND))) == pytest.approx((0.0, 0.02054))


def test_native_supplier_witness_inventory():
    names = {name for name, _, _ in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert len(names) == len(spec.SUPPLIER_REFERENCE_DIMENSIONS)
    assert names == set(spec.SUPPLIER_REFERENCE_STARTS) == set(spec.SUPPLIER_REFERENCE_PLANES)
    assert names == set(spec.SUPPLIER_REFERENCE_FORMATS) == set(spec.SUPPLIER_REFERENCE_UNITS)
    assert names == set(spec.SUPPLIER_REFERENCE_SIDES)
    assert set(spec.SUPPLIER_REFERENCE_TOLERANCES_MM) <= names
    for name, value, orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS:
        assert value > 0
        plane = spec.SUPPLIER_REFERENCE_PLANES[name]
        assert plane in FEATURE_BY_PLANE
        assert orientation == ("horizontal" if plane == "Front" else "vertical")
        assert spec.SUPPLIER_REFERENCE_UNITS[name] == "mm"
    assert all(lower <= upper for lower, upper in spec.SUPPLIER_REFERENCE_TOLERANCES_MM.values())


def test_build_uses_contract_dimensions_and_publishes_z_axis(monkeypatch):
    calls = []

    async def ring(adapter, name, od, bore, length, **kwargs):
        calls.append((name, od, bore, length, kwargs))

    monkeypatch.setattr(part, "_ring", ring)
    monkeypatch.setattr(part, "check", lambda label, value: value)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    monkeypatch.setattr(part, "blank_reference_geometry", lambda *args: None)
    monkeypatch.setattr(part, "apply_custom_properties", lambda *args: None)
    for name in ("volume_check", "bbox_extent_check", "apply_material", "apply_color",
                 "_supplier_references", "report_mass_properties"):
        monkeypatch.setattr(part, name, AsyncMock())
    saved = AsyncMock(return_value={"part": STEM})
    monkeypatch.setattr(part, "save_part_and_images", saved)
    adapter = SimpleNamespace(create_part=AsyncMock(), create_axis=AsyncMock())
    assert asyncio.run(part.build(adapter)) == {"part": STEM}
    assert calls == [('Pin', 10.2, 0.0, 20.0, {})]
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
