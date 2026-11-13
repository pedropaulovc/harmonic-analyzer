"""R4 workholding: common end clamps, loose stops and screw-centred washer.

Pure geometry. Product geometry stays main's .4000 strap hole. Partial head
bearing at 1 Nm is owner-accepted; there is no new bearing-strength or
complete-annulus rejection gate. The carrier's #2151 hole table supplies the
correlated pin errors: ``PIN_RELATIVE_ERROR`` against the in-situ HUB, and
the table-row/sweep displacement for the end heads and stop pins. The HUB
washer is the bought brass #8 SAE flat washer TL-VN-85 (owner ruling
2026-11-13, #2448): it must clear every complete cutter sweep (gap > 0), the
real limit, not the retired top hat's 1.5 mm margin.
"""
from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_vn_oblique_hub_washer_spec as washer
import ch_rocker_arm_tl_oblique_blank_spec as blank
import ch_rocker_strap_spec as strap
from _mcmaster_91251a197 import DIMS as COMMON_SCREW
from _printed_tolerance import printed_band_mm
from ch_rocker_hub_fit import STRAP_HOLE_BAND

# The strap's printed hub hole (main's MHA-CH-13), reamed in place at HUB.
PRODUCT_HOLE_LIMITS = (
    strap.HOLE_DIA + STRAP_HOLE_BAND[1],
    strap.HOLE_DIA + STRAP_HOLE_BAND[0],
)
HUB_TORQUE_NM = 1.0

# ASME B18.3-2012 Tables 1/2, supplier envelopes, NOT custom jig bands.
# https://www.finesz.com/pic/ASME%20B18.3.pdf
SCREW_LENGTH_LIMITS = (COMMON_SCREW.length - 0.03 * trammel.INCH, COMMON_SCREW.length)
SCREW_HEAD_DIA_LIMITS = (0.257 * trammel.INCH, 0.270 * trammel.INCH)
SCREW_HEAD_RADIAL_RUNOUT_MAX = 0.006 * trammel.INCH / 2.0
SCREW_FILLET_DIA_MAX = 0.188 * trammel.INCH
SCREW_FILLET_LENGTH_MAX = 0.020 * trammel.INCH
SCREW_TIP_INCOMPLETE_MAX = COMMON_SCREW.pitch  # conservative full pitch, not recipe's .75P
# ASME B1.1 #8-32 UNC-3A least major (base bar spec's bracket-screw float).
SCREW_MAJOR_MIN = 0.1585 * trammel.INCH

END_GRIP_LIMITS = (
    riser.THICKNESS - riser.THICKNESS_BAND + trammel.STRAP_THICK + min(rocker.ARM_THICKNESS_BAND),
    riser.THICKNESS + riser.THICKNESS_BAND + trammel.STRAP_THICK + max(rocker.ARM_THICKNESS_BAND),
)
END_INSERTION_LIMITS = (
    SCREW_LENGTH_LIMITS[0] - END_GRIP_LIMITS[1],
    SCREW_LENGTH_LIMITS[1] - END_GRIP_LIMITS[0],
)
END_FULL_THREAD_MIN = END_INSERTION_LIMITS[0] - SCREW_TIP_INCOMPLETE_MAX - carrier.TAP_MOUTH_BREAK
END_UNDERSIDE_CLEARANCE_MIN = carrier.THICKNESS - carrier.THICKNESS_BAND - END_INSERTION_LIMITS[1]
HUB_GRIP_LIMITS = (
    END_GRIP_LIMITS[0] + washer.THICKNESS_MIN,
    END_GRIP_LIMITS[1] + washer.THICKNESS_MAX,
)
HUB_FULL_THREAD_MIN = (
    SCREW_LENGTH_LIMITS[0] - HUB_GRIP_LIMITS[1]
    - SCREW_TIP_INCOMPLETE_MAX - carrier.TAP_MOUTH_BREAK
)
HUB_UNDERSIDE_CLEARANCE_MIN = (
    carrier.THICKNESS - carrier.THICKNESS_BAND
    - (SCREW_LENGTH_LIMITS[1] - HUB_GRIP_LIMITS[0])
)
# The screw, not a spigot, centres the washer: its largest bore floats on the
# screw's least major, and its O.D. may run out of its bore by the supplier
# bound (ASME B18.21.1 section 4.5, taken as a full radial offset). The screw
# stands in the carrier's in-situ HUB tap, whose 60° flanks centre it under
# the clamp load (no thread play is charged, as for the base bar's bracket
# screws); HUB_RADIAL_STACK charges the HUB setting itself.
WASHER_FLOAT_MAX = (washer.ID_MAX - SCREW_MAJOR_MIN) / 2.0
WASHER_OFFSET_MAX = WASHER_FLOAT_MAX + washer.OD_ID_RUNOUT_MAX
# The washer passes the screw, and its least O.D. spans the largest hole.
WASHER_SCREW_CLEARANCE_MIN = (washer.ID_MIN - COMMON_SCREW.major_dia) / 2.0
STRAP_BEARING_LAND_CONCENTRIC = (washer.OD_MIN - PRODUCT_HOLE_LIMITS[1]) / 2.0
# At the worst offset the washer's rim overhangs the hole on one side: the
# partial bearing the owner accepted (#2448), disclosed here, not gated.
STRAP_BEARING_LAND_MIN = (
    STRAP_BEARING_LAND_CONCENTRIC - WASHER_OFFSET_MAX - carrier.HUB_RADIAL_STACK
)
# The SHCS under-head fillet (ASME B18.3, .188 MAX) can exceed the washer's
# least bore (.183): at those limits the head first bears on the bore's edge,
# which the soft brass coins under the 1 N·m clamp. Disclosed, not gated.
FILLET_BORE_OVERLAP_MAX = (SCREW_FILLET_DIA_MAX - washer.ID_MIN) / 2.0


