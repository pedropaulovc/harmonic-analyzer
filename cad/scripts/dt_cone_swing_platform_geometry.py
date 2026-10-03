r"""Plan geometry of the MHA-DT-020 cone swing platform.

PURE, SolidWorks-free: the plate outline, the v2 post footprint, the lock-notch
seat and chord and the base-fixed swing hardware stations.
``build_cone_swing_platform`` authors the part from these numbers; the harmonic
base (pivot, lock and stop seats) and the drive train (placement and clearance
checks) read them here instead of importing the part builder, so a sketch or
drawing change in the builder does not re-key them. The fixed crank reference
axis the plate carries lives in ``cone_swing_platform_crank_axis``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
from dt_cone_swing_platform_spec import (
    HOLDDOWN_CBORE_DIA,
    HOLDDOWN_CLEARANCE_DIA,
    HOLDDOWN_LOCAL_X,
    HOLDDOWN_LOCAL_Z,
    HOLDDOWN_STATION_TOL_MM,
    PIVOT_BEARING_RELIEF_DEPTH,
    PIVOT_BEARING_RELIEF_DIAMETER,
    PIVOT_BEARING_THICKNESS,
    PIVOT_HOLE_DIA,
    PLATE_THICKNESS,
    POST_ATTACHMENT_SPACING,
    POST_BLOCK_DIA,
    POST_MOUNT_STATION_TOL_MM,
    POST_MOUNT_TAP_DIA,
    POST_MOUNT_THREAD_DIA,
)

PLATE_T = PLATE_THICKNESS  # 1/4" plate
HALF_WIDTH_N = 16.0  # north (pivot/tip) half-width, EAST side (the lock-slot
# region keeps its full seat)
WEST_HALF_N = 8.0  # north half-width, WEST side.  The recentered north arbor
# pedestal otherwise clips the flared edge; 8.0 leaves 0.37 mm exact plan
# clearance while retaining the close photo relationship in ch12 img09.
EAST_HALF_S = 24.0  # widened for the v2 post's Ø42.011 casting foot
WEST_HALF_S = 37.0  # west half-width at the south end: the flare that makes
# the pivot -> lock-knob line solid plate (covers the notch seat + knob head)
NORTH_OVERHANG = 7.0  # pivot -> north edge (plate continues past the pivot)

if abs(PLATE_T - PIVOT_BEARING_RELIEF_DEPTH - PIVOT_BEARING_THICKNESS) > 1e-9:
    raise AssertionError(
        "pivot bearing relief no longer leaves its specified thickness"
    )

INCLINE_DEG = 12.5182  # cone-axis plan incline (the assembly's ROT_Y_INCLINE)
_SIN_I = math.sin(math.radians(INCLINE_DEG))
_COS_I = math.cos(math.radians(INCLINE_DEG))

# --- cone-pivot-post-v2 attachment footprint -------------------------------
# The casting is centred at cone station -39.90136099793 while the plate
# origin/pivot remains station 196.  Its inward-shifted vertical attachment
# holes are a world-X pair at +/-POST_MOUNT_HALF_PITCH.  Undoing the engaged
# Ry(+INCLINE) placement gives the skewed pair in the platform's local (x, z).
POST_STATION = -39.90136099793
PIVOT_STATION = 152.27232594770453
POST_MAIN_DIA = POST_BLOCK_DIA
POST_LOCAL_Z = POST_STATION - PIVOT_STATION
POST_SOUTH_MARGIN = 3.175  # 1/8 in clearance beyond the post's south rim
PLATE_SOUTH_Z = POST_LOCAL_Z - POST_MAIN_DIA / 2.0 - POST_SOUTH_MARGIN
PLATE_LEN = NORTH_OVERHANG - PLATE_SOUTH_Z
POST_MOUNT_HALF_PITCH = POST_ATTACHMENT_SPACING / 2.0
POST_MOUNT_X = POST_MOUNT_HALF_PITCH * _COS_I
POST_MOUNT_DZ = POST_MOUNT_HALF_PITCH * _SIN_I
POST_MOUNT_WEST_XZ = (POST_MOUNT_X, POST_LOCAL_Z + POST_MOUNT_DZ)
POST_MOUNT_EAST_XZ = (-POST_MOUNT_X, POST_LOCAL_Z - POST_MOUNT_DZ)

# Fail before COM if the v2 foot ever drifts off the tapered plate.  Distance
# is normal to each straight boundary, not merely an axis-aligned half-width.
_POST_R = POST_MAIN_DIA / 2.0
_POST_SOUTH_CLEAR = POST_LOCAL_Z - (NORTH_OVERHANG - PLATE_LEN)
_POST_FRAC = (NORTH_OVERHANG - POST_LOCAL_Z) / PLATE_LEN
_POST_EAST_HALF = HALF_WIDTH_N + (EAST_HALF_S - HALF_WIDTH_N) * _POST_FRAC
_POST_WEST_HALF = WEST_HALF_N + (WEST_HALF_S - WEST_HALF_N) * _POST_FRAC
_POST_EAST_NORMAL_CLEAR = _POST_EAST_HALF / math.hypot(
    1.0, (EAST_HALF_S - HALF_WIDTH_N) / PLATE_LEN
)
_POST_WEST_NORMAL_CLEAR = _POST_WEST_HALF / math.hypot(
    1.0, (WEST_HALF_S - WEST_HALF_N) / PLATE_LEN
)
POST_FOOT_CONTAINMENT = (
    min(_POST_SOUTH_CLEAR, _POST_EAST_NORMAL_CLEAR, _POST_WEST_NORMAL_CLEAR) - _POST_R
)
if POST_FOOT_CONTAINMENT < 0.25:
    raise AssertionError(
        f"v2 post foot has only {POST_FOOT_CONTAINMENT:.3f} mm platform containment"
    )
if POST_MOUNT_HALF_PITCH + POST_MOUNT_TAP_DIA / 2.0 > _POST_R:
    raise AssertionError("v2 post mount taps fall outside the casting foot")

# Rule-12 webs round the tip-block hold-down hole (user ruling 2026-09-29), at
# print worst: the outline at .X, relief and counterbore at .XX, drilled holes
# +0.10, the hole's two stations (HoldDownX, HoldDownZ) at their +/-0.10
# bands; the post taps at their +/-0.10 bands, judged at the thread major.
# The relief is on the TOP face only (there the hole is the drilled
# clearance), the counterbore on the UNDERSIDE only (there the pivot is the
# bare drilled bore); each web is judged on the face both share.  The plan
# corner rounds sweep toward their own corners, away from this hole, so the
# straight edges bound the outline web.
_GENERAL_1PL_MM = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_GENERAL_2PL_MM = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_DRILL_OVERSIZE_MM = float(_config.title_block("drilled_hole")["plus_mm"])
_HOLDDOWN_SHIFT = math.hypot(HOLDDOWN_STATION_TOL_MM, HOLDDOWN_STATION_TOL_MM)
_HOLDDOWN_THRU_R = (HOLDDOWN_CLEARANCE_DIA + _DRILL_OVERSIZE_MM) / 2.0
_HOLDDOWN_CBORE_R = (HOLDDOWN_CBORE_DIA + _GENERAL_2PL_MM) / 2.0
_HOLDDOWN_PIVOT_DIST = math.hypot(HOLDDOWN_LOCAL_X, HOLDDOWN_LOCAL_Z)


def _edge_normal_distance(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Distance from ``point`` to the infinite line through plan points a, b."""
    (px, pz), (ax, az), (bx, bz) = point, a, b
    return abs((bx - ax) * (az - pz) - (ax - px) * (bz - az)) / math.hypot(
        bx - ax, bz - az
    )


