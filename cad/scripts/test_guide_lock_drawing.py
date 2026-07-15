"""Offline contracts for the guide-lock drawing."""

from __future__ import annotations

from pathlib import Path

import build_guide_lock as lock
import draw_guide_lock as drawing
import guide_lock_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import CLEARANCE_MM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/guide-lock.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/guide-lock.pdf")
    assert drawing.PNG.as_posix().endswith("/png/guide-lock_drawing.png")
    assert DRAWINGS_BY_NAME["guide_lock"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map, and the drawing's view math reads the spec's
    # nominal spans, not a divergent copy.
    assert lock.DRAWING_DIMENSIONS is guide_lock_spec.DRAWING_DIMENSIONS
    marked = set().union(*guide_lock_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.LOCK_WIDTH, drawing.LOCK_HEIGHT, drawing.LOCK_THICK) == (
        guide_lock_spec.LOCK_WIDTH,
        guide_lock_spec.LOCK_HEIGHT,
        guide_lock_spec.LOCK_THICK,
    )
    assert lock.HOLE_XY is guide_lock_spec.HOLE_XY


def test_spec_hole_diameter_matches_the_wizard_clearance_table() -> None:
    # The drawing's COM-free pinned copy of the #4 CLOSE clearance drill must
    # track the wizard table the part build actually cuts from.
    assert guide_lock_spec.HOLE_DIA_MM == CLEARANCE_MM[("#4", "close")]
    source = Path(lock.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("clearance", "#4", fit="close")' in source


def test_sheet_runs_at_4_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(4, 1)") == 2  # front + right
    assert source.count("scale=(2, 1)") == 1  # the isometric override
    assert guide_lock_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_use_us_customary_fasteners_and_functional_tolerances() -> None:
    notes = guide_lock_spec.DRAWING_NOTES
    assert "#4 CLEARANCE DRILL THRU" in notes
    assert "LINEAR +/-0.25" in notes
    assert "HOLE POSITION PER FCF" in notes
    assert "4 REQUIRED" in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series; no display-zero tolerances.
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_locators_are_basic_dimensions_off_the_datum_edges() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_edge_dimension(") == 3
    assert source.count("set_basic_dimension(") == 3
    assert "add_native_hole_callout(" in source


def test_native_gdt_replaces_form_orientation_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 2
    assert 'characteristic="position"' in source
    assert 'characteristic="flatness"' in source
    assert 'quantity="2X"' in source
    assert source.count("add_surface_finish(") == 1


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "ScrewHoles" not in lock.DRAWING_DIMENSIONS
    marked = set().union(*lock.DRAWING_DIMENSIONS.values())
    assert not {name for name in marked if "Hole" in name}


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lock.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("guide-lock")
    assert spec["material_specification"]
    assert "black oxide" in str(spec["finish"]).lower()
    assert int(spec["quantity"]) == 4
