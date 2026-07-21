"""Offline contracts for the magnifying-vertical-rod drawing."""

from __future__ import annotations

from pathlib import Path

import build_magnifying_vertical_rod as part
import draw_magnifying_vertical_rod as drawing
import magnifying_vertical_rod_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifying-vertical-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifying-vertical-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifying-vertical-rod_drawing.png")
    assert (
        DRAWINGS_BY_NAME["magnifying_vertical_rod"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is magnifying_vertical_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*magnifying_vertical_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.ROD_DIA, drawing.ROD_LENGTH) == (
        magnifying_vertical_rod_spec.ROD_DIA,
        magnifying_vertical_rod_spec.ROD_LENGTH,
    )
    assert (magnifying_vertical_rod_spec.ROD_DIA, magnifying_vertical_rod_spec.ROD_LENGTH) == (
        5.0,
        150.0,
    )


def test_linked_notes_specify_round_brass_stock_and_domed_ends() -> None:
    notes = magnifying_vertical_rod_spec.DRAWING_NOTES
    assert "Ø5 ROUND BAR" in notes
    assert "BRASS" not in notes and "C36000" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "HEMISPHERE" in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes
    assert "150" in notes  # overall length carried in the note
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert drawing.DIMENSION_CALLOUTS["DomeRadius"] == "FULL R, BOTH ENDS - Ø5 ROD"


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the front side view
    assert "scale=(4, 1)" in source  # the end view
    assert drawing.ISO_SCALE == (1, 2)
    assert "scale=ISO_SCALE" in source
    assert magnifying_vertical_rod_spec.END_VIEW_NOTE == "END VIEW SCALE 4:1"
    assert magnifying_vertical_rod_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source


def test_form_and_finish_are_note_based_on_the_unpickable_capsule() -> None:
    # A smooth hemispherical-ended capsule exposes no selectable edge, so there
    # are NO coordinate-pick annotations (datum/FCF/Ra/edge dims); the OD
    # straightness + Ra requirement is carried in the manufacturing note instead.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 0
    assert source.count("add_feature_control_frame(") == 0
    assert source.count("add_surface_finish(") == 0
    assert source.count("add_edge_dimension(") == 0
    assert "Ra 1.6" in magnifying_vertical_rod_spec.DRAWING_NOTES


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-vertical-rod")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