_HOLDDOWN_XZ = (HOLDDOWN_LOCAL_X, HOLDDOWN_LOCAL_Z)
_SOUTH_Z = NORTH_OVERHANG - PLATE_LEN
HOLDDOWN_WEBS = {
    "pivot relief (top)": _HOLDDOWN_PIVOT_DIST
    - _HOLDDOWN_SHIFT
    - _HOLDDOWN_THRU_R
    - (PIVOT_BEARING_RELIEF_DIAMETER + _GENERAL_2PL_MM) / 2.0,
    "pivot bore (underside)": _HOLDDOWN_PIVOT_DIST
    - _HOLDDOWN_SHIFT
    - _HOLDDOWN_CBORE_R
    - (PIVOT_HOLE_DIA + _DRILL_OVERSIZE_MM) / 2.0,
    **{
        f"post tap {side}": math.dist(_HOLDDOWN_XZ, tap)
        - _HOLDDOWN_SHIFT
        - math.hypot(POST_MOUNT_STATION_TOL_MM, POST_MOUNT_STATION_TOL_MM)
        - _HOLDDOWN_CBORE_R
        - POST_MOUNT_THREAD_DIA / 2.0
        for side, tap in (("west", POST_MOUNT_WEST_XZ), ("east", POST_MOUNT_EAST_XZ))
    },
    "north edge": NORTH_OVERHANG - HOLDDOWN_LOCAL_Z,
    "east edge": _edge_normal_distance(
        _HOLDDOWN_XZ, (-HALF_WIDTH_N, NORTH_OVERHANG), (-EAST_HALF_S, _SOUTH_Z)
    ),
    "west edge": _edge_normal_distance(
        _HOLDDOWN_XZ, (WEST_HALF_N, NORTH_OVERHANG), (WEST_HALF_S, _SOUTH_Z)
    ),
}
for _edge in ("north edge", "east edge", "west edge"):
    HOLDDOWN_WEBS[_edge] -= _HOLDDOWN_SHIFT + _HOLDDOWN_CBORE_R + _GENERAL_1PL_MM
