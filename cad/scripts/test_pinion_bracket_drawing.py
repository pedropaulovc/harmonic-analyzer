"""Offline contracts for the pinion-swing-bracket drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_bracket_spec
import pinion_bracket_geometry
import draw_pinion_bracket as drawing
import build_pinion_bracket as bracket
from _buildgraph import module_deps_of
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-bracket_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_bracket"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert bracket.DRAWING_DIMENSIONS is pinion_bracket_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_bracket_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.C2C, drawing.OVERALL_LENGTH, drawing.R_END) == (
        pinion_bracket_spec.C2C,
        pinion_bracket_spec.OVERALL_LENGTH,
        pinion_bracket_spec.R_END,
    )
    assert pinion_bracket_spec.C2C == pinion_bracket_geometry.C2C


def test_drive_train_recipe_depends_on_geometry_not_drawing_notes() -> None:
    drive_train = Path(__file__).with_name("build_drive_train_assembly.py")
    dependency_names = {Path(path).name for path in module_deps_of(drive_train)}
    assert "pinion_bracket_geometry.py" in dependency_names
    assert "build_pinion_bracket.py" not in dependency_names
    assert "pinion_bracket_spec.py" not in dependency_names


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert pinion_bracket_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_and_callouts_fully_define_functional_limits() -> None:
    notes = pinion_bracket_spec.DRAWING_NOTES
    assert "3.00 MIN" not in notes
    assert "GO PIN" not in notes
    assert "CLAMPED FACE-TO-FACE" in notes
    assert "2X OPEN R6.90 SCALLOPS" in notes
    assert "SILVER-BRAZE" in notes
    assert model_toleranced_dimensions(bracket) == {
        ("StrapProfile", "ArborBoreCz"): "ARBOR_BORE_CZ_TOLERANCE_MM",
        ("StrapProfile", "PivotBoreDia"): "*deviations(PIVOT_BORE_BAND)",
        ("StrapProfile", "ArborBoreDia"): "*deviations(ARBOR_BORE_BAND)",
        ("Strap", "Depth"): "THICKNESS_TOLERANCE_MM",
        ("PinSeatProfile", "PinSeatCy"): "PIN_SEAT_AXIS_TOLERANCE_MM",
        ("PinSeatProfile", "PinSeatDia"): "*deviations(PIN_SEAT_DIA_BAND)",
        ("PinSeatProfile", "PinSeatCz"): "PIN_SEAT_CZ_TOLERANCE_MM",
        ("PinSeat", "PinSeatDepth"): "*deviations(PIN_SEAT_DEPTH_BAND)",
    }
    assert "1/4 IN" not in drawing.DIMENSION_CALLOUTS["PivotBoreDia"]
    assert "5/16" not in drawing.DIMENSION_CALLOUTS["ArborBoreDia"]
    assert "+/-" not in "\n".join(drawing.DIMENSION_CALLOUTS.values())
    assert "THRU - REAM" in drawing.DIMENSION_CALLOUTS["ArborBoreDia"]
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert " BA " not in f" {notes} "
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert "THRU - REAM" in callouts["PivotBoreDia"]
    assert "THRU" in callouts["ArborBoreDia"]
    assert "FLAT BOTTOM" in callouts["PinSeatDia"]
    assert "FULL-DIAMETER DEPTH" in callouts["PinSeatDepth"]
    assert "ENTRY ON THE STRAIGHT EDGE FACE" in callouts["PinSeatDia"]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"PinSeatDepth"' in source


def test_blind_seat_depth_uses_the_marked_drawing_name() -> None:
    source = Path(bracket.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "PinSeat", ["PinSeatDepth"])' in source


def test_cam_scallops_cover_both_linkage_extremes() -> None:
    assert pinion_bracket_geometry.CAM_RELIEF_RADIUS == 6.90
    assert pinion_bracket_geometry.CAM_RELIEF_MIN_PIVOT_LIGAMENT >= 2.5
    source = Path(bracket.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, f"CamRelief{label}")' in source
    assert "_cam_relief_area(centers)" in source


def test_datum_scheme_fully_defines_functional_relationships() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 2
    assert (
        "        edge_xy=pivot_bore_edge,\n"
        "        symbol_xy=(pivot_bore_edge[0] + 0.026, pivot_bore_edge[1] - 0.009),\n"
        '        datum="A",\n'
        '        label="pivot bore axis",\n'
        "        position_tolerance_m=0.013," in source
    )
    assert source.count("position_tolerance_m=0.013") == 1
    assert (
        "        edge_xy=arbor_bore_edge,\n"
        "        symbol_xy=(arbor_bore_edge[0] + 0.020, arbor_bore_edge[1] + 0.017),\n"
        '        datum="B",\n'
        '        label="arbor bore axis",\n'
        "        position_tolerance_m=0.006," in source
    )
    assert source.count("position_tolerance_m=0.006") == 1
    assert source.count('characteristic="profile_surface"') == 2
    assert 'datums=("A",)' in source
    assert 'datums=("B",)' in source
    assert "add_surface_finish(" not in source
    assert "ArborBoreCz" not in drawing.DIMENSION_CALLOUTS
    assert drawing.DIMENSION_CALLOUTS["PinSeatCz"] == "FROM DATUM C"
    assert "CONCENTRIC" not in pinion_bracket_spec.DRAWING_NOTES
    assert "TIR" not in pinion_bracket_spec.DRAWING_NOTES


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(bracket.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-bracket")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 2  # the book uses two swing brackets


def test_part_notes_do_not_duplicate_template_edge_break_instruction() -> None:
    assert "REMOVE BURRS" not in pinion_bracket_spec.DRAWING_NOTES
