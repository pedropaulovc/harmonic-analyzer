r"""RodPin member of MHA-SH-VN-58 and the rod-fork-to-rocker joint it closes.

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the
pattern). The part build (``build_sh_vn_pivot_pin.py``), the channel assembly
and ``test_sh_vn_pivot_pin_rod_fit`` import it; it reads only the two parts it
joins and the purchased pin (``sh_vn_pivot_pin_spec``), so the pin never
re-keys on bank layout or config.

The joint: each connecting rod's fork (``ch_connecting_rod_spec``) straddles
its rocker arm (``ch_rocker_arm_spec``) in the arm's own plane, and one
purchased 5/64 x 5/16 dowel runs through both tines and the arm's #47 rod
hole. The pin RUNS in the arm (the one moving member) and is PRESSED into
holes reamed through both tines, its ends dressed flush with the fork's
faces, exactly as the BarPin member (``sh_vn_pivot_pin_bar_spec``) is pressed
into the amplitude bar. Press-fit retention is the user's ruling (2026-10-09,
PR #1292 review F1): a 90-degree Ø3.2 countersink sunk into each tine for a
peened end left 0.92 of bearing land under the pin, below drawing-guidelines.md rule 17 (walls and webs)'s 1.5 floor, so the
ruling reverses the #746 reconstruction choice of peening. A pressed pin
drives out with a punch.

Frame (part): pin axis = part Z, axial mid-plane = Front Plane (z = 0); the
member is the INSTALLED pin -- a Ø PIN_DIA cylinder FORK_THICKNESS long, flush
with both tines.
"""

from __future__ import annotations

import math

import ch_connecting_rod_spec as _rod
import ch_rocker_arm_spec as _arm
import _rocker_interface as rocker_interface
import sh_vn_pivot_pin_spec as _pin
from _hole_spec import NUMBER_DRILL_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

# --- The arm sheet's drilled-hole band (its #47 rod hole): a twist drill
# cuts on-size to oversize. ---
DRILLED_PLUS = drilled_oversize_mm(unit=_arm.UNIT)
# The rod sheet's .XX band: its fork outline, slot depth and boss length.
ROD_LINEAR_2PL = printed_band_mm(2, unit=_rod.UNIT)

# --- The pin: the purchased dowel (McMaster 90145A299, 0/+.0002 in on its
# 5/64 diameter), used as supplied: pressed through and dressed flush. ---
CONFIGURATION = _pin.ROD_PIN_CONFIGURATION
BOM_DESCRIPTION = "ROD PIVOT PIN"
PIN_DIA = _pin.PIN_DIA  # 1.984
PIN_DIA_LIMITS = _pin.PIN_DIA_LIMITS
PIN_INSTALLED_LENGTH = _rod.FORK_THICKNESS  # dressed flush with both tines
# The supplied length (5/16 in, ASME B18.8.2 +/-.010 assumed) stands proud of
# both tines before dressing: the shortest pin over the thickest fork leaves
# the stock both dressed ends share.
PIN_LENGTH_LIMITS = _pin.PIN_LENGTH_LIMITS
# Dressed ends stand nothing proud of the tine faces (the press-fit ruling).
PIN_END_PROUD_MAX = 0.0

# --- The fork's reamed press hole (the rod spec owns it; restated here so the
# budget reads one place). ---
ROD_HOLE_DIA = _rod.PIN_HOLE_DIA
ROD_HOLE_BAND = _rod.PIN_HOLE_BAND

