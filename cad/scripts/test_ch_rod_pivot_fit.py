"""Offline contract: the rod fork straddles its rocker arm in one plane, and
the peened MHA-CH-010 pin runs in the arm and is retained in the fork, with
every fit held at the worst case of its printed bands (policy rule 12).

``ch_rod_pivot_pin_spec`` reads only the two parts it joins; the restated
floors and the swing it designs for are pinned to their sources here.
"""

from __future__ import annotations

import math

import pytest

import _config
import ch_amplitude_bar_spec as bar
import channel_frame_geom as frame
import channel_kinematics as ck
import ch_connecting_rod_spec as rod
import ch_rocker_arm_spec as arm
import ch_rod_pivot_pin_spec as pin
import cylinder_bank_layout as drum_bank
import dt_cylinder_gear_spec as gear
import rocker_bank_layout as bank


def test_restated_floors_are_their_sources() -> None:
    drilled = _config.title_block("drilled_hole")
    assert (drilled["minus_mm"], drilled["plus_mm"]) == (0.0, pin.DRILLED_PLUS)
    assert pin.RUNNING_FLOOR == bank.MIN_END_PLAY
    assert pin.MARGIN_SPARE == bank.MARGIN_SPARE
    assert arm.LINEAR_2PL == pytest.approx(
        _config.title_block("linear_2pl")["value_in"] * 25.4
    )
    # The hubs set the pitch the neighbour stack is judged at.
    assert arm.HUB_LENGTH == bank.PITCH and arm.HUB_LENGTH_BAND[1] == 0.0


def test_the_rod_arm_and_cam_share_one_plane() -> None:
    assert bank.ARM_MID_DZ == drum_bank.CAM_MID_DZ
    assert drum_bank.CAM_MID_DZ == pytest.approx(
        -(gear.FACE_WIDTH + gear.CAM_THICKNESS) / 2.0
    )
    # The pin is centred on the fork, which is centred on the rod plane.
    assert pin.PIN_INSTALLED_LENGTH == rod.FORK_THICKNESS
    assert pin.PIN_CSK_DIA == rod.PIN_HOLE_CSK_DIA
    assert rod.PIN_HOLE_SPEC == arm.ROD_HOLE_SPEC


def test_worst_case_joint_budget() -> None:
    b = pin.BUDGET
    assert b["side_clearance_min"] == pytest.approx(0.100, abs=1e-6)
    assert b["side_clearance_max"] == pytest.approx(0.277, abs=1e-6)
    assert b["neighbour_clearance_min"] == pytest.approx(0.3545, abs=1e-6)
    assert b["neighbour_clearance_min"] >= pin.NEIGHBOUR_CLEARANCE_MIN
    assert b["tine_min"] == pytest.approx(1.5865, abs=1e-6)
    assert b["tine_min"] >= pin.RULE12_WALL_FLOOR
    assert b["running_clearance_min"] > 0.0
    assert b["retention_overlap_min"] >= pin.RETENTION_OVERLAP_MIN
    assert b["upset_projection_min"] >= b["upset_needed_max"]
    assert b["crown_wall_min"] >= 2.0
    assert b["crotch_clearance_min"] >= pin.CROTCH_CLEARANCE_MIN


def test_neighbour_stack_fills_the_inter_arm_gap_exactly() -> None:
    """The gap (pitch less the thickest arm) holds both side clearances,
    both outer tines, both proud ends and the neighbour clearance: the
    stack closes with nothing left out."""
    b = pin.BUDGET
    w_max = rod.FORK_THICKNESS + rod.FORK_THICKNESS_BAND[0]
    off = rod.FORK_TINE_MATCH / 2.0
    float_total = b["side_clearance_max"]
    assert bank.PITCH - (
        w_max + float_total + 2.0 * off + 2.0 * pin.PIN_END_PROUD_MAX
    ) == pytest.approx(b["neighbour_clearance_min"])


def _relative_swing_deg() -> tuple[float, float]:
    """(min, max) arm tilt less rod tilt over one cam turn (degrees)."""
    ox, oy = frame.ROCKER_PIVOT_XY
    lever, c2c = ck._ARM_ROD_LEVER, rod.CENTER_DISTANCE
    rel = []
    for k in range(720):
        phase = math.radians(k / 2.0)
        cx = frame.CAM_SHAFT_XY[0] + gear.ECCENTRICITY * math.sin(phase)
        cy = frame.CAM_SHAFT_XY[1] + gear.ECCENTRICITY * math.cos(phase)
        dx, dy = cx - ox, cy - oy
        d = math.hypot(dx, dy)
        a = (lever**2 - c2c**2 + d * d) / (2.0 * d)
        h = math.sqrt(lever**2 - a * a)
        px, py = ox + a * dx / d + h * dy / d, oy + a * dy / d - h * dx / d
        arm_tilt = math.degrees(math.atan2(py - oy, ox - px)) - ck._ARM_LEVER_BETA_DEG
        rod_tilt = math.degrees(math.atan2(px - cx, py - cy))
        rel.append(arm_tilt - rod_tilt)
    return min(rel), max(rel)


def test_crotch_clears_the_arm_through_the_whole_swing() -> None:
    low, high = _relative_swing_deg()
    assert max(abs(low), abs(high)) <= pin.ARM_TO_ROD_SWING_DEG
    assert (low, high) == pytest.approx((-8.60, 1.01), abs=0.01)


def test_fork_stays_clear_of_the_amplitude_bar_foot() -> None:
    """The bar foot slides along the arm's top edge up to the full amplitude
    either side of the pivot; the fork sits a lever's length out, below the
    top edge, so neither the foot nor its notch cheeks can reach it."""
    travel = _config.machine("amplitude", "max_travel_mm")
    foot_reach = math.hypot(travel + bar.BAR_WIDTH / 2.0, arm.TOP_EDGE_ABOVE_PIVOT)
    fork_reach = ck._ARM_ROD_LEVER - math.hypot(
        rod.FORK_WIDTH / 2.0, rod.FORK_BASE_BELOW_PIN
    )
    assert fork_reach - foot_reach > 25.0
    # The crown also stays under the foot cheeks' hang below the top edge.
    top_edge_above_pin = arm.ARM_DEPTH - arm.ROD_HOLE_ABOVE_BOTTOM
    assert top_edge_above_pin - rod.FORK_CROWN_RADIUS > bar.BOTTOM_NOTCH_HEIGHT
