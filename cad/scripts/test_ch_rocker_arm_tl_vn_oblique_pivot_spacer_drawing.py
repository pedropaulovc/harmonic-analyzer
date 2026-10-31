"""SolidWorks-free physical and registry contracts for TL-VN-78."""
from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import _config
import build_ch_rocker_arm_tl_vn_oblique_pivot_spacer as part
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _supplier_screw_reference_names import FEATURE_BY_PLANE

STEM = "ch-rocker-arm-tl-vn-oblique-pivot-spacer"


def test_envelope_volume_preserves_the_supplied_bore():
    assert part.MODEL_VOLUME == pytest.approx(math.pi / 4.0 * (spec.OD**2 - spec.ID**2) * spec.LENGTH)


def test_native_section_is_an_annulus_in_the_front_plane(monkeypatch):
    circles = AsyncMock()
    monkeypatch.setattr(part, "define_circle", circles)
    monkeypatch.setattr(part, "ensure_fully_defined", AsyncMock())
    monkeypatch.setattr(part, "check", lambda label, value: value)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    adapter = SimpleNamespace(
        create_sketch=AsyncMock(), exit_sketch=AsyncMock(), create_extrusion=AsyncMock(),
    )
    asyncio.run(part._ring(adapter, "Ring", 16.0, 10.0, 15.0))
    adapter.create_sketch.assert_awaited_once_with("Front")
    assert [call.args[1:4] for call in circles.await_args_list] == [(0.0, 0.0, 8.0), (0.0, 0.0, 5.0)]
    extrusion = adapter.create_extrusion.call_args.args[0]
    assert extrusion.depth == 15.0
    assert not extrusion.reverse_direction


def test_catalogue_and_current_identity():
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert row["number"] == "MHA-CH-06-TL-VN-78"
    assert row["process"] == "purchased"
    assert row["supplier"] == stock.supplier == "AluminumSpacers.com"
    assert tuple(row["supplier_skus"]) == stock.skus == (spec.SKU,)
    assert row["stock_name"] == stock.stock_name
    assert row["material"] == stock.material == part.MATERIAL
    assert row["quantity"] == spec.QUANTITY == 2


def test_supplier_dimensions_and_physical_contract():
    import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as screw

    inch = 25.4
    assert spec.SKU == "AS62-18-40"
    assert spec.ID == pytest.approx(0.382 * inch)
    assert spec.OD == pytest.approx(0.625 * inch)
    assert spec.LENGTH == pytest.approx(0.625 * inch)
    assert spec.UNIT == "in"
    # The loose spacer clears the shoulder at every band; it never locates it.
    assert spec.ID + min(spec.ID_BAND) > screw.SHOULDER_DIA + max(screw.SHOULDER_DIA_BAND)
    assert spec.OD + min(spec.OD_BAND) > spec.ID + max(spec.ID_BAND)


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
        assert spec.SUPPLIER_REFERENCE_UNITS[name] == "in"
    assert all(lower <= upper for lower, upper in spec.SUPPLIER_REFERENCE_TOLERANCES_MM.values())


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
    adapter = SimpleNamespace(create_part=AsyncMock(), create_axis=AsyncMock())
    assert asyncio.run(part.build(adapter)) == {"part": STEM}
    assert calls == [("Ring", spec.OD, spec.ID, spec.LENGTH, {})]
    axis = adapter.create_axis.call_args.args[0]
    assert axis.mode == "two_planes"
    assert set(axis.planes) == {"Top Plane", "Right Plane"}
    part.volume_check.assert_awaited_once()
    assert part.MODEL_VOLUME > 0.0
    saved.assert_awaited_once_with(adapter, STEM)


def test_purchased_sheet_documents_built_part():
    import draw_ch_rocker_arm_tl_vn_oblique_pivot_spacer as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_spacer"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
