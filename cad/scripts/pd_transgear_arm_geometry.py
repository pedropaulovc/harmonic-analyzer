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
from _gear_quality import reducer_position_diameter_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
    printed_deviations,
)
import pd_transgear_pivot_spacer_spec as SPACER
import _transgear_arm_plate_locating_interface as LOCATING_PIN

from _hole_spec import DRILL_POINT_H, THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm

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

# --- Stock: 3/8 x 1 precision-ground flat bar, faces as supplied -------------
# The arm is cut from Online Metals part 12095, 3/8 x 1 1018 precision ground
# (R9-6, R9-25; #2019: owner ruling 2026-10-27 (#1379), "pick stock next size
# up available at onlinemetals.com"; it was 5/16, McMaster 9517K466): its
# thickness is the stock's, ±0.001 in as supplied (Online Metals' tool-steel
# tolerance row for precision-ground 1018), not a machined band.  The sheet
# prints it as an untoleranced reference to the stock (#2147); walls, joints
# and the chain stack read the catalogue limits, THICKNESS_BAND.  The front
# face keeps its station on the spacer, so the arm grew rearward: its rear
# face (the MHA-PD-19 plate's seat and the MHA-PD-23 head's) stands 1.5875
# further back than on the 5/16 bar.
STOCK_SKU = "12095"
STOCK_THICKNESS_IN = Fraction(3, 8)
THICKNESS = float(STOCK_THICKNESS_IN) * MM_PER_IN  # 9.525
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

# --- Pivot at P: a drilled running clearance on the as-supplied shoulder ---
# Fit audit 2026-11-23 (pending owner confirmation; owner: "can the holes not
# be reamed in the first place"): a #9 drill at the title block's DRILLED
# HOLES row, where #2413's .1940 reamer and its GO / NO-GO pair stood.  The
# arm only swings a few degrees to throw the feed in and is held on the
# spacer by its spring; nothing reads a clearance window: the latch sets the
# arm's working position and the hanger stack pays the whole maximum
# clearance as float.  The traveler keeps one .194 set pin as a GO check
# against a wrong drill.


# The spot face seats the MHA-PD-VN-63 curved disc spring's OD rim (Ø10.744) under
# the MHA-PD-VN-57 head; the spring's float on the shoulder still clears its rim.
# Ø.500 (was .453; owner ruling 2026-11-20 (Pedro), #2424 option C: "B, C
# and D together in the #2019 stock-change"): one plunge of an owned 1/2
# end mill, where .453 had no cutter but a boring head.
SPOT_FACE_DIA = 12.7  # .50
# A clearance pocket at the title block's .XX (fit batch review r1: its
# +.004/0, the drilled-hole row's growth, was a band under the three-place
# row with no necessity answer).  Nothing reads it closer: at .49 the
# spring's rim keeps .027 radial clearance (transgear_hanger_joints.
# SPRING_RIM_CLEARANCE) and the head .089; at .51 the wall to the end
# round keeps .225.
SPOT_FACE_DIA_PLACES = 2
SPOT_FACE_DIA_BAND_MM = printed_band_mm(SPOT_FACE_DIA_PLACES, unit=UNIT)  # ±.01
SPOT_FACE_DIA_MIN = SPOT_FACE_DIA - SPOT_FACE_DIA_BAND_MM
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
# The seated arm's bore against the shoulder's axis, at the printed bands:
# the bore's general angular row to the front face, and the bonded spacer's
# rear face to the plane it seats in (SPACER.SEATED_FACE_TILT, one frame).
PIVOT_SEATED_AXIS_ANGLE_MAX = (
    math.radians(PIVOT_BORE_TO_FRONT_FACE_ANGLE_BAND_DEG) + SPACER.SEATED_FACE_TILT
)
PIVOT_AXIS_BINDING_SWEEP_MAX = PIVOT_BEARING_LENGTH_MAX * math.tan(PIVOT_SEATED_AXIS_ANGLE_MAX)
# The least clearance the shoulder needs to run free: the shared
# close-running minimum plus the sweep of a bore at the general angular row
# on the seated spacer.
if not 3.0 < PIVOT.SHOULDER_DIA <= 6.0:
    raise ValueError("the pivot running minimum requires the shared ISO 3-through-6 mm clearance class")