# --- The joint's limits (the budget test_sh_vn_pivot_pin_rod_fit holds). ---
# The press the tines take: ANSI B4.1-1967 (R1987) FN2 "medium drive fit,
# suitable for ordinary steel parts", nominal size 0-0.12 in: interference
# 0.2-0.85 thousandths of an inch. Its 0.85 thou maximum caps the press; the
# loosest pin in the largest hole still presses at its 0.2 thou minimum (the
# pin carries no axial load: the arm bears on it radially and the tines hold
# it square).
PRESS_INTERFERENCE_MIN, PRESS_INTERFERENCE_MAX = _pin.FN2_INTERFERENCE
RULE12_WALL_TARGET = WALL_TARGET_MM  # drawing-guidelines.md rule 17: .080 in
RULE12_WALL_FLOOR = WALL_FLOOR_MM  # .060 in
RUNNING_FLOOR = 0.10  # rocker_bank_layout.RUNNING_FLOOR: oiled steel faces
MARGIN_SPARE = 0.25  # rocker_bank_layout.MARGIN_SPARE: novice spare
NEIGHBOUR_CLEARANCE_MIN = RUNNING_FLOOR + MARGIN_SPARE  # 0.35
CROTCH_CLEARANCE_MIN = 1.0  # slot floor below the arm's bottom edge, all poses
BRIDGE_TARGET = WALL_TARGET_MM  # fork bridge below the slot floor: the drawing-guidelines.md rule 17 (walls and webs) target
# Arm tilt less rod tilt, the swing the crotch must clear: the solved loop
# (channel_kinematics, cam phase 0..360) spans -8.662..+1.061 deg with the
# rod closing the raised drive axis to the level rocker, restated here
# rounded outward (test_sh_vn_pivot_pin_rod_fit pins it to the solved loop).
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
    x0 = -rocker_interface.ROD_HOLE_X
    y0 = rocker_interface.PIVOT_MID_Y + top_above_pivot + r_top - rocker_interface.ROD_HOLE_Y
    cx = x0 * math.cos(t) - y0 * math.sin(t)
    cy = x0 * math.sin(t) + y0 * math.cos(t)
    if cx >= -half_width:
        raise AssertionError("arm edge arc centre inside the fork window")
    return cy - math.sqrt(r_bottom**2 - (half_width + cx) ** 2)


