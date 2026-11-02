"""Offline run-out, full-thread, wall, tip and loop contracts for the upper clamp.

Owner rulings 2026-10-27 (#1951): MHA-SM-04's 1/4-28 UNF thread runs into
the BLIND 1/4-28 UNF-2B tap in the solid Ø.500 end piece of MHA-SM-01's 1/2
in arm, and the MHA-SM-VN-51 loop is clamped on the screw's plain Ø.250 body.
The 2026-09-21 clamp rulings stand.  The arm-end counterbore clears the
screw's die run-out with the loop clamped coil-bound (codjiflo P1 on #1997).
Two owner minors stand against unchanged checks: the counterbore wall
(sm-gooseneck RV-01) and the head's retention (sm-gooseneck-spring-screw
RV-01).  Both sheets print decimal inch (#290): every term is charged at the
limits the sheets print.
"""

from __future__ import annotations

import math
import runpy
from pathlib import Path

import pytest

import _config
import machinist_exceptions
import sm_gooseneck_geom as gooseneck
import sm_gooseneck_spec as gooseneck_spec
import sm_gooseneck_spring_joint as joint
import sm_gooseneck_spring_screw_geom as screw
import sm_gooseneck_spring_screw_spec as screw_spec
import sm_vn_counter_spring_stock_geom as spring
from _buildgraph import config_files_of

ONE_POINT_FIVE_D = 1.5 * screw.MAJOR_DIA
IN = 25.4
# MHA-SM-04 as its inch sheet prints it.
SCREW_LENGTH_LOWER, SCREW_LENGTH_UPPER = screw.PRINTED_BANDS["UnderHeadLength"]
SCREW_HEAD_DIA_MIN = screw.HEAD_DIA + screw.PRINTED_BANDS["HeadDia"][0]
SCREW_HEAD_DIA_MAX = screw.HEAD_DIA + screw.PRINTED_BANDS["HeadDia"][1]
SCREW_BODY_DIA_MIN = screw.BODY_DIA + screw.PRINTED_BANDS["BodyDia"][0]
SCREW_BODY_DIA_MAX = screw.BODY_DIA + screw.PRINTED_BANDS["BodyDia"][1]
SCREW_RELIEF_MIN = (
    screw.HEAD_RELIEF_CHAMFER + screw.PRINTED_BANDS["HeadReliefChamfer"][0]
)
SCREW_RELIEF_MAX = (
    screw.HEAD_RELIEF_CHAMFER + screw.PRINTED_BANDS["HeadReliefChamfer"][1]
)
# The inch title block's .010 edge break.
EDGE_BREAK = 0.010 * IN


def test_clamp_preload_binds_the_loop_coil_bound() -> None:
    rise = spring.LOOP_TURNS * spring.WIRE_DIA_MM  # one wire per turn, bound
    assert joint.CLAMPED_GAP_MAX == pytest.approx(rise + spring.WIRE_DIA_MM)
    assert joint.CLAMPED_GAP_MAX == pytest.approx(4.40, abs=0.005)
    # Two stacked pull-side layers on the body, inside both faces.
    assert joint.CLAMPED_GAP_MIN == pytest.approx(2.0 * spring.WIRE_DIA_MM)
    rate = 82_700.0 * 1.6002**4 / (8.0 * 11.0998**3 * 1.75)
    assert joint.LOOP_AXIAL_RATE == pytest.approx(rate)
    assert joint.LOOP_BIND_FORCE == pytest.approx(rate * (4.88061 - 4.40055))
    least_preload = min(
        screw_spec.clamp_preload_n(mu) for mu in screw_spec.CLAMP_FRICTIONS
    )
    assert least_preload == pytest.approx(231.0, abs=0.5)
    assert joint.LOOP_BIND_FORCE < 0.1 * least_preload


def _screw_play() -> float:
    # The screw in the 2B thread: tap major + root oversize against the 2A
    # major minimum (crest to root).
    return (screw.MAJOR_DIA + 0.025 - screw.THREAD_MAJOR_2A_MIN) / 2.0


def test_screw_tilts_by_its_play_over_the_shortest_engagement() -> None:
    # The play on opposite sides at the two ends of the 1.5D floor
    # (ENGAGEMENT_MIN is at least that).
    tilt = math.atan(2.0 * _screw_play() / ONE_POINT_FIVE_D)
    assert joint.SCREW_RADIAL_PLAY_MAX == pytest.approx(_screw_play())
    assert joint.SCREW_TILT_MAX == pytest.approx(tilt)
    assert math.degrees(tilt) == pytest.approx(1.296, abs=5e-4)
    assert joint.ENGAGEMENT_MIN >= ONE_POINT_FIVE_D
    # On the screw's axis the tilted head face stands closer than the
    # stacked passes allow where they bear, at most LOOP_PASS_RADIUS_MAX off
    # the axis (test_rocked_loop_keeps_the_gap_floor_and_bears_on_the_body).
    pass_radius = (
        spring.COIL_MEAN_RADIUS_MM - (spring.EYE_ID_MM - SCREW_BODY_DIA_MAX) / 2.0
    )
    assert joint.LOOP_PASS_RADIUS_MAX == pytest.approx(pass_radius)
    axis_gap = joint.CLAMPED_GAP_MIN - math.tan(tilt) * pass_radius
    assert joint.CLAMPED_AXIS_GAP_MIN == pytest.approx(axis_gap)
    assert axis_gap == pytest.approx(3.111, abs=5e-4)
    # At the end face: the deepest floor and its .010 break past the
    # receiver's first full thread.
    face = _screw_play() + (joint.COUNTERBORE_DEPTH_MAX + EDGE_BREAK) * math.tan(tilt)
    assert joint.SCREW_FACE_OFFSET_MAX == pytest.approx(face)
    assert face == pytest.approx(0.178, abs=5e-4)


def test_counterbore_depth_clears_the_deepest_runout_with_margin() -> None:
    # The tilted full-thread circle's low side dips past its axis station,
    # from the ".225 MAX" MHA-SM-04 prints.
    full_thread = screw.PRINTED_LIMITS["FullThread"]
    assert full_thread == pytest.approx(0.225 * IN)
    dip = screw.MAJOR_DIA / 2.0 * math.sin(joint.SCREW_TILT_MAX)
    deepest = full_thread - joint.CLAMPED_AXIS_GAP_MIN + dip
    free = full_thread - gooseneck.SPRING_EYE_GAP + dip
    assert joint.SCREW_RUNOUT_INTRUSION_MAX == pytest.approx(deepest)
    assert joint.SCREW_RUNOUT_INTRUSION_FREE_MAX == pytest.approx(free)
    assert (free, deepest) == pytest.approx((0.906, 2.676), abs=5e-4)
    assert joint.COUNTERBORE_DEPTH_MIN - deepest >= joint.COUNTERBORE_RUNOUT_MARGIN_MIN
    # The printed LIMIT .108/.112 holds the calibrated 2.78 model.
    assert (
        joint.COUNTERBORE_DEPTH_MIN / IN,
        joint.COUNTERBORE_DEPTH_MAX / IN,
    ) == pytest.approx((0.108, 0.112))
    assert joint.COUNTERBORE_DEPTH_MIN < joint.COUNTERBORE_DEPTH == 2.78
    assert joint.COUNTERBORE_DEPTH < joint.COUNTERBORE_DEPTH_MAX