if min(HOLDDOWN_WEBS.values()) < 2.0:
    raise AssertionError(
        f"tip-block hold-down leaves a web under the U27 2.0 target: {HOLDDOWN_WEBS}"
    )

# The open-ended lock notch cuts from the engaged stud seat straight out
# through the plate's WEST edge. The cone-lock-knob stud is fixed to the base;
# on disengage the plate swings until its edge passes the stud and head.
# Tightened with no plate under it, the head fences the mouth and locks the
# plate disengaged; tightened on the plate it clamps the engaged pose.
# The notch runs along the swing arc's CHORD: at R~192 over ~3 deg to the
# mouth the sagitta is ~0.07, absorbed by the O6.35-stud-in-8.0 clearance.
#
# LOCAL-FRAME CONVENTION: the assembly places this part at Ry(+INCLINE)
# (train._plate_local_to_machine), under which local +x maps to machine WEST
# at the engaged pose -- every west-side feature below (the flare, the lock
# notch) is authored at local +x, east-side features at local -x.
SLOT_W = 8.0  # Ø6.35 stud clearance plus chord-vs-arc slack
# The notch seat was placed for the former stock O25.4-head knob (91882A425):
# the northern solution beside the post cleared the post but overlapped the
# T120/64T gear row, so the stud moved west to x 33.0 on the southern solution
# where that head kept a 2 mm post gap.  The O15.875 93585A190 head keeps the
# same seat (plate and base unchanged) with a wider post gap; the drive train
# re-checks the head against the post, gears and stop at import.
SLOT_E_X = 33.0
SLOT_E_Z = -205.8075686471163
LOCK_HEAD_POST_CLEARANCE = 2.0
SLOT_R = math.hypot(SLOT_E_X, SLOT_E_Z)
# The plate swings toward disengage (big end away from the drum), so in PLATE
# coords the fixed stud sweeps the INVERSE rotation: unit direction (-z, x)/R
# at E -- outward toward the west edge (+x), slightly north (+z).
SLOT_TX, SLOT_TZ = -SLOT_E_Z / SLOT_R, SLOT_E_X / SLOT_R


def _west_edge_x(z_local: float) -> float:
    """Authored x of the west taper edge at local z (linear 8 -> 37)."""
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
# mouth.  Sized so the linear worst case keeps >= 2.0 mm (U27) with the plate
# outline at .X (+/-0.8) and the base stop/stud holes at .XX (+/-0.51/axis):
# east edge at the stop 2 x 0.8 (lever 105.6 vs SLOT_R 208.4), west edge at the
# mouth 0.99 x 0.8, stop hole ~1.1, stud hole ~0.59, head/shank ~0.35 -- 4.41
# in all.  The base derives its swing-stop hole from this function.
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
