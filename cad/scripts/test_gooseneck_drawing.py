"""Offline contracts for the gooseneck drawing."""

from __future__ import annotations

from pathlib import Path

import build_gooseneck as part
import draw_gooseneck as drawing
import gooseneck_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/gooseneck.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/gooseneck.pdf")
    assert drawing.PNG.as_posix().endswith("/png/gooseneck_drawing.png")
    assert DRAWINGS_BY_NAME["gooseneck"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is gooseneck_spec.DRAWING_DIMENSIONS
    marked = set().union(*gooseneck_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked


def test_notes_describe_the_chrome_tube_and_bend() -> None:
    notes = gooseneck_spec.DRAWING_NOTES
    assert "2.0 WALL" in notes
    assert "SILVER-BRAZE" in notes
    assert "AISI 1018" in notes
    assert "JOINT PENETRATION" in notes
    assert "CHROME" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert '"Manufacturing Notes", 0.016, 0.105' in source


def test_view_scale_is_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 3.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 3)" in source
    assert "scale=(1, 4)" in source
    # The lug detail view was intentionally dropped (see the "NO lug detail
    # view" rationale in draw_gooseneck.py): assert no detail-view CALL exists,
    # not the historical mention in the explanatory comment.
    assert "CreateDetailViewAt4(" not in source
    assert "NO lug detail view" in source
    assert gooseneck_spec.ELEVATION_VIEW_NOTE == "ELEVATION SCALE 1:3"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("gooseneck")
    assert config["material"] == "AISI 1010 seamless steel tube"
    assert config["material"] == config["material_specification"]
    assert "chrome" not in str(config["material_specification"]).lower()
    assert "ASTM B456 SC2" in str(config["finish"])
    assert int(config["quantity"]) == 1