def test_counterbore_clears_the_fat_runout_radially() -> None:
    clearance = (
        joint.COUNTERBORE_DIA_MIN / 2.0  # its printed LIMIT's .275
        - screw.MAJOR_DIA / 2.0  # run-out crest, at or above the 2A major max
        - joint.COUNTERBORE_AXIS_OFFSET_MAX  # MHA-SM-01 note, to the tap
        - joint.SCREW_FACE_OFFSET_MAX  # the tilted screw, at the end face
    )
    assert joint.COUNTERBORE_DIA_MIN / IN == pytest.approx(0.275)
    assert joint.COUNTERBORE_DIA_MIN <= joint.COUNTERBORE_DIA == 7.00
    assert joint.RUNOUT_RADIAL_CLEARANCE_MIN == pytest.approx(clearance)
    assert clearance == pytest.approx(0.038, abs=5e-4)
    # Ø6.90 would rub once the tilt counts: the reason the counterbore is Ø7.00.
    assert (6.90 - screw.MAJOR_DIA) / 2.0 - joint.COUNTERBORE_AXIS_OFFSET_MAX - (
        joint.SCREW_FACE_OFFSET_MAX
    ) < 0.0


def test_counterbore_floor_corner_round_clears_the_runout() -> None:
    # The run-out's crest corner, u above the floor and v off the wall, inside
    # the R.004 MAX round's square: its clearance is the round's radius less
    # the distance to the round's centre.
    rf = joint.COUNTERBORE_FLOOR_CORNER_R_MAX
    assert rf == pytest.approx(0.004 * IN)
    u = joint.COUNTERBORE_DEPTH_MIN - joint.SCREW_RUNOUT_INTRUSION_MAX
    v = joint.RUNOUT_RADIAL_CLEARANCE_MIN
    assert 0.0 < u < rf and 0.0 < v < rf
    exact = rf - math.hypot(u - rf, v - rf)
    assert joint.RUNOUT_FLOOR_CORNER_CLEARANCE_MIN == pytest.approx(exact)
    assert exact == pytest.approx(0.029, abs=5e-4)
    # The title block's INSIDE CORNERS R.040 MAX would stop the screw.
    assert joint._fillet_clearance(u, v, 0.040 * IN, 0.0) < 0.0
    # Printed by the model's own radial dimension, R.004 MAX from sharp up.
    assert joint.COUNTERBORE_FLOOR_CORNER_R_BAND == (0.0, -rf)
    assert joint.COUNTERBORE_FLOOR_CORNER_R_TOL_TYPE == 6  # swTolMAX
    assert (
        "CounterboreFloorCornerR"
        in gooseneck_spec.DRAWING_DIMENSIONS["CounterboreProfile"]
    )
    # The corner says what it clears (rule 4); the counterbore Ø's block,
    # under it, names whose run-out (machinist review r8).
    assert (
        gooseneck_spec.DIMENSION_CALLOUTS_BY_NAME["CounterboreFloorCornerR"]
        == gooseneck_spec.COUNTERBORE_FLOOR_CALLOUT
    )
    assert gooseneck_spec.COUNTERBORE_FLOOR_CALLOUT.startswith("CLEARS RUN-OUT;\n")
    assert gooseneck_spec.COUNTERBORE_DIA_CALLOUT.startswith(
        f"MIN CLEARS {gooseneck_spec.SCREW_NUMBER}\nRUN-OUT"
    )


def test_receiver_full_thread_past_the_counterbore_is_1_5d() -> None:
    # The shortest screw at the free gap, less its 1.5-pitch chamfered end,
    # against the blind tap's least full thread: the screw governs.
    screw_full = (
        screw.LENGTH + SCREW_LENGTH_LOWER - gooseneck.SPRING_EYE_GAP - 1.5 * screw.PITCH
    )
    tap_full = joint.TAP_THREAD_DEPTH - joint.TAP_DEPTH_BAND
    assert joint.FULL_THREAD_REACH_MIN == pytest.approx(screw_full)
    assert screw_full < tap_full
    full_thread = (
        min(screw_full, tap_full)
        - joint.COUNTERBORE_DEPTH_MAX  # deepest counterbore
        - EDGE_BREAK  # title-block break on the tap edge at the counterbore floor
    )
    assert joint.ENGAGEMENT_MIN == pytest.approx(full_thread)
    assert (joint.ENGAGEMENT_NOMINAL, joint.ENGAGEMENT_MIN) == pytest.approx(
        (10.225, 9.964), abs=5e-4
    )
    assert joint.ENGAGEMENT_MIN >= ONE_POINT_FIVE_D == pytest.approx(9.525)
    # Full thread starts inside the counterbore at either gap, so the mated
    # length is the receiver's.
    assert joint.SCREW_RUNOUT_INTRUSION_FREE_MAX < joint.COUNTERBORE_DEPTH_MIN
    assert joint.SCREW_RUNOUT_INTRUSION_MAX < joint.COUNTERBORE_DEPTH_MIN


def test_deepest_tip_stays_inside_the_blind_full_thread() -> None:
    # The longest screw at the least gap on its axis sits deepest.
    deepest_tip = screw.LENGTH + SCREW_LENGTH_UPPER - joint.CLAMPED_AXIS_GAP_MIN
    # The tap's depths run from the counterbore floor, its start face.
    shallowest_thread = (
        joint.COUNTERBORE_DEPTH_MIN
        + joint.TAP_THREAD_DEPTH_FROM_FLOOR
        - joint.TAP_DEPTH_BAND
    )
    assert joint.CLAMPED_SCREW_REACH_MAX == pytest.approx(deepest_tip)
    assert joint.TIP_THREAD_MARGIN_MIN == pytest.approx(shallowest_thread - deepest_tip)
    assert joint.TIP_THREAD_MARGIN_MIN == pytest.approx(0.520, abs=5e-4)
    assert joint.TIP_THREAD_MARGIN_MIN > 0.0
    assert joint.TAP_SPEC.end == "blind"
    assert joint.TAP_SPEC.size == screw.THREAD_SIZE == "1/4-28"
    assert joint.TAP_SPEC.thread_class == "2B"