def joint_budget() -> dict[str, float]:
    """Worst-case values of every fit the joint must hold (all mm).

    Every term is at the worst case of its printed band (drawing-guidelines.md rule 17 (walls and webs)):
    the purchased pin's 0/+.0002 in, the reamed tine hole +.0009/+.0005, the
    arm's #47 hole at its sheet's DRILLED HOLES row, the arm strap and its
    symmetry to its hub (STRAP_HUB_SYMMETRY), each tine .067 +/-.002, the slot
    .106 +/-.002 (so the fork over the tines, their reference sum, spans
    FORK_THICKNESS_BAND), the hubs that set the pitch never shorter than
    nominal; the fork outline and slot depth at the rod sheet's .XX band, the
    arm radii at the arm sheet's, the arm's top edge at its TOP_EDGE_BAND over
    its pivot; the supplied pin at its shortest length.
    """
    t_min, t_max = _band(_arm.ARM_THICKNESS, _arm.ARM_THICKNESS_BAND)
    _w_min, w_max = _band(_rod.FORK_THICKNESS, _rod.FORK_THICKNESS_BAND)
    s_min, s_max = _band(_rod.FORK_SLOT_WIDTH, _rod.FORK_SLOT_BAND)
    tine_min, tine_max = _band(_rod.TINE_THICKNESS, _rod.TINE_BAND)
    hole_min, hole_max = _band(ROD_HOLE_DIA, ROD_HOLE_BAND)
    arm_hole_min = NUMBER_DRILL_MM[_arm.ROD_HOLE_SPEC.size]
    arm_hole_max = arm_hole_min + DRILLED_PLUS
    pin_min, pin_max = PIN_DIA_LIMITS
    pitch_min = _arm.HUB_LENGTH  # hubs bear face on face; +0.05/0 band
    # Each rod floats on its own arm's strap by the slot's side clearance, and
    # each strap stands off its hub's mid-plane by up to half its symmetry
    # zone: rod j's fork leans north on a strap set north, rod j+1's south on
    # a strap set south. With its slot's trailing wall on the strap, a fork's
    # leading face stands the slot plus a tine, less half the strap, past the
    # strap's mid-plane, each dressed pin end flush. The ring's place on the
    # plate does not enter: the fork's reach from its strap is bounded by the
    # slot and tine alone, wherever the ring rides in its cam slot.
    side_clearance_max = s_max - t_min
    neighbour = (
        pitch_min
        - 2.0 * (s_max + tine_max - t_min / 2.0)
        - _arm.STRAP_HUB_SYMMETRY
        - 2.0 * PIN_END_PROUD_MAX
    )
    # Arm material inside the slot: the arm's bottom-edge arc, lowest at the
    # print-worst corner (top radius short, bottom radius long, top edge at
    # its MIN height over the pivot), swept through the relative swing across
    # the widest fork's window.
    arm_2pl = _arm.LINEAR_2PL
    half_width = (_rod.FORK_WIDTH + ROD_LINEAR_2PL) / 2.0
    lo, hi = RELATIVE_SWING_DEG
    edge_low = min(
        _arm_bottom_low(
            lo + (hi - lo) * k / _SWING_STEPS,
            _arm.R_TOP - arm_2pl,
            rocker_interface.R_BOTTOM + arm_2pl,
            _arm.TOP_EDGE_ABOVE_PIVOT + _arm.TOP_EDGE_BAND[1],
            half_width,
        )
        for k in range(_SWING_STEPS + 1)
    )
    # The slot floor stands SlotDepth below the crown top (half the fork
    # width over the pin): highest with the fork widest and the slot shallowest.
    floor_high = half_width - (
        _rod.FORK_WIDTH / 2.0 + _rod.FORK_CROTCH_BELOW_PIN - ROD_LINEAR_2PL
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
    crown_loss = ROD_LINEAR_2PL / 2.0 + (
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
            _rod.FORK_BASE_BELOW_PIN - _rod.FORK_CROTCH_BELOW_PIN - 2.0 * ROD_LINEAR_2PL
        ),
        "crown_wall_min": _rod.FORK_CROWN_RADIUS - crown_loss - hole_max / 2.0,
        # The shortest supplied pin over the thickest fork: the dressing stock
        # both ends share, and each end's share with the pin pressed centred.
        "length_excess_min": PIN_LENGTH_LIMITS[0] - w_max,
        "dress_stock_per_end_min": (PIN_LENGTH_LIMITS[0] - w_max) / 2.0,
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
    raise AssertionError("the pin's land in a tine is under the drawing-guidelines.md rule 17 (walls and webs) floor")
if BUDGET["crotch_clearance_min"] < CROTCH_CLEARANCE_MIN - 1e-9:
    raise AssertionError("fork crotch can strike the arm's bottom edge")
# The slot floor's corner radii stand no higher than the arm's least
# clearance over the floor, so the arm never meets them.
if _rod.INSIDE_CORNER_R >= BUDGET["crotch_clearance_min"]:
    raise AssertionError("the slot floor's corner radii reach the arm's bottom edge")
if BUDGET["bridge_min"] < BRIDGE_TARGET - 1e-9:
    raise AssertionError("fork bridge below the slot under the .080 in target")
if BUDGET["crown_wall_min"] < RULE12_WALL_TARGET - 1e-9:
    raise AssertionError("reamed hole to fork crown under the drawing-guidelines.md rule 17 (walls and webs) target")
if BUDGET["length_excess_min"] <= 0.0:
    raise AssertionError("the shortest supplied pin cannot dress flush at both tines")
if BUDGET["dress_stock_per_end_min"] < 0.0:
    raise AssertionError("a centred pin leaves a tine end short of its face")
if PIN_INSTALLED_LENGTH != _rod.FORK_THICKNESS:
    raise AssertionError("the installed pin must be flush with both tines")
