r"""Pure transgear-arm (MHA-PD-18) geometry shared by the arm, its plate, its
pivot hardware and the paper-drive assembly.

Book ch. 23 (t157 / t161 / t241): a steel link that swings on the MHA-PD-VN-57
shoulder screw at the pivot P on the support bar, carries the MHA-PD-23 pin of
the disc cluster (pressed into a reamed hole) at S, the MHA-PD-19 plate (and
through it the knob shaft) on two #8-32 taps between them, and the 1/8 latch
pin in its square end.

Local frame (the part's origin and axes; the assembly places it by a pure
rotation about Z and a translation):

* origin on the pivot axis P, on the arm's FRONT face (the face that bears on
  the MHA-PD-20 spacer; machine z FRONT_FACE_MACHINE_Z, -124.4);
* +X along the arm centreline from P toward the square end (machine U);
* +Y across the arm toward its upper tangent edge (machine N = U rotated
  +90 deg about +Z), the edge the plate's top edge sits flush with;
* +Z through the thickness toward the rear face (machine +Z), so the arm
  occupies z 0..THICKNESS and the plate mounts on z = THICKNESS.

Keep drawing-only notes and annotation contracts out of this module so that
sheet-text edits cannot invalidate the assembly recipe.
"""

from __future__ import annotations

import math
from fractions import Fraction

import _config
from _column_clamp_interface import ARC_DEPTH
from _cone_axis_constants import FRAME_FRONT_COLUMN_Z
import pd_rack_pinion_spec as DISC
import pd_support_bar_spec as BAR
import _mcmaster_90325a174 as PIVOT
from _fit_close_running import measured_close_running_clearance_mm
from _fit_deviations import deviations
from _gear_quality import reducer_position_diameter_mm
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_deviations,
)
import pd_transgear_pivot_spacer_spec as SPACER
import _transgear_arm_plate_locating_interface as LOCATING_PIN

from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm

MM_PER_IN = 25.4
# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/pd-transgear-arm", _config.parts("pd-transgear-arm"))


def printed_reach_mm(
    model: float, places: int, limits: tuple[float, float] | None = None
) -> float:
    """Farthest an accepted part may stand from the mm model, either way, when
    the sheet prints the model rounded to ``places`` inch places under
    ``limits`` (the title-block row when None).  The interface nominals the
    arm keeps in mm print rounded, so their walls and stacks are judged at
    this symmetric enclosure of the printed limits."""
    return max(abs(d) for d in printed_deviations(model, places, limits, unit=UNIT))


# The assembly's anchor for the arm: its front face on the spacer's rear
# face, the spacer's front face on the bar's back face (the column clamp's
# arc depth in front of the frame's front column plane): -124.413.
FRONT_FACE_MACHINE_Z = FRAME_FRONT_COLUMN_Z - ARC_DEPTH + SPACER.LENGTH

# --- Stock: 5/16 x 1 precision-ground flat bar, faces as supplied ------------
# The arm is cut from McMaster 9517K466 (R9-6, R9-25): its thickness is the
# stock's, ±0.001 in as supplied (the catalogue tolerance), not a machined
# band.  The sheet prints it as an untoleranced reference to the stock
# (#2147); walls, joints and the chain stack read the catalogue limits,
# THICKNESS_BAND.
STOCK_SKU = "9517K466"
STOCK_THICKNESS_IN = Fraction(5, 16)
THICKNESS = float(STOCK_THICKNESS_IN) * MM_PER_IN  # 7.9375
THICKNESS_BAND = 0.001 * MM_PER_IN  # ±0.0254
# The pin bore S's perpendicularity to face A, over the bore: ⊥ .001, the
# shop's reamed-hole row (owner ruling 2026-11-08 (Pedro), #2144 item 4.1).
# Its axis zone run on to the chain plane is
# paper_drive_arm_registration.S_AXIS_ZONE_DIAMETER_MM.
PIN_BORE_PERPENDICULARITY_IN = ".001"
PIN_BORE_PERPENDICULARITY_MM = float(PIN_BORE_PERPENDICULARITY_IN) * MM_PER_IN

