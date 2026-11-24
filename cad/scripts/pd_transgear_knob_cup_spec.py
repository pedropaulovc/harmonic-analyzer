r"""MHA-PD-16 transgear-knob-cup: the brass cup on the knob shaft's rear journal end.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  A blind turned cup (owner ruling 2026-11-20 (Pedro), #2425): its
flat-bottomed front pilot, plunged .250 with a 1/4 end mill, takes the knob
shaft's (MHA-PD-08) journal end, bonded on it with LOCTITE 641; its web
carries the MHA-PD-VN-71 #2-56 fillister on the axis, the head sunk in a rear pocket,
into the journal's rear tap.  Its front face runs END_FLOAT behind the
MHA-PD-28 bush's rear face: the cup is the REAR stop of the knob's end float
(the MHA-PD-15 thrust ring is the forward one).  The float is set at
fit-up: the cup is turned with its pilot PILOT_DEPTH deep, and at
MHA-PD-00 its front face is faced until the pilot depth is the journal's
measured stand-out behind the bush less the float (FACING_REMOVAL), so the
journal end seats on the pilot's floor.  The cup's O.D. is the bush's rear
stub's, the Ø the cup's front face meets (owner: "pd-16 diameter should also
be reduced to match new knob bush").

Decimal inch (#290): the pilot is .250 REF, a bonded seat made to fit the
MHA-PD-08 journal (drawing-guidelines rule 4, form 2): sheet note 2 prints
its diametral clearance on the journal (PILOT_CLEARANCE), the requirement,
which stays inside LOCTITE 641's fill.

Part frame: axis local +Y through the origin (``Axis1``); the front face
(the running face, as turned) is the Top Plane, y = 0; the pilot's floor
(the web's front face) is y = PILOT_DEPTH; the pocket's floor (the web's
rear face, the screw's seat) is y = LENGTH - CBORE_DEPTH; the rear face is
y = LENGTH.
"""

from __future__ import annotations

import math

import _config
import pd_transgear_knob_bush_geometry as BUSH
import pd_vn_transgear_knob_cup_screw_spec as SCREW
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_rack_pinion_spec import inch_ceil_mm, inch_floor_mm, inch_text
from pd_transgear_knob_shaft_spec import (
    EDGE_BREAK_MAX as SHAFT_EDGE_BREAK_MAX,
    END_FLOAT,
    END_FLOAT_SET_TOL,
    JOURNAL_DIA,
    JOURNAL_DIA_BAND,
    JOURNAL_STANDOUT,
    JOURNAL_STANDOUT_BAND,
    REAR_CHAMFER_MIN as SHAFT_REAR_CHAMFER_MIN,
    REAR_TAP_FULL_THREAD_MIN,
)

MM_PER_IN = 25.4
# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/pd-transgear-knob-cup", _config.parts("pd-transgear-knob-cup"))

# --- Turned sizes ---------------------------------------------------------------
# The bush's Ø.4375 rear stub at the .XX row: routine, nothing fits on it.
OD = 11.176  # .44
LENGTH = 9.144  # .36 as turned (SUPPLY)
# The pilot: a blind bore cannot be reamed to a flat floor (the reamer's
# lead and the drill's cone), and the journal end must seat flat on the web
# for the fitted float, so after a B pilot drill the owned 1/4 HSS 2-flute
# centre-cutting square end mill (tools-cutting endmill-hss-2fl-1-4,
# McMaster 3051A51) is plunged from the tailstock.  The pilot is a bonded
# seat made to fit its mate (drawing-guidelines.md rule 4, form 2; owner,
# 2026-11-23:
# "why do we need single micron level tolerance x class plug gauges for a
# hobby machining project"): its size prints REF with no limits and
# PILOT_CLEARANCE, the diametral clearance on the MHA-PD-08 journal, is the
# printed requirement (machinist review 2026-11-24, two runs: the printed
# +.004/0, with no drill named, read as a tight band whose only reason was
# a fit name).  It was the end mill's own +.001/0, gauged by a Class X plug
# pair.  What fails if the clearance is greater: the bond gap on the
# journal passes LOCTITE 641's fill (LOCTITE_641_GAP_MAX below); if it is
# less the journal does not enter with the compound on it.  BORE_BAND is
# the ANALYSIS band, what the 1/4 end mill is taken to cut (the .250 pin of
# the .001-step set enters, the .253 pin does not), never a printed limit;
# the ring round the pilot keeps the wall target (PILOT_WALL_WORST).
BORE_DIA = 6.35  # .250 REF
BORE_BAND = (0.0762, 0.0)  # analysis (upper, lower) deviations: +.003/0
PILOT_CLEARANCE = (0.0127, 0.127)  # printed (least, greatest) diametral: .0005-.005
PILOT_DEPTH = 3.8608  # .152 as turned (SUPPLY)
# The web's #33 drill and the rear pocket the screw head sinks in, cut flat
# with a 3/16 end mill after the drill.  The pocket only clears the head, so
# its Ø prints .XX (rule 3; machinist review r10: ".188" carried a third
# place with no band and no function); its depth keeps .XXX, which holds the
# web at the .080 target.
CLEAR_HOLE_DIA = 2.8702  # #33, .113
# Modelled on the printed .01 grid (the 3/16 cutter's .1875 lies in its band).
CBORE_DIA = 4.826  # .19
CBORE_DEPTH = 2.7432  # .108

