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

import math

import _config
from cone_pivot_post_installation import DRUM_X, GEAR_AXIS_SHIFT
from cone_tip_block_spec import BLOCK_Z as TIP_BLOCK_Z
from cone_tip_bushing_spec import LENGTH as BUSH_LEN

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + 6.35 + 33.368  # 90.518: v2 casting's journal axis

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
# Shared station anchor. Cone seats, cylinder faces, and channels translate as
# one rigid family without re-indexing the j-to-j pairs.
Z_DRUM0 = _config.machine("channels", "station_z0_mm")

# True-cone incline (M6.7, exact tracking). Values are at the OD-62.2 /
# DP 49.82 re-anchor (was 21.10 deg at the retired DP 30).
SIN_I = RADIUS_STEP / Z_PITCH  # 0.21675
COS_I = math.sqrt(1.0 - SIN_I * SIN_I)  # 0.97623
TAN_I = SIN_I / COS_I
SEC_I = 1.0 / COS_I
INCLINE_DEG = math.degrees(math.asin(SIN_I))  # 12.5182
SEAT_PITCH = Z_PITCH * COS_I  # 6.8888: seat pitch along the shaft

# Every station stays on the historical 6.5 cone reference face (the gears
# are narrowed from their SOUTH faces only; build_drive_train_assembly).
CONE_FACE_STATION_REFERENCE = 6.5
DRUM_FACE = 3.0  # cylinder gear face (gear z = 0..3, cam 3..6.5)

# Mesh anchor: X_PITCH is every cone gear's pitch-section x at the contact
# azimuth; the oblique-mesh edge slack is checker-arbitrated (see the drive
# train's mesh notes).
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
# unequal; the post station still fixes crank X and the pair DP.
POST_STATION = -39.90136099792956
X_CRANK = cone_station(POST_STATION)[0]  # -129.336: Ry180 v2 installation
Y_CRANK = Y_BASE_TOP + 6.35 + 72.7  # 129.850: v2 cast-in crank-axis height

# T006 is the reference gear for the tip-end stack. The bushing sits directly
# against its north face; the block follows after one bushing-half-width of
# clearance, and the pivot keeps its established 11 mm offset from the block.
T006_CENTER_STATION = SHAFT_T120_STATION + GEAR_AXIS_SHIFT + 19 * SEAT_PITCH
T006_NORTH_FACE = T006_CENTER_STATION + CONE_FACE_STATION_REFERENCE / 2.0
TIP_BLOCK_STATION = T006_NORTH_FACE + BUSH_LEN + BUSH_LEN / 2.0 + TIP_BLOCK_Z / 2.0
# The swing platform pivots about a vertical axis here, just north of the
# shaft's rear end; the base's pivot-screw seat sits directly under it.
PIVOT_STATION = TIP_BLOCK_STATION + 11.0
_PIVOT = cone_station(PIVOT_STATION)
PIVOT_XZ = (_PIVOT[0], _PIVOT[2])
