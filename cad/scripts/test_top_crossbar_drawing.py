"""Offline contracts for the top-crossbar drawing."""

from __future__ import annotations

from pathlib import Path

import build_top_crossbar as part
import draw_top_crossbar as drawing
import top_crossbar_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/top-crossbar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/top-crossbar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/top-crossbar_drawing.png")
    assert DRAWINGS_BY_NAME["top_crossbar"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is top_crossbar_spec.DRAWING_DIMENSIONS
    marked = set().union(*top_crossbar_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP)
    assert kept == marked
    assert (drawing.BAR_WIDTH, drawing.BAR_HEIGHT) == (
        top_crossbar_spec.BAR_WIDTH,
        top_crossbar_spec.BAR_HEIGHT,
    )


def test_notes_define_a_buildable_cast_crossbar() -> None:
    notes = drawing._manufacturing_notes()
    assert "GRAY-IRON CASTING" in notes
    assert "FOR 5/16 STUD" in notes
    assert "CLOSE FIT" in notes
    assert "21/64 DRILL THRU" in notes
    assert "Ø8.33 NOMINAL" in notes
    assert "ACTUAL SIDE FACES" in notes
    assert drawing.HOLE_CALLOUT == "Ø8.33 (21/64) THRU - NOTE 4"
    assert "END FACES PARALLEL 0.10" in notes
    assert "GREEN ENAMEL" in notes
    assert "NO DRAFT MODELLED" in notes
    assert "X.XX" not in notes


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 1
    assert source.count("scale=(1, 2)") == 2
    assert "TOP VIEW SCALE 1:2" in source
    assert "ISOMETRIC VIEW SCALE 1:2" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("top-crossbar")
    assert "gray cast iron" in str(config["material_specification"]).lower()
    assert "green enamel" in str(config["finish"]).lower()
    assert int(config["quantity"]) == 1