def cutter_gap(
    point: tuple[float, float], radius: float, pass_name: str,
    *, cutter_diameter: float = trammel.PART_CUTTER_DIA,
) -> float:
    """Exact minimum from a circle to the complete finite cutter sweep."""
    dx, dy = point[0], point[1] + trammel.H1
    theta = max(-trammel.SWEEP[pass_name], min(trammel.SWEEP[pass_name], math.atan2(dx, dy)))
    rc = trammel.PASS_RADIUS[pass_name]
    cutter = (rc * math.sin(theta), rc * math.cos(theta) - trammel.H1)
    return math.dist(point, cutter) - radius - cutter_diameter / 2.0


def washer_cutter_gaps(correlated_pin_error: float = 0.0) -> dict[str, float]:
    """Screw-centred full-sweep gaps with play and one correlated pin error.

    The largest O.D., offset by the bore's float on the screw and the
    supplier's O.D.-to-bore runout, then the HUB setting stack (shoulder
    clearance included) and carriage play, each charged once as in
    carrier.pin_relative_stack.
    """
    if correlated_pin_error < 0.0:
        raise ValueError("correlated pin error must be nonnegative")
    return {
        name: cutter_gap(trammel.HUB, washer.OD_MAX / 2.0, name)
        - WASHER_OFFSET_MAX - carrier.HUB_RADIAL_STACK
        - trammel.CARRIAGE_PLAY_RADIUS - correlated_pin_error
        for name in trammel.SWEEP
    }


WASHER_GAPS = {name: cutter_gap(trammel.HUB, washer.OD / 2.0, name) for name in trammel.SWEEP}
# Each pass charges its own correlated pin-shape error against the SAME
# in-situ HUB once, beside the washer offset, HUB setting stack and carriage play.
WASHER_GAPS_MIN = {
    name: washer_cutter_gaps(carrier.PIN_RELATIVE_ERROR[name])[name]
    for name in trammel.SWEEP
}
# Even a zero-radius shank cannot put its centre beyond the clearance-hole
# radius. This intentionally conservative head-offset bound needs no guessed
# thread/root minimum or thread-centred washer assumption.
END_HEAD_AXIS_FLOAT_MAX = blank.CLAMP_HOLE_LIMITS[1] / 2.0
# CL/CR are table rows from A1 (.XXX plus rounding). The blank registers on
# stops set about the carrier centre, D1/2 from A1, so X also carries half
# of B1's table error.
_D1_HALF_ERROR = max(abs(v) for v in carrier.pin_coordinate_intervals()[0]) / 2.0
END_STATION_ERROR = max(
    math.hypot(ex + _D1_HALF_ERROR, ey)
    for ex, ey in map(carrier.table_coordinate_errors, carrier.END_CLAMPS.values())
)
END_FILLET_CLEARANCE_MIN = (
    (blank.CLAMP_HOLE_LIMITS[0] - SCREW_FILLET_DIA_MAX) / 2.0
    - math.sqrt(2.0) * blank.CLAMP_TRANSFER_BAND
)
END_HEAD_GAPS = {
    name: min(cutter_gap(point, SCREW_HEAD_DIA_LIMITS[1] / 2.0, name)
              for point in carrier.END_CLAMPS.values())
    for name in trammel.SWEEP
}
# CL/CR lie beyond the finite cutter arc: charge each head's complete
# correlated table-row and cut displacement, including accepted carriage play.
END_HEAD_GAPS_MIN = {
    name: min(
        cutter_gap(point, SCREW_HEAD_DIA_LIMITS[1] / 2.0, name)
        - carrier.station_sweep_error(point, name)
        for point in carrier.END_CLAMPS.values()
    ) - END_HEAD_AXIS_FLOAT_MAX - SCREW_HEAD_RADIAL_RUNOUT_MAX
    - trammel.RADIUS_FROM_SHOULDER_CLEARANCE
    for name in trammel.SWEEP
}


