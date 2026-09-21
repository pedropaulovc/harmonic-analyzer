"""Offline behavioral contracts for the cone-tip-bushing drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import build_cone_tip_bushing as part
import cone_gear_shaft_spec
import cone_tip_bushing_spec as spec
import draw_cone_tip_bushing as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-bushing_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_tip_bushing"].script == Path(drawing.__file__).resolve()
    )


def test_part_and_drawing_share_the_native_dimension_contract() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.SIDE_KEEP)
    assert kept == marked == {"ODDim", "BoreDiaDim", "Depth"}
    assert drawing.DIMENSION_CALLOUTS == {"BoreDiaDim": "REAM THRU"}
    assert spec.OUTER_DIA == part.OD
    assert spec.BORE_DIA == part.BORE_DIA
    assert spec.LENGTH == part.LENGTH


def test_model_owns_the_printed_precision() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ODDim": 2,
        "BoreDiaDim": 3,
        "Depth": 2,
    }
    assert "draw_cone_tip_bushing.py" in PRECISION_MIGRATED_DRAWINGS


def test_bore_band_is_derived_live_from_the_enlarged_tip_journal_and_fit() -> None:
    assert _config.parts("cone-tip-bushing")["fit_class"] == "shaft_in_bushing"
    minimum, maximum = _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
    journal_upper, journal_lower = cone_gear_shaft_spec.SECTION_DIA_BAND
    assert spec.BORE_DIA == pytest.approx(1.5875)
    assert spec.BORE_DIA == pytest.approx(cone_gear_shaft_spec.SECTION_DIAS[-1])
    assert part.BORE_DIA_BAND == (
        pytest.approx(journal_lower + maximum),
        pytest.approx(journal_upper + minimum),
    )
    bore_upper, bore_lower = part.BORE_DIA_BAND
    assert bore_lower - journal_upper == pytest.approx(minimum)
    assert bore_upper - journal_lower == pytest.approx(maximum)


def test_enlarged_journal_leaves_a_practical_plain_bushing_wall() -> None:
    radial_wall = (spec.OUTER_DIA - spec.BORE_DIA) / 2.0
    assert radial_wall > spec.BORE_DIA
    assert spec.LENGTH > spec.BORE_DIA
    assert not hasattr(spec, "LENGTH_TOLERANCE_MM")
    assert [name for name in dir(part) if name.endswith("_BAND")] == [
        "BORE_DIA_BAND"
    ]


def test_note_identifies_the_mate_and_required_fit_without_a_duplicate_size() -> None:
    text = spec.DRAWING_NOTES
    assert len(text.splitlines()) == 1
    assert len(text) <= 90
    assert "SLIP-FITS" in text
    assert spec.SHAFT_MATE_NUMBER in text
    assert spec.SHAFT_MATE_NUMBER == _config.parts("cone-gear-shaft")["number"]
    stripped = text.replace(spec.SHAFT_MATE_NUMBER, "")
    assert not any(character.isdigit() for character in stripped)
    for method_or_duplicate in (
        "BELL-MOUTH",
        "ONE SETUP",
        "DRILL",
        "REAM",
        "1/16",
        "1.588",
    ):
        assert method_or_duplicate not in text


def test_no_gdt_and_only_the_running_bore_has_a_surface_finish() -> None:
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(spec, "PART_DATUMS")
    assert [control.key for control in spec.SURFACE_FINISHES] == ["bushing_bore"]
    assert spec.SURFACE_FINISHES[0].face.diameter_mm == spec.BORE_DIA


def test_sheet_scale_and_layout_keep_every_annotation_clear() -> None:
    assert drawing.SHEET_SCALE == (8.0, 1.0)
    assert drawing.VIEW_SCALE == (8, 1)
    outer_radius = spec.OUTER_DIA * 8 / 2000.0
    half_length = spec.LENGTH * 8 / 2000.0
    assert drawing.OUTER_R == pytest.approx(outer_radius)
    for name, (x, _y) in drawing.END_KEEP.items():
        assert abs(x - drawing.END_CENTER[0]) > outer_radius + 0.004, name
    for name, (x, _y) in drawing.SIDE_KEEP.items():
        assert x > drawing.SIDE_CENTER[0] + outer_radius + 0.004, name
    for x, y in (
        *drawing.END_KEEP.values(),
        *drawing.SIDE_KEEP.values(),
        drawing.MANUFACTURING_NOTES_POS,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070)
    assert drawing.END_CENTER[0] + outer_radius < drawing.SIDE_CENTER[0] - outer_radius
    assert drawing.SIDE_CENTER[0] + outer_radius < drawing.ISO_CENTER[0] - half_length


def test_part_registry_values_remain_the_title_block_source() -> None:
    config = _config.parts("cone-tip-bushing")
    assert config["number"] == "MHA-096"
    assert config["material_specification"] == "C36000 free-machining brass"
    assert int(config["quantity"]) == 1
