r"""Pure-data contract for MHA-PD-23, the transgear pin (R9-68).

The plain steel pin the disc cluster runs on.  It is pressed through the
MHA-PD-18 arm's reamed hole at S from the rear until its domed head seats on
the arm's rear face; forward of the arm it carries, rear to front, the
MHA-PD-24 rear bushing, the MHA-PD-10 sleeve (with the disc, hub and screws on
it), the MHA-PD-25 front bushing and, in the groove near its front end, the
MHA-PD-VN-61 retaining ring (McMaster 97431A240).  Nothing on it is threaded.

#290: the sheet prints decimal inch (the row's ``drawing_unit: in``); every
length below is the exact millimetre value of its printed inch nominal.  The
owner ruling of 2026-10-30 took the shank from 3.9 mm to 1/8 in.

Frame: one revolve about local +Z.  Local z = 0 is the head's underside
(the face that seats on the arm's rear face, machine z -116.4625) and local
+Z runs toward the machine front, so machine z = ``HEAD_SEAT_MACHINE_Z`` -
local z.  The head runs z -HEAD_HEIGHT..0, the shank z 0..LENGTH.

PURE DATA: the build and the drawing both import it; neither imports the
other.  ``transgear_cluster_fit`` holds the chain the groove station sets.
"""

from __future__ import annotations

import math

import _config
import pd_transgear_arm_geometry as ARM
import pd_vn_transgear_retaining_ring_spec as RING
from _gtol_cylinder import CylinderFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm
from pd_cluster_stack_band import PRINTED_LENGTH_BAND_IN
from _surface_finish import MACHINED_UM, SurfaceFinishControl

