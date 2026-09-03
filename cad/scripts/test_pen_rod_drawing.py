"""Offline contracts for the pen-rod drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a length of drawn
square bar carries no datums or frames; its slide fit is the band on the model
section, plus one Ra on the face that slides in the v-block, and the wire hole
says DRILL on its callout.
"""

from __future__ import annotations

from pathlib import Path

import build_pen_rod as part
import draw_pen_rod as drawing
import pen_rod_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import NUMBER_DRILL_MM


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-rod_drawing.png")
    assert DRAWINGS_BY_NAME["pen_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pen_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert (part.ROD_SECTION, part.ROD_LENGTH, part.WIRE_HOLE_Y) == (
        pen_rod_spec.ROD_SECTION,
        pen_rod_spec.ROD_LENGTH,
        pen_rod_spec.WIRE_HOLE_Y,
    )


def test_wire_hole_callout_states_size_and_process() -> None:
    assert pen_rod_spec.WIRE_HOLE_DIA == NUMBER_DRILL_MM[pen_rod_spec.WIRE_HOLE_DRILL]
    assert pen_rod_spec.WIRE_HOLE_DRILL == "#47"
    assert pen_rod_spec.WIRE_HOLE_Y < pen_rod_spec.ROD_LENGTH
    source = _source()
    assert source.count("add_native_hole_callout(") == 1
    # Harvey #13: the callout says DRILL; the drill number rides as its prefix.
    assert 'process="#47 DRILL"' in source
    # Two located dims for the wire hole: along the rod (length) AND across the
    # section (centerline), so the cross-hole cannot drift off-centre.
    assert source.count("add_edge_dimension(") == 2


def test_slide_fit_rides_the_model_section() -> None:
    assert drawing.DIMENSION_CALLOUTS == {}
    assert drawing.TOP_DIMENSION_CALLOUTS == {}
    assert pen_rod_spec.SECTION_BAND == (0.00, -0.05)
    assert model_toleranced_dimensions(part) == {
        ("RodProfile", "Section"): "*deviations(SECTION_BAND)",
        ("Rod", "Depth"): "*deviations(SECTION_BAND)",
    }


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pen_rod_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "OK AS RECEIVED" in notes  # the cleanup-cut licence (Lipton)
    # The drill rides the hole callout; deburr is a title-block row; the
    # v-block role is design intent.
    for banned in ("DRILL", "#47", "DEBURR", "V-BLOCK", "WITHIN", "+/-", "UOS", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_and_one_sliding_finish() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert pen_rod_spec.PART_DATUMS == ()
    assert pen_rod_spec.GEOMETRIC_CONTROLS == ()
    assert not hasattr(pen_rod_spec, "GEOMETRIC_TOLERANCES_MM")
    # The -X face slides in the v-block, so it alone carries a roughness symbol.
    (control,) = pen_rod_spec.SURFACE_FINISHES
    assert control.key == "slide_face"
    assert control.roughness_um == 1.6
    assert control.face.normal == (-1, 0, 0)
    assert control.face.offset_mm == pen_rod_spec.ROD_SECTION / 2.0
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "slide_face")' in source
    assert "roughness_ra=" not in source
    # The part build keeps its author_part_pmi call shape on the empty tuples.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(" in part_source
    assert "datums=PART_DATUMS" in part_source
    assert "controls=GEOMETRIC_CONTROLS" in part_source
    assert "surface_finishes=SURFACE_FINISHES" in part_source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    assert source.count("scale=(1, 1)") == 3
    assert source.count("scale=(4, 1)") == 1
    assert pen_rod_spec.TOP_VIEW_NOTE == "TOP VIEW SCALE 4:1"
    assert 'add_property_linked_note(adapter, "Top View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pen-rod")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