_PIVOT_CLOSE_RUNNING_MIN = measured_close_running_clearance_mm()[0]
PIVOT_RUNNING_CLEARANCE_MIN = _PIVOT_CLOSE_RUNNING_MIN + PIVOT_AXIS_BINDING_SWEEP_MAX
PIVOT_BORE_DRILL = "#9"
PIVOT_BORE_DIA = 4.9784  # .196, the drill's size
# ANALYSIS band, what the drill cuts (the DRILLED HOLES row); the sheet
# prints the drill and no band of its own.
PIVOT_BORE_DIA_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)  # (upper, lower)
PIVOT_BORE_FULL_LIMITS = (
    PIVOT_BORE_DIA + PIVOT_BORE_DIA_BAND[1],
    PIVOT_BORE_DIA + PIVOT_BORE_DIA_BAND[0],
)
PIVOT_BORE_DIAMETRAL_CLEARANCE = (
    round(PIVOT_BORE_FULL_LIMITS[0] - PIVOT.SHOULDER_DIA - max(PIVOT.SHOULDER_DIA_LIMITS), 6),
    round(PIVOT_BORE_FULL_LIMITS[1] - PIVOT.SHOULDER_DIA - min(PIVOT.SHOULDER_DIA_LIMITS), 6),
)  # .0085, .0135
if PIVOT_BORE_DIAMETRAL_CLEARANCE[0] < PIVOT_RUNNING_CLEARANCE_MIN:
    raise AssertionError("the MHA-PD-18 pivot drill binds the largest MHA-PD-VN-57 shoulder")
# The bonded spacer cures with its front face and the bought screw's
# shoulder end in one plane, so the shoulder's axis leans to the seat by the
# shoulder end's own out-of-square, which the catalogue does not state.  The
# least clearance leaves it this much, as an angle and across the smallest
# shoulder; MHA-PD-00's dry trial before the bond (the arm swings free on the
# seated screw and spacer) and its free-fall check after are what hold one
# screw inside it.
PIVOT_SHOULDER_END_ANGLE_ALLOWED = (
    math.atan(
        (PIVOT_BORE_DIAMETRAL_CLEARANCE[0] - _PIVOT_CLOSE_RUNNING_MIN)
        / PIVOT_BEARING_LENGTH_MAX
    )
    - PIVOT_SEATED_AXIS_ANGLE_MAX
)
PIVOT_SHOULDER_END_SQUARENESS_ALLOWED = (
    PIVOT.SHOULDER_DIA + min(PIVOT.SHOULDER_DIA_LIMITS)
) * math.tan(PIVOT_SHOULDER_END_ANGLE_ALLOWED)  # .0019


# --- Pin at S: REAM THROUGH, the bore the MHA-PD-23 pin is bonded in ---------
# The one-diameter MHA-PD-23 pin slips in from the rear until its head seats
# on the rear face and is bonded there (owner ruling 2026-11-24, fit audit
# question 4; it replaces the #2415 press), so the hole is reamed square
# through the ground faces.  The bond's gap is asserted in
# pd_transgear_arm_spec, which imports both: the pin spec imports this
# module.
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
# root clears it and the head lands on the face (Codjiflo, #2124). The sheet
# prints that one limit, `.006 MIN` (fit batch review r3: a two-sided ±.002
# band was over-specification, nothing on the sheet wanting its upper
# limit); the upper limit is the title block's chamfer break, which every
# edge takes.  ``pd_transgear_pin_spec`` checks the clearance against the
# pin's root.  The model value is the printed minimum (#2174: the build
# puts " MIN" on the mouth profile's native leg dimension, which section D-D
# imports); the traveler cuts .008.
PIN_MOUTH_CHAMFER = 0.1524  # .006 MIN
PIN_MOUTH_CHAMFER_PLACES = 3
PIN_MOUTH_CHAMFER_LIMITS = (
    PIN_MOUTH_CHAMFER,
    edge_break_chamfer_mm(unit=UNIT),
)  # .006/.010
# What the traveler cuts: midway between the limits, .008.
PIN_MOUTH_CHAMFER_AIM = round(sum(PIN_MOUTH_CHAMFER_LIMITS) / 2.0, 6)
# --- Plate taps: 2 x #8-32 THROUGH; ordinary entry/exit edge breaks ---------
PLATE_SCREW_PITCH = 15.0
PLATE_CENTRELINE_OFFSET = -3.375  # 1-1/4 in plate's centreline from its bore
PLATE_SCREW_MID_STATION = KNOB_BORE_STATION + PLATE_CENTRELINE_OFFSET
PLATE_TAP_STATIONS = (
    PLATE_SCREW_MID_STATION - PLATE_SCREW_PITCH / 2.0,
    PLATE_SCREW_MID_STATION + PLATE_SCREW_PITCH / 2.0,
)

