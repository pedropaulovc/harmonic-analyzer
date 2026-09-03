"""Offline contracts for the crank-drive-gear drawing (batch gear pattern).

The print follows cad/docs/drawing-simplicity-policy.md: a gear keyed to the
cone shaft carries no datums, frames or roughness symbols; the compact GEAR
DATA block (helix angle and hand, thinned tooth, over-pins acceptance), a
cut-face-only SECTION A-A with the face width, and three lines of notes
replace the former pair-commissioning package.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _gear
import _gear_inspection
import build_crank_drive_gear as part
import crank_drive_gear_spec as spec
import crank_pinion_spec as pinion_spec
import draw_crank_drive_gear as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-drive-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-drive-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-drive-gear_drawing.png")
    assert DRAWINGS_BY_NAME["crank_drive_gear"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"BoreDia"}
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_bore_volume_formula_dependency_is_available() -> None:
    expected = math.pi * (part.BORE_DIAMETER / 2.0) ** 2 * part.FACE_WIDTH
    assert part.math.pi * (part.BORE_DIAMETER / 2.0) ** 2 * part.FACE_WIDTH == expected


def test_gear_data_block_is_the_compact_helical_tooth_system() -> None:
    data = spec.GEAR_DATA
    lines = data.split("\n")
    assert lines[0] == "GEAR DATA"
    assert len(lines) <= 13
    for field in (
        "NUMBER OF TEETH", "DIAMETRAL PITCH (TRANSVERSE)",
        "PRESSURE ANGLE (TRANSVERSE)", "HELIX ANGLE", "PITCH DIAMETER (REF)",
        "OUTSIDE DIAMETER", "WHOLE DEPTH (REF)", "FACE WIDTH",
        "TRANSVERSE TOOTH THICKNESS", "OVER 2 PINS", "TOOTH FORM", "MATES WITH",
    ):
        assert field in data, field
    assert "64" in data
    assert "DIAMETRAL PITCH (TRANSVERSE):  25.73" in data
    assert f"HELIX ANGLE:  {spec.HELIX_ANGLE_DEG:.2f} DEG RIGHT-HAND" in data
    assert f"{spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f} (THINNED 0.15)" in data
    assert "16T CRANK PINION, 12.52 DEG CROSSED AXES" in data
    assert "X.XX" not in data
    # The inspection package is gone: no ISO grade, no span, no fixture data.
    for banned in ("ISO 1328", "BASE-TANGENT", "NONCONJUGATE", "BASIC", "+/-", "MHA-"):
        assert banned not in data, banned
    source = _source()
    assert 'adapter, "Gear Data"' in source
    assert 'adapter, "Manufacturing Notes"' in source


def test_over_pins_row_is_computed_on_the_helical_thinned_tooth() -> None:
    assert spec.PIN_DIA_MM == pytest.approx(1.90)
    assert spec.PIN_DIA_MM == _gear_inspection.preferred_pin_dia_mm(spec.DIAMETRAL_PITCH)
    assert spec.OVER_PINS.usable
    assert spec.OVER_PINS.over_pins_mm == pytest.approx(66.13, abs=0.005)
    assert "OVER 2 PINS 1.90 DIA:  66.13 +0/-0.10" in spec.GEAR_DATA
    # Helix and thinning both feed the reading: a spur, standard tooth of the
    # same system reads differently.
    plain = _gear_inspection.pin_measurement(
        teeth=spec.TEETH,
        diametral_pitch=spec.DIAMETRAL_PITCH,
        pressure_angle_deg=spec.PRESSURE_ANGLE_DEG,
        pin_dia_mm=spec.PIN_DIA_MM,
    )
    assert plain.over_pins_mm != pytest.approx(spec.OVER_PINS.over_pins_mm, abs=0.01)


def test_helix_hand_is_derived_from_the_build_sweep_sign() -> None:
    # _gear sweeps the tooth with a CCW-about-+Z twist while advancing +Z: a
    # helix turning counter-clockwise as it advances is right-handed.
    assert _gear._TWIST_CCW > 0
    assert spec.HELIX_HAND == "RIGHT-HAND"
    assert "RIGHT-HAND HELIX" in spec.DRAWING_NOTES


def test_spec_tooth_math_matches_the_build() -> None:
    assert spec.HELIX_ANGLE_DEG == pytest.approx(part.HELIX_DEG, abs=0.01)
    assert spec.TOTAL_TWIST_DEG == pytest.approx(3.09, abs=0.01)
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
    assert spec.PAIR_SHAFT_ANGLE_DEG == pinion_spec.PAIR_SHAFT_ANGLE_DEG
    assert spec.FACE_WIDTH == part.FACE_WIDTH


def test_gear_data_block_is_inset_from_the_zone_border() -> None:
    assert drawing.GEAR_DATA_POS == (0.025, 0.262)
    assert drawing.GEAR_DATA_POS[0] < drawing.FRONT_CENTER[0]


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "RIGHT-HAND HELIX: ON THE END VIEW A TOOTH TURNS CCW AS IT COMES TOWARD YOU" in notes
    assert "DO NOT CHAMFER OR BLEND TOOTH FLANKS, TIPS OR ROOTS" in notes
    assert "FIXED TO THE CONE SHAFT" in notes
    # No axis letters to decode (the reviewer's clarity finding).
    assert "-Z" not in notes and "+Z" not in notes
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
    assert spec.BORE_DIA_BAND == (0.050, 0.000)
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_section_replaces_the_side_view_and_states_the_face_width() -> None:
    source = _source()
    assert "create_section_view(" in source
    assert "show_only_cut_face(adapter, section" in source
    assert 'section_label="A"' in source
    assert "RIGHT_CENTER" not in source
    assert (
        drawing.SECTION_LINE[0][0]
        == drawing.SECTION_LINE[1][0]
        == drawing.FRONT_CENTER[0]
    )
    assert drawing.SECTION_HALF_LINE > spec.OUTSIDE_DIA / 2000.0
    assert drawing.SECTION_NOTE == f"SECTION A-A\nFACE WIDTH {spec.FACE_WIDTH:.2f}"
    assert "add_note(adapter, SECTION_NOTE, *SECTION_NOTE_XY)" in source
    assert "add_edge_dimension(" not in source


def test_hidden_lines_stay_on_in_the_orthographic_view() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("crank-drive-gear")
    material = "SAE 1018 CF bar, ASTM A108-24"
    assert config["material"] == material
    assert config["material_specification"] == material
    assert config["finish"] == "bright, oiled"
    assert int(config["quantity"]) == 1