def test_bottoming_tap_lead_stays_inside_the_drill() -> None:
    # A bottoming tap's 1.5-pitch lead past the deepest full thread, inside
    # the shallowest full-Ø drill; the full-Ø drill stays in the head.
    # Both depths run from the counterbore floor, so its band cancels.
    lead_end = (
        joint.TAP_THREAD_DEPTH_FROM_FLOOR + joint.TAP_DEPTH_BAND + 1.5 * screw.PITCH
    )
    shallowest_drill = joint.TAP_DRILL_DEPTH_FROM_FLOOR - joint.TAP_DEPTH_BAND
    assert joint.TAP_LEAD_DRILL_MARGIN_MIN == pytest.approx(shallowest_drill - lead_end)
    assert joint.TAP_LEAD_DRILL_MARGIN_MIN == pytest.approx(0.671, abs=5e-4)
    assert joint.TAP_LEAD_DRILL_MARGIN_MIN >= 0.0
    # Both depths print .XX on the inch sheet, modelled on that grid.
    assert (
        joint.TAP_THREAD_DEPTH_FROM_FLOOR / IN,
        joint.TAP_DRILL_DEPTH_FROM_FLOOR / IN,
        joint.TAP_DEPTH_BAND / IN,
    ) == pytest.approx((0.58, 0.68, 0.01))
    # The full-Ø drill stays inside the SHORTEST head: .85 at its .XX band.
    assert joint.PLUG_HEAD_LENGTH_MIN == pytest.approx(0.84 * IN)
    assert (
        joint.COUNTERBORE_DEPTH_MAX
        + joint.TAP_DRILL_DEPTH_FROM_FLOOR
        + joint.TAP_DEPTH_BAND
        <= joint.PLUG_HEAD_LENGTH_MIN
    )


def _smallest_end_piece_radius() -> float:
    return 0.49 * IN / 2.0  # the head Ø's .50 at its .XX lower limit


def test_tap_wall_meets_the_080_target_at_the_full_worst_case() -> None:
    largest_tap_major = screw.MAJOR_DIA + 0.025  # basic major + root oversize
    # Hole drilled after braze, head OD turned before: different setups.
    runoff = (
        joint.COUNTERBORE_DEPTH_MAX
        + joint.TAP_THREAD_DEPTH_FROM_FLOOR
        + joint.TAP_DEPTH_BAND
        + 1.5 * screw.PITCH
    ) * math.tan(math.radians(0.3))
    worst_wall = (
        _smallest_end_piece_radius()
        - largest_tap_major / 2.0
        - joint.THREAD_AXIS_OFFSET_MAX  # MHA-SM-01 note
        - joint.DRILL_WANDER_MAX  # MHA-SM-01 note
        - runoff
        - 2.0 * EDGE_BREAK  # tap edge + head OD edge, title block
    )
    assert joint.EDGE_BREAK == pytest.approx(EDGE_BREAK)
    assert joint.TAP_ROOT_OVERSIZE == 0.025
    assert joint.THREAD_AXIS_OFFSET_MAX == pytest.approx(0.006 * IN)
    assert joint.DRILL_RUNOFF_MAX == pytest.approx(runoff)
    assert joint.PLUG_WALL_MIN == pytest.approx(worst_wall)
    assert worst_wall == pytest.approx(2.175, abs=5e-4)
    assert worst_wall >= joint.PLUG_WALL_TARGET == 0.080 * IN


def test_drill_point_shank_wall_meets_the_080_target_at_the_full_worst_case() -> None:
    # The deepest drill's 118-degree point crosses the head's end into the
    # shank: its cone radius there, at the SHORTEST head (.XX band, codjiflo
    # P1 on #1997), against the shank's lower printed limit (.363 at .XXX).
    drill_r = (joint.TAP_DRILL_DIA + 0.004 * IN) / 2.0  # DRILLED HOLES +.004
    point_h = drill_r / math.tan(math.radians(59.0))
    tip = (
        joint.COUNTERBORE_DEPTH_MAX
        + joint.TAP_DRILL_DEPTH_FROM_FLOOR
        + joint.TAP_DEPTH_BAND
        + point_h
    )
    cone_r = drill_r * (tip - 0.84 * IN) / point_h
    assert 0.0 < cone_r < drill_r
    worst_wall = (
        (0.363 - 0.005) * IN / 2.0
        - cone_r
        - joint.THREAD_AXIS_OFFSET_MAX
        - joint.DRILL_WANDER_MAX
        - tip * math.tan(math.radians(0.3))
    )
    assert joint.DRILL_POINT_RADIUS_AT_SHANK == pytest.approx(cone_r, abs=1e-4)
    assert joint.DRILL_POINT_SHANK_WALL_MIN == pytest.approx(worst_wall, abs=1e-4)
    assert worst_wall == pytest.approx(3.029, abs=5e-4)
    assert worst_wall >= joint.PLUG_WALL_TARGET


def test_counterbore_wall_holds_the_floor_and_declares_its_minor() -> None:
    largest_cbore = 0.279 * IN  # its printed LIMIT .279/.275
    # Counterbore cut after braze, head OD turned before: different setups.
    runoff = joint.COUNTERBORE_DEPTH_MAX * math.tan(math.radians(0.3))
    worst_wall = (
        _smallest_end_piece_radius()
        - largest_cbore / 2.0
        - joint.THREAD_AXIS_OFFSET_MAX  # MHA-SM-01 note, tap to tube
        - joint.COUNTERBORE_AXIS_OFFSET_MAX  # MHA-SM-01 note, to the tap
        - runoff
        - 2.0 * EDGE_BREAK  # counterbore mouth + head OD edge, title block
    )
    assert joint.COUNTERBORE_DIA_MAX == pytest.approx(largest_cbore)
    assert joint.COUNTERBORE_WALL_MIN == pytest.approx(worst_wall)
    assert worst_wall / IN == pytest.approx(0.0749, abs=5e-5)
    assert joint.PLUG_WALL_FLOOR == pytest.approx(0.060 * IN)
    assert joint.PLUG_WALL_FLOOR <= worst_wall < joint.PLUG_WALL_TARGET
    # The sheet states it in inches, floored, next to its feature (rule 20).
    assert joint.COUNTERBORE_WALL_CALLOUT_MIN == 0.074
    assert joint.COUNTERBORE_WALL_CALLOUT_MIN * IN <= worst_wall
    callout = "C'BORE WALL .074 MIN"
    assert callout in gooseneck_spec.COUNTERBORE_WALL_CALLOUT
    assert any(
        gooseneck_spec.COUNTERBORE_WALL_CALLOUT in text
        for text in gooseneck_spec.DIMENSION_CALLOUTS_BY_NAME.values()
    )


