"""Offline contracts for the fulcrum-shaft drawing."""

from __future__ import annotations

from pathlib import Path

import build_fulcrum_shaft as part
import draw_fulcrum_shaft as drawing
import fulcrum_shaft_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/fulcrum-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/fulcrum-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/fulcrum-shaft_drawing.png")
    assert DRAWINGS_BY_NAME["fulcrum_shaft"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is fulcrum_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*fulcrum_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.SHAFT_DIA, drawing.SHAFT_LENGTH) == (
        fulcrum_shaft_spec.SHAFT_DIA,
        fulcrum_shaft_spec.SHAFT_LENGTH,
    )


def test_notes_define_a_buildable_bearing_shaft() -> None:
    notes = drawing._manufacturing_notes()
    assert "O6.35 +0.00/-0.02" in notes
    assert "CYLINDRICITY 0.03" in notes
    assert "STRAIGHTNESS" in notes
    assert "Ra 1.6" in notes
    assert "O6.50 LEVER BUSHINGS" in notes
    assert "X.XX" not in notes


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 2
    assert "scale=(2, 1)" in source
    assert "END VIEW SCALE 2:1" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("fulcrum-shaft")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
