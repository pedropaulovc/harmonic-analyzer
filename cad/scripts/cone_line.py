"""Machine-frame cone journal line and the stations named on it.

Pure, SolidWorks-free: the drive train places the cone shaft, gears, post,
tip block and swing platform on this line, and the parts that must sit under
it read the same numbers instead of importing the drive-train script:

- the harmonic base drills the swing-platform pivot seat at ``PIVOT_XZ``;
- the paper-drive chain's crank sprocket sits on ``(X_CRANK, Y_CRANK)``.

Those consumers therefore depend on the gear-train configuration the line is
derived from, which is the honest dependency: a train change moves the seat.
Every expression here was moved verbatim out of build_drive_train_assembly,
so the values are bit-identical to what the assembly computed.
"""

from __future__ import annotations

import _config
from cone_shaft_land_bands import TIP_COLLAR_BODY_NORTH_SHIFT_MM
from cone_pitch import (
    COS_I,
    DP_TRAIN,
    INCLINE_DEG as INCLINE_DEG,
    RADIUS_STEP,
    SEAT_PITCH,
    SEC_I,
    SIN_I,
    TAN_I,
    Z_PITCH,
)
from dt_cone_pivot_post_installation import DRUM_X, GEAR_AXIS_SHIFT
from dt_cone_tip_block_spec import BLOCK_Z as TIP_BLOCK_Z
from dt_post_mount_stack import CONE_AXIS_HEIGHT_MM, PLATFORM_THICKNESS_MM

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + PLATFORM_THICKNESS_MM + CONE_AXIS_HEIGHT_MM

ADDENDUM = 25.4 / DP_TRAIN  # pitch-based placement reference, not a finite-tool tip
WORKING_DEPTH = 2.0 * ADDENDUM  # reference interleave depth for the mesh anchor
CONE_T120_PITCH_R = (
    (120.0 / DP_TRAIN) * 25.4 / 2.0
)  # largest cone gear's pitch radius

# The shared pitch/incline math is placement-independent (``cone_pitch``).
X_DRUM = DRUM_X
# Shared station anchor. Cone seats, cylinder faces, and channels translate as
# one rigid family without re-indexing the j-to-j pairs.
Z_DRUM0 = _config.machine("channels", "station_z0_mm")


# Every station stays on the historical 6.5 cone reference face: the gears
# grew SOUTH to the full seat pitch with their north faces fixed, so they
# touch (dt_cone_gear_stack; build_dt_drive_train_assembly).
CONE_FACE_STATION_REFERENCE = 6.5
DRUM_FACE = 3.0  # cylinder gear face (gear z = 0..3, cam 3..6.5)

# Mesh anchor: X_PITCH is every cone gear's pitch-section x at the contact
# azimuth; the oblique-mesh edge slack is checker-arbitrated (see the drive
# train's mesh notes).
# The ideal (N+2)/DP tip below is a retained PLACEMENT REFERENCE, not current
# material. Actual 120T/32T tooth-tip caps and physical envelopes come from
# dt_cylinder_gear_spec / dt_alignment_pinion_spec and their stock-form profiles.
DRUM_TIP_X = X_DRUM - (122.0 / DP_TRAIN) * 25.4 / 2.0
PEN_EDGE_SLACK = _config.fit(
    "cone_drum_oblique_mesh", "edge_slack_mm"
)  # cad/config/tolerances.yaml
PEN_MID = WORKING_DEPTH - PEN_EDGE_SLACK - (DRUM_FACE / 2.0) * TAN_I
X_PITCH = DRUM_TIP_X - ADDENDUM * SEC_I + PEN_MID


def cone_seat(j: int) -> tuple[float, float]:
    """(x, z) centre of cone gear j: pitch-projected x, r*sin(i) north."""
    r = CONE_T120_PITCH_R - RADIUS_STEP * j
    return X_PITCH - r * COS_I, Z_DRUM0 + Z_PITCH * j + r * SIN_I


# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_dt_cone_gear_shaft.py).
# CONE_ORIGIN stays the PIVOT END (station 0, the station datum).
SHAFT_T120_STATION = 25.0 + CONE_FACE_STATION_REFERENCE / 2.0  # 28.25
_GEAR_CONE_ORIGIN = [
    cone_seat(0)[0] - SHAFT_T120_STATION * SIN_I,
    Y_DRIVE,
    cone_seat(0)[1] - SHAFT_T120_STATION * COS_I,
]
# The post/carrier axis remains at its ch30-fitted world placement.  The gear
# family is translated GEAR_AXIS_SHIFT along that same infinite line.
CONE_ORIGIN = [
    _GEAR_CONE_ORIGIN[0] - GEAR_AXIS_SHIFT * SIN_I,
    Y_DRIVE,
    _GEAR_CONE_ORIGIN[2] - GEAR_AXIS_SHIFT * COS_I,
]


def cone_station(s: float) -> list[float]:
    """Machine point of the cone-shaft axis at station s (mm from pivot end)."""
    return [
        CONE_ORIGIN[0] + s * SIN_I,
        Y_DRIVE,
        CONE_ORIGIN[2] + s * COS_I,
    ]


# The corrected 2.8360-in v2 crank boss spans local z
# -21.3753..+50.6591. The 16T follows the shifted 64T row while the T12 chain
# plane remains photo-anchored, so the resulting axial gaps are intentionally
# unequal; the post station fixes crank X and the configured bore sets Y.
POST_STATION = -39.90136099792956
X_CRANK = cone_station(POST_STATION)[0]  # fixed post station in the machine frame
Y_CRANK = Y_BASE_TOP + PLATFORM_THICKNESS_MM + _config.machine("gear_train", "crank_axis_height_mm")

# T006 is the reference gear for the tip-end stack: its north face is the
# fixed layout reference the MHA-VN-016 stack collar is feeler-set off.
T006_CENTER_STATION = SHAFT_T120_STATION + GEAR_AXIS_SHIFT + 19 * SEAT_PITCH
T006_NORTH_FACE = T006_CENTER_STATION + CONE_FACE_STATION_REFERENCE / 2.0
# Extend the tip, block and pivot by the SAME northward delta that moves only
# the custom collar's large body and tap. Its small south end remains feeler-
# set off T006; collar-to-block and block-to-pivot clearances are invariant.
# The retained 7.5-mm extension and ordinary bands are not regraded.
TIP_END_EXTENSION_MM = 7.5 + TIP_COLLAR_BODY_NORTH_SHIFT_MM
PIVOT_STATION = T006_NORTH_FACE + 23.0 + TIP_END_EXTENSION_MM
# User ruling 2026-09-29 (eight-views-4.png): the tip block is a straight
# prism held by one screw in a fixed platform hole under its centre.  Its
# north face stands TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET south of the pivot,
# 0.8125 off the pivot screw's head at nominal -- the gap
# build_dt_drive_train_assembly proves at print-worst -- and the block grows
# SOUTH from there (its depth closes the adjuster's embed window), so the
# centre, and the platform hole under it, follow the depth.
TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET = 5.575
TIP_BLOCK_NORTH_FACE = PIVOT_STATION - TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET
TIP_BLOCK_STATION = TIP_BLOCK_NORTH_FACE - TIP_BLOCK_Z / 2.0
TIP_BLOCK_PIVOT_OFFSET = PIVOT_STATION - TIP_BLOCK_STATION
_PIVOT = cone_station(PIVOT_STATION)
PIVOT_XZ = (_PIVOT[0], _PIVOT[2])
