"""Offline contracts for the amplitude-bar drawing."""

from __future__ import annotations

from pathlib import Path

import amplitude_bar_spec
import draw_amplitude_bar as drawing
import build_amplitude_bar as bar
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/amplitude-bar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/amplitude-bar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/amplitude-bar_drawing.png")
    assert DRAWINGS_BY_NAME["amplitude_bar"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert bar.DRAWING_DIMENSIONS is amplitude_bar_spec.DRAWING_DIMENSIONS
    marked = set().union(*amplitude_bar_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked


def test_part_geometry_matches_the_spec() -> None:
    assert amplitude_bar_spec.BAR_LENGTH == bar.BAR_LENGTH
    assert amplitude_bar_spec.BAR_WIDTH == bar.BAR_WIDTH


def test_sheet_runs_at_1_to_4_with_1_to_8_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 8)" in source  # the isometric override
    assert "scale=(4, 1)" in source  # the top end-view section override
    assert amplitude_bar_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:8"
    assert amplitude_bar_spec.END_VIEW_NOTE == "END VIEW SCALE 4:1"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_carry_the_notches_and_hole() -> None:
    notes = amplitude_bar_spec.DRAWING_NOTES
    assert "BOTTOM NOTCH" in notes
    assert "TOP NOTCH" in notes
    assert "#47 DRILL" in notes
    assert "LINEAR +/-" not in notes
    assert "STEEL" not in notes
    assert "CHROME" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_functional_notch_finish_is_feature_specific() -> None:
    notes = amplitude_bar_spec.DRAWING_NOTES
    assert "BOTTOM NOTCH FOOT: Ra 0.8" in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "add_surface_finish(" not in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(bar.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("amplitude-bar")
    assert spec["material_specification"] == "AISI 1018 cold-rolled steel, 6.35 sq"
    assert spec["finish"] == "bright chrome plated"
    assert int(spec["quantity"]) == 20