def test_head_retains_the_eye_under_its_declared_minor() -> None:
    eye_x = gooseneck.ARM_END_X - spring.END_OCCUPIED_WIDTH_MM / 2.0
    assert eye_x == pytest.approx(-105.8)
    assert gooseneck.SPRING_EYE_GAP == spring.END_OCCUPIED_WIDTH_MM
    smallest_head = SCREW_HEAD_DIA_MIN  # its printed LIMIT's .449
    assert smallest_head == pytest.approx(0.449 * IN)
    retention = (smallest_head - spring.EYE_ID_MM) / 2.0
    assert joint.HEAD_RETENTION_MIN == pytest.approx(retention)
    assert retention == pytest.approx(0.9525, abs=5e-4)
    assert 0.0 < retention < joint.HEAD_RETENTION_TARGET == 1.0
    assert SCREW_BODY_DIA_MAX < spring.EYE_ID_MM


def _upper_transition_section(steps: int = 4000):
    """The vendor's +X (upper) transition wire, in the head's axial section.

    The four B-curve control points are the vendor model's
    (diag_build_1330K524._transition_ctrl), placed by the reference pose's
    rotation (half-turn clocking) about the upper eye, as
    spring_mount_geom.counter_half_turn_clearances places the half-turn.
    Returns, per centreline sample, the station along the screw axis from
    the free-gap head face (positive into the head) and the radial offset
    from the eye's own axis line, as (s, dy, dz); the screw axis stands the
    eye's body-bearing offset above it.
    """
    import spring_mount_geom as mounts
    from diagnostics import diag_build_1330K524 as vendor

    pose = mounts.COUNTER_REFERENCE_POSE
    ctrl = vendor._transition_ctrl(pose.length_mm, positive_x=True)
    eye = spring.end_centers_mm(pose.length_mm)[1]
    rows = pose.rotation_rows
    head_x = mounts.GOOSENECK_END_X + gooseneck.SPRING_EYE_GAP
    section = []
    for index in range(steps + 1):
        t = index / steps
        weights = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t**3)
        local = [
            sum(w * point[k] for w, point in zip(weights, ctrl)) - eye[k]
            for k in range(3)
        ]
        x, y, z = (
            sum(local[k] * rows[k][j] for k in range(3))
            + (pose.upper_eye_xy + (0.0,))[j]
            for j in range(3)
        )
        section.append((x - head_x, y - pose.upper_eye_xy[1], z))
    return section


def _head_section_clearance(s, rho, head_r, relief, head_h=screw.HEAD_H):
    """Signed distance from a section point to the relieved head's profile:
    (0, 0)-(0, R - c)-(c, R)-(H, R)-(H, 0), negative inside."""
    corners = ((0.0, 0.0), (0.0, head_r - relief), (relief, head_r), (head_h, head_r))
    nearest = math.inf
    for (s0, r0), (s1, r1) in zip(corners, corners[1:] + ((head_h, 0.0),)):
        ds, dr = s1 - s0, r1 - r0
        length2 = ds * ds + dr * dr
        if length2 == 0.0:
            continue  # an unrelieved head's zero-length relief
        u = max(0.0, min(1.0, ((s - s0) * ds + (rho - r0) * dr) / length2))
        nearest = min(nearest, math.hypot(s - s0 - u * ds, rho - r0 - u * dr))
    inside = 0.0 <= s <= head_h and rho <= min(head_r, head_r - relief + s)
    return -nearest if inside else nearest


def test_head_relief_clears_the_vendor_transition_wire() -> None:
    """Native probe 20261027T193324627Z: the unrelieved Ø11.50 edge cut
    0.21 into the upper loop's transition wire.  The relief clears it at
    every printed limit of the head Ø, the chamfer and the body (the eye's
    offset), on the free-gap seat the head face holds the loop's head-side
    end at (that end carries the transition, so clamping moves it with the
    head)."""
    section = _upper_transition_section()
    # The distance is 1-Lipschitz along the wire: half the widest sample
    # spacing bounds a closer point between two samples.
    sampling = max(math.dist(a, b) for a, b in zip(section, section[1:])) / 2.0

    def least(head_dia, relief, body_dia):
        axis = (spring.EYE_ID_MM - body_dia) / 2.0
        return min(
            _head_section_clearance(
                s, math.hypot(dy - axis, dz), head_dia / 2.0, relief
            )
            for s, dy, dz in section
        ) - (joint.WIRE_R + sampling)

    # The unrelieved nominal head reproduces the native interference.
    assert least(screw.HEAD_DIA, 0.0, screw.BODY_DIA) == pytest.approx(-0.21, abs=0.01)
    worst = min(
        least(head, relief, body)
        for head in (
            SCREW_HEAD_DIA_MIN,
            SCREW_HEAD_DIA_MAX,
        )
        for relief in (SCREW_RELIEF_MIN, SCREW_RELIEF_MAX)
        for body in (SCREW_BODY_DIA_MIN, SCREW_BODY_DIA_MAX, screw.BODY_DIA)
    )
    assert worst > 0.0
    # The CAD seat (the nominal head and relief) clears it too.
    assert least(screw.HEAD_DIA, screw.HEAD_RELIEF_CHAMFER, screw.BODY_DIA) > worst


def test_relieved_head_flat_still_bears_the_loop() -> None:
    flat = SCREW_HEAD_DIA_MIN / 2.0 - SCREW_RELIEF_MAX
    pass_r = spring.COIL_MEAN_RADIUS_MM - (spring.EYE_ID_MM - SCREW_BODY_DIA_MAX) / 2.0
    assert joint.HEAD_FLAT_RADIUS_MIN == pytest.approx(flat)
    assert joint.LOOP_PASS_RADIUS_MAX == pytest.approx(pass_r)
    assert joint.HEAD_FLAT_BEARING_MARGIN_MIN == pytest.approx(flat - pass_r)
    assert joint.HEAD_FLAT_BEARING_MARGIN_MIN > 0.0


def _declared(package: str):
    return {
        entry.id: entry.kind
        for entry in machinist_exceptions.load_exceptions(
            _config.CONFIG_DIR, package, "part"
        )
    }


def test_owner_minors_are_declared_and_required(monkeypatch) -> None:
    assert _declared("sm_gooseneck")["RV-01"] == "minor"
    assert _declared("sm_gooseneck_spring_screw")["RV-01"] == "minor"
    rows = {
        "sm_gooseneck": "sm-gooseneck",
        "sm_gooseneck_spring_screw": "sm-gooseneck-spring-screw",
    }
    for package, dashed in rows.items():
        joint.owner_minor(_config.parts(dashed), "RV-01", package)
    real = _config.parts

    def without(hidden: str, accept: bool = False):
        def parts(stem=None):
            row = real(stem)
            if stem != rows[hidden]:
                return row
            entries = [dict(entry) for entry in row["machinist_exceptions"]]
            if accept:
                for entry in entries:
                    entry["kind"] = "accept"
            else:
                entries = [entry for entry in entries if entry["id"] != "RV-01"]
            return {**row, "machinist_exceptions": entries}

        return parts

    # An undeclared shortfall, or one declared only as accept, raises.
    for hidden, dashed in rows.items():
        for accept in (False, True):
            row = without(hidden, accept)(dashed)
            with pytest.raises(AssertionError, match=f"{hidden}: no owner minor RV-01"):
                joint.owner_minor(row, "RV-01", hidden)
    # Each part's spec checks its own declaration: run it afresh with the
    # minor hidden.
    specs = {
        "sm_gooseneck": gooseneck_spec,
        "sm_gooseneck_spring_screw": screw_spec,
    }
    for hidden, spec_module in specs.items():
        monkeypatch.setattr(_config, "parts", without(hidden))
        with pytest.raises(AssertionError, match=f"{hidden}: no owner minor RV-01"):
            runpy.run_path(spec_module.__file__)


