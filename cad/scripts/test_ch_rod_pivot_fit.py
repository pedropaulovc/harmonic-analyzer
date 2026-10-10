"""Offline contract: the rod fork straddles its rocker arm in one plane, and
the MHA-CH-010 pin is pressed into the fork's reamed tines and runs in the
arm, with every fit held at the worst case of its printed bands (policy rule
12). Press fit, ends dressed flush: the user's ruling (2026-10-09, PR #1292
review F1), the MHA-CH-011 bar pin's joint (``test_ch_bar_pivot_fit``).

``ch_rod_pivot_pin_spec`` reads only the two parts it joins; the restated
floors and the swing it designs for are pinned to their sources here.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

import _config
import cam_plane
import ch_amplitude_bar_spec as bar
import ch_bar_pivot_pin_spec as bar_pin
import channel_frame_geom as frame
import channel_kinematics as ck
import ch_connecting_rod_notes as rod_notes
import ch_connecting_rod_spec as rod
import ch_rocker_arm_notes as arm_notes
import ch_rocker_arm_spec as arm
import ch_rod_pivot_pin_spec as pin
import dt_cylinder_gear_spec as gear
import rocker_bank_layout as bank
from _hole_spec import NUMBER_DRILL_MM


def test_restated_floors_are_their_sources() -> None:
    drilled = _config.title_block("drilled_hole")
    assert (drilled["minus_mm"], drilled["plus_mm"]) == (0.0, pin.DRILLED_PLUS)
    assert pin.RUNNING_FLOOR == bank.RUNNING_FLOOR
    assert pin.MARGIN_SPARE == bank.MARGIN_SPARE
    assert arm.LINEAR_2PL == pytest.approx(
        _config.title_block("linear_2pl")["value_in"] * 25.4
    )
    # The hubs set the pitch the neighbour stack is judged at.
    assert arm.HUB_LENGTH == bank.PITCH and arm.HUB_LENGTH_BAND[1] == 0.0
    # FN2's 0.85 thou cap, as the bar pin's press.
    assert pin.PRESS_INTERFERENCE_MAX == pytest.approx(0.0215900, abs=1e-9)
    assert pin.PRESS_INTERFERENCE_MAX == bar_pin.PRESS_INTERFERENCE_MAX


def test_the_rod_arm_and_cam_share_one_plane() -> None:
    assert bank.ARM_MID_DZ == cam_plane.CAM_MID_DZ
    assert cam_plane.CAM_MID_DZ == pytest.approx(
        -(gear.FACE_WIDTH + gear.CAM_THICKNESS) / 2.0
    )
    # The pin is centred on the fork, which is centred on the rod plane.
    assert pin.PIN_INSTALLED_LENGTH == rod.FORK_THICKNESS


def test_the_pin_is_pressed_in_the_fork_and_runs_in_the_arm() -> None:
    """The bar pin's joint: the same drill rod pressed into the same Ø1.968
    +0.010/0 ream, running in a drilled #47 in the moving member."""
    assert pin.PIN_DIA == bar_pin.PIN_DIA
    assert pin.PIN_DIA_TOLERANCE == bar_pin.PIN_DIA_TOLERANCE
    assert pin.ROD_HOLE_DIA == rod.PIN_HOLE_DIA == bar.TOP_PIN_HOLE_DIA
    assert pin.ROD_HOLE_BAND == rod.PIN_HOLE_BAND == bar.TOP_PIN_HOLE_BAND
    assert arm.ROD_HOLE_SPEC.kind == "drilled_number"
    assert arm.ROD_HOLE_SPEC.size == "#47"
    assert pin.PIN_END_PROUD_MAX == 0.0
    # Nothing is sunk into the tines and nothing is upset (the peened design).
    for gone in ("PIN_HOLE_SPEC", "PIN_HOLE_CSK_DIA", "PIN_HOLE_CSK_BAND"):
        assert not hasattr(rod, gone)
    for gone in ("PIN_CSK_DIA", "RETENTION_OVERLAP_MIN"):
        assert not hasattr(pin, gone)


