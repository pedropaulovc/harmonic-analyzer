"""Offline contracts for the pinion-return-leaf-spring drawing.

A formed brass leaf is not on the GD&T allowlist
(cad/docs/drawing-simplicity-policy.md): the print carries no datums, frames,
roughness symbols or explicit bands, and its note is the one form fact the
views cannot show.
"""

from __future__ import annotations

import math
from pathlib import Path

import pinion_spring_spec
import draw_pinion_spring as drawing
import build_pinion_spring as spring
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-spring.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-spring.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-spring_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_spring"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert spring.DRAWING_DIMENSIONS is pinion_spring_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_spring_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The build re-imports its primitive nominals from the spec.
    assert (spring.FOOT_LEN, spring.THICK, spring.WIDTH) == (
        pinion_spring_spec.FOOT_LEN,
        pinion_spring_spec.THICK,
        pinion_spring_spec.WIDTH,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.TOP_CENTER[0] >= 0.250
    assert drawing.TOP_CENTER[1] >= 0.090
    source = _source()
    assert "scale=(1, 1)" in source  # the isometric override
    assert pinion_spring_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert drawing.FRONT_BBOX_CX < 0.0
    assert "FORMED PROFILE - FRONT VIEW SCALE 2:1" in source
    assert "TOP VIEW - LOOKING AT SCREW-DOWN FOOT BROAD FACE - SCALE 2:1" in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_notes_are_the_strip_form_fact_and_never_a_tolerance() -> None:
    # It is a bent strip, not a coil: the note is the stock and the inside-
    # surface convention; the blade and the hole are view dimensions now.
    notes = pinion_spring_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert f"FORM FROM {pinion_spring_spec.THICK:.2f} X {pinion_spring_spec.WIDTH:.2f} STRIP" in notes
    assert "INSIDE SURFACE" in notes
    assert "BLADE STRAIGHT" not in notes
    assert "FROM THE FREE END" not in notes
    assert f"{pinion_spring_spec.BLADE_STRAIGHT_LEN:.2f}" not in notes
    assert f"{pinion_spring_spec.HOLE_FROM_END:.2f}" not in notes
    assert "COIL" not in notes
    for banned in ("+/-", "LINEAR", "X.XX", "DATUM", "FLATNESS", "DRILL", "PER NATIVE"):
        assert banned not in notes, banned
    assert " BA " not in f" {notes} "
    assert max(len(line) for line in lines) <= 60
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_terminal_is_flagged_from_the_view_without_a_band() -> None:
    callout = pinion_spring_spec.TERMINAL_CALLOUT
    terminal_angle = (
        90.0 - pinion_spring_spec.BLADE_TILT_DEG + pinion_spring_spec.KINK_DEG
    )
    assert f"{pinion_spring_spec.FLAT_LEN:.2f} TERMINAL" in callout
    assert f"{terminal_angle:.2f} DEG CCW FROM FOOT INSIDE PATH" in callout
    assert "+/-" not in callout
    source = _source()
    assert source.count("add_attached_note(") == 1
    assert 'label="spring short terminal inside edge"' in source
    assert "INSIDE RADIUS" in drawing.DIMENSION_CALLOUTS["BendR"]
    assert "INSIDE RADIUS" in drawing.DIMENSION_CALLOUTS["KinkR"]
    assert "+/-" not in "\n".join(drawing.DIMENSION_CALLOUTS.values())
    assert abs(spring._BLADE_LEN - pinion_spring_spec.BLADE_STRAIGHT_LEN) < 1e-9


def test_blade_and_hole_are_dimensioned_on_the_views() -> None:
    # Machinist review 2026-09-02: the 26.36 straight length and the blade
    # angle sit on the front view (tangent-point VERTICES; the interior angle
    # between the foot and blade path EDGES), the 3.10 / 2.00 hole location
    # on the top view (rim picks re-anchored at the hole centre).
    source = _source()
    assert source.count("add_edge_dimension(") == 4
    for label in (
        "blade straight length",
        "foot to blade angle",
        "foot hole from free end",
        "foot hole from side face",
    ):
        assert f'label="{label}"' in source, label
    assert 'entity_types=("VERTEX", "VERTEX")' in source
    assert "p0=_front_xy(*BEND_EXIT)" in source
    assert "p1=_front_xy(*KINK_START)" in source
    assert source.count("set_arc_endpoints_to_center(") == 2
    assert math.isclose(pinion_spring_spec.FOOT_TO_BLADE_INTERIOR_DEG, 98.138574451932667)
    # The angle text sits inside the L (above the foot, west of the blade);
    # the blade length east of the blade.
    assert drawing.BLADE_ANGLE_TEXT_XY[0] < drawing.BLADE_PICK_XY[0]
    assert drawing.BLADE_ANGLE_TEXT_XY[1] > drawing.FOOT_PICK_XY[1]
    assert drawing.BLADE_LENGTH_TEXT_XY[0] > drawing.BLADE_PICK_XY[0]
    # Hole location: the rim picks straddle the hole, the 3.10 above the
    # strip, the 2.00 left of the free end, the callout below-right.
    assert drawing.HOLE_END_RIM_XY[0] < drawing.HOLE_SIDE_RIM_XY[0]
    assert drawing.HOLE_END_TEXT_XY[1] > drawing.HOLE_SIDE_PICK_XY[1]
    assert drawing.HOLE_SIDE_TEXT_XY[0] < drawing.HOLE_END_PICK_XY[0]
    assert drawing.HOLE_CALLOUT_XY[0] > drawing.HOLE_SIDE_RIM_XY[0]
    assert drawing.HOLE_CALLOUT_XY[1] < drawing.TOP_CENTER[1]
    assert drawing.HOLE_CALLOUT_XY[1] > drawing.TOP_LABEL_XY[1] + 0.012


def test_radius_leaders_stay_clear_of_the_foot() -> None:
    # An imported radius leader runs on the ray from the text to the arc
    # centre: the R2 text sits below-right of the bend on a ray through the
    # arc's -90..-8 degree span (the old far-left text ran its leader through
    # the foot and the 28.00's extension line); the R1.5 text above-left.
    bend_centre = (spring.BEND_CX, spring.BEND_CY)
    text = drawing.FRONT_KEEP["BendR"]
    centre = drawing._front_xy(*bend_centre)
    angle = math.degrees(math.atan2(text[1] - centre[1], text[0] - centre[0]))
    assert -90.0 < angle < -8.0
    assert text[0] > drawing._front_x(spring.FOOT_TAN[0]) + 0.010
    assert drawing.FRONT_KEEP["KinkR"][0] < drawing._front_x(spring.KINK_C[0])
    assert drawing.FRONT_KEEP["KinkR"][1] > drawing._front_y(spring.KINK_C[1])


def test_hole_callout_states_the_process() -> None:
    source = _source()
    assert source.count("add_native_hole_callout(") == 1
    assert 'process="DRILL"' in source


def test_print_carries_no_gdt_finish_or_explicit_bands() -> None:
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
    assert not hasattr(pinion_spring_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pinion_spring_spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(pinion_spring_spec, "SURFACE_FINISHES")
    # The +/-0.1 on the foot length and both radii was over-specification
    # for a hand-formed strip: the title block's two-place tolerance governs.
    for name in (
        "FOOT_LENGTH_TOLERANCE_MM",
        "BEND_RADIUS_TOLERANCE_MM",
        "KINK_RADIUS_TOLERANCE_MM",
    ):
        assert not hasattr(pinion_spring_spec, name), name
    assert model_toleranced_dimensions(spring) == {}


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-spring")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
