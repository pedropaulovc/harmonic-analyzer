r"""Pure-data contract for MHA-PD-023, the transgear pin (R9-68).

The plain steel pin the disc cluster runs on.  It is pressed through the
MHA-PD-018 arm's reamed hole at S from the rear until its domed head seats on
the arm's rear face; forward of the arm it carries, rear to front, the
MHA-PD-024 rear bushing, the MHA-PD-010 sleeve (with the disc, hub and screws on
it), the MHA-PD-025 front bushing and, in the groove near its front end, the
MHA-VN-047 retaining ring (McMaster 97431A260).  Nothing on it is threaded.

Frame: one revolve about local +Z.  Local z = 0 is the head's underside
(the face that seats on the arm's rear face, machine z -116.4625) and local
+Z runs toward the machine front, so machine z = ``HEAD_SEAT_MACHINE_Z`` -
local z.  The head runs z -HEAD_HEIGHT..0, the shank z 0..LENGTH.

PURE DATA: the build and the drawing both import it; neither imports the
other.  ``transgear_cluster_fit`` holds the chain the groove station sets.
"""

from __future__ import annotations

import math

import pd_transgear_arm_geometry as ARM
import vn_transgear_retaining_ring_spec as RING
from _gtol_cylinder import CylinderFace
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

PIN_NUMBER = "MHA-PD-023"
ARM_NUMBER = "MHA-PD-018"
RING_NUMBER = "MHA-VN-047"

# The head seats on the arm's rear face.
HEAD_SEAT_MACHINE_Z = round(ARM.FRONT_FACE_MACHINE_Z + ARM.THICKNESS, 6)  # -116.4625

# --- Shank: the running journal and the press in the arm -----------------------
# The sleeve and both bushings run on it (their bores Ø3.900 +0.030/+0.012,
# 0.012..0.038 diametral); the arm's REAM Ø3.874 +0.008/0 holds it by a
# 0.010..0.026 press (``pd_transgear_arm_geometry``), named on this sheet.
DIA = 3.900
DIA_BAND = (0.0, -0.008)  # (upper, lower) deviations, ground
DIA_MIN = round(DIA + DIA_BAND[1], 6)
DIA_MAX = round(DIA + DIA_BAND[0], 6)
DIA_PLACES = 3
# (loosest, tightest): smallest shank in the largest ream, and the reverse.
PRESS_INTERFERENCE = (
    round(DIA_MIN - ARM.PIN_BORE_DIA_MAX, 6),
    round(DIA_MAX - ARM.PIN_BORE_DIA_MIN, 6),
)  # 0.010, 0.026

# --- Head: Ø5.0, a 2.10 land then a spherical dome, 2.9 proud of the arm ------
# The head stops the press and, pulled forward by the ring's thrust on the
# load wall, holds the pin in the arm; nothing bears on its dome.  The land
# is a wall held to the policy's 1.5 hard floor at its printed lower limit:
# it prints .XX, so 2.10 leaves 1.59 (1.20 left 0.69, review of e0ac6477e; a
# 0.5 land at .X went to -0.3, review of 6de7230aa).  The dome stays 0.8
# high on top, so the apex stands 2.9 proud, less than the MHA-VN-041 head.
WALL_FLOOR = 1.5
HEAD_DIA = 5.0
HEAD_LAND = 2.10
HEAD_LAND_PLACES = 2
HEAD_LAND_MIN = round(HEAD_LAND - printed_band_mm(HEAD_LAND_PLACES), 6)  # 1.59
HEAD_LAND_FLOOR = WALL_FLOOR
HEAD_DOME_SAG = 0.8
HEAD_HEIGHT = HEAD_LAND + HEAD_DOME_SAG  # 2.9 proud of the arm's rear face
HEAD_DOME_R = ((HEAD_DIA / 2.0) ** 2 + HEAD_DOME_SAG**2) / (2.0 * HEAD_DOME_SAG)

# --- Ring groove -------------------------------------------------------------
# The groove's FRONT wall is the load wall: the cluster pushed forward bears
# the front bushing on the ring and the ring on this wall.  Its station from
# the head's underside is the pin's one functional length; it prints .XXX
# and the front bushing is faced to fit over its band (transgear_cluster_fit).
GROOVE_STATION = 47.25  # head underside to the groove's front (load) wall
GROOVE_STATION_PLACES = 3
GROOVE_STATION_BAND = printed_band_mm(GROOVE_STATION_PLACES)
GROOVE_DIA = RING.GROOVE_DIA
GROOVE_DIA_BAND = RING.GROOVE_DIA_BAND
GROOVE_WIDTH = RING.GROOVE_WIDTH
GROOVE_WIDTH_BAND = RING.GROOVE_WIDTH_BAND
GROOVE_REAR_STATION = round(GROOVE_STATION - GROOVE_WIDTH, 6)

