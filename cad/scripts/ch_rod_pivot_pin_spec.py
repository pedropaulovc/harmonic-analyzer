r"""Rod pivot pin (MHA-CH-010) and the rod-fork-to-rocker joint it closes.

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the
pattern). The part build (``build_ch_rod_pivot_pin.py``), its drawing, the
channel assembly and ``test_ch_rod_pivot_fit`` import it; it reads only the
two parts it joins, so the pin never re-keys on bank layout or config.

The joint: each connecting rod's fork (``ch_connecting_rod_spec``) straddles
its rocker arm (``ch_rocker_arm_spec``) in the arm's own plane, and one plain
5/64 drill-rod pin runs through both tines and the arm's #47 rod hole. The
pin RUNS in the arm (the one moving member) and is PRESSED into holes reamed
through both tines, its ends dressed flush with the fork's faces, exactly as
the MHA-CH-011 bar pin (``ch_bar_pivot_pin_spec``) is pressed into the
amplitude bar. Press-fit retention is the user's ruling (2026-10-09, PR #1292
review F1): a 90-degree Ø3.2 countersink sunk into each tine for a peened end
left 0.92 of bearing land under the pin, below rule 12's 1.5 floor, so the
ruling reverses the #746 reconstruction choice of peening. A pressed pin
drives out with a punch.

Frame (part): pin axis = part Z, axial mid-plane = Front Plane (z = 0); the
model is the INSTALLED pin -- a Ø PIN_DIA cylinder FORK_THICKNESS long, flush
with both tines. The shop cuts the blank PIN_BLANK_LENGTH long; the drawing
states that.
"""

from __future__ import annotations

import math

import ch_connecting_rod_spec as _rod
import ch_rocker_arm_spec as _arm
from _hole_spec import NUMBER_DRILL_MM

MM_PER_IN = 25.4

# --- Title-block drilled-hole band, restated (test_ch_rod_pivot_fit pins it to
# title_block.yaml): a twist drill cuts on-size to oversize. ---
DRILLED_PLUS = 0.10

# --- The pin: 5/64 drill rod (AISI O1/W1 drill rod or 1018 pin stock, used
# annealed as supplied; ground to +/-0.0002 in). ---
PIN_DIA = 5.0 / 64.0 * MM_PER_IN  # 1.984
PIN_DIA_TOLERANCE = 0.005  # +/-, drill-rod grind
PIN_INSTALLED_LENGTH = _rod.FORK_THICKNESS  # dressed flush with both tines
# Cut length of the blank: the fork plus dressing stock at each end. 2-place,
# printed on the pin sheet with its band (the bar pin's pattern).
PIN_BLANK_LENGTH = 6.40
PIN_BLANK_LENGTH_BAND = (0.13, -0.13)  # (upper, lower) deviations
# Dressed ends stand nothing proud of the tine faces (the press-fit ruling).
PIN_END_PROUD_MAX = 0.0

# --- The fork's reamed press hole (the rod spec owns it; restated here so the
# budget reads one place). ---
ROD_HOLE_DIA = _rod.PIN_HOLE_DIA
ROD_HOLE_BAND = _rod.PIN_HOLE_BAND

# --- The joint's limits (the budget test_ch_rod_pivot_fit holds). ---
# The tightest press the tines take: ANSI B4.1-1967 (R1987) FN2 "medium drive
# fit, suitable for ordinary steel parts", nominal size 0-0.12 in:
# interference 0.2-0.85 thousandths of an inch. Its 0.85 thou maximum caps the
# press; the minimum only has to stay positive (the pin carries no axial load:
# the arm bears on it radially and the tines hold it square).
PRESS_INTERFERENCE_MAX = 0.00085 * MM_PER_IN  # 0.0216
RULE12_WALL_TARGET = 2.0  # drawing-simplicity policy rule 12
RULE12_WALL_FLOOR = 1.5
RUNNING_FLOOR = 0.10  # rocker_bank_layout.RUNNING_FLOOR: oiled steel faces
MARGIN_SPARE = 0.25  # rocker_bank_layout.MARGIN_SPARE: novice spare
NEIGHBOUR_CLEARANCE_MIN = RUNNING_FLOOR + MARGIN_SPARE  # 0.35
CROTCH_CLEARANCE_MIN = 1.0  # slot floor below the arm's bottom edge, all poses
BRIDGE_TARGET = 2.0  # fork bridge below the slot floor: the rule-12 target
# Arm tilt less rod tilt, the swing the crotch must clear: the solved loop
# (channel_kinematics, cam phase 0..360) spans -8.662..+1.061 deg with the
# rod closing the raised drive axis to the level rocker, restated here
# rounded outward (test_ch_rod_pivot_fit pins it to the solved loop).
RELATIVE_SWING_DEG = (-8.67, 1.07)
_SWING_STEPS = 400


