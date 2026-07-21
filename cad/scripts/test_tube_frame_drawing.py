"""Offline contracts for the tube-frame drawing."""

from __future__ import annotations

from pathlib import Path

import build_tube_frame as part
import draw_tube_frame as drawing
import tube_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/tube-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/tube-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/tube-frame_drawing.png")
    assert DRAWINGS_BY_NAME["tube_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is tube_frame_spec.DRAWING_DIMENSIONS
    marked = set().union(*tube_frame_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.LENGTH_KEEP)
    assert kept == marked
    assert drawing.OUTER_DIA == tube_frame_spec.OUTER_DIA


def test_tube_nominals_are_single_sourced() -> None:
    assert part.OUTER_DIA is tube_frame_spec.OUTER_DIA
    assert part.COLUMN_LENGTH is tube_frame_spec.COLUMN_LENGTH
    assert tube_frame_spec.OUTER_DIA == 25.4
    # 1 in OD, 0.12 in wall -> Ø19.304 bore.
    assert abs(tube_frame_spec.INNER_DIA - 19.304) < 1e-6


def test_notes_and_native_gdt() -> None:
    notes = tube_frame_spec.DRAWING_NOTES
    assert "STEEL TUBE" in notes
    assert "FACED SQUARE TO AXIS A" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert source.count("add_surface_finish(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 5)" in source
    assert "scale=(2, 1)" in source
    assert tube_frame_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("tube-frame")
    assert "tube" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 4
