"""Offline contracts for the alignment-pinion drawing (batch gear pattern).

The print follows cad/docs/drawing-simplicity-policy.md: a drum pressed onto
its arbor carries no datums, frames or roughness symbols; the GEAR DATA block
and two lines of notes are the whole specification beyond the bore.
"""

from __future__ import annotations

from pathlib import Path

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
    assert set(drawing.FRONT_KEEP) == marked == {"ArborBoreDia"}
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_gear_data_block_is_the_compact_tooth_system() -> None:
    data = spec.GEAR_DATA
    lines = data.split("\n")
    assert lines[0] == "GEAR DATA"
    assert len(lines) <= 9
    for field in (
        "NUMBER OF TEETH", "DIAMETRAL PITCH", "PRESSURE ANGLE",
        "PITCH DIAMETER (REF)", "OUTSIDE DIAMETER", "WHOLE DEPTH",
        "FACE WIDTH", "TOOTH FORM",
    ):
        assert field in data, field
    assert "42" in data
    assert "143.2" in data  # the only place the drum length is stated
    assert "X.XX" not in data
    assert "MODULE" not in data
    source = _source()
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "FULL LENGTH OF THE DRUM" in notes
    assert "LIGHT PRESS" in notes
    assert "FINISH TO FIT" in notes
    for banned in ("DATUM", "RUNOUT", "+/-", "MHA-", "DEBUR", "X.XX", "UOS"):
        assert banned not in notes, banned


def test_press_bore_states_the_process_and_keeps_its_band_on_the_model() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"ArborBoreDia": "REAM THRU\nPRESS ON ARBOR"}
    assert drawing.DIMENSION_PRECISION == {"ArborBoreDia": 2}
    assert spec.ARBOR_BORE_BAND == (-0.020, -0.040)
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "set_dimension_bilateral_tolerance(" in build_source
    assert "deviations(ARBOR_BORE_BAND)" in build_source


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


def test_hidden_lines_stay_on_in_both_orthographic_views() -> None:
    # Two views, no isometric: nothing on this sheet removes hidden lines.
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
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