def test_owner_minor_reads_stay_scoped_to_their_registry_rows() -> None:
    # codjiflo P2/P3 on #1997: the joint reads no registry row, so the
    # channel seats importing it through settled_spring_seats do not re-key
    # on these parts' rows; each part's spec reads its own row, a concrete
    # file, never the whole-config fallback.
    joint_tokens = config_files_of(Path(joint.__file__))
    assert "**" not in joint_tokens
    assert not {token for token in joint_tokens if token.startswith("parts/")}
    for spec_module, row in (
        (gooseneck_spec, "parts/sm-gooseneck.yaml"),
        (screw_spec, "parts/sm-gooseneck-spring-screw.yaml"),
    ):
        tokens = config_files_of(Path(spec_module.__file__))
        assert "**" not in tokens
        assert row in tokens
    # The joint charges each inch sheet's printed limits through the geometry
    # modules' SHEET_UNIT, and each spec holds it to its own row's unit.
    assert gooseneck_spec.UNIT == gooseneck.SHEET_UNIT == "in"
    assert screw_spec.UNIT == screw.SHEET_UNIT == "in"
    assert joint.UNIT == gooseneck.SHEET_UNIT


def test_loop_passes_bear_on_the_plain_body_free_and_clamped() -> None:
    # The plain body's ".14 MIN" as MHA-SM-04 prints it.
    plain = screw.PRINTED_LIMITS["PlainLength"]
    assert plain == pytest.approx(0.14 * IN)
    head_pass, plug_pass = joint.LOOP_PASS_X
    assert 0.0 < head_pass < plug_pass < plain
    assert (head_pass, plug_pass) == pytest.approx((1.2687, 3.1433), abs=5e-4)
    clamped_head, clamped_plug = joint.CLAMPED_LOOP_PASS_X
    assert 0.0 < clamped_head < clamped_plug < plain
    assert (clamped_head, clamped_plug) == pytest.approx((1.2002, 2.8004), abs=5e-4)
    # Plug-side pass short of the thread's earliest start: worst free.
    margin = plain - plug_pass
    assert joint.LOOP_PLAIN_MARGIN_MIN == pytest.approx(margin)
    assert margin == pytest.approx(0.413, abs=5e-4)
    assert joint.LOOP_PLAIN_MARGIN_MIN > 0.0
    # No step: the blank lies inside the 2A major band, so the die's crests
    # stand at the blank and the body is one diameter wherever a wire bears.
    assert screw.THREAD_MAJOR_2A_MIN <= SCREW_BODY_DIA_MIN
    assert SCREW_BODY_DIA_MAX <= screw.THREAD_MAJOR_2A_MAX


def test_wire_on_the_head_face_clears_the_underhead_fillet() -> None:
    # The under-head corner's "R.020 MAX" as MHA-SM-04 prints it.
    r, fillet = joint.WIRE_R, screw.PRINTED_LIMITS["UnderHeadCornerR"]
    assert fillet == pytest.approx(0.020 * IN)
    # Wire touching head face and body: its centre (r, r) from the corner, the
    # fillet circle centred (fillet, fillet).  With r > fillet the nearest
    # fillet material is a tangent point, (fillet, 0) or (0, fillet).
    floor = math.hypot(r - fillet, r) - r
    assert joint.LOOP_CORNER_CLEARANCE_MIN == pytest.approx(floor)
    assert floor == pytest.approx(0.052, abs=5e-4)
    assert joint.LOOP_CORNER_CLEARANCE_MIN > 0.0
    # The floor is the least of every state: clearance grows with station.
    stations = [r + 0.01 * k for k in range(300)]
    gaps = [joint._fillet_clearance(station, r, fillet, r) for station in stations]
    assert gaps == sorted(gaps)
    # Exact on the far side of the tangent points too: the title block's
    # R1.0 would hold the wire off the body, and a wire whose centre lies in
    # a deeper fillet's material overlaps by more than its radius.
    assert joint._fillet_clearance(r, r, 1.0, r) == pytest.approx(
        1.0 - math.hypot(r - 1.0, r - 1.0) - r
    )
    assert joint._fillet_clearance(r, r, 1.0, r) < 0.0
    assert joint._fillet_clearance(0.1, r, 2.0, r) < -r


def _helix_points(gap: float, rise: float, body: float, n: int = 20_000):
    """Supplier loop wire centreline: (station from head, radius from screw)."""
    d = (spring.EYE_ID_MM - body) / 2.0  # inner surface on the body, pull side
    turns = spring.LOOP_TURNS
    for k in range(n + 1):
        t = k / n
        theta = math.pi / 2.0 + 2.0 * math.pi * turns * (t - 1.0 / (4.0 * turns))
        x = spring.COIL_MEAN_RADIUS_MM * math.cos(theta)
        y = -d + spring.COIL_MEAN_RADIUS_MM * math.sin(theta)
        yield gap / 2.0 - rise / 2.0 + rise * t, math.hypot(x, y)


def _rim_reach(radius, inner: float, outer: float):
    """Axial reach of the wire's section onto the annular face ``[inner, outer]``.

    A section whose centreline lies within the wire radius past either rim
    still bears on that rim (codjiflo round 5 on #1997); farther off, none.
    """
    import numpy as np

    reach = np.full_like(radius, -np.inf)
    reach[(radius >= inner) & (radius <= outer)] = joint.WIRE_R
    for off in (radius - outer, inner - radius):
        rim = (off > 0.0) & (off < joint.WIRE_R)
        reach[rim] = np.sqrt(joint.WIRE_R**2 - off[rim] ** 2)
    return reach


