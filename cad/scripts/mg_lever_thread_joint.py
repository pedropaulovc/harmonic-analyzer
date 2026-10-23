"""Approved MG lever-to-bracket thread, independent of machine pose and COM.

2026-10-20 Option B replaces the collar press entirely.  The rod is installed
by depth, not against an invented shoulder: its flat threaded tip reaches the
far bracket face.  The lever and bracket move together about the knife axis;
no locknut, set screw or adhesive is added.
"""

from __future__ import annotations

import math

import _config
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import angular_band_deg, printed_band_mm
from mg_magnifying_bracket_spec import DRAWING_PRECISION, HEAD_MATERIAL_TOL

THREAD = "1/4-20"
THREAD_MAJOR = 6.35
PITCH = 25.4 / 20.0
ROD_DIA = 6.35
# Acceptance on selected 1/4-inch brass stock, not a supplier tolerance claim.
ROD_DIA_BAND = (0.0, -0.05)  # upper, lower
NECK_THICKNESS = 12.50  # nominal geometry unchanged; the sheet prints 12.5
NECK_THICKNESS_TOL = printed_band_mm(DRAWING_PRECISION["Neck"]["NeckThickness"])
NECK_HALF_X = NECK_THICKNESS / 2.0
NOSE_R = 5.50
NOSE_R_TOL = HEAD_MATERIAL_TOL
HOLE_LOCATION_TOL = HEAD_MATERIAL_TOL  # material from the real side and nose tip
MOUTH_CHAMFER = 0.20
# The title-block ceiling owns the native primary distance, not both legs.
# Keep the modeled 0.20; remove only the unsupported positive lower limit.
MOUTH_CHAMFER_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])
MOUTH_CHAMFER_BAND = (MOUTH_CHAMFER_MAX - MOUTH_CHAMFER, -MOUTH_CHAMFER)
# The native chamfer is 45 degrees and uses the ordinary angular band.
# The bracket defers to the title-block edge maximum, without a local note.
CHAMFER_LEG_MAX = MOUTH_CHAMFER_MAX * math.tan(math.radians(45.0 + angular_band_deg()))
INCOMPLETE_THREAD_MAX = 1.5 * PITCH
REQUIRED_FULL_ENGAGEMENT = 1.5 * THREAD_MAJOR
TAP_SPEC = HoleSpec("tapped", THREAD, end="through_all", thread_class="2B")
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)

# Length from the free hemispherical tip; the opposite end is FLAT, threaded.
ROD_LENGTH = 167.5
ROD_LENGTH_TOL = printed_band_mm(1)
THREAD_LENGTH = 18.00  # flat tip to the end of incomplete root runout
THREAD_LENGTH_TOL = printed_band_mm(2)
TIP_CHAMFER = 0.20
TIP_CHAMFER_MAX = MOUTH_CHAMFER_MAX
TIP_CHAMFER_BAND = (TIP_CHAMFER_MAX - TIP_CHAMFER, -TIP_CHAMFER)
THREAD_ROOT_X = ROD_LENGTH - THREAD_LENGTH


def installation_full_overlap(
    projection: float,
    projection_tol: float,
    *,
    thickness: float = NECK_THICKNESS,
    thickness_tol: float = NECK_THICKNESS_TOL,
    thread_length: float = THREAD_LENGTH,
    thread_length_tol: float = THREAD_LENGTH_TOL,
    incomplete: float = INCOMPLETE_THREAD_MAX,
    mouth: float = CHAMFER_LEG_MAX,
    tip_chamfer: float = CHAMFER_LEG_MAX,
) -> float:
    """Full-thread intersection when the fitter sets native tip projection.

    Coordinates start at the near receiver face. Independent interval bounds
    include both thread leads and an additive tip chamfer; no shoulder seating
    or preload is assumed. Overall rod length cancels from this fitted setting.
    """
    earliest_end = min(thickness - thickness_tol - mouth, thickness - thickness_tol + projection - projection_tol - incomplete - tip_chamfer)
    latest_start = max(mouth, thickness + thickness_tol + projection + projection_tol - (thread_length - thread_length_tol) + incomplete)
    return max(0.0, earliest_end - latest_start)


# ASME B1.1 specifies no internal maximum major diameter. These are nominal
# standard-thread geometry checks, NOT a guaranteed manufactured wall bound.
# Actual finished walls remain subject to drawing-guidelines rule17.
NOMINAL_THREAD_WALL = NOSE_R - THREAD_MAJOR / 2.0
NOMINAL_MOUTH_WALL = NOMINAL_THREAD_WALL - MOUTH_CHAMFER
