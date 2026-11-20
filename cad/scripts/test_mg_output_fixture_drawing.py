"""Offline contracts for the output fixture (MHA-MG-06): part, sheet, pose."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

import build_mg_output_fixture as part
import draw_mg_output_fixture as drawing
import mg_output_fixture_geom as geom
import mg_output_fixture_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_audit import LayoutAuditMode, audit_dump, audit_report
from _layout_geometry import Box, Segment as AuditSegment, segment_box_distance
from _printed_tolerance import printed_band_mm

SCRIPTS = Path(geom.__file__).resolve().parent


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-output-fixture.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-output-fixture.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-output-fixture_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_output_fixture"].script
        == Path(drawing.__file__).resolve()
    )


def test_sheet_prints_exactly_the_marked_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) | set(drawing.END_KEEP) == marked
    assert not set(drawing.SIDE_KEEP) & set(drawing.END_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_no_printed_dimension_carries_its_own_band() -> None:
    # r1 review: every explicit ±0.05 was a band the part's function never
    # asked for.  The places carry the title block's band (rule 3); the
    # groove's radius is a LIMIT band (owner ruling 2026-10-17, review r4);
    # the drilled bore's band is the DRILLED HOLES row; the shoulder's inside
    # corner is the title block's INSIDE CORNERS row, unprinted.
    for retired in (
        "SYMMETRIC_BANDS", "ROD_BORE_DIA_BAND", "POSITION_TOLERANCE", "SIZE_TOLERANCE",
        "SINGLE_LIMITS",
    ):
        assert not hasattr(spec, retired), retired
    assert {
        name: places for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places != 2
    } == {"HexAf": 3, "GrooveRadius": 3, "RodBoreDia": 3}
    assert spec.LIMIT_BANDS == {
        "GrooveRadius": ("GrooveProfile", pytest.approx((-0.6858, 0.0), abs=1e-12)),
    }
    assert part.LIMIT_BANDS is spec.LIMIT_BANDS
    assert spec.UNIT == "in"
    assert printed_band_mm(2, unit=spec.UNIT) == pytest.approx(0.254)
    # The F drill (.257) over the 1/4 rod (#2404), plus the DRILLED HOLES
    # row's +.004.
    assert geom.ROD_BORE_DRILL == "F"
    assert 2.0 * spec.ROD_BORE_R_MAX == pytest.approx(0.261 * 25.4)
    # The largest 1/4 rod (+.005) still runs in the smallest bore.
    assert spec.ROD_RUNNING_CLEARANCE_MIN == pytest.approx((0.257 - 0.255) * 25.4)
    assert spec.ROD_BORE_CALLOUT == "DRILL THRU"


def test_flats_and_overall_length_print_as_unbanded_references() -> None:
    # Machinist review: the flats at .XXX asked for a size the bar is bought at.
    # r1: the overall length closed a loop with the bore's two stations.
    assert spec.REFERENCE_DIMENSIONS == {"OverallLength"}
    # The flats as bought: the exact 7/16 in, a fraction REF.
    assert spec.STOCK_REFERENCE_DIMENSION == "HexAf"
    assert spec.HEX_AF_FRACTION_DENOMINATOR == 16
    assert geom.HEX_AF * spec.HEX_AF_FRACTION_DENOMINATOR / 25.4 == pytest.approx(7.0)
    assert spec.DRAWING_DIMENSIONS["HexProfile"] == {"HexAf"}
    assert geom.OVERALL_LENGTH == pytest.approx(geom.ROD_STATION + spec.BORE_STATION)


def _machine_offset(local: tuple[float, float, float], yaw_deg: float) -> tuple[float, float]:
    """(dx, dz) of a local point under the installed Ry(180 deg + yaw)."""
    theta = math.radians(180.0 + yaw_deg)
    x, _y, z = local
    return (
        x * math.cos(theta) + z * math.sin(theta),
        -x * math.sin(theta) + z * math.cos(theta),
    )


def test_installed_hook_sits_on_the_wire_start() -> None:
    dx, dz = _machine_offset(geom.HOOK_LOCAL, geom.FIXTURE_YAW_DEG)
    assert dz == pytest.approx(geom.HOOK_TARGET_Z - geom.VROD_Z, abs=1e-9)
    assert dx == pytest.approx(geom.HOOK_OFFSET_X, abs=1e-9)
    # The wire's centre in the groove root, on the +Z side, at the groove.
    x, y, z = geom.HOOK_LOCAL
    assert x == geom.GROOVE_X and y == 0.0 and z > 0.0
    assert math.hypot(y, z) == pytest.approx(
        geom.GROOVE_ROOT_DIA / 2.0 + geom.WIRE_DIA / 2.0 + geom.WIRE_CLEARANCE
    )
    # Option A1: the hook lies in the rod's own plane (dz = 0), on the bracket
    # side, and the run heads further from the rod, so the wire clears it.
    from mg_magnifying_vertical_rod_geom import ROD_DIA
    import sh_vn_music_wire_lever_geom as wire

    assert geom.HOOK_TARGET_Z == geom.VROD_Z
    assert -geom.HOOK_OFFSET_X - ROD_DIA / 2.0 - geom.WIRE_DIA / 2.0 >= geom.WIRE_CLEARANCE
    assert wire.WIRE_END[0] < wire.WIRE_START[0]


def test_hook_point_is_authored_on_the_top_plane_where_the_geometry_puts_it() -> None:
    # Top-plane sketch (x, y) is model (X, -Z).
    x, y = part._hook_sketch_xy()
    assert (x, 0.0, -y) == geom.HOOK_LOCAL


def test_groove_runs_on_the_spigot_with_both_lips() -> None:
    low, high = geom.GROOVE_MOUTHS
    assert geom.SHOULDER_X < low < high < geom.SPIGOT_FACE_X
    assert geom.GROOVE_ROOT_DIA < geom.SPIGOT_DIA < geom.HEX_AF


def test_every_wall_holds_the_target_and_the_sheet_states_none() -> None:
    assert spec.WALL_TARGET == pytest.approx(0.080 * 25.4)
    for name, (nominal, worst) in spec.WALLS.items():
        assert worst <= nominal, name
        assert worst >= spec.WALL_TARGET, (name, worst)
    assert {name: worst for name, (_n, worst) in spec.WALLS.items()} == pytest.approx(
        {
            "rod bore to a flat": 2.0445,
            "rod bore to the free end": 2.1397,
            "rod bore to the shoulder": 2.1397,
            "groove lip to the spigot face": 2.1082,
            "groove root over the thread major": 2.1089,
        },
        abs=1e-4,
    )
    # Rule 20: only a wall under the target prints as a MIN; none is.
    for retired in (
        "STATED_WALL_MINS",
        "BORE_WALL_STATED_MIN",
        "BORE_CENTRING_ACCEPTED",
        "BORE_WALL_NOTE",
        "GROOVE_WALL_NOTE",
        "WALL_FLOOR",
        "floor_2",
    ):
        assert not hasattr(spec, retired), retired


def test_the_owner_ruling_numbers_hold() -> None:
    # #1559, 2026-10-16: semicircular groove on the spigot on 7/16 hex, the
    # hook in the plumb plane; #2403 (owner ruling 2026-11-20) moves the face
    # .010 nearer the bore, the groove held on the hook (3.496 from the
    # face).  #290: R.047 MAX, the spigot Ø the root's plus 2R.
    lip = spec.WALLS["groove lip to the spigot face"][1]
    root = spec.WALLS["groove root over the thread major"][1]
    assert lip == pytest.approx(2.1082, abs=0.005)
    assert root == pytest.approx(2.1089, abs=0.005)
    assert spec.GROOVE_DEPTH_MIN == pytest.approx(0.040 * 25.4, abs=0.005)
    assert spec.SHOULDER_ANNULUS == pytest.approx(0.51, abs=0.005)
    assert geom.FIXTURE_YAW_DEG == pytest.approx(26.69, abs=0.005)


def test_bore_is_centred_and_its_walls_take_the_drill_run_off() -> None:
    # Independent of the spec's arithmetic: the bore on the thinnest stock
    # (7/16 in less the .005 stock assumption) at its largest drilled Ø (the
    # F drill's .257 and the DRILLED HOLES +.004/0), off the hex axis by the
    # drill's run-off at the exit corner (0.10 start, 0.3 deg over the corner
    # radius): nothing locates it from a flat, so the run-off is its only
    # offset.
    assert spec.HEX_STOCK_AF_BAND == 0.127
    assert geom.HEX_AF == pytest.approx(11.1125, abs=1e-12)
    smallest_af = 7.0 / 16.0 * 25.4 - 0.127
    largest_bore_r = (0.257 + 0.004) * 25.4 / 2.0
    wander = 0.10 + geom.HEX_CORNER_RADIUS * math.tan(math.radians(0.3))
    assert spec.BORE_WANDER == pytest.approx(wander, abs=1e-12)
    assert spec.BORE_OFFSET_MAX == spec.BORE_WANDER
    worst = smallest_af / 2.0 - largest_bore_r - wander
    assert worst == pytest.approx(2.0445, abs=1e-4)
    assert spec.WALLS["rod bore to a flat"] == pytest.approx((2.29235, worst), abs=1e-9)
    # The free-end wall: one station printed .23 +/-.01, the drilled Ø, the
    # run-off.
    assert spec.WALLS["rod bore to the free end"][1] == pytest.approx(
        (0.23 - 0.01) * 25.4 - largest_bore_r - wander, abs=1e-9
    )
    # Nothing locates the bore from a flat any longer: the hex sketch centres
    # it by equal flats.
    assert not hasattr(geom, "BORE_FROM_FLAT")


def test_thumb_screw_tap_runs_axially_into_the_rod_bore() -> None:
    assert spec.TAP_SPEC is geom.TAP_SPEC
    assert geom.TAP_SPEC.kind == "tapped"
    assert geom.TAP_SPEC.size == "#4-40"
    # Blind, not up-to-next: the callout states both depths, never THRU.
    assert geom.TAP_SPEC.end == "blind"
    assert geom.TAP_SPEC.depth_mm == geom.TAP_DRILL_DEPTH == geom.SPIGOT_FACE_X
    assert geom.TAP_SPEC.overrides_mm == {"ThreadDepth": geom.TAP_LENGTH}
    # Full thread from the spigot face to where the tap's axis meets the bore.
    assert geom.TAP_LENGTH == pytest.approx(12.446 - 0.1285 * 25.4, abs=1e-9)
    assert geom.TAP_LENGTH == pytest.approx(
        geom.OVERALL_LENGTH - geom.ROD_STATION - geom.ROD_BORE_DIA / 2.0, abs=1e-9
    )
    assert geom.TAP_DRILL_DIA < geom.ROD_BORE_DIA
    # Full thread from the face to the bore, well over 1.5D.
    assert geom.TAP_LENGTH >= 1.5 * geom.THREAD_MAJOR
    # The extent row under the thread says INTO the bore; the prefix only
    # names the work.
    assert spec.TAP_PROCESS == "TAP"
    assert spec.TAP_DEPTH_PLACES == 2
    assert spec.TAP_CALLOUT_PRECISION == {
        "hw-tapdrldia": 3,
        "hw-tapdrldepth": 2,
        "hw-threaddepth": 2,
    }


def test_a_bottoming_tap_reaches_full_thread_through_the_wall_and_stops_short() -> None:
    # Morse Cutting Tools #4-40 hand tap (catalogue 552474): usable length
    # LU 9/16 in on a 0.141 in shank (over the 0.112 in major, so the shank
    # stops at the spigot face and LU is the tap's whole reach); ICS gives
    # the bottoming chamfer as 1-2 threads.
    reach = 9.0 / 16.0 * 25.4
    pitch = 25.4 / 40.0
    assert spec.TAP_USABLE_LENGTH == pytest.approx(14.2875, abs=1e-9)
    assert spec.TAP_SHANK_DIA == pytest.approx(3.5814, abs=1e-9)
    assert spec.BOTTOMING_TAP_CHAMFER_THREADS == (1, 2)
    assert spec.BOTTOMING_TAP_LEAD == pytest.approx(2.0 * pitch, abs=1e-9)
    # Face to bore axis at the printed worst case: one station, .49 +/-.01.
    face_to_axis_max, face_to_axis_min = 12.446 + 0.254, 12.446 - 0.254
    assert (spec.FACE_TO_BORE_AXIS_MAX, spec.FACE_TO_BORE_AXIS_MIN) == pytest.approx(
        (face_to_axis_max, face_to_axis_min), abs=1e-9
    )
    # The thread's widest reach off the bore axis: the library's metric basic
    # major Ø2.845, tap oversize and the bore's run-off off the hex axis.
    assert spec.THREAD_MAJOR == 2.845
    reach_off_axis = 2.845 / 2.0 + 0.0254 + spec.BORE_WANDER
    half_chord = math.sqrt((0.1285 * 25.4) ** 2 - reach_off_axis**2)
    deepest_wall = face_to_axis_max - half_chord
    assert spec.TAP_WALL_DEEPEST == pytest.approx(deepest_wall, abs=1e-9)
    assert spec.TAP_WALL_DEEPEST == pytest.approx(9.8448, abs=5e-4)
    assert spec.TAP_REACH_NEEDED == pytest.approx(deepest_wall + 2.0 * pitch, abs=1e-9)
    assert reach - spec.TAP_REACH_NEEDED == pytest.approx(3.1727, abs=5e-4)
    # On one part both walls move together: the tap stops anywhere in the
    # bore's chord less its lead.
    assert spec.FAR_WALL_NEAREST == pytest.approx(face_to_axis_min + half_chord, abs=1e-9)
    assert spec.TAP_STOP_WINDOW == pytest.approx(2.0 * half_chord - 2.0 * pitch, abs=1e-9)
    assert spec.TAP_STOP_WINDOW > 0.0
    assert spec.TAP_EXTENT_CALLOUT == "FULL THREAD TO ROD BORE"
    for retired in ("PLUG_TAP_USABLE_LENGTH", "PLUG_TAP_LEAD", "TAP_TOOL_NOTE"):
        assert not hasattr(spec, retired), retired
    # The tap drill's full Ø clears the near wall; its point stops short of
    # the far one.
    assert spec.TAP_DRILL_NEAR_CLEAR > 0.0 and spec.TAP_DRILL_FAR_CLEAR > 0.0


def test_the_bore_datum_holds_the_screw_reach_and_the_rejected_datums_fail() -> None:
    from sh_vn_thumb_screw_spec import PITCH, SHANK_DIA, SHANK_LEN
    from mg_magnifying_vertical_rod_geom import ROD_DIA_BAND

    rod_min = geom.VROD_DIA + ROD_DIA_BAND[1]
    bore_r_max = (0.257 + 0.004) * 25.4 / 2.0
    # One .XX band from the spigot face to the bore axis.
    reach = (12.446 + 0.254) + bore_r_max - rod_min
    assert spec.SCREW_REACH_NEEDED == pytest.approx(reach, abs=1e-9)
    assert spec.SCREW_REACH_NEEDED == pytest.approx(9.7917, abs=5e-3)
    assert SHANK_LEN == pytest.approx(7.0 / 16.0 * 25.4)
    assert spec.SCREW_REACH_MARGIN == pytest.approx(SHANK_LEN - reach, abs=1e-9)
    assert spec.SCREW_REACH_MARGIN > 0.0
    # #2403 (owner ruling 2026-11-20): the face .010 nearer the bore keeps
    # the reach even with the screw .030 short of its 7/16.
    assert spec.SCREW_REACH_MARGIN - 0.030 * 25.4 > 0.0
    # r1's datums: the overall length (.72) from the free end less the rod
    # station, two .XX bands to the bore: the screw has less margin.
    stacked = (0.72 + 0.01) * 25.4 - (0.23 - 0.01) * 25.4 + bore_r_max - rod_min
    assert stacked > reach
    # The bore from the face with the overall from the free end (the rod
    # station a reference) leaves the free-end wall under the target.
    free_end_wall = (0.72 - 0.01) * 25.4 - (12.446 + 0.254) - bore_r_max - spec.BORE_WANDER
    assert free_end_wall == pytest.approx(1.886, abs=1e-3)
    assert free_end_wall < spec.WALL_TARGET
    # Engagement at the shallowest bore: at least 1.5 D.
    engagement = (12.446 - 0.254) - bore_r_max - PITCH
    assert spec.ENGAGEMENT_WORST == pytest.approx(engagement, abs=1e-9)
    assert engagement >= 1.5 * SHANK_DIA


def test_the_groove_station_from_the_face_holds_the_face_lip() -> None:
    # One .XX band from the face to the groove centre (.14 printed over the
    # 3.496 model: .13 to .15), and the MAX radius.
    station_min, station_max = (0.14 - 0.01) * 25.4, (0.14 + 0.01) * 25.4
    face_lip = station_min - 0.047 * 25.4
    assert spec.GROOVE_STATION == geom.GROOVE_STATION == pytest.approx(3.496)
    assert geom.GROOVE_X == pytest.approx(geom.SPIGOT_FACE_X - 3.496)
    assert spec.WALLS["groove lip to the spigot face"][1] == pytest.approx(face_lip, abs=1e-9)
    assert face_lip >= spec.WALL_TARGET
    # The groove stays on the spigot: its shoulder-side mouth clears the hex
    # shoulder at the worst case (a step up to the hex, not a wall), and the
    # modelled corner too.  r2 review: the spigot's own length from the
    # face, one .XX band, not the hex from the free end (three bands).
    clearance = (0.25 - 0.01) * 25.4 - (station_max + 0.047 * 25.4)
    assert spec.GROOVE_SHOULDER_CLEARANCE == pytest.approx(clearance, abs=1e-9)
    assert clearance == pytest.approx(1.0922)
    assert spec.GROOVE_FILLET_CLEARANCE == pytest.approx(clearance - 0.008 * 25.4, abs=1e-9)
    # The wire stays in it at the smallest OD (.40) over the largest root (.30).
    assert spec.GROOVE_DEPTH_MIN == pytest.approx(((0.40 - 0.01) - (0.30 + 0.01)) * 25.4 / 2.0)
    assert spec.GROOVE_DEPTH_MIN > geom.WIRE_DIA / 2.0


def test_the_groove_is_a_true_semicircle_centred_on_the_spigot_od() -> None:
    # OD = root Ø + 2R: the arc's centre on the OD, so the groove is as deep
    # as its radius and opens its full Ø at the mouth.  The owner's Ø10.5
    # would bury the centre under the OD: a re-entrant groove.
    assert geom.SPIGOT_DIA == pytest.approx(
        geom.GROOVE_ROOT_DIA + 2.0 * geom.GROOVE_RADIUS
    )
    assert geom.GROOVE_CENTRE_R == pytest.approx(geom.SPIGOT_DIA / 2.0, abs=1e-12)
    assert geom.GROOVE_HALF_OPENING == pytest.approx(geom.GROOVE_RADIUS, abs=1e-12)
    assert (10.5 - geom.GROOVE_ROOT_DIA) / 2.0 > geom.GROOVE_RADIUS
    assert part.V_GROOVE == pytest.approx(
        2.0
        * math.pi
        * (geom.GROOVE_CENTRE_R - 4.0 * geom.GROOVE_RADIUS / (3.0 * math.pi))
        * math.pi
        * geom.GROOVE_RADIUS**2
        / 2.0,
        rel=1e-9,
    )


def test_the_groove_radius_is_a_limit_band_and_the_title_block_x_row_would_thin_the_face_lip() -> None:
    # Owner ruling 2026-10-17 (review r4, rule 1: a bare MAX had no
    # minimum): a native LIMIT, the model value its upper limit, so every
    # largest-radius proof still runs on the model.
    assert spec.GROOVE_RADIUS_PLACES == 3 and spec.GROOVE_RADIUS_TOL_TYPE == 3
    assert spec.GROOVE_RADIUS_MAX == geom.GROOVE_RADIUS == pytest.approx(0.047 * 25.4)
    assert spec.GROOVE_RADIUS_MIN == pytest.approx(0.020 * 25.4)
    lower, upper = spec.GROOVE_RADIUS_DEVIATIONS
    assert geom.GROOVE_RADIUS + upper == pytest.approx(0.047 * 25.4, abs=1e-12)
    assert geom.GROOVE_RADIUS + lower == pytest.approx(0.020 * 25.4, abs=1e-12)
    assert spec.GROOVE_HALF_OPENING_MAX == geom.GROOVE_RADIUS
    # Two rows, "R.047" over ".020": the R row is the wider.
    assert drawing.RADIUS_GLYPHS == len("R.047")
    # A bare R.047 at the title block's .X admits R.147: across the printed
    # root and OD the mouth opens wide and the face lip falls under the
    # target.
    r = 0.047 * 25.4 + printed_band_mm(1, unit=spec.UNIT)
    half = max(
        spec.groove_half_opening(r, root, od)
        for root in _PRINTED_ROOTS
        for od in _PRINTED_ODS
    )
    assert (0.15 - 0.01) * 25.4 - half < spec.WALL_TARGET


_PRINTED_ROOTS = ((0.30 - 0.01) * 25.4, (0.30 + 0.01) * 25.4)
_PRINTED_ODS = ((0.40 - 0.01) * 25.4, (0.40 + 0.01) * 25.4)


def _groove_at(radius: float) -> dict[str, float]:
    """Every groove proof that moves with the radius, at the printed worst
    root, OD and station, for one radius."""
    opens = [
        spec.groove_half_opening(radius, root, od)
        for root in _PRINTED_ROOTS
        for od in _PRINTED_ODS
    ]
    far_depth = (0.14 + 0.01) * 25.4 + radius
    return {
        "narrowest mouth": 2.0 * min(opens),
        "face lip": (0.14 - 0.01) * 25.4 - max(opens),
        "root over thread": _PRINTED_ROOTS[0] / 2.0 - spec._THREAD_R_MAX - spec._wander(far_depth),
        "shoulder clearance": (0.25 - 0.01) * 25.4 - ((0.14 + 0.01) * 25.4 + max(opens)),
    }


def test_the_groove_holds_the_wire_and_every_wall_at_its_smallest_radius() -> None:
    # The floor's R.020 over the lever wire's radius: the wire seats on the
    # floor at one line, its centre the root plus its radius (the hook), and
    # the groove's depth is the root's, whatever the radius.
    assert spec.GROOVE_RADIUS_MIN > geom.WIRE_DIA / 2.0
    assert geom.HOOK_RADIAL_OFFSET == pytest.approx(
        geom.GROOVE_ROOT_DIA / 2.0 + geom.WIRE_DIA / 2.0 + geom.WIRE_CLEARANCE
    )
    assert spec.GROOVE_DEPTH_MIN == pytest.approx(0.040 * 25.4) and spec.GROOVE_DEPTH_MIN > 0.4
    r_min, r_max = 0.020 * 25.4, 0.047 * 25.4
    smallest, largest = _groove_at(r_min), _groove_at(r_max)
    # R MIN centres under the OD at every printed root and OD: walls .040 apart.
    assert spec.GROOVE_HALF_OPENING_MIN == pytest.approx(r_min)
    assert smallest["narrowest mouth"] == pytest.approx(2.0 * r_min)
    assert smallest["narrowest mouth"] > geom.WIRE_DIA
    # Owner ruling on review r5: the radius's own row reads FULL R, the arc
    # tangent to both walls (2R wide), the depth the root Ø's.  An R.020 arc
    # cannot reach the root from the OD, so its walls run straight: .020 long
    # at the shallowest printed groove, .040 at the deepest.  At R.047 the
    # shallowest groove (.040) is under R: the arc meets the OD first, a
    # narrower mouth than 2R.
    assert spec.GROOVE_RADIUS_CALLOUT == "FULL R"
    assert spec.GROOVE_WALL_AT_RADIUS_MIN == pytest.approx(0.020 * 25.4)
    assert (_PRINTED_ODS[1] - _PRINTED_ROOTS[0]) / 2.0 - r_min == pytest.approx(0.040 * 25.4)
    above = _PRINTED_ROOTS[1] / 2.0 + r_max - _PRINTED_ODS[0] / 2.0
    assert largest["narrowest mouth"] == pytest.approx(2.0 * math.sqrt(r_max**2 - above**2))
    assert largest["narrowest mouth"] == pytest.approx(2.361, abs=5e-4)
    # Each wall the largest radius sets only thickens at the smallest.
    assert largest["face lip"] == pytest.approx(spec.WALLS["groove lip to the spigot face"][1])
    assert largest["root over thread"] == pytest.approx(
        spec.WALLS["groove root over the thread major"][1]
    )
    assert largest["shoulder clearance"] == pytest.approx(spec.GROOVE_SHOULDER_CLEARANCE)
    assert smallest["face lip"] == pytest.approx(2.794)
    assert smallest["root over thread"] == pytest.approx(2.1125, abs=1e-4)
    assert smallest["shoulder clearance"] == pytest.approx(1.778)
    for name in ("face lip", "root over thread", "shoulder clearance"):
        assert smallest[name] > largest[name], name
    assert min(smallest["face lip"], smallest["root over thread"]) > spec.WALL_TARGET


def test_the_overall_reference_is_an_accepted_exception_with_its_real_stack() -> None:
    # Owner ruling 2026-10-17 (review r4): the two-station bore location and
    # the (.72) REF stay; the bore is the datum the rod and the thumb screw
    # work off.
    import machinist_exceptions

    (exception,) = machinist_exceptions.load_exceptions(
        SCRIPTS.parent / "config", "mg_output_fixture", "part"
    )
    assert exception.id == "RV-01" and exception.kind == "accept"
    for text in (".23", ".49", "(.72)", "Ø.257"):
        assert text in exception.where, text
    assert "rule 10" in exception.finding and "rule 11" in exception.finding
    # A real .72 overall stacks the free end's station to +/-.02.
    stacked = (0.23 - 0.02) * 25.4 - spec.ROD_BORE_R_MAX - spec.BORE_WANDER
    assert stacked == pytest.approx(0.0742 * 25.4, abs=5e-3) and stacked < spec.WALL_TARGET
    assert spec.WALLS["rod bore to the free end"][1] == pytest.approx(0.0842 * 25.4, abs=5e-3)
    for number in ("±.02", ".1305", ".0053", ".0742", ".0842", "2026-10-17"):
        assert number in exception.reason, number
    assert spec.REFERENCE_DIMENSIONS >= {"OverallLength"}


def test_the_spigot_cleans_up_inside_the_thinnest_flats() -> None:
    # A route check, not a band: the shop turns the largest printed Ø (.41)
    # inside the thinnest flats.
    assert geom.SPIGOT_DIA + spec._SPIGOT_HI < geom.HEX_AF - spec.HEX_STOCK_AF_BAND
    assert geom.HEX_AF - spec.HEX_STOCK_AF_BAND - 0.41 * 25.4 == pytest.approx(0.5715)


def test_the_spigot_prints_its_own_length_and_the_hex_is_the_stations_less_it() -> None:
    # r2 review: the hex from the free end left the turner to find the
    # shoulder through the stations; the lathe faces the spigot and measures
    # back to its shoulder.  The hex stays modelled, unprinted.
    assert "HexLength" not in spec.DRAWING_PRECISION_BY_NAME
    assert spec.DRAWING_PRECISION_BY_NAME["SpigotLength"] == spec.SPIGOT_LENGTH_PLACES == 2
    assert spec.DRAWING_DIMENSIONS["TurnedProfile"] >= {"SpigotLength", "RodStation", "BoreStation"}
    assert geom.SPIGOT_LENGTH == pytest.approx(0.25 * 25.4)
    assert geom.HEX_LENGTH == pytest.approx(0.23 * 25.4 + 12.446 - 0.25 * 25.4)
    assert geom.OVERALL_LENGTH == pytest.approx(0.72 * 25.4)


def test_the_shoulder_corner_takes_the_title_block_inside_corner_row() -> None:
    # ENFORCE review 2026-10-24 (rule 4): a bare MAX radius named no mate and
    # nothing seats on the shoulder, so the title block's INSIDE CORNERS row
    # (R.040 MAX) governs the corner and the sheet prints no size.  The part
    # keeps its modelled .008 tool nose inside that row.
    from _printed_tolerance import inside_corner_radius_mm

    ceiling = inside_corner_radius_mm(unit=spec.UNIT)
    assert ceiling == pytest.approx(0.040 * 25.4)
    assert geom.SHOULDER_FILLET_R == pytest.approx(0.008 * 25.4)
    assert geom.SHOULDER_FILLET_R <= ceiling
    assert "ShoulderFillet" not in spec.DRAWING_DIMENSIONS
    assert "ShoulderRadius" not in spec.DRAWING_PRECISION_BY_NAME
    assert "ShoulderRadius" not in drawing.SIDE_KEEP
    for retired in (
        "SHOULDER_RADIUS_PLACES", "SHOULDER_RADIUS_TOL_TYPE", "SHOULDER_FILLET_R_MAX",
        "TITLE_BLOCK_EDGE_BREAK", "SHOULDER_FILLET_FLAT_OVERRUN_MAX",
    ):
        assert not hasattr(spec, retired), retired
    for retired in ("_place_shoulder_radius", "_prove_shoulder_radius", "LOWER_ARC_KEEP"):
        assert not hasattr(drawing, retired), retired
    # The modelled corner sits inside the shoulder's annulus on 7/16 flats,
    # even on the thinnest bar, and clear of the groove's shoulder-side mouth.
    annulus = (geom.HEX_AF - geom.SPIGOT_DIA) / 2.0
    assert annulus == pytest.approx(0.51245)
    assert spec.SHOULDER_ANNULUS == pytest.approx(annulus)
    thinnest = (geom.HEX_AF - spec.HEX_STOCK_AF_BAND - geom.SPIGOT_DIA) / 2.0
    assert spec.SHOULDER_ANNULUS_MIN == pytest.approx(thinnest)
    assert thinnest == pytest.approx(0.44895)
    assert geom.SHOULDER_FILLET_R < thinnest
    nominal = geom.GROOVE_MOUTHS[0] - (geom.SHOULDER_X + geom.SHOULDER_FILLET_R)
    assert nominal == pytest.approx(1.457, abs=1e-4)
    # Even the row's R.040 clears the groove's mouth at the worst-case stack:
    # an inside-corner blend never reaches the groove.
    assert geom.GROOVE_MOUTHS[0] - (geom.SHOULDER_X + ceiling) == pytest.approx(0.6442, abs=1e-4)
    assert spec.GROOVE_SHOULDER_CLEARANCE > ceiling


def test_the_builder_fillets_the_shoulder_and_its_volume_is_the_swept_spandrel() -> None:
    steps = 20000
    r = geom.SHOULDER_FILLET_R
    swept = sum(
        _fillet_annulus(geom.SHOULDER_X + (index + 0.5) * r / steps) * r / steps
        for index in range(steps)
    )
    assert part.V_FILLET == pytest.approx(swept, rel=1e-4)
    assert part.V_FILLET == pytest.approx(0.2833, abs=1e-3)
    assert part.V_TOTAL == pytest.approx(
        part.V_HEX + part.V_SPIGOT + part.V_FILLET - part.V_GROOVE - part.V_BORE - part.V_TAP
    )


def test_the_rod_bore_ends_the_thread_and_its_depth_is_ref() -> None:
    # The native thread depth is the nominal wall on the tap's axis; the
    # callout brackets it as REF, so no band governs the thread's extent: the
    # rod bore does (the callout's extent row).  Review09: a bare depth in the
    # callout read as controlling while the note said REF.  Review r3 (rule
    # 7): the extent sat in a general note far from the tap; it is the
    # callout's own row now, words only (the bore's Ø is its own native
    # dimension; a typed size would not follow the model).
    assert spec.TAP_EXTENT_CALLOUT == "FULL THREAD TO ROD BORE"
    assert not any(ch.isdigit() for ch in spec.TAP_EXTENT_CALLOUT)
    assert not hasattr(spec, "TAP_EXTENT_NOTE")
    assert geom.TAP_SPEC.overrides_mm["ThreadDepth"] == geom.TAP_LENGTH
    assert geom.TAP_LENGTH == pytest.approx(geom.SPIGOT_FACE_X - geom.ROD_BORE_DIA / 2.0)
    assert set(spec.TAP_CALLOUT_PRECISION) == {
        spec.TAP_DRILL_DIA_VARIABLE,
        spec.TAP_DRILL_DEPTH_VARIABLE,
        spec.TAP_THREAD_DEPTH_VARIABLE,
    } == {"hw-tapdrldia", "hw-tapdrldepth", "hw-threaddepth"}


# Retry09's definitions, as the resolved parts imply (prefix 5 carries the
# process and the thread row, callout-above 7 the drill row), under today's
# process.
_NATIVE_DEFINITIONS = {
    5: "TAP <hw-thread> <HOLE-DEPTH> <hw-threaddepth>",
    6: "",
    7: "<MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH> <hw-tapdrldepth>",
    8: "",
}
_REFERENCED_DEFINITIONS = {
    **_NATIVE_DEFINITIONS,
    5: "TAP <hw-thread> <HOLE-DEPTH> (<hw-threaddepth>)",
}


def test_thread_depth_definition_gains_reference_brackets_only() -> None:
    updated = drawing.reference_thread_depth_definitions(dict(_NATIVE_DEFINITIONS))
    assert updated == _REFERENCED_DEFINITIONS


@pytest.mark.parametrize(
    "definitions",
    [
        # Already bracketed: someone else's edit, not the native definition.
        _REFERENCED_DEFINITIONS,
        # No thread depth to bracket.
        {**_NATIVE_DEFINITIONS, 5: "TAP <hw-thread>"},
        # Two thread depths: which one is the reference is a guess.
        {**_NATIVE_DEFINITIONS, 8: "<hw-threaddepth>"},
        # The controlling drill depth missing, or bracketed.
        {**_NATIVE_DEFINITIONS, 7: "<MOD-DIAM><hw-tapdrldia>"},
        {**_NATIVE_DEFINITIONS, 7: "<MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH> (<hw-tapdrldepth>)"},
    ],
)
def test_thread_depth_definition_refuses_anything_but_one_bare_variable(
    definitions: dict[int, str],
) -> None:
    with pytest.raises(RuntimeError, match="expected one bare"):
        drawing.reference_thread_depth_definitions(definitions)


def test_thread_extent_is_the_below_definition_under_the_thread() -> None:
    # The prefix carries the thread row, so the below definition prints the
    # extent directly under it; nothing else changes.
    assert drawing.thread_extent_definitions(dict(_REFERENCED_DEFINITIONS)) == {
        **_REFERENCED_DEFINITIONS,
        8: "FULL THREAD TO ROD BORE",
    }


@pytest.mark.parametrize(
    "definitions",
    [
        # The below row already holds text: someone else's row.
        {**_REFERENCED_DEFINITIONS, 8: "BREAK EDGE"},
        # The extent already stated, here or on another row.
        {**_REFERENCED_DEFINITIONS, 8: "FULL THREAD TO ROD BORE"},
        {**_REFERENCED_DEFINITIONS, 6: " FULL THREAD TO ROD BORE"},
        # The thread row is not the prefix's: the below row would sit under
        # something else.
        {
            **_REFERENCED_DEFINITIONS,
            5: "TAP",
            7: "<hw-thread> <HOLE-DEPTH> (<hw-threaddepth>)",
        },
    ],
)
def test_thread_extent_refuses_anything_but_an_empty_below_row_under_the_thread(
    definitions: dict[int, str],
) -> None:
    with pytest.raises(RuntimeError, match="empty below definition"):
        drawing.thread_extent_definitions(definitions)


_EXTENT = "FULL THREAD TO ROD BORE"


@pytest.mark.parametrize(
    ("resolved", "reads"),
    [
        (
            {
                1: "TAP 4-40 UNC-2B <HOLE-DEPTH> (.36)",
                2: "<MOD-DIAM>.089 <HOLE-DEPTH> .49",
                3: "",
                4: _EXTENT,
            },
            True,
        ),
        # Retry09's native layout, bracketed, under today's process and with
        # the extent row under the thread.
        (
            {
                1: "TAP 4-40 UNC - 2B <HOLE-DEPTH> (.36)",
                2: "",
                3: "<MOD-DIAM> .089 <HOLE-DEPTH> .49",
                4: _EXTENT,
            },
            True,
        ),
        # Review r3's print: the extent only in a general note, not here.
        (
            {
                1: "TAP INTO BORE 4-40 UNC - 2B <HOLE-DEPTH> (.36)",
                2: "",
                3: "<MOD-DIAM> .089 <HOLE-DEPTH> .49",
                4: "",
            },
            False,
        ),
        # The extent over the drill row, not under the thread.
        (
            {
                1: "TAP 4-40 UNC - 2B <HOLE-DEPTH> (.36)",
                2: "",
                3: f"<MOD-DIAM> .089 <HOLE-DEPTH> .49\n{_EXTENT}",
                4: "",
            },
            False,
        ),
        # The extent stated twice.
        (
            {
                1: f"TAP 4-40 UNC - 2B <HOLE-DEPTH> (.36) {_EXTENT}",
                2: "",
                3: "<MOD-DIAM> .089 <HOLE-DEPTH> .49",
                4: _EXTENT,
            },
            False,
        ),
        # The thread row off the prefix: the below row would not sit under it.
        (
            {
                1: "<MOD-DIAM> .089 <HOLE-DEPTH> .49",
                2: "",
                3: "TAP 4-40 UNC - 2B <HOLE-DEPTH> (.36)",
                4: _EXTENT,
            },
            False,
        ),
        # Retry09 as printed: a bare thread depth reads as controlling
        # (review09).
        (
            {
                1: "TAP 4-40 UNC - 2B <HOLE-DEPTH> .36",
                2: "",
                3: "<MOD-DIAM> .089 <HOLE-DEPTH> .49",
                4: _EXTENT,
            },
            False,
        ),
        # The reference stated twice, once bare.
        (
            {
                1: "TAP 4-40 UNC-2B <HOLE-DEPTH> (.36) .36",
                2: "<MOD-DIAM>.089 <HOLE-DEPTH> .49",
                3: "",
                4: _EXTENT,
            },
            False,
        ),
        # The controlling drill depth bracketed as if it were REF.
        (
            {
                1: "TAP 4-40 UNC-2B <HOLE-DEPTH> (.36)",
                2: "<MOD-DIAM>.089 <HOLE-DEPTH> (.49)",
                3: "",
                4: _EXTENT,
            },
            False,
        ),
        # The old ambiguous callout: THRU on both rows.
        (
            {
                1: "TAP TO BORE 4-40 UNC-2B THRU",
                2: "<MOD-DIAM>.089 THRU",
                3: "",
                4: _EXTENT,
            },
            False,
        ),
        # Three places on the thread depth asks for the .XXX band.
        (
            {
                1: "TAP 4-40 UNC-2B <HOLE-DEPTH> (.362)",
                2: "<MOD-DIAM>.089 <HOLE-DEPTH> .49",
                3: "",
                4: _EXTENT,
            },
            False,
        ),
        # The thread without its process.
        (
            {
                1: "4-40 UNC-2B <HOLE-DEPTH> (.36)",
                2: "<MOD-DIAM>.089 <HOLE-DEPTH> .49",
                3: "",
                4: _EXTENT,
            },
            False,
        ),
        # The drill row without its depth.
        (
            {
                1: "TAP 4-40 UNC-2B <HOLE-DEPTH> (.36)",
                2: "<MOD-DIAM>.089",
                3: "",
                4: _EXTENT,
            },
            False,
        ),
        # A band on the REF thread depth.
        (
            {
                1: "TAP 4-40 UNC-2B <HOLE-DEPTH> (.36)<MOD-PM>.01",
                2: "<MOD-DIAM>.089 <HOLE-DEPTH> .49",
                3: "",
                4: _EXTENT,
            },
            False,
        ),
    ],
)
def test_tap_callout_states_its_depths_and_extent(
    resolved: dict[int, str], reads: bool
) -> None:
    assert drawing._tap_callout_resolved(resolved) is reads


def test_final_sheet_census_expects_no_tapped_hole_note_from_the_blind_tap() -> None:
    # Two passing runs of the up-to-next tap each swept one "#4-40 Tapped
    # Hole" note; retry08's blind tap, on the same views and imports, swept
    # none and failed the stale census of one.  The census is the tap's.
    assert drawing.AUTO_TAPPED_HOLE_NOTES == 0
    # The topology it was measured on: a blind tap no targeted import selects.
    assert geom.TAP_SPEC.end == "blind"
    assert set(spec.DRAWING_DIMENSIONS) == {
        "TurnedProfile",
        "GrooveProfile",
        "HexProfile",
        "RodBoreProfile",
    }
    # The sweep (a case-blind substring) reaches the note SolidWorks pins and
    # never the native callout that states the tap.
    note = drawing.TAPPED_HOLE_NOTE.lower()
    assert note in f"{geom.TAP_SPEC.size} Tapped Hole".lower()
    native_callout = (
        "<MOD-DIAM> .089 <HOLE-DEPTH> .49\n"
        "TAP 4-40 UNC - 2B <HOLE-DEPTH> (.36)\n"
        "FULL THREAD TO ROD BORE"
    )
    assert note not in native_callout.lower()


def _fillet_annulus(x: float) -> float:
    """The shoulder fillet's ring at axial station ``x``: the arc's height
    over the spigot, the arc centred R out from the shoulder and the OD."""
    r, spigot_r = geom.SHOULDER_FILLET_R, geom.SPIGOT_DIA / 2.0
    dx = x - (geom.SHOULDER_X + r)
    if not geom.SHOULDER_X <= x <= geom.SHOULDER_X + r:
        return 0.0
    top = spigot_r + r - math.sqrt(r**2 - dx**2)
    return math.pi * (top**2 - spigot_r**2)


def _slice_area(x: float) -> float:
    """The part's cross-section at axial station ``x``, from the shapes alone."""
    af, corner = geom.HEX_AF, geom.HEX_CORNER_RADIUS
    bore_r = geom.ROD_BORE_DIA / 2.0
    drill_r = geom.TAP_DRILL_DIA / 2.0
    if x < geom.SHOULDER_X:
        area = math.sqrt(3.0) / 2.0 * af**2
    else:
        spigot_r = geom.SPIGOT_DIA / 2.0
        area = math.pi * spigot_r**2 + _fillet_annulus(x)
        dx = x - geom.GROOVE_X
        if abs(dx) < geom.GROOVE_RADIUS:
            cut_r = geom.GROOVE_CENTRE_R - math.sqrt(geom.GROOVE_RADIUS**2 - dx**2)
            if cut_r < spigot_r:
                area -= math.pi * (spigot_r**2 - cut_r**2)
    band = math.sqrt(bore_r**2 - x**2) if abs(x) < bore_r else 0.0
    if band:
        # The bore along Y cuts the band |z| <= band through the hex, whose
        # chord along Y at height z is 2(corner - |z|/sqrt(3)).
        area -= 2.0 * (2.0 * corner * band - band**2 / math.sqrt(3.0))
    if x > 0.0:
        # The tap drill, outside what the bore already took.
        if band >= drill_r:
            pass
        elif band:
            area -= 2.0 * (
                drill_r**2 * math.acos(band / drill_r)
                - band * math.sqrt(drill_r**2 - band**2)
            )
        else:
            area -= math.pi * drill_r**2
    return area


