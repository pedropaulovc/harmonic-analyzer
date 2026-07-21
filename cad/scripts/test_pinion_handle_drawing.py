"""Offline contracts for the pinion-turning-handle drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_handle_spec
import draw_pinion_handle as drawing
import build_pinion_handle as handle
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-handle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-handle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-handle_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_handle"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert handle.DRAWING_DIMENSIONS is pinion_handle_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_handle_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.TUBE_ID, drawing.ROD_UP, drawing.ROD_DOWN) == (
        pinion_handle_spec.TUBE_ID,
        pinion_handle_spec.ROD_UP,
        pinion_handle_spec.ROD_DOWN,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert pinion_handle_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_handle_spec.DRAWING_NOTES
    assert "BLIND" in notes
    assert "8.010-8.025" in notes
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_unique_feature_dimensions_and_direct_bore_limits() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "add_surface_finish(" not in source
    assert {"GripLen", "TubeLen", "RodSpan"} <= set().union(
        *pinion_handle_spec.DRAWING_DIMENSIONS.values()
    )
    assert "8.010/8.025" in drawing.DIMENSION_CALLOUTS["TubeId"]


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-handle")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
