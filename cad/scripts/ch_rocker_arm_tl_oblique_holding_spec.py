"""R3 hold-down proof: continuous cutter sweeps and pose-invariant flange gaps.

These are nominal-source and explicit printed-band calculations, not a claim
that the installed spindle/holder has been measured. The assembly's native
whole-model interference gate and its installed-tool acceptance remain required.
"""
from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_hub_stud_spec as stud
import ch_rocker_arm_tl_oblique_hub_sleeve_spec as sleeve
import ch_rocker_arm_tl_oblique_hub_washer_spec as washer
import ch_rocker_arm_tl_vn_oblique_left_clamp_screw_spec as left_screw
import ch_rocker_arm_tl_vn_oblique_hub_screw_spec as hub_screw
import ch_rocker_arm_tl_vn_oblique_clamp_screw_spec as cr_screw
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as feed
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as spacer
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

# Removal is part of the setup, not a band-clipped approximation of the sleeve.
SELF_CUT_REMOVED = (
    "ch-rocker-arm-tl-oblique-hub-stud",
    "ch-rocker-arm-tl-oblique-hub-sleeve",
    "ch-rocker-arm-tl-oblique-hub-washer",
    "ch-rocker-arm-tl-vn-oblique-hub-screw",
    "ch-rocker-arm-tl-vn-oblique-left-clamp-screw",
    "ch-rocker-arm-tl-vn-oblique-clamp-screw",
)


def cutter_gap(
    point: tuple[float, float], radius: float, pass_name: str,
    *, cutter_diameter: float = trammel.PART_CUTTER_DIA,
) -> float:
    """Exact minimum from a circular item to the complete finite cutter sweep."""
    dx, dy = point[0], point[1] + trammel.H1
    theta = max(-trammel.SWEEP[pass_name], min(trammel.SWEEP[pass_name], math.atan2(dx, dy)))
    rc = trammel.PASS_RADIUS[pass_name]
    cutter = (rc * math.sin(theta), rc * math.cos(theta) - trammel.H1)
    return math.dist(point, cutter) - radius - cutter_diameter / 2.0


WASHER_GAPS = {name: cutter_gap(trammel.HUB, washer.OD / 2.0, name) for name in trammel.SWEEP}
LEFT_HEAD_GAPS = {name: cutter_gap(trammel.LEFT_CLAMP, left_screw.DIMS.head_dia / 2.0, name) for name in trammel.SWEEP}
# Include the carrier's in-situ locating error, the stud's carrier slip and
# sleeve-on-shank float, plus the sleeve OD's actual printed .XXX size band.
SLEEVE_FLOAT = (sleeve.ID + max(sleeve.ID_BAND) - min(carrier.HUB_STUD_LIMITS)) / 2.0
STUD_FLOAT = carrier.HUB_SLIP_CLEARANCE_MAX / 2.0
SLEEVE_RADIUS_MAX = (sleeve.OD + printed_band_mm(sleeve.OD_PLACES, unit=carrier.UNIT)) / 2.0
SLEEVE_GAPS_MIN = {
    name: cutter_gap(trammel.HUB, SLEEVE_RADIUS_MAX, name)
    - SLEEVE_FLOAT - STUD_FLOAT - carrier.HUB_RADIAL_STACK
    for name in trammel.SWEEP
}
# Owner clarification relayed by Main, 2026-11-06: use the plain Ø11 washer;
# 2 mm was a coordinator concept, not the owner's requirement. The accepted
# lower bound is 1.5 mm at the worst case, without a centring fit-up.
WASHER_CLEARANCE_MIN = 1.5
# Manufacturer standard tables read 2026-11-06:
# https://www.brightonbest.com/download/pds/PDS_Thread_Details_Inch_Series.pdf
# #10-24 class 3A: major .1828 MIN, pitch .1604 MIN.
# https://www.americanfastener.com/nuts/ (Internal Threads — Class 2B):
# #10-24 pitch .1672 MAX. These are actual lower/upper limits, not basic major.
SCREW_MAJOR_MIN = 0.1828 * trammel.INCH
THREAD_RADIAL_PLAY = (0.1672 - 0.1604) * trammel.INCH / 2.0
# Double the pitch-diameter radial play conservatively includes cantilever
# extrapolation above the engaged thread: the head grip is under half the
# minimum full engagement, as checked in the screw's installed-stack contract.
SCREW_AXIS_FLOAT_MAX = 2.0 * THREAD_RADIAL_PLAY
WASHER_BORE_MAX = (
    round(washer.ID / trammel.INCH, washer.ID_PLACES) * trammel.INCH
    + drilled_oversize_mm(unit=washer.UNIT)
)
WASHER_FLOAT_MAX = (WASHER_BORE_MAX - SCREW_MAJOR_MIN) / 2.0
WASHER_GAPS_MIN = {
    name: gap - printed_band_mm(washer.OD_PLACES, unit=washer.UNIT) / 2.0
    - STUD_FLOAT - carrier.HUB_RADIAL_STACK - WASHER_FLOAT_MAX - SCREW_AXIS_FLOAT_MAX
    for name, gap in WASHER_GAPS.items()
}
LEFT_STATION_ERROR = math.hypot(
    printed_band_mm(3, unit=carrier.UNIT) + carrier.POSITION_BAND / 2.0,
    printed_band_mm(3, unit=carrier.UNIT),
)
LEFT_GRIP_MAX = trammel.RISER_THICK + trammel.RISER_THICK_BAND + trammel.STRAP_THICK + max(rocker.ARM_THICKNESS_BAND)
LEFT_AXIS_FLOAT_MAX = THREAD_RADIAL_PLAY * (1.0 + 2.0 * LEFT_GRIP_MAX / left_screw.ENGAGEMENT_MIN)
LEFT_HEAD_GAPS_MIN = {
    name: gap - LEFT_STATION_ERROR - LEFT_AXIS_FLOAT_MAX - trammel.RADIUS_FROM_SHOULDER_CLEARANCE
    for name, gap in LEFT_HEAD_GAPS.items()
}
LEFT_CLAMP_TO_CL = math.dist(trammel.LEFT_CLAMP, trammel.CL)
LEFT_HOLE_TO_END_MIN = (
    riser.BLANK_LENGTH / 2.0 + trammel.LEFT_CLAMP[0]
    - printed_band_mm(2, unit=carrier.UNIT) * 1.5
    - (riser.LEFT_CLAMP_DIA + riser.DRILLED_BAND[0]) / 2.0
)
LEFT_HOLE_TO_CL_MIN = (
    LEFT_CLAMP_TO_CL - (riser.LEFT_CLAMP_DIA + riser.CLAMP_DIA) / 2.0
    - riser.DRILLED_BAND[0] - 2.0 * printed_band_mm(3, unit=carrier.UNIT)
)
LEFT_BAND_WALL_MIN = min(
    trammel.HUB_RADIUS - trammel.RISER_INNER_RADIUS,
    trammel.RISER_OUTER_RADIUS - trammel.HUB_RADIUS,
) - (riser.LEFT_CLAMP_DIA + riser.DRILLED_BAND[0]) / 2.0 - riser.CLAMP_STATION_ERROR

