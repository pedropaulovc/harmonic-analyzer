"""Offline run-out, full-thread, wall, tip and loop contracts for the upper clamp.

Owner ruling 2026-10-26 (#1951, option B): the loop sits on MHA-SM-04's plain
Ø3.50 shoulder and its #8-32 thread runs through MHA-SM-01's plug, retapped
#8-32 UNC-2B THRU.  The 2026-09-21 clamp rulings stand.  The plug's arm-end
counterbore clears the screw's die run-out with the loop clamped coil-bound
(codjiflo P1 on #1997).
"""

from __future__ import annotations

import math

import pytest

import sm_gooseneck_geom as gooseneck
import sm_gooseneck_spring_joint as joint
import sm_gooseneck_spring_screw_geom as screw
import sm_gooseneck_spring_screw_spec as screw_spec
import sm_vn_counter_spring_stock_geom as spring

ONE_POINT_FIVE_D = 1.5 * screw.MAJOR_DIA


def test_clamp_preload_binds_the_loop_coil_bound() -> None:
    rise = spring.LOOP_TURNS * spring.WIRE_DIA_MM  # one wire per turn, bound
    assert joint.CLAMPED_GAP == pytest.approx(rise + spring.WIRE_DIA_MM)
    assert joint.CLAMPED_GAP == pytest.approx(4.40, abs=0.005)
    rate = 82_700.0 * 1.6002**4 / (8.0 * 11.0998**3 * 1.75)
    assert joint.LOOP_AXIAL_RATE == pytest.approx(rate)
    assert joint.LOOP_BIND_FORCE == pytest.approx(rate * (4.88061 - 4.40055))
    least_preload = min(
        screw_spec.clamp_preload_n(mu) for mu in screw_spec.CLAMP_FRICTIONS
    )
    assert least_preload == pytest.approx(231.0, abs=0.5)
    assert joint.LOOP_BIND_FORCE < 0.1 * least_preload


def test_counterbore_depth_clears_the_clamped_runout_with_margin() -> None:
    clamped = screw.FULL_THREAD_STATION_MAX - joint.CLAMPED_GAP
    free = screw.FULL_THREAD_STATION_MAX - gooseneck.SPRING_EYE_GAP
    assert joint.SCREW_RUNOUT_INTRUSION_MAX == pytest.approx(clamped)
    assert joint.SCREW_RUNOUT_INTRUSION_FREE_MAX == pytest.approx(free)
    assert (free, clamped) == pytest.approx((0.79, 1.27), abs=0.005)
    assert joint.COUNTERBORE_DEPTH_MIN - clamped >= joint.COUNTERBORE_RUNOUT_MARGIN_MIN
    assert (
        joint.COUNTERBORE_DEPTH_MIN,
        joint.COUNTERBORE_DEPTH,
        joint.COUNTERBORE_DEPTH_MAX,
    ) == pytest.approx((1.32, 1.37, 1.42))


def test_counterbore_clears_the_fat_runout_radially() -> None:
    play = (screw.MAJOR_DIA + 0.025 - screw.THREAD_MAJOR_2A_MIN) / 2.0
    clearance = (
        joint.COUNTERBORE_DIA / 2.0  # DRILLED HOLES minus is 0
        - screw.MAJOR_DIA / 2.0  # run-out crest, at or above the 2A major max
        - joint.COUNTERBORE_AXIS_OFFSET_MAX  # MHA-SM-01 note 4, to the tap
        - play  # screw in the 2B thread, crest-to-root bound
    )
    assert joint.RUNOUT_RADIAL_CLEARANCE_MIN == pytest.approx(clearance)
    assert clearance == pytest.approx(0.067, abs=5e-4)
    # Ø4.50 would rub: the reason the counterbore is Ø4.70.
    assert (4.50 - screw.MAJOR_DIA) / 2.0 - joint.COUNTERBORE_AXIS_OFFSET_MAX - play < 0


