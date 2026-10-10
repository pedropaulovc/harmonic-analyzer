"""Offline contracts for the fulcrum-keeper drawing."""

from __future__ import annotations

from pathlib import Path

import build_ch_fulcrum_keeper as part
import draw_ch_fulcrum_keeper as drawing
import ch_fulcrum_keeper_spec
import _config
from _drawing_registry import DRAWINGS_BY_NAME
from vn_frame_side_screw_spec import HEAD_H as FRAME_SIDE_HEAD_H


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-fulcrum-keeper.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-fulcrum-keeper.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-fulcrum-keeper_drawing.png")
    assert DRAWINGS_BY_NAME["ch_fulcrum_keeper"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set
    # are BOTH the shared spec's map.
    assert part.DRAWING_DIMENSIONS is ch_fulcrum_keeper_spec.DRAWING_DIMENSIONS
    marked = set().union(*ch_fulcrum_keeper_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_geometry_matches_the_top_frame_contract() -> None:
    # The keeper exists to hold the fulcrum shaft 25.2 above the rail top
    # face (1061.4 - 1036.2, the 2026-08-02 rederive contract) on a flat
    # seat: a 6.0 lug with a straight foot running OUTBOARD to x = 13.5.
    spec = ch_fulcrum_keeper_spec
    assert spec.SHAFT_AXIS_H == 25.2
    assert spec.CROWN_DIA == spec.KEEPER_WIDTH == 14.0
    assert 2.0 * spec.LUG_HALF_T == 6.0
    assert spec.FOOT_TIP_X == spec.LUG_HALF_T + spec.FOOT_L == 13.5
    assert spec.SCREW_X == 8.25
    assert spec.KEEPER_SCREW_Z_OFF == spec.KEEPER_Z_OFF + spec.SCREW_X == 82.25
    # Plain reamed bore on the plain Ø6.35 shaft: a running band, cut by one
    # made-to-order 0.2514 in reamer through both keepers at their installed
    # spacing, that covers the faced rail seats' flatness (ch_fulcrum_shaft_spec).
    assert spec.BORE_DIA == 6.35
    assert spec.BORE_DIA_BAND == (0.050, 0.035)  # (upper, lower)
    assert spec.BORE_PAIR_CALLOUT.startswith("DRILL AND REAM IN ONE PASS WITH THE")
    assert "AT ITS INSTALLED\nSPACING, FEET ON ONE FLAT" in spec.BORE_PAIR_CALLOUT


def test_crown_set_screw_tap_stops_at_the_bore() -> None:
    spec = ch_fulcrum_keeper_spec
    assert spec.SET_SCREW_THREAD == "#1-72"
    assert spec.SET_SCREW_HOLE_SPEC.kind == "tapped"
    assert spec.SET_SCREW_HOLE_SPEC.end == "through_next"
    assert spec.CROWN_TOP_Y == spec.SHAFT_AXIS_H + spec.CROWN_DIA / 2.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="SetScrewTap"' in source
    # through_next stops at the bore only if the bore is already cut.
    assert source.index('"cut bore"') < source.index('name="SetScrewTap"')


def test_rule_12_worst_case_walls_and_thread() -> None:
    # Worst case of the printed bands (policy rule 12): >= 1.5D of full
    # crown thread and of foot-screw engagement in the frame, >= 1.5 web from
    # the crown thread major to each lug face and from the foot counterbore
    # to the foot tip and sides.
    spec = ch_fulcrum_keeper_spec
    assert spec.SET_SCREW_ENGAGEMENT_D >= 1.5
    assert spec.FOOT_SCREW_ENGAGEMENT_D >= 1.5
    assert spec.SET_SCREW_WEB_MM >= 1.5
    assert spec.FOOT_TIP_WALL_MM >= 1.5
    assert spec.FOOT_SIDE_WALL_MM >= 1.5
    assert round(spec.SET_SCREW_WEB_MM, 3) == 1.813
    assert round(spec.FOOT_TIP_WALL_MM, 3) == 2.37
    assert round(spec.FOOT_SCREW_ENGAGEMENT_D, 2) == 1.79
    # The native counterbore callout prints the template's .XX; the engagement
    # and bottoming stacks take that printed depth (2.11), not 2.1082.
    assert spec.FOOT_COUNTERBORE_DEPTH_PLACES == 2
    # The web is only met with the lug and tap station at three places.
    assert spec.DRAWING_PRECISION["LugBody"]["LugThickness"] == 3
    assert spec.DRAWING_PRECISION["SetScrewReference"]["SetScrewLocation"] == 3
    # GPT review F4 / ruling (d): plain .XXX coordinate dims locate the foot
    # hole; the frame's transferred tap takes the side-station band.
    assert spec.DRAWING_PRECISION["FootScrewReference"]["ScrewFromLug"] == 3
    assert spec.DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"] == 3
    assert spec.KEEPER_SCREW_TRANSVERSE_BAND_MM == spec._BAND_BY_PLACES[3]


def test_tap_and_foot_hole_station_reference_sketches() -> None:
    spec = ch_fulcrum_keeper_spec
    assert part.REFERENCE_SKETCHES == spec.REFERENCE_SKETCHES
    assert [row[0] for row in part.REFERENCE_LINES] == [
        "SetScrewReference",
        "FootScrewReference",
        "FootScrewSideReference",
    ]
    rows = {row[0]: row for row in part.REFERENCE_LINES}
    _, plane, dimension, start, end, _, value, _ = rows["SetScrewReference"]
    assert (plane, dimension) == ("Front", "SetScrewLocation")
    # From the outer lug face to the tap axis, on the crown top.
    assert start == (spec.LUG_HALF_T, spec.CROWN_TOP_Y)
    assert end == (0.0, spec.CROWN_TOP_Y)
    assert value == spec.LUG_HALF_T
    _, plane, dimension, start, end, _, value, _ = rows["FootScrewReference"]
    assert (plane, dimension) == ("Top", "ScrewFromLug")
    assert start == (spec.LUG_HALF_T, 0.0) and end == (spec.SCREW_X, 0.0)
    assert value == spec.SCREW_X - spec.LUG_HALF_T
    _, plane, dimension, start, end, _, value, _ = rows["FootScrewSideReference"]
    assert (plane, dimension) == ("Top", "ScrewFromSide")
    # One keeper part: the foot hole on the width centreline.
    assert start == (spec.SCREW_X, 0.0)
    assert end == (spec.SCREW_X, spec.KEEPER_WIDTH / 2.0)
    assert value == spec.KEEPER_WIDTH / 2.0


def test_keeper_tap_spec_for_the_frame() -> None:
    spec = ch_fulcrum_keeper_spec
    tap = spec.KEEPER_TAP_SPEC
    assert (tap.kind, tap.size, tap.end) == ("tapped", "#2-56", "blind")
    assert tap.size == spec.FOOT_SCREW_THREAD
    assert tap.overrides_mm["ThreadDepth"] == spec.KEEPER_TAP_THREAD_DEPTH_MM == 7.6
    assert tap.depth_mm == 11.5


def test_fitup_exports_for_the_top_frame() -> None:
    # The pair is set by DRO (MHA-CH-000 STEP 9): X off the rail web under
    # each lug, Z off the front socket line; the frame taps are transferred.
    spec = ch_fulcrum_keeper_spec
    assert spec.KEEPER_FITUP_LOCATION_BAND_MM == 0.02
    assert spec.KEEPER_FITUP_PLACES == 2
    assert spec.KEEPER_FITUP_X_FROM_WEB_MM == 2.9
    front, rear = spec.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    assert (round(front, 2), round(rear, 2)) == (40.5, 182.5)
    assert rear - front == 2.0 * (spec.KEEPER_Z_OFF - spec.LUG_HALF_T)


def test_print_carries_no_datums_or_frames_and_cites_the_fitup_steps() -> None:
    # Policy: brackets carry no GD&T; the bore pair's coaxiality is a named
    # step (F5) and the set-screw lock is a staked mouth (F6).
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature" not in source
    assert "add_feature_control_frame" not in source
    assert not hasattr(ch_fulcrum_keeper_spec, "GEOMETRIC_TOLERANCES_MM")
    assert drawing.DIMENSION_CALLOUTS["BoreDia"].endswith("PER MHA-CH-000 STEP 8")
    assert drawing.DIMENSION_CALLOUTS["CrownDia"].endswith("PER MHA-CH-000 STEP 8")
    assert "STAKE MOUTH 2 PLACES" in drawing.SET_SCREW_PROCESS
    assert "MHA-CH-000 STEP 10" in drawing.SET_SCREW_PROCESS


def test_screw_hole_seats_the_frame_side_screw() -> None:
    hole = ch_fulcrum_keeper_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is hole
    assert hole.kind == "counterbore_fillister"
    assert hole.size == "#2"
    assert hole.overrides_mm == {
        "HoleDiameter": ch_fulcrum_keeper_spec.HOLE_DIA_MM,
        "CounterBoreDiameter": ch_fulcrum_keeper_spec.CBORE_DIA_MM,
        "CounterBoreDepth": ch_fulcrum_keeper_spec.CBORE_DEPTH_MM,
    }
    assert ch_fulcrum_keeper_spec.HOLE_DIA_MM > part.FRAME_SIDE_SHANK_DIA
    assert ch_fulcrum_keeper_spec.CBORE_DIA_MM > part.FRAME_SIDE_HEAD_DIA
    assert ch_fulcrum_keeper_spec.CBORE_DEPTH_MM == FRAME_SIDE_HEAD_H
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="FootScrewHole"' in source


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source
    assert "scale=(1, 1)" in source
    assert ch_fulcrum_keeper_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "add_native_hole_callout(" in source


def test_notes_cover_the_finish_the_tap_and_the_screw() -> None:
    notes = ch_fulcrum_keeper_spec.DRAWING_NOTES
    assert "BLACK OXIDE" in notes
    # The pair ream is on the bore callout (STEP 8), not a note.
    assert "REAM" not in notes
    assert "MHA-CH-004" in notes
    assert "MHA-VN-055" in notes
    assert "MHA-VN-022 #2-56 FILLISTER" in notes
    assert "2 REQUIRED" in notes
    assert len(notes.splitlines()) <= 6


def test_keeper_is_one_body_with_no_ball() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "merge_result=False" not in source
    assert "Ball" not in source
    assert not hasattr(ch_fulcrum_keeper_spec, "BALL_DIA")


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "FootScrewHole" not in part.DRAWING_DIMENSIONS
    marked = set().union(*part.DRAWING_DIMENSIONS.values())
    assert not {name for name in marked if "Hole" in name}


def test_parts_registry_row() -> None:
    config = _config.parts("ch-fulcrum-keeper")
    assert config["number"] == "MHA-CH-007"
    assert config["material"] == "Plain Carbon Steel"
    assert "black oxide" in str(config["finish"])
    assert int(config["quantity"]) == 2
