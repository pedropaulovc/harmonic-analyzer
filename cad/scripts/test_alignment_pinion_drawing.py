"""Offline contracts for the alignment-pinion drawing (batch gear pattern).

The print follows cad/docs/drawing-simplicity-policy.md: a drum pressed onto
its arbor carries no datums, frames or roughness symbols; the GEAR DATA block
(with the over-pins acceptance), the bore callout in DETAIL B (3:1), the face
length on a cut-face-only SECTION A-A and one line of notes are the whole
specification.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import _gear_inspection
import alignment_pinion_spec as spec
import build_alignment_pinion as part
import draw_alignment_pinion as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/alignment-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/alignment-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/alignment-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["alignment_pinion"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.DETAIL_KEEP) == marked == {"ArborBoreDia"}


def test_gear_data_block_is_the_compact_tooth_system_with_over_pins() -> None:
    data = spec.GEAR_DATA
    lines = data.split("\n")
    assert lines[0] == "GEAR DATA"
    assert len(lines) <= 10
    for field in (
        "NUMBER OF TEETH", "DIAMETRAL PITCH", "PRESSURE ANGLE",
        "PITCH DIAMETER (REF)", "OUTSIDE DIAMETER", "WHOLE DEPTH (REF)",
        "FACE WIDTH", "OVER 2 PINS", "TOOTH FORM",
    ):
        assert field in data, field
    assert "42" in data
    assert "143.2" in data
    assert "DIAMETRAL PITCH:  49.82" in data
    assert "X.XX" not in data
    assert "MODULE" not in data
    # 42T, DP 49.82, 14.5 deg, the 1.00 pin -> 23.15 over two pins.
    assert spec.PIN_DIA_MM == pytest.approx(1.00)
    assert spec.PIN_DIA_MM == _gear_inspection.preferred_pin_dia_mm(spec.DIAMETRAL_PITCH)
    assert spec.OVER_PINS.usable
    assert "OVER 2 PINS 1.00 DIA:  23.15 +0/-0.10" in data
    source = _source()
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "MATES WITH THE 20 CYLINDER GEARS" in notes
    # The full-length-teeth line (the views show it) and the second fit
    # wording (now at the bore leader) are gone.
    assert "FULL LENGTH" not in notes
    assert "FINISH TO FIT" not in notes
    for banned in ("DATUM", "RUNOUT", "+/-", "MHA-", "DEBUR", "X.XX", "UOS"):
        assert banned not in notes, banned


def test_press_bore_states_the_whole_fit_at_the_leader_in_the_detail() -> None:
    assert drawing.DIMENSION_CALLOUTS == {
        "ArborBoreDia": "REAM THRU\nLIGHT PRESS ON ARBOR, FINISH TO FIT"
    }
    assert drawing.DIMENSION_PRECISION == {"ArborBoreDia": 3}
    assert spec.ARBOR_BORE_BAND == (-0.020, -0.040)
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "set_dimension_bilateral_tolerance(" in build_source
    assert "deviations(ARBOR_BORE_BAND)" in build_source
    source = _source()
    # Only the detail is curated (it claims the bore); the end view is never
    # asked for model items, matching the pinion_arbor precedent.
    assert source.count("curate_view_dimensions(") == 1
    assert 'view_label="detail"' in source
    assert 'view_label="front"' not in source
    assert "set_dimension_callouts(adapter, detail_annotations" in source
    assert drawing.DETAIL_SCALE == (3, 1)
    assert drawing.DETAIL_RADIUS > spec.OUTSIDE_DIA / 2000.0
    # The callout text sits outside the enlarged detail circle.
    text = drawing.DETAIL_KEEP["ArborBoreDia"]
    dx = text[0] - drawing.DETAIL_CENTER[0]
    dy = text[1] - drawing.DETAIL_CENTER[1]
    assert (dx * dx + dy * dy) ** 0.5 > drawing.DETAIL_RADIUS * drawing.DETAIL_SCALE[0]


def test_print_carries_no_gdt_or_finish_symbols() -> None:
    # drawing-simplicity-policy.md rules 3-5: gears are not on the GD&T
    # allowlist and a pressed bore does not run.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "visible_circle_edge(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert spec.SURFACE_FINISHES == ()
    assert "surface_finishes=SURFACE_FINISHES" in Path(part.__file__).read_text(
        encoding="utf-8"
    )


def test_section_replaces_the_drum_profile_and_states_the_face_length() -> None:
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
    assert drawing.SECTION_NOTE == f"SECTION A-A\nFACE LENGTH {spec.FACE_WIDTH:.1f}"
    assert "add_note(adapter, SECTION_NOTE, *SECTION_NOTE_XY)" in source
    assert "add_edge_dimension(" not in source
    # The 143 mm section fits between the end view and the right zone border.
    half_len = spec.FACE_WIDTH / 2000.0
    assert (
        drawing.SECTION_CENTER[0] - half_len
        > drawing.FRONT_CENTER[0] + spec.OUTSIDE_DIA / 2000.0
    )
    assert drawing.SECTION_CENTER[0] + half_len < 0.41
    # The detail sits under the section, clear of it.
    assert (
        drawing.DETAIL_CENTER[1] + drawing.DETAIL_RADIUS * 3
        < drawing.SECTION_CENTER[1] - spec.OUTSIDE_DIA / 2000.0
    )


def test_hidden_lines_stay_on_in_the_end_view() -> None:
    # One orthographic view (the end view), no isometric: nothing on this
    # sheet removes hidden lines.
    source = _source()
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "set_hidden_lines_removed" not in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "clear_dimensions_for_drawing(adapter)" in source
    assert "mark_dimensions_for_drawing(adapter, feature_name, dimension_names)" in source
    assert '"Gear Data": GEAR_DATA' in source
    assert '"Manufacturing Notes": DRAWING_NOTES' in source
    import _config

    config = _config.parts("alignment-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "polished brass"
    assert int(config["quantity"]) == 1
