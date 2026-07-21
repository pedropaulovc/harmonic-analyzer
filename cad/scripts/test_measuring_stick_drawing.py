"""Offline contracts for the measuring-stick drawing."""

from __future__ import annotations

from pathlib import Path

import build_measuring_stick as part
import draw_measuring_stick as drawing
import measuring_stick_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/measuring-stick.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/measuring-stick.pdf")
    assert drawing.PNG.as_posix().endswith("/png/measuring-stick_drawing.png")
    assert (
        DRAWINGS_BY_NAME["measuring_stick"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is measuring_stick_spec.DRAWING_DIMENSIONS
    marked = set().union(*measuring_stick_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked


def test_notes_cover_the_scale_and_graduations() -> None:
    notes = measuring_stick_spec.DRAWING_NOTES
    assert "FINISHED BAR" in notes
    assert "11 FULL TICKS" in notes
    assert "HALF-DIVISION" in notes
    assert "SQUARE-BOTTOM" in notes
    assert "ASME Y14.2 VERTICAL GOTHIC" in notes
    assert "DEPTH 0.20 +/-0.05" in notes
    assert "CDA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source
    assert "scale=(1, 2)" in source
    assert measuring_stick_spec.FRONT_VIEW_NOTE == "RULED FACE SCALE 1:1"
    assert '"*Back"' in source
    assert "_rotate_ruled_face(adapter, front)" in source
    assert "_add_scale_labels(adapter)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("measuring-stick")
    assert config["material"] == "C26000 brass, half-hard"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