# --- Outline: hull of r12.5 about P and r7 about T, cut square through T ----
PIVOT_END_R = 12.5
TIP_END_R = 7.0
# T: the r7 round's centre; the square end face lies on it.  The model
# carries 128.9 (R9-13); the outline's lean and end width derive from it.
# It prints .XX (R9-23, TIP_STATION_BAND): the latch pin's full diameter
# must pass the hook's far face, and the hook's fit-up set moves the hook in
# y/z only, so nothing absorbs the station along the pin axis.
# #290: the pivot round, the tip station and the end width keep their mm
# nominals (the MHA-PD-19 plate's flush edge and the MHA-PD-14 hook's pin
# station are fitted to them) and print rounded to .XX (R.49, 5.07, .55);
# the walls and the hanger joints read the printed limits' reach.
TIP_STATION = 128.9
OUTLINE_PLACES = 2
TIP_STATION_PLACES = 2
# The straight edges are tangent to both rounds; each leans in toward the
# square end by EDGE_LEAN, its outward normal (sin, cos) of that angle.
EDGE_LEAN = math.asin((PIVOT_END_R - TIP_END_R) / TIP_STATION)
# Tangent point of the upper edge on the pivot round (the lower is its mirror
# in y); the square end truncates both edges at the tip station, short of
# their tangent points on the r7 round.
PIVOT_TANGENT_X = PIVOT_END_R * math.sin(EDGE_LEAN)
PIVOT_TANGENT_Y = PIVOT_END_R * math.cos(EDGE_LEAN)


def edge_half_width(x: float) -> float:
    """The outline's half-width at station x on its straight tangent edges."""
    if not PIVOT_TANGENT_X <= x <= TIP_STATION:
        raise ValueError(f"station {x} is off the straight edges")
    return PIVOT_END_R / math.cos(EDGE_LEAN) - x * math.tan(EDGE_LEAN)


END_HALF_WIDTH = edge_half_width(TIP_STATION)
PIVOT_END_R_BAND = printed_reach_mm(PIVOT_END_R, OUTLINE_PLACES)
END_HALF_WIDTH_BAND = printed_reach_mm(2.0 * END_HALF_WIDTH, OUTLINE_PLACES) / 2.0
# Either printed outline row moves a straight edge at most this far.
OUTLINE_BAND = max(PIVOT_END_R_BAND, END_HALF_WIDTH_BAND)

# --- Pivot at P: a reamed running fit on the as-supplied shoulder ----------
# #2413 (DFM, 2026-11-11): one standard .1940 chucking reamer, banded
# +.0010/0 so .194 GO and .195 NO-GO pin gauges accept it; every as-supplied
# MHA-PD-VN-57 shoulder (.1865-.1875) runs in every accepted bore.  Nothing
# reads a tenth-level clearance window: the latch sets the arm's working
# position and the hanger stack pays the whole maximum clearance as float.


# The spot face seats the MHA-PD-VN-63 curved disc spring's OD rim (Ø10.744) under
# the MHA-PD-VN-57 head; the spring's float on the shoulder still clears its rim.
SPOT_FACE_DIA = 11.5062  # .453
SPOT_FACE_DIA_GROWTH = drilled_oversize_mm(unit=UNIT)  # +.004/0 (drilled row)
# The floor is dimensioned from the FRONT face so the spring's room never
# sees the arm's stock thickness (transgear_hanger_joints.SPRING_ROOM_*).
# 6.9 (was 6.4; owner ruling 2026-10-31, #290): the spot face is 0.5
# shallower and gives the spring the room the retired MHA-PD-VN-67 shim
# restored.  It is the spring's seat (exempt from the inch grid, the spring
# model is untouched): it keeps 6.9, so the room's nominal stays the
# spring's 0.80 model height, and prints .2717 ±.0020; the room is judged
# at that print's reach (0.693..0.957 with the spacer's .197 ±.002, inside
# the spring's travel).
SPOT_FACE_FLOOR_FROM_FRONT = 6.9
SPOT_FACE_FLOOR_PLACES = 4
SPOT_FACE_FLOOR_TOLERANCE = 0.0508  # ±.002
SPOT_FACE_FLOOR_BAND = printed_reach_mm(
    SPOT_FACE_FLOOR_FROM_FRONT,
    SPOT_FACE_FLOOR_PLACES,
    (-SPOT_FACE_FLOOR_TOLERANCE, SPOT_FACE_FLOOR_TOLERANCE),
)
SPOT_FACE_DEPTH = THICKNESS - SPOT_FACE_FLOOR_FROM_FRONT