def test_worst_case_joint_budget() -> None:
    b = pin.BUDGET
    # The press, at the pin's +/-0.005 against the ream's +0.010/0.
    assert b["interference_min"] == pytest.approx(0.001375, abs=1e-6)
    assert b["interference_max"] == pytest.approx(0.021375, abs=1e-6)
    assert 0.0 < b["interference_min"] <= b["interference_max"]
    assert b["interference_max"] <= pin.PRESS_INTERFERENCE_MAX
    # The run, in the arm's #47 (1.994 +0.10/0).
    assert b["running_clearance_min"] == pytest.approx(0.004625, abs=1e-6)
    assert b["running_clearance_max"] == pytest.approx(0.114625, abs=1e-6)
    assert b["side_clearance_min"] == pytest.approx(0.100, abs=1e-6)
    assert b["side_clearance_max"] == pytest.approx(0.277, abs=1e-6)
    assert b["neighbour_clearance_min"] == pytest.approx(0.4545, abs=1e-6)
    assert b["neighbour_clearance_min"] >= pin.NEIGHBOUR_CLEARANCE_MIN
    assert b["tine_min"] == pytest.approx(1.5865, abs=1e-6)
    assert b["tine_bearing_land_min"] == b["tine_min"]
    assert b["tine_bearing_land_min"] >= pin.RULE12_WALL_FLOOR
    assert b["crown_wall_min"] >= pin.RULE12_WALL_TARGET
    assert b["crotch_clearance_min"] == pytest.approx(1.2029, abs=1e-4)
    assert b["crotch_clearance_min"] >= pin.CROTCH_CLEARANCE_MIN
    assert b["bridge_min"] == pytest.approx(2.234, abs=1e-6)
    assert b["bridge_min"] >= pin.BRIDGE_TARGET
    # Dressing stock: the shortest blank still covers the thickest fork.
    assert b["blank_excess_min"] == pytest.approx(0.145, abs=1e-6)
    assert b["blank_excess_max"] == pytest.approx(0.505, abs=1e-6)
    assert not any(key.startswith(("upset", "retention")) for key in b)


def test_the_pin_bears_on_the_whole_tine() -> None:
    """PR #1292 review F1: the land the pin bears on in each tine is the
    thinnest tine itself, built here from the fork's printed bands, and it
    holds rule 12's 1.5 floor. Positive control: the withdrawn 90-degree
    Ø3.2 countersink sunk into each tine mouth, on the #47's largest drill,
    left under that floor."""
    w_min = rod.FORK_THICKNESS + rod.FORK_THICKNESS_BAND[1]
    s_max = rod.FORK_SLOT_WIDTH + rod.FORK_SLOT_BAND[0]
    tine = (w_min - s_max) / 2.0 - rod.FORK_TINE_MATCH / 2.0
    assert pin.BUDGET["tine_bearing_land_min"] == pytest.approx(tine, abs=1e-12)
    assert tine >= pin.RULE12_WALL_FLOOR
    withdrawn_leg = (3.2 - NUMBER_DRILL_MM["#47"]) / 2.0
    assert tine - withdrawn_leg < pin.RULE12_WALL_FLOOR


def test_neighbour_stack_fills_the_inter_arm_gap_exactly() -> None:
    """The gap (pitch less the thickest arm) holds both side clearances,
    both outer tines' slot offsets, the two straps' offsets from their hubs
    and the neighbour clearance: the stack closes with nothing left out. The
    dressed ends are flush, so no pin end stands in it."""
    b = pin.BUDGET
    w_max = rod.FORK_THICKNESS + rod.FORK_THICKNESS_BAND[0]
    off = rod.FORK_TINE_MATCH / 2.0
    float_total = b["side_clearance_max"]
    assert bank.PITCH - (
        w_max + float_total + 2.0 * off + arm.STRAP_HUB_SYMMETRY
    ) == pytest.approx(b["neighbour_clearance_min"])


