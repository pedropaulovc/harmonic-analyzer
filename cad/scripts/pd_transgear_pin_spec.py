r"""Pure-data contract for MHA-PD-23, the transgear pin (R9-68).

The plain steel pin the disc cluster runs on: one diameter from head to tip.
Its shank slides through the MHA-PD-18 arm's reamed hole at S from the rear
until the domed head seats on the arm's rear face, and is bonded there with
LOCTITE 638 (owner ruling 2026-11-24, fit audit question 4; it replaces
the #2415 press land).  Forward of the arm the same shank carries, rear to
front, the MHA-PD-24 rear bushing, the MHA-PD-10 sleeve (with the disc, hub
and screws on it), the MHA-PD-25 front bushing and, in the groove near its
front end, the MHA-PD-VN-61 retaining ring (McMaster 97431A240).  Nothing on
it is threaded.

#290: the sheet prints decimal inch (the row's ``drawing_unit: in``); every
length below is the exact millimetre value of its printed inch nominal.  The
owner ruling of 2026-10-30 took the shank from 3.9 mm to 1/8 in.

Frame: one revolve about local +Z.  Local z = 0 is the head's underside
(the face that seats on the arm's rear face, machine z -114.888) and local
+Z runs toward the machine front, so machine z = ``HEAD_SEAT_MACHINE_Z`` -
local z.  The head runs z -HEAD_HEIGHT..0 and the shank z 0..LENGTH.

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
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN
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
HEAD_SEAT_MACHINE_Z = round(ARM.FRONT_FACE_MACHINE_Z + ARM.THICKNESS, 6)  # -114.888

# --- Shank: the bonded length and the running journal, one diameter -----------
# Made to fit (fit audit 2026-11-23, pending owner confirmation; owner
# 2026-11-23: "why do we need single micron level tolerance x class plug
# gauges for a hobby machining project"): the sheet prints the size as a
# reference and the acceptance by feel, the shank turned last to the three
# reamed running bores (the sleeve's and both bushings', the set's .1260
# reamer) until each turns free with no shake.  It prints no limits.
#
# DIA_BAND is NOT a printed limit: it is the ANALYSIS band, the shank that
# fit is modelled to produce.  What fails if it is .002 looser: play in the
# running bores cocks the sleeve and the front bushing, which tilts the disc
# toward the MHA-PD-22 collar and closes the collar-to-disc air
# (pd_cluster_air.COLLAR_AIR; build_pd_paper_drive_assembly gates it).  Its
# top stops at .1250, the MHA-PD-VN-68 shims' smallest bore, so no shim
# interferes (line-on-line at the worst case; transgear_cluster_fit,
# codjiflo P2 on #2124).  Its bottom is .1245 (owner ruling 2026-11-24, fit
# audit question 5: "pin +0/-.0005"; it was .1248): with the disc
# cluster .005 further back (transgear_cluster_fit) the collar air carries
# a running clearance to .0025, the range the shank's callout prints as a
# reference (pd_transgear_pin_callouts.RUNNING_CLEARANCE_TEXT).
DIA = 3.175  # .125
DIA_BAND = (0.0, -0.0127)  # (upper, lower) ANALYSIS deviations, +.0000/-.0005 in
DIA_MIN = round(DIA + DIA_BAND[1], 6)
DIA_MAX = round(DIA + DIA_BAND[0], 6)
DIA_PLACES = 3  # prints (Ø.125), a reference

# --- The running fit: the shank in its three mates' reamed bores ---------------
# The sleeve (MHA-PD-10) and both bushings (MHA-PD-24, MHA-PD-25) are reamed
# with the set's one .1260 reamer and print that size with no band.
# RUNNING_BORE_DIA_BAND is the ANALYSIS band that reamer is modelled to cut,
# on size to .0010 over (owner ruling 2026-11-24, fit audit question 5:
# "bores +.001"; it was .0005 over, the band those holes printed before
# the fit audit).  It is not a printed limit and no gauge is charged with
# it: nothing on a sheet bounds these bores from above, the shank is
# turned last to them.  Owned here,
# with the shank made to those bores, so the three bore specs and this
# part's callout read one number and the callout's module imports no mate's
# spec (Codjiflo on #3506).  RUNNING_CLEARANCE is the modelled result of the
# fit, which every stack reads: .0010-.0025.
RUNNING_BORE_DIA = 3.2004  # .1260, the reamer's size
RUNNING_BORE_DIA_BAND = (0.0254, 0.0)  # (upper, lower) ANALYSIS deviations: +.0010/0
RUNNING_CLEARANCE = (
    round(RUNNING_BORE_DIA + RUNNING_BORE_DIA_BAND[1] - DIA_MAX, 6),
    round(RUNNING_BORE_DIA + RUNNING_BORE_DIA_BAND[0] - DIA_MIN, 6),
)  # (least, greatest) diametral

# --- Bond: the shank's slip fit in the arm (fit audit 2026-11-23) --------------
# The shank slides through the arm's .1260 reamed bore and is bonded over the
# bore's full-diameter length; the head, seated on the arm's rear face, is
# clamped there while the compound cures (MHA-PD-00's pin step).  The gap is
# the arm bore's modelled band against the shank's, inside LOCTITE 638's
# gap fill (TDS: 0.25 mm; dt_pinion_arbor_geometry, sm_gooseneck_spring_joint
# and cone_tip_cluster book the same limit; test_pd_transgear_pin_drawing
# pins these literals to them, so this spec does not import a drive-train
# module).
RETAINING_COMPOUND = "LOCTITE 638"
LOCTITE_638_GAP_MAX = 0.25
BOND_GAP = (
    round(ARM.PIN_BORE_DIA_MIN - DIA_MAX, 6),
    round(ARM.PIN_BORE_DIA_MAX - DIA_MIN, 6),
)  # (least, greatest) diametral: .0010, .0020
# Rule 23: the bond's clearance as note 1 prints it (the pin is made last),
# the least the reamer and the shank model to the most the arm traveler's
# .127 set pin accepts: a bore that just refuses that pin, on the smallest
# modelled shank.  Here, not in pd_transgear_arm_spec, so the pin's sheet
# reads no arm module but the geometry above (Codjiflo r1 on #3492).
BOND_NO_GO_PIN_DIA = 3.2258  # .127, one pin of the .001-step set
BOND_GAP_ACCEPTED_MAX = round(BOND_NO_GO_PIN_DIA - DIA_MIN, 6)  # .0025
BOND_CLEARANCE_PRINTED = (BOND_GAP[0], BOND_GAP_ACCEPTED_MAX)  # .0010-.0025
# The bonded length: the thinnest arm less the rear mouth's largest chamfer
# and the front face's largest edge break.
BOND_LENGTH_MIN = round(
    ARM.THICKNESS
    - ARM.THICKNESS_BAND
    - ARM.PIN_MOUTH_CHAMFER_LIMITS[1]
    - edge_break_chamfer_mm(unit=UNIT),
    6,
)  # .354
# Capacity: ISO 10123 shear 25 N/mm^2 minimum (TDS), derated with the Henkel
# Retaining Compound Design Guide's factors as the repository books them,
# each taken low: 0.9 for steel on steel (sm_gooseneck_spring_joint), 0.3
# for the clearance (booked there at the 0.25 mm limit; the widest gap the
# arm's NO-GO accepts, .0025, is a quarter of it) and 0.5 for a long land
# (dt_pinion_arbor_geometry; .354 on Ø.125 is L/D 2.8).
LOCTITE_638_SHEAR_MPA = 25.0
BOND_FACTOR = 0.9 * 0.3 * 0.5
BOND_AXIAL_CAPACITY_N = (
    LOCTITE_638_SHEAR_MPA * BOND_FACTOR * math.pi * DIA_MIN * BOND_LENGTH_MIN
)  # 301 N (68 lbf)
BOND_TORQUE_CAPACITY_NMM = BOND_AXIAL_CAPACITY_N * DIA_MIN / 2.0  # 477 N mm
# Demand.  No working load crosses the bond axially: the ring's forward
# thrust pulls the head onto the arm's rear face, and rearward thrust goes
# through the rear bushing and the shims to the arm's front face.  The bond
# only keeps the pin from turning, rocking or backing out.  It is judged
# against the most the MHA-PD-VN-61 ring can pass, its catalogue thrust
# rating: pushed straight back on the pin (handling), and as the drag the
# turning front bushing puts on the ring's face at the ring's O.D., which
# twists the pin (ASSUMPTION: dry brass on steel, friction 0.2; the head's
# own friction on the arm is given no credit).
_N_PER_LBF = 4.4482216
BOND_AXIAL_DEMAND_N = RING.THRUST_LBF * _N_PER_LBF  # 267 N
BOND_FACE_FRICTION = 0.2
BOND_TORQUE_DEMAND_NMM = BOND_FACE_FRICTION * BOND_AXIAL_DEMAND_N * RING.OD / 2.0  # 156
BOND_TORQUE_MARGIN_MIN = 2.0  # the repository's bonded-joint margin

# --- Head: Ø.20, a .09 land then a spherical dome R.18 ------------------------
# The head seats on the arm's rear face and, pulled forward by the ring's
# thrust on the load wall, holds the pin in the arm (the bond only keeps it
# from turning or backing out); nothing bears on its dome.  The land
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
# the whole seat).  The root's fillet stands at most R off both the shank and
# the seat, so the arm's 45-degree rear mouth clears it when its leg is at
# least R (``ARM.PIN_MOUTH_CHAMFER_LIMITS``; Codjiflo, #2124): the head then
# seats flat on the arm.
SEAT_FILLET_R = 0.127  # .005 MAX
SEAT_FILLET_PLACES = 3
SEAT_FILLET_SUFFIX = " MAX"
# The arm's rear face under the head: outside the ream's chamfered mouth,
# inside the head's broken rim.
SEAT_CONTACT_WIDTH_MIN = round(
    (HEAD_DIA - printed_band_mm(2, unit=UNIT)) / 2.0
    - edge_break_chamfer_mm(unit=UNIT)
    - max(
        ARM.PIN_BORE_DIA_MAX / 2.0 + ARM.PIN_MOUTH_CHAMFER_LIMITS[1],
        DIA_MAX / 2.0 + SEAT_FILLET_R,
    ),
    6,
)

# --- Ring groove -------------------------------------------------------------
# The groove's FRONT wall is the load wall: the cluster pushed forward bears
# the front bushing on the ring and the ring on this wall.  Its station from
# the head's underside is the pin's one functional length: a term of the
# disc cluster's stack (transgear_cluster_fit).  The shims set the end float
# (owner ruling 2026-11-01, #2124); the station still sets the collar-to-disc
# air, so it prints +/-.001.
# #2019: the 3/8 arm seats the head .0625 further back, so the station grew
# from 1.860 by that and a half thousandth onto the grid: the load wall
# stands .0005 forward of its 5/16-arm station.
GROOVE_STATION = 48.8442  # 1.923, head underside to the groove's load wall
GROOVE_STATION_PLACES = 3
GROOVE_STATION_BAND = FIT_LENGTH_BAND_IN
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
# 2.08 leaves .0835 (2.07 would leave .0735).  #2019: 2.02 plus the 3/8 arm's
# .0625, on the .XX grid; the apex stands .0025 behind its 5/16-arm station.
TIP_STATION = 52.832  # 2.08, head seat to the tip's apex
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
)  # .0835
LENGTH = TIP_STATION
OVERALL_LENGTH = round(LENGTH + HEAD_HEIGHT, 6)  # apex to tip
TIP_MACHINE_Z = round(HEAD_SEAT_MACHINE_Z - LENGTH, 6)  # -167.72
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
# tip dome's junction, prints as a reference.  The shank prints its Ø as a
# reference (made to fit its three running bores, note 1).
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
        ARM.PIN_MOUTH_CHAMFER_LIMITS[0] >= SEAT_FILLET_R,
        f"the R{inch_text(SEAT_FILLET_R, SEAT_FILLET_PLACES)} root stands past "
        f"the {ARM_NUMBER} rear mouth's "
        f"{inch_text(ARM.PIN_MOUTH_CHAMFER_LIMITS[0], 3)} chamfer: the head "
        "stops on it short of the face",
    ),
    (
        HEAD_LAND_MIN >= HEAD_LAND_FLOOR - 1e-9,
        f"the head land {inch_text(HEAD_LAND, HEAD_LAND_PLACES)} has a printed "
        f"lower limit {inch_text(HEAD_LAND_MIN, 4)}, under the "
        f"{inch_text(HEAD_LAND_FLOOR, 3)} wall target",
    ),
    (
        0.0 < BOND_GAP[0] <= BOND_GAP[1] <= LOCTITE_638_GAP_MAX,
        f"the shank's gap {BOND_GAP} in the {ARM_NUMBER} ream is outside "
        f"{RETAINING_COMPOUND}'s 0-{LOCTITE_638_GAP_MAX} window",
    ),
    (
        BOND_AXIAL_CAPACITY_N >= BOND_AXIAL_DEMAND_N,
        f"the {RETAINING_COMPOUND} bond holds {BOND_AXIAL_CAPACITY_N:.0f} N, under "
        f"the {RING_NUMBER} ring's {BOND_AXIAL_DEMAND_N:.0f} N rating",
    ),
    (
        BOND_TORQUE_CAPACITY_NMM >= BOND_TORQUE_MARGIN_MIN * BOND_TORQUE_DEMAND_NMM,
        f"the {RETAINING_COMPOUND} bond holds {BOND_TORQUE_CAPACITY_NMM:.0f} N mm, "
        f"under {BOND_TORQUE_MARGIN_MIN} x the {BOND_TORQUE_DEMAND_NMM:.0f} N mm the "
        "front bushing's drag on the ring can put on the pin",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-PD-23: {_what}")

# The bond into the arm is the MHA-PD-00 assembly's pin step, not a
# part-sheet note (rule 24); the sheet gives the fit (rule 23).
DRAWING_NOTES = "1/4 IN BAR STOCK OK."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