PIVOT_BEARING_LENGTH_MAX = SPOT_FACE_FLOOR_FROM_FRONT + SPOT_FACE_FLOOR_BAND
PIVOT_BORE_TO_FRONT_FACE_ANGLE_DEG = 90.0
PIVOT_BORE_TO_FRONT_FACE_ANGLE_BAND_DEG = angular_band_deg(unit=UNIT)
PIVOT_SEATED_AXIS_ANGLE_MAX = (
    math.radians(PIVOT_BORE_TO_FRONT_FACE_ANGLE_BAND_DEG)
    + math.atan(SPACER.FRONT_FACE_PERPENDICULARITY / SPACER.FACE_PERPENDICULARITY_ZONE_DIA)
    + math.atan(SPACER.REAR_FACE_PERPENDICULARITY / SPACER.FACE_PERPENDICULARITY_ZONE_DIA)
)
PIVOT_AXIS_BINDING_SWEEP_MAX = PIVOT_BEARING_LENGTH_MAX * math.tan(PIVOT_SEATED_AXIS_ANGLE_MAX)
# The clearance prints in inches, to four places.
PIVOT_FIT_CLEARANCE_PLACES = 4
# The least clearance the shoulder needs to run free: the shared
# close-running minimum plus the sweep of a bore at the general angular row
# on the seated spacer, both spacer face grades paid.
if not 3.0 < PIVOT.SHOULDER_DIA <= 6.0:
    raise ValueError("the pivot running minimum requires the shared ISO 3-through-6 mm clearance class")
PIVOT_RUNNING_CLEARANCE_MIN = measured_close_running_clearance_mm()[0] + PIVOT_AXIS_BINDING_SWEEP_MAX
PIVOT_BORE_DIA = 4.9276  # .1940, the reamer's size
PIVOT_BORE_DIA_BAND = (0.0254, 0.0)  # (upper, lower) deviations: +.0010/0
PIVOT_BORE_FULL_LIMITS = (
    PIVOT_BORE_DIA + PIVOT_BORE_DIA_BAND[1],
    PIVOT_BORE_DIA + PIVOT_BORE_DIA_BAND[0],
)
PIVOT_BORE_DIAMETRAL_CLEARANCE = (
    round(PIVOT_BORE_FULL_LIMITS[0] - PIVOT.SHOULDER_DIA - max(PIVOT.SHOULDER_DIA_LIMITS), 6),
    round(PIVOT_BORE_FULL_LIMITS[1] - PIVOT.SHOULDER_DIA - min(PIVOT.SHOULDER_DIA_LIMITS), 6),
)  # .0065, .0085
if PIVOT_BORE_DIAMETRAL_CLEARANCE[0] < PIVOT_RUNNING_CLEARANCE_MIN:
    raise AssertionError("the MHA-PD-18 pivot ream binds the largest MHA-PD-VN-57 shoulder")


# --- Pin at S: REAM THROUGH, the press for the MHA-PD-23 pin (R9-68) ---------
# The MHA-PD-23 pin is pressed in from the rear until its head seats on the
# rear face, so the hole is reamed square through the ground faces.  #2415:
# only the pin's short press land under its head grips this ream; the
# running journal passes through it clear and is never dragged through the
# press.  The press is asserted in pd_transgear_arm_spec, which imports
# both: the pin spec imports this module.
PIN_STATION = 68.815  # |S - P|, the reducer's kinematic station; BASIC .XXXX
# Preserve the pivot, latch and pressed stud. The rack setting follows the
# feed contact law; only the reducer bearing follows its physical axis datum.
STUD_MACHINE_X = 0.0
ARM_U = (
    (STUD_MACHINE_X - BAR.PIVOT_TAP_X) / PIN_STATION,
    -math.sqrt(1.0 - ((STUD_MACHINE_X - BAR.PIVOT_TAP_X) / PIN_STATION) ** 2),
)
ARM_N = (-ARM_U[1], ARM_U[0])
ARM_ANGLE_DEG = math.degrees(math.atan2(ARM_U[1], ARM_U[0]))
_MESH_ANGLE = math.radians(DISC.MESH_ANGLE_DEG)
# CENTRE_DISTANCE is the physical mounting source, not a profile-shift-derived
# generated centre. Keep this transform shared by the plate and native assembly.
KNOB_BORE_STATION = PIN_STATION + DISC.CENTRE_DISTANCE * (
    math.cos(_MESH_ANGLE) * ARM_U[0] + math.sin(_MESH_ANGLE) * ARM_U[1]
)
KNOB_BORE_OFFSET = DISC.CENTRE_DISTANCE * (
    math.cos(_MESH_ANGLE) * ARM_N[0] + math.sin(_MESH_ANGLE) * ARM_N[1]
)

