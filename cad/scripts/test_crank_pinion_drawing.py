"""Offline contracts for the crank-pinion drawing (batch gear pattern)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_crank_pinion as part
import crank_pinion_spec as spec
import draw_crank_pinion as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["crank_pinion"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"BoreDia"}
    assert drawing.DIMENSION_PRECISION["BoreDia"] == 3
    assert "+0.050/+0.030" in drawing.DIMENSION_CALLOUTS["BoreDia"]


def test_gear_data_block_specifies_the_tooth_system() -> None:
    data = spec.GEAR_DATA
    for field in (
        "GEAR DATA", "NUMBER OF TEETH", "DIAMETRAL PITCH", "MODULE (mm",
        "TRANSVERSE PRESSURE ANGLE", "PITCH DIAMETER (mm", "OUTSIDE DIAMETER (mm)",
        "WHOLE DEPTH (mm)", "FACE WIDTH (mm)", "TOOTH FORM",
        "ROOT DIAMETER (mm)", "BASE-TANGENT SPAN", "TOOTH-FLANK ACCURACY",
        "PAIR GEOMETRY", "PAIR SHAFT ANGLE", "MID-FACE TRANSVERSE C2C",
        "FACE MIDPLANE OFFSET",
        "BASE CIRCLE DIAMETER", "PROFILE SHIFT COEFFICIENT",
        "ACTIVE FLANK DEFINITION", "PROFILE / LEAD MODIFICATION",
    ):
        assert field in data, field
    assert "16" in data
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
    assert f"{spec.BASE_TANGENT_SPAN:.3f} +0.000/-0.020" in data
    assert "ISO 1328-1:2013 GRADE 10" in data
    assert "NONCONJUGATE" in data
    assert "ANALYTIC INVOLUTE, BASE CIRCLE TO OD" in data
    assert "NONE; THICKNESS PER CONTROLLED SPAN" in data
    assert "EVERY 2 TEETH" in data
    assert "PROFILE/LEAD/PITCH, EVERY ACTIVE FLANK" in data
    assert "X.XX" not in data
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'adapter, "Gear Data"' in source
    assert 'adapter, "Manufacturing Notes"' in source


def test_manufacturing_notes_present() -> None:
    notes = spec.DRAWING_NOTES
    assert "CUT TEETH PER GEAR DATA" in notes
    assert "ROOT DIAMETER" in notes
    assert "DO NOT SUBSTITUTE" in notes
    assert "PART ACCEPTANCE IS BY INDIVIDUAL DRAWING LIMITS" in notes
    assert "PAIR ASSEMBLY COMMISSIONING - NOT INDIVIDUAL PART ACCEPTANCE" in notes
    assert "LOCATE BOTH BORES ON EXPANDING ARBORS" in notes
    assert "APPLY 2.0 +/-0.2 mL ISO VG 32 OIL AT 20 +/-5 C" in notes
    assert "DRIVE 16T PINION AT 6 +/-1 RPM IN BOTH DIRECTIONS" in notes
    assert "64T OUTPUT UNLOADED" in notes
    assert "SAMPLE RAW INLINE TORQUE AT 10 Hz MIN" in notes
    assert "MEASURE ENGAGED 16T INPUT TORQUE OVER ONE FULL 64T REVOLUTION" in notes
    assert "INPUT TARE AT 6 RPM AND OUTPUT TARE AT 1.5 RPM" in notes
    assert "CORRECTED INPUT = ENGAGED INPUT - INPUT TARE - OUTPUT TARE/4" in notes
    assert "CORRECTED MAGNITUDE 0.10 N*m MAX" in notes
    assert "PEAK-TO-PEAK 0.05 N*m MAX" in notes
    assert "MATCH-MARK" not in notes
    assert "R0.10 MAX" in notes
    assert "TOOTH FLANKS, TIPS, AND ROOTS: DO NOT CHAMFER OR BLEND" in notes
    assert "HARDNESS NOT CONTROLLED" in notes
    assert "DESIGN DIAMETRAL CLEARANCE: 0.030-0.070" in notes
    assert "DEBUR" not in notes
    assert "X.XX" not in notes


def test_native_gdt_controls_bore_datum_and_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert "entity=bore_edge" in source
    assert "shoulder=True" in source
    assert "position_tolerance_m=0.080" in source
    assert 'quantity="2X AXIAL END FACES"' in source
    assert source.count('characteristic="perpendicularity"') == 1
    assert source.count("add_feature_control_frame(") == 2
    assert 'characteristic="circular_runout"' in source
    assert source.count("add_surface_finish(") == 1
    assert source.count("char_height=0.0025") == 2


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("crank-pinion")
    material = "SAE 1018 CF bar, ASTM A108-24"
    assert config["material"] == material
    assert config["material_specification"] == material
    assert config["finish"] == "gear teeth cut, oiled"
    assert int(config["quantity"]) == 1