# Matched locating dowels, independent of the mounting screws' clearance.
# 12.8 (was 13.1, and 13.7 before): owner ruling 2026-11-24, fit audit
# question 9 ("Arm-to-plate dowels: 1/8 dowels on two reamers of the set,
# holes .504 apart", approved as recommended; it reverses the 3/32 dowel of
# #290).  The dowels go from 3/32 to 1/8 so their holes are cut by
# the over/under reamer set's .1240 and .1260 members; at 13.1 the larger
# plate hole's full worst-case wall to the plate's edge falls to 1.91 under
# the 2.03 target (pd_transgear_arm_plate_geometry.WALLS), at 12.8 it keeps
# 2.06 and the arm's own edge wall 2.35 (WALLS below).  13.1 was owner
# ruling 2026-10-27 (#1379), option W1 under the full-budget wall rule
# (issuecomment-6443060097), for the 3/32 dowel.
LOCATOR_PAIR_BASELINE_MM = 12.8
LOCATOR_SITES_MM = (
    (PLATE_SCREW_MID_STATION, LOCATOR_PAIR_BASELINE_MM / 2.0),
    (PLATE_SCREW_MID_STATION, -LOCATOR_PAIR_BASELINE_MM / 2.0),
)
# The interface's .1240 set reamer.  The sheet prints the reamer's size and
# no band (the dowel that does not enter by hand is the gauge); the reamed
# limits are the ANALYSIS limits the walls and the press are judged at, what
# the reamer is modelled to cut.
LOCATOR_HOLE_DIA_MM = min(LOCATING_PIN.PRESS_HOLE_LIMITS_MM)  # .1240
LOCATOR_HOLE_PLACES = 4
LOCATOR_HOLE_REAMED_LIMITS_MM = tuple(LOCATING_PIN.PRESS_HOLE_LIMITS_MM)
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

# --- Latch pin: reamed press hole along -X into the square end, drill point -
# REAM .1240 (the over/under set's reamer), printed as the reamer's size
# with no band: the 98381A474 dowel (+.0001/+.0003 over 1/8) is the gauge,
# it does not enter by hand.  Permanent stop pin with no other fastener
# (owner 2026-10-27, #1379: "should never come out").  The band is the
# ANALYSIS band, what the reamer is modelled to cut (REAM_H7), for the walls
# and the press range (fit audit 2026-11-23, pending owner confirmation;
# was the same hole printed .1250 -.0005/-.0010).
PIN_HOLE_DIA = 3.1496  # .1240
PIN_HOLE_DIA_BAND = (0.0127, 0.0)
# Owner decision 2026-11-19 (#3124 item 3): drilled and reamed to a drill
# point, the full-diameter depth printed as a MIN; the dowel is pressed to
# its proud height at assembly (MHA-PD-00 DETAIL L), not onto a floor.  The
# model carries the MIN itself, .38: past the deepest insertion
# (pd_vn_transgear_latch_pin_spec.INSERTION_LIMITS, 9.373), so the pressed
# end never reaches the point (transgear_hanger_joints checks it).
PIN_HOLE_DEPTH = 0.38 * MM_PER_IN  # 9.652
PIN_HOLE_DEPTH_PLACES = 2
# The drill point: a 118-degree cone on the reamed diameter beyond the MIN.
PIN_HOLE_POINT_LENGTH = PIN_HOLE_DIA / 2.0 * DRILL_POINT_H  # 0.954
PIN_HOLE_Z = THICKNESS / 2.0  # mid-thickness, on y = 0
# The latch pin's axis in the machine frame; the hook's hole is drilled on it.
PIN_MACHINE_Z = FRONT_FACE_MACHINE_Z + PIN_HOLE_Z  # -119.6505

