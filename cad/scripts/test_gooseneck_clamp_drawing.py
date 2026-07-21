"""Offline contracts for the gooseneck-clamp drawing."""

from __future__ import annotations

from pathlib import Path

import build_gooseneck_clamp as part
import draw_gooseneck_clamp as drawing
import gooseneck_clamp_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/gooseneck-clamp.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/gooseneck-clamp.pdf")
    assert drawing.PNG.as_posix().endswith("/png/gooseneck-clamp_drawing.png")
    assert (
        DRAWINGS_BY_NAME["gooseneck_clamp"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is gooseneck_clamp_spec.DRAWING_DIMENSIONS
    marked = set().union(*gooseneck_clamp_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked


def test_notes_describe_the_post_bore_and_pinch_screw() -> None:
    notes = gooseneck_clamp_spec.DRAWING_NOTES
    assert "GOOSENECK POST" in notes
    assert "PINCH" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source
    assert "scale=(1, 1)" in source
    assert gooseneck_clamp_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("gooseneck-clamp")
    assert "iron" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
