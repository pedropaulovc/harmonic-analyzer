"""Offline contracts for the crankshaft drawing."""

from __future__ import annotations

import re
from pathlib import Path

import build_crankshaft as part
import crankshaft_spec
import draw_crankshaft as drawing
from _drawing_registry import DRAWINGS_BY_NAME
import _holes as hole_wizard
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
    assert drawing.JOURNAL_DIA == crankshaft_spec.JOURNAL_DIA
    assert drawing.JOURNAL_START == crankshaft_spec.JOURNAL_START
    assert drawing.JOURNAL_LENGTH == crankshaft_spec.JOURNAL_LENGTH


def test_v2_post_journal_recloses_the_hardware_seats() -> None:
    assert crankshaft_spec.JOURNAL_BORE_DIA == 11.438
    assert crankshaft_spec.JOURNAL_CLEARANCE == 0.05
    assert crankshaft_spec.JOURNAL_DIA == 11.388
    assert crankshaft_spec.JOURNAL_START == 32.755105572
    assert crankshaft_spec.JOURNAL_END == 104.789505572
    assert crankshaft_spec.JOURNAL_LENGTH == 72.0344
    assert -175.0 + crankshaft_spec.JOURNAL_START == -142.244894428
    assert -175.0 + crankshaft_spec.JOURNAL_END == -70.210494428
    assert (part.SEAT_T12, part.SEAT_PINION, part.SEAT_ARM) == (
        17.5,
        105.039505572,
        8.0,
    )
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'await set_global(adapter, "JournalDia"' in source
    assert 'await adapter.create_sketch("JournalStartPlane")' in source
    assert "ExtrusionParameters(depth=JOURNAL_LENGTH)" in source


def test_cross_hole_matches_the_wizard_drill_and_build_station() -> None:
    # The spec mirrors the #9 wizard drill table so the drawing stays COM-free;
    # a drill-size change in _holes must move the spec (and this test) with it.
    assert crankshaft_spec.PIN_HOLE_DIA == NUMBER_DRILL_MM["#9"]
    assert part.PIN_HOLE_HEIGHT is crankshaft_spec.PIN_HOLE_HEIGHT
    assert crankshaft_spec.PIN_HOLE_HEIGHT == 4.0
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'await set_global(adapter, "PinHoleHeight"' in build_source
    assert 'name_last_feature(adapter, "PinHoleStationPlane")' in build_source
    assert "[-SHAFT_DIA / 2.0, PIN_HOLE_HEIGHT, 0.0]" in build_source
    assert 'point_planes=("PinHoleStationPlane", "Front Plane")' in build_source
    hole_source = Path(hole_wizard.__file__).read_text(encoding="utf-8")
    assert "face_candidates.append(candidate)" in hole_source
    assert '_add_sketch_constraint_impl(' in hole_source
    notes = crankshaft_spec.DRAWING_NOTES
    assert "#9" not in notes
    assert "TAPER PIN" in notes
    assert "FINISHED SIZE FOR THIS PART" in notes
    assert "<MOD-DIAM>4.98" not in notes
    assert "+0.10/0" not in notes
    assert "INTERSECTS THE SHAFT AXIS" not in notes
    assert "PART ACCEPTANCE:" not in notes
    assert "CUSTOM TAPER PIN" in notes and "MHA-024" in notes
    assert "CRANK ARM MHA-020" in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Ø/THRU comes from the associative wizard callout; a drawing-native
    # end-face-to-hole-axis dimension supplies the basic station.
    assert source.count("add_native_hole_callout(") == 1
    assert "GetVisibleEntities2(c, 1)" in source
    assert "cross_hole_edge = _visible_cross_hole_edge(adapter, right)" in source
    assert "edge=cross_hole_edge" in source
    assert source.count("add_edge_dimension(") == 1
    assert "pin_station = add_edge_dimension(" in source
    assert 'orientation="vertical"' in source
    assert "set_arc_endpoints_to_center(adapter, pin_station" in source
    assert "set_basic_dimension(adapter, pin_station" in source
    assert "PinHole" not in crankshaft_spec.DRAWING_DIMENSIONS


def test_linked_notes_define_remaining_operations() -> None:
    notes = crankshaft_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    assert "AISI" not in notes
    assert "ZINC" not in notes
    assert "UOS" not in notes
    assert "OUTSIDE THIS PART DRAWING" in notes
    assert "11.388 BEARING JOURNAL" in notes
    assert "11.438 POST BORE" in notes
    assert "0.05 DIAMETRAL CLEARANCE" in notes
    assert "KEEP DIA 9.525" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_finish_and_notes_control_the_turned_shaft() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert source.count("add_feature_control_frame(") == 2
    assert source.count("add_surface_finish(") == 1
    assert "add_view_centerline(" in source
    assert re.search(r"GetVisibleEntities2\(\s*c,\s*3\s*\)", source)
    assert "face=journal_face" in source
    assert re.search(r"GetVisibleEntities2\(\s*c,\s*4\s*\)", source)
    assert "journal_silhouette = _visible_journal_silhouette(adapter, right)" in source
    assert "edge_entity=journal_silhouette" in source
    assert 'entity_type="SILHOUETTE"' in source
    assert 'production_method="BEARING JOURNAL"' not in source
    assert crankshaft_spec.SURFACE_FINISHES[0].production_method == "BEARING JOURNAL"
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bearing_journal")' in source
    assert 'dimension_name(adapter, annotation) == "ShaftDiaDim"' in source
    assert drawing.DATUM_A_RIGHT == (
        drawing.FRONT_CENTER[0] + drawing.JOURNAL_DIA * drawing.END_VIEW_SCALE / 2000.0,
        drawing.FRONT_CENTER[1],
    )
    assert "edge_xy=DATUM_A_RIGHT" in source
    assert "entity=shaft_datum_edge" not in source
    assert "shoulder=True" not in source
    assert "position_tolerance_m=0.0001" in source
    assert "annotation=shaft_dia_annotation" not in source
    assert "symbol_xy=(0.205, 0.145)" in source
    assert "frame_xy=(0.100, 0.055)" in source
    assert 'characteristic="position"' in source
    assert 'characteristic="perpendicularity"' in source
    assert "face_xy=" not in source
    assert "BOTH END FACES SQUARE" not in crankshaft_spec.DRAWING_NOTES


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.ISO_CENTER == (0.345, 0.197)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 2
    assert "scale=(2, 1)" in source
    assert crankshaft_spec.END_VIEW_NOTE == "CRANK-END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert 'add_property_linked_note(adapter, "Crank End Note", 0.250, 0.090)' in source
    assert 'place_view(adapter, str(SOURCE), "*Right"' in source


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