# Places each printed dimension carries (drawing-guidelines.md rule 3): the
# O.D. and the length are routine at .XX; the pilot prints .XXX under its
# end-milled band; its depth, the drill and the pocket's depth print .XXX,
# the pocket's Ø .XX.
OD_PLACES = 2
LENGTH_PLACES = 2
BORE_PLACES = 3
PILOT_DEPTH_PLACES = 3
HOLE_PLACES = 3
CBORE_DIA_PLACES = 2
CBORE_DEPTH_PLACES = 3

if not math.isclose(
    OD, math.floor(BUSH.STUB_DIA / MM_PER_IN * 10**OD_PLACES + 0.5) / 10**OD_PLACES
    * MM_PER_IN,
):
    raise AssertionError("MHA-PD-16's O.D. no longer prints the MHA-PD-28 stub's .44")

WALL_FLOOR = WALL_TARGET_MM

_OD_LO, _ = printed_deviations(OD, OD_PLACES, unit=UNIT)
_LENGTH_LO, _LENGTH_HI = printed_deviations(LENGTH, LENGTH_PLACES, unit=UNIT)
_PILOT_LO, _PILOT_HI = printed_deviations(PILOT_DEPTH, PILOT_DEPTH_PLACES, unit=UNIT)
_CBORE_DIA_LO, _CBORE_DIA_HI = printed_deviations(CBORE_DIA, CBORE_DIA_PLACES, unit=UNIT)
_CBORE_DEPTH_LO, _CBORE_DEPTH_HI = printed_deviations(
    CBORE_DEPTH, CBORE_DEPTH_PLACES, unit=UNIT
)
# DRILLED HOLES: the drill's own size, never under.
HOLE_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)  # (upper, lower) deviations
OD_MIN = OD + _OD_LO
LENGTH_MIN = LENGTH + _LENGTH_LO
LENGTH_MAX = LENGTH + _LENGTH_HI
PILOT_DEPTH_MIN = PILOT_DEPTH + _PILOT_LO
PILOT_DEPTH_MAX = PILOT_DEPTH + _PILOT_HI
CBORE_DIA_MIN = CBORE_DIA + _CBORE_DIA_LO
CBORE_DIA_MAX = CBORE_DIA + _CBORE_DIA_HI
CBORE_DEPTH_MIN = CBORE_DEPTH + _CBORE_DEPTH_LO
CBORE_DEPTH_MAX = CBORE_DEPTH + _CBORE_DEPTH_HI
CLEAR_HOLE_MIN = CLEAR_HOLE_DIA + min(HOLE_BAND)
CLEAR_HOLE_MAX = CLEAR_HOLE_DIA + max(HOLE_BAND)
BORE_MAX = BORE_DIA + max(BORE_BAND)