def test_analytic_volume_matches_the_part_sliced_along_its_axis() -> None:
    """The builder's volume guards assert ``part.V_TOTAL``; a part that lost
    a feature (the groove, the bore or the tap) misses it by far more than
    the guard's 0.5 %."""
    steps = 40000
    width = (geom.SPIGOT_FACE_X - geom.FREE_END_X) / steps
    sliced = sum(
        _slice_area(geom.FREE_END_X + (index + 0.5) * width) * width
        for index in range(steps)
    )
    assert part.V_TOTAL == pytest.approx(sliced, rel=2e-3)
    smallest_feature = min(part.V_GROOVE, part.V_BORE, part.V_TAP)
    assert smallest_feature > 0.005 * part.V_TOTAL


# A dimension's text centre sits ~2.8 mm over its line (2026-10-12 farm
# sheet: HexLength's text at 209.05 mm over its line at 206.27 mm).
_TEXT_OVER_LINE = 0.0028
_TEXT_HEIGHT = 0.0035


def _dia_text_box(name: str) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of a turned Ø text centred on its keep: retry09's
    Ø9.00 broke its line 2.8 mm either side of the keep's y."""
    x, y = drawing.SIDE_KEEP[name]
    half = drawing.TURNED_DIA_TEXT_HALF_WIDTH
    return (x - half, y - _TEXT_OVER_LINE, x + half, y + _TEXT_OVER_LINE)