def end_head_material_margins(
    raw_y_min: float, registration_error: float, longitudinal_error: float,
) -> dict[str, float]:
    """Both complete heads stay in real end waste, including the sawn edge."""
    if min(registration_error, longitudinal_error) < 0.0:
        raise ValueError("blank placement errors must be nonnegative")
    a, b = blank.OUTER_ANCHORS[-2:]
    vx, vy = b[0] - a[0], b[1] - a[1]
    x, y = carrier.CR
    saw_distance = abs(vx * (y - a[1]) - vy * (x - a[0])) / math.hypot(vx, vy)
    tip_distance = x * math.cos(trammel.TIP_ANGLE) - (y + trammel.H1) * math.sin(trammel.TIP_ANGLE)
    margins = {
        "square end": trammel.BLANK_LENGTH / 2.0 - x - longitudinal_error,
        "registered raw edge": y - raw_y_min - registration_error,
        "outer saw edge": saw_distance - blank.SAW_EDGE_TOLERANCE
                          - math.hypot(registration_error, longitudinal_error),
        "finished tip ray": tip_distance,
    }
    return {
        name: margin - SCREW_HEAD_DIA_LIMITS[1] / 2.0 - END_STATION_ERROR - END_HEAD_AXIS_FLOAT_MAX
        for name, margin in margins.items()
    }


# Stock pins extend above the strap. Charge cant at their FULL height for
# cutter/holder envelopes, not merely at the strap's contact line.
# A carrier-seated tilted bounding cylinder spans L*cos(theta)+D*sin(theta)
# vertically: D includes BOTH the raised bottom-axis datum and upper rim.
# L + D*tan(theta_max) bounds every allowed angle without assuming which
# chamfer/crown edge contacts the carrier. The real pin fits this cylinder.
STOP_PIN_HEIGHT_MAX = (
    riser.STOP_PIN_TOP_LIMITS[1]
    + riser.STOP_PIN_DIA_LIMITS[1] * riser.STOP_PIN_SLOPE_MAX
)
STOP_PIN_TOP_FLOAT_MAX = riser.STOP_PIN_FLOAT_MAX * (
    1.0 + 2.0 * (STOP_PIN_HEIGHT_MAX - riser.THICKNESS + riser.THICKNESS_BAND)
    / riser.STOP_PIN_SUPPORT_MIN
)
# The stop axes are set from the carrier at the riser's one ordinary .XX
# station band; correlated pin errors and carriage play move both self-cut sweeps.
STOP_STATION_BAND = printed_band_mm(riser.STATION_PLACES, unit=riser.UNIT)
STOP_PIN_GAPS_MIN = {
    name: min(
        cutter_gap(point, riser.STOP_PIN_DIA_LIMITS[1] / 2.0, name,
                   cutter_diameter=trammel.RISER_CUTTER_DIA)
        - carrier.station_sweep_error(point, name, (STOP_STATION_BAND,) * 2)
        for point in riser.STOP_PIN_CARRIER_POINTS
    ) - STOP_PIN_TOP_FLOAT_MAX - trammel.RADIUS_FROM_SHOULDER_CLEARANCE
    for name in trammel.SWEEP
}
END_HEAD_MATERIAL_MARGINS = end_head_material_margins(riser.STRAP_RAW_Y_MIN, 0.5, 0.6)
PART_TOP_Z = trammel.CARRIER_TOP_Z + riser.THICKNESS + trammel.STRAP_THICK
CLAMP_TOP_Z = {
    "CL": PART_TOP_Z + COMMON_SCREW.head_h,
    "CR": PART_TOP_Z + COMMON_SCREW.head_h,
    "hub": PART_TOP_Z + washer.THICKNESS + COMMON_SCREW.head_h,
}
TOOLING_TOP_Z_MAX = trammel.CARRIER_TOP_Z + max(
    HUB_GRIP_LIMITS[1] + COMMON_SCREW.head_h,
    STOP_PIN_HEIGHT_MAX,
)

