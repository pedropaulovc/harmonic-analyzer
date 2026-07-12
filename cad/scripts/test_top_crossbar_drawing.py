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


def test_linked_notes_define_remaining_casting_requirements() -> None:
    notes = top_crossbar_spec.DRAWING_NOTES
    assert "GRAY-IRON CASTING" in notes
    assert "FOR 5/16 STUD" in top_crossbar_spec.HOLE_CALLOUT
    assert "CLOSE FIT" in top_crossbar_spec.HOLE_CALLOUT
    assert "21/64" in top_crossbar_spec.HOLE_CALLOUT
    assert "O8.33" in top_crossbar_spec.HOLE_CALLOUT
    assert "NO DRAFT MODELLED" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert 'property_name="Hole Callout"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_crossbar_end_seats_and_hole() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 3
    assert "characteristic=\"position\"" in source
    assert "characteristic=\"perpendicularity\"" in source
    assert "characteristic=\"parallelism\"" in source
    assert source.count("add_surface_finish(") == 1
    assert '"lower end-seat finish"' in source
    assert '"upper end-seat finish"' in source
    assert '"crossbar stud-hole finish"' not in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 1
    assert source.count("scale=(1, 2)") == 2
    assert top_crossbar_spec.TOP_VIEW_NOTE == "TOP VIEW SCALE 1:2"
    assert top_crossbar_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Top View Note"' in source
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("top-crossbar")
    assert "gray cast iron" in str(config["material_specification"]).lower()
    assert "green enamel" in str(config["finish"]).lower()
    assert int(config["quantity"]) == 1
