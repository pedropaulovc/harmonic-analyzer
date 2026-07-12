"""Offline contracts for the lever-bushing drawing."""

from __future__ import annotations

from pathlib import Path

import build_lever_bushing as part
import draw_lever_bushing as drawing
import lever_bushing_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/lever-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/lever-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/lever-bushing_drawing.png")
    assert DRAWINGS_BY_NAME["lever_bushing"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is lever_bushing_spec.DRAWING_DIMENSIONS
    marked = set().union(*lever_bushing_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.OUTER_DIA, drawing.BORE_DIA, drawing.LENGTH) == (
        lever_bushing_spec.OUTER_DIA,
        lever_bushing_spec.BORE_DIA,
        lever_bushing_spec.LENGTH,
    )


def test_notes_define_a_buildable_turned_part() -> None:
    notes = drawing._manufacturing_notes()
    assert "REAM O6.50 THRU" in notes
    assert "TOTAL LENGTH +/-0.03" in notes
    assert "0.05 TIR" in notes
    assert "MAKE 19" in notes
    assert "Ra 1.6" in notes
    assert "X.XX" not in notes


def test_sheet_and_views_pin_scale() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(4, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("lever-bushing")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 19
