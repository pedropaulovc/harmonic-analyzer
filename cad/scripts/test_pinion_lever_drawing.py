"""Offline contracts for the pinion-engage-lever drawing.

A lever that turns with its rod is not on the GD&T allowlist
(cad/docs/drawing-simplicity-policy.md): no datums, frames or roughness
symbols; the bore band rides the model bore, the blind bore is opened by
SECTION A-A (never a hidden line), both hub stations run from the flat end,
and the notes are two lines of process fact.
"""

from __future__ import annotations

from pathlib import Path

import pinion_lever_spec
import draw_pinion_lever as drawing
import build_pinion_lever as lever
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-lever_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_lever"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert lever.DRAWING_DIMENSIONS is pinion_lever_spec.DRAWING_DIMENSIONS
    assert lever.SURFACE_FINISHES is pinion_lever_spec.SURFACE_FINISHES
    marked = set().union(*pinion_lever_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.SECTION_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.HUB_OD, drawing.ROD_LEN, drawing.HUB_LEN) == (
        pinion_lever_spec.HUB_OD,
        pinion_lever_spec.ROD_LEN,
        pinion_lever_spec.HUB_LEN,
    )
    # The blind bore, the end wall and the crown height are section sizes;
    # the crown radius stays on the top view.
    assert set(drawing.SECTION_KEEP) == {"BoreDepth", "EndWall", "CapSagDim"}
    assert set(drawing.TOP_KEEP) == {"CapR"}


def test_sheet_runs_at_1_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    assert "scale=(1, 1)" in source  # the isometric override
    assert pinion_lever_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    # SECTION A-A replaced the hidden-line side view (policy rule 7).
    assert source.count("create_section_view(") == 1
    assert 'section_label="A"' in source
    assert 'place_view(adapter, str(SOURCE), "*Right"' not in source
    # The isometric and its caption sit above the title block (top ~0.0655).
    assert drawing.ISO_CENTER[1] >= 0.120
    assert 'add_property_linked_note(adapter, "Isometric View Note", 0.320, 0.078)' in source


def test_angle_end_wall_depth_and_section_label_use_distinct_lanes() -> None:
    # The long section is shifted right of the front-view half-angle note.
    assert (
        drawing.SECTION_CENTER[0] - drawing.FRONT_KEEP["GripHalfAngle"][0]
        >= 0.100
    )
    bore_up, _ = drawing.SECTION_KEEP["BoreDepth"]
    wall_up, _ = drawing.SECTION_KEEP["EndWall"]
    crown_up, _ = drawing.SECTION_KEEP["CapSagDim"]
    # Each multi-line annotation owns a vertical lane with useful text height
    # between it and its neighbors.
    assert wall_up - bore_up >= 0.040
    assert crown_up - wall_up >= 0.015
    assert bore_up - drawing.SECTION_LABEL_OFFSET[0] >= 0.020
    assert drawing.SECTION_LABEL_OFFSET[0] <= -0.040


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, section, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pinion_lever_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # Short lines end well before the tolerance table (sheet x ~0.218).
    assert all(len(line) <= 72 for line in lines), [len(line) for line in lines]
    assert notes.isascii()
    assert "ONE SETUP" in notes
    assert "CORNER R0.15 MAX" in notes
    assert "GRIP AXIS 90 DEG TO THE BORE AXIS; AXES INTERSECT." in notes
    # Sizes live on the views; the crown-root edge takes the block edge break.
    for banned in (
        "FROM THE FLAT END",
        "SQUARE",
        "SHARP",
        "R0.10",
        "JUNCTION",
        "DATUM",
        "EXEMPT",
        "TITLE-BLOCK",
        "+/-",
        "LINEAR",
        "X.XX",
        "RELEASE HOLD",
        "AT ASSEMBLY",
        "LIFT ROD",
        "BREAK ALL",
        "SHORTEST DISTANCE",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_hub_stations_run_from_the_flat_end_on_the_top_view() -> None:
    # One origin: the hub length (flat end -> crown-root rim, both visible
    # lines) and the grip station (flat end -> tip circle, snapped to its
    # centre) are top-view edge dimensions; the crown is a size, not a note.
    source = _source()
    assert source.count("add_edge_dimension(") == 2
    assert 'label="flat end to crown root"' in source
    assert 'label="flat end to grip axis"' in source
    assert source.count("set_arc_endpoints_to_center(") == 1
    assert "add_attached_note(" not in source
    assert "add_view_centerline(" in source
    assert drawing.DIMENSION_CALLOUTS["CapR"] == "SPHERICAL CROWN"
    assert 'set_reference_dimensions(adapter, section_annotations, ["EndWall", "CapSagDim"])' in source
    assert "GRIP_HALF_ANGLE_DEG" not in source
    # Section positions are derived from the projected axes, never assumed.
    assert "_section_frame(adapter, section" in source
    assert drawing.GRIP_STATION_TEXT_XY[0] < drawing.TOP_CENTER[0] < drawing.HUB_LENGTH_TEXT_XY[0]


def test_diameter_leaders_end_at_the_circumference() -> None:
    source = _source()
    assert "_ARROWS_OUTSIDE = 1" in source
    assert source.count("_leaders_to_circumference(") >= 2  # def + call
    assert drawing.FRONT_DIAMETERS == ("HubOd", "HubBore")


def test_print_carries_no_gdt_or_finish_symbols() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert "WITHIN" not in source
    assert "FLAT WITHIN" not in source
    assert not hasattr(pinion_lever_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pinion_lever_spec, "GEOMETRIC_CONTROLS")
    assert pinion_lever_spec.SURFACE_FINISHES == ()
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        lever.__file__
    ).read_text(encoding="utf-8")