# The end-face latch hole's height is an ordinary title-block row with no
# tightened band (coordinator ruling (a), #2019).  It prints .19 for the
# 3/16 model: fit batch review r4 found the third place of .188 had no
# function on the sheet (rule 3), and the walls below hold at the .XX row.
LATCH_PIN_HEIGHT_PLACES = 2
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
WALL_TARGET = WALL_TARGET_MM
# The inch title block's edge-break row: either permitted form, the round or
# the chamfer, takes its full size off a wall at the outline's face edges.
OUTLINE_EDGE_BREAK_MAX_MM = max(
    edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT)
)
# The locating holes' mouths break at the title block's row, as the plate's
# do (pd_transgear_arm_plate_geometry.LOCATOR_MOUTH_BREAK_MAX_MM; fit batch
# review r1: the sheet's .002 MAX mouth break was a second reason with a
# dimension in it, and no stack needs it: the grip keeps .354, the punch
# air .103 and the wall to the arm's edge .084 at the title block's .010).
LOCATOR_MOUTH_BREAK_MAX_MM = OUTLINE_EDGE_BREAK_MAX_MM
# The dowel's full-diameter grip runs the through ream between its two
# mouth breaks, on the thinnest stock (as the plate's slip holes).
LOCATOR_FULL_CYLINDER_SPAN_MIN_MM = (
    THICKNESS - THICKNESS_BAND - 2.0 * LOCATOR_MOUTH_BREAK_MAX_MM
)
LOCATOR_MOUTH_POSITION_RADIUS_MM = REDUCER_POSITION_RADIUS * (
    1.0 + 2.0 * LOCATOR_MOUTH_BREAK_MAX_MM / LOCATOR_FULL_CYLINDER_SPAN_MIN_MM
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
        (SPOT_FACE_DIA_MIN - PIVOT_BORE_FULL_LIMITS[1]) / 2.0,
    ),
    "spot-face floor": (
        SPOT_FACE_FLOOR_FROM_FRONT,
        SPOT_FACE_FLOOR_FROM_FRONT - SPOT_FACE_FLOOR_BAND,
    ),
    "spot face to end round": (
        PIVOT_END_R - SPOT_FACE_DIA / 2.0,
        PIVOT_END_R - PIVOT_END_R_BAND - (SPOT_FACE_DIA + SPOT_FACE_DIA_BAND_MM) / 2.0,
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
    # run-off over the hole to its point at the MIN depth, and both
    # title-block breaks at the mouth (the face edge's and the hole's). A MIN
    # prints no upper depth: a deeper hole is the shop's choice and must
    # still hold the wall target (pd_transgear_arm_spec.PIN_HOLE_DEPTH_BAND).
    "pin hole to faces": (
        (THICKNESS - PIN_HOLE_DIA) / 2.0,
        (THICKNESS - PIN_HOLE_DIA - PIN_HOLE_DIA_BAND[0]) / 2.0
        - THICKNESS_BAND
        - LATCH_PIN_HEIGHT_BAND
        - (PIN_HOLE_DEPTH + PIN_HOLE_POINT_LENGTH) * math.tan(math.radians(DRILL_RUN_OFF_DEG))
        - 2.0 * OUTLINE_EDGE_BREAK_MAX_MM,
    ),
    "pin hole to end-face edges": (
        TIP_END_R - PIN_HOLE_DIA / 2.0,
        TIP_END_R
        - END_HALF_WIDTH_BAND
        - (PIN_HOLE_DIA + PIN_HOLE_DIA_BAND[0]) / 2.0
        - LATCH_PIN_HEIGHT_BAND,
    ),
    # The latch pin's hole, its point at the MIN depth on the shortest tip
    # station, to the pin bore's far side (about 49 mm of metal: no
    # practical overrun of the MIN reaches it).
    "latch-pin hole point to pin bore": (
        TIP_STATION - PIN_HOLE_DEPTH - PIN_HOLE_POINT_LENGTH - PIN_STATION - PIN_BORE_DIA / 2.0,
        TIP_STATION
        - TIP_STATION_BAND
        - PIN_HOLE_DEPTH
        - PIN_HOLE_POINT_LENGTH
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
        - LOCATING_PIN.PRESS_HOLE_LIMITS_MM[1] / 2.0 - LOCATOR_MOUTH_BREAK_MAX_MM
        - OUTLINE_EDGE_BREAK_MAX_MM - LOCATOR_RUN_OFF_MM,
    )
    _tap_air = min(math.hypot(_x - station, _y) for station in PLATE_TAP_STATIONS)
    WALLS[f"locator {_index} to tap mouth"] = (
        _tap_air - (LOCATOR_HOLE_DIA_MM + PLATE_TAP_MOUTH_DIA_MAX_MM) / 2.0,
        _tap_air - LOCATOR_MOUTH_POSITION_RADIUS_MM - PLATE_TAP_LOCATION_RADIUS_MM
        - (LOCATING_PIN.PRESS_HOLE_LIMITS_MM[1] + PLATE_TAP_MOUTH_DIA_MAX_MM) / 2.0
        - LOCATOR_MOUTH_BREAK_MAX_MM - LOCATOR_RUN_OFF_MM,
    )
# The latch pin's hole-to-face ligament holds the .080 target on the 3/8 bar
# (#2019; on the 5/16 bar it was the owner-accepted .065 shortfall, #1379).
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET:
        raise AssertionError(f"arm {_name} wall {_worst:.3f} < {WALL_TARGET}")

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
    # The drill point: a cone on the floor, its centroid a quarter of its
    # length from the base.
    remove(
        math.pi * (PIN_HOLE_DIA / 2.0)**2 * PIN_HOLE_POINT_LENGTH / 3.0,
        TIP_STATION - PIN_HOLE_DEPTH - PIN_HOLE_POINT_LENGTH / 4.0, 0.0, PIN_HOLE_Z,
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
