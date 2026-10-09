r"""Rod pivot pin (MHA-CH-010) and the rod-fork-to-rocker joint it closes.

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the
pattern). The part build (``build_ch_rod_pivot_pin.py``), its drawing, the
channel assembly and ``test_ch_rod_pivot_fit`` import it; it reads only the
two parts it joins, so the pin never re-keys on bank layout or config.

The joint: each connecting rod's fork (``ch_connecting_rod_spec``) straddles
its rocker arm (``ch_rocker_arm_spec``) in the arm's own plane, and one plain
5/64 drill-rod pin runs through both tines and the arm's #47 rod hole. The
pin RUNS in the arm (the one moving member) and is RETAINED in the fork: both
ends are peened into 90-degree countersinks on the tines' outer faces and
dressed near flush, so nothing proud of the fork reaches the neighbouring
channel. Peening is a reconstruction choice (issue #746): the photographs show
two rod cheeks round each rocker, not the original fastener.

Frame (part): pin axis = part Z, axial mid-plane = Front Plane (z = 0); the
model is the INSTALLED pin -- a Ø PIN_DIA journal FORK_THICKNESS long whose
ends are the countersink cones they were peened into, flush with the tines.
The shop cuts the blank PIN_BLANK_LENGTH long; the drawing states that.
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
# Cut length of the blank: the fork plus upset stock at each end that, peened,
# fills the countersink (PEEN_FILL below). 3-place, printed on the pin sheet.
PIN_BLANK_LENGTH = 7.5
PIN_BLANK_LENGTH_BAND = (0.127, -0.127)  # (upper, lower) deviations
# Dressed ends may stand this far proud of each tine face (the neighbour stack
# carries it).
PIN_END_PROUD_MAX = 0.10
PIN_CSK_DIA = _rod.PIN_HOLE_CSK_DIA  # the installed ends fill the countersinks
PIN_CSK_ANGLE_DEG = 90.0

# --- The joint's limits (the clearance budget test_ch_rod_pivot_fit holds). ---
RULE12_WALL_FLOOR = 1.5  # drawing-simplicity policy rule 12
RUNNING_FLOOR = 0.10  # rocker_bank_layout.RUNNING_FLOOR: oiled steel faces
MARGIN_SPARE = 0.25  # rocker_bank_layout.MARGIN_SPARE: novice spare
NEIGHBOUR_CLEARANCE_MIN = RUNNING_FLOOR + MARGIN_SPARE  # 0.35
RETENTION_OVERLAP_MIN = 0.35  # radial: countersink rim over the drilled hole
CROTCH_CLEARANCE_MIN = 1.0  # slot floor below the arm's bottom edge, all poses
BRIDGE_TARGET = 2.0  # fork bridge below the slot floor: the rule-12 target
# Arm tilt less rod tilt, the swing the crotch must clear: the solved loop
# (channel_kinematics, cam phase 0..360) spans -8.602..+1.006 deg, restated
# here rounded outward (test_ch_rod_pivot_fit pins it to the solved loop).
RELATIVE_SWING_DEG = (-8.61, 1.01)
_SWING_STEPS = 400


def _band(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    return nominal + band[1], nominal + band[0]


def _frustum_fill(csk_dia: float, hole_dia: float, pin_dia: float) -> float:
    """Volume a peened end must fill: one 90-degree countersink cone from the
    hole edge to the rim, less the pin already inside it."""
    depth = (csk_dia - hole_dia) / 2.0
    cone = math.pi * depth / 12.0 * (csk_dia**2 + csk_dia * hole_dia + hole_dia**2)
    return cone - math.pi * pin_dia**2 / 4.0 * depth


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
    the arm strap 2.500 +/-0.025, the fork 6.075 +/-0.05, the slot
    2.625 +0.127/0, the tines equal within FORK_TINE_MATCH, drilled holes
    +0.10/0, the hubs that set the pitch never shorter than nominal; the
    fork outline, slot depth and arm radii at the title block's .XX class,
    the arm's top edge 8.0 +0.5/0 over its pivot.
    """
    t_min, t_max = _band(_arm.ARM_THICKNESS, _arm.ARM_THICKNESS_BAND)
    w_min, w_max = _band(_rod.FORK_THICKNESS, _rod.FORK_THICKNESS_BAND)
    s_min, s_max = _band(_rod.FORK_SLOT_WIDTH, _rod.FORK_SLOT_BAND)
    csk_min, csk_max = _band(_rod.PIN_HOLE_CSK_DIA, _rod.PIN_HOLE_CSK_BAND)
    blank_min, blank_max = _band(PIN_BLANK_LENGTH, PIN_BLANK_LENGTH_BAND)
    hole_min = NUMBER_DRILL_MM[_rod.PIN_HOLE_SPEC.size]
    hole_max = hole_min + DRILLED_PLUS
    arm_hole_min = NUMBER_DRILL_MM[_arm.ROD_HOLE_SPEC.size]
    arm_hole_max = arm_hole_min + DRILLED_PLUS
    pin_min, pin_max = PIN_DIA - PIN_DIA_TOLERANCE, PIN_DIA + PIN_DIA_TOLERANCE
    off_centre = _rod.FORK_TINE_MATCH / 2.0
    pitch_min = _arm.HUB_LENGTH  # hubs bear face on face; +0.05/0 band
    # Each rod floats on its own arm by the slot's side clearance; rod j's
    # fork leans north and rod j+1's south, each face at half the fork plus
    # its float and off-centre, each dressed pin end proud of it.
    side_clearance_max = s_max - t_min
    neighbour = (
        pitch_min
        - w_max
        - side_clearance_max
        - 2.0 * off_centre
        - 2.0 * PIN_END_PROUD_MAX
    )
    tine_min = (w_min - s_max) / 2.0 - off_centre
    csk_depth_max = (csk_max - hole_min) / 2.0
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
    # Each pin hole wanders by half its position zone, and the pin drops by
    # half its running clearance in the arm and in the tines.
    hole_wander = (
        float(_rod.GEOMETRIC_TOLERANCES_MM["rocker pin hole position"])
        + float(_arm.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
    ) / 2.0
    pin_drop = (arm_hole_max - pin_min) / 2.0 + (hole_max - pin_min) / 2.0
    projection_min = (blank_min - w_max) / 2.0
    fill = _frustum_fill(csk_max, hole_min, pin_min)
    # The crown radius rides the fork width at the title block's .XX class,
    # and the countersunk hole wanders by half its position zone.
    crown_loss = _arm.LINEAR_2PL / 2.0 + (
        float(_rod.GEOMETRIC_TOLERANCES_MM["rocker pin hole position"]) / 2.0
    )
    return {
        "side_clearance_min": s_min - t_max,
        "side_clearance_max": side_clearance_max,
        "neighbour_clearance_min": neighbour,
        "tine_min": tine_min,
        "tine_bearing_land_min": tine_min - csk_depth_max,
        "running_clearance_min": arm_hole_min - pin_max,
        "running_clearance_max": arm_hole_max - pin_min,
        "tine_hole_clearance_max": hole_max - pin_min,
        "retention_overlap_min": (csk_min - hole_max) / 2.0,
        "crotch_clearance_min": edge_low - floor_high - hole_wander - pin_drop,
        # ForkBossLength less SlotDepth, both .XX from the crown top.
        "bridge_min": (
            _rod.FORK_BASE_BELOW_PIN - _rod.FORK_CROTCH_BELOW_PIN - 2.0 * two_place
        ),
        "upset_projection_min": projection_min,
        "upset_projection_max": (blank_max - w_min) / 2.0,
        "upset_needed_max": fill / (math.pi * pin_min**2 / 4.0),
        "crown_wall_min": _rod.FORK_CROWN_RADIUS - crown_loss - csk_max / 2.0,
    }


BUDGET = joint_budget()
if BUDGET["side_clearance_min"] < RUNNING_FLOOR - 1e-9:
    raise AssertionError("fork slot can close on the thickest arm")
if BUDGET["neighbour_clearance_min"] < NEIGHBOUR_CLEARANCE_MIN - 1e-9:
    raise AssertionError("neighbouring forks can touch in the inter-arm gap")
if BUDGET["tine_min"] < RULE12_WALL_FLOOR - 1e-9:
    raise AssertionError("fork tine under the rule-12 floor")
if BUDGET["running_clearance_min"] <= 0.0:
    raise AssertionError("pin can seize in the arm's rod hole")
if BUDGET["retention_overlap_min"] < RETENTION_OVERLAP_MIN - 1e-9:
    raise AssertionError("countersink rim too narrow to retain a peened end")
if BUDGET["crotch_clearance_min"] < CROTCH_CLEARANCE_MIN - 1e-9:
    raise AssertionError("fork crotch can strike the arm's bottom edge")
if BUDGET["bridge_min"] < BRIDGE_TARGET - 1e-9:
    raise AssertionError("fork bridge below the slot under the 2.0 target")
if BUDGET["upset_projection_min"] < BUDGET["upset_needed_max"] - 1e-9:
    raise AssertionError("pin blank too short to fill both countersinks")
if BUDGET["crown_wall_min"] < 2.0 - 1e-9:
    raise AssertionError("countersink rim to fork crown under the 2.0 target")