# #2415: .1260 +.0005/0, cut by the owned .1260 reamer (the bushings'), so
# the pin's Ø.1250 journal slips through and only its land presses.
PIN_BORE_DIA = 3.2004  # .126
PIN_BORE_DIA_BAND = (0.0127, 0.0)  # (upper, lower) deviations, reamed
PIN_BORE_DIA_MAX = round(PIN_BORE_DIA + PIN_BORE_DIA_BAND[0], 6)
PIN_BORE_DIA_MIN = round(PIN_BORE_DIA + PIN_BORE_DIA_BAND[1], 6)
# The MHA-PD-23 head seats on the rear face over its R.005 MAX root: the rear
# mouth is a 45-degree chamfer at least the root's radius on the leg, so the
# root clears it and the head lands on the face (Codjiflo, #2124). Its upper
# limit is the title block's chamfer break; ``pd_transgear_pin_spec`` checks
# the clearance against the pin's root. The band is the model's (#2174): the
# build puts it on the mouth profile's native leg dimension, which section
# D-D imports, and the limits below are that printed dimension's.
PIN_MOUTH_CHAMFER = 0.2032  # .008
PIN_MOUTH_CHAMFER_PLACES = 3
PIN_MOUTH_CHAMFER_TOLERANCE = 0.0508  # ±.002
PIN_MOUTH_CHAMFER_LIMITS = tuple(
    round(PIN_MOUTH_CHAMFER + deviation, 6)
    for deviation in printed_deviations(
        PIN_MOUTH_CHAMFER,
        PIN_MOUTH_CHAMFER_PLACES,
        (-PIN_MOUTH_CHAMFER_TOLERANCE, PIN_MOUTH_CHAMFER_TOLERANCE),
        unit=UNIT,
    )
)  # .006/.010
# --- Plate taps: 2 x #8-32 THROUGH; ordinary entry/exit edge breaks ---------
PLATE_SCREW_PITCH = 15.0
PLATE_CENTRELINE_OFFSET = -3.375  # 1-1/4 in plate's centreline from its bore
PLATE_SCREW_MID_STATION = KNOB_BORE_STATION + PLATE_CENTRELINE_OFFSET
PLATE_TAP_STATIONS = (
    PLATE_SCREW_MID_STATION - PLATE_SCREW_PITCH / 2.0,
    PLATE_SCREW_MID_STATION + PLATE_SCREW_PITCH / 2.0,
)

# Matched locating dowels, independent of the mounting screws' clearance.
# 13.1 (was 13.7): owner ruling 2026-10-27 (#1379) confirmed option W1 under
# the full-budget wall rule (sketch and per-term arithmetic in
# issuecomment-6443060097). At 13.7 the full
# worst-case wall to the arm's edge, with the outline's edge break and the
# drill's run-off, fell to 1.76 (WALLS below). 13.2 met 2.0 by 0.014, too
# thin for the reducer centre's ±0.5 source-mutation control; 13.1 keeps 2.06.
LOCATOR_PAIR_BASELINE_MM = 13.1
LOCATOR_SITES_MM = (
    (PLATE_SCREW_MID_STATION, LOCATOR_PAIR_BASELINE_MM / 2.0),
    (PLATE_SCREW_MID_STATION, -LOCATOR_PAIR_BASELINE_MM / 2.0),
)
# The interface's .093 REAM_H7 press, printed as the reamer's band
# (upper, lower), as the named fit bands are written.
LOCATOR_HOLE_DIA_MM = min(LOCATING_PIN.PRESS_HOLE_LIMITS_MM)  # .0930
LOCATOR_HOLE_PLACES = 4
LOCATOR_HOLE_DIA_BAND = tuple(
    limit - LOCATOR_HOLE_DIA_MM for limit in reversed(LOCATING_PIN.PRESS_HOLE_LIMITS_MM)
)
_LOCATOR_PRINTED = tuple(
    LOCATOR_HOLE_DIA_MM + deviation
    for deviation in printed_deviations(
        LOCATOR_HOLE_DIA_MM, LOCATOR_HOLE_PLACES, deviations(LOCATOR_HOLE_DIA_BAND), unit=UNIT,
    )
)
if not (
    LOCATING_PIN.PRESS_HOLE_LIMITS_MM[0] - 1e-9
    <= min(_LOCATOR_PRINTED)
    < max(_LOCATOR_PRINTED)
    <= LOCATING_PIN.PRESS_HOLE_LIMITS_MM[1] + 1e-9
):
    raise AssertionError("the printed locating ream leaves the interface's press limits")