def _relieved_head_reach(radius, inner: float, flat: float, outer: float):
    """Axial reach of the wire's section onto MHA-SM-04's relieved head.

    The flat annulus ``[inner, flat]`` has both rims (_rim_reach).  Past it
    lies the 45-degree relief out to the head's Ø ``outer``, which stands
    ``outer - flat`` back from the face at the OD, and then that OD corner.
    A section bears on the relief where the foot of its normal lands on the
    relief.
    """
    import numpy as np

    r = joint.WIRE_R
    reach = _rim_reach(radius, inner, flat)
    root2 = math.sqrt(2.0)
    cone = (radius >= flat + r / root2) & (radius <= outer + r / root2)
    reach[cone] = np.maximum(reach[cone], r * root2 - (radius[cone] - flat))
    off = radius - outer
    corner = (off > 0.0) & (off < r)
    reach[corner] = np.maximum(
        reach[corner], -(outer - flat) + np.sqrt(r**2 - off[corner] ** 2)
    )
    return reach


def test_rocked_loop_keeps_the_gap_floor_and_bears_on_the_body() -> None:
    # The loop, rigid (free helix and coil-bound), rocked by a tilt vector
    # over a grid, then pulled down the spring's line until it bears on the
    # body (either limit).  No friction or equilibrium filter: every rocked
    # state whose width fits the gap (the free gap, or CLAMPED_GAP_MAX bound)
    # counts.  Its section bears on a face wherever it meets the face's
    # footprint, rims included (_rim_reach).  Head: from the R.020 corner's
    # tangent out to the relieved flat's edge, then the 45-degree relief to
    # the head's Ø (_relieved_head_reach), at the least flat (smallest head,
    # largest relief) and the most.  End face: from the counterbore mouth's
    # reach out to the flush end piece's Ø lower limit less its break, or its
    # upper limit.
    #  * every width holds the floor CLAMPED_GAP_MIN, which is tight, and the
    #    gap on the screw axis with the head face tilted SCREW_TILT_MAX
    #    against the end face in any direction holds CLAMPED_AXIS_GAP_MIN,
    #    which is near-tight too (a finer grid reads it lower, toward it);
    #  * in every state that fits, the wire bears on the body at the body's
    #    own radius (no step: test_loop_passes_bear_on_the_plain_body_free_and_clamped),
    #    past the head face's wire radius (the R.020 corner's floor,
    #    LOOP_CORNER_CLEARANCE_MIN) and short of the end face: a wire on the
    #    body spans the counterbore's mouth rim, so at most it rides that rim
    #    and never enters the counterbore.
    import numpy as np

    r = joint.WIRE_R
    step = 0.01
    grid = np.round(np.arange(-0.40, 0.4001, step), 6)
    tx, ty = (axis.ravel() for axis in np.meshgrid(grid, grid, indexing="ij"))
    # Rocked about every horizontal axis alike: the disc the grid spans.
    inside = np.hypot(tx, ty) <= grid[-1] + 1e-9
    tx, ty = tx[inside], ty[inside]
    tilt = np.hypot(tx, ty)
    unit = np.zeros((tx.size, 2))
    np.divide(
        np.stack([tx, ty], axis=1), tilt[:, None], out=unit, where=tilt[:, None] > 0.0
    )
    ux, uy = unit[:, 0], unit[:, 1]
    k = np.zeros((tx.size, 3, 3))
    k[:, 0, 2], k[:, 1, 2], k[:, 2, 0], k[:, 2, 1] = uy, -ux, -uy, ux
    rotations = (
        np.eye(3)
        + np.sin(tilt)[:, None, None] * k
        + (1.0 - np.cos(tilt))[:, None, None] * (k @ k)
    )
    n = 240
    t = np.linspace(0.0, 1.0, n + 1)
    theta = math.pi / 2.0 + 2.0 * math.pi * spring.LOOP_TURNS * (
        t - 1.0 / (4.0 * spring.LOOP_TURNS)
    )
    heads = {
        "least flat": (
            SCREW_HEAD_DIA_MIN / 2.0 - SCREW_RELIEF_MAX,
            SCREW_HEAD_DIA_MIN / 2.0,
        ),
        "most flat": (
            SCREW_HEAD_DIA_MAX / 2.0 - SCREW_RELIEF_MIN,
            SCREW_HEAD_DIA_MAX / 2.0,
        ),
    }
    assert heads["least flat"][0] == pytest.approx(joint.HEAD_FLAT_RADIUS_MIN)
    mouth_r = joint.COUNTERBORE_MOUTH_REACH
    footprints = {
        "least": _smallest_end_piece_radius() - joint.EDGE_BREAK,
        "most": (gooseneck.PLUG_DIA + joint.PLUG_DIA_DEVIATIONS[1]) / 2.0,
    }
    face_tilts = math.tan(joint.SCREW_TILT_MAX) * np.array(
        [[math.cos(a), math.sin(a)] for a in np.linspace(0.0, 2.0 * math.pi, 9)[:-1]]
    )
    states = {
        "free": (gooseneck.SPRING_EYE_GAP, spring.LOOP_RISE_MM),
        "bound": (joint.CLAMPED_GAP_MAX, joint.CLAMPED_LOOP_RISE),
    }
    cases = []
    for state, (gap_max, rise) in states.items():
        for body in (SCREW_BODY_DIA_MIN, SCREW_BODY_DIA_MAX):
            d = (spring.EYE_ID_MM - body) / 2.0
            loop = np.stack(
                [
                    spring.COIL_MEAN_RADIUS_MM * np.cos(theta),
                    -d + spring.COIL_MEAN_RADIUS_MM * np.sin(theta),
                    rise * (t - 0.5),
                ],
                axis=1,
            )
            rocked = loop @ rotations.transpose(0, 2, 1)
            # Pull down -y until the first wire point meets the body: each
            # point reaches the body circle after its own drop.
            bearing_r = body / 2.0 + r
            x, y = rocked[..., 0], rocked[..., 1]
            with np.errstate(invalid="ignore"):
                drop = y - np.sqrt(bearing_r**2 - x**2)
            drop = np.where(np.isnan(drop) | (drop < -d), np.inf, drop).min(axis=1)
            rocked[..., 1] -= drop[:, None]
            xy, z = rocked[..., :2], rocked[..., 2]
            radius = np.hypot(xy[..., 0], xy[..., 1])
            assert radius.min(axis=1) == pytest.approx(bearing_r)
            bearing = radius <= bearing_r + 1e-9
            head_inner = body / 2.0 + screw.PRINTED_LIMITS["UnderHeadCornerR"]
            for head, (flat, head_r) in heads.items():
                head_side = z - _relieved_head_reach(radius, head_inner, flat, head_r)
                head_face = head_side.min(axis=1)
                station = z - head_face[:, None]
                for foot, outer in footprints.items():
                    end_side = z + _rim_reach(radius, mouth_r, outer)
                    width = end_side.max(axis=1) - head_face
                    axis_gap = min(
                        float(((end_side - xy @ tilted).max(axis=1) - head_face).min())
                        for tilted in face_tilts
                    )
                    fits = width <= gap_max
                    bearing_station = station[fits][bearing[fits]]
                    bearing_width = np.broadcast_to(
                        width[fits][:, None], bearing[fits].shape
                    )[bearing[fits]]
                    cases.append(
                        (
                            state,
                            body,
                            f"{head}/{foot}",
                            float(width.min()),
                            axis_gap,
                            int(fits.sum()),
                            float(tilt[fits].max()),
                            float(bearing_station.min()),
                            float((bearing_station - bearing_width).max()),
                        )
                    )
    print(
        "rocked loop: "
        + ", ".join(
            f"{state}/{body:.2f}/{name} width {least:.4f} (axis {axis:.4f}) "
            f"{count} fit to tilt {most:.3f}, bearing {low:.3f}..width{high:+.3f}"
            for state, body, name, least, axis, count, most, low, high in cases
        )
    )
    assert min(case[3] for case in cases) >= joint.CLAMPED_GAP_MIN
    axis_least = min(case[4] for case in cases)
    assert joint.CLAMPED_AXIS_GAP_MIN <= axis_least <= joint.CLAMPED_AXIS_GAP_MIN + 0.05
    tight = min(
        case[3] for case in cases if case[0] == "bound" and case[2].endswith("/least")
    )
    assert tight <= joint.CLAMPED_GAP_MIN + 0.10
    # A wire bearing on the body spans the counterbore's mouth rim (its section
    # reaches past it), so it rides that rim at most: its centre stands the
    # rim's reach short of the end face, never inside the counterbore.
    for state, body, _name, _, _, count, most, low, high in cases:
        assert count  # the width minimum at least
        assert most < grid[-1] - step  # inside the swept grid
        assert low >= r - 1e-9  # past the head face: the corner floor holds
        overlap = mouth_r - (body / 2.0 + r)
        assert 0.0 < overlap < r
        assert high <= -math.sqrt(r**2 - overlap**2) + 1e-9, (state, body)