# A dimension arrow's length on the sheet (retry09 audit: 3.556 mm).
_ARROW = 0.003556


def test_turned_diameters_stack_right_of_the_face_smaller_inside() -> None:
    # Review09 finding 8: the root Ø's text hung under the view, so its line
    # ran out of the groove into a shoulder that read as an axial length.
    face_x = drawing._side_x(geom.SPIGOT_FACE_X)
    root_x, root_y = drawing.SIDE_KEEP["GrooveRootDia"]
    spigot_x, spigot_y = drawing.SIDE_KEEP["SpigotDia"]
    root_box, spigot_box = _dia_text_box("GrooveRootDia"), _dia_text_box("SpigotDia")
    # Both clear the face's witnesses; the smaller stands inside, so its
    # extension lines end short of the larger's line.
    assert root_box[0] > face_x + 0.003
    assert face_x < root_x < spigot_x
    # Each text breaks its own dimension line between the arrows: the root's
    # inside the groove's roots, the spigot's inside its OD; neither hangs
    # off the view.
    low, high = drawing.GROOVE_ROOT_SHEET_YS
    assert (low, high) == pytest.approx(
        (drawing._side_y(-geom.GROOVE_ROOT_DIA / 2.0), drawing._side_y(geom.GROOVE_ROOT_DIA / 2.0))
    )
    assert low + _ARROW < root_box[1] and root_box[3] < high - _ARROW
    od_low = drawing._side_y(-geom.SPIGOT_DIA / 2.0)
    od_high = drawing._side_y(geom.SPIGOT_DIA / 2.0)
    assert od_low + _ARROW < spigot_box[1] and spigot_box[3] < od_high - _ARROW
    assert drawing._SIDE_BOTTOM < root_y < drawing._SIDE_TOP
    # Neither text crosses the other's dimension line, and the two stagger a
    # text height apart so they never read as one row.
    assert spigot_box[0] > root_x + 0.003
    assert root_box[2] < spigot_x - 0.003
    assert spigot_box[1] - root_box[3] >= _TEXT_HEIGHT
    # The spigot's text clears the rotated end view's left-standing AF line.
    assert spigot_box[2] < drawing.END_KEEP["HexAf"][0] - 0.005
    # Overall length stays under the view.  The radius text reads right of
    # the face, its shoulder under the spigot mouth.
    assert drawing.SIDE_KEEP["OverallLength"][1] < drawing._SIDE_BOTTOM
    assert drawing.SIDE_KEEP["GrooveRadius"] == drawing.RADIUS_TEXT_XY
    assert drawing.RADIUS_TEXT_XY[1] - drawing.GROOVE_RADIUS_SHOULDER_DROP < od_high