LOCATOR_HOLE_PRINTED_LIMITS_MM = (min(_LOCATOR_PRINTED), max(_LOCATOR_PRINTED))
PLATE_TAP_SPEC = HoleSpec("tapped", "#8-32")
# The tap mouths take the title block's ordinary edge break (.010 chamfer):
# no band is tightened to protect the thread (fan-out screen, gating); the
# plate screw still engages 1.5D (transgear_hanger_joints).
PLATE_TAP_ENTRY_BREAK_MAX_MM = edge_break_chamfer_mm(unit=UNIT)
PLATE_TAP_EXIT_BREAK_MAX_MM = edge_break_chamfer_mm(unit=UNIT)
TAP_EDGE_BREAK_ANGLE_DEG = 90.0
PLATE_TAP_MOUTH_DIA_MAX_MM = (
    blind_cut_dia_mm(PLATE_TAP_SPEC)
    + 2.0 * max(PLATE_TAP_ENTRY_BREAK_MAX_MM, PLATE_TAP_EXIT_BREAK_MAX_MM)
)
# Pay the ordinary angular row at its smallest half-angle, not nominal 45.
PLATE_TAP_ENTRY_LOSS_MAX_MM = PLATE_TAP_ENTRY_BREAK_MAX_MM / math.tan(
    math.radians((TAP_EDGE_BREAK_ANGLE_DEG - angular_band_deg(unit=UNIT)) / 2.0)
)
PLATE_TAP_EXIT_LOSS_MAX_MM = PLATE_TAP_EXIT_BREAK_MAX_MM / math.tan(
    math.radians((TAP_EDGE_BREAK_ANGLE_DEG - angular_band_deg(unit=UNIT)) / 2.0)
)
# ASME B1.1 #8-32 UNC-2B pitch limits; Thread Check standard-inch table p54.
PLATE_TAP_PITCH_DIA_LIMITS_MM = tuple(value * 25.4 for value in (0.1437, 0.1475))

# --- Latch pin: reamed press hole along -X into the square end, flat floor --
PIN_HOLE_DIA = 3.175  # .125, the 1/8 dowel's nominal
# REAM .125 -.0005/-.0010 (#290, owned .1240 reamer): the blind press for the
# 98381A474 dowel (+.0001/+.0003 over nominal) holds at both limits (R9-12).
PIN_HOLE_DIA_BAND = (-0.0127, -0.0254)
# The dowel is pressed to the hole's flat floor (R9-12, the MHA-DT-11 / MHA-DT-VN-67
# precedent), so the depth sets the pin's proud length: 22.225 - 8.50 = 13.725.
# R9-50: 8.50 (was 6.05 for the 3/4 pin) keeps the full diameter past the
# latch hook's far face with the flap's bend and the pin's length grade.
# #290: it keeps 8.50 (the MHA-PD-VN-58 pin's proud length is fitted to it)
# and prints .33.
PIN_HOLE_DEPTH = 8.50
PIN_HOLE_DEPTH_PLACES = 2
# The hanger joints judge the pin's full-diameter grip at the shallowest
# hole, and the latch hook's grip on the pin over the proud range, both at
# the printed .XX reach.
PIN_HOLE_DEPTH_BAND = printed_reach_mm(PIN_HOLE_DEPTH, PIN_HOLE_DEPTH_PLACES)
PIN_HOLE_Z = THICKNESS / 2.0  # mid-thickness, on y = 0
# The latch pin's axis in the machine frame; the hook's hole is drilled on it.
PIN_MACHINE_Z = FRONT_FACE_MACHINE_Z + PIN_HOLE_Z  # -120.43025

# The end-face latch hole's height is an ordinary .XXX row: the title block
# governs it, with no tightened band (coordinator ruling (a), #2019).  It
# prints .156 for the 5/32 model.
LATCH_PIN_HEIGHT_PLACES = 3
LATCH_PIN_HEIGHT_BAND = printed_reach_mm(PIN_HOLE_Z, LATCH_PIN_HEIGHT_PLACES)
REDUCER_POSITION_DIAMETER = reducer_position_diameter_mm()
REDUCER_POSITION_RADIUS = REDUCER_POSITION_DIAMETER / 2.0
# The plate taps are spotted and drilled through MHA-PD-19's screw holes at
# assembly, the plate doweled on (MHA-PD-00): PD-19's holes are the master
# for this joint, screws clamp only (the dowels locate), and the arm sheet
# prints no frame on them (fan-out Q2-A, L1; delegated ruling 2026-11-07
# (Main), no precedent; owner review #2144). Plain ⌖ zones without the
# projected modifier (rule 26) could not keep the screw entering PD-19's
# hole above Ø.002. The tap's location on the arm is the plate hole's
# through the dowels; this radius (Ø.040) bounds it for the arm's walls,
# which keep over 6 mm to spare (transgear_hanger_joints checks the chain,
# PD-19's screw-hole zone included, against it).
PLATE_TAP_LOCATION_RADIUS_MM = 0.508
# The dowel's full-diameter grip runs the through ream between its two
# mouth breaks, on the thinnest stock (as the plate's slip holes).
LOCATOR_FULL_CYLINDER_SPAN_MIN_MM = (
    THICKNESS - THICKNESS_BAND - 2.0 * LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM
)
LOCATOR_MOUTH_POSITION_RADIUS_MM = REDUCER_POSITION_RADIUS * (
    1.0 + 2.0 * LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM
    / LOCATOR_FULL_CYLINDER_SPAN_MIN_MM
)
WALL_TARGET = WALL_TARGET_MM
# The inch title block's edge-break row: either permitted form, the round or
# the chamfer, takes its full size off a wall at the outline's face edges.
OUTLINE_EDGE_BREAK_MAX_MM = max(
    edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT)
)
# The locating holes are match-drilled through after the outline is milled,
# in another setup: their walls to the outline pay 0.3 deg of drill run-off
# over the full depth, the thickest stock (the brief's run-off rule; #2000
# holds the method).
DRILL_RUN_OFF_DEG = 0.3
LOCATOR_RUN_OFF_MM = (THICKNESS + THICKNESS_BAND) * math.tan(math.radians(DRILL_RUN_OFF_DEG))
# The tip station's printed reach (R9-23; see TIP_STATION).
TIP_STATION_BAND = printed_reach_mm(TIP_STATION, TIP_STATION_PLACES)