# --- Front end: a plain length in front of the groove, then a dome -----------
# The land in front of the groove carries the ring's thrust, so it is a wall
# held at its PRINTED lower limit to the larger of the policy's 1.5 hard
# floor and three groove depths (ASSUMPTION from the ring maker's edge-margin
# guidance: 0.4768 x 3 = 1.4304).  Nothing mates on it, so it prints .XX:
# 2.10 leaves 1.59 (1.600 at .XXX left 1.470, review of e0ac6477e; at .X the
# title block's +/-0.8 left 0.7, Codex P2).
FRONT_LAND = 2.10  # groove load wall to the dome's base
FRONT_LAND_PLACES = 2
FRONT_LAND_BAND = printed_band_mm(FRONT_LAND_PLACES)
FRONT_LAND_MIN = round(FRONT_LAND - FRONT_LAND_BAND, 6)  # 1.59
TIP_DOME_SAG = 1.5
TIP_DOME_R = ((DIA / 2.0) ** 2 + TIP_DOME_SAG**2) / (2.0 * TIP_DOME_SAG)
LENGTH = round(GROOVE_STATION + FRONT_LAND + TIP_DOME_SAG, 6)  # 50.85
OVERALL_LENGTH = round(LENGTH + HEAD_HEIGHT, 6)  # 53.75, apex to tip
TIP_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z - LENGTH, 6)  # -167.3125
HEAD_APEX_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z + HEAD_HEIGHT, 6)  # -113.5625
GROOVE_LOAD_WALL_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z - GROOVE_STATION, 6)

GROOVE_DEPTH = (DIA - GROOVE_DIA) / 2.0
EDGE_MARGIN_MIN = 3.0 * GROOVE_DEPTH
FRONT_LAND_FLOOR = max(WALL_FLOOR, EDGE_MARGIN_MIN)  # 1.5

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "journal",
        MACHINED_UM,
        CylinderFace(DIA, contains_z_mm=GROOVE_REAR_STATION / 2.0),
    ),
)

# --- Decimal places ARE the tolerance (policy rule 2) --------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {
        "ShankDia",
        "HeadDia",
        "HeadLand",
        "GrooveStation",
        "GrooveDia",
        "GrooveWidth",
        "FrontLand",
    },
    "HeadDomeProfile": {"HeadDomeR"},
    "TipDomeProfile": {"TipDomeR"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {
        "ShankDia": DIA_PLACES,
        "HeadDia": 1,
        "HeadLand": HEAD_LAND_PLACES,
        "GrooveStation": GROOVE_STATION_PLACES,
        "GrooveDia": 3,
        "GrooveWidth": 3,
        "FrontLand": FRONT_LAND_PLACES,
    },
    "HeadDomeProfile": {"HeadDomeR": 1},
    "TipDomeProfile": {"TipDomeR": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-PD-023 dimension needs authored places")

for _ok, _what in (
    (HEAD_DOME_SAG < HEAD_DOME_R, "the head is not a spherical cap"),
    (TIP_DOME_SAG < TIP_DOME_R, "the tip is not a spherical cap"),
    (
        FRONT_LAND_MIN >= FRONT_LAND_FLOOR,
        f"the land in front of the groove {FRONT_LAND} at {FRONT_LAND_PLACES} "
        f"places has a printed lower limit {FRONT_LAND_MIN:.3f}, under "
        f"{FRONT_LAND_FLOOR:.4f}, the wall floor or three groove depths",
    ),
    (GROOVE_DIA < DIA_MIN, "the groove does not cut below the shank"),
    (
        math.isclose(HEAD_APEX_MACHINE_Z, -113.5625, abs_tol=1e-6),
        "the head apex is not 2.9 proud of the arm's rear face",
    ),
    (
        HEAD_LAND_MIN >= HEAD_LAND_FLOOR,
        f"the head land {HEAD_LAND} at {HEAD_LAND_PLACES} places has a printed "
        f"lower limit {HEAD_LAND_MIN:.2f}, under the {HEAD_LAND_FLOOR:.1f} "
        "wall floor",
    ),
    (
        PRESS_INTERFERENCE[0] > 0.0,
        f"the shank loses its press in the {ARM_NUMBER} ream: {PRESS_INTERFERENCE}",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-PD-023: {_what}")

# The ring the groove takes, named once above the groove Ø (one line: an
# above-callout holding a line break never prints).
GROOVE_CALLOUT = f"FOR {RING_NUMBER} RING, McMASTER {RING.SKU}"
# The shank's band sets the press in the arm's ream: the note names it, so
# the 0.008 band reads as the fit it is (review of 6de7230aa).  The finish
# field already says ground.
DRAWING_NOTES = "\n".join(
    (
        "1/4 IN BAR STOCK OK.",
        f"PRESSED INTO {ARM_NUMBER} FROM THE REAR UNTIL THE HEAD SEATS.",
        f"SHANK TO {ARM_NUMBER} REAM: {PRESS_INTERFERENCE[0]:.3f}-"
        f"{PRESS_INTERFERENCE[1]:.3f} DIAMETRAL INTERFERENCE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
