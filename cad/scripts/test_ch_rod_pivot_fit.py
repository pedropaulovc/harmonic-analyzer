"""Offline contract: the rod fork straddles its rocker arm in one plane, and
the peened MHA-CH-010 pin runs in the arm and is retained in the fork, with
every fit held at the worst case of its printed bands (policy rule 12).

``ch_rod_pivot_pin_spec`` reads only the two parts it joins; the restated
floors and the swing it designs for are pinned to their sources here.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

import _config
import build_ch_rod_pivot_pin as pin_build
from _hole_spec import blind_cut_dia_mm
import ch_amplitude_bar_spec as bar
import channel_frame_geom as frame
import channel_kinematics as ck
import ch_connecting_rod_notes as rod_notes
import ch_connecting_rod_spec as rod
import ch_rocker_arm_notes as arm_notes
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


# The #47 the Hole Wizard cuts in the rod's tines (and the arm): the ANSI-inch
# table's 0.0785 in, which _hole_spec.NUMBER_DRILL_MM rounds to 1.994.
_WIZARD_47_DRILL = 0.0785 * 25.4
_TABLE_47_DRILL = blind_cut_dia_mm(rod.PIN_HOLE_SPEC)
_TINE_DEPTHS = np.linspace(0.0, rod.FORK_TINE_THICKNESS, 20001)


def _tine_cavity_r(drill: float, leg: float) -> np.ndarray:
    """Radius of the tine's drill + 90-degree countersink (an equal-leg
    chamfer on the drill mouth) at each depth below the tine's outer face."""
    return np.maximum(drill / 2.0, drill / 2.0 + leg - _TINE_DEPTHS)


def _installed_pin_r() -> np.ndarray:
    """Radius of the installed pin at each depth below its dressed end: the
    45-degree flare from the Ø CskDia rim down to the journal."""
    return np.maximum(pin_build.PIN_R, pin_build.CSK_R - _TINE_DEPTHS)


def _sliver_mm3(drill: float, leg: float) -> float:
    """Volume of the installed pin proud of one tine's drill + countersink."""
    proud = np.maximum(_installed_pin_r(), _tine_cavity_r(drill, leg))
    ring = math.pi * (proud**2 - _tine_cavity_r(drill, leg) ** 2)
    return float(np.trapezoid(ring, _TINE_DEPTHS))


def test_installed_pin_sits_inside_the_tine_hole_and_countersinks() -> None:
    """The native interference gate counts ANY positive pin-rod volume, so the
    installed pin's flare may meet the countersink but never stand proud of it.
    The build cuts the chamfer leg from the drill the wizard reports, which
    puts the countersink rim on PinCskDia whatever the drill's last decimal."""
    # The pin's dressed ends are the tine faces; its flare is the 90-degree
    # countersink's cone from the same Ø rim.
    assert pin_build.HALF_LEN == rod.FORK_THICKNESS / 2.0
    assert pin_build.CSK_R == rod.PIN_HOLE_CSK_DIA / 2.0
    assert pin_build.CSK_DEPTH == pytest.approx(pin_build.CSK_R - pin_build.PIN_R)
    assert pin.PIN_CSK_ANGLE_DEG == 90.0
    for drill in (
        _TABLE_47_DRILL - 0.0005,
        _WIZARD_47_DRILL,
        _TABLE_47_DRILL,
        _TABLE_47_DRILL + 0.0005,
    ):
        leg = (rod.PIN_HOLE_CSK_DIA - drill) / 2.0
        proud = _installed_pin_r() - _tine_cavity_r(drill, leg)
        assert proud.max() <= 1e-12, drill
        assert _sliver_mm3(drill, leg) <= 1e-15, drill
    # The journal runs free in the arm's #47 between the tines.
    assert pin_build.PIN_R < _WIZARD_47_DRILL / 2.0


def test_a_table_drill_leg_leaves_the_pin_flare_proud() -> None:
    """Regression (farm build at 71a6e3107, assembly:ch_channel): the leg
    taken from the table's 1.994 on the 0.0785 in drill the wizard cut left
    the rim Ø3.1999 and every pin's flare 0.05 um proud of it -- the reported
    0.000245865 mm^3 per pin end."""
    table_leg = (rod.PIN_HOLE_CSK_DIA - _TABLE_47_DRILL) / 2.0
    proud = _installed_pin_r() - _tine_cavity_r(_WIZARD_47_DRILL, table_leg)
    assert proud.max() == pytest.approx((_TABLE_47_DRILL - _WIZARD_47_DRILL) / 2.0)
    assert _sliver_mm3(_WIZARD_47_DRILL, table_leg) == pytest.approx(
        0.000245865, rel=2e-3
    )


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
    assert b["crotch_clearance_min"] == pytest.approx(1.1524, abs=1e-4)
    assert b["crotch_clearance_min"] >= pin.CROTCH_CLEARANCE_MIN
    assert b["bridge_min"] == pytest.approx(2.234, abs=1e-6)
    assert b["bridge_min"] >= pin.BRIDGE_TARGET


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


def _relative_swing_deg() -> list[float]:
    """Arm tilt less rod tilt at each half-degree of one cam turn (degrees)."""
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
    return rel


