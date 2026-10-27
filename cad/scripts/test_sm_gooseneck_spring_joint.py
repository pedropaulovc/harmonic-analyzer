"""Offline full-thread, wall, tip and loop-seat contracts for the upper spring clamp.

Owner ruling 2026-10-26 (#1951, option B): the loop sits on MHA-SM-04's plain
Ø3.50 shoulder and its #8-32 thread runs through MHA-SM-01's plug, retapped
#8-32 UNC-2B THRU.  The 2026-09-21 clamp rulings stand.
"""

from __future__ import annotations

import math

import pytest

import sm_gooseneck_geom as gooseneck
import sm_gooseneck_spring_joint as joint
import sm_gooseneck_spring_screw_geom as screw
import sm_vn_counter_spring_stock_geom as spring


def test_receiver_full_thread_is_at_least_1_5d_at_both_broken_edges() -> None:
    shortest_plug = gooseneck.PLUG_LENGTH - joint.PLUG_LENGTH_BAND
    full_thread = shortest_plug - 2.0 * joint.EDGE_BREAK
    assert joint.ENGAGEMENT_MIN == pytest.approx(full_thread)
    assert (joint.ENGAGEMENT_NOMINAL, joint.ENGAGEMENT_MIN) == pytest.approx(
        (7.50, 6.99)
    )
    assert full_thread >= 1.5 * screw.MAJOR_DIA


def test_mated_full_thread_starts_past_the_screw_runout_and_is_1_5d() -> None:
    # The screw's full thread starts no later than the printed single limit
    # FULL_THREAD_STATION_MAX ("5.67 MAX") from the head; past the clamp gap
    # that station lies inside the plug mouth.
    assert screw.FULL_THREAD_STATION_MAX == 5.67
    intrusion_max = screw.FULL_THREAD_STATION_MAX - gooseneck.SPRING_EYE_GAP
    assert intrusion_max > joint.EDGE_BREAK
    mated_min = (
        gooseneck.PLUG_LENGTH
        - joint.PLUG_LENGTH_BAND
        - joint.EDGE_BREAK  # inner tap exit break
        - intrusion_max  # screw lead + die run-out at the longest shoulder
    )
    assert joint.MATED_ENGAGEMENT_MIN == pytest.approx(mated_min)
    assert (joint.MATED_ENGAGEMENT_NOMINAL, joint.MATED_ENGAGEMENT_MIN) == (
        pytest.approx((7.21, 6.45), abs=0.005)
    )
    assert mated_min >= 1.5 * screw.MAJOR_DIA == pytest.approx(6.25, abs=0.005)
    # Even the shortest screw's incomplete tip starts beyond the longest plug.
    longest_plug = gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND
    full_tip_reach = (
        screw.LENGTH + screw.LENGTH_LOWER - gooseneck.SPRING_EYE_GAP - 1.5 * screw.PITCH
    )
    assert full_tip_reach > longest_plug


def test_plug_wall_is_2_0_at_the_full_worst_case() -> None:
    # Every term (sm_gooseneck_spring_joint wall comment):
    smallest_plug_od = joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND  # .XX lower limit
    largest_tap_major = screw.MAJOR_DIA + 0.025  # basic major + root oversize
    axis_offset = joint.THREAD_AXIS_OFFSET_MAX  # MHA-SM-01 note 4
    wander = joint.DRILL_WANDER_MAX  # MHA-SM-01 note 4
    # Hole drilled after braze, plug OD turned before: different setups.
    runoff = (gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND) * math.tan(
        math.radians(0.3)
    )
    edge_breaks = 2.0 * 0.25  # tap mouth + plug OD edge, title block
    worst_wall = (
        smallest_plug_od / 2.0
        - largest_tap_major / 2.0
        - axis_offset
        - wander
        - runoff
        - edge_breaks
    )
    assert joint.EDGE_BREAK == 0.25
    assert joint.TAP_ROOT_OVERSIZE == 0.025
    assert joint.DRILL_RUNOFF_MAX == pytest.approx(runoff)
    assert joint.PLUG_WALL_MIN == pytest.approx(worst_wall)
    assert worst_wall == pytest.approx(2.86, abs=0.005)
    assert worst_wall >= joint.PLUG_WALL_TARGET == 2.0