# --- The bonded pilot: the journal end, LOCTITE 641 -----------------------------
# drawing-guidelines.md rule 23: a bonded fit is a fit; the sheet prints the
# pilot's size REF, names MHA-PD-08 and states the diametral clearance,
# PILOT_CLEARANCE, which must lie inside the grade's gap fill.  The journal
# is itself made to fit: turned to the MHA-PD-28 bush's reamed bore, REF on
# its own sheet, so its size follows that bore.  The journal this pilot can
# meet is therefore the bush bore's analysis band less the running
# clearance the shaft's model gives the pair (Codjiflo on #3493: the range
# rested on the journal's own g6 band, which a journal fitted to a bore at
# the top of its band leaves, .2492 in a .2495 bore).  The traveler accepts
# the pilot with the journal itself and two pins of the
# .001-step set.  Henkel's LOCTITE 641 product page
# (https://next.henkel-adhesives.com/us/en/products/industrial-adhesives/central-pdp.html/loctite-641/BP000000153498.html,
# read 2026-11-20) gives "Gap fill: 0.15 mm"; its TDS (May 2004,
# https://datasheets.tdx.henkel.com/LOCTITE-641-en_GL.pdf) charts full cure
# on steel pins and collars at 0.05-0.2 mm gaps.  641 is the removable grade
# (rule 23: "641 where the part must come out").
LOCTITE_641_GAP_MAX = 0.15
_JOURNAL_RUNNING_CLEARANCE = (
    min(BUSH.BORE_DIA_LIMITS) - max(JOURNAL_DIA_BAND),
    max(BUSH.BORE_DIA_LIMITS) - min(JOURNAL_DIA_BAND),
)
# (least, greatest) journal as fitted to the bush's bore: .2480-.2493.
JOURNAL_FITTED = (
    BUSH.BORE_DIA + min(BUSH.BORE_DIA_LIMITS) - max(_JOURNAL_RUNNING_CLEARANCE),
    BUSH.BORE_DIA + max(BUSH.BORE_DIA_LIMITS) - min(_JOURNAL_RUNNING_CLEARANCE),
)
BORE_JOURNAL_CLEARANCE = (
    BORE_DIA + min(BORE_BAND) - max(JOURNAL_FITTED),
    BORE_MAX - min(JOURNAL_FITTED),
)
if min(BORE_JOURNAL_CLEARANCE) <= 0.0:
    raise AssertionError("MHA-PD-16's pilot bore binds on the journal")
if max(PILOT_CLEARANCE) > LOCTITE_641_GAP_MAX:
    raise AssertionError("MHA-PD-16's pilot clearance passes LOCTITE 641's gap fill")
if not (
    min(PILOT_CLEARANCE) <= min(BORE_JOURNAL_CLEARANCE) + 1e-9
    and max(BORE_JOURNAL_CLEARANCE) <= max(PILOT_CLEARANCE) + 1e-9
):
    raise AssertionError("MHA-PD-16's modelled pilot leaves its printed clearance")
# The pilot note's diametral clearance, the printed requirement: its least
# at four places (half a thousandth), its greatest at three.
BORE_CLEARANCE_TEXT = (
    f"{inch_text(min(PILOT_CLEARANCE), 4)}-{inch_text(max(PILOT_CLEARANCE), 3)}"
)
# The pilot's Ø prints in parentheses (REF): the fit is the requirement.
REFERENCE_DIMENSIONS: frozenset[str] = frozenset({"BoreDia"})

# --- The float, set at fit-up (drawing-guidelines.md rule 19) ------------------
# The journal end seats on the pilot's floor, so the fitted pilot depth is
# the journal's stand-out behind the bush's rear face less the float.
PILOT_DEPTH_FITTED = JOURNAL_STANDOUT - END_FLOAT  # .132
if not math.isclose(PILOT_DEPTH_FITTED, 3.3528, abs_tol=1e-9):
    raise AssertionError("MHA-PD-16's fitted pilot is no longer .132")
# What the fitter faces off the front to reach the nominal float, over the
# supplied pilot's band and the stand-out's whole stack: never negative, so
# no cup is ever too short to set.
FACING_REMOVAL = (
    PILOT_DEPTH_MIN - (JOURNAL_STANDOUT + JOURNAL_STANDOUT_BAND) + END_FLOAT,
    PILOT_DEPTH_MAX - (JOURNAL_STANDOUT - JOURNAL_STANDOUT_BAND) + END_FLOAT,
)
if min(FACING_REMOVAL) < -1e-9:
    raise AssertionError("MHA-PD-16's supplied pilot is shallower than the float needs")
