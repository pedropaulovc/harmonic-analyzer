"""Offline contracts for the cylinder-gear drawing (batch gear-drawing pattern).

The print follows cad/docs/drawing-simplicity-policy.md: no datums or frames;
roughness symbols only on the bore (RUNS on the cylinder-gear shaft) and the
cam O.D. (the follower track); a compact GEAR DATA block with the over-pins
acceptance; the cam dimensioned in the front view, the kerf in DETAIL B, the
axial stack in a cut-face-only SECTION A-A; three lines of notes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import _gear_inspection
import build_cylinder_gear as part
import cylinder_gear_spec as spec
import draw_cylinder_gear as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cylinder-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cylinder-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cylinder-gear_drawing.png")
    assert DRAWINGS_BY_NAME["cylinder_gear"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"BoreDia", "CamDia", "CamOffset"}
    assert not hasattr(drawing, "DETAIL_KEEP")
    assert set(drawing.DIMENSION_CALLOUTS) <= set(drawing.FRONT_KEEP)


def test_cam_dimensions_are_named_by_value_in_the_build() -> None:
    # The cam circle sits on an offset plane where the x=0 anchor still emits
    # a dim, so the build names CamDia / CamOffset by matching values.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "_name_cam_dimensions(adapter)" in source
    assert 'names.append("CamDia")' in source
    assert 'names.append("CamOffset")' in source
    assert part.CAM_DIAMETER == spec.CAM_DIA
    assert part.ECCENTRICITY == spec.ECCENTRICITY
    assert part.CAM_THICKNESS == spec.CAM_THICKNESS
    assert part.FACE_WIDTH == spec.FACE_WIDTH


def test_kerf_geometry_matches_the_build() -> None:
    assert part.NOTCH_WIDTH == spec.NOTCH_WIDTH
    assert part.NOTCH_DEPTH == spec.NOTCH_DEPTH
    assert part.NOTCH_FLOOR == pytest.approx(spec.NOTCH_FLOOR_MM)
    assert part.NOTCH_X == pytest.approx(spec.NOTCH_X_MM)
    # The detail circle clears the A-A cut line (x = 0) and still holds the kerf.
    x_min = drawing.DETAIL_MODEL_CENTER_MM[0] - drawing.DETAIL_RADIUS * 1000.0
    x_max = drawing.DETAIL_MODEL_CENTER_MM[0] + drawing.DETAIL_RADIUS * 1000.0
    assert x_max < 0.0
    assert x_min < spec.NOTCH_X_MM - spec.NOTCH_WIDTH / 2.0
    assert x_max > spec.NOTCH_X_MM + spec.NOTCH_WIDTH / 2.0
    assert drawing.DETAIL_SCALE == (4, 1)


def test_gear_data_block_is_the_compact_tooth_system_with_over_pins() -> None:
    data = spec.GEAR_DATA
    lines = data.split("\n")
    assert lines[0] == "GEAR DATA"
    assert len(lines) <= 10
    for field in (
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (REF)",
        "OUTSIDE DIAMETER",
        "WHOLE DEPTH (REF)",
        "FACE WIDTH",
        "OVER 2 PINS",
        "TOOTH FORM",
        "INVOLUTE, FULL DEPTH",
    ):
        assert field in data, field
    assert "120" in data
    assert "DIAMETRAL PITCH:  49.82" in data
    assert "X.XX" not in data
    assert "MODULE" not in data
    # 20 gears stack on one drum: the face width keeps its band in the blank
    # row because it is not a view dimension.
    assert "FACE WIDTH:  3.00 +/-0.05" in data
    # The over-pins row is computed, never typed: 120T, DP 49.82, 14.5 deg,
    # the 1.00 pin -> 63.00 over two pins, minus-only band.
    assert spec.PIN_DIA_MM == pytest.approx(1.00)
    assert spec.OVER_PINS.over_pins_mm == pytest.approx(63.00, abs=0.005)
    assert "OVER 2 PINS 1.00 DIA:  63.00 +0/-0.10" in data
    assert spec.OVER_PINS.usable
    assert spec.PIN_DIA_MM == _gear_inspection.preferred_pin_dia_mm(
        spec.DIAMETRAL_PITCH
    )
    source = _source()
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_gear_data_block_is_inset_from_the_zone_border() -> None:
    assert drawing.GEAR_DATA_POS == (0.040, 0.262)
    assert drawing.GEAR_DATA_POS[0] < drawing.FRONT_CENTER[0]


def test_notes_carry_only_the_set_station_and_running_facts() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert max(len(line) for line in lines) <= 90
    assert "SET OF 20: CAM OFFSETS WITHIN 0.025" in notes
    assert "DETAIL B" in notes
    assert "RUNS FREE ON THE CYLINDER-GEAR SHAFT" in notes
    # The cam size/offset, the kerf size and the cam finish moved to the views.
    for banned in (
        "FAR FACE",
        "<MOD-DIAM>",
        "Ra 1.6",
        "SAW KERF",
        "THK",
        "DATUM",
        "RUNOUT",
        "+/-",
        "BASIC",
        "MHA-",
        "DEBUR",
        "X.XX",
        "UOS",
    ):
        assert banned not in notes, banned


def test_running_bore_and_cam_track_carry_the_two_finish_symbols() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU"}
    assert drawing.DIMENSION_PRECISION == {"BoreDia": 3, "CamOffset": 3, "CamDia": 2}
    assert not hasattr(drawing, "DETAIL_PRECISION")
    assert spec.BORE_DIA_BAND == (0.05, 0.00)
    assert spec.NOTCH_WIDTH_TOLERANCE_MM == 0.05
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
    }
    bore, cam = spec.SURFACE_FINISHES
    assert bore.key == "cylinder_gear_bore"
    assert bore.roughness_um == 1.6
    assert bore.face.diameter_mm == spec.BORE_DIA
    assert cam.key == "cam_track"
    assert cam.roughness_um == 1.6
    assert cam.face.diameter_mm == spec.CAM_DIA
    source = _source()
    assert source.count("add_surface_finish(") == 2
    assert "bore_edge = visible_circle_edge(" in source
    assert "cam_edge = visible_circle_edge(" in source
    assert source.count("entity=bore_edge") == 1
    assert source.count("entity=cam_edge") == 1
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES, "cylinder_gear_bore")'
        in source
    )
    assert 'control=surface_finish_by_key(SURFACE_FINISHES, "cam_track")' in source


def test_finish_symbols_have_a_dedicated_column_outside_the_gear() -> None:
    cx, cy = drawing.FRONT_CENTER
    bore_text = drawing.FRONT_KEEP["BoreDia"]
    assert bore_text[0] < cx and bore_text[1] > cy  # upper-left
    bore_ra = drawing.BORE_FINISH_SYMBOL
    cam_ra = drawing.CAM_FINISH_SYMBOL
    gear_left = cx - spec.OUTSIDE_DIA / 2000.0
    assert bore_ra[0] < gear_left - 0.025
    assert cam_ra[0] < gear_left - 0.025
    assert bore_ra[1] < cy < cam_ra[1]
    assert cam_ra[1] - bore_ra[1] >= 0.050
    for name in ("CamDia", "CamOffset"):
        assert drawing.FRONT_KEEP[name][0] > cx  # right
    # Symbols and dimensions stay clear of the A-A cut line at x = cx.
    for x, _y in (*drawing.FRONT_KEEP.values(), bore_ra, cam_ra):
        assert abs(x - cx) >= 0.030


def test_section_shows_only_the_cut_face_and_carries_the_cam_thickness() -> None:
    source = _source()
    assert "create_section_view(" in source
    assert "show_only_cut_face(adapter, section" in source
    assert 'section_label="A"' in source
    assert drawing.SECTION_SCALE == (1, 2)
    assert "scale=SECTION_SCALE" in source
    assert (
        drawing.SECTION_LINE[0][0]
        == drawing.SECTION_LINE[1][0]
        == drawing.FRONT_CENTER[0]
    )
    assert drawing.SECTION_HALF_LINE > spec.OUTSIDE_DIA / 2000.0
    assert drawing.CAM_THICKNESS_NOTE == f"CAM THICKNESS {spec.CAM_THICKNESS:.2f}"
    assert "add_note(adapter, CAM_THICKNESS_NOTE, *CAM_THICKNESS_NOTE_XY)" in source
    assert "CAM_THICKNESS_PICKS" not in source
    assert "add_edge_dimension(" not in source
    helper = Path(__import__("_gear_drawing_entities").__file__).read_text(
        encoding="utf-8"
    )
    assert "SetDisplayOnlySurfaceCut(True)" in helper
    assert "GetDisplayOnlySurfaceCut()" in helper


def test_kerf_detail_uses_one_complete_plain_saw_note() -> None:
    source = _source()
    assert "add_attached_note(" not in source
    assert "add_note(adapter, KERF_DISPLAY_NOTE, *KERF_NOTE_XY)" in source
    assert not hasattr(drawing, "DETAIL_KEEP")
    assert 'view_label="detail"' not in source
    assert spec.KERF_CALLOUT == (
        "SAW KERF 0.40 +/-0.05 WIDE, 3.0 DEEP FROM O.D., FULL FACE"
    )
    assert (
        drawing.KERF_DISPLAY_NOTE.replace("\n", ", ").replace(";", ",")
        == spec.KERF_CALLOUT
    )
    assert f"{spec.NOTCH_WIDTH:.2f} +/-{spec.NOTCH_WIDTH_TOLERANCE_MM:.2f}" in (
        spec.KERF_CALLOUT
    )
    assert f"{spec.NOTCH_DEPTH:.1f} DEEP" in spec.KERF_CALLOUT


def test_print_carries_no_gdt() -> None:
    # drawing-simplicity-policy.md rule 3: gears are not on the GD&T allowlist.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "_largest_visible_planar_face",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")


def test_hidden_lines_stay_on_in_the_orthographic_view() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1
    assert "RIGHT_CENTER" not in source  # the projected side view is gone


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cylinder-gear")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "polished brass"
    assert int(config["quantity"]) == 20