def test_receiver_full_thread_past_the_counterbore_is_1_5d() -> None:
    full_thread = (
        gooseneck.PLUG_LENGTH
        - joint.PLUG_LENGTH_BAND  # shortest plug
        - joint.COUNTERBORE_DEPTH_MAX  # deepest counterbore
        - 0.25  # title-block break on the tap edge at the counterbore floor
        - 0.25  # title-block break at the inner tap end
    )
    assert gooseneck.PLUG_LENGTH == 8.80
    assert joint.ENGAGEMENT_MIN == pytest.approx(full_thread)
    assert (joint.ENGAGEMENT_NOMINAL, joint.ENGAGEMENT_MIN) == pytest.approx(
        (6.93, 6.37)
    )
    assert full_thread >= ONE_POINT_FIVE_D == pytest.approx(6.25, abs=0.005)


def test_screw_full_thread_spans_the_receiver_so_mated_equals_receiver() -> None:
    # Full thread starts inside the counterbore at either gap ...
    assert joint.SCREW_RUNOUT_INTRUSION_FREE_MAX < joint.COUNTERBORE_DEPTH_MIN
    assert joint.SCREW_RUNOUT_INTRUSION_MAX < joint.COUNTERBORE_DEPTH_MIN
    assert not hasattr(joint, "MATED_ENGAGEMENT_MIN")
    # ... and even the shortest screw at the free gap carries it past the
    # longest plug's inner end.
    longest_plug = gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND
    full_tip_reach = (
        screw.LENGTH + screw.LENGTH_LOWER - gooseneck.SPRING_EYE_GAP - 1.5 * screw.PITCH
    )
    assert joint.FULL_THREAD_REACH_MIN == pytest.approx(full_tip_reach)
    assert full_tip_reach > longest_plug


def test_threaded_plug_wall_is_2_0_at_the_full_worst_case() -> None:
    smallest_plug_od = joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND  # .XX lower limit
    largest_tap_major = screw.MAJOR_DIA + 0.025  # basic major + root oversize
    # Hole drilled after braze, plug OD turned before: different setups.
    runoff = (gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND) * math.tan(
        math.radians(0.3)
    )
    worst_wall = (
        smallest_plug_od / 2.0
        - largest_tap_major / 2.0
        - joint.THREAD_AXIS_OFFSET_MAX  # MHA-SM-01 note 4
        - joint.DRILL_WANDER_MAX  # MHA-SM-01 note 4
        - runoff
        - 2.0 * 0.25  # tap edge + plug OD edge, title block
    )
    assert joint.EDGE_BREAK == 0.25
    assert joint.TAP_ROOT_OVERSIZE == 0.025
    assert joint.DRILL_RUNOFF_MAX == pytest.approx(runoff)
    assert joint.PLUG_WALL_MIN == pytest.approx(worst_wall)
    assert worst_wall == pytest.approx(2.85, abs=0.005)
    assert worst_wall >= joint.PLUG_WALL_TARGET == 2.0


def test_counterbore_wall_is_2_0_at_the_full_worst_case() -> None:
    smallest_plug_od = joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND  # .XX lower limit
    largest_cbore = joint.COUNTERBORE_DIA + 0.10  # DRILLED HOLES +0.10
    # Counterbore cut after braze, plug OD turned before: different setups.
    runoff = joint.COUNTERBORE_DEPTH_MAX * math.tan(math.radians(0.3))
    worst_wall = (
        smallest_plug_od / 2.0
        - largest_cbore / 2.0
        - joint.THREAD_AXIS_OFFSET_MAX  # MHA-SM-01 note 4, tap to tube
        - joint.COUNTERBORE_AXIS_OFFSET_MAX  # MHA-SM-01 note 4, to the tap
        - runoff
        - 2.0 * 0.25  # counterbore mouth + plug OD edge, title block
    )
    assert joint.COUNTERBORE_DIA_MAX == pytest.approx(largest_cbore)
    assert joint.COUNTERBORE_WALL_MIN == pytest.approx(worst_wall)
    assert worst_wall == pytest.approx(2.59, abs=0.005)
    assert worst_wall >= joint.PLUG_WALL_TARGET