def _corner_gap(proud: float, strap_offsets: tuple[float, ...]) -> float:
    """Least axial gap between rod j's north-most point and rod j + 1's
    south-most, over every corner of the bands both rods and both arms are
    printed to, built as positions: hub j's mid-plane at 0 and hub j + 1's
    half the two hub lengths north; each strap's mid-plane off its hub's
    by one of ``strap_offsets``; each fork's slot anywhere it still clears
    its strap; each fork's mid-plane off its slot's by half the tine match;
    each dressed pin end ``proud`` of its fork face."""
    t_band = [arm.ARM_THICKNESS + d for d in arm.ARM_THICKNESS_BAND]
    w_band = [rod.FORK_THICKNESS + d for d in rod.FORK_THICKNESS_BAND]
    s_band = [rod.FORK_SLOT_WIDTH + d for d in rod.FORK_SLOT_BAND]
    hubs = [arm.HUB_LENGTH + d for d in arm.HUB_LENGTH_BAND]
    match = (-rod.FORK_TINE_MATCH / 2.0, rod.FORK_TINE_MATCH / 2.0)

    def reach(sign: int) -> list[float]:
        """Offsets of a rod's outer face (pin end included) from its own
        hub's mid-plane, toward the neighbour (+1 north, -1 south)."""
        out = []
        for e, t, w, s, m, side in itertools.product(
            strap_offsets, t_band, w_band, s_band, match, (-1.0, 1.0)
        ):
            slot_centre = e + side * (s - t) / 2.0
            fork_centre = slot_centre + m
            out.append(sign * (fork_centre + sign * (w / 2.0 + proud)))
        return out

    north_j = max(reach(+1))  # rod j's north-most point
    south_next = max(reach(-1))  # how far rod j + 1 reaches south
    pitch = min((a + b) / 2.0 for a, b in itertools.product(hubs, hubs))
    return pitch - north_j - south_next


def test_opposed_neighbour_forks_clear_at_every_band_corner() -> None:
    """PR #1292 review F2: an independent construction of the neighbour
    clearance, rod by rod from positions, not the spec's closed form. Rod j
    leans north on a strap set north of its hub, rod j + 1 south on one set
    south; the budget is exactly that corner."""
    half_zone = arm.STRAP_HUB_SYMMETRY / 2.0
    gap = _corner_gap(pin.PIN_END_PROUD_MAX, (-half_zone, half_zone))
    assert gap == pytest.approx(pin.BUDGET["neighbour_clearance_min"], abs=1e-9)
    assert gap == pytest.approx(0.4545, abs=1e-9)
    assert gap >= pin.NEIGHBOUR_CLEARANCE_MIN
    # Positive controls: the strap symmetry is in the corner (centred straps
    # gain its whole zone), and the withdrawn peened pin (0.10 proud each
    # end) on these straps would have broken the 0.35 floor the earlier
    # budget claimed it held.
    centred = _corner_gap(pin.PIN_END_PROUD_MAX, (0.0,))
    assert centred - gap == pytest.approx(arm.STRAP_HUB_SYMMETRY, abs=1e-9)
    assert _corner_gap(0.10, (-half_zone, half_zone)) < pin.NEIGHBOUR_CLEARANCE_MIN


def test_the_assembly_press_allowance_is_this_joint() -> None:
    """_interference_contracts restates the modelled press as literals (every
    assembly imports it); they must be the nominal pin, the fork's reamed
    hole and the two tines, and name channel j's pin with channel j's rod
    only. The channel's only other press pairs are the bar pins'."""
    import _interference_contracts as ic

    pin_dia, hole_dia, engaged = ic.ROD_PIVOT_PIN_PRESS
    assert pin_dia == pytest.approx(pin.PIN_DIA, abs=1e-9)
    assert hole_dia == rod.PIN_HOLE_DIA
    assert engaged == pytest.approx(rod.FORK_THICKNESS - rod.FORK_SLOT_WIDTH, abs=1e-9)
    pairs = ic.allowed_interference_pairs("ch-channel")
    rod_pairs = {
        frozenset((f"ch-rod-pivot-pin-{n}", f"ch-connecting-rod-{n}"))
        for n in range(1, 21)
    }
    bar_pairs = {
        frozenset((f"ch-bar-pivot-pin-{n}", f"ch-amplitude-bar-{n}"))
        for n in range(1, 21)
    }
    assert set(pairs) == rod_pairs | bar_pairs
    nominal = math.pi / 4.0 * (pin_dia**2 - hole_dia**2) * engaged
    assert all(pairs[pair] == pytest.approx(1.10 * nominal) for pair in rod_pairs)
    # The arm the pin runs in is never a press pair.
    assert not any("rocker-arm" in name for pair in pairs for name in pair)


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
    arm dropped on the pin by its running clearance (the pin is pressed in
    the tines, so it does not drop in them)."""
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
    pin_drop = b["running_clearance_max"] / 2.0
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
