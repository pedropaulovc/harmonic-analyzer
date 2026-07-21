"""Offline contracts for the crankshaft drawing."""

from __future__ import annotations

from pathlib import Path

import build_crankshaft as part
import crankshaft_spec
import draw_crankshaft as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import NUMBER_DRILL_MM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crankshaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crankshaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crankshaft_drawing.png")
    assert DRAWINGS_BY_NAME["crankshaft"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is crankshaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*crankshaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.SHAFT_DIA, drawing.SHAFT_LENGTH) == (
        crankshaft_spec.SHAFT_DIA,
        crankshaft_spec.SHAFT_LENGTH,
    )


def test_cross_hole_matches_the_wizard_drill_and_build_station() -> None:
    # The spec mirrors the #9 wizard drill table so the drawing stays COM-free;
    # a drill-size change in _holes must move the spec (and this test) with it.
    assert crankshaft_spec.PIN_HOLE_DIA == NUMBER_DRILL_MM["#9"]
    assert part.PIN_HOLE_HEIGHT is crankshaft_spec.PIN_HOLE_HEIGHT
    assert crankshaft_spec.PIN_HOLE_HEIGHT == 12.0
    notes = crankshaft_spec.DRAWING_NOTES
    assert "#9" not in notes
    assert "TAPER PIN" in notes
    assert "FINISHED PILOT-HOLE CONDITION" in notes
    assert "INTERSECTS THE SHAFT AXIS" in notes
    assert "PART ACCEPTANCE:" not in notes
    assert "CUSTOM TAPER PIN" in notes and "MHA-024" in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Ø/THRU comes from the associative wizard callout; the model-owned nested
    # sketch dimension supplies the station without a coordinate pick.
    assert source.count("add_native_hole_callout(") == 1
    assert "GetVisibleEntities2(c, 1)" in source
    assert "edge=_visible_cross_hole_edge(adapter, right)" in source
    assert "edge_xy=" not in source
    assert source.count("add_edge_dimension(") == 0
    assert source.count("set_basic_dimensions(") == 0
    assert crankshaft_spec.DRAWING_DIMENSIONS["3DSketch1"] == {"PinHeight"}


def test_linked_notes_define_remaining_operations() -> None:
    notes = crankshaft_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS["ShaftDiaDim"] == "+0.00/-0.02"
    assert "AISI" not in notes
    assert "ZINC" not in notes
    assert "UOS" not in notes
    assert "OUTSIDE THIS PART DRAWING" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_finish_and_notes_control_the_turned_shaft() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 0
    assert source.count("add_feature_control_frame(") == 0
    assert source.count("add_surface_finish(") == 1
    assert "add_view_centerline(" in source
    assert "GetVisibleEntities2(c, 3)" in source
    assert "face=shaft_face" in source
    assert 'symbol_xy=(0.185, 0.065)' in source
    assert 'entity_type="FACE"' in source
    assert "edge_entity=shaft_face" in source
    assert "face_xy=" not in source
    assert "BOTH END FACES SQUARE" in crankshaft_spec.DRAWING_NOTES


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 2
    assert "scale=(2, 1)" in source
    assert crankshaft_spec.END_VIEW_NOTE == "CRANK-END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert 'add_property_linked_note(adapter, "Crank End Note", 0.250, 0.090)' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("crankshaft")
    assert config["material"] == config["material_specification"]
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