def test_screw_tip_exits_plug_without_reaching_tube_wall_or_bend() -> None:
    longest_plug = gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND
    # Free gap: the screw sits shallowest.
    shortest_reach = screw.LENGTH + screw.LENGTH_LOWER - gooseneck.SPRING_EYE_GAP
    assert joint.TIP_PROTRUSION_MIN == pytest.approx(shortest_reach - longest_plug)
    assert joint.TIP_PROTRUSION_MIN == pytest.approx(1.30, abs=0.005)
    assert joint.PLUG_INNER_X < joint.SCREW_TIP_X < -gooseneck.BEND_R
    # Clamped gap: the screw sits deepest.
    longest_reach = screw.LENGTH + screw.LENGTH_UPPER - joint.CLAMPED_GAP
    assert joint.TIP_TO_BEND_MIN == pytest.approx(gooseneck.ARM_RUN - longest_reach)
    assert joint.TIP_TO_BEND_MIN > 0.0
    smallest_bore = joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND
    radial = smallest_bore / 2.0 - (
        screw.MAJOR_DIA / 2.0
        + joint.THREAD_AXIS_OFFSET_MAX
        + joint.DRILL_WANDER_MAX
        + joint.DRILL_RUNOFF_MAX
    )
    assert joint.TIP_BORE_RADIAL_CLEARANCE_MIN == pytest.approx(radial)
    assert radial > 0.0


def test_clamped_eye_stays_at_existing_station_and_has_radial_capture() -> None:
    eye_x = gooseneck.ARM_END_X - spring.END_OCCUPIED_WIDTH_MM / 2.0
    assert eye_x == pytest.approx(-105.8)
    assert gooseneck.SPRING_EYE_GAP == spring.END_OCCUPIED_WIDTH_MM
    smallest_head = screw.HEAD_DIA + screw.HEAD_DIA_LOWER
    assert (smallest_head - spring.EYE_ID_MM) / 2.0 == pytest.approx(
        joint.HEAD_RETENTION_MIN
    )
    assert joint.HEAD_RETENTION_MIN >= 1.0
    assert screw.SEAT_DIA_MAX < screw.MAJOR_DIA < spring.EYE_ID_MM


def test_loop_passes_bear_on_the_plain_seat_free_and_clamped() -> None:
    head_pass, plug_pass = joint.LOOP_PASS_X
    assert 0.0 < head_pass < plug_pass < screw.SHOULDER_LENGTH_MIN
    assert (head_pass, plug_pass) == pytest.approx((1.2687, 3.1433), abs=5e-4)
    clamped_head, clamped_plug = joint.CLAMPED_LOOP_PASS_X
    assert 0.0 < clamped_head < clamped_plug < screw.SHOULDER_LENGTH_MIN
    assert (clamped_head, clamped_plug) == pytest.approx((1.2002, 2.8004), abs=5e-4)

    def lead_gap(station: float) -> float:
        return (screw.SHOULDER_LENGTH_MIN - station + joint.WIRE_R) / math.sqrt(
            2.0
        ) - joint.WIRE_R

    def corner_gap(station: float) -> float:
        return (
            math.hypot(station - joint.INSIDE_CORNER_R_MAX, joint.WIRE_R) - joint.WIRE_R
        )

    assert joint.INSIDE_CORNER_R_MAX == 1.0
    # Plug-side pass vs the lead: worst free (the clamped loop pulls it back).
    assert lead_gap(plug_pass) == pytest.approx(0.159, abs=5e-4)
    assert lead_gap(clamped_plug) > lead_gap(plug_pass)
    assert joint.LOOP_LEAD_CLEARANCE_MIN == pytest.approx(lead_gap(plug_pass))
    # Head-side pass vs the R1.0 MAX corner: worst clamped, still clear.
    assert corner_gap(head_pass) == pytest.approx(0.044, abs=5e-4)
    assert corner_gap(clamped_head) == pytest.approx(0.025, abs=5e-4)
    assert joint.LOOP_CORNER_CLEARANCE_MIN == pytest.approx(corner_gap(clamped_head))
    assert min(joint.LOOP_LEAD_CLEARANCE_MIN, joint.LOOP_CORNER_CLEARANCE_MIN) > 0.0


