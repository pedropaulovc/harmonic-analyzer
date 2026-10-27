"""SolidWorks-free physical and registry contracts for TL-VN-77."""
from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import _config
import build_ch_rocker_arm_tl_vn_oblique_pivot_screw as part
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _supplier_screw_reference_names import FEATURE_BY_PLANE

STEM = "ch-rocker-arm-tl-vn-oblique-pivot-screw"


def test_envelope_volume_has_all_three_supplied_sections():
    assert part.MODEL_VOLUME == pytest.approx(
        math.pi / 4.0 * (10.0**2 * 35.0 + 16.0**2 * 4.5 + 8.0**2 * 13.0)
    )


@pytest.mark.parametrize("offset,reverse", [(0.0, False), (35.0, False), (0.0, True)])
def test_native_section_frame_and_direction(monkeypatch, offset, reverse):
    circles = AsyncMock()
    monkeypatch.setattr(part, "define_circle", circles)
    monkeypatch.setattr(part, "ensure_fully_defined", AsyncMock())
    monkeypatch.setattr(part, "check", lambda label, value: value)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    blanked = []
    monkeypatch.setattr(part, "blank_reference_geometry", lambda _adapter, refs: blanked.extend(refs))
    adapter = SimpleNamespace(
        create_plane=AsyncMock(return_value=SimpleNamespace(name="HeadPlane")),
        create_sketch=AsyncMock(), exit_sketch=AsyncMock(), create_extrusion=AsyncMock(),
    )
    asyncio.run(part._ring(adapter, "Section", 10.0, 0.0, 13.0, offset=offset, reverse=reverse))
    adapter.create_sketch.assert_awaited_once_with("HeadPlane" if offset else "Front")
    circles.assert_awaited_once_with(adapter, 0.0, 0.0, 5.0, "Section OD")
    extrusion = adapter.create_extrusion.call_args.args[0]
    assert extrusion.depth == 13.0
    assert extrusion.reverse_direction is reverse
    if offset:
        plane = adapter.create_plane.call_args.args[0]
        assert plane.base_plane == "Front Plane"
        assert plane.offset == offset
        assert blanked == [("HeadPlane", "PLANE")]
    else:
        adapter.create_plane.assert_not_awaited()


def test_catalogue_and_current_identity():
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert row["number"] == "MHA-CH-06-TL-VN-77"
    assert row["process"] == "purchased"
    assert row["supplier"] == stock.supplier == "McMaster-Carr"
    assert tuple(row["supplier_skus"]) == stock.skus == ('90323A492',)
    assert row["stock_name"] == stock.stock_name
    assert row["material"] == stock.material == part.MATERIAL
    assert row["quantity"] == spec.QUANTITY == 2


def test_supplier_dimensions_and_physical_contract():
    assert spec.SKU == "90323A492"
    assert (spec.SHOULDER_DIA, spec.SHOULDER_DIA_BAND) == (10.0, (0.0, -0.025))
    assert (spec.SHOULDER_LENGTH, spec.SHOULDER_LENGTH_BAND) == (35.0, (0.05, 0.0))
    assert (spec.THREAD, spec.THREAD_LENGTH) == ("M8x1.25", 13.0)
    assert (spec.HEAD_DIA, spec.HEAD_HEIGHT, spec.HEX) == (16.0, 4.5, 5.0)
    assert spec.AXIS_NAME == part.AXIS_NAME == "PivotAxis"
    # A plain purchased pivot permits the owner-approved 0..0.040 diametral range.
    assert (10.0 - (spec.SHOULDER_DIA + max(spec.SHOULDER_DIA_BAND)),
            10.015 - (spec.SHOULDER_DIA + min(spec.SHOULDER_DIA_BAND))) == pytest.approx((0.0, 0.040))


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
        # Diameters are horizontal chords; only the shoulder length is axial.
        assert orientation == ("vertical" if name == "SupplierShoulderLength" else "horizontal")
        assert spec.SUPPLIER_REFERENCE_UNITS[name] == "mm"
    assert all(lower <= upper for lower, upper in spec.SUPPLIER_REFERENCE_TOLERANCES_MM.values())
    # The head hides the shoulder in the head-end Front view: measure it in Top,
    # at the shoulder's thread-end step, its Ø wider than the M8 thread it clears.
    assert spec.SUPPLIER_REFERENCE_PLANES["SupplierShoulderDiameter"] == "Top"
    assert spec.SUPPLIER_REFERENCE_STARTS["SupplierShoulderDiameter"] == (-spec.SHOULDER_DIA / 2.0, 0.0)
    assert spec.SHOULDER_DIA > spec.THREAD_DIA


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
    assert calls == [('Shoulder', 10.0, 0.0, 35.0, {}), ('Head', 16.0, 0.0, 4.5, {'offset': 35.0}), ('ThreadEnvelope', 8.0, 0.0, 13.0, {'reverse': True})]
    axis = adapter.create_axis.call_args.args[0]
    assert axis.mode == "two_planes"
    assert set(axis.planes) == {"Top Plane", "Right Plane"}
    part.volume_check.assert_awaited_once()
    assert part.MODEL_VOLUME > 0.0
    saved.assert_awaited_once_with(adapter, STEM)


def test_purchased_sheet_documents_built_part():
    import draw_ch_rocker_arm_tl_vn_oblique_pivot_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