def test_groove_root_dia_is_a_doubled_distance_to_the_root_point() -> None:
    # Finding 8 is presentation only: the part already dimensions the root as
    # a diametric linear dimension from the groove's axis to the root point,
    # the start of the face-side arc (GROOVE_X, root_v).
    assert geom.GROOVE_CENTRE_R - geom.GROOVE_RADIUS == pytest.approx(geom.GROOVE_ROOT_DIA / 2.0)
    # swDimensionType_e: the sheet's import read the part's diametric linear
    # dimension back as swDiameterDimension (6) with Diametric True (retry10,
    # farm 20261012T170144152Z); the authoring type (15) is the other doubled
    # distance.  Neither the single-distance radial linear (14) nor a plain
    # linear is one.
    assert drawing._DOUBLED_DISTANCE_TYPES == {
        6: "swDiameterDimension",
        15: "swDiametricLinearDimension",
    }
    assert drawing.GROOVE_ROOT_VALUE_SLOP_MM == 1e-5


def _nested_root_ink() -> list:
    """The root Ø's ink as SolidWorks draws a nested doubled distance: an
    extension line from each root, 1 mm off the groove, 1 mm past the line;
    the line root to root, broken at the text."""
    line_x, text_y = drawing.SIDE_KEEP["GrooveRootDia"]
    low, high = drawing.GROOVE_ROOT_SHEET_YS
    start = drawing._side_x(geom.GROOVE_X) + 0.001
    return [
        ((start, low), (line_x + 0.001, low)),
        ((start, high), (line_x + 0.001, high)),
        ((line_x, low), (line_x, text_y - _TEXT_OVER_LINE)),
        ((line_x, high), (line_x, text_y + _TEXT_OVER_LINE)),
    ]