def _tap_major(spec: HoleSpec) -> float:
    return THREAD_MAJOR_MM[spec.size]


# Walls: nominal and worst at the printed bands (contract §8).  The hull
# radii and the tip station take their printed outline reach. The reducer
# bores/taps use the drawn circular position radius, not a coordinate box;
# tap majors carry a 0.025 radial allowance for the tap's oversize.
_TAP_OVERSIZE_R = 0.025
WALLS: dict[str, tuple[float, float]] = {
    "pivot bore to end round": (
        PIVOT_END_R - PIVOT_BORE_DIA / 2.0,
        PIVOT_END_R - PIVOT_END_R_BAND - PIVOT_BORE_FULL_LIMITS[1] / 2.0,
    ),
    "pivot bore to spot face": (
        (SPOT_FACE_DIA - PIVOT_BORE_DIA) / 2.0,
        # conservative, as the contract: the counterbore's growth is charged
        # against the ring too (it only widens it in fact)
        (SPOT_FACE_DIA - SPOT_FACE_DIA_GROWTH - PIVOT_BORE_FULL_LIMITS[1]) / 2.0,
    ),
    "spot-face floor": (
        SPOT_FACE_FLOOR_FROM_FRONT,
        SPOT_FACE_FLOOR_FROM_FRONT - SPOT_FACE_FLOOR_BAND,
    ),
    "spot face to end round": (
        PIVOT_END_R - SPOT_FACE_DIA / 2.0,
        PIVOT_END_R - PIVOT_END_R_BAND - (SPOT_FACE_DIA + SPOT_FACE_DIA_GROWTH) / 2.0,
    ),
    "pin bore to edges": (
        edge_half_width(PIN_STATION) - PIN_BORE_DIA / 2.0,
        edge_half_width(PIN_STATION)
        - OUTLINE_BAND
        - REDUCER_POSITION_RADIUS
        - PIN_BORE_DIA_MAX / 2.0
        - PIN_MOUTH_CHAMFER_LIMITS[1]
        - OUTLINE_EDGE_BREAK_MAX_MM,
    ),
    "plate taps to edges": (
        edge_half_width(PLATE_TAP_STATIONS[1]) - _tap_major(PLATE_TAP_SPEC) / 2.0,
        edge_half_width(PLATE_TAP_STATIONS[1])
        - OUTLINE_BAND
        - PLATE_TAP_LOCATION_RADIUS_MM
        - _tap_major(PLATE_TAP_SPEC) / 2.0
        - _TAP_OVERSIZE_R,
    ),
    # The hole's height is dimensioned from the FRONT face, so thin stock
    # takes its whole band off the rear ligament. Full budget: the drill's
    # run-off over the deepest hole, and both title-block breaks at the mouth
    # (the face edge's and the hole's).
    "pin hole to faces": (
        (THICKNESS - PIN_HOLE_DIA) / 2.0,
        (THICKNESS - PIN_HOLE_DIA - PIN_HOLE_DIA_BAND[0]) / 2.0
        - THICKNESS_BAND
        - LATCH_PIN_HEIGHT_BAND
        - (PIN_HOLE_DEPTH + PIN_HOLE_DEPTH_BAND) * math.tan(math.radians(DRILL_RUN_OFF_DEG))
        - 2.0 * OUTLINE_EDGE_BREAK_MAX_MM,
    ),
    "pin hole to end-face edges": (
        TIP_END_R - PIN_HOLE_DIA / 2.0,
        TIP_END_R
        - END_HALF_WIDTH_BAND
        - (PIN_HOLE_DIA + PIN_HOLE_DIA_BAND[0]) / 2.0
        - LATCH_PIN_HEIGHT_BAND,
    ),
    # The latch pin's hole, at its deepest on the shortest tip station, to
    # the pin bore's far side.
    "latch-pin hole floor to pin bore": (
        TIP_STATION - PIN_HOLE_DEPTH - PIN_STATION - PIN_BORE_DIA / 2.0,
        TIP_STATION
        - TIP_STATION_BAND
        - PIN_HOLE_DEPTH
        - PIN_HOLE_DEPTH_BAND
        - PIN_STATION
        - REDUCER_POSITION_RADIUS
        - PIN_BORE_DIA_MAX / 2.0,
    ),
}
# Each locating hole's wall to the arm's edge is thinnest at a face, where
# the hole's mouth break meets the outline's edge break; run-off is charged
# at the exit face.
for _index, (_x, _y) in enumerate(LOCATOR_SITES_MM, 1):
    _edge_air = PIVOT_END_R - _x * math.sin(EDGE_LEAN) - abs(_y) * math.cos(EDGE_LEAN)
    WALLS[f"locator {_index} to arm edge"] = (
        _edge_air - LOCATOR_HOLE_DIA_MM / 2.0,
        _edge_air - OUTLINE_BAND - LOCATOR_MOUTH_POSITION_RADIUS_MM
        - LOCATING_PIN.PRESS_HOLE_LIMITS_MM[1] / 2.0 - LOCATING_PIN.HOLE_MOUTH_BREAK_RADIAL_MAX_MM
        - OUTLINE_EDGE_BREAK_MAX_MM - LOCATOR_RUN_OFF_MM,
    )
    _tap_air = min(math.hypot(_x - station, _y) for station in PLATE_TAP_STATIONS)
    WALLS[f"locator {_index} to tap mouth"] = (
        _tap_air - (LOCATOR_HOLE_DIA_MM + PLATE_TAP_MOUTH_DIA_MAX_MM) / 2.0,
        _tap_air - LOCATOR_MOUTH_POSITION_RADIUS_MM - PLATE_TAP_LOCATION_RADIUS_MM
        - (LOCATING_PIN.PRESS_HOLE_LIMITS_MM[1] + PLATE_TAP_MOUTH_DIA_MAX_MM) / 2.0
        - LOCATING_PIN.HOLE_MOUTH_BREAK_RADIAL_MAX_MM - LOCATOR_RUN_OFF_MM,
    )
