"""Offline contracts for the pinion-swing-bracket drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_bracket_spec
import draw_pinion_bracket as drawing
import build_pinion_bracket as bracket
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-bracket_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_bracket"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert bracket.DRAWING_DIMENSIONS is pinion_bracket_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_bracket_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.C2C, drawing.OVERALL_LENGTH, drawing.R_END) == (
        pinion_bracket_spec.C2C,
        pinion_bracket_spec.OVERALL_LENGTH,
        pinion_bracket_spec.R_END,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert (
        pinion_bracket_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    )
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_use_us_customary_fasteners_and_functional_tolerances() -> None:
    notes = pinion_bracket_spec.DRAWING_NOTES
    assert "REAM THRU" in notes
    assert "PRESS FIT" in notes
    assert "1/4 IN" in drawing.DIMENSION_CALLOUTS["PivotBoreDia"]
    # The arbor bore is metric Ø8 -- no fractional-inch reamer matches, so it is
    # a plain metric ream (NOT a wrong 5/16 in reamer, which is 7.94 undersize).
    assert "5/16" not in drawing.DIMENSION_CALLOUTS["ArborBoreDia"]
    assert "REAM THRU" in drawing.DIMENSION_CALLOUTS["ArborBoreDia"]
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["PivotBoreDia"].startswith("THRU")
    assert "THRU" in callouts["ArborBoreDia"]
    assert "DEEP" in callouts["PinSeatDia"]


def test_native_gdt_replaces_form_orientation_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 2
    assert 'characteristic="parallelism"' in source
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert "set_basic_dimension(" in source  # the bore centre distance


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(bracket.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-bracket")
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 2  # the book uses two swing brackets
