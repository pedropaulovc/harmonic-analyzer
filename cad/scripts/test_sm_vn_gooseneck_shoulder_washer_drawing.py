"""SolidWorks-free physical and registry contracts for MHA-SM-VN-57.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4: a thin washer under the
MHA-SM-VN-56 shoulder screw's head retains the counter spring's free upper
eye (McMaster 93475A250, DIN 125 M6, read live 2026-11-08; auto-selected
after the owner's ask timed out, pending owner confirmation).
"""
from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import _config
import build_sm_vn_gooseneck_shoulder_washer as part
import sm_vn_gooseneck_shoulder_screw_spec as screw
import sm_vn_gooseneck_shoulder_washer_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS

STEM = "sm-vn-gooseneck-shoulder-washer"


def test_envelope_volume_preserves_the_supplied_bore():
    assert part.MODEL_VOLUME == pytest.approx(math.pi / 4.0 * (spec.OD**2 - spec.ID**2) * spec.THICKNESS)


def test_native_section_is_the_nominal_washer(monkeypatch):
    circles = AsyncMock()
    monkeypatch.setattr(part, "define_circle", circles)
    monkeypatch.setattr(part, "ensure_fully_defined", AsyncMock())
    monkeypatch.setattr(part, "check", lambda label, value: value)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    adapter = SimpleNamespace(
        create_sketch=AsyncMock(), exit_sketch=AsyncMock(), create_extrusion=AsyncMock(),
    )
    asyncio.run(part._ring(adapter, "Ring", 12.0, 6.4, 1.6))
    adapter.create_sketch.assert_awaited_once_with("Front")
    assert [call.args[1:4] for call in circles.await_args_list] == [
        (0.0, 0.0, 6.0), (0.0, 0.0, 3.2)
    ]
    extrusion = adapter.create_extrusion.call_args.args[0]
    assert extrusion.depth == 1.6
    assert not extrusion.reverse_direction


def test_catalogue_and_current_identity():
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert row["number"] == "MHA-SM-VN-57"
    assert row["process"] == "purchased"
    assert row["supplier"] == stock.supplier == "McMaster-Carr"
    assert tuple(row["supplier_skus"]) == stock.skus == (spec.SKU,)
    assert row["stock_name"] == stock.stock_name
    assert row["material"] == stock.material == part.MATERIAL
    assert row["quantity"] == spec.QUANTITY == 1
    # #290: the sheet prints the registry row's drawing unit.
    assert row["drawing_unit"] == spec.UNIT == "mm"


def test_supplier_dimensions_and_physical_contract():
    assert spec.SKU == "93475A250"
    assert (spec.ID, spec.OD, spec.THICKNESS) == pytest.approx((6.4, 12.0, 1.6))
    # ISO 7089 grade A, M6 (the page states no ID/OD tolerance); the page's
    # thickness range.
    assert (spec.ID_MIN, spec.ID_MAX) == pytest.approx((6.40, 6.62))
    assert (spec.OD_MIN, spec.OD_MAX) == pytest.approx((11.57, 12.00))
    assert (spec.THICKNESS_MIN, spec.THICKNESS_MAX) == pytest.approx((1.4, 1.8))
    # The washer slides on the largest shoulder and the head covers its bore.
    assert spec.ID_MIN > screw.SHOULDER_DIA + max(screw.SHOULDER_DIA_BAND)
    assert screw.HEAD_DIA_MIN > spec.ID_MAX


def test_native_supplier_witness_inventory():
    names = {name for name, _, _ in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert len(names) == len(spec.SUPPLIER_REFERENCE_DIMENSIONS)
    assert names == set(spec.SUPPLIER_REFERENCE_STARTS) == set(spec.SUPPLIER_REFERENCE_PLANES)
    assert names == set(spec.SUPPLIER_REFERENCE_FORMATS) == set(spec.SUPPLIER_REFERENCE_UNITS)
    assert names == set(spec.SUPPLIER_REFERENCE_SIDES)
    for name, value, orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS:
        assert value > 0
        assert spec.SUPPLIER_REFERENCE_PLANES[name] == "Top"
        assert orientation == ("vertical" if name == "SupplierThickness" else "horizontal")
        assert spec.SUPPLIER_REFERENCE_UNITS[name] == "mm"
    assert spec.SUPPLIER_REFERENCE_STARTS == {
        "SupplierOuterDiameter": (-spec.OD / 2.0, -spec.THICKNESS),
        "SupplierThickness": (spec.OD / 2.0, -spec.THICKNESS),
    }
    assert spec.BORE_FEATURE == "RingProfile" and spec.BORE_DIMENSION not in names
    assert spec.BORE_FORMAT == (1, "diameter", None, "BORE")


def test_build_uses_contract_dimensions_and_publishes_z_axis(monkeypatch):
    calls = []

    async def ring(adapter, name, od, bore, length, **kwargs):
        calls.append((name, od, bore, length, kwargs))

    monkeypatch.setattr(part, "_ring", ring)
    monkeypatch.setattr(part, "check", lambda label, value: value)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    monkeypatch.setattr(part, "blank_reference_geometry", lambda *args: None)
    monkeypatch.setattr(part, "apply_package_model_units", lambda *args, **kwargs: None)
    monkeypatch.setattr(part, "apply_custom_properties", lambda *args: None)
    for name in ("volume_check", "bbox_extent_check", "apply_material", "apply_color",
                 "_supplier_references", "report_mass_properties"):
        monkeypatch.setattr(part, name, AsyncMock())
    saved = AsyncMock(return_value={"part": STEM})
    monkeypatch.setattr(part, "save_part_and_images", saved)
    bore = []
    monkeypatch.setattr(part, "_bore_reference", bore.append)
    adapter = SimpleNamespace(create_part=AsyncMock(), create_axis=AsyncMock())
    assert asyncio.run(part.build(adapter)) == {"part": STEM}
    assert calls == [("Ring", spec.OD, spec.ID, spec.THICKNESS, {})]
    assert bore == [adapter]
    axis = adapter.create_axis.call_args.args[0]
    assert axis.mode == "two_planes"
    assert set(axis.planes) == {"Top Plane", "Right Plane"}
    part.volume_check.assert_awaited_once()
    saved.assert_awaited_once_with(adapter, STEM)


def test_purchased_sheet_documents_built_part():
    import draw_sm_vn_gooseneck_shoulder_washer as drawing

    sheet = DRAWINGS_BY_NAME["sm_vn_gooseneck_shoulder_washer"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
