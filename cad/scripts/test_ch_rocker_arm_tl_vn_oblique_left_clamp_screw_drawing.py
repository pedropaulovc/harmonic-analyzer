"""Offline contracts for the MHA-CH-06-TL-VN-86 left clamp screw (McMaster 92220A165)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import _config
import _mcmaster_92220a165 as dims
import build_ch_rocker_arm_tl_vn_oblique_left_clamp_screw as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_vn_oblique_left_clamp_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _socket_head_dimensions import SocketHeadScrew
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_92220A165 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-left-clamp-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("92220A165",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-86"
    assert row["process"] == "purchased"
    notes = row["installation_notes"]
    assert "CUT TO THE ACTUAL STRAP/RISER GRIP AT ASSEMBLY" in notes
    assert "MHA-CH-06-TL-00 STEP O6" in notes
    assert "CUT-END\nCHAMFER CONTROLS ON THIS SHEET" in notes
    # The reflowed footer fits the purchased sheet's reserved note space
    # (native failure: one 151-character line ran to x = .2969 m).
    from _purchased_fastener_drawing import MAX_ITEM_CHARS, note_lines

    lines = note_lines(notes, label=STEM)
    assert 1 < len(lines) <= 3
    assert max(len(line) for line in lines) <= MAX_ITEM_CHARS
    assert spec.SKU in row["material_specification"]
    metadata = recipe_declaration(spec.SKU, recipe.build_92220A165)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_92220A165
    assert metadata.threaded is True


def test_production_build_is_the_cut_screw_with_its_native_chamfer(monkeypatch) -> None:
    seen: dict = {}

    async def stock_fastener(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", stock_fastener)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    # The author re-cuts the tip after the recipe; wraps keeps the recipe's
    # declaration, so the stock row still resolves to 92220A165's recipe.
    assert component.author is not recipe.build_92220A165
    assert component.author.__wrapped__ is recipe.build_92220A165
    assert recipe_declaration(spec.SKU, component.author).module == recipe.__name__
    assert component.parameters == {"cut_length": spec.CUT_LENGTH}
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_cut_end_chamfer_is_a_native_toleranced_control() -> None:
    low, high = spec.TIP_CHAMFER
    # Modelled at the band's maximum, banded down to its minimum.
    assert spec.TIP_CHAMFER_LENGTH == high
    assert spec.TIP_CHAMFER_BAND == (0.0, low - high)
    assert (high, low) == pytest.approx((0.035 * IN, 0.030 * IN))
    # It contains the recipe's 0.75P chamfer, so the native control is the tip.
    assert dims.DIMS.tip_chamfer == pytest.approx(0.75 * dims.DIMS.pitch)
    assert dims.DIMS.tip_chamfer <= spec.TIP_CHAMFER_LENGTH
    assert spec.TIP_CHAMFER_ANGLE == 45.0
    assert spec.DRAWING_DIMENSIONS == {
        "TipChamferProfile": {"ChamferLength", "ChamferAngle"}
    }
    assert spec.DIMENSION_TOLERANCE_TYPES == {"ChamferLength": 2, "ChamferAngle": 11}
    assert spec.DIMENSION_PRECISION == {"ChamferLength": 3, "ChamferAngle": 0}
    callout = spec.DIMENSION_CALLOUTS["ChamferLength"]
    assert spec.CARRIER_NUMBER in callout and "1.5D" in callout
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "*deviations(TIP_CHAMFER_BAND)" in source
    assert "mark_dimensions_for_drawing(adapter, feature, names)" in source
    assert "tolerance.Type = 11" in source
    assert "angle.DrivenState = 2" in source


def test_sheet_prints_and_rereads_the_cut_end_controls() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_left_clamp_screw as drawing

    assert set(drawing.EXPECTED_CONTROLS) == set(spec.DIMENSION_TOLERANCE_TYPES)
    nominal, lower, upper = drawing.EXPECTED_CONTROLS["ChamferLength"]
    assert nominal * 1000 == pytest.approx(spec.TIP_CHAMFER[1])
    assert (nominal + lower) * 1000 == pytest.approx(spec.TIP_CHAMFER[0])
    assert upper == 0.0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "dimensions_by_feature=supplier.DRAWING_DIMENSIONS" in source
    assert "_verify_cut_end_controls(adapter, controls)" in source
    assert drawing.SUPPLIER_MARGINS["*Front"][1] >= drawing._CUT_END_TEXT_ROOM


def test_recipe_refuses_a_cut_outside_the_bought_screw() -> None:
    for cut in (0.0, dims.DIMS.length):
        with pytest.raises(ValueError):
            asyncio.run(recipe.build_92220A165(None, cut_length=cut))


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_92220A165
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/92220A165*.SLDPRT"))


def test_recipe_is_the_catalogue_low_head_screw() -> None:
    d = dims.DIMS
    assert type(d) is SocketHeadScrew
    assert d.part_no == spec.SKU
    assert d.major_dia == pytest.approx(0.19 * IN)
    assert d.pitch == pytest.approx(IN / 24.0)
    assert d.length == pytest.approx(0.75 * IN)
    assert d.head_dia == pytest.approx(5.0 / 16.0 * IN)
    assert d.head_h == pytest.approx(3.0 / 32.0 * IN)
    assert d.socket_af == pytest.approx(3.0 / 32.0 * IN)
    assert d.socket_depth == pytest.approx(0.072 * IN)
    assert d.fully_threaded


def test_cut_screw_engages_the_blind_tap_and_clears_its_floor() -> None:
    low, high = spec.CUT_INSERTION
    chamfer_low, chamfer_high = spec.TIP_CHAMFER
    assert 0.0 < low < high
    assert 0.0 < chamfer_low < chamfer_high
    assert 0.0 < spec.CUT_LENGTH < dims.DIMS.length
    assert spec.CUT_LENGTH == spec.ROW.cut_length_mm
    # Engagement at the LONGEST chamfer and shallowest reach (rule 18: only
    # full-form thread counts).
    assert spec.ENGAGEMENT_MIN == pytest.approx(
        min(low - chamfer_high - carrier.TAP_MOUTH_BREAK, carrier.LEFT_CLAMP_FULL_THREAD_MIN)
    )
    assert spec.ENGAGEMENT_MIN >= 1.5 * dims.DIMS.major_dia
    # Runout at the SHORTEST chamfer and deepest reach: the external full form
    # never passes the receiver's guaranteed full thread (codjiflo PR #2228).
    assert spec.FULL_THREAD_END_MAX == pytest.approx(high - chamfer_low)
    assert spec.FULL_THREAD_END_MAX <= carrier.LEFT_CLAMP_THREAD_DEPTH
    # Mutation witness: the old proof passed an 8.85 reach that, at the
    # recipe's real 0.75P chamfer, ran 8.056 deep.
    assert 8.85 - dims.DIMS.tip_chamfer > carrier.LEFT_CLAMP_THREAD_DEPTH
    # Past both full forms the screw's crest falls faster than the tap lead's
    # root, so the truncated crest never meets the incomplete internal thread.
    assert spec.LEAD_ROOT_SLOPE_MAX == pytest.approx(
        (dims.DIMS.major_dia - carrier.LEFT_CLAMP_TAP_DRILL) / 2.0 / dims.DIMS.pitch
    )
    assert spec.LEAD_ROOT_SLOPE_MAX < spec.CHAMFER_RADIAL_SLOPE_MIN
    assert spec.MODEL_FULL_THREAD_END == pytest.approx(
        spec.CUT_LENGTH - spec.ROW.grip_mm - spec.TIP_CHAMFER_LENGTH
    )
    assert (
        spec.SCREW_FULL_THREAD_MIN + carrier.TAP_MOUTH_BREAK
        <= spec.MODEL_FULL_THREAD_END
        <= spec.FULL_THREAD_END_MAX
    )
    assert high < spec.PILOT_DEPTH_MIN
    assert dims.DIMS.neck_h < spec.ROW.grip_mm
    # No "one pitch" ceiling stands in for the proof above.
    spec_source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "under one incomplete pitch" not in spec_source


def test_cut_length_is_a_reference_beside_the_stock_witness() -> None:
    names = [name for name, _value, _orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS]
    assert names[:2] == ["CutLength", "SupplierLength"]
    assert spec.SUPPLIER_REFERENCE_FORMATS["CutLength"][3] == "CUT TO FIT"
    assert spec.SUPPLIER_REFERENCE_FORMATS["SupplierLength"][3] == (
        "AS-SUPPLIED STOCK LENGTH"
    )
    assert spec.SUPPLIER_REFERENCE_STARTS["SupplierThreadDiameter"] == (
        -dims.DIMS.major_dia / 2.0,
        -spec.CUT_LENGTH,
    )


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_left_clamp_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_left_clamp_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT == "#10-24 X 3/4 LOW-HEAD SHCS"
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