# All carrier poses are rotations/translations in XY. These vertical gaps
# therefore hold for every pose, not just sampled stop positions. Use current
# source hardware, including the KP08 clearance envelope and full handwheel
# sweep, rather than the older concept's 69.4/73.9 height estimates.
FLANGE_BOTTOM_Z = trammel.CARRIER_UNDERSIDE_Z - stud.FLANGE_THICK
FLANGE_VERTICAL_GAPS = {
    "pivot blocks": FLANGE_BOTTOM_Z - trammel.PIVOT_BLOCK_TOP_Z,
    "KP08 envelope": FLANGE_BOTTOM_Z - feed.KP08_Z[1],
    "handwheel sweep": FLANGE_BOTTOM_Z - feed.HANDWHEEL_Z[1],
}
# The supports reach the carrier underside, so they need a plan proof instead.
# Both circles are carried by the same rigid pin-pair geometry in either pass.
FLANGE_SUPPORT_GAPS = {
    f"{name} {index}": math.dist(trammel.HUB, pin) - stud.FLANGE_DIA / 2.0 - spacer.OD / 2.0
    for name in trammel.PASS_RADIUS
    for index, pin in enumerate(trammel.pin_pair(name), 1)
}
# The handwheel's nominal vertical gap is small, but it is also far away in
# plan. HUB's exact machine path is x=-(Rc+rho)sin(theta/2),
# y=(rho-Rc)cos(theta/2). Bound that entire arc, not a sampled polyline.
_HUB_PATH_X = max(
    (rc + trammel.HUB_RADIUS) * math.sin(trammel.SWEEP[name] / 2.0)
    for name, rc in trammel.PASS_RADIUS.items()
)
_HUB_PATH_Y = [
    (trammel.HUB_RADIUS - rc) * scale
    for name, rc in trammel.PASS_RADIUS.items()
    for scale in (1.0, math.cos(trammel.SWEEP[name] / 2.0))
]
_HANDWHEEL_POINTS = feed.rect(*feed.HANDWHEEL_BOX)
_PLAN_SEPARATIONS = (
    max(0.0, min(p[0] for p in _HANDWHEEL_POINTS) - _HUB_PATH_X,
        -_HUB_PATH_X - max(p[0] for p in _HANDWHEEL_POINTS)),
    max(0.0, min(p[1] for p in _HANDWHEEL_POINTS) - max(_HUB_PATH_Y),
        min(_HUB_PATH_Y) - max(p[1] for p in _HANDWHEEL_POINTS)),
)
FLANGE_HANDWHEEL_PLAN_GAP = math.hypot(*_PLAN_SEPARATIONS) - stud.FLANGE_DIA / 2.0
PART_TOP_Z = trammel.CARRIER_TOP_Z + trammel.RISER_THICK + trammel.STRAP_THICK
CLAMP_TOP_Z = {
    "hub": PART_TOP_Z + washer.THICK + hub_screw.DIMS.head_h,
    "left": PART_TOP_Z + left_screw.DIMS.head_h,
    "CR": PART_TOP_Z + cr_screw.DIMS.head_h,
}