# The latch pin's hole-to-face ligament is about 1.67 (.065) at full budget
# (the .XXX height reach included), under the .080 target but over the .060
# floor. #2019 tracks the owner's next stock size up (owner ruling
# 2026-10-27, #1379); until then it is held at the floor.
LATCH_PIN_WALL_FLOOR = WALL_FLOOR_MM
WALL_FLOORS = {"pin hole to faces": LATCH_PIN_WALL_FLOOR}
for _name, (_nominal, _worst) in WALLS.items():
    _floor = WALL_FLOORS.get(_name, WALL_TARGET)
    if _worst < _floor:
        raise AssertionError(f"arm {_name} wall {_worst:.3f} < {_floor}")

def polygon_area_moments(points: tuple[tuple[float, float], ...]) -> tuple[float, float, float]:
    """Exact signed-polygon area and first moments, returned with positive area."""
    area = mx = my = 0.0
    for first, last in zip(points, points[1:] + points[:1], strict=True):
        cross = first[0] * last[1] - last[0] * first[1]
        area += cross / 2.0
        mx += (first[0] + last[0]) * cross / 6.0
        my += (first[1] + last[1]) * cross / 6.0
    sign = 1.0 if area > 0.0 else -1.0
    return sign * area, sign * mx, sign * my


def sector_area_moments(radius: float, start: float, end: float) -> tuple[float, float, float]:
    """Exact circular-sector area and first moments about the circle centre."""
    return (
        radius**2 * (end - start) / 2.0,
        radius**3 * (math.sin(end) - math.sin(start)) / 3.0,
        radius**3 * (math.cos(start) - math.cos(end)) / 3.0,
    )


