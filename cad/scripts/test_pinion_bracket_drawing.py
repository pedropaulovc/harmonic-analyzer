"""Offline contracts for the pinion-swing-bracket drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_bracket_spec
import pinion_bracket_geometry
import draw_pinion_bracket as drawing
import build_pinion_bracket as bracket
from _buildgraph import module_deps_of
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
    assert pinion_bracket_spec.C2C == pinion_bracket_geometry.C2C


def test_drive_train_recipe_depends_on_geometry_not_drawing_notes() -> None:
    drive_train = Path(__file__).with_name("build_drive_train_assembly.py")
    dependency_names = {Path(path).name for path in module_deps_of(drive_train)}
    assert "pinion_bracket_geometry.py" in dependency_names
    assert "build_pinion_bracket.py" not in dependency_names
    assert "pinion_bracket_spec.py" not in dependency_names


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert (
        pinion_bracket_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    )
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_and_callouts_fully_define_functional_limits() -> None:
    notes = pinion_bracket_spec.DRAWING_NOTES
    assert "3.00 MIN" not in notes
    assert "GO PIN" not in notes
    assert "CLAMPED FACE-TO-FACE" in notes
    assert "6.375 MAX / 6.360 MIN" in drawing.DIMENSION_CALLOUTS["PivotBoreDia"]
    assert "8.025 MAX / 8.010 MIN" in drawing.DIMENSION_CALLOUTS["ArborBoreDia"]
    assert "4.012 MAX / 4.000 MIN" in drawing.DIMENSION_CALLOUTS["PinSeatDia"]
    assert "1/4 IN" not in drawing.DIMENSION_CALLOUTS["PivotBoreDia"]
    assert "5/16" not in drawing.DIMENSION_CALLOUTS["ArborBoreDia"]
    assert drawing.DIMENSION_CALLOUTS["PinSeatCy"].count("\n") == 2
    assert "THRU - REAM" in drawing.DIMENSION_CALLOUTS["ArborBoreDia"]
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert " BA " not in f" {notes} "
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert "THRU - REAM" in callouts["PivotBoreDia"]
    assert "THRU" in callouts["ArborBoreDia"]
    assert "FLAT BOTTOM" in callouts["PinSeatDia"]
    assert "TOTAL DEPTH" in callouts["PinSeatDepth"]


def test_blind_seat_depth_uses_the_marked_drawing_name() -> None:
    source = Path(bracket.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "PinSeat", ["PinSeatDepth"])' in source


def test_direct_limits_replace_ambiguous_datum_scheme() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "add_surface_finish(" not in source
    assert drawing.DIMENSION_CALLOUTS["ArborBoreCz"] == "+/-0.10"
    assert "BROAD FACE" in drawing.DIMENSION_CALLOUTS["PinSeatCz"]


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(bracket.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-bracket")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 2  # the book uses two swing brackets


def test_shared_template_edge_break_is_metric_and_not_duplicated() -> None:
    import _drawing_common

    assert _drawing_common._METRIC_EDGE_BREAK_NOTE == (
        "REMOVE BURRS AND BREAK SHARP EDGES R0.25 OR CHAMFER 0.25 MAX"
    )
    common_source = Path(_drawing_common.__file__).read_text(encoding="utf-8")
    assert "_replace_template_edge_break_note(adapter, ddoc)" in common_source
    assert "REMOVE BURRS" not in pinion_bracket_spec.DRAWING_NOTES


def test_drawing_exports_pdf_before_view_only_reopen() -> None:
    import _drawing_common

    common_source = Path(_drawing_common.__file__).read_text(encoding="utf-8")
    first_pdf_export = common_source.index(
        "adapter, str(outputs.slddrw), pdf_path=str(outputs.pdf)"
    )
    first_reopen = common_source.index(
        "await reopen_drawing(adapter, outputs.slddrw)", first_pdf_export
    )
    assert first_pdf_export < first_reopen
    assert 'adapter._get_attr_or_call(drawing_model, "GetSaveFlag")' in common_source
    assert "if sheet_scale_dirty:" in common_source
    persisted_pdf_export = common_source.index(
        "adapter, str(outputs.slddrw), pdf_path=str(outputs.pdf)",
        first_reopen + 1,
    )
    second_reopen = common_source.index(
        "await reopen_drawing(adapter, outputs.slddrw)", first_reopen + 1
    )
    dirty_branch = common_source.index("if sheet_scale_dirty:", first_reopen)
    assert dirty_branch < persisted_pdf_export < second_reopen
    assert "persisted-scale drawing save/export incomplete" in common_source