def _helix_points(gap: float, rise: float, seat: float, n: int = 20_000):
    """Supplier loop wire centreline: (station from head, radius from screw)."""
    d = (spring.EYE_ID_MM - seat) / 2.0  # inner surface on the seat, pull side
    turns = spring.LOOP_TURNS
    for k in range(n + 1):
        t = k / n
        theta = math.pi / 2.0 + 2.0 * math.pi * turns * (t - 1.0 / (4.0 * turns))
        x = spring.COIL_MEAN_RADIUS_MM * math.cos(theta)
        y = -d + spring.COIL_MEAN_RADIUS_MM * math.sin(theta)
        yield gap / 2.0 - rise / 2.0 + rise * t, math.hypot(x, y)


def test_loop_wire_clears_the_counterbore_mouth_at_full_worst_case() -> None:
    reach = (
        joint.COUNTERBORE_DIA_MAX / 2.0  # largest counterbore
        + 0.25  # title-block break on its mouth
        + joint.COUNTERBORE_AXIS_OFFSET_MAX  # counterbore axis vs thread axis
        + joint.SCREW_RADIAL_PLAY_MAX  # screw axis vs thread axis
    )
    assert joint.COUNTERBORE_MOUTH_REACH == pytest.approx(reach)
    r = joint.WIRE_R
    contact, standoff = [], []
    for gap, rise in (
        (gooseneck.SPRING_EYE_GAP, spring.LOOP_RISE_MM),
        (joint.CLAMPED_GAP, joint.CLAMPED_LOOP_RISE),
    ):
        for seat in (screw.SEAT_DIA_MIN, screw.SEAT_DIA_MAX):
            points = list(_helix_points(gap, rise, seat))
            # The plug-side tip is the wire that meets the plug face.
            tip_station, tip_radius = points[-1]
            assert tip_station + r == pytest.approx(gap)
            contact.append(tip_radius - r)
            inside = [s for s, rad in points if rad - r < reach]
            standoff.append(gap - (max(inside) + r))
    print(
        f"loop wire at the plug face: {min(contact):.3f} from the screw axis "
        f"vs mouth reach {reach:.3f}; wire inside the mouth stands "
        f"{min(standoff):.3f} off the face"
    )
    assert joint.LOOP_FACE_CONTACT_RADIUS_MIN == pytest.approx(min(contact))
    assert joint.LOOP_MOUTH_STANDOFF_MIN == pytest.approx(min(standoff), abs=1e-3)
    assert min(contact) > reach
    assert min(standoff) > 0.0


def test_shared_interference_contract_inputs_match_their_owners() -> None:
    # _interference_contracts keeps the plug pair's inputs narrow (shared
    # thread tables and a literal threaded length) so screw or gooseneck edits
    # do not re-key every assembly; pin them to their owners here.
    import _interference_contracts
    from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM

    assert screw.THREAD.split()[0] == joint.TAP_SPEC.size == "#8-32"
    assert _interference_contracts._GOOSENECK_THREAD_LENGTH == pytest.approx(
        gooseneck.PLUG_LENGTH - joint.COUNTERBORE_DEPTH
    )
    assert TAP_DRILL_MM["#8-32"] == pytest.approx(joint.TAP_DRILL_DIA) == 3.454
    assert THREAD_MAJOR_MM["#8-32"] == pytest.approx(screw.MAJOR_DIA, abs=1e-3)
    assert THREAD_MAJOR_MM["#8-32"] < joint.COUNTERBORE_DIA
