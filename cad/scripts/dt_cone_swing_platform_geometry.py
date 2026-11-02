r"""Plan geometry of the MHA-DT-20 cone swing platform.

PURE, SolidWorks-free: the plate outline, lock-notch seat and chord and the
base-fixed swing hardware stations. The harmonic base reads these placements
without the post/shaft/tip-block specifications. It does require the post's
body envelope: BLOCK_DIA sets PLATE_SOUTH_Z and PLATE_LEN; that length sets
the notch exit and tapered edge used by ``swing_hardware_geometry`` to
calculate the base's swing-stop hole. Removing that dependency would duplicate
the mating platform geometry in the base. Spec-dependent mounting, web and
manufactured-stop checks live in ``dt_cone_swing_platform_checks``; the fixed
crank reference lives in ``dt_cone_swing_platform_crank_axis``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from _cone_axis_constants import PLATFORM_THICKNESS_MM
from dt_cone_post_envelope import BLOCK_DIA
from cone_line import (
    COS_I as _COS_I,
    INCLINE_DEG,
    PIVOT_STATION,
    POST_STATION,
    SIN_I as _SIN_I,
)

PLATE_T = PLATFORM_THICKNESS_MM  # 1/4" plate
# The outline prints .XX inch (#290, Main ruling: option (a)), so every
# printed outline station sits on the .01 in grid.
_GRID_XX = 0.254
HALF_WIDTH_N = 16.002  # .63 north (pivot/tip) half-width, EAST side (the
# lock-slot region keeps its full seat)
WEST_HALF_N = 7.874  # .31 north half-width, WEST side.  The recentered north
# arbor pedestal otherwise clips the flared edge; the half-width keeps plan
# clearance while retaining the close photo relationship in ch12 img09.
EAST_HALF_S = 23.876  # .94, widened for the v2 post's casting foot
WEST_HALF_S = 37.084  # 1.46 west half-width at the south end: the flare that
# makes the pivot -> lock-knob line solid plate (covers the notch seat + knob
# head)
NORTH_OVERHANG = 7.112  # .28 pivot -> north edge (plate continues past the pivot)


# The engaged plate follows the configured cone journal line.

# --- cone-pivot-post-v2 attachment footprint -------------------------------
# The casting and swing-pivot stations come from the live cone line.
POST_MAIN_DIA = BLOCK_DIA
POST_LOCAL_Z = POST_STATION - PIVOT_STATION
POST_SOUTH_MARGIN = 3.175  # 1/8 in least clearance beyond the post's south rim
# The length rounds UP to the grid so the margin stays at least 1/8 in.
PLATE_LEN = round(
    math.ceil(
        round((NORTH_OVERHANG - POST_LOCAL_Z + POST_MAIN_DIA / 2.0 + POST_SOUTH_MARGIN)
              / _GRID_XX, 9)
    )
    * _GRID_XX,
    4,
)
PLATE_SOUTH_Z = NORTH_OVERHANG - PLATE_LEN
# Rounded native plan corners (.XX radii). Shared with the manufactured
# stop-fence enclosure; the southwest radius clears the relocated lock notch.
PLATE_CORNERS = (
    ("NE", -HALF_WIDTH_N, NORTH_OVERHANG, 9.906),  # .39
    ("NW", WEST_HALF_N, NORTH_OVERHANG, 7.874),  # .31
    ("SW", WEST_HALF_S, NORTH_OVERHANG - PLATE_LEN, 5.08),  # .20
    ("SE", -EAST_HALF_S, NORTH_OVERHANG - PLATE_LEN, 11.938),  # .47
)

# The open-ended lock notch cuts from the engaged stud seat straight out
# through the plate's WEST edge. The cone-lock-knob stud is fixed to the base;
# on disengage the plate swings until its edge passes the stud and head.
# Tightened with no plate under it, the head fences the mouth and locks the
# plate disengaged; tightened on the plate it clamps the engaged pose, which
# is SET AT ASSEMBLY: swing in until the tightest cone meets a feeler/backlash,
# then tighten. The knob clamps by friction anywhere along the notch.
# The notch runs along the swing arc's CHORD: at R~192 over ~3 deg to the
# mouth the sagitta is ~0.07, absorbed by the O6.35 stud's clearance in SLOT_W.
#
# LOCAL-FRAME CONVENTION: the assembly places this part at Ry(+INCLINE)
# (train._plate_local_to_machine), under which local +x maps to machine WEST
# at the engaged pose -- every west-side feature below (the flare, the lock
# notch) is authored at local +x, east-side features at local -x.
SLOT_W = 7.874  # .31: Ø6.35 stud clearance plus chord-vs-arc slack
# The notch seat was placed for the former stock O25.4-head knob (91882A425):
# the northern solution beside the post cleared the post but overlapped the
# T120/64T gear row, so the stud moved west to x 1.30 in on the southern solution
# where that head kept a 2 mm post gap.  The O15.875 93585A190 head keeps the
# same seat (plate and base unchanged) with a wider post gap; the drive train
# re-checks the head against the post, gears and stop at import.
SLOT_E_X = 33.02  # 1.30
LOCK_HEAD_POST_CLEARANCE = 2.0
# Floored to the grid: the seat moves south, away from the post.
SLOT_E_Z = round(
    math.floor(
        round(
            (
                POST_LOCAL_Z
                - math.sqrt(
                    (POST_MAIN_DIA / 2.0 + 25.4 / 2.0 + LOCK_HEAD_POST_CLEARANCE) ** 2
                    - SLOT_E_X**2
                )
            )
            / _GRID_XX,
            9,
        )
    )
    * _GRID_XX,
    4,
)
SLOT_R = math.hypot(SLOT_E_X, SLOT_E_Z)
# The plate swings toward disengage (big end away from the drum), so in PLATE
# coords the fixed stud sweeps the INVERSE rotation: unit direction (-z, x)/R
# at E -- outward toward the west edge (+x), slightly north (+z).
SLOT_TX, SLOT_TZ = -SLOT_E_Z / SLOT_R, SLOT_E_X / SLOT_R


def _west_edge_x(z_local: float) -> float:
    """Authored x of the west taper edge at local z (linear WEST_HALF_N -> WEST_HALF_S)."""
    return (
        WEST_HALF_N
        + (WEST_HALF_S - WEST_HALF_N) * (NORTH_OVERHANG - z_local) / PLATE_LEN
    )


def _chord_exit_travel(x0: float, z0: float) -> float:
    """Stud travel from (x0, z0) along the chord to the west taper edge."""
    # solve x0 + t*TX = _west_edge_x(z0 + t*TZ) for t (both sides linear)
    k = (WEST_HALF_S - WEST_HALF_N) / PLATE_LEN
    return (WEST_HALF_N + k * (NORTH_OVERHANG - z0) - x0) / (SLOT_TX + k * SLOT_TZ)


# Stud travel from the engaged seat to the mouth. Past this the stud is out of
# the plate; the shared hardware calculation adds the knob head radius to
# derive the disengaged pose.
NOTCH_EXIT_TRAVEL = _chord_exit_travel(SLOT_E_X, SLOT_E_Z)
_MOUTH_OVERSHOOT = 4.0  # cut ends past the edge so the mouth opens clean
SLOT_OUT_X = SLOT_E_X + (NOTCH_EXIT_TRAVEL + _MOUTH_OVERSHOOT) * SLOT_TX
SLOT_OUT_Z = SLOT_E_Z + (NOTCH_EXIT_TRAVEL + _MOUTH_OVERSHOOT) * SLOT_TZ
# Plan angle of the notch run off the plate's east-west line (the run is the
# chord the stud follows, so it climbs north as it opens through the west
# edge).  Printed as a DRIVEN reference on the notch sketch; the chord itself
# is what the sketch geometry pins.
NOTCH_RUN_DEG = math.degrees(math.atan2(SLOT_TZ, SLOT_TX))

STOP_LOCAL_Z = -105.0


@dataclass(frozen=True, slots=True)
class SwingHardwareGeometry:
    """Shared machine-frame stations for the base-fixed lock and travel stop."""

    lock_xz: tuple[float, float]
    disengage_deg: float
    stop_contact_xz: tuple[float, float]
    stop_xz: tuple[float, float]
    stop_engaged_gap: float


# Designed clear air between the lock-knob head and the notch mouth at the
# disengaged stop, so the knob can be tightened onto bare base to fence the
# mouth.  Sized when the plate outline printed .X (+/-0.8 mm) and the base
# stop/stud holes .XX (+/-0.51/axis): the linear worst case then spent 4.41
# and kept >= 2.0 mm (U27).  The outline now prints .XX inch (+/-.01), so the
# same margin holds with more to spare.  The base derives its swing-stop hole
# from this function.
DISENGAGE_HEAD_MARGIN = 6.5


def swing_hardware_geometry(
    pivot_xz: tuple[float, float],
    *,
    lock_head_dia: float,
    stop_contact_dia: float,
) -> SwingHardwareGeometry:
    """Derive the lock seat and stop contact once from the platform outline.

    ``stop_contact_dia`` is the stop diameter the plate edge bears on (the
    seated screw's head)."""
    if lock_head_dia <= 0.0 or stop_contact_dia <= 0.0:
        raise ValueError("swing hardware diameters must be positive")

    def placed(x_local: float, z_local: float, angle_rad: float) -> tuple[float, float]:
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return (
            pivot_xz[0] + x_local * c + z_local * s,
            pivot_xz[1] - x_local * s + z_local * c,
        )

    incline_rad = math.radians(INCLINE_DEG)
    lock_xz = placed(SLOT_E_X, SLOT_E_Z, incline_rad)
    disengage_deg = math.degrees(
        (NOTCH_EXIT_TRAVEL + lock_head_dia / 2.0 + DISENGAGE_HEAD_MARGIN) / SLOT_R
    )
    disengaged_rad = incline_rad + math.radians(disengage_deg)

    east_slope = (EAST_HALF_S - HALF_WIDTH_N) / PLATE_LEN
    stop_local_x = -(HALF_WIDTH_N + east_slope * (NORTH_OVERHANG - STOP_LOCAL_Z))
    edge_out_local = (-1.0, east_slope)
    edge_norm = math.hypot(*edge_out_local)
    edge_out_local = (
        edge_out_local[0] / edge_norm,
        edge_out_local[1] / edge_norm,
    )

    contact_xz = placed(stop_local_x, STOP_LOCAL_Z, disengaged_rad)
    c_dis, s_dis = math.cos(disengaged_rad), math.sin(disengaged_rad)
    edge_out_disengaged = (
        edge_out_local[0] * c_dis + edge_out_local[1] * s_dis,
        -edge_out_local[0] * s_dis + edge_out_local[1] * c_dis,
    )
    stop_xz = (
        contact_xz[0] + edge_out_disengaged[0] * stop_contact_dia / 2.0,
        contact_xz[1] + edge_out_disengaged[1] * stop_contact_dia / 2.0,
    )

    engaged_edge_xz = placed(stop_local_x, STOP_LOCAL_Z, incline_rad)
    edge_out_engaged = (
        edge_out_local[0] * _COS_I + edge_out_local[1] * _SIN_I,
        -edge_out_local[0] * _SIN_I + edge_out_local[1] * _COS_I,
    )
    stop_delta = (
        stop_xz[0] - engaged_edge_xz[0],
        stop_xz[1] - engaged_edge_xz[1],
    )
    engaged_gap = (
        stop_delta[0] * edge_out_engaged[0]
        + stop_delta[1] * edge_out_engaged[1]
        - stop_contact_dia / 2.0
    )
    return SwingHardwareGeometry(
        lock_xz=lock_xz,
        disengage_deg=disengage_deg,
        stop_contact_xz=contact_xz,
        stop_xz=stop_xz,
        stop_engaged_gap=engaged_gap,
    )


