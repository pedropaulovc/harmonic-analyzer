"""Offline contracts for the pen-v-block drawing."""

from __future__ import annotations

from pathlib import Path
from _drawing_test_support import linked_note_properties

import build_pen_v_block as part
import draw_pen_v_block as drawing
import pen_v_block_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_spec import CylinderFace


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-v-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-v-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-v-block_drawing.png")
    assert DRAWINGS_BY_NAME["pen_v_block"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert part.DRAWING_DIMENSIONS is pen_v_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_v_block_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    )
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.BLOCK_LENGTH, drawing.BLOCK_HEIGHT, drawing.BLOCK_DEPTH) == (
        pen_v_block_spec.BLOCK_LENGTH,
        pen_v_block_spec.BLOCK_HEIGHT,
        pen_v_block_spec.BLOCK_DEPTH,
    )
    assert (drawing.BORE_X, drawing.GROOVE_WIDTH) == (
        pen_v_block_spec.BORE_X,
        pen_v_block_spec.GROOVE_WIDTH,
    )
    # Screw location is imported from the marked native dimensions. The recipe
    # no longer computes sheet coordinates from a second screw-location alias.
    assert {"ScrewHoleCx", "ScrewHoleCz", "ScrewHoleDiaDim"} <= set(drawing.FRONT_KEEP)


def test_sheet_runs_at_3_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(3, 1)") == 3
    assert source.count("scale=(2, 1)") == 1  # the isometric override
    assert pen_v_block_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert "Isometric View Note" in linked_note_properties(source)


def test_linked_notes_cover_the_marker_groove_and_functional_tolerances() -> None:
    notes = pen_v_block_spec.DRAWING_NOTES
    # The make-or-scrap instructions: the marker groove runs the FULL length
    # (the barrel passes right through, v4_t00612) and the block ships bright.
    assert "ALONG THE FULL LENGTH" in notes
    assert "MARKER GROOVE" in notes
    assert "DO NOT PAINT" in notes
    assert "GREEN" not in notes
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" in linked_note_properties(source)
    assert "_NOTES_" not in source


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["Bore0Dia"] == "2X THRU"
    assert callouts["ScrewHoleDiaDim"] == "THRU"
    assert "45 DEG" in callouts["Chamfer2dx"]


def test_native_gdt_replaces_form_orientation_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 2
    assert "characteristic=\"parallelism\"" in source
    assert "characteristic=\"position\"" in source
    # Ra 1.6 on BOTH pen bores (the 2X functional pair), one symbol each.
    assert source.count("add_surface_finish(") == 2
    assert all(
        isinstance(control.face, CylinderFace)
        for control in pen_v_block_spec.SURFACE_FINISHES
    )
    assert {control.face.contains_x_mm for control in pen_v_block_spec.SURFACE_FINISHES} == set(
        pen_v_block_spec.BORE_X
    )
    assert source.count("surface_finish_by_key(SURFACE_FINISHES") == 2


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in source
    import _config

    spec = _config.parts("pen-v-block")
    assert "brass" in str(spec["material_specification"]).lower()
    assert "bright brass" in str(spec["finish"]).lower()
    assert int(spec["quantity"]) == 1