# Retry09's GrooveRootDia ink, verbatim from its layout audit
# (20261012T124257186Z): degenerate extensions at the roots, the line down
# the groove, its 20 mm leg out of it and the 30 mm shoulder under the text.
_RETRY09_ROOT_INK = [
    ((0.146, 0.166), (0.146, 0.166)),
    ((0.146, 0.194), (0.146, 0.194)),
    ((0.1171778, 0.1461451), (0.147, 0.1461451)),
    ((0.147, 0.1461451), (0.147, 0.166)),
    ((0.147, 0.166), (0.147, 0.194)),
]


def test_nested_root_ink_reads_across_the_groove() -> None:
    line_x = drawing.SIDE_KEEP["GrooveRootDia"][0]
    assert drawing._groove_root_ink_problem(_nested_root_ink(), line_x) is None


@pytest.mark.parametrize(
    ("case", "problem"),
    [
        # Retry09's line against its own keep, shoulder aside: the line
        # leaves the groove.
        ("retry09-leg", "not root to root"),
        # Retry09 whole against the nested keep: its shoulder is stray ink.
        ("retry09", "neither its dimension line"),
        # A shoulder hung off the nested line.
        ("shoulder", "neither its dimension line"),
        ("drop-extension", "no extension line from the root"),
        ("drop-line", "no dimension line"),
    ],
)
def test_groove_root_ink_off_the_groove_fails(case: str, problem: str) -> None:
    keep_x, text_y = drawing.SIDE_KEEP["GrooveRootDia"]
    nested = _nested_root_ink()
    segments, line_x = {
        "retry09-leg": ([s for i, s in enumerate(_RETRY09_ROOT_INK) if i != 2], 0.147),
        "retry09": (_RETRY09_ROOT_INK, keep_x),
        "shoulder": ([*nested, ((keep_x, text_y), (keep_x + 0.03, text_y))], keep_x),
        "drop-extension": (nested[1:], keep_x),
        "drop-line": (nested[:2], keep_x),
    }[case]
    found = drawing._groove_root_ink_problem(segments, line_x)
    assert found is not None and problem in found


def test_bore_callout_reads_over_the_hex_between_its_witnesses() -> None:
    # The free end carries witnesses over its whole height, so the bore's Ø
    # reads over the hex, between the free end and the shoulder.
    x, y = drawing.SIDE_KEEP["RodBoreDia"]
    half_width = drawing.BORE_CALLOUT_HALF_WIDTH
    half_height = drawing.BORE_CALLOUT_HALF_HEIGHT
    assert x - half_width > drawing._side_x(geom.FREE_END_X) + 0.005
    assert x + half_width < drawing._side_x(geom.SHOULDER_X) - 0.005
    assert y - half_height > drawing._SIDE_TOP + 0.003
    # The groove's station, from the spigot face, reads over the spigot; the
    # spigot's length reads under it, then the bore's two stations on one
    # row, then the overall REF.
    station_x = drawing.SIDE_KEEP["GrooveStation"][0]
    assert station_x - 0.005 > drawing._side_x(geom.SHOULDER_X) + 0.003
    assert station_x == pytest.approx(
        drawing._side_x((geom.GROOVE_X + geom.SPIGOT_FACE_X) / 2.0)
    )
    spigot_x, spigot_y = drawing.SIDE_KEEP["SpigotLength"]
    assert drawing._side_x(geom.SHOULDER_X) < spigot_x < drawing._side_x(geom.SPIGOT_FACE_X)
    assert spigot_y < drawing._SIDE_BOTTOM - 0.005
    assert drawing.SIDE_KEEP["RodStation"][1] == drawing.SIDE_KEEP["BoreStation"][1]
    assert drawing.SIDE_KEEP["BoreStation"][1] < spigot_y - 0.010
    assert drawing.SIDE_KEEP["OverallLength"][1] < drawing.SIDE_KEEP["BoreStation"][1] - 0.010


def test_end_view_flats_read_vertically_left_of_the_hex_clear_of_the_tap() -> None:
    assert drawing._END_HALF_HEIGHT == pytest.approx(geom.HEX_AF * drawing._S / 2000.0)
    assert drawing._END_HALF_WIDTH == pytest.approx(geom.HEX_CORNER_RADIUS * drawing._S / 1000.0)
    assert set(drawing.END_KEEP) == {"HexAf"}
    af_x, af_y = drawing.END_KEEP["HexAf"]
    assert af_x < drawing.END_CENTER[0] - drawing._END_HALF_WIDTH - 0.010
    assert af_y == drawing.END_CENTER[1]
    text_left = drawing.TAP_CALLOUT_XY[0] - drawing._TAP_CALLOUT_HALF_WIDTH
    assert text_left > drawing.END_CENTER[0] + drawing._END_HALF_WIDTH + 0.005
    assert drawing.TAP_CALLOUT_XY[1] - drawing._TAP_CALLOUT_SHOULDER_DROP > af_y
    # Three rows (drill, thread, FULL THREAD TO ROD BORE): the block grows a
    # 6.0 mm pitch about its centre, so the centre rises half a pitch over
    # the two-row 5.6 mm drop and the shoulder stays 4 mm over the hole.
    assert drawing._TAP_CALLOUT_SHOULDER_DROP == pytest.approx(0.0056 + 0.0030)
    assert drawing.TAP_CALLOUT_XY[1] - drawing._TAP_CALLOUT_SHOULDER_DROP == pytest.approx(
        drawing.END_CENTER[1] + 0.004
    )
    # The widest row, the extent, holds inside the half width: r3 printed the
    # same words with a full stop, in the same capitals, 61.2 mm wide.
    assert 2.0 * drawing._TAP_CALLOUT_HALF_WIDTH > 0.0612
    # Right of the hex and clear of the sheet's right border zone.
    assert drawing.TAP_CALLOUT_XY[0] + drawing._TAP_CALLOUT_HALF_WIDTH < 0.400


def test_the_sheet_carries_no_general_note() -> None:
    # Machinist review (run 20261101T025747277Z): the flats' REF named no
    # supplier band.  It is on the REF's own rows now, so the stock note
    # (rule 11: notes carry no dimensions) is gone; the thread's extent was
    # already the tap callout's row (review r3).
    for retired in ("DRAWING_NOTES", "STOCK_NOTE"):
        assert not hasattr(spec, retired), retired
    assert not hasattr(drawing, "NOTES_XY")


def test_part_stamps_make_critical_properties() -> None:
    import _config

    config = _config.parts("mg-output-fixture")
    assert config["material"] == "C36000 free-cutting brass"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_the_flats_reference_states_the_stock_untoleranced() -> None:
    # The supplier's +/-.005 on the 7/16 flats governs and every wall proof
    # reads it; the fraction REF prints untoleranced.
    assert spec.HEX_AF_CALLOUT == "HEX STOCK"
    assert spec.HEX_STOCK_AF_BAND == pytest.approx(0.005 * 25.4)
    assert drawing.HEX_AF_REFERENCE["callout"] is spec.HEX_AF_CALLOUT
    # The REF's rows fit between the side view's turned Ø text and the hex.
    keep_x = drawing.END_KEEP["HexAf"][0]
    spigot_text_right = drawing.SIDE_KEEP["SpigotDia"][0] + drawing.TURNED_DIA_TEXT_HALF_WIDTH
    assert keep_x - drawing._AF_TEXT_HALF_WIDTH > spigot_text_right + 0.003
    assert keep_x + drawing._AF_TEXT_HALF_WIDTH < drawing.END_CENTER[0] - drawing._END_HALF_WIDTH
    # The text box stays between the flats, so their witnesses are never
    # read as text.
    assert drawing._AF_TEXT_HALF_HEIGHT < drawing._END_HALF_HEIGHT - 0.002


def _end_flat_points() -> tuple[tuple[float, float], tuple[float, float]]:
    x, y = drawing.END_CENTER
    return (
        (x - drawing._END_HALF_WIDTH / 2.0, y + drawing._END_HALF_HEIGHT),
        (x + drawing._END_HALF_WIDTH / 2.0, y - drawing._END_HALF_HEIGHT),
    )


def _vertical_af_ink() -> list:
    x = drawing.END_KEEP["HexAf"][0]
    top, bottom = _end_flat_points()
    return [
        ((x, bottom[1]), (x, top[1])),
        ((top[0] - drawing.EXTENSION_START_GAP, top[1]), (x - 0.001, top[1])),
        ((bottom[0] - drawing.EXTENSION_START_GAP, bottom[1]), (x - 0.001, bottom[1])),
    ]


def test_rotated_end_stock_af_ink_stands_across_flats_not_corners() -> None:
    assert drawing._end_af_ink_problem(_vertical_af_ink(), _end_flat_points()) is None


def test_rotated_end_stock_af_reads_its_fraction_bar_as_text_not_a_stray_stroke() -> None:
    # The farm's (7/16 in) REF draws its fraction bar as a display line
    # (run 20261031T211631726Z): inside the text's box it is the text's ink.
    keep_x, keep_y = drawing.END_KEEP["HexAf"]
    bar = ((keep_x - 0.004, keep_y), (keep_x - 0.002, keep_y))
    assert drawing._end_af_ink_problem([*_vertical_af_ink(), bar], _end_flat_points()) is None
    # The same stroke out beside the hex is no text of this dimension.
    stray = ((keep_x + 0.020, keep_y), (keep_x + 0.022, keep_y))
    problem = drawing._end_af_ink_problem([*_vertical_af_ink(), stray], _end_flat_points())
    assert problem is not None and "neither" in problem


@pytest.mark.parametrize("case", ["empty", "missing-flat", "ac-height", "horizontal", "short-witness"])
def test_rotated_end_stock_af_refuses_wrong_frame_or_unwitnessed_flats(case: str) -> None:
    ink = _vertical_af_ink()
    if case == "empty":
        ink = []
    elif case == "missing-flat":
        ink = ink[:-1]
    elif case == "ac-height":
        x = drawing.END_KEEP["HexAf"][0]
        y = drawing.END_CENTER[1]
        ink[0] = ((x, y - drawing._END_HALF_WIDTH), (x, y + drawing._END_HALF_WIDTH))
    elif case == "horizontal":
        x, y = drawing.END_CENTER
        ink[0] = ((x - drawing._END_HALF_HEIGHT, y), (x + drawing._END_HALF_HEIGHT, y))
    else:
        (x0, y0), p1 = ink[1]
        ink[1] = ((x0 - 0.004, y0), p1)
    assert drawing._end_af_ink_problem(ink, _end_flat_points()) is not None


