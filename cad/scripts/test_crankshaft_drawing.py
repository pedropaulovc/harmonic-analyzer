"""Offline contracts for the crankshaft drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a turned shaft
carries no datums, frames or basic dimensions; its one running fit (the
journal) rides the model dimension, its one roughness symbol sits on the
bearing journal that runs in the pedestal bore, the shoulder roots carry a
leadered allowance, and its notes are three lines of process fact.
"""

from __future__ import annotations

import re
from pathlib import Path

import build_crankshaft as part
import crankshaft_spec
import draw_crankshaft as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
import _holes as hole_wizard
from _holes import NUMBER_DRILL_MM


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


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
    assert drawing.JOURNAL_END == crankshaft_spec.JOURNAL_END
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
    assert "y_dim=" not in build_source
    source = _source()
    # Diameter/THRU comes from the associative wizard callout with the drill as
    # its prefix; a drawing-native end-face-to-hole-axis dimension supplies the
    # station under the block tolerance.
    assert source.count("add_native_hole_callout(") == 1
    assert 'process="#9 DRILL"' in source
    assert re.search(r"GetVisibleEntities2\(\s*c,\s*1\s*\)", source)
    assert "cross_hole_edge = _visible_cross_hole_edge(adapter, right)" in source
    assert "edge=cross_hole_edge" in source
    assert source.count("add_edge_dimension(") == 1
    assert "pin_station = add_edge_dimension(" in source
    assert 'orientation="vertical"' in source
    assert "set_arc_endpoints_to_center(adapter, pin_station" in source
    assert "PinHole" not in crankshaft_spec.DRAWING_DIMENSIONS


def test_length_view_lanes_keep_leaders_off_dimension_lines() -> None:
    # Machinist review 2026-09-02: the station text crowded the 122.00 line
    # and the Ra leader crossed the 72.03 line.  Overall + journal length now
    # stack on the LEFT (longer outside shorter); the station, journal start,
    # Ra symbol and root callout sit on the RIGHT.
    left = drawing.RIGHT_CENTER[0]
    assert drawing.RIGHT_KEEP["Depth"][0] < drawing.RIGHT_KEEP["JournalLength"][0] < left
    assert drawing.RIGHT_KEEP["JournalStart"][0] > left
    assert drawing.PIN_STATION_TEXT_XY[0] > left
    assert drawing.PIN_STATION_TEXT_XY[0] < drawing.RIGHT_KEEP["JournalStart"][0]
    assert drawing.JOURNAL_FINISH_SYMBOL_XY[0] > left
    assert drawing.JOURNAL_FINISH_ATTACH_XY == (
        drawing.RIGHT_CENTER[0] + crankshaft_spec.JOURNAL_DIA / 2000.0,
        drawing.JOURNAL_FINISH_SYMBOL_XY[1],
    )
    # The Ra symbol sits above the JournalStart lane's top (the journal's
    # lower shoulder) and below the root callout.
    journal_bottom = drawing._SIDE_BOTTOM + crankshaft_spec.JOURNAL_START / 1000.0
    assert drawing.JOURNAL_FINISH_SYMBOL_XY[1] > journal_bottom
    assert drawing.JOURNAL_ROOT_NOTE_XY[1] > drawing.JOURNAL_FINISH_SYMBOL_XY[1]
    source = _source()
    assert "text_xy=PIN_STATION_TEXT_XY" in source
    assert "leader_attach_xy=JOURNAL_FINISH_ATTACH_XY" in source


def test_shoulder_roots_carry_a_leadered_allowance() -> None:
    # The drawn-sharp journal steps get a 2X root allowance from the view;
    # the pick sits outboard of the 3/8 core so only the Ø11.388 rim is hit.
    assert crankshaft_spec.JOURNAL_ROOT_NOTE == "2X ROOT R0.25 MAX"
    pick_x = drawing.JOURNAL_ROOT_PICK_XY[0] - drawing.RIGHT_CENTER[0]
    assert crankshaft_spec.SHAFT_DIA / 2000.0 < pick_x < crankshaft_spec.JOURNAL_DIA / 2000.0
    assert drawing.JOURNAL_ROOT_PICK_XY[1] == (
        drawing._SIDE_BOTTOM + crankshaft_spec.JOURNAL_END / 1000.0
    )
    source = _source()
    assert "text=JOURNAL_ROOT_NOTE" in source
    assert "entity_xy=root_xy" in source
    assert 'axis="y"' in source
    assert source.count("add_attached_note(") == 1


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = crankshaft_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert drawing.DIMENSION_CALLOUTS == {}
    assert "CENTRES OK" in notes
    # The one operation outside this print: the match-ream at assembly.
    assert "MATCH-REAM AT ASSEMBLY" in notes
    assert "MHA-020" in notes and "MHA-024" in notes
    # The drill rides the callout; the fits ride the dimensions; the root
    # allowance rides its leader.
    assert "#9" not in notes
    assert "ROOT" not in notes
    for banned in ("AISI", "ZINC", "UOS", "+/-", "CLEARANCE", "KEEP DIA", "X.XX", "MAX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_only_the_bearing_journal_carries_a_roughness_symbol() -> None:
    # drawing-simplicity-policy.md rule 5: the journal RUNS in the pedestal
    # bore, so it keeps its symbol; the pinned/set-screwed seats do not.
    source = _source()
    assert source.count("add_surface_finish(") == 1
    assert "add_view_centerline(" in source
    assert re.search(r"GetVisibleEntities2\(\s*c,\s*3\s*\)", source)
    assert "face=journal_face" in source
    assert re.search(r"GetVisibleEntities2\(\s*c,\s*4\s*\)", source)
    assert "journal_silhouette = _visible_journal_silhouette(adapter, right)" in source
    assert "edge_entity=journal_silhouette" in source
    assert 'entity_type="SILHOUETTE"' in source
    assert 'production_method="BEARING JOURNAL"' not in source
    (control,) = crankshaft_spec.SURFACE_FINISHES
    assert control.key == "bearing_journal"
    assert control.production_method == "BEARING JOURNAL"
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bearing_journal")' in source
    assert "symbol_xy=JOURNAL_FINISH_SYMBOL_XY" in source
    assert "surface_finishes=SURFACE_FINISHES" in Path(part.__file__).read_text(
        encoding="utf-8"
    )


def test_print_carries_no_gdt_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-4: a shaft is not on the GD&T
    # allowlist; running fits are size bands on the diameters.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert "_visible_shaft_end_edges(" not in source
    assert "DATUM_A_RIGHT" not in source
    assert not hasattr(crankshaft_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(crankshaft_spec, "GEOMETRIC_CONTROLS")


def test_only_the_journal_carries_a_band_and_both_seats_print_three_decimals() -> None:
    # Machinist review 2026-09-02 / policy rule 2: the journal is the one
    # running fit, so it is the only banded dimension; the 3/8 seats (pinned,
    # set-screwed) are held by their three decimals under the block.
    source = _source()
    assert '{"ShaftDiaDim": 3, "JournalDiaDim": 3}' in source
    assert '"JournalStart": 3' not in source
    assert not hasattr(crankshaft_spec, "SHAFT_DIA_BAND")
    assert crankshaft_spec.JOURNAL_DIA_BAND == (0.00, -0.02)
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert build_source.count("set_dimension_bilateral_tolerance(") == 1
    assert model_toleranced_dimensions(part) == {
        ("JournalProfile", "JournalDiaDim"): "*deviations(JOURNAL_DIA_BAND)"
    }


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.ISO_CENTER == (0.345, 0.197)
    source = _source()
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