def _band(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    return nominal + band[1], nominal + band[0]


def _arm_bottom_low(
    theta_deg: float,
    r_top: float,
    r_bottom: float,
    top_above_pivot: float,
    half_width: float,
) -> float:
    """Lowest point of the arm's bottom edge across the fork window
    |x| <= half_width, in the rod frame (pin at the origin, rod axis +y),
    the arm turned ``theta_deg`` CCW on the pin relative to the rod.

    The edge is the r_bottom arc concentric with the r_top top edge, whose
    centre stands top_above_pivot + r_top over the pivot. Past the arc's end
    the tip taper rises above the arc's continuation, so the continued arc
    bounds the edge from below. The centre lies far to the pivot side of the
    window, so the arc climbs across it: the window's pivot-side end is its
    lowest point.
    """
    t = math.radians(theta_deg)
    x0 = -_arm.ROD_HOLE_X
    y0 = _arm.PIVOT_MID_Y + top_above_pivot + r_top - _arm.ROD_HOLE_Y
    cx = x0 * math.cos(t) - y0 * math.sin(t)
    cy = x0 * math.sin(t) + y0 * math.cos(t)
    if cx >= -half_width:
        raise AssertionError("arm edge arc centre inside the fork window")
    return cy - math.sqrt(r_bottom**2 - (half_width + cx) ** 2)


def joint_budget() -> dict[str, float]:
    """Worst-case values of every fit the joint must hold (all mm).

    Every term is at the worst case of its printed band (policy rule 12):
    the drill rod +/-0.005, the reamed tine hole +0.010/0, the arm's #47 hole
    +0.10/0, the arm strap 2.500 +/-0.025 and symmetric to its hub within
    STRAP_HUB_SYMMETRY, the fork 6.075 +/-0.05, the slot 2.625 +0.127/0, the
    tines equal within FORK_TINE_MATCH, the hubs that set the pitch never
    shorter than nominal; the fork outline, slot depth and arm radii at the
    title block's .XX class, the arm's top edge 8.0 +0.5/0 over its pivot.
    """
    t_min, t_max = _band(_arm.ARM_THICKNESS, _arm.ARM_THICKNESS_BAND)
    w_min, w_max = _band(_rod.FORK_THICKNESS, _rod.FORK_THICKNESS_BAND)
    s_min, s_max = _band(_rod.FORK_SLOT_WIDTH, _rod.FORK_SLOT_BAND)
    blank_min, blank_max = _band(PIN_BLANK_LENGTH, PIN_BLANK_LENGTH_BAND)
    hole_min, hole_max = _band(ROD_HOLE_DIA, ROD_HOLE_BAND)
    arm_hole_min = NUMBER_DRILL_MM[_arm.ROD_HOLE_SPEC.size]
    arm_hole_max = arm_hole_min + DRILLED_PLUS
    pin_min, pin_max = PIN_DIA - PIN_DIA_TOLERANCE, PIN_DIA + PIN_DIA_TOLERANCE
    off_centre = _rod.FORK_TINE_MATCH / 2.0
    pitch_min = _arm.HUB_LENGTH  # hubs bear face on face; +0.05/0 band
    # Each rod floats on its own arm's strap by the slot's side clearance, and
    # each strap stands off its hub's mid-plane by up to half its symmetry
    # zone: rod j's fork leans north on a strap set north, rod j+1's south on
    # a strap set south, each face at half the fork plus its float and the
    # slot's off-centre, each dressed pin end flush. The ring's symmetry to
    # the slot does not enter: the fork's reach from its strap is bounded by
    # the slot float alone, wherever the ring rides in its cam slot.
    side_clearance_max = s_max - t_min
    neighbour = (
        pitch_min
        - w_max
        - side_clearance_max
        - 2.0 * off_centre
        - _arm.STRAP_HUB_SYMMETRY
        - 2.0 * PIN_END_PROUD_MAX
    )
    tine_min = (w_min - s_max) / 2.0 - off_centre
    # Arm material inside the slot: the arm's bottom-edge arc, lowest at the
    # print-worst corner (top radius short, bottom radius long, top edge at
    # its MIN height over the pivot), swept through the relative swing across
    # the widest fork's window.
    two_place = _arm.LINEAR_2PL
    half_width = (_rod.FORK_WIDTH + two_place) / 2.0
    lo, hi = RELATIVE_SWING_DEG
    edge_low = min(
        _arm_bottom_low(
            lo + (hi - lo) * k / _SWING_STEPS,
            _arm.R_TOP - two_place,
            _arm.R_BOTTOM + two_place,
            _arm.TOP_EDGE_ABOVE_PIVOT + _arm.TOP_EDGE_BAND[1],
            half_width,
        )
        for k in range(_SWING_STEPS + 1)
    )
    # The slot floor stands SlotDepth below the crown top (half the fork
    # width over the pin): highest with the fork widest and the slot shallowest.
    floor_high = half_width - (
        _rod.FORK_WIDTH / 2.0 + _rod.FORK_CROTCH_BELOW_PIN - two_place
    )
    # Each pin hole wanders by half its position zone, and the arm drops on
    # the pin by half its running clearance (the pin is pressed in the tines).
    hole_wander = (
        float(_rod.GEOMETRIC_TOLERANCES_MM["rocker pin hole position"])
        + float(_arm.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
    ) / 2.0
    pin_drop = (arm_hole_max - pin_min) / 2.0
    # The crown radius rides the fork width at the title block's .XX class,
    # and the reamed hole wanders by half its position zone.
    crown_loss = _arm.LINEAR_2PL / 2.0 + (
        float(_rod.GEOMETRIC_TOLERANCES_MM["rocker pin hole position"]) / 2.0
    )
    return {
        "interference_min": pin_min - hole_max,
        "interference_max": pin_max - hole_min,
        "running_clearance_min": arm_hole_min - pin_max,
        "running_clearance_max": arm_hole_max - pin_min,
        "side_clearance_min": s_min - t_max,
        "side_clearance_max": side_clearance_max,
        "neighbour_clearance_min": neighbour,
        "tine_min": tine_min,
        # The reamed hole runs straight through each tine (nothing sunk into
        # its mouths), so the pin bears on the tine's whole thickness.
        "tine_bearing_land_min": tine_min,
        "crotch_clearance_min": edge_low - floor_high - hole_wander - pin_drop,
        # ForkBossLength less SlotDepth, both .XX from the crown top.
        "bridge_min": (
            _rod.FORK_BASE_BELOW_PIN - _rod.FORK_CROTCH_BELOW_PIN - 2.0 * two_place
        ),
        "crown_wall_min": _rod.FORK_CROWN_RADIUS - crown_loss - hole_max / 2.0,
        "blank_excess_min": blank_min - w_max,
        "blank_excess_max": blank_max - w_min,
    }


BUDGET = joint_budget()
if BUDGET["interference_min"] <= 0.0:
    raise AssertionError("the loosest pin can slide out of the largest reamed hole")
if BUDGET["interference_max"] > PRESS_INTERFERENCE_MAX + 1e-9:
    raise AssertionError("the tightest press exceeds ANSI FN2 for the fork tines")
if BUDGET["running_clearance_min"] <= 0.0:
    raise AssertionError("pin can seize in the arm's rod hole")
if BUDGET["side_clearance_min"] < RUNNING_FLOOR - 1e-9:
    raise AssertionError("fork slot can close on the thickest arm")
if BUDGET["neighbour_clearance_min"] < NEIGHBOUR_CLEARANCE_MIN - 1e-9:
    raise AssertionError("neighbouring forks can touch in the inter-arm gap")
if BUDGET["tine_bearing_land_min"] < RULE12_WALL_FLOOR - 1e-9:
    raise AssertionError("the pin's land in a tine is under the rule-12 floor")
if BUDGET["crotch_clearance_min"] < CROTCH_CLEARANCE_MIN - 1e-9:
    raise AssertionError("fork crotch can strike the arm's bottom edge")
if BUDGET["bridge_min"] < BRIDGE_TARGET - 1e-9:
    raise AssertionError("fork bridge below the slot under the 2.0 target")
if BUDGET["crown_wall_min"] < RULE12_WALL_TARGET - 1e-9:
    raise AssertionError("reamed hole to fork crown under the rule-12 target")
if BUDGET["blank_excess_min"] <= 0.0:
    raise AssertionError("pin blank too short to dress flush at both tines")
if PIN_INSTALLED_LENGTH != _rod.FORK_THICKNESS:
    raise AssertionError("the installed pin must be flush with both tines")