# Native15 audit (20261013T091530503Z): printed glyphs, not the wider COM row.
# "R1.20 ±0.05" (11 glyphs) printed 24.16 mm wide, centred on its keep, from
# 1.84 mm under to 1.72 mm over it; the full shoulder ran from 15.28 mm left
# of and 2.78 mm under the keep to 1.50 mm past the text's right end.
_NATIVE15_RADIUS_KEEP = (0.1724, 0.1988)
# What the radius prints: the part's LIMIT band, the R row over the lower
# limit, and under them the sheet's callout row (owner ruling, review r5).
_RADIUS_ROWS = ("R.047", ".020", "FULL R")
# r12's GrooveRadius (20261017T053834039Z: audit display data, 300 dpi PNG):
# keep (164.8379, 188.2781) mm; " R", "1.2" over "0.5" and a closing space
# from x 158.8952 to 170.7806 mm, centred on the keep; the upper row on the
# keep, the lower LIMIT_ROW_PITCH under it, the shoulder under the lower
# row; the ink from 0.99 mm over a row's position (the lower row's foot at
# 184.74 mm) to 4.42 mm over it (the upper row's top at 192.70 mm).
_R12_RADIUS_KEEP = (0.1648379, 0.1882781)
_R12_RADIUS_STACK_X = (0.1588952, 0.1707806)
_R12_RADIUS_ROWS = (0.1882781, 0.1837524)
_ROW_INK = (0.00099, 0.00442)
# The two same-template callout rows: pd-latch-hook's RoundR "R5.75" over
# "FULL ROUND" (keep y 87.8837 mm, rows at 87.8837 and 82.3274 mm, 27.7861
# mm for the ten capitals; 20261015T223846658Z), and dt-cone-gear's FloorDia
# LIMIT over "ROOT ENVELOPE" (keep y 169.338 mm, limits at 172.1161 and
# 167.5904 mm, callout row and shoulder at 162.0342 mm; 20261015T201555493Z).
_LATCH_ROUND_ROWS = (0.0878837, 0.0823274)
_CAPITAL_PITCH = 0.0277861 / 10
_CONE_FLOOR_KEEP_Y = 0.169338
_CONE_FLOOR_ROWS = (0.1721161, 0.1675904, 0.1620342)
_NATIVE15_RADIUS_TEXT_BOX = Box(0.1604289, 0.1969558, 0.1845905, 0.2005212)
_NATIVE15_SPIGOT_TOP_WITNESS = ((0.1614, 0.198), (0.2003, 0.198))
_NATIVE15_SHOULDER_OVERRUN = 0.1860889 - _NATIVE15_RADIUS_TEXT_BOX.xmax
_GROOVE_CENTRE = (drawing._side_x(geom.GROOVE_X), drawing._side_y(geom.GROOVE_CENTRE_R))
_FACE_ON_AXIS = (drawing._side_x(geom.SPIGOT_FACE_X), drawing.SIDE_CENTER[1])
_SHEET_RADIUS = geom.GROOVE_RADIUS * drawing._S / 1000.0


def _proposed_radius_rows() -> tuple[Box, Box]:
    """The LIMIT stack and the FULL R row under it, printed ink, on the keep:
    r12's stack lifted half a callout pitch, the callout row a callout pitch
    under the lower limit at the capitals' pitch (wider than FULL R's real
    13.76 mm), both centred on the keep."""
    x, y = drawing.RADIUS_TEXT_XY
    upper = y + drawing.CALLOUT_ROW_PITCH / 2.0
    lower = upper - drawing.LIMIT_ROW_PITCH
    callout = lower - drawing.CALLOUT_ROW_PITCH
    stack_half = (_R12_RADIUS_STACK_X[1] - _R12_RADIUS_STACK_X[0]) / 2.0
    callout_half = len(_RADIUS_ROWS[-1]) * _CAPITAL_PITCH / 2.0
    return (
        Box(x - stack_half, lower + _ROW_INK[0], x + stack_half, upper + _ROW_INK[1]),
        Box(x - callout_half, callout + _ROW_INK[0], x + callout_half, callout + _ROW_INK[1]),
    )


def _proposed_radius_text_box() -> Box:
    """Everything the radius prints: the stack over the callout row."""
    stack, callout = _proposed_radius_rows()
    return Box(
        min(stack.xmin, callout.xmin),
        callout.ymin,
        max(stack.xmax, callout.xmax),
        stack.ymax,
    )


def test_radius_rows_replay_the_r12_latch_and_cone_gear_audits() -> None:
    # r12, two LIMIT rows: the upper on the keep, the shoulder under the
    # lower, the stack centred on the keep.
    assert _R12_RADIUS_ROWS[0] == _R12_RADIUS_KEEP[1]
    assert _R12_RADIUS_ROWS[0] - _R12_RADIUS_ROWS[1] == pytest.approx(
        drawing.LIMIT_ROW_PITCH, abs=1e-7
    )
    assert sum(_R12_RADIUS_STACK_X) / 2.0 == pytest.approx(_R12_RADIUS_KEEP[0], abs=1e-7)
    # A callout row one callout pitch under the last value row.
    assert _LATCH_ROUND_ROWS[0] - _LATCH_ROUND_ROWS[1] == pytest.approx(
        drawing.CALLOUT_ROW_PITCH, abs=1e-7
    )
    upper, lower, callout = _CONE_FLOOR_ROWS
    assert upper - lower == pytest.approx(drawing.LIMIT_ROW_PITCH, abs=1e-7)
    assert lower - callout == pytest.approx(drawing.CALLOUT_ROW_PITCH, abs=1e-7)
    # Under a LIMIT it lifts the limits half a callout pitch off the keep
    # and hangs the shoulder GROOVE_RADIUS_SHOULDER_DROP under it.
    assert upper - _CONE_FLOOR_KEEP_Y == pytest.approx(drawing.CALLOUT_ROW_PITCH / 2.0, abs=1e-6)
    assert _CONE_FLOOR_KEEP_Y - callout == pytest.approx(
        drawing.GROOVE_RADIUS_SHOULDER_DROP, abs=1e-6
    )
    assert drawing.GROOVE_RADIUS_SHOULDER_DROP == pytest.approx(0.0073039, abs=1e-7)
    # The callout row is the widest; the layout's run-in sizes it at the
    # glyph pitch, as wide as FULL R's 13.76 mm advance in the template's
    # 3.5 mm Century Gothic (the font's widths scale to every audit string
    # above at one factor: 27.7861 mm for FULL ROUND).
    assert _RADIUS_ROWS[-1] == spec.GROOVE_RADIUS_CALLOUT
    assert drawing.RADIUS_CALLOUT_GLYPHS == len(spec.GROOVE_RADIUS_CALLOUT) == 6
    assert drawing.RADIUS_TEXT_HALF_WIDTH == pytest.approx(0.01376 / 2.0, abs=1e-5)
    stack, row = _proposed_radius_rows()
    assert row.xmax - row.xmin > stack.xmax - stack.xmin


def _audit_line(stroke: tuple) -> AuditSegment:
    (x0, y0), (x1, y1) = stroke
    return AuditSegment(x0, y0, x1, y1, "ext-line")


def _proposed_extension_lines() -> dict[str, list]:
    """Every extension line the proposed side view draws near the radius
    text, from the model and the keeps (1 mm start gaps, 1 mm overrun)."""
    face_x, axis_y = _FACE_ON_AXIS
    od_low, od_high = drawing._side_y(-geom.SPIGOT_DIA / 2.0), drawing._side_y(geom.SPIGOT_DIA / 2.0)
    root_low, root_high = drawing.GROOVE_ROOT_SHEET_YS
    root_x = drawing.SIDE_KEEP["GrooveRootDia"][0]
    spigot_x = drawing.SIDE_KEEP["SpigotDia"][0]
    station_y = drawing.SIDE_KEEP["GrooveStation"][1] - _TEXT_OVER_LINE + 0.001
    under_y = drawing.SIDE_KEEP["BoreStation"][1] - _TEXT_OVER_LINE - 0.001
    overall_y = drawing.SIDE_KEEP["OverallLength"][1] - _TEXT_OVER_LINE - 0.001
    gap = drawing.EXTENSION_START_GAP
    return {
        "SpigotDia": [
            ((face_x + gap, od_low), (spigot_x + gap, od_low)),
            ((face_x + gap, od_high), (spigot_x + gap, od_high)),
        ],
        "GrooveRootDia": [
            ((_GROOVE_CENTRE[0] + gap, root_low), (root_x + gap, root_low)),
            ((_GROOVE_CENTRE[0] + gap, root_high), (root_x + gap, root_high)),
        ],
        "GrooveStation": [
            ((face_x, axis_y + drawing.GROOVE_STATION_FACE_GAP), (face_x, station_y)),
            (
                (_GROOVE_CENTRE[0], _GROOVE_CENTRE[1] + drawing.GROOVE_STATION_GAP),
                (_GROOVE_CENTRE[0], station_y),
            ),
        ],
        "BoreStation": [((face_x, axis_y - gap), (face_x, under_y))],
        "OverallLength": [((face_x, axis_y - gap), (face_x, overall_y))],
    }


# r12's printed Ø7.70 (300 dpi PNG): its ink, the Ø's stroke included.
_R12_ROOT_DIA_INK = Box(0.17391, 0.17010, 0.18694, 0.17797)


def test_radius_text_reads_in_open_air_over_the_root_dia_text() -> None:
    # r1 review: the shelf ran along the spigot Ø's extension at the OD.
    # r5 ruling: FULL R prints on its own row under the LIMIT.
    stack, callout = _proposed_radius_rows()
    box = _proposed_radius_text_box()
    face_x = _FACE_ON_AXIS[0]
    assert drawing.RADIUS_GLYPHS == len(_RADIUS_ROWS[0])
    assert drawing.SIDE_KEEP["GrooveRadius"] == drawing.RADIUS_TEXT_XY
    # Right of the face, under the root Ø's upper extension, left of its
    # dimension line: the upper limit's ink 1.9 mm under the extension.
    assert box.xmin > face_x + 0.003
    assert drawing.GROOVE_ROOT_SHEET_YS[1] - box.ymax == pytest.approx(0.0019, abs=5e-5)
    assert box.xmax < drawing.SIDE_KEEP["GrooveRootDia"][0] - 0.009
    # The callout row stands over the root Ø's text, never level with it:
    # 2.0 mm over r12's printed ink, 2.2 mm over the layout's text box.
    root_text = _dia_text_box("GrooveRootDia")
    assert callout.ymin - _R12_ROOT_DIA_INK.ymax == pytest.approx(0.0020, abs=5e-5)
    assert callout.ymin > root_text[3] + 0.002
    assert stack.ymin > callout.ymax
    extensions = _proposed_extension_lines()
    distances = {
        name: min(segment_box_distance(_audit_line(stroke), box) for stroke in strokes)
        for name, strokes in extensions.items()
    }
    assert min(distances.values()) >= 0.0018
    assert min(distances, key=distances.get) == "GrooveRootDia"
    # The shoulder passes over the root Ø's text.  Here it runs past the
    # capitals'-pitch row by native15's overrun, to 172.4 mm: 1.8 mm off
    # r12's Ø7.70 ink.  r12, the latch and the cone gear all ended theirs
    # at the widest row's right edge, which for FULL R's 13.76 mm is
    # 169.4 mm: 4.5 mm left of it.
    ink, _tip, _station, _centre = _material_radius_ink()
    shoulder = _audit_line(ink[-1])
    assert shoulder.y0 - _R12_ROOT_DIA_INK.ymax > 0.001
    assert segment_box_distance(shoulder, Box(*root_text)) > 0.001
    assert segment_box_distance(shoulder, _R12_ROOT_DIA_INK) > 0.0018
    real_end = drawing.RADIUS_TEXT_XY[0] + 0.01376 / 2.0
    assert _R12_ROOT_DIA_INK.xmin - real_end == pytest.approx(0.0045, abs=1e-4)


def _radius_ink(
    elbow: tuple[float, float], *, overrun: float = _NATIVE15_SHOULDER_OVERRUN
) -> tuple[list, tuple[float, float]]:
    """Native-style radius ink for an elbow: the radial line from the arc
    centre to the tip, on to the elbow, and the full shoulder from the elbow
    to past the text's right end."""
    run = math.dist(elbow, _GROOVE_CENTRE)
    tip = tuple(
        c + (e - c) * _SHEET_RADIUS / run for e, c in zip(elbow, _GROOVE_CENTRE)
    )
    box = _proposed_radius_text_box()
    shoulder = (elbow, (box.xmax + overrun, elbow[1]))
    return [(_GROOVE_CENTRE, tip), (tip, elbow), shoulder], tip