def test_screw_tip_exits_plug_without_reaching_tube_wall_or_bend() -> None:
    longest_plug = gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND
    shortest_reach = screw.LENGTH + screw.LENGTH_LOWER - gooseneck.SPRING_EYE_GAP
    assert shortest_reach > longest_plug
    assert joint.TIP_PROTRUSION_MIN > 0.0
    assert joint.PLUG_INNER_X < joint.SCREW_TIP_X < -gooseneck.BEND_R
    longest_reach = screw.LENGTH + screw.LENGTH_UPPER - gooseneck.SPRING_EYE_GAP
    assert longest_reach < gooseneck.ARM_RUN
    smallest_bore = joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND
    assert smallest_bore / 2.0 > (
        screw.MAJOR_DIA / 2.0
        + joint.THREAD_AXIS_OFFSET_MAX
        + joint.DRILL_WANDER_MAX
        + joint.DRILL_RUNOFF_MAX
    )


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


def test_loop_passes_bear_on_the_plain_seat_only() -> None:
    head_pass, plug_pass = joint.LOOP_PASS_X
    assert 0.0 < head_pass < plug_pass < screw.SHOULDER_LENGTH_MIN
    assert (head_pass, plug_pass) == pytest.approx((1.2687, 3.1433), abs=5e-4)
    # Plug-side pass vs the 45-degree lead at the shortest shoulder.
    lead_gap = (screw.SHOULDER_LENGTH_MIN - plug_pass + joint.WIRE_R) / math.sqrt(
        2.0
    ) - joint.WIRE_R
    assert joint.LOOP_LEAD_CLEARANCE_MIN == pytest.approx(lead_gap)
    assert lead_gap == pytest.approx(0.159, abs=5e-4)
    # Head-side pass vs the largest title-block inside corner under the head.
    assert joint.INSIDE_CORNER_R_MAX == 1.0
    corner_gap = (
        math.hypot(head_pass - joint.INSIDE_CORNER_R_MAX, joint.WIRE_R) - joint.WIRE_R
    )
    assert joint.LOOP_CORNER_CLEARANCE_MIN == pytest.approx(corner_gap)
    assert corner_gap == pytest.approx(0.044, abs=5e-4)
    assert min(lead_gap, corner_gap) > 0.0


def test_shared_interference_contract_inputs_match_their_owners() -> None:
    # _interference_contracts keeps the plug pair's inputs narrow (shared
    # thread tables and a literal plug length) so screw or gooseneck edits do
    # not re-key every assembly; pin them to their owners here.
    import _interference_contracts
    from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM

    assert screw.THREAD.split()[0] == joint.TAP_SPEC.size == "#8-32"
    assert _interference_contracts._GOOSENECK_PLUG_LENGTH == gooseneck.PLUG_LENGTH
    assert TAP_DRILL_MM["#8-32"] == pytest.approx(joint.TAP_DRILL_DIA) == 3.454
    assert THREAD_MAJOR_MM["#8-32"] == pytest.approx(screw.MAJOR_DIA, abs=1e-3)


def test_strength_sweeps_clamp_and_thread_friction_independently() -> None:
    import sm_gooseneck_spring_screw_spec as spec

    pairs = {(c, t) for c in spec.CLAMP_FRICTIONS for t in spec.THREAD_FRICTIONS}
    assert set(spec.SERVICE_SF) == set(spec.TIGHTENING_SF) == pairs
    # The lowest clamp friction needs the most preload and the highest thread
    # friction converts the most of it to torsion: that pair governs both.
    worst = (min(spec.CLAMP_FRICTIONS), max(spec.THREAD_FRICTIONS))
    assert min(spec.SERVICE_SF, key=spec.SERVICE_SF.get) == worst
    assert min(spec.TIGHTENING_SF, key=spec.TIGHTENING_SF.get) == worst
    assert spec.SERVICE_SF[worst] >= spec.STRENGTH_SF_TARGET
    assert spec.TIGHTENING_SF[worst] >= spec.STRENGTH_SF_TARGET


def test_service_peak_stations_bound_a_dense_sweep() -> None:
    import sm_gooseneck_spring_screw_spec as spec

    mu_clamp, mu_thread = min(spec.CLAMP_FRICTIONS), max(spec.THREAD_FRICTIONS)
    preload = spec.clamp_preload_n(mu_clamp)
    torsion = spec.RESIDUAL_TORSION_FACTOR * spec.thread_torque_n_mm(preload, mu_thread)
    dense = min(
        spec._von_mises_sf(preload, moment(x0 + (x1 - x0) * i / 2000), torsion, dia)
        for x0, x1, dia in spec._SECTIONS
        for i in range(2001)
        for moment in spec._MOMENT_CASES
    )
    exact = spec.service_safety_factor(mu_clamp, mu_thread)
    assert exact <= dense + 1e-12
    assert dense - exact < 1e-3