def nominal_material_properties(*, density_kg_m3: float = 7870.0) -> dict[str, object]:
    """Analytic native-recipe nominal volume, mass and full 3D local CG.

    Density is an explicit engineering material input, not a stock-lot
    certificate. The paired pivot is the nominal reference realization;
    a physical force counterexample must supply its actual accepted bore.
    """
    return material_properties(PIVOT_BORE_DIA, density_kg_m3=density_kg_m3)


def material_properties(pivot_bore_mm: float, *, density_kg_m3: float = 7870.0) -> dict[str, object]:
    """Material properties of an accepted pivot-bore realization of the arm."""
    if (not math.isfinite(pivot_bore_mm)
            or not PIVOT_BORE_FULL_LIMITS[0] <= pivot_bore_mm <= PIVOT_BORE_FULL_LIMITS[1]
            or not math.isfinite(density_kg_m3) or density_kg_m3 <= 0.0):
        raise ValueError("arm material properties require an accepted bore and positive density")
    polygon = polygon_area_moments((
        (0.0, 0.0), (PIVOT_TANGENT_X, -PIVOT_TANGENT_Y),
        (TIP_STATION, -END_HALF_WIDTH), (TIP_STATION, END_HALF_WIDTH),
        (PIVOT_TANGENT_X, PIVOT_TANGENT_Y),
    ))
    sector = sector_area_moments(
        PIVOT_END_R, math.pi / 2.0 - EDGE_LEAN, 3.0 * math.pi / 2.0 + EDGE_LEAN,
    )
    area, ax, ay = (polygon[i] + sector[i] for i in range(3))
    volume = area * THICKNESS
    moments = [ax * THICKNESS, ay * THICKNESS, volume * THICKNESS / 2.0]

    def remove(amount: float, x: float, y: float, z: float) -> None:
        nonlocal volume
        volume -= amount
        for axis, coordinate in enumerate((x, y, z)):
            moments[axis] -= amount * coordinate

    bore_radius = pivot_bore_mm / 2.0
    remove(math.pi * bore_radius**2 * THICKNESS, 0.0, 0.0, THICKNESS / 2.0)
    remove(math.pi * (PIN_BORE_DIA / 2.0)**2 * THICKNESS, PIN_STATION, 0.0, THICKNESS / 2.0)
    pin_radius, pin_leg = PIN_BORE_DIA / 2.0, PIN_MOUTH_CHAMFER
    pin_mouth_depth = (
        pin_leg * (4.0 * pin_radius + pin_leg) / (12.0 * (pin_radius + pin_leg / 3.0))
    )
    remove(
        math.pi * pin_leg**2 * (pin_radius + pin_leg / 3.0),
        PIN_STATION,
        0.0,
        THICKNESS - pin_mouth_depth,
    )
    drill_radius = blind_cut_dia_mm(PLATE_TAP_SPEC) / 2.0
    leg = PLATE_TAP_ENTRY_BREAK_MAX_MM
    tap_volume = math.pi * drill_radius**2 * THICKNESS
    rear_volume = math.pi * leg**2 * (drill_radius + leg / 3.0)
    front_leg = PLATE_TAP_EXIT_BREAK_MAX_MM
    front_volume = math.pi * front_leg**2 * (drill_radius + front_leg / 3.0)
    rear_z = THICKNESS - leg * (4.0 * drill_radius + leg) / (12.0 * (drill_radius + leg / 3.0))
    front_z = front_leg * (4.0 * drill_radius + front_leg) / (12.0 * (drill_radius + front_leg / 3.0))
    for station in PLATE_TAP_STATIONS:
        remove(tap_volume, station, 0.0, THICKNESS / 2.0)
        remove(rear_volume, station, 0.0, rear_z)
        remove(front_volume, station, 0.0, front_z)
    remove(
        math.pi * ((SPOT_FACE_DIA / 2.0)**2 - bore_radius**2) * SPOT_FACE_DEPTH,
        0.0, 0.0, (SPOT_FACE_FLOOR_FROM_FRONT + THICKNESS) / 2.0,
    )
    remove(
        math.pi * (PIN_HOLE_DIA / 2.0)**2 * PIN_HOLE_DEPTH,
        TIP_STATION - PIN_HOLE_DEPTH / 2.0, 0.0, PIN_HOLE_Z,
    )
    for x, y in LOCATOR_SITES_MM:
        remove(
            math.pi * (LOCATOR_HOLE_DIA_MM / 2.0)**2 * THICKNESS,
            x, y, THICKNESS / 2.0,
        )
    return {
        "volume_mm3": volume,
        "mass_kg": volume * density_kg_m3 * 1e-9,
        "centre_of_mass_local_mm": tuple(moment / volume for moment in moments),
        "density_kg_m3": density_kg_m3,
    }