def _station_ink() -> list:
    top = drawing.SIDE_KEEP["GrooveStation"][1] - _TEXT_OVER_LINE + 0.001
    return [
        (
            (_GROOVE_CENTRE[0], _GROOVE_CENTRE[1] + drawing.GROOVE_STATION_GAP),
            (_GROOVE_CENTRE[0], top),
        ),
        (
            (_FACE_ON_AXIS[0], _FACE_ON_AXIS[1] + drawing.GROOVE_STATION_FACE_GAP),
            (_FACE_ON_AXIS[0], top),
        ),
        ((_FACE_ON_AXIS[0], top - 0.001), (_GROOVE_CENTRE[0], top - 0.001)),
    ]


def _material_radius_ink() -> tuple[list, tuple[float, float], list, tuple[float, float]]:
    ink, tip = _radius_ink(drawing.RADIUS_ELBOW_XY)
    return ink, tip, _station_ink(), _GROOVE_CENTRE


def _root_line_x() -> float:
    return drawing.SIDE_KEEP["GrooveRootDia"][0]


def test_predicted_radius_leader_lands_on_the_face_side_material_arc() -> None:
    ink, tip, station, centre = _material_radius_ink()
    assert tip == pytest.approx(drawing.RADIUS_PREDICTED_TIP_XY)
    assert math.dist(tip, centre) == pytest.approx(_SHEET_RADIUS)
    assert centre[0] < tip[0] < centre[0] + geom.GROOVE_HALF_OPENING * drawing._S / 1000.0
    assert drawing.GROOVE_ROOT_SHEET_YS[1] < tip[1] < drawing._side_y(geom.SPIGOT_DIA / 2.0)
    # The text runs 2 mm plus the widest row's run-in right of the face, its
    # shoulder 1 mm under the axis: the elbow 2 mm right of the face.  The
    # root Ø's line holds r1-r4's place, off their eight-glyph keep.
    assert drawing.RADIUS_TEXT_XY == pytest.approx((
        _FACE_ON_AXIS[0] + 0.002 + drawing.RADIUS_SHOULDER_RUN_IN,
        _FACE_ON_AXIS[1] - 0.001 + drawing.GROOVE_RADIUS_SHOULDER_DROP,
    ))
    assert drawing.RADIUS_ELBOW_XY == pytest.approx((
        drawing.RADIUS_TEXT_XY[0] - drawing.RADIUS_SHOULDER_RUN_IN,
        drawing.RADIUS_TEXT_XY[1] - drawing.GROOVE_RADIUS_SHOULDER_DROP,
    ))
    assert drawing.RADIUS_ELBOW_XY[0] - _FACE_ON_AXIS[0] == pytest.approx(0.002, abs=1e-9)
    assert drawing.RADIUS_ELBOW_XY[1] - _FACE_ON_AXIS[1] == pytest.approx(-0.001, abs=1e-9)
    eight_glyph_run_in = 8 * drawing._GLYPH_PITCH / 2.0 + drawing.RADIUS_SHOULDER_LEAD
    assert _root_line_x() == pytest.approx(
        _FACE_ON_AXIS[0] + 0.002 + eight_glyph_run_in + 8 * drawing._GLYPH_PITCH / 2.0 + 0.006
    )
    assert _root_line_x() == pytest.approx(0.1800072, abs=1e-7)  # r12's audit
    assert drawing._groove_radius_ink_problem(ink, tip, station, centre, _FACE_ON_AXIS) is None
    assert drawing._radius_leader_ink_problem(ink, tip, centre, _root_line_x()) is None
    assert drawing.GROOVE_STATION_GAP == 0.003
    assert drawing.RADIUS_STATION_CLEARANCE == 0.002
    assert drawing.RADIUS_INK_SLOP == 0.0004


@pytest.mark.parametrize("dy_mm", [-0.51, 0.0, 0.51])
@pytest.mark.parametrize("dx_mm", [-3.0, -1.4, 0.0, 1.08, 3.4, 5.0])
def test_radius_leader_holds_wherever_solidworks_runs_the_elbow(
    dx_mm: float, dy_mm: float
) -> None:
    # The run-in is an estimate for the three rows: at native15's lead the
    # elbow lands within a few mm of the prediction either way (r12's ran
    # 1.59 mm short of its text, 1.08 mm right of this estimate), and the
    # leader still lands on the material arc, radial, short of the root Ø's
    # line.  The drop too: half a millimetre either way (latch's unbanded
    # stack centres 0.51 mm lower on its keep than a LIMIT's).
    elbow = (
        drawing.RADIUS_ELBOW_XY[0] + dx_mm / 1000.0,
        drawing.RADIUS_ELBOW_XY[1] + dy_mm / 1000.0,
    )
    ink, tip = _radius_ink(elbow)
    centre = _GROOVE_CENTRE
    assert drawing._groove_radius_ink_problem(
        ink, tip, _station_ink(), centre, _FACE_ON_AXIS
    ) is None
    assert drawing._radius_leader_ink_problem(ink, tip, centre, _root_line_x()) is None


def test_radius_leader_accepts_a_leader_drawn_from_the_elbow_alone() -> None:
    ink, tip, _station, centre = _material_radius_ink()
    assert drawing._radius_leader_ink_problem(ink[1:], tip, centre, _root_line_x()) is None
    reversed_ink = [stroke[::-1] for stroke in reversed(ink)]
    assert drawing._radius_leader_ink_problem(reversed_ink, tip, centre, _root_line_x()) is None
    # Zero-length records print nothing.
    assert drawing._radius_leader_ink_problem(
        [*ink, ((0.0, 0.0), (0.0, 0.0))], tip, centre, _root_line_x()
    ) is None


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("no-shoulder", "no unique horizontal shoulder"),
        ("two-shoulders", "no unique horizontal shoulder"),
        ("no-leader", "no radial leader"),
        ("jogged-leader", "not on the radial line"),
        ("detached-shoulder", "does not run right"),
        ("shoulder-runs-left", "does not run right"),
        # r1's shelf: along the spigot Ø's extension at the OD.  The groove's
        # centre now sits on the OD, so that shelf is the radial line itself
        # and leaves the leader no shoulder.
        ("shelf-at-the-od", "no unique horizontal shoulder"),
        # A shoulder level with the root Ø's text (its ink tops out 2.03 mm
        # under the axis on r12).
        ("shoulder-by-the-root-dia-text", "not between the root Ø's text and its extension"),
        ("into-the-root-dia-line", "reaches the root Ø's dimension line"),
    ],
)
def test_radius_leader_refuses_bent_detached_or_crowded_ink(case: str, message: str) -> None:
    ink, tip, _station, centre = _material_radius_ink()
    elbow = ink[1][1]
    if case == "no-shoulder":
        ink.pop()
    elif case == "two-shoulders":
        ink.append(((elbow[0], elbow[1] + 0.001), (elbow[0] + 0.01, elbow[1] + 0.001)))
    elif case == "no-leader":
        ink = ink[2:]
    elif case == "jogged-leader":
        joint = (elbow[0] - 0.0007, elbow[1])
        ink[1] = (tip, joint)
        ink.insert(2, (joint, (elbow[0], elbow[1] + 0.0007)))
    elif case == "detached-shoulder":
        ink[2] = ((elbow[0] + 0.001, elbow[1]), ink[2][1])
    elif case == "shoulder-runs-left":
        ink[2] = (elbow, (elbow[0] - 0.02, elbow[1]))
    elif case == "shelf-at-the-od":
        ink, tip = _radius_ink((elbow[0], drawing._side_y(geom.SPIGOT_DIA / 2.0)))
    elif case == "shoulder-by-the-root-dia-text":
        ink, tip = _radius_ink((elbow[0], _FACE_ON_AXIS[1] - 0.0025))
    else:
        # A shoulder running on to 1 mm short of the root Ø's line.
        box = _proposed_radius_text_box()
        ink, tip = _radius_ink(elbow, overrun=_root_line_x() - 0.001 - box.xmax)
    problem = drawing._radius_leader_ink_problem(ink, tip, centre, _root_line_x())
    assert problem is not None and message in problem


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("retry12-arrow", "not on the face-side material arc"),
        ("opposite-arc", "not on the face-side material arc"),
        ("off-circle", "not on the face-side material arc"),
        ("empty", "no attached leader ink"),
        ("disconnected", "no attached leader ink"),
        ("missing-centre-witness", "no unique witness at the groove arc centre"),
        ("stale-centre-gap", "groove arc centre witness gap did not reach"),
        ("near-foot", "not clear of the station's groove arc centre witness"),
        ("crossing", "not clear of the station's groove arc centre witness"),
        ("missing-face-witness", "no unique witness at the spigot face"),
        ("face-witness-down-the-face", "spigot face witness gap did not reach"),
        ("crossing-face-witness", "not clear of the station's spigot face witness"),
    ],
)
def test_radius_ink_refuses_extension_air_detachment_and_station_ambiguity(
    case: str, message: str
) -> None:
    ink, tip, station, centre = _material_radius_ink()
    if case == "retry12-arrow":
        tip = (centre[0] + 0.00454, centre[1] + 0.00156)  # native12: past the mouth
    elif case == "opposite-arc":
        tip = (2.0 * centre[0] - tip[0], tip[1])
    elif case == "off-circle":
        tip = (tip[0] + 0.001, tip[1])
    elif case == "empty":
        ink = []
    elif case == "disconnected":
        ink = [((0.170, 0.185), (0.180, 0.185))]
    elif case == "missing-centre-witness":
        station.pop(0)
    elif case == "stale-centre-gap":
        station[0] = ((centre[0], centre[1] + 0.001), station[0][1])
    elif case == "near-foot":
        ink.append((centre, (centre[0], centre[1] + 0.0015)))
    elif case == "crossing":
        ink.append((centre, (centre[0], centre[1] + 0.004)))
    elif case == "missing-face-witness":
        station.pop(1)
    elif case == "face-witness-down-the-face":
        station[1] = (
            (_FACE_ON_AXIS[0], _FACE_ON_AXIS[1] + drawing.EXTENSION_START_GAP),
            station[1][1],
        )
    else:
        y = _FACE_ON_AXIS[1] + drawing.GROOVE_STATION_FACE_GAP + 0.003
        ink.append(((_FACE_ON_AXIS[0] - 0.002, y), (_FACE_ON_AXIS[0] + 0.002, y)))
    problem = drawing._groove_radius_ink_problem(ink, tip, station, centre, _FACE_ON_AXIS)
    assert problem is not None and message in problem


