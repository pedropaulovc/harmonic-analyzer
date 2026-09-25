"""The cone<->drum (MHA-027) mesh at its deep transverse slice, as posed.

Planar involute geometry shared by ``test_cone_gear_mesh_design`` (which
re-derives the printed deepened-mesh table from it) and ``error_budget``
(which reads each channel's nominal backlash and working pressure angle from
it for the mesh-lag and flank-toggle terms).  Pure python: imported by no
build script.
"""

from __future__ import annotations

import math

import numpy as np

import _config
import build_drive_train_assembly as assembly
import cone_gear_shaft_spec
import cone_gear_spec as spec
import cylinder_gear_spec as drum


M = spec.MODULE_MM
PRESSURE_ANGLE = math.radians(spec.PRESSURE_ANGLE_DEG)
DRUM_PITCH_R = drum.TEETH * M / 2.0
DRUM_BASE_R = DRUM_PITCH_R * math.cos(PRESSURE_ANGLE)
DRUM_TIP_R = drum.OUTSIDE_DIA / 2.0
DRUM_THICKNESS = spec.STANDARD_TOOTH_THICKNESS  # "FULL STANDARD THICKNESS"
DRUM_OD_LOWER = 0.10  # MHA-027 prints its tip +0/-0.10
DRUM_FLOOR_R = spec.chord_floor_radius_mm(120, thickness_mm=DRUM_THICKNESS)
BASE_PITCH = math.pi * M * math.cos(PRESSURE_ANGLE)

# Radial play.  Runouts turn with their gear, so they close the mesh at some
# angle; float can open it.  The cone runout is sized for the soldered seats
# #839 prints (0/-0.05), the looser of that and the current shaft land band.
SEAT_LAND_LOWER = min(cone_gear_shaft_spec.GEAR_SEAT_BAND[1], -0.05)
CONE_RUNOUT = (spec.BORE_DIA_BAND[0] - SEAT_LAND_LOWER) / 2.0
DRUM_RUNOUT = drum.BORE_DIAMETRAL_CLEARANCE_MM[1] / 2.0
JOURNAL_FLOAT = max(_config.fit("shaft_in_bushing")["diametral_clearance_mm"]) / 2.0
RUNOUT = CONE_RUNOUT + DRUM_RUNOUT
# Cone-shaft journal in its post, and the drum arbor in its pedestal.
FLOAT = RUNOUT + 2.0 * JOURNAL_FLOAT


def inv(angle: float) -> float:
    return math.tan(angle) - angle


def interleave(teeth: int) -> float:
    """Standard-tip interleave at the deep edge of the drum face, as posed.

    The assembly places a standard ``(N + 2) / DP`` tip circle; its nearest
    reach to the drum axis inside the drum face band sets the operating centre
    distance of the deep transverse slice.
    """
    j = (120 - teeth) // 6
    axis = np.array([assembly.SIN_I, 0.0, assembly.COS_I])
    e1 = np.cross(axis, [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    centre = np.array(
        assembly.cone_station(
            assembly.SHAFT_T120_STATION
            + assembly.GEAR_AXIS_SHIFT
            + (assembly.CONE_FACE_STATION_REFERENCE - assembly.CONE_FACE) / 2.0
            + j * assembly.SEAT_PITCH
        )
    )
    z0 = assembly.Z_DRUM0 + assembly.Z_PITCH * j
    tip_r = teeth * M / 2.0 + M
    theta = np.radians(np.linspace(0.0, 360.0, 36001))
    ring = centre + tip_r * (np.cos(theta)[:, None] * e1 + np.sin(theta)[:, None] * e2)
    # Along the gear axis a point is ring + a * axis.  Its z is linear in a,
    # so the drum face band and the cone face bound a to one interval, and
    # its squared distance from the drum axis is a quadratic in a: the exact
    # minimum is the vertex clipped to that interval.
    half_band = assembly.DRUM_FACE / 2.0
    a_lo = np.maximum(
        -assembly.CONE_FACE / 2.0, (z0 - half_band - ring[:, 2]) / axis[2]
    )
    a_hi = np.minimum(assembly.CONE_FACE / 2.0, (z0 + half_band - ring[:, 2]) / axis[2])
    dx = ring[:, 0] - assembly.X_DRUM
    dy = ring[:, 1] - assembly.Y_DRIVE
    slope = axis[0] ** 2 + axis[1] ** 2
    vertex = -(dx * axis[0] + dy * axis[1]) / slope
    along = np.clip(vertex, a_lo, a_hi)
    rho = np.hypot(dx + along * axis[0], dy + along * axis[1])
    return DRUM_TIP_R - float(rho[a_lo <= a_hi].min())


INTERLEAVE = {teeth: interleave(teeth) for teeth in spec.CONFIGURATION_TEETH}


def centre(teeth: int) -> float:
    """Nominal operating centre distance of the deep transverse slice."""
    return teeth * M / 2.0 + M + DRUM_TIP_R - INTERLEAVE[teeth]


def backlash(teeth: int, thickness: float, centre: float) -> float:
    """Exact planar circumferential backlash at the operating pitch circles."""
    r1 = teeth * M / 2.0
    working = math.acos((r1 + DRUM_PITCH_R) * math.cos(PRESSURE_ANGLE) / centre)
    r1w = centre * r1 / (r1 + DRUM_PITCH_R)
    r2w = centre * DRUM_PITCH_R / (r1 + DRUM_PITCH_R)
    delta = inv(PRESSURE_ANGLE) - inv(working)
    s1w = 2.0 * r1w * (thickness / (2.0 * r1) + delta)
    s2w = 2.0 * r2w * (DRUM_THICKNESS / (2.0 * DRUM_PITCH_R) + delta)
    return 2.0 * math.pi * r1w / teeth - s1w - s2w


def tip_land(teeth: int, thickness: float, tip_r: float) -> float:
    r1 = teeth * M / 2.0
    tip_angle = math.acos(r1 * math.cos(PRESSURE_ANGLE) / tip_r)
    return 2.0 * tip_r * (thickness / (2.0 * r1) + inv(PRESSURE_ANGLE) - inv(tip_angle))


def contact_ratio(teeth: int, tip_r: float, drum_tip_r: float, centre: float) -> float:
    """Transverse CR with both base-circle interference limits."""
    base_r = teeth * M / 2.0 * math.cos(PRESSURE_ANGLE)
    working = math.acos((base_r + DRUM_BASE_R) / centre)
    line = centre * math.sin(working)
    start = max(line - math.sqrt(drum_tip_r**2 - DRUM_BASE_R**2), 0.0)
    end = min(math.sqrt(tip_r**2 - base_r**2), line)
    return (end - start) / BASE_PITCH


def working_angle(teeth: int, centre_mm: float) -> float:
    """Operating pressure angle (rad) of the mesh at centre distance ``centre_mm``."""
    r1 = teeth * M / 2.0
    return math.acos((r1 + DRUM_PITCH_R) * math.cos(PRESSURE_ANGLE) / centre_mm)