def test_loop_wire_clears_the_counterbore_mouth_at_full_worst_case() -> None:
    reach = (
        joint.COUNTERBORE_DIA_MAX / 2.0  # largest counterbore
        + EDGE_BREAK  # title-block break on its mouth
        + joint.COUNTERBORE_AXIS_OFFSET_MAX  # counterbore axis vs thread axis
        + joint.SCREW_FACE_OFFSET_MAX  # the tilted screw's axis at the end face
    )
    assert joint.COUNTERBORE_MOUTH_REACH == pytest.approx(reach)
    r = joint.WIRE_R
    contact, standoff = [], []
    for gap, rise in (
        (gooseneck.SPRING_EYE_GAP, spring.LOOP_RISE_MM),
        (joint.CLAMPED_GAP_MAX, joint.CLAMPED_LOOP_RISE),
    ):
        for body in (SCREW_BODY_DIA_MIN, SCREW_BODY_DIA_MAX):
            points = list(_helix_points(gap, rise, body))
            # The plug-side tip is the wire that meets the end face.
            tip_station, tip_radius = points[-1]
            assert tip_station + r == pytest.approx(gap)
            contact.append(tip_radius - r)
            inside = [s for s, rad in points if rad - r < reach]
            standoff.append(gap - (max(inside) + r))
    print(
        f"loop wire at the end face: {min(contact):.3f} from the screw axis "
        f"vs mouth reach {reach:.3f}; wire inside the mouth stands "
        f"{min(standoff):.3f} off the face"
    )
    assert joint.LOOP_FACE_CONTACT_RADIUS_MIN == pytest.approx(min(contact))
    assert joint.LOOP_MOUTH_STANDOFF_MIN == pytest.approx(min(standoff), abs=1e-3)
    assert min(contact) > reach
    assert min(standoff) > 0.0


def test_shared_interference_contract_inputs_match_their_owners() -> None:
    # _interference_contracts keeps the end-piece pair's inputs narrow (shared
    # thread tables and a literal threaded length) so screw or gooseneck edits
    # do not re-key every assembly; pin them to their owners here.  The model
    # seats the screw at the free gap: its thread overlaps the blind tap drill
    # from the counterbore floor to its tip, short of the full thread's end.
    import _interference_contracts
    from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM

    size = joint.TAP_SPEC.size
    assert screw.THREAD.split()[0] == size == "1/4-28"
    assert joint.SCREW_REACH < joint.TAP_THREAD_DEPTH < joint.TAP_DRILL_DEPTH
    engaged = min(joint.SCREW_REACH, joint.TAP_THREAD_DEPTH) - joint.COUNTERBORE_DEPTH
    assert _interference_contracts._GOOSENECK_THREAD_LENGTH == pytest.approx(
        round(engaged, 2)
    )
    assert _interference_contracts._GOOSENECK_THREAD_LENGTH >= engaged
    assert TAP_DRILL_MM[size] == pytest.approx(joint.TAP_DRILL_DIA) == 5.410
    assert THREAD_MAJOR_MM[size] == pytest.approx(screw.MAJOR_DIA, abs=1e-3)
    assert THREAD_MAJOR_MM[size] < joint.COUNTERBORE_DIA


def test_bending_span_reaches_the_receiver_first_full_thread() -> None:
    # Inside the counterbore the screw is unsupported: the beam runs to the
    # end piece's first full thread at its farthest (codjiflo round 3, #1997).
    receiver = joint.CLAMPED_GAP_MAX + joint.COUNTERBORE_DEPTH_MAX + joint.EDGE_BREAK
    assert screw_spec.RECEIVER_FULL_THREAD_STATION_MAX == pytest.approx(receiver)
    assert screw_spec.STRENGTH_SPAN == pytest.approx(
        max(screw.FULL_THREAD_STATION_MAX, receiver)
    )
    assert screw_spec.STRENGTH_SPAN == pytest.approx(7.499, abs=5e-4)
    assert screw_spec._SECTIONS[-1][1] == screw_spec.STRENGTH_SPAN


def test_clamp_couple_is_bounded_by_the_relieved_head_flat() -> None:
    # The flat ends at the largest head less the smallest relief; a wire on
    # the face's plane meets the 45-degree relief nowhere past it.
    spec = screw_spec
    flat = (screw.HEAD_DIA + screw.HEAD_DIA_UPPER) / 2.0 - screw.HEAD_RELIEF_CHAMFER_MIN
    assert spec.CLAMP_ECCENTRICITY_MAX == pytest.approx(flat)
    assert flat == pytest.approx(4.40)
    worst = (min(spec.CLAMP_FRICTIONS), max(spec.THREAD_FRICTIONS))
    # The couple is what governs: on the axis both SFs are several times it.
    assert spec.service_safety_factor(*worst, 0.0) > 2.0 * spec.service_safety_factor(
        *worst
    )
    assert spec.tightening_safety_factor(
        *worst, 0.0
    ) > 2.0 * spec.tightening_safety_factor(*worst)


