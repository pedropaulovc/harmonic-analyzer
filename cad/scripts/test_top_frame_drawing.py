"""Offline contracts for the top-frame drawing."""

from __future__ import annotations

from pathlib import Path

import build_top_frame as part
import draw_top_frame as drawing
import top_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/top-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/top-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/top-frame_drawing.png")
    assert DRAWINGS_BY_NAME["top_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is top_frame_spec.DRAWING_DIMENSIONS
    marked = set().union(*top_frame_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP)
    assert kept == marked


def test_notes_carry_the_pitch_rail_and_boss() -> None:
    notes = top_frame_spec.DRAWING_NOTES
    assert "GRAY-IRON" not in notes
    assert "ASTM A48" not in notes
    assert "GREEN ENAMEL" not in notes
    assert "UOS" not in notes
    assert "MACHINE FROM SOLID STOCK" in notes
    assert "394.00 X 224.00" in notes
    assert "25.50 +0.05/-0.00" in notes
    assert "GOOSENECK BORE" in notes
    assert "LEFT RAIL IN PLAN" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert "scale=(1, 4)" in source
    assert top_frame_spec.TOP_VIEW_NOTE == "PLAN VIEW SCALE 1:2"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("top-frame")
    assert config["material"] == config["material_specification"]
    assert "gray cast iron" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert config["process"] == "machined from solid stock"
    assert int(config["quantity"]) == 1
