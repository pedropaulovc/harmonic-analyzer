r"""Pure-data contract for MHA-179, the transgear pin (R9-68).

The plain steel pin the disc cluster runs on.  It is pressed through the
MHA-164 arm's reamed hole at S from the rear until its domed head seats on
the arm's rear face; forward of the arm it carries, rear to front, the
MHA-180 rear bushing, the MHA-110 sleeve (with the disc, hub and screws on
it), the MHA-181 front bushing and, in the groove near its front end, the
MHA-182 retaining ring (McMaster 97431A260).  Nothing on it is threaded.

Frame: one revolve about local +Z.  Local z = 0 is the head's underside
(the face that seats on the arm's rear face, machine z -116.4625) and local
+Z runs toward the machine front, so machine z = ``HEAD_SEAT_MACHINE_Z`` -
local z.  The head runs z -HEAD_HEIGHT..0, the shank z 0..LENGTH.

PURE DATA: the build and the drawing both import it; neither imports the
other.  ``transgear_cluster_fit`` holds the chain the groove station sets.
"""

from __future__ import annotations

import math

import transgear_arm_geometry as ARM
import transgear_retaining_ring_spec as RING
from _gtol_spec import CylinderFace
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

PIN_NUMBER = "MHA-179"
ARM_NUMBER = "MHA-164"
RING_NUMBER = "MHA-182"

# The head seats on the arm's rear face.
HEAD_SEAT_MACHINE_Z = round(ARM.FRONT_FACE_MACHINE_Z + ARM.THICKNESS, 6)  # -116.4625

# --- Shank: the running journal and the press in the arm -----------------------
# The sleeve and both bushings run on it (their bores Ø3.900 +0.030/+0.012,
# 0.012..0.038 diametral); the arm's REAM Ø3.874 +0.008/0 holds it by a
# 0.010..0.026 press (``transgear_arm_geometry``).
DIA = 3.900
DIA_BAND = (0.0, -0.008)  # (upper, lower) deviations, ground
DIA_MIN = round(DIA + DIA_BAND[1], 6)
DIA_MAX = round(DIA + DIA_BAND[0], 6)
DIA_PLACES = 3

# --- Head: Ø5.0, a 0.5 land then a spherical dome, 2.0 proud of the arm ------
HEAD_DIA = 5.0
HEAD_LAND = 0.5
HEAD_DOME_SAG = 1.5
HEAD_HEIGHT = HEAD_LAND + HEAD_DOME_SAG  # 2.0 proud of the arm's rear face
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
FRONT_LAND = 1.5  # groove load wall to the dome's base
TIP_DOME_SAG = 1.5
TIP_DOME_R = ((DIA / 2.0) ** 2 + TIP_DOME_SAG**2) / (2.0 * TIP_DOME_SAG)
LENGTH = round(GROOVE_STATION + FRONT_LAND + TIP_DOME_SAG, 6)  # 50.25
OVERALL_LENGTH = round(LENGTH + HEAD_HEIGHT, 6)  # 52.25, apex to tip
TIP_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z - LENGTH, 6)
HEAD_APEX_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z + HEAD_HEIGHT, 6)  # -114.4625
GROOVE_LOAD_WALL_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z - GROOVE_STATION, 6)

# The groove's depth leaves the ring's catalogue seat; the land in front of
# it carries the ring's thrust (rule 12 target on the shear land: the land
# must be at least the groove depth times 3, ASSUMPTION from the ring maker's
# edge-margin guidance, so 1.5 covers 0.48 x 3 = 1.43).
GROOVE_DEPTH = (DIA - GROOVE_DIA) / 2.0
EDGE_MARGIN_MIN = 3.0 * GROOVE_DEPTH

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
        "HeadLand": 1,
        "GrooveStation": GROOVE_STATION_PLACES,
        "GrooveDia": 3,
        "GrooveWidth": 3,
        "FrontLand": 1,
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
    raise AssertionError("every marked MHA-179 dimension needs authored places")

for _ok, _what in (
    (HEAD_DOME_SAG < HEAD_DOME_R, "the head is not a spherical cap"),
    (TIP_DOME_SAG < TIP_DOME_R, "the tip is not a spherical cap"),
    (
        FRONT_LAND >= EDGE_MARGIN_MIN,
        f"the land in front of the groove {FRONT_LAND} is under "
        f"{EDGE_MARGIN_MIN:.2f}, three groove depths",
    ),
    (GROOVE_DIA < DIA_MIN, "the groove does not cut below the shank"),
    (
        math.isclose(HEAD_APEX_MACHINE_Z, -114.4625, abs_tol=1e-6),
        "the head apex is not 2.0 proud of the arm's rear face",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-179: {_what}")

# The ring the groove takes, named once above the groove Ø (one line: an
# above-callout holding a line break never prints).
GROOVE_CALLOUT = f"FOR {RING_NUMBER} RING, McMASTER {RING.SKU}"
DRAWING_NOTES = "\n".join(
    (
        "1/4 IN BAR STOCK OK. SHANK GROUND.",
        f"PRESSED INTO {ARM_NUMBER} FROM THE REAR UNTIL THE HEAD SEATS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