# The pilot depth after facing, over the stand-out's stack and the float's
# acceptance: the sheet's FITTED range, rounded inward onto the .XXX grid.
PILOT_DEPTH_FITTED_RANGE = (
    JOURNAL_STANDOUT - JOURNAL_STANDOUT_BAND - (END_FLOAT + END_FLOAT_SET_TOL),
    JOURNAL_STANDOUT + JOURNAL_STANDOUT_BAND - (END_FLOAT - END_FLOAT_SET_TOL),
)
PILOT_DEPTH_FITTED_TEXT = (
    f"{inch_text(inch_ceil_mm(PILOT_DEPTH_FITTED_RANGE[0], 3), 3)}-"
    f"{inch_text(inch_floor_mm(PILOT_DEPTH_FITTED_RANGE[1], 3), 3)}"
)
# The shortest fitted pilot still centres the cup on the journal end: the
# design record's .4D floor (no repository floor exists for a bonded pilot).
PILOT_DEPTH_FITTED_FLOOR = 0.4 * JOURNAL_DIA
if PILOT_DEPTH_FITTED_RANGE[0] < PILOT_DEPTH_FITTED_FLOOR:
    raise AssertionError("MHA-PD-16's shortest fitted pilot no longer centres the cup")

# --- Web and walls at the printed worst case (drawing-guidelines.md rule 17) ----
# The web: the length less the pilot (from the front chucking's face) and the
# pocket (from the rear's).  Facing the front at fit-up leaves it alone.
WEB = LENGTH - PILOT_DEPTH - CBORE_DEPTH
if not math.isclose(WEB, 2.54, abs_tol=1e-9):
    raise AssertionError("MHA-PD-16's web is no longer .100")
WEB_MIN = LENGTH_MIN - PILOT_DEPTH_MAX - CBORE_DEPTH_MAX
WEB_MAX = LENGTH_MAX - PILOT_DEPTH_MIN - CBORE_DEPTH_MIN
# The ring round the pilot and round the pocket.
PILOT_WALL_WORST = (OD_MIN - BORE_MAX) / 2.0
CBORE_WALL_WORST = (OD_MIN - CBORE_DIA_MAX) / 2.0
for _name, _wall in (
    ("web", WEB_MIN),
    ("ring round the pilot", PILOT_WALL_WORST),
    ("ring round the head pocket", CBORE_WALL_WORST),
):
    if _wall < WALL_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-PD-16 {_name} {_wall:.3f} at the printed worst case is under "
            f"the {WALL_FLOOR} floor"
        )

# --- The MHA-PD-VN-71 screw in the web ----------------------------------------
# The #33 hole clears the screw's whole under-head fillet envelope (Ø1.3D,
# ASME B18.6.3), so the head seats on the web, not on the fillet.
HOLE_FILLET_CLEARANCE_MIN = CLEAR_HOLE_MIN - SCREW.UNDER_HEAD_FILLET_ENVELOPE_DIA
if HOLE_FILLET_CLEARANCE_MIN <= 0.0:
    raise AssertionError("MHA-PD-16's #33 hole rides MHA-PD-VN-71's under-head fillet")
# Informational: the head's bearing land round the largest hole.
HEAD_BEARING_LAND = (SCREW.HEAD_DIA - CLEAR_HOLE_MAX) / 2.0
# The head drops into the smallest pocket with room all round, and its top
# stays below the rear face in the shallowest pocket.
HEAD_POCKET_CLEARANCE_MIN = (CBORE_DIA_MIN - SCREW.HEAD_DIA) / 2.0
if HEAD_POCKET_CLEARANCE_MIN <= 0.0:
    raise AssertionError("MHA-PD-VN-71's head does not enter MHA-PD-16's pocket")
HEAD_BELOW_REAR_FACE_MIN = CBORE_DEPTH_MIN - SCREW.HEAD_H
if HEAD_BELOW_REAR_FACE_MIN < 0.0:
    raise AssertionError("MHA-PD-VN-71's head stands out of MHA-PD-16's rear face")