# Compatible standard chucking tool, NOT a measured tool or a long hand reamer.
# Primary sources: Toolmex 5-018-400 specifies a 45-degree chamfer;
# https://www.toolmex.com/itemdetail/5-018-400
# GARR 4100, row 96314, .4000 +.0003/0, specifies STANDARD 45 DEGREE LEAD:
# https://www.garrtool.com/doc/pdf/4100.pdf
# A flat-front 45-degree tip cannot have an axial lead longer than its radius.
# Bound by the existing PRODUCT hole upper limit, larger than that tool limit.
REAMER_LEAD_MAX = PRODUCT_HOLE_LIMITS[1] / 2.0
TOOL_BREAKTHROUGH_SPACE_MIN = riser.THICKNESS - riser.THICKNESS_BAND
TOOL_OVERTRAVEL_BUDGET = 0.010 * trammel.INCH
REAMER_DEPTH_RESERVE = TOOL_BREAKTHROUGH_SPACE_MIN - REAMER_LEAD_MAX - TOOL_OVERTRAVEL_BUDGET
DRILL_POINT_ANGLE_DEG = 118.0
DRILL_POINT_LEAD = PRODUCT_HOLE_LIMITS[1] / 2.0 / math.tan(math.radians(DRILL_POINT_ANGLE_DEG / 2.0))
DRILL_DEPTH_RESERVE = TOOL_BREAKTHROUGH_SPACE_MIN - DRILL_POINT_LEAD - TOOL_OVERTRAVEL_BUDGET


def tool_depth_reserve(lead_length: float, breakthrough: float, depth_error: float) -> float:
    """Air above the carrier after the full-diameter land exits the strap."""
    if min(lead_length, breakthrough, depth_error) < 0.0:
        raise ValueError("tool lead, breakthrough and depth error must be nonnegative")
    return TOOL_BREAKTHROUGH_SPACE_MIN - lead_length - breakthrough - depth_error


def require_clearance() -> None:
    """Resolved R4 geometric acceptance; native/installed-tool gates remain."""
    if min(END_FULL_THREAD_MIN, HUB_FULL_THREAD_MIN) < 1.5 * COMMON_SCREW.major_dia:
        raise AssertionError("a common clamp screw has under 1.5D full thread")
    if min(END_UNDERSIDE_CLEARANCE_MIN, HUB_UNDERSIDE_CLEARANCE_MIN) <= 0.0:
        raise AssertionError("a clamp screw protrudes below the carrier")
    if END_FILLET_CLEARANCE_MIN <= 0.0:
        raise AssertionError("a transferred end-clamp hole catches the underhead fillet")
    if min(END_HEAD_GAPS_MIN.values()) <= 0.0:
        raise AssertionError("an end-clamp head reaches a complete cutter sweep")
    if min(STOP_PIN_GAPS_MIN.values()) <= 0.0:
        raise AssertionError("a plain stop pin reaches a self-cut sweep")
    if min(END_HEAD_MATERIAL_MARGINS.values()) <= 0.0:
        raise AssertionError("an end-clamp head leaves the retained end waste")
    if min(WASHER_GAPS_MIN.values()) <= 0.0:
        raise AssertionError("the HUB washer reaches a complete cutter sweep")
    if min(WASHER_SCREW_CLEARANCE_MIN, STRAP_BEARING_LAND_CONCENTRIC) <= 0.0:
        raise AssertionError("the HUB washer binds on its screw or drops into the hub hole")
    if min(DRILL_DEPTH_RESERVE, REAMER_DEPTH_RESERVE) <= 0.0:
        raise AssertionError("a compatible drill/reamer reaches the carrier")
