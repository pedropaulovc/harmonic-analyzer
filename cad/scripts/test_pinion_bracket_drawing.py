"""Offline contracts for the pinion-swing-bracket drawing.

A swing strap is not on the GD&T allowlist
(cad/docs/drawing-simplicity-policy.md): no datums, frames, basics or
roughness symbols; the bore bands ride the model dimensions, the blind stud
seat is dimensioned on visible geometry (LEFT view + SECTION A-A), the cam
scallops are located on DETAIL B, and the notes are two lines of process fact.
"""

from __future__ import annotations

import math
from pathlib import Path

import pinion_bracket_spec
import pinion_bracket_geometry
import draw_pinion_bracket as drawing
import build_pinion_bracket as bracket
from _buildgraph import module_deps_of
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-bracket_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_bracket"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map.
    assert bracket.DRAWING_DIMENSIONS is pinion_bracket_spec.DRAWING_DIMENSIONS
    assert bracket.SURFACE_FINISHES is pinion_bracket_spec.SURFACE_FINISHES
    marked = set().union(*pinion_bracket_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.LEFT_KEEP)
        | set(drawing.SECTION_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The seat's diameter and through-thickness station are visible circles on
    # the -X flank (LEFT view); its depth and the strap thickness are section
    # edges; the seat's rise above the pivot stays on the face view.
    assert set(drawing.LEFT_KEEP) == {"PinSeatDia", "PinSeatCz"}
    assert set(drawing.SECTION_KEEP) == {"PinSeatDepth", "Depth"}
    assert "PinSeatCy" in drawing.FRONT_KEEP
    # Both end radii print; the scallops live on the detail.
    assert {"BottomCapRadius", "TopCapRadius"} <= set(drawing.FRONT_KEEP)
    assert set(drawing.DETAIL_KEEP) == {
        "CamReliefParkDia",
        "CamReliefParkX",
        "CamReliefParkY",
        "CamReliefEngagedX",
        "CamReliefEngagedY",
    }
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
    source = _source()
    assert "scale=(1, 1)" in source  # the isometric override
    assert pinion_bracket_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    # The isometric and its caption sit above the title block (top ~0.0655).
    assert drawing.ISO_CENTER[1] >= 0.100
    assert 'add_property_linked_note(adapter, "Isometric View Note", 0.345, 0.088)' in source


def test_views_follow_the_machinist() -> None:
    # Third angle: the LEFT view (the flank the seat enters) sits left of the
    # front; the section is cut on it through the seat axis; the detail is a
    # 4:1 enlargement of the scalloped flank enclosing the pivot-bore origin
    # and both scallop centres its imported dimensions reference.
    source = _source()
    assert 'place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER' in source
    assert 'place_view(adapter, str(SOURCE), "*Right"' not in source
    assert drawing.LEFT_CENTER[0] < drawing.FRONT_CENTER[0]
    assert source.count("create_section_view(") == 1
    assert 'section_label="A"' in source
    assert "seat_axis_y = _front_y(-PIN_DROP)" in source
    assert source.count("create_detail_view(") == 1
    assert 'detail_label="B"' in source
    assert drawing.DETAIL_SCALE == (4, 1)
    centre, radius = drawing.DETAIL_MODEL_CENTER, drawing.DETAIL_MODEL_RADIUS
    for point in (
        (0.0, 0.0),
        pinion_bracket_geometry.CAM_RELIEF_PARK_CENTER,
        pinion_bracket_geometry.CAM_RELIEF_ENGAGED_CENTER,
    ):
        assert math.hypot(point[0] - centre[0], point[1] - centre[1]) < radius, point
    # The scallops have not reached the flank at the seat-axis cut.
    y_cut = -pinion_bracket_geometry.PIN_DROP
    for cx, cy in (
        pinion_bracket_geometry.CAM_RELIEF_PARK_CENTER,
        pinion_bracket_geometry.CAM_RELIEF_ENGAGED_CENTER,
    ):
        reach = pinion_bracket_geometry.CAM_RELIEF_RADIUS**2 - (y_cut - cy) ** 2
        assert reach <= 0.0 or cx + math.sqrt(reach) < -pinion_bracket_geometry.R_END
    # Section positions are derived from the projected axes, never assumed.
    assert "_section_frame(adapter, section" in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (left, front, section):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pinion_bracket_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert notes.isascii()
    assert "CLAMPED FACE-TO-FACE" in notes
    # One "MATES WITH" line replaces the stud-press/braze assembly steps; the
    # scallops are dimensions on DETAIL B, not a "PER MODEL" note.
    assert "MATES WITH MHA-116" in notes
    for banned in (
        "PER MODEL",
        "SCALLOP",
        "BRAZE",
        "PRESS THE",
        "MIN WALL",
        "BASIC",
        "DATUM",
        "PROFILE",
        "INTERCHANGEABLE",
        "+/-",
        "LINEAR",
        "HOLE CENTRES",
        "X.XX",
        "REMOVE BURRS",
        "CONCENTRIC",
        "TIR",
    ):
        assert banned not in notes, banned
    assert " BA " not in f" {notes} "
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_bands_ride_the_model_dimensions_and_callouts_say_the_process() -> None:
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
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["PivotBoreDia"] == "REAM THRU"
    assert callouts["ArborBoreDia"] == "REAM THRU"
    assert callouts["PinSeatDia"] == "REAM; FLAT BOTTOM"
    assert callouts["PinSeatDepth"] == "FULL-DIAMETER DEPTH"
    assert callouts["CamReliefParkDia"] == "2X CAM SCALLOP"
    joined = "\n".join(callouts.values())
    for banned in ("H7", "+/-", "DATUM", "1/4 IN", "5/16"):
        assert banned not in joined, banned


def test_outside_profile_is_fully_defined_with_a_reference_overall() -> None:
    # Both end radii are model dimensions; the overall runs arc extreme to arc
    # extreme (REF) outboard of the controlling 28.00 bore-to-bore distance.
    source = _source()
    assert source.count("add_edge_dimension(") == 1
    assert 'label="strap overall length"' in source
    assert "set_arc_endpoints_to_max(adapter, overall" in source
    assert '_parenthesize(adapter, overall' in source
    # The overall stands alone left of the strap; the rise and bore-to-bore
    # distance stack on the right, every leader text beyond both.
    assert drawing.OVERALL_TEXT_XY[0] < drawing.FRONT_CENTER[0]
    assert drawing.FRONT_KEEP["ArborBoreCz"][0] > drawing.FRONT_KEEP["PinSeatCy"][0] > drawing.FRONT_CENTER[0]
    for name in ("ArborBoreDia", "TopCapRadius", "PivotBoreDia", "BottomCapRadius"):
        assert drawing.FRONT_KEEP[name][0] > drawing.FRONT_CENTER[0], name


def test_diameter_leaders_end_at_the_circumference() -> None:
    source = _source()
    assert "_ARROWS_OUTSIDE = 1" in source
    assert source.count("_leaders_to_circumference(") >= 4  # def + three calls
    assert drawing.FRONT_DIAMETERS == ("ArborBoreDia", "PivotBoreDia")
    assert drawing.LEFT_DIAMETERS == ("PinSeatDia",)
    assert drawing.DETAIL_DIAMETERS == ("CamReliefParkDia",)


def test_blind_seat_depth_uses_the_marked_drawing_name() -> None:
    source = Path(bracket.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "PinSeat", ["PinSeatDepth"])' in source


def test_cam_scallops_cover_both_linkage_extremes() -> None:
    assert pinion_bracket_geometry.CAM_RELIEF_RADIUS == 6.90
    assert pinion_bracket_geometry.CAM_RELIEF_MIN_PIVOT_LIGAMENT >= 2.5
    source = Path(bracket.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, f"CamRelief{label}")' in source
    assert "_cam_relief_area(centers)" in source
    # The scallop dimensions the detail imports are the build's own named
    # circle dimensions (centre X/Y to the pivot-bore origin + diameter).
    assert 'names=(f"CamRelief{label}X", f"CamRelief{label}Y", f"CamRelief{label}Dia")' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
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
    assert not hasattr(pinion_bracket_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pinion_bracket_spec, "GEOMETRIC_CONTROLS")
    # The arbor bore's Ra 1.6 was deleted (machinist review 2026-09-02): the
    # reamed running fit is a size band on the dimension; block Ra 3.2 covers it.
    assert pinion_bracket_spec.SURFACE_FINISHES == ()
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        bracket.__file__
    ).read_text(encoding="utf-8")


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
