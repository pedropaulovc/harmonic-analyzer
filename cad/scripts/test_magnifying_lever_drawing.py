"""Offline contracts for the magnifying-lever drawing."""

from __future__ import annotations

from pathlib import Path

import build_magnifying_lever as part
import draw_magnifying_lever as drawing
import magnifying_lever_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifying-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifying-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifying-lever_drawing.png")
    assert (
        DRAWINGS_BY_NAME["magnifying_lever"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is magnifying_lever_spec.DRAWING_DIMENSIONS
    marked = set().union(*magnifying_lever_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.ROD_DIA, drawing.ROD_LENGTH) == (
        magnifying_lever_spec.ROD_DIA,
        magnifying_lever_spec.ROD_LENGTH,
    )


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The knife-axis station the assembly imports lives in the drawing-FREE geom
    # module, so a print-note edit cannot enter the assembly's recipe closure.
    import magnifying_lever_geom as geom

    assert (geom.ROD_DIA, geom.ROD_LENGTH) == (6.0, 165.0)
    assert hasattr(geom, "KNIFE_LOCAL_X") and hasattr(geom, "KNIFE_LOCAL_Y")
    assembly = Path(part.__file__).with_name("build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from magnifying_lever_geom import KNIFE_LOCAL_X, KNIFE_LOCAL_Y" in assembly


def test_linked_notes_specify_round_brass_stock_and_domed_ends() -> None:
    notes = magnifying_lever_spec.DRAWING_NOTES
    assert "Ø6 ROUND BRASS" in notes
    assert "HEMISPHERE" in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes
    assert "165" in notes  # overall length carried in the note
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert drawing.DIMENSION_CALLOUTS["DomeRadius"] == "FULL R, BOTH ENDS - Ø6 ROD"


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the front side view
    assert "scale=(4, 1)" in source  # the end view
    assert drawing.ISO_SCALE == (1, 2)
    assert "scale=ISO_SCALE" in source
    assert magnifying_lever_spec.END_VIEW_NOTE == "END VIEW SCALE 4:1"
    assert magnifying_lever_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
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
    assert "Ra 1.6" in magnifying_lever_spec.DRAWING_NOTES


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-lever")
    assert config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
