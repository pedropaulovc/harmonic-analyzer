"""Offline contracts for the guide-lock drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a clamp plate
carries no datums, frames, roughness symbols or basic dimensions; its hole
locators are ordinary coordinate dimensions and its notes are two lines of
process fact.
"""

from __future__ import annotations

from pathlib import Path

import build_guide_lock as lock
import draw_guide_lock as drawing
import guide_lock_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import CLEARANCE_MM


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


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
    source = _source()
    assert source.count("scale=(4, 1)") == 2  # front + right
    assert source.count("scale=(2, 1)") == 1  # the isometric override
    assert guide_lock_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = guide_lock_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "STOCK" in notes  # the cleanup-cut licence (Lipton)
    assert "MATES WITH" in notes
    # The hole size and process ride the native callout, not the notes; the
    # quantity and finish live in the title block.
    for banned in (
        "DRILL",
        "PER FCF",
        "REQUIRED",
        "BLACK OXIDE",
        "UOS",
        "+/-",
        "DATUM",
        "BA ",
        "X.XX",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_locators_are_ordinary_dimensions_with_a_native_callout() -> None:
    source = _source()
    assert source.count("add_edge_dimension(") == 3
    assert 'label="hole-1 X location"' in source
    assert 'label="hole-2 X location"' in source
    assert 'label="hole band height"' in source
    assert source.count("add_native_hole_callout(") == 1
    # Harvey #13: the callout says DRILL.
    assert 'process="DRILL"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-5: a clamp plate is not on the GD&T
    # allowlist and nothing runs on it.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(guide_lock_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(guide_lock_spec, "GEOMETRIC_CONTROLS")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


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
