"""Approved MG lever-to-bracket thread, independent of machine pose and COM.

2026-10-20 Option B replaces the collar press entirely.  The rod is installed
by depth, not against an invented shoulder: its flat threaded tip reaches the
far bracket face.  The lever and bracket move together about the knife axis;
no locknut, set screw or adhesive is added.
"""

from __future__ import annotations

import math

from _hole_spec import HoleSpec, blind_cut_dia_mm

THREAD = "1/4-20"
THREAD_MAJOR = 6.35
PITCH = 25.4 / 20.0
ROD_DIA = 6.35
# Acceptance on selected 1/4-inch brass stock, not a supplier tolerance claim.
ROD_DIA_BAND = (0.0, -0.05)  # upper, lower
NECK_THICKNESS = 12.50
NECK_THICKNESS_TOL = 0.10
NECK_HALF_X = NECK_THICKNESS / 2.0
NOSE_R = 5.50
NOSE_R_TOL = 0.05
HOLE_LOCATION_TOL = 0.05  # locations from a real neck side and nose tip
THREAD_ROOT_ENVELOPE = 6.45  # native MAX requirement; NOT the tap-drill diameter
MOUTH_CHAMFER = 0.20
MOUTH_CHAMFER_BAND = (0.05, -0.05)  # axial and radial, 45 degrees
MOUTH_CHAMFER_MAX = MOUTH_CHAMFER + MOUTH_CHAMFER_BAND[0]
INCOMPLETE_THREAD_MAX = 1.5 * PITCH
REQUIRED_FULL_ENGAGEMENT = 1.5 * THREAD_MAJOR
TAP_SPEC = HoleSpec("tapped", THREAD, end="through_all", thread_class="2B")
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)

# Length from the free hemispherical tip; the opposite end is FLAT, threaded.
ROD_LENGTH = 167.5
ROD_LENGTH_TOL = 0.8  # printed title-block .X band
THREAD_LENGTH = 18.00  # flat tip to the end of incomplete root runout
THREAD_LENGTH_TOL = 0.51  # printed title-block .XX band
TIP_CHAMFER = 0.20
TIP_CHAMFER_BAND = (0.05, -0.05)
THREAD_ROOT_X = ROD_LENGTH - THREAD_LENGTH
FULL_THREAD_START_MAX = ROD_LENGTH + ROD_LENGTH_TOL - (THREAD_LENGTH - THREAD_LENGTH_TOL) + INCOMPLETE_THREAD_MAX


def full_thread_overlap(
    bracket_station: float,
    *,
    thickness: float = NECK_THICKNESS,
    thickness_tol: float = NECK_THICKNESS_TOL,
    rod_length: float = ROD_LENGTH,
    rod_length_tol: float = ROD_LENGTH_TOL,
    thread_length: float = THREAD_LENGTH,
    thread_length_tol: float = THREAD_LENGTH_TOL,
    incomplete: float = INCOMPLETE_THREAD_MAX,
    mouth: float = MOUTH_CHAMFER_MAX,
) -> float:
    """Worst installed intersection of full male and female thread intervals.

    Both ends' die lead is excluded.  The root lead is outside the receiver;
    the tip lead is conservatively deducted even though the tip is proud.
    A through tap runs completely through, so its lead exits the far face.
    """
    female_start = bracket_station - (thickness - thickness_tol) / 2.0 + mouth
    female_end = bracket_station + (thickness - thickness_tol) / 2.0 - mouth
    male_start = rod_length + rod_length_tol - (thread_length - thread_length_tol) + incomplete
    male_end = rod_length - rod_length_tol - incomplete
    return max(0.0, min(female_end, male_end) - max(female_start, male_start))


def installation_full_overlap(
    projection: float,
    projection_tol: float,
    *,
    thickness: float = NECK_THICKNESS,
    thickness_tol: float = NECK_THICKNESS_TOL,
    thread_length: float = THREAD_LENGTH,
    thread_length_tol: float = THREAD_LENGTH_TOL,
    incomplete: float = INCOMPLETE_THREAD_MAX,
    mouth: float = MOUTH_CHAMFER_MAX,
) -> float:
    """Full-thread intersection when the fitter sets native tip projection.

    Coordinates start at the near receiver face. Independent interval bounds
    include both thread leads; no shoulder seating or preload is assumed.
    """
    earliest_end = min(thickness - thickness_tol - mouth, thickness - thickness_tol + projection - projection_tol - incomplete)
    latest_start = max(mouth, thickness + thickness_tol + projection + projection_tol - (thread_length - thread_length_tol) + incomplete)
    return max(0.0, earliest_end - latest_start)


# Both the nose radius and each hole location have independent native bands.
# A toleranced radius is not an exact centre-to-edge distance.
DRILL_WANDER_START = 0.10
DRILL_WANDER_DEG = 0.3
THREAD_BORE_WANDER = DRILL_WANDER_START + (NECK_THICKNESS + NECK_THICKNESS_TOL) * math.tan(math.radians(DRILL_WANDER_DEG))
AXIS_OFFSET_MAX = math.hypot(NOSE_R_TOL + HOLE_LOCATION_TOL, NOSE_R_TOL + HOLE_LOCATION_TOL)
WALL_MIN = NOSE_R - NOSE_R_TOL - AXIS_OFFSET_MAX - THREAD_BORE_WANDER - THREAD_ROOT_ENVELOPE / 2.0 - MOUTH_CHAMFER_MAX
if WALL_MIN < 1.5:
    raise AssertionError("MG threaded nose loses the worst-case 1.5 mm wall")