def _native15_radius_spigot_dump(*, proposed: bool = False) -> dict:
    """Replay native15's actual COM rows, PDF glyph boxes and both Ø9
    witnesses, or the proposed layout's, built from the model and keeps."""

    def line(stroke: tuple, *, z: float = 0.0004) -> list:
        (x0, y0), (x1, y1) = stroke
        return [0.0, 0.0, 0.0, 0.0, x0, y0, z, x1, y1, z]

    if proposed:
        keep = drawing.RADIUS_TEXT_XY
        radius_ink, tip, _station, centre = _material_radius_ink()
        box = _proposed_radius_text_box()
        radius_text, radius_glyphs = f" {' '.join(_RADIUS_ROWS)} ", "".join(_RADIUS_ROWS)
        spigot_x = drawing.SIDE_KEEP["SpigotDia"][0]
        spigot_y = drawing.SIDE_KEEP["SpigotDia"][1]
        spigot_extensions = _proposed_extension_lines()["SpigotDia"]
        spigot_value = f" {geom.SPIGOT_DIA:.2f} "
    else:
        keep = _NATIVE15_RADIUS_KEEP
        centre = (0.147, 0.1988)
        tip = (0.1516289, 0.1975297)
        radius_ink = [
            (tip, (0.1571236, 0.1960219)),
            (centre, tip),
            ((0.1571236, 0.1960219), (0.1860889, 0.1960219)),
        ]
        box = _NATIVE15_RADIUS_TEXT_BOX
        radius_text, radius_glyphs = " R1.20 ±0.05 ", "R1.20±0.05"
        spigot_x, spigot_y = 0.1993, 0.185
        spigot_extensions = [((0.1614, 0.162), (0.2003, 0.162)), _NATIVE15_SPIGOT_TOP_WITNESS]
        spigot_value = "9.00 ±0.05 "
    od_low, od_high = spigot_extensions[0][0][1], spigot_extensions[1][0][1]
    direction = tuple((tip[i] - centre[i]) / math.dist(tip, centre) for i in range(2))
    radius = {
        "type": 4, "name": "GrooveRadius", "visible": 1, "owner_type": 0,
        "pos": [*keep, 0.0004],
        "display": {
            "lines": [line(stroke) for stroke in radius_ink],
            "arrows": [[*tip, 0.0004, *direction, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, -1.0]],
            "texts": [{
                "t": radius_text, "pos": [box.xmin - 0.0015, radius_ink[-1][0][1], 0.0004],
                "h": 0.0035, "ref": 1, "ang": 0.0, "w": box.xmax - box.xmin + 0.003,
            }],
        },
        "dim": {"hole_callout": False},
    }
    spigot = {
        "type": 4, "name": "SpigotDia", "visible": 1, "owner_type": 0,
        "pos": [spigot_x, spigot_y, -0.0004],
        "display": {
            "lines": [line(stroke, z=-0.0004) for stroke in [
                *spigot_extensions,
                ((spigot_x, od_low), (spigot_x, spigot_y - 0.0028)),
                ((spigot_x, od_high), (spigot_x, spigot_y + 0.0028)),
            ]],
            "arrows": [
                [spigot_x, od_low, -0.0004, 0.0, 1.0, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0],
                [spigot_x, od_high, -0.0004, 0.0, -1.0, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0],
            ],
            "texts": [
                {"t": " ", "pos": [spigot_x - 0.0149, spigot_y - 0.0027514, -0.0004], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0012931},
                {"t": "<MOD-DIAM>", "pos": [spigot_x - 0.013618, spigot_y - 0.0028049, -0.0004], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0052784},
                {"t": spigot_value, "pos": [spigot_x - 0.0083396, spigot_y - 0.0027514, -0.0004], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0232507},
            ],
        },
        "dim": {"hole_callout": False},
    }
    spigot_half = 0.0045 * len(spigot_value.strip()) / 4.0
    spigot_glyphs = (
        [
            spigot_value.strip(),
            spigot_x - spigot_half,
            spigot_y - 0.0018175,
            spigot_x + spigot_half,
            spigot_y + 0.0017479,
        ]
        if proposed
        else ["9.00±0.05", 0.1911891, 0.1831825, 0.2127127, 0.1867479]
    )
    return {
        "schema": 1, "stem": drawing.PART_STEM, "sheet": "Sheet1",
        "width": 0.4318, "height": 0.2794,
        "zone": {"left": 0.0127, "right": 0.0127, "bottom": 0.0127, "top": 0.0127},
        "title_block": [0.216, 0.0, 0.4318, 0.066],
        "views": [{
            "name": "Drawing View1", "type": 7, "orientation": "*Top", "pictorial": False,
            "outline": [0.084012, 0.155362, 0.165988, 0.204638],
            "annotations": [radius, spigot],
        }],
        "sheet_annotations": [], "tables": [], "read_errors": {},
        "ink": {"spans": [
            [radius_glyphs, box.xmin, box.ymin, box.xmax, box.ymax],
            spigot_glyphs,
        ], "strokes": []},
    }


def _write_fixture_audit(tmp_path: Path, dump: dict) -> tuple[Path, dict]:
    content, _gating = audit_report(drawing.PART_STEM, LayoutAuditMode.REPORT, [dump])
    report = tmp_path / f"{drawing.PART_STEM}.json"
    report.write_text(json.dumps(content), encoding="utf-8")
    return report, content


def test_real_text_crossing_is_not_waived_by_a_report_severity_label(tmp_path: Path) -> None:
    report, content = _write_fixture_audit(tmp_path, _native15_radius_spigot_dump())
    (crossing,) = [finding for finding in content["findings"] if finding["kind"] == "text-on-line"]
    crossing["severity"] = "advisory"
    content["summary"]["gating"] -= 1
    report.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(RuntimeError, match="text-on-line"):
        drawing._enforce_fixture_text_on_line(report)


def test_native15_actual_radius_text_crossing_fails_the_local_report_gate(tmp_path: Path) -> None:
    dump = _native15_radius_spigot_dump()
    findings = audit_dump(dump)
    (crossing,) = [finding for finding in findings if finding.kind == "text-on-line"]
    assert crossing.a.startswith("dim GrooveRadius ")
    assert crossing.b.startswith("dim SpigotDia ")
    assert "'s ext-line (161.4,198.0)->(200.3,198.0)mm" in crossing.detail
    assert crossing.extra["overlap_mm"] == pytest.approx(23.1905)
    report, content = _write_fixture_audit(tmp_path, dump)
    assert content["mode"] == "report"
    with pytest.raises(RuntimeError, match="text-on-line.*\\n.*GrooveRadius.*SpigotDia"):
        drawing._enforce_fixture_text_on_line(report)


def test_proposed_layout_passes_the_same_gate_without_waiving_view_edge_false_positive(
    tmp_path: Path,
) -> None:
    report, content = _write_fixture_audit(tmp_path, _native15_radius_spigot_dump(proposed=True))
    assert not any(finding["kind"] == "text-on-line" for finding in content["findings"])
    assert any(finding["kind"] == "view-edges-missing" for finding in content["findings"])
    drawing._enforce_fixture_text_on_line(report)


@pytest.mark.parametrize("sheet", ["Sheet1", "AnotherSheet"])
def test_local_text_gate_refuses_unrelated_dimension_names_and_text_on_any_sheet(
    tmp_path: Path, sheet: str,
) -> None:
    dump = _native15_radius_spigot_dump()
    dump["sheet"] = sheet
    target, source = dump["views"][0]["annotations"]
    target["name"] = "UnrelatedWidth"
    target["display"]["texts"][0]["t"] = " 42.00 "
    dump["ink"]["spans"][0][0] = "42.00"
    source["name"] = "CounterboreDepth"
    report, content = _write_fixture_audit(tmp_path, dump)
    (crossing,) = [finding for finding in content["findings"] if finding["kind"] == "text-on-line"]
    assert crossing["sheet"] == sheet
    assert "UnrelatedWidth" in crossing["a"] and "CounterboreDepth" in crossing["b"]
    with pytest.raises(RuntimeError, match="UnrelatedWidth.*CounterboreDepth"):
        drawing._enforce_fixture_text_on_line(report)


@pytest.mark.parametrize("case", [
    "missing-file", "invalid-json", "not-object", "schema", "stem", "mode",
    "missing-findings", "findings-type", "finding-type", "kind-type", "detail-type",
    "finding-stem", "finding-sheet", "finding-severity", "sheets-type", "empty-sheets",
    "sheet-type", "sheet-stem", "sheet-name", "duplicate-sheet", "summary-type",
    "missing-counts", "counts-type", "counts-value", "count-mismatch", "sheet-count",
    "gating-count", "bool-schema", "bool-count", "bool-sheet-count", "bool-gating-count",
])
def test_local_text_gate_fails_loud_on_missing_malformed_or_incomplete_reports(
    tmp_path: Path, case: str,
) -> None:
    report, content = _write_fixture_audit(tmp_path, _native15_radius_spigot_dump())
    if case == "missing-file":
        report.unlink()
    elif case == "invalid-json":
        report.write_text("{", encoding="utf-8")
    else:
        if case == "not-object":
            content = []
        elif case in ("schema", "bool-schema"):
            content["schema"] = True if case == "bool-schema" else 99
        elif case in ("stem", "mode"):
            content[case] = "unrelated"
        elif case == "missing-findings":
            content.pop("findings")
        elif case == "findings-type":
            content["findings"] = {}
        elif case == "finding-type":
            content["findings"][0] = None
        elif case in ("kind-type", "detail-type"):
            content["findings"][0][case.removesuffix("-type")] = None
        elif case.startswith("finding-"):
            content["findings"][0][case.removeprefix("finding-")] = "unrelated"
        elif case == "sheets-type":
            content["sheets"] = {}
        elif case == "empty-sheets":
            content["sheets"] = []
        elif case == "sheet-type":
            content["sheets"][0] = None
        elif case == "sheet-stem":
            content["sheets"][0]["stem"] = "unrelated"
        elif case == "sheet-name":
            content["sheets"][0]["sheet"] = None
        elif case == "duplicate-sheet":
            content["sheets"].append(content["sheets"][0])
        elif case == "summary-type":
            content["summary"] = []
        elif case == "missing-counts":
            content["summary"].pop("findings")
        elif case == "counts-type":
            content["summary"]["findings"] = []
        elif case in ("counts-value", "bool-count"):
            content["summary"]["findings"]["text-on-line"] = True if case == "bool-count" else "1"
        elif case == "count-mismatch":
            content["findings"].pop(0)
        elif case in ("sheet-count", "bool-sheet-count"):
            content["summary"]["sheets"] = True if case == "bool-sheet-count" else 2
        elif case in ("gating-count", "bool-gating-count"):
            content["summary"]["gating"] = True if case == "bool-gating-count" else 0
        else:
            raise AssertionError(case)
        report.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises((RuntimeError, OSError, json.JSONDecodeError)):
        drawing._enforce_fixture_text_on_line(report)


_Y_BORE_CYLINDER = (0.0, 0.004, 0.0, 0.0, 1.0, 0.0, geom.ROD_BORE_DIA / 2000.0)


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_rod_bore_cylinder_accepts_only_the_model_y_axis(sign: float) -> None:
    params = (*_Y_BORE_CYLINDER[:4], sign, *_Y_BORE_CYLINDER[5:])
    assert drawing._is_rod_bore_cylinder(params)


@pytest.mark.parametrize(
    "params",
    [
        (),
        _Y_BORE_CYLINDER[:6],
        (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, geom.TAP_DRILL_DIA / 2000.0),
        (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, geom.ROD_BORE_DIA / 2000.0),
        (0.0001, *_Y_BORE_CYLINDER[1:]),
        (*_Y_BORE_CYLINDER[:6], geom.SPIGOT_DIA / 2000.0),
        (*_Y_BORE_CYLINDER[:6], float("nan")),
    ],
)
def test_rod_bore_cylinder_refuses_the_axial_tap_wrong_radius_and_offset(params: tuple) -> None:
    assert not drawing._is_rod_bore_cylinder(params)


def _bore_axis_corners() -> tuple[tuple[float, float], tuple[float, float]]:
    x, y = drawing.END_CENTER
    return ((x - drawing._END_HALF_WIDTH, y), (x + drawing._END_HALF_WIDTH, y))


def test_bore_axis_ink_spans_both_corners_horizontally_in_the_rotated_frame() -> None:
    corners = _bore_axis_corners()
    assert drawing._bore_axis_ink_problem([corners], corners) is None


@pytest.mark.parametrize("case", ["empty", "tap-cross", "vertical", "offset", "overshoot"])
def test_bore_axis_ink_refuses_a_tap_mark_or_false_axis(case: str) -> None:
    corners = _bore_axis_corners()
    x, y = drawing.END_CENTER
    ink = {
        "empty": [],
        "tap-cross": [((x - 0.003, y), (x + 0.003, y))],
        "vertical": [((x, y - drawing._END_HALF_WIDTH), (x, y + drawing._END_HALF_WIDTH))],
        "offset": [((corners[0][0], y + 0.001), (corners[1][0], y + 0.001))],
        "overshoot": [((x - 0.04, y), (x + 0.04, y))],
    }[case]
    assert drawing._bore_axis_ink_problem(ink, corners) is not None