def test_restated_swing_brackets_the_solved_loop() -> None:
    rel = _relative_swing_deg()
    lo, hi = pin.RELATIVE_SWING_DEG
    assert lo <= min(rel) <= lo + 0.01
    assert hi - 0.01 <= max(rel) <= hi


def _arm_bottom_silhouette(
    r_top: float, r_bottom: float, top_above_pivot: float
) -> np.ndarray:
    """Arm-frame points along the arm's lower outline near the rod pin: the
    bottom arc, then the straight taper to the tip land (arm notes 3-5)."""
    cy = arm.PIVOT_MID_Y + top_above_pivot + r_top
    a_bot = arm.BOT_ARC_LEN / 2.0 / r_bottom
    a_top = arm.TOP_ARC_LEN / 2.0 / r_top
    bot_end = np.array([r_bottom * math.sin(a_bot), cy - r_bottom * math.cos(a_bot)])
    tip = np.array(
        [
            (r_top + arm.TIP_FACE) * math.sin(a_top),
            cy - (r_top + arm.TIP_FACE) * math.cos(a_top),
        ]
    )
    x = np.arange(arm.ROD_HOLE_X - 10.0, bot_end[0], 0.005)
    arc = np.stack([x, cy - np.sqrt(r_bottom**2 - x * x)], axis=1)
    t = np.linspace(0.0, 1.0, 2001)[:, None]
    return np.concatenate([arc, bot_end + t * (tip - bot_end)])


def test_crotch_clears_the_arm_through_the_whole_swing() -> None:
    """Every printed-band corner of the arm's curved lower outline and the
    fork's slot floor, at every solved pose of one cam turn: the floor stays
    CROTCH_CLEARANCE_MIN below the arm with both pin holes wandered and the
    pin dropped in its clearances."""
    two_place = arm.LINEAR_2PL
    # The bands the sweep reads are the ones the sheets print.
    assert "SlotDepth" not in rod_notes.DRAWING_PRECISION.get("ForkSlotProfile", {})
    assert "ForkWidthDim" not in rod_notes.DRAWING_PRECISION.get("ForkProfile", {})
    assert arm_notes.DRAWING_DIMENSIONS["StrapProfile"] == {"TopRadius", "BottomRadius"}
    assert arm_notes.DEFAULT_DRAWING_PRECISION == 2
    rad = np.radians(np.array(_relative_swing_deg()))
    cos, sin = np.cos(rad)[:, None], np.sin(rad)[:, None]
    hole = np.array([arm.ROD_HOLE_X, arm.ROD_HOLE_Y])
    slot_depth = rod.FORK_TOP_Y - rod.FORK_CROTCH_Y
    worst = math.inf
    for r_top, r_bottom, top_above_pivot in itertools.product(
        (arm.R_TOP - two_place, arm.R_TOP + two_place),
        (arm.R_BOTTOM - two_place, arm.R_BOTTOM + two_place),
        (
            arm.TOP_EDGE_ABOVE_PIVOT + arm.TOP_EDGE_BAND[1],
            arm.TOP_EDGE_ABOVE_PIVOT + arm.TOP_EDGE_BAND[0],
        ),
    ):
        local = _arm_bottom_silhouette(r_top, r_bottom, top_above_pivot) - hole
        # Rows are poses, columns outline points, in the rod frame (pin at
        # the origin): the arm turned CCW on the pin by the relative swing.
        x = cos * local[:, 0] - sin * local[:, 1]
        y = sin * local[:, 0] + cos * local[:, 1]
        for width in (rod.FORK_WIDTH - two_place, rod.FORK_WIDTH + two_place):
            low = np.where(np.abs(x) <= width / 2.0, y, np.inf).min()
            for depth in (slot_depth - two_place, slot_depth + two_place):
                worst = min(worst, low - (width / 2.0 - depth))
    b = pin.BUDGET
    hole_wander = (
        float(rod.GEOMETRIC_TOLERANCES_MM["rocker pin hole position"])
        + float(arm.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
    ) / 2.0
    pin_drop = (b["running_clearance_max"] + b["tine_hole_clearance_max"]) / 2.0
    clearance = worst - hole_wander - pin_drop
    assert clearance >= pin.CROTCH_CLEARANCE_MIN
    # The spec's closed-form budget is the same envelope, on its restated swing.
    assert b["crotch_clearance_min"] == pytest.approx(clearance, abs=0.005)
    assert b["crotch_clearance_min"] <= clearance


def test_fork_bridge_below_the_slot_holds_the_rule_12_target() -> None:
    """The bridge joining the tines under the slot floor: ForkBossLength less
    SlotDepth, both measured at two places from the crown top."""
    two_place = arm.LINEAR_2PL
    assert "ForkBossLength" not in rod_notes.DRAWING_PRECISION.get(
        "ForkSlotProfile", {}
    )
    boss_length = rod.FORK_TOP_Y - rod.FORK_BASE_Y
    slot_depth = rod.FORK_TOP_Y - rod.FORK_CROTCH_Y
    bridge = (boss_length - two_place) - (slot_depth + two_place)
    assert bridge == pytest.approx(pin.BUDGET["bridge_min"], abs=1e-9)
    assert bridge >= pin.BRIDGE_TARGET >= pin.RULE12_WALL_FLOOR


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