def tooling_clearance_report(setup: str) -> dict[str, dict[str, float]]:
    """Actual carried cutting-level hardware for the two different setups.

    Carrier/pivots/feed are below or outside this cutter-height envelope and
    retain the native interference and installed spindle/holder checks.
    """
    if setup not in ("riser_self_cut", "strap"):
        raise ValueError(f"unknown tooling setup {setup!r}")
    items = {
        "ch-rocker-arm-tl-oblique-hub-stud": ((trammel.HUB,), stud.DIA / 2.0),
        "ch-rocker-arm-tl-oblique-hub-sleeve": ((trammel.HUB,), sleeve.OD / 2.0),
        "ch-rocker-arm-tl-oblique-hub-washer": ((trammel.HUB,), washer.OD / 2.0),
        "ch-rocker-arm-tl-vn-oblique-hub-screw": ((trammel.HUB,), hub_screw.DIMS.head_dia / 2.0),
        "ch-rocker-arm-tl-vn-oblique-left-clamp-screw": ((trammel.LEFT_CLAMP,), left_screw.DIMS.head_dia / 2.0),
        "ch-rocker-arm-tl-vn-oblique-clamp-screw": ((trammel.CR,), cr_screw.DIMS.head_dia / 2.0),
        "ch-rocker-arm-tl-vn-oblique-cl-dowel": ((trammel.CL,), (carrier.CL_DOWEL_DIA + max(carrier.CL_DOWEL_BAND)) / 2.0),
        "ch-rocker-arm-tl-vn-oblique-riser-screw": (trammel.RISER_SCREWS, trammel.RISER_SCREW_HEAD_DIA / 2.0),
    }
    cutter = trammel.PART_CUTTER_DIA
    if setup == "riser_self_cut":
        cutter = trammel.RISER_CUTTER_DIA
        for stem in SELF_CUT_REMOVED:
            del items[stem]
    return {
        stem: {
            name: min(cutter_gap(point, radius, name, cutter_diameter=cutter) for point in points)
            for name in trammel.PASS_RADIUS
        }
        for stem, (points, radius) in items.items()
    }


def require_clearance() -> None:
    """Refuse the design if an authored geometric acceptance stops holding."""
    if 2.0 * hub_screw.GRIP_MAX > hub_screw.ENGAGEMENT_MIN:
        raise AssertionError("screw-axis float bound no longer covers the head overhang")
    if min(WASHER_GAPS_MIN.values()) < WASHER_CLEARANCE_MIN:
        raise AssertionError("hub washer violates the accepted 1.5 mm worst-case clearance")
    if min(LEFT_HEAD_GAPS_MIN.values()) < 5.0:
        raise AssertionError("left clamp head is under 5 mm from a sweep")
    if min(SLEEVE_GAPS_MIN.values()) <= 0.0:
        raise AssertionError("full round steel sleeve touches a cutter flank")
    if min(FLANGE_VERTICAL_GAPS.values()) <= 0.0 or min(FLANGE_SUPPORT_GAPS.values()) <= 0.0:
        raise AssertionError("hub flange collides with an obstacle at a carrier pose")
    if FLANGE_HANDWHEEL_PLAN_GAP <= 0.0:
        raise AssertionError("hub flange's swept plan reaches the handwheel")
    if min(LEFT_HOLE_TO_END_MIN, LEFT_HOLE_TO_CL_MIN, LEFT_BAND_WALL_MIN) < 2.032:
        raise AssertionError("left clamp lacks the .080 material edge target")
    if max(CLAMP_TOP_Z["hub"], CLAMP_TOP_Z["left"]) >= CLAMP_TOP_Z["CR"]:
        raise AssertionError("CR is no longer the tallest work clamp")
    for setup in ("riser_self_cut", "strap"):
        report = tooling_clearance_report(setup)
        if not report or min(gap for passes in report.values() for gap in passes.values()) <= 0.0:
            raise AssertionError(f"{setup}: installed cutting-level hardware reaches a cutter")
