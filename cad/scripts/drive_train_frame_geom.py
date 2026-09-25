"""Machine frame of the cone train -- SolidWorks-free.

The drive line (Y_DRIVE), the true-cone incline (SIN_I/COS_I/...), the 20
cone-gear seats on the inclined shaft (cone_seat / cone_station) and the
cast-in crank axis (X_CRANK, Y_CRANK) all derive from one chain: the gear-train
diametral pitch and cone incline in ``cad/config/machine/``, the oblique-mesh
edge slack in ``tolerances``, and the v2 cone-pivot-post installation
(``cone_pivot_post_installation``). The drive-train assembly places the train
on these; the paper-drive assembly pins its chain layout to the crank axis.
Keeping the derivation here, not in ``build_drive_train_assembly``, is what
keeps the paper-drive recipe free of the drive-train assembly script. Same
drawing-free convention as ``channel_frame_geom``.
"""

from __future__ import annotations

import math

import _config
from channel_frame_geom import CAM_SHAFT_XY
from cone_pivot_post_installation import (
    CHANNEL_Z0,
    DRUM_X,
    GEAR_AXIS_SHIFT,
    POST_ROTATION_Y_DEG,
)

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + 6.35 + 33.368  # 90.518: v2 casting's journal axis
if abs(Y_DRIVE - CAM_SHAFT_XY[1]) > 1e-9 or abs(DRUM_X - CAM_SHAFT_XY[0]) > 1e-9:
    raise AssertionError(
        f"drum shaft axis ({DRUM_X}, {Y_DRIVE}) drifted from channel_frame_geom"
        f".CAM_SHAFT_XY {CAM_SHAFT_XY} (gear_train.drive_axis_y_mm) -- the channel"
        " assembly and the error budget read that one"
    )
# The manually rederived cone-pivot-post-v2 is the harder source than the old
# GT centreline fit: its foot sits on the 1/4-in platform and its cast-in
# journal is 33.368 above that seat. The resulting drive line cascades into
# the arbor pedestals, channel cams and connecting rods below.

DP_TRAIN = _config.machine(
    "gear_train", "diametral_pitch"
)  # cad/config/machine.yaml (DIMENSIONS.md ch12)
ADDENDUM = 25.4 / DP_TRAIN  # 0.510 at DP 49.82

WORKING_DEPTH = 2.0 * ADDENDUM  # 1.020: full tooth interleave depth
RADIUS_STEP = 3.0 * 25.4 / DP_TRAIN  # 1.5295: pitch-radius step per 6 teeth
CONE_T120_PITCH_R = (
    (120.0 / DP_TRAIN) * 25.4 / 2.0
)  # 30.59: largest cone gear pitch radius

# Shared machine grid: the working train is recentered independently of the
# fixed post/carrier, along the post's unchanged inclined journal.
_DRUM_SEAT_NOMINAL = _config.machine(
    "cone_incline", "drum_seat_nominal_mm"
)  # 7.2204 (OD 62.2)
Z_PITCH = _DRUM_SEAT_NOMINAL * math.cos(
    math.asin(RADIUS_STEP / _DRUM_SEAT_NOMINAL)
)  # 7.0566: drum z-pitch
X_DRUM = DRUM_X
if POST_ROTATION_Y_DEG != 180.0:
    raise AssertionError(
        "v2 post installation must preserve the exact Ry180 journal line"
    )
# (ch30 p004 post fit).  The cone seats are derived from this same anchor, so
# the complete cone and cylinder families retain all 20 radial mesh depths.
# solved -52.3 +/- 0.9). The drum sits directly UNDER the rocker arms' rod-side
# tips: the rocker pivot (+72.9) is the seesaw mid-span, its rod-pin hole 127.37
# out, and every connecting rod hangs PLUMB from tip to cam (ch30 photos + GT
# rocker-corner triangulation; the earlier "line-2 photogrammetry" oblique-rod
# reading -- drum well clear of the support, LONG rods -- is refuted).
# The whole cone/64T/crank train cascades rigidly off this (DRUM_TIP_X -> X_PITCH ...).
# The cone/crank cluster extends EAST of the drum (machine east = -x, the
# crank side), so every radial x-extent in the cascade below SUBTRACTS.
Z_DRUM0 = _config.machine("channels", "station_z0_mm")
# Shared station anchor. Cone seats, cylinder faces, and channels translate as
# one rigid family without re-indexing the j-to-j pairs.
if abs(Z_DRUM0 - CHANNEL_Z0) > 1e-9:
    raise AssertionError("channel station_z0 does not carry the fixed-post recenter")