@pytest.mark.parametrize("yield_mpa", [screw_spec.YIELD_MPA, 724.0])
def test_strength_holds_sf_2_at_the_bar_yield_and_at_105_ksi(
    monkeypatch, yield_mpa: float
) -> None:
    spec = screw_spec
    assert spec.YIELD_MPA == pytest.approx(896.3, abs=0.05)  # 130 ksi, 6818T53
    monkeypatch.setattr(spec, "YIELD_MPA", yield_mpa)
    pairs = {(c, t) for c in spec.CLAMP_FRICTIONS for t in spec.THREAD_FRICTIONS}
    assert set(spec.SERVICE_SF) == set(spec.TIGHTENING_SF) == pairs
    # The lowest clamp friction needs the most preload and the highest thread
    # friction converts the most of it to torsion: that pair governs both.
    worst = (min(spec.CLAMP_FRICTIONS), max(spec.THREAD_FRICTIONS))
    assert min(spec.SERVICE_SF, key=spec.SERVICE_SF.get) == worst
    assert min(spec.TIGHTENING_SF, key=spec.TIGHTENING_SF.get) == worst
    service = spec.service_safety_factor(*worst)
    tightening = spec.tightening_safety_factor(*worst)
    print(
        f"yield {yield_mpa:.1f}: service SF {service:.3f}, tightening {tightening:.3f}"
    )
    assert service >= spec.STRENGTH_SF_TARGET == 2.0
    assert tightening >= spec.STRENGTH_SF_TARGET
    # 12L14 CD's 415 MPa would not carry the clamp couple at SF 2: the grade
    # is required.
    assert service * 415.0 / yield_mpa < 2.0


def test_service_peak_stations_bound_a_dense_sweep() -> None:
    spec = screw_spec
    mu_clamp, mu_thread = min(spec.CLAMP_FRICTIONS), max(spec.THREAD_FRICTIONS)
    preload = spec.clamp_preload_n(mu_clamp)
    torsion = spec.RESIDUAL_TORSION_FACTOR * spec.thread_torque_n_mm(preload, mu_thread)
    couple = preload * spec.CLAMP_ECCENTRICITY_MAX
    dense = min(
        spec._von_mises_sf(
            preload, moment(x0 + (x1 - x0) * i / 2000) + couple, torsion, dia
        )
        for x0, x1, dia in spec._SECTIONS
        for i in range(2001)
        for moment in spec._MOMENT_CASES
    )
    exact = spec.service_safety_factor(mu_clamp, mu_thread)
    assert exact <= dense + 1e-12
    assert dense - exact < 1e-3


def test_tightening_sf_is_the_overtightening_margin() -> None:
    # Both tightening stresses (with the clamp couple) are linear in the
    # preload, so the tightening SF is the multiple of the needed preload the
    # root takes to nominal yield.
    spec = screw_spec
    worst = (min(spec.CLAMP_FRICTIONS), max(spec.THREAD_FRICTIONS))
    needed = spec.clamp_preload_n(worst[0])
    margin = spec.tightening_safety_factor(*worst)
    at_margin = needed * margin
    sf = spec._von_mises_sf(
        at_margin,
        at_margin * spec.CLAMP_ECCENTRICITY_MAX,
        spec.thread_torque_n_mm(at_margin, worst[1]),
        spec.THREAD_MINOR_2A_MIN_EST,
    )
    assert sf == pytest.approx(1.0)
    assert spec.OVERTIGHTEN_MARGIN == pytest.approx(margin)
    assert spec.OVERTIGHTEN_MARGIN >= spec.STRENGTH_SF_TARGET


def _end_piece_torque_n_mm(mu_clamp: float, mu_thread: float) -> float:
    # Tightening MHA-SM-04 turns the end piece through its thread and its
    # under-head face; the shank joint reacts both.
    preload = screw_spec.clamp_preload_n(mu_clamp)
    head = preload * mu_clamp * screw_spec.CLAMP_ECCENTRICITY_MAX
    return screw_spec.thread_torque_n_mm(preload, mu_thread) + head


def test_loctite_638_alternative_holds_the_clamp_torque() -> None:
    # Owner ruling 2026-10-27 (#1997): LOCTITE 638 in the braze window.
    # Henkel Retaining Compound Design Guide: T = pi d^2 L tau f / 2000 (N m)
    # with f = alloy steel 0.9 x clearance 0.3 x L/D 0.6 (static, slip fit,
    # room-temperature cure: 1.0); tau = 25 N/mm^2 (TDS ISO 10123, 24 h).
    assert joint.BRAZE_CLEARANCE_MAX <= joint.LOCTITE_638_GAP_MAX
    shank = gooseneck.TUBE_BORE_DIA_MIN - joint.BRAZE_CLEARANCE_MAX
    capacity = math.pi * shank**2 * gooseneck.PLUG_SHANK_LENGTH * 25.0 * 0.162 / 2.0
    needed = max(_end_piece_torque_n_mm(*pair) for pair in screw_spec.FRICTION_PAIRS)
    assert capacity / needed == pytest.approx(3.66, abs=0.01)
    assert capacity >= 2.0 * needed


def test_press_fit_window_is_too_narrow_to_fit_by_hand() -> None:
    # Shigley 10e eq. 3-57/3-58, same steel, solid shaft: the interference
    # the thinnest tube's bore takes to yield (4130-N, 60 ksi) against the
    # interference that holds the torque at the screw's own yield (DIN 7190
    # steel-steel friction 0.12).
    e_mpa, sy_mpa = 205_000.0, 60_000 * 0.00689475729
    od = gooseneck.TUBE_DIA_MIN
    bore = od - 2.0 * gooseneck.WALL_T_MIN

    def pressure(delta: float, d: float, do: float) -> float:
        return e_mpa * delta / (2.0 * d) * (1.0 - (d / do) ** 2)

    def von_mises(delta: float, d: float, do: float) -> float:
        p = pressure(delta, d, do)
        hoop = p * (do**2 + d**2) / (do**2 - d**2)
        return math.sqrt(hoop**2 + hoop * p + p**2)

    cap = sy_mpa / von_mises(1.0, bore, od)
    at_yield = max(
        _end_piece_torque_n_mm(*pair) * screw_spec._TIGHTENING_SF_EXACT[pair]
        for pair in screw_spec.FRICTION_PAIRS
    )
    d, do = gooseneck.TUBE_BORE_DIA, gooseneck.TUBE_DIA
    hold_per_mm = (
        0.12 * pressure(1.0, d, do) * math.pi * d**2 * gooseneck.PLUG_SHANK_LENGTH / 2
    )
    need = at_yield / hold_per_mm
    assert cap == pytest.approx(0.0214, abs=5e-4)
    assert need == pytest.approx(0.0080, abs=5e-4)
    assert cap / 1.5 - need < 0.0065
