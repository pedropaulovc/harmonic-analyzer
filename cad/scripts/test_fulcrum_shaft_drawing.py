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


def test_linked_notes_define_remaining_bearing_shaft_operations() -> None:
    notes = fulcrum_shaft_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS["ShaftDia"] == "+0.00/-0.02"
    clearance_min = 6.50 - fulcrum_shaft_spec.SHAFT_DIA
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
    assert "position_tolerance_m=0.001" in source
    assert source.count("add_feature_control_frame(") == 2
    assert "characteristic=\"cylindricity\"" in source
    assert source.count("characteristic=\"perpendicularity\"") == 1
    assert source.count("add_surface_finish(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Only the side view is 1:1 now; the isometric renders at ISO_SCALE so its
    # outline stays inside the right zone border (see draw_fulcrum_shaft).
    assert source.count("scale=(1, 1)") == 1
    assert "scale=(2, 1)" in source
    assert drawing.ISO_SCALE == (1, 2)
    assert "scale=ISO_SCALE" in source
    assert fulcrum_shaft_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    # An off-sheet-scale view needs its OWN scale label or the title block's 1:1
    # misstates it. cylinder-gear-shaft got this from a codex machinist review;
    # this sibling shipped the same 1:2 iso unlabelled until codex #334.
    assert fulcrum_shaft_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("fulcrum-shaft")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
