"""Offline contracts for the fulcrum-keeper drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_fulcrum_keeper as part
import draw_fulcrum_keeper as drawing
import fulcrum_keeper_spec
import _config
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import deviations


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/fulcrum-keeper.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/fulcrum-keeper.pdf")
    assert drawing.PNG.as_posix().endswith("/png/fulcrum-keeper_drawing.png")
    assert DRAWINGS_BY_NAME["fulcrum_keeper"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and all drawing-side keep sets
    # are the shared spec's map.
    assert part.DRAWING_DIMENSIONS is fulcrum_keeper_spec.DRAWING_DIMENSIONS
    marked = set().union(*fulcrum_keeper_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.SECTION_KEEP)
    assert kept == marked
    assert set(drawing.FRONT_CALLOUTS) <= set(drawing.FRONT_KEEP)
    assert set(drawing.SECTION_CALLOUTS) <= set(drawing.SECTION_KEEP)
    assert set(drawing.SECTION_PRECISION) <= set(drawing.SECTION_KEEP)


def test_geometry_matches_the_top_frame_contract() -> None:
    # The keeper exists to hold the fulcrum shaft 25.2 above the rail top
    # face (1061.4 - 1036.2, the 2026-08-02 rederive contract); its underside
    # relief must clear the 4.5-proud corner-boss land.
    assert fulcrum_keeper_spec.SHAFT_AXIS_H == 25.2
    assert fulcrum_keeper_spec.RELIEF_H > 4.5
    # The Ø6.35 shaft end must float in the ball bore with real clearance.
    assert fulcrum_keeper_spec.BORE_DIA > 6.35
    assert fulcrum_keeper_spec.BALL_DIA > fulcrum_keeper_spec.BORE_DIA
    # The reamed bore takes the ball's poles: the proud extreme is the
    # bore/sphere circle, and the overall runs to it.
    assert math.isclose(fulcrum_keeper_spec.BALL_EDGE_X, math.sqrt(4.75**2 - 3.25**2))
    assert math.isclose(
        fulcrum_keeper_spec.OVERALL_LEN,
        fulcrum_keeper_spec.FOOT_REACH + fulcrum_keeper_spec.BALL_EDGE_X,
    )
    assert fulcrum_keeper_spec.OVERALL_LEN < fulcrum_keeper_spec.FOOT_REACH + 4.75


def test_screw_hole_seats_the_frame_side_screw() -> None:
    # The foot screw is the MHA-117 #10-24 slotted cheese head (Ø7 x 3): the
    # counterbore must swallow the head, the drill must clear the #10 major.
    assert fulcrum_keeper_spec.CBORE_DIA_MM > 7.0
    assert fulcrum_keeper_spec.CBORE_DEPTH_MM >= 3.0
    assert fulcrum_keeper_spec.HOLE_DIA_MM > 4.826
    assert fulcrum_keeper_spec.HOLE_FROM_PAD_END == 8.25
    assert fulcrum_keeper_spec.HOLE_FROM_SIDE == 7.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"counterbore_fillister"' in source
    assert 'name="FootScrewHole"' in source


def test_sheet_runs_at_2_to_1_with_axial_section_and_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = _source()
    assert "scale=(2, 1)" in source
    assert "scale=(1, 1)" in source
    assert source.count("create_section_view(") == 1
    assert 'section_label="A"' in source
    assert 'label="lug axial section"' in source
    assert fulcrum_keeper_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "add_native_hole_callout(" in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3: a screwed-down bracket is not on
    # the allowlist, so the datum-B edge resolver went with the datums.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "_visible_outboard_lug_edge(",
        "visible_view_entities(",
    ):
        assert helper not in source, helper
    assert not hasattr(fulcrum_keeper_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(fulcrum_keeper_spec, "GEOMETRIC_CONTROLS")


def test_counterbore_callout_separates_the_two_operations() -> None:
    # The wizard counterbore is flat-bottomed; the semicolon binds DRILL THRU
    # only to the Ø5.105 hole and names the recess as a counterbore.
    assert (
        'process="#7 DRILL THRU; FLAT-BOTTOM COUNTERBORE"' in _source()
    )
    assert fulcrum_keeper_spec.HOLE_DIA_MM == 5.105


def test_lug_bores_carry_model_bands_and_live_on_the_axial_section() -> None:
    # The ball seat is a press band (the ball cannot be a clearance fit), the
    # shaft bore a reamed H7 band; both print three decimals from the model
    # dimension on section A-A, never against hidden end-view circles.
    assert fulcrum_keeper_spec.SOCKET_DIA_BAND == (-0.010, -0.025)
    assert fulcrum_keeper_spec.BORE_DIA_BAND == (0.015, 0.000)
    assert deviations(fulcrum_keeper_spec.SOCKET_DIA_BAND) == (-0.025, -0.010)
    assert deviations(fulcrum_keeper_spec.BORE_DIA_BAND) == (0.000, 0.015)
    assert model_toleranced_dimensions(part) == {
        ("SocketProfile", "SocketDia"): "*deviations(SOCKET_DIA_BAND)",
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
    }
    assert "SocketDia" in fulcrum_keeper_spec.DRAWING_DIMENSIONS["SocketProfile"]
    assert "BoreDia" in fulcrum_keeper_spec.DRAWING_DIMENSIONS["BoreProfile"]
    assert drawing.SECTION_PRECISION == {"SocketDia": 3, "BoreDia": 3}
    assert drawing.SECTION_CALLOUTS["BoreDia"] == "REAM THRU"
    assert drawing.SECTION_CALLOUTS["SocketDia"] == "BALL SEAT"
    assert drawing.RIGHT_DIAMETER_LEADERS_TO_RIM == ("CrownDia",)
    assert drawing.SECTION_DIAMETER_LEADERS_TO_RIM == ("SocketDia", "BoreDia")
    source = _source()
    assert "set_dimension_precision(adapter, section_annotations, SECTION_PRECISION)" in source
    assert source.count("_leaders_to_circumference(") == 3  # def + two calls
    assert "_BROKEN_LEADER_HORIZONTAL = 2" in source
    assert "SetBrokenLeader2(False, _BROKEN_LEADER_HORIZONTAL)" in source
    assert "broken_horizontal=True" in source


def test_every_number_is_on_a_view() -> None:
    # Side view: pad height, lug thickness, (REF) overall to the ball's proud
    # edge, the native relief height and a TO BALL C/L callout on the 23.00.
    # Plan: the screw hole located from the pad end and a side face.  Section
    # A-A: the ball sequence flagged from the visible seat cut edge.
    source = _source()
    assert source.count("add_edge_dimension(") == 5
    for label in (
        "pad height",
        "lug thickness",
        "overall length",
        "screw hole from pad end",
        "screw hole from side face",
    ):
        assert f'label="{label}"' in source, label
    assert source.count("set_reference_dimension(") == 1
    assert source.count("set_arc_endpoints_to_center(") == 2
    assert "p1=_front_xy(BALL_EDGE_X, SHAFT_AXIS_H)" in source
    assert drawing.FRONT_CALLOUTS == {"FootReach": "TO BALL C/L"}
    assert source.count("_add_ball_midplane_centerline(") == 2  # def + call
    assert "CreateCenterLine(x, y0, 0.0, x, y1, 0.0)" in source
    assert "ReliefRise" in fulcrum_keeper_spec.DRAWING_DIMENSIONS["FootProfile"]
    assert source.count("add_attached_note(") == 1
    assert "section,\n        text=BALL_CALLOUT" in source
    assert 'label="sectioned ball seat"' in source
    assert f"PRESS Ø{fulcrum_keeper_spec.BALL_DIA:.3f}" in (
        fulcrum_keeper_spec.BALL_CALLOUT
    )
    # The process flag is wrapped into the clear lane left of section A-A.
    # Its seven rows finish above the title block instead of overprinting it.
    assert len(fulcrum_keeper_spec.BALL_CALLOUT.splitlines()) == 7
    assert max(map(len, fulcrum_keeper_spec.BALL_CALLOUT.splitlines())) <= 20
    assert drawing.BALL_NOTE_XY[0] < drawing.SECTION_CENTER[0] - 0.08
    assert drawing.BALL_NOTE_XY[1] >= 0.110
    # Text placement: the profile stack below the view, each row centred on
    # its span, the shorter nearer; the overall lowest, above the notes.
    assert drawing.FRONT_KEEP["PadLen"][1] > drawing.FRONT_KEEP["FootReach"][1]
    assert drawing.FRONT_KEEP["FootReach"][1] > drawing.OVERALL_TEXT_XY[1] > 0.050
    assert math.isclose(drawing.FRONT_KEEP["PadLen"][0], drawing._front_x(-14.75))
    # The Ø14 crown text sits right of the lug, off the 14.00 width's line.
    assert drawing.RIGHT_KEEP["CrownDia"][0] > drawing.RIGHT_CENTER[0] + 0.02
    assert drawing.RIGHT_KEEP["CrownDia"][1] < drawing.RIGHT_KEEP["Depth"][1]
    # The hole callout left the left-hand field the 7.00 location now uses.
    assert drawing.HOLE_CALLOUT_XY[0] > drawing.HOLE_CALLOUT_RIM_XY[0]
    assert drawing.HOLE_SIDE_TEXT_XY[0] < drawing._front_x(-23.0)


def test_lug_sequence_is_flagged_and_remote_note_is_only_the_mating_contract() -> None:
    callout = fulcrum_keeper_spec.BALL_CALLOUT
    lines = callout.splitlines()
    assert len(lines) == 7
    assert "BORE BALL SEAT THRU" in lines[0]
    assert "SHAFT AXIS" in lines[1]
    assert f"Ø{fulcrum_keeper_spec.BALL_DIA:.3f}" in lines[2]
    assert "PRESS" in lines[2]
    assert "HARDENED STEEL BALL" in lines[3]
    assert "CENTRED" in lines[4]
    assert "REAM SHAFT BORE THRU" in lines[5]
    assert "AFTER PRESSING" in lines[6]
    assert "BLACK OXIDE" not in callout
    assert max(len(line) for line in lines) <= 20

    # The allowed MATES WITH note is the only remote prose; every operation
    # and every manufacturing number remains attached to a view.
    notes = fulcrum_keeper_spec.DRAWING_NOTES
    assert notes == "MATES WITH FULCRUM SHAFT."
    assert not any(character.isdigit() for character in notes)
    for banned in (
        "25.20", "AISI", "1018", "2 REQUIRED", "MHA-", "CORNER-BOSS", "FLIPPED",
        "UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "DATUM", "BASIC", "WITHIN",
    ):
        assert banned not in notes, banned


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top, right, section):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_ball_is_a_separate_pressed_body() -> None:
    # A merged Ø9.5 sphere in the Ø9.5 socket is a zero-thickness tangent
    # boolean (equator-circle contact only) -- the ball must stay its own
    # solid body, like the pinion-handle cross rod.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "merge_result=False" in source
    assert 'name_last_feature(adapter, "Ball")' in source
    # And the wizard screw hole must land while the part is one body (its
    # placement-face scan reads GetBodies2()[0]).
    assert source.index('name="FootScrewHole"') < source.index('"revolve ball"')


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "FootScrewHole" not in part.DRAWING_DIMENSIONS
    marked = set().union(*part.DRAWING_DIMENSIONS.values())
    assert not {name for name in marked if "Hole" in name}


def test_parts_registry_row() -> None:
    config = _config.parts("fulcrum-keeper")
    assert config["number"] == "MHA-120"
    assert config["material"] == "Plain Carbon Steel"
    assert "black oxide" in str(config["finish"])
    assert int(config["quantity"]) == 2