UNIT = drawing_unit("parts/pd-transgear-pin", _config.parts("pd-transgear-pin"))


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.0003``, ``1.860``."""
    text = f"{value_mm / 25.4:.{places}f}"
    return text[1:] if text.startswith("0.") else text


PIN_NUMBER = "MHA-PD-23"
ARM_NUMBER = "MHA-PD-18"
RING_NUMBER = "MHA-PD-VN-61"
FRONT_BUSHING_NUMBER = "MHA-PD-25"
# The sleeve and the two bushings, rear to front order on the shank.
RUNNING_MATES = ("MHA-PD-10", "MHA-PD-24", FRONT_BUSHING_NUMBER)

# The head seats on the arm's rear face.
HEAD_SEAT_MACHINE_Z = round(ARM.FRONT_FACE_MACHINE_Z + ARM.THICKNESS, 6)  # -116.4625

# --- Shank: the running journal and the press in the arm -----------------------
# The sleeve and both bushings run on it (their bores .125 REAM_SLIDE, cut by
# the owned .1260 reamer, .0009..0017 diametral); the arm's .124 REAM_H7 (the
# owned .1240 reamer) holds it by a .0003..0011 press
# (``pd_transgear_arm_geometry``), named at the shank Ø.  One turned diameter
# both presses and runs, so its band is the reamers' gap less both fits: .0003.
DIA = 3.175  # .125
DIA_BAND = (0.00254, -0.00508)  # (upper, lower) deviations, +.0001/-.0002 in
DIA_MIN = round(DIA + DIA_BAND[1], 6)
DIA_MAX = round(DIA + DIA_BAND[0], 6)
DIA_PLACES = 4
# (loosest, tightest): smallest shank in the largest ream, and the reverse.
PRESS_INTERFERENCE = (
    round(DIA_MIN - ARM.PIN_BORE_DIA_MAX, 6),
    round(DIA_MAX - ARM.PIN_BORE_DIA_MIN, 6),
)  # 0.00762, 0.02794

# --- Head: Ø.20, a .09 land then a spherical dome R.18 ------------------------
# The head stops the press and, pulled forward by the ring's thrust on the
# load wall, holds the pin in the arm; nothing bears on its dome.  The land
# is a wall held to the .080 target at its printed lower limit: .09 at .XX
# leaves exactly .080.  The R.18 dome rises .030 on top, so the apex stands
# .120 proud of the arm's rear face, under the MHA-PD-VN-57 head's 5/32.
HEAD_DIA = 5.08  # .20
HEAD_LAND = 2.286  # .09
HEAD_LAND_PLACES = 2
HEAD_LAND_MIN = round(HEAD_LAND - printed_band_mm(HEAD_LAND_PLACES, unit=UNIT), 6)
HEAD_LAND_FLOOR = WALL_TARGET_MM
HEAD_DOME_R = 4.572  # .18
HEAD_DOME_SAG = HEAD_DOME_R - math.sqrt(HEAD_DOME_R**2 - (HEAD_DIA / 2.0) ** 2)
HEAD_HEIGHT = HEAD_LAND + HEAD_DOME_SAG  # proud of the arm's rear face
# The inside corner where the shank meets the head's seat: the tool-nose
# radius the print allows, a single R MAX limit (machinist review round 4: the
# title block's .040 inside corner is wider than the .0375 step and could eat
# the whole seat).  At .005 it sinks less than .003 into the 45-deg corner, so
# the ream mouth's deburr clears it and the head seats flat on the arm.
SEAT_FILLET_R = 0.127  # .005 MAX
SEAT_FILLET_PLACES = 3
SEAT_FILLET_SUFFIX = " MAX"
# The arm's rear face under the head: outside the ream's broken mouth, inside
# the head's broken rim.
SEAT_CONTACT_WIDTH_MIN = round(
    (HEAD_DIA - printed_band_mm(2, unit=UNIT)) / 2.0
    - edge_break_chamfer_mm(unit=UNIT)
    - max(
        ARM.PIN_BORE_DIA_MAX / 2.0 + edge_break_chamfer_mm(unit=UNIT),
        DIA_MAX / 2.0 + SEAT_FILLET_R,
    ),
    6,
)

# --- Ring groove -------------------------------------------------------------
# The groove's FRONT wall is the load wall: the cluster pushed forward bears
# the front bushing on the ring and the ring on this wall.  Its station from
# the head's underside is the pin's one functional length: a term of the
# disc cluster's printed stack (transgear_cluster_fit), so it prints four
# places at the cluster's band (#2038 owner ruling 2026-10-28, option A).
GROOVE_STATION = 47.244  # 1.860, head underside to the groove's load wall
GROOVE_STATION_PLACES = 4
GROOVE_STATION_BAND = PRINTED_LENGTH_BAND_IN
GROOVE_DIA = RING.GROOVE_DIA
GROOVE_DIA_BAND = RING.GROOVE_DIA_BAND
GROOVE_WIDTH = RING.GROOVE_WIDTH
GROOVE_WIDTH_BAND = RING.GROOVE_WIDTH_BAND
GROOVE_REAR_STATION = round(GROOVE_STATION - GROOVE_WIDTH, 6)

# --- Front end: the tip apex from the head seat, the land and the dome -------
# The tip apex prints .XX from the head seat, the pin's one faced origin
# (rule 11): the dome's near-tangent junction with the shank cannot be picked
# up, so the land from the load wall to that junction prints only as a
# reference (ENFORCE run 20261024T034648173Z).  The land carries the ring's
# thrust, so it is a wall held to the larger of the .080 target and three
# groove depths (ASSUMPTION from the ring maker's edge-margin guidance:
# 3 x .015 = .045) at the worst case: the tip at its printed lower limit, the
# load wall at its upper, and the deepest dome on the shank, a hemisphere.
# 2.02 leaves .0867 (2.01 would leave .0767).
TIP_STATION = 51.308  # 2.02, head seat to the tip's apex
TIP_STATION_PLACES = 2
TIP_STATION_BAND = printed_band_mm(TIP_STATION_PLACES, unit=UNIT)
TIP_DOME_R = 1.778  # .07
TIP_DOME_SAG = TIP_DOME_R - math.sqrt(TIP_DOME_R**2 - (DIA / 2.0) ** 2)
TIP_DOME_SAG_MAX = DIA_MAX / 2.0  # a hemisphere on the largest shank
FRONT_LAND = round(TIP_STATION - GROOVE_STATION - TIP_DOME_SAG, 6)  # .12 REF
FRONT_LAND_PLACES = 2
FRONT_LAND_MIN = round(
    TIP_STATION
    - TIP_STATION_BAND
    - (GROOVE_STATION + GROOVE_STATION_BAND)
    - TIP_DOME_SAG_MAX,
    6,
)  # .0867
LENGTH = TIP_STATION
OVERALL_LENGTH = round(LENGTH + HEAD_HEIGHT, 6)  # apex to tip
TIP_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z - LENGTH, 6)  # -167.7705
HEAD_APEX_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z + HEAD_HEIGHT, 6)
GROOVE_LOAD_WALL_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z - GROOVE_STATION, 6)

GROOVE_DEPTH = (DIA - GROOVE_DIA) / 2.0
EDGE_MARGIN_MIN = 3.0 * GROOVE_DEPTH
FRONT_LAND_FLOOR = max(WALL_TARGET_MM, EDGE_MARGIN_MIN)  # .080

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "journal",
        MACHINED_UM,
        CylinderFace(DIA, contains_z_mm=GROOVE_REAR_STATION / 2.0),
        display_unit=UNIT,
    ),
)

# --- Decimal places ARE the tolerance (drawing-guidelines.md rule 3 (decimal places carry the tolerance)) --------------------------
# Each dome prints its radius and, as a reference, its height off the land's
# end face, so the blank and the dome read without deriving the cap.  The tip
# apex prints from the head seat; the land ahead of the groove, ending at the
# tip dome's junction, prints as a reference.
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
    "HeadDomeProfile": {"HeadDomeR", "HeadDomeSagDim"},
    "TipDomeProfile": {"TipDomeR", "TipDomeSagDim", "TipDomeZ"},
    "SeatFillet": {"SeatRadius"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {
        "ShankDia": DIA_PLACES,
        "HeadDia": 2,
        "HeadLand": HEAD_LAND_PLACES,
        "GrooveStation": GROOVE_STATION_PLACES,
        "GrooveDia": 3,
        "GrooveWidth": 3,
        "FrontLand": FRONT_LAND_PLACES,
    },
    "HeadDomeProfile": {"HeadDomeR": 2, "HeadDomeSagDim": 2},
    "TipDomeProfile": {
        "TipDomeR": 2,
        "TipDomeSagDim": 2,
        "TipDomeZ": TIP_STATION_PLACES,
    },
    "SeatFillet": {"SeatRadius": SEAT_FILLET_PLACES},
}
# The overall, apex to tip, a drawing reference for the bar cut (rule 10);
# the dome heights print as references through ``pd_transgear_pin_callouts``.
DRAWING_REFERENCE_PRECISION = 2
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-PD-23 dimension needs authored places")

for _ok, _what in (
    (HEAD_DOME_SAG < HEAD_DOME_R, "the head is not a spherical cap"),
    (TIP_DOME_SAG < TIP_DOME_R, "the tip is not a spherical cap"),
    (
        FRONT_LAND_MIN >= FRONT_LAND_FLOOR,
        f"the land in front of the groove leaves {inch_text(FRONT_LAND_MIN, 4)} "
        f"with the tip apex {inch_text(TIP_STATION, TIP_STATION_PLACES)} at its "
        "lower limit, the load wall at its upper and a hemispherical dome, under "
        f"{inch_text(FRONT_LAND_FLOOR, 4)}, the wall target or three groove depths",
    ),
    (GROOVE_DIA < DIA_MIN, "the groove does not cut below the shank"),
    (
        SEAT_CONTACT_WIDTH_MIN > 0.0,
        f"the head has no seat on the {ARM_NUMBER} rear face past its broken "
        f"edges and the R{inch_text(SEAT_FILLET_R, SEAT_FILLET_PLACES)} root",
    ),
    (
        HEAD_LAND_MIN >= HEAD_LAND_FLOOR - 1e-9,
        f"the head land {inch_text(HEAD_LAND, HEAD_LAND_PLACES)} has a printed "
        f"lower limit {inch_text(HEAD_LAND_MIN, 4)}, under the "
        f"{inch_text(HEAD_LAND_FLOOR, 3)} wall target",
    ),
    (
        PRESS_INTERFERENCE[0] > 0.0,
        f"the shank loses its press in the {ARM_NUMBER} ream: {PRESS_INTERFERENCE}",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-PD-23: {_what}")

# The press into the arm is the MHA-PD-00 assembly's pin-pressed step, not a
# part-sheet note (rule 24).
DRAWING_NOTES = "1/4 IN BAR STOCK OK."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
