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
from _printed_tolerance import printed_band_mm

STEM = "ch-rocker-arm-tl-vn-oblique-pivot-screw"


def test_envelope_volume_has_all_three_supplied_sections_less_the_end_chamfer():
    ring = math.pi * spec.CUT_CHAMFER**2 * (spec.THREAD_DIA / 2.0 - spec.CUT_CHAMFER / 3.0)
    assert part.MODEL_VOLUME == pytest.approx(
        math.pi / 4.0 * (spec.SHOULDER_DIA**2 * spec.SHOULDER_LENGTH
                         + spec.HEAD_DIA**2 * spec.HEAD_HEIGHT
                         + spec.THREAD_DIA**2 * spec.CUT_THREAD_LENGTH) - ring
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
    assert row["supplier"] == stock.supplier == "Huyett"
    assert tuple(row["supplier_skus"]) == stock.skus == (spec.SKU,)
    assert row["stock_name"] == stock.stock_name
    assert row["material"] == stock.material == part.MATERIAL
    assert row["quantity"] == spec.QUANTITY == 2


def test_supplier_dimensions_and_physical_contract():
    inch = 25.4
    assert spec.SKU == "BLTS40-0375-1500188P"
    assert spec.SHOULDER_DIA == pytest.approx(0.375 * inch)
    assert spec.SHOULDER_DIA_BAND == pytest.approx((0.0, -0.001 * inch))
    assert spec.SHOULDER_LENGTH == pytest.approx(1.5 * inch)
    assert spec.THREAD == "5/16-18"
    assert spec.THREAD_PITCH == pytest.approx(inch / 18)
    # The shop cuts the supplied extended thread back; it never lengthens it.
    assert spec.THREAD_LENGTH == spec.CUT_THREAD_LENGTH < spec.SUPPLIED_THREAD_LENGTH
    assert spec.HEAD_DIA > spec.SHOULDER_DIA > spec.THREAD_DIA
    assert spec.AXIS_NAME == part.AXIS_NAME == "PivotAxis"
    assert spec.UNIT == "in"
    # The shoulder slides in the reamed seat with clearance at every band.
    import ch_rocker_arm_tl_oblique_pivot_block_spec as block

    seat_low = block.BORE_DIA + min(block.BORE_BAND)
    assert seat_low > spec.SHOULDER_DIA + max(spec.SHOULDER_DIA_BAND)


def test_native_supplier_witness_inventory():
    names = {name for name, _, _ in spec.REFERENCE_DIMENSIONS}
    assert len(names) == len(spec.REFERENCE_DIMENSIONS)
    assert names == set(spec.REFERENCE_STARTS) == set(spec.REFERENCE_FORMATS)
    assert set(spec.REFERENCE_TOLERANCES_MM) <= names
    for name, value, orientation in spec.REFERENCE_DIMENSIONS:
        assert value > 0
        # Diameters stand across the horizontal axis; only the shoulder length runs along it.
        assert orientation == ("horizontal" if name == "SupplierShoulderLength" else "vertical")
    assert all(lower <= upper for lower, upper in spec.REFERENCE_TOLERANCES_MM.values())
    # Every line lies on a Right-view edge (Right sketch x is model -z): the
    # shoulder Ø on the thread-end step, the shoulder length on the shoulder's
    # upper silhouette, the head Ø on the head's end face (z = LENGTH).
    assert spec.REFERENCE_STARTS == {
        "SupplierShoulderDiameter": (0.0, -spec.SHOULDER_DIA / 2.0),
        "SupplierShoulderLength": (-spec.SHOULDER_LENGTH, spec.SHOULDER_DIA / 2.0),
        "SupplierHeadDiameter": (-spec.LENGTH, -spec.HEAD_DIA / 2.0),
    }
    assert spec.SHOULDER_DIA > spec.THREAD_DIA


def test_cut_length_names_its_three_place_reason_and_sized_chamfer():
    import ch_rocker_arm_tl_oblique_pivot_block_spec as block

    assert spec.CUT_THREAD_PLACES == 3
    # A .XX cut would let TL-22's tip clearance fall under its .011 floor.
    loose = (block.PIVOT_TIP_CLEARANCE_MIN + printed_band_mm(3, unit="in")
             - printed_band_mm(2, unit="in"))
    assert loose < 0.011 * 25.4 - 1e-9 <= block.PIVOT_TIP_CLEARANCE_MIN
    assert "CHAMFER END .03 X 45°" in spec.CUT_CALLOUT
    assert "TL-22" in spec.CUT_CALLOUT
    assert spec.CUT_CHAMFER == pytest.approx(0.03 * 25.4)


def test_build_uses_contract_dimensions_and_publishes_z_axis(monkeypatch):
    calls = []

    async def ring(adapter, name, od, bore, length, **kwargs):
        calls.append((name, od, bore, length, kwargs))

    monkeypatch.setattr(part, "_ring", ring)
    monkeypatch.setattr(part, "check", lambda label, value: value)
    monkeypatch.setattr(part, "name_last_feature", lambda *args: None)
    monkeypatch.setattr(part, "blank_reference_geometry", lambda *args: None)
    monkeypatch.setattr(part, "apply_package_model_units", lambda *args, **kwargs: None)
    monkeypatch.setattr(part, "_shop_cut_dimension", lambda *args: None)
    monkeypatch.setattr(part, "apply_custom_properties", lambda *args: None)
    for name in ("volume_check", "bbox_extent_check", "apply_material", "apply_color",
                 "_supplier_references", "report_mass_properties"):
        monkeypatch.setattr(part, name, AsyncMock())
    saved = AsyncMock(return_value={"part": STEM})
    monkeypatch.setattr(part, "save_part_and_images", saved)
    adapter = SimpleNamespace(
        create_part=AsyncMock(), create_axis=AsyncMock(), add_chamfer=AsyncMock(),
    )
    assert asyncio.run(part.build(adapter)) == {"part": STEM}
    assert calls == [
        ("Shoulder", spec.SHOULDER_DIA, 0.0, spec.SHOULDER_LENGTH, {}),
        ("Head", spec.HEAD_DIA, 0.0, spec.HEAD_HEIGHT, {"offset": spec.SHOULDER_LENGTH}),
        (spec.CUT_FEATURE, spec.THREAD_DIA, 0.0, spec.CUT_THREAD_LENGTH, {"reverse": True}),
    ]
    adapter.add_chamfer.assert_awaited_once_with(
        spec.CUT_CHAMFER, [[spec.THREAD_DIA / 2.0, 0.0, -spec.CUT_THREAD_LENGTH]]
    )
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