# True-cone incline (M6.7, exact tracking -- see the TRUE-CONE MESH GEOMETRY
# section of build_drive_train_assembly's docstring). Values are
# at the OD-62.2 / DP 49.82 re-anchor (was 21.10 deg at the retired DP 30).
SIN_I = RADIUS_STEP / Z_PITCH  # 0.21675
COS_I = math.sqrt(1.0 - SIN_I * SIN_I)  # 0.97623
TAN_I = SIN_I / COS_I
SEC_I = 1.0 / COS_I
INCLINE_DEG = math.degrees(math.asin(SIN_I))  # 12.5182
SEAT_PITCH = Z_PITCH * COS_I  # 6.8888: seat pitch along the shaft

from cone_gear_spec import FACE_WIDTH as CONE_GEAR_FACE_WIDTH  # noqa: E402

# Cone gear face (cone_gear_spec.FACE_WIDTH, 6.0 since the U27 ruling of
# 2026-09-23).  Every station, the 64T gap and the T006 -> bushing -> tip-block
# stack stay on the historical 6.5 reference face: each gear is narrowed from
# its SOUTH face only (seed placed (reference - face)/2 north of its station),
# so all north faces -- and the tip end-play stack against T006 -- are
# unchanged; the drum's engaged zone ([-0.50, +1.60] about the reference
# centre) stays inside the minimum 5.2 face.
CONE_FACE = CONE_GEAR_FACE_WIDTH
CONE_FACE_STATION_REFERENCE = 6.5
DRUM_FACE = 3.0  # cylinder gear face (gear z = 0..3, cam 3..6.5)

# Mesh anchor: X_PITCH is every cone gear's pitch-section x at the
# contact azimuth. The oblique crossing dives (DRUM_FACE/2)*tan(i) past
# the mid-face penetration, so the mid value is capped at working depth
# minus the dive minus the edge slack -> tip interleave 0.00..1.14.
# Slack 0.55 is checker-arbitrated: the oblique crossing distorts the
# flank match beyond plain backlash math, worst at the smallest gears
# (their engagement arc spans a large azimuth, where the off-centre
# teeth barely drift out of the drum band) -- 0.15 left <=0.06 mm^3
# flank slivers at the five smallest stations, 0.35 still skinned the
# last four.
DRUM_TIP_X = X_DRUM - (122.0 / DP_TRAIN) * 25.4 / 2.0  # -85.80 at DP 49.82
PEN_EDGE_SLACK = _config.fit(
    "cone_drum_oblique_mesh", "edge_slack_mm"
)  # cad/config/tolerances.yaml
PEN_MID = WORKING_DEPTH - PEN_EDGE_SLACK - (DRUM_FACE / 2.0) * TAN_I  # 0.565
X_PITCH = DRUM_TIP_X - ADDENDUM * SEC_I + PEN_MID  # -85.76 at DP 49.82


def cone_seat(j: int) -> tuple[float, float]:
    """(x, z) centre of cone gear j: pitch-projected x, r*sin(i) north."""
    r = CONE_T120_PITCH_R - RADIUS_STEP * j
    return X_PITCH - r * COS_I, Z_DRUM0 + Z_PITCH * j + r * SIN_I


# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_cone_gear_shaft.py).
# CONE_ORIGIN stays the PIVOT END (station 0, the station datum); the physical
# shaft now runs FRONT_STUB further south (ch30 GT), so the part -- authored
# from its front stub end -- is PLACED at SHAFT_FRONT_STATION instead.
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
# unequal; the post station still fixes crank X and the pair DP.
POST_STATION = -39.90136099792956


# Exact-tracking self-check: the 20 mesh-derived seats lie on the shaft.
for _j in range(20):
    _x, _z = cone_seat(_j)
    _p = cone_station(SHAFT_T120_STATION + GEAR_AXIS_SHIFT + _j * SEAT_PITCH)
    if abs(_p[0] - _x) > 1e-9 or abs(_p[2] - _z) > 1e-9:
        raise AssertionError(f"cone seat {_j} off the shaft line: {(_x, _z)} vs {_p}")

X_CRANK = cone_station(POST_STATION)[0]  # -129.336: Ry180 v2 installation
Y_CRANK = Y_BASE_TOP + 6.35 + 72.7  # 129.850: v2 cast-in crank-axis height
