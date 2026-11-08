"""SolidWorks-free physical and registry contracts for MHA-SM-VN-56.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4: the counter spring's upper
eye rides free on the shoulder of McMaster 91259A576 (read live 2026-11-08),
seated on the MHA-SM-01 end face.
"""
from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import _config
import build_sm_vn_gooseneck_shoulder_screw as part
import sm_vn_gooseneck_shoulder_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS

STEM = "sm-vn-gooseneck-shoulder-screw"


def test_envelope_volume_has_all_three_supplied_sections():
    assert part.MODEL_VOLUME == pytest.approx(
        math.pi / 4.0 * (
            spec.SHOULDER_DIA**2 * spec.SHOULDER_LENGTH
            + spec.HEAD_DIA**2 * spec.HEAD_HEIGHT
            + spec.MAJOR_DIA**2 * spec.THREAD_LENGTH
        )
    )


@pytest.mark.parametrize("offset,reverse", [(0.0, False), (9.525, False), (0.0, True)])
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
    assert row["number"] == "MHA-SM-VN-56"
    assert row["process"] == "purchased"
    assert row["supplier"] == stock.supplier == "McMaster-Carr"
    assert tuple(row["supplier_skus"]) == stock.skus == (spec.SKU,)
    assert row["stock_name"] == stock.stock_name
    assert row["material"] == stock.material == part.MATERIAL
    assert row["quantity"] == spec.QUANTITY == 1
    # #290: the sheet prints the registry row's drawing unit.
    assert row["drawing_unit"] == spec.UNIT == "in"


def test_counter_seat_certificate_names_this_screw():
    import settled_spring_seats

    support = settled_spring_seats.counter_upper_support_geometry()
    assert support["component"] == STEM
    assert support["number"] == _config.parts(STEM)["number"]
    assert support["supplier_sku"] == spec.SKU


def test_supplier_dimensions_and_physical_contract():
    inch = 25.4
    assert spec.SKU == "91259A576"
    assert spec.SHOULDER_DIA == pytest.approx(5 / 16 * inch)
    assert spec.SHOULDER_DIA_BAND == pytest.approx((-0.002 * inch, -0.004 * inch))
    assert spec.SHOULDER_LENGTH == pytest.approx(0.375 * inch)
    assert spec.SHOULDER_LENGTH_BAND == pytest.approx((0.005 * inch, -0.005 * inch))
    assert (spec.THREAD, spec.THREAD_CLASS) == ("1/4-20", "3A")
    assert spec.PITCH == pytest.approx(inch / 20.0)
    assert spec.THREAD_LENGTH == pytest.approx(7 / 16 * inch)
    assert (spec.HEAD_DIA, spec.HEAD_HEIGHT) == pytest.approx((7 / 16 * inch, 7 / 32 * inch))
    assert spec.LENGTH == pytest.approx(spec.SHOULDER_LENGTH + spec.HEAD_HEIGHT)
    # ASME B18.3's 5/16 row: the head's least Ø and the necks the joint charges.
    assert spec.HEAD_DIA_MIN == pytest.approx(0.419 * inch)
    assert spec.THREAD_NECK_WIDTH_MAX == pytest.approx(0.100 * inch)
    assert spec.SHOULDER_NECK_DIA_MIN < spec.SHOULDER_DIA + min(spec.SHOULDER_DIA_BAND)
    assert spec.HEAD_DIA > spec.SHOULDER_DIA > spec.MAJOR_DIA


def test_native_supplier_witness_inventory():
    names = {name for name, _, _ in spec.REFERENCE_DIMENSIONS}
    assert len(names) == len(spec.REFERENCE_DIMENSIONS)
    assert names == set(spec.REFERENCE_STARTS) == set(spec.REFERENCE_FORMATS)
    for name, value, orientation in spec.REFERENCE_DIMENSIONS:
        assert value > 0
        assert orientation == ("horizontal" if name == "SupplierShoulderLength" else "vertical")
    assert spec.REFERENCE_STARTS == {
        "SupplierShoulderDiameter": (0.0, -spec.SHOULDER_DIA / 2.0),
        "SupplierShoulderLength": (-spec.SHOULDER_LENGTH, spec.SHOULDER_DIA / 2.0),
        "SupplierHeadDiameter": (-spec.LENGTH, -spec.HEAD_DIA / 2.0),
    }
    assert spec.THREAD_NOTE == "1/4-20 UNC-3A\n(AS SUPPLIED)"


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
    assert calls == [
        ("Shoulder", spec.SHOULDER_DIA, 0.0, spec.SHOULDER_LENGTH, {}),
        ("Head", spec.HEAD_DIA, 0.0, spec.HEAD_HEIGHT, {"offset": spec.SHOULDER_LENGTH}),
        (part.THREAD_FEATURE, spec.MAJOR_DIA, 0.0, spec.THREAD_LENGTH, {"reverse": True}),
    ]
    axis = adapter.create_axis.call_args.args[0]
    assert axis.mode == "two_planes"
    assert set(axis.planes) == {"Top Plane", "Right Plane"}
    part.volume_check.assert_awaited_once()
    saved.assert_awaited_once_with(adapter, STEM)


def test_purchased_sheet_documents_built_part():
    import draw_sm_vn_gooseneck_shoulder_screw as drawing

    sheet = DRAWINGS_BY_NAME["sm_vn_gooseneck_shoulder_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert set(drawing.SHELVES) <= {name for name, _, _ in spec.REFERENCE_DIMENSIONS}