def test_bands_ride_the_model_dimensions_and_callouts_say_the_process() -> None:
    # The end wall is REFERENCE (no band); the taper half-angle keeps a
    # relaxed explicit band because the block's +/-1 deg exceeds its nominal.
    assert model_toleranced_dimensions(lever) == {
        ("BarrelProfile", "HubBore"): "*deviations(BORE_BAND)",
        ("Barrel", "BoreDepth"): "*deviations(BORE_DEPTH_BAND)",
        ("RodProfile", "RodTipY"): "ROD_TIP_Y_TOLERANCE_MM",
        ("RodProfile", "RodTipDia"): "ROD_TIP_DIAMETER_TOLERANCE_MM",
        ("RodProfile", "GripHalfAngle"): "GRIP_HALF_ANGLE_TOLERANCE_DEG",
        ("CapProfile", "CapR"): "CAP_RADIUS_TOLERANCE_MM",
    }
    assert not hasattr(pinion_lever_spec, "END_WALL_TOLERANCE_MM")
    assert 0.2 <= pinion_lever_spec.GRIP_HALF_ANGLE_TOLERANCE_DEG < 1.0
    assert pinion_lever_spec.GRIP_HALF_ANGLE_TOLERANCE_DEG < pinion_lever_spec.GRIP_HALF_ANGLE_DEG
    part_source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "await add_diametric_linear_dimension(" in part_source
    assert "await add_angular_reference_dimension(" in part_source
    assert "set_dimension_symmetric_angular_tolerance(" in part_source
    callouts = drawing.DIMENSION_CALLOUTS
    # One process for the blind bore, consistent with its flat bottom.
    assert callouts["HubBore"] == "BORE"
    assert "REAM" not in "\n".join(callouts.values())
    assert callouts["BoreDepth"] == "FULL-DIA DEPTH; FLAT BOTTOM"
    assert callouts["EndWall"] == "END WALL"
    joined = "\n".join(callouts.values())
    for banned in ("+/-", "DATUM", "FROM B", "+0.10"):
        assert banned not in joined, banned


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-lever")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 1