# Rule 18: full-thread engagement in the journal's rear tap at the worst
# case: the shortest screw through the thickest web, less the tap mouth's
# first thread and title-block break, and the screw's point chamfer.
SCREW_ENGAGEMENT_MIN = (
    SCREW.LENGTH_MIN
    - WEB_MAX
    - (SCREW.PITCH + SHAFT_EDGE_BREAK_MAX)
    - SCREW.POINT_CHAMFER_LENGTH_MAX
)
SCREW_ENGAGEMENT_MIN_D = SCREW_ENGAGEMENT_MIN / SCREW.MAJOR_DIA
if SCREW_ENGAGEMENT_MIN_D < 1.5:
    raise AssertionError(
        f"MHA-PD-VN-71 engages {SCREW_ENGAGEMENT_MIN_D:.2f}D in MHA-PD-08, under 1.5D"
    )
# The longest screw through the thinnest web ends short of the tap's full
# thread, so it never bottoms.
SCREW_REACH_MAX = SCREW.LENGTH - WEB_MIN
SCREW_TIP_SHORT_OF_FULL_THREAD_MIN = REAR_TAP_FULL_THREAD_MIN - SCREW_REACH_MAX
if SCREW_TIP_SHORT_OF_FULL_THREAD_MIN <= 0.0:
    raise AssertionError("MHA-PD-VN-71 reaches past MHA-PD-08's full thread")

# --- Inside corners that matter (drawing-guidelines.md rule 16) ------------------
# The title block lets an inside corner run to R.040; two here must not.
# Each is a tangent arc in the turned profile sketch at its largest
# acceptable radius (a sketch dimension imports into the section; a fillet
# feature's does not), printed as the single limit "R.xxx MAX" (MHA-PD-28's
# shoulder root pattern).
# The pilot's floor corner: the journal's rear face must bear on the web, so
# its .015 X 45° rear chamfer, at its least leg, clears every point of the
# corner (a 45° chamfer of leg c clears a root fillet of radius r once c >= r).
PILOT_FLOOR_R_MAX = 0.127  # .005 MAX
# The pocket's floor corner: the screw head's bearing face must land flat
# on the web inside the corner, in the smallest pocket.
POCKET_FLOOR_R_MAX = 0.254  # .010 MAX
CORNER_R_PLACES = 3
CORNER_TOL_TYPE = 0  # swTolType_e.swTolNONE: the " MAX" suffix carries the limit
CORNER_SUFFIX = " MAX"
if SHAFT_REAR_CHAMFER_MIN < PILOT_FLOOR_R_MAX - 1e-9:
    raise AssertionError(
        "MHA-PD-08's least rear chamfer rides MHA-PD-16's pilot floor corner"
    )
HEAD_CORNER_CLEARANCE_MIN = (
    CBORE_DIA_MIN / 2.0 - POCKET_FLOOR_R_MAX - SCREW.HEAD_DIA / 2.0
)
if HEAD_CORNER_CLEARANCE_MIN <= 0.0:
    raise AssertionError("MHA-PD-VN-71's head rides MHA-PD-16's pocket floor corner")

# The front face is the running face on the bush's rear face: MACHINED, on
# the exact native face the part build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "front_face", MACHINED_UM, PlanarFace((0.0, -1.0, 0.0), 0.0), display_unit=UNIT,
    ),
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the
# guidelines`).  The turned profile carries the O.D., the length, the pilot
# and the pocket, and its two floor arcs their radii, so they print on the
# axial section (rule 11); the web's drill is its own cut, sized on the face
# view where it shows round.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CupProfile": {
        "CupDia", "CupLength", "BoreDia", "PilotDepth", "CboreDia", "CboreDepth",
        "PilotFloorR", "PocketFloorR",
    },
    "WebHole": {"HoleDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CupProfile": {
        "CupDia": OD_PLACES,
        "CupLength": LENGTH_PLACES,
        "BoreDia": BORE_PLACES,
        "PilotDepth": PILOT_DEPTH_PLACES,
        "CboreDia": CBORE_DIA_PLACES,
        "CboreDepth": CBORE_DEPTH_PLACES,
        "PilotFloorR": CORNER_R_PLACES,
        "PocketFloorR": CORNER_R_PLACES,
    },
    "WebHole": {"HoleDia": HOLE_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
