"""Offline contracts for the crank-drive-gear drawing (batch gear pattern)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_crank_drive_gear as part
import crank_drive_gear_spec as spec
import crank_pinion_spec as pinion_spec
import draw_crank_drive_gear as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-drive-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-drive-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-drive-gear_drawing.png")
    assert DRAWINGS_BY_NAME["crank_drive_gear"].script == Path(drawing.__file__).resolve()


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
        "WHOLE DEPTH (mm)", "FACE WIDTH (mm)", "TOOTH FORM", "HELIX ANGLE",
        "HELIX TWIST", "ROOT DIAMETER (mm)", "NORMAL BASE-TANGENT SPAN",
        "TRANSVERSE TOOTH THINNING FROM STANDARD", "NORMAL MODULE",
        "NORMAL PRESSURE ANGLE", "TOOTH-FLANK ACCURACY", "PAIR GEOMETRY",
        "PAIR SHAFT ANGLE", "MID-FACE TRANSVERSE C2C", "FACE MIDPLANE OFFSET",
        "BASE CIRCLE DIAMETER", "PROFILE SHIFT COEFFICIENT",
        "ACTIVE FLANK DEFINITION", "PROFILE / LEAD MODIFICATION",
    ):
        assert field in data, field
    assert "64" in data
    assert spec.HELIX_ANGLE_DEG == pytest.approx(part.HELIX_DEG, abs=0.01)
    assert spec.TOTAL_TWIST_DEG == pytest.approx(4.16, abs=0.01)
    assert spec.ROOT_DIA == pytest.approx(
        (part.TEETH / part.DP - 2.0 * 1.157 / part.DP) * spec.MM_PER_IN
    )
    circular_thickness = math.pi * spec.MODULE_MM / 2.0 - part.BACKLASH_MM
    assert spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS == pytest.approx(circular_thickness)
    assert spec.DIAMETRAL_PITCH == pytest.approx(part.DP)
    assert spec.PRESSURE_ANGLE_DEG == pytest.approx(part.PA_DEG)
    assert spec.BASE_DIA == pytest.approx(
        spec.PITCH_DIA * math.cos(math.radians(spec.PRESSURE_ANGLE_DEG))
    )
    assert spec.BACKLASH_MM == pytest.approx(part.BACKLASH_MM)
    assert (
        spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS
        + pinion_spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS
    ) == pytest.approx(math.pi * spec.MODULE_MM - spec.BACKLASH_MM)
    assert f"{spec.NORMAL_BASE_TANGENT_SPAN:.3f} +0.000/-0.020" in data
    assert f"{part.BACKLASH_MM:.3f}" in data
    assert f"+{spec.HELIX_ANGLE_DEG:.2f} +/-0.10 DEG" in data
    assert "ISO 1328-1:2013 GRADE 10" in data
    assert "NONCONJUGATE" in data
    assert "ANALYTIC INVOLUTE, BASE CIRCLE TO OD" in data
    assert "NONE; THICKNESS PER CONTROLLED SPAN" in data
    assert "EVERY 6 TEETH" in data
    assert "PROFILE/LEAD/PITCH, EVERY ACTIVE FLANK" in data
    assert "X.XX" not in data
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'adapter, "Gear Data"' in source
    assert 'adapter, "Manufacturing Notes", 0.018, 0.130' in source


def test_gear_data_block_is_inset_from_the_zone_border() -> None:
    assert drawing.GEAR_DATA_POS == (0.025, 0.262)
    assert drawing.GEAR_DATA_POS[0] < drawing.FRONT_CENTER[0]


def test_manufacturing_notes_present() -> None:
    notes = spec.DRAWING_NOTES
    assert "CUT TEETH PER GEAR DATA" in notes
    assert "POSITIVE HELIX" in notes
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
    assert "visible_circle_edge" not in source
    assert "visible_tooth_tip_silhouette" not in source
    assert source.count("edge_xy=bore_top") == 2
    assert "edge_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + HALF_OD)" in source
    assert 'label="gear tooth-tip circular runout"' in source
    assert 'entity_type="SILHOUETTE"' in source
    assert 'with _telemetry.span("drawing.auto_center_marks"):' in source
    assert "shoulder=True" in source
    assert "position_tolerance_m=0.080" in source
    assert 'quantity="2X AXIAL END FACES"' in source
    assert source.count('characteristic="perpendicularity"') == 1
    assert source.count("add_feature_control_frame(") == 2
    assert 'characteristic="circular_runout"' in source
    assert source.count("add_surface_finish(") == 1
    assert "char_height=" not in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("crank-drive-gear")
    material = "SAE 1018 CF bar, ASTM A108-24"
    assert config["material"] == material
    assert config["material_specification"] == material
    assert config["finish"] == "gear teeth cut, oiled"
    assert int(config["quantity"]) == 1
