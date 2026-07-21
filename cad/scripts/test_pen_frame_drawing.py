"""Offline contracts for the pen-frame drawing."""

from __future__ import annotations

from pathlib import Path

import build_pen_frame as part
import draw_pen_frame as drawing
import pen_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME


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


def test_notes_describe_the_yoke_and_set_screw() -> None:
    notes = pen_frame_spec.DRAWING_NOTES
    assert "#4-40 UNC-2B" in notes
    assert "WINDOW" in notes
    assert "10.25 +/-0.05 FROM LEFT OUTER FACE" in notes
    assert "MID-DEPTH CENTER PLANE" in notes
    assert "CDA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
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
