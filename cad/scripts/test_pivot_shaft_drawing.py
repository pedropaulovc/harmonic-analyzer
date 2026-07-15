"""Offline contracts for the pivot-shaft drawing."""

from __future__ import annotations

from pathlib import Path

import build_pivot_shaft as part
import draw_pivot_shaft as drawing
import pivot_shaft_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pivot-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pivot-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pivot-shaft_drawing.png")
    assert DRAWINGS_BY_NAME["pivot_shaft"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pivot_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*pivot_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.SHAFT_DIA, drawing.SHAFT_LENGTH) == (
        pivot_shaft_spec.SHAFT_DIA,
        pivot_shaft_spec.SHAFT_LENGTH,
    )


def test_linked_notes_define_remaining_bearing_shaft_operations() -> None:
    notes = pivot_shaft_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS["ShaftDia"] == "+0.00/-0.02"
    # The length tolerance rides the dimension, not the general note.
    assert drawing.DIMENSION_CALLOUTS["Depth"] == "+/-0.25"
    assert "LENGTH +/-" not in notes
    clearance_min = 6.50 - pivot_shaft_spec.SHAFT_DIA
    clearance_max = clearance_min + 0.02 + 0.03
    assert round(clearance_min, 2) == 0.15
    assert round(clearance_max, 2) == 0.20
    assert "CENTRE MARKS" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_shaft_form_orientation_and_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 2
    assert "characteristic=\"cylindricity\"" in source
    assert source.count("characteristic=\"perpendicularity\"") == 1
    assert source.count("add_surface_finish(") == 2


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 2
    assert "scale=(2, 1)" in source
    assert pivot_shaft_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pivot-shaft")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
