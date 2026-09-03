"""Offline contracts for the pen-frame drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a brass stirrup
yoke carries no datums, frames or roughness symbols, and its notes are three
lines of process fact.
"""

from __future__ import annotations

from pathlib import Path

import build_pen_frame as part
import draw_pen_frame as drawing
import pen_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-frame_drawing.png")
    assert DRAWINGS_BY_NAME["pen_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pen_frame_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_frame_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pen_frame_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "#4-40 UNC" in notes
    assert "DO NOT MIRROR" in notes
    assert "WINDOW" in notes
    for banned in ("UOS", "DIMENSIONS IN", "+/-", "WITHIN", "DATUM", "CDA", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(pen_frame_spec, "GEOMETRIC_TOLERANCES_MM")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = _source()
    assert "scale=(2, 1)" in source
    assert pen_frame_spec.FRONT_VIEW_NOTE == "FRONT VIEW SCALE 2:1"
    assert pen_frame_spec.RIGHT_VIEW_NOTE == "RIGHT-SIDE VIEW SCALE 2:1"
    assert '"*Right"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pen-frame")
    assert config["material"] == "C36000 free-machining brass"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
