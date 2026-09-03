"""Offline contracts for the crank-pinion drawing (batch gear pattern).

The print follows cad/docs/drawing-simplicity-policy.md: a pinion keyed to the
crankshaft carries no datums, frames or roughness symbols; the compact GEAR
DATA block and two lines of notes replace the former pair-commissioning
package.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_crank_pinion as part
import crank_pinion_spec as spec
import draw_crank_pinion as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["crank_pinion"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"BoreDia"}
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_gear_data_block_is_the_compact_tooth_system() -> None:
    data = spec.GEAR_DATA
    lines = data.split("\n")
    assert lines[0] == "GEAR DATA"
    assert len(lines) <= 11
    for field in (
        "NUMBER OF TEETH", "DIAMETRAL PITCH", "PRESSURE ANGLE",
        "PITCH DIAMETER (REF)", "OUTSIDE DIAMETER", "WHOLE DEPTH",
        "FACE WIDTH", "CIRCULAR TOOTH THICKNESS", "TOOTH FORM", "MATES WITH",
    ):
        assert field in data, field
    assert "16" in data
    assert "SPUR INVOLUTE, FULL DEPTH" in data
    assert "64T HELICAL CRANK-DRIVE GEAR, 12.52 DEG CROSSED AXES" in data
    assert "X.XX" not in data
    for banned in ("ISO 1328", "BASE-TANGENT", "NONCONJUGATE", "BASIC", "+/-", "MHA-"):
        assert banned not in data, banned
    source = _source()
    assert 'adapter, "Gear Data"' in source
    assert 'adapter, "Manufacturing Notes"' in source


def test_spec_tooth_math_matches_the_build() -> None:
    assert spec.ROOT_DIA == pytest.approx((
        part.TEETH / part.DP - 2.0 * 1.157 / part.DP
    ) * spec.MM_PER_IN)
    circular_thickness = math.pi * spec.MODULE_MM / 2.0
    assert spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS == pytest.approx(circular_thickness)
    assert spec.DIAMETRAL_PITCH == pytest.approx(part.DP)
    assert spec.PRESSURE_ANGLE_DEG == pytest.approx(part.PA_DEG)
    assert spec.BASE_DIA == pytest.approx(
        spec.PITCH_DIA * math.cos(math.radians(spec.PRESSURE_ANGLE_DEG))
    )


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "DO NOT CHAMFER OR BLEND TOOTH FLANKS, TIPS OR ROOTS" in notes
    assert "FIXED TO THE CRANKSHAFT" in notes
    for banned in (
        "DATUM", "RUNOUT", "+/-", "MHA-", "DEBUR", "X.XX", "UOS",
        "COMMISSIONING", "TORQUE", "ISO", "HEAT TREATMENT", "HARDNESS",
        "CLEARANCE",
    ):
        assert banned not in notes, banned


def test_print_carries_no_gdt_or_finish_symbols() -> None:
    # drawing-simplicity-policy.md rules 3-5: gears are not on the GD&T
    # allowlist and a keyed bore does not run.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "visible_circle_edge(",
        "visible_tooth_tip_silhouette(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert spec.SURFACE_FINISHES == ()
    assert "surface_finishes=SURFACE_FINISHES" in Path(part.__file__).read_text(
        encoding="utf-8"
    )


def test_reamed_bore_keeps_its_band_on_the_model_and_three_decimals() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU"}
    assert drawing.DIMENSION_PRECISION == {"BoreDia": 3}
    assert spec.BORE_DIA_BAND == (0.050, 0.030)
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("crank-pinion")
    material = "SAE 1018 CF bar, ASTM A108-24"
    assert config["material"] == material
    assert config["material_specification"] == material
    assert config["finish"] == "bright, oiled"
    assert int(config["quantity"]) == 1
