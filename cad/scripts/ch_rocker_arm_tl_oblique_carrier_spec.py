r"""Pure-data contract for the oblique-trammel jig's carrier plate (MHA-CH-06-TL-21).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). The
carrier is the moving plate of the rocker arm's oblique-trammel mill jig
(``ch_rocker_arm_tl_oblique_trammel_spec``, imported as ``trammel``). It rides
on two purchased shoulder screws (MHA-CH-06-TL-VN-77), supported by loose
spacers; for the inner pass they sit in A1/B1, for the outer pass in A2/B2.
The rocker blank on its 6061 riser (MHA-CH-06-TL-24) locates on the TL-33
hub stud's nose and the retained CL dowel. HUB and left #10-24 hold-downs
supplement the CR clamp. The TL-26 feed lever bolts to the -Y edge.

Material and stock: 1/2 x 6 in 6061-T6511 aluminium bar, the owned OnlineMetals
1173 (shop inventory); sawn to length and milled to width on edge in the
vise, no bandsaw rip (owner ruling #2083: the 6 in width does not fit the
5 3/4 in vise jaws flat), then faced to .47 (``CARRIER_THICK``) and milled to
20.5 x 5.1. Finished thickness takes the .XX title-block band, not STOCK.

Issue #2151: one native hole table locates all holes from A1's actual axis,
with +X along A1-B1. Coordinates print .XXX under the title-block ±.005.
The sole local exception is A2/B2 Y .964 ±.002. Kinematic geometric nominals
remain unchanged; their printed rounding is included in the budget below.

Frame (the calculator's carrier frame, and the model frame): origin at the
midpoint of A1-B1; +X runs A1 -> B1, +Y points toward the part, Z0 is the
carrier's TOP face. The plate occupies X -10.25..+10.25 in, Y -1.77..+3.33
in, Z -.47..0. SolidWorks axes: model X = carrier X, model Y (up) = carrier
Z, model Z = -carrier Y, so a Top-plane sketch reads (carrier X, carrier Y)
directly.

Values marked (calc) are read from ``trammel``, never retyped:

* (calc) Pivot-pin holes A1/B1 at (-/+D1/2, 0), D1 prints 17.722 in.
  A2/B2 have independent X baselines from A1, not chained offsets.
  Their Y .964 ±.002 is measured from the A1-B1 axis line.
* (calc) CL (-6.334, 1.156): a Ø.12 x 90° centre-drill spot only, finished
  in place on the running jig to .2490-.2495 (the owned .2490 reamer) for the
  bought 1/4 x 1 dowel (.2501-.2503, McMaster 98381A542), a .0006-.0013
  diametral press (``CL_DOWEL_INTERFERENCE``). The jig assembly carries that
  size, not this sheet. The spot's callout names the MHA-CH-13 strap feature
  it becomes.
* (calc) HUB (0, 1.792): the table's location is REF, not a second drilling
  control (owner ruling 5, option A, 2026-11-01). Its Y station moves the pivot
  radially 1:1, so it is drilled in situ at MHA-CH-06-TL-00 step 10: at the symmetric
  position, the table run from the apex (the spindle origin) +Y by
  ``trammel.HUB_OFFSET`` (``HUB_OFFSET_BAND``), then reamed to Ø.4000
  +.0005/0 (the purchased .4000 reamer) for the removable TL-33 hub clamp stud.
  The pin spacing moves HUB with the cut. The residual pin-shape error is
  bounded against that same HUB by ``PIN_RELATIVE_ERROR``. Together with
  carrier/stud slip and strap/nose float it fills ``PIN_RELATIVE_STACK``;
  the separate setting/pin-clearance half remains ``HUB_RADIAL_STACK``.
* (calc) CR (+6.334, 1.156): 1/4-20 UNC tapped THRU for the clamp screw that
  clamps the MHA-CH-13 strap (``CR_TAP_CALLOUT``); its SHCS head (Ø.375) is
  under the Ø12 mm that clears both cutter paths.
* (calc) Riser screws: 4 x #4-40 UNC tapped THRU at ``trammel.RISER_SCREWS``,
  on the R808.0 mm centreline of the riser's self-cut band
  (``trammel.RISER_SCREW_RADIUS``). Their stations print at
  ``trammel.RISER_TAP_STATION_PLACES``: the riser's holes are spotted through
  them, so they set its screws' walls to its cut edges (``RISER_TAP_CALLOUT``).
* Feed lever: 2 x 5/16-18 UNC tapped THRU at ``LEVER_HOLES`` (0, -.87) and
  (0, -1.50), .63 pitch (TrammelJig ruling) so the Ø.469 SHCS heads keep a gap.

The pin-hole fit remains Ø.3750 +.0015/+.0010, REAM THRU, on the
MHA-CH-06-TL-VN-77 shoulder. The assembly's rail alignment retains its own
±.0008 setting; it is not a carrier coordinate tolerance. In-situ HUB
location follows the actual inner-pass apex. The correlated pin/radius
calculation below therefore compares both cuts to that SAME HUB, rather
than adding independent absolute radius errors.

Pin-hole chamfer (``PIN_CHAMFER``): a .012 MIN x 45° underside edge break on
all four holes. Each active pair slides on the purchased TL-VN-78 spacer's top
face, rather than a pin collar; the chamfer's mouth stays inside the spacer's
smallest OD.

No skid (user ruling, option (b), 2026-10-16). The plate is carried on the two
pins only. Its centre sag between pins 450 mm apart, simply supported, E = 69
GPa: about 0.02 mm under its own weight and under 10 N of cutting load at
mid-span (``SAG_SELF_WEIGHT``, ``SAG_CUTTING_LOAD``) - far inside the cut's own
tolerance, so nothing need bear under the plate.

Rule 17 (walls) at worst case, against the inch .080 target: the lever tap's
thread major to the -Y edge at the stations' and the edge's .XX bands
(``WALLS_MM``). The existing CR, riser and lever taps run THRU the .47 plate:
their available full thread is the low-limit plate less its entry break
and one incomplete pitch (``ENGAGEMENT_MM``), not actual screw engagement.
The added left #10-24 receiver is BLIND, with a flat-bottom pilot and
separately required full thread; its own floor and engagement guards apply.
The feed-lever tap's existing under-1.5D RV-01 shortfall remains unchanged.
"""

from __future__ import annotations

import math
from itertools import product

import _config
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer
import ch_rocker_arm_tl_oblique_hub_stud_spec as hub_stud
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_spec as rocker
import _mcmaster_98381a542 as cl_dowel_stock
from _fit_deviations import deviations
from _fit_ream_h7 import REAM_H7
from _fit_ream_slide import REAM_SLIDE
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    printed_band_mm,
)

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-carrier",
    _config.parts("ch-rocker-arm-tl-oblique-carrier"),
)
if UNIT != trammel.CARRIER_UNIT:
    raise AssertionError("the carrier row and the calculator disagree on its unit")


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.0010``, ``8.861``."""
    text = f"{value_mm / trammel.INCH:.{places}f}"
    return text.replace("0.", ".", 1) if text.lstrip("-").startswith("0.") else text


def prints_exactly(value_mm: float, places: int) -> bool:
    """True when ``value_mm`` is an inch value on the ``places`` grid."""
    value_in = value_mm / trammel.INCH
    return abs(value_in - round(value_in, places)) <= 1e-9


_XX = printed_band_mm(2, unit=UNIT)
# Title-block DRILLED HOLES: the tap drills print with no band of their own.
DRILLED_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)

# --- Interface (TL-26 feed lever and the jig assembly import these) ---------
# PlateLength and PlateWidth print .X (no stack, wall or fit reads them);
# PlateNearY, which the lever-tap wall reads, prints .XX.
OUTLINE_X = (-260.35, 260.35)  # 20.5 overall
OUTLINE_Y = (-44.958, 84.582)  # -1.77 (.XX); 5.1 overall
THICKNESS = trammel.CARRIER_THICK
THICKNESS_PLACES = trammel.CARRIER_THICK_PLACES
THICKNESS_BAND = trammel.CARRIER_THICK_BAND
LEVER_HOLES = ((0.0, -22.098), (0.0, -38.1))  # -.87, -1.50
LEVER_INNER_END_Y = -14.986  # -.59

PLATE_LENGTH = OUTLINE_X[1] - OUTLINE_X[0]  # 20.5
PLATE_WIDTH = OUTLINE_Y[1] - OUTLINE_Y[0]  # 5.1
PLATE_NEAR_Y = -OUTLINE_Y[0]  # 1.77: the pin line to the -Y (operator) edge
PLATE_HALF_LENGTH = OUTLINE_X[1]  # 10.25: the centreline to either end

# --- Pivot-pin holes (calc) -------------------------------------------------
PIN_HOLES = trammel.PIN_HOLES
# Each pivot bore has a named axis for the shoulder-screw mate.
PIN_HOLE_AXES = {hole: f"PinAxis{hole}" for hole in PIN_HOLES}
D1 = trammel.D1
A2_DX = trammel.A2[0] - trammel.A1[0]  # -.2844 (outward)
A2_DY = trammel.A2[1] - trammel.A1[1]  # .9638
if abs(abs(A2_DX) - (trammel.D2 - trammel.D1) / 2.0) > 1e-9:
    raise AssertionError("A2 is not chained (D2 - D1)/2 outboard of A1")
# Fit doc F17: REAM_SLIDE on the 3/8 shoulder, cut by the owned .3760 reamer.
PIN_HOLE_DIA = 9.525  # .3750
PIN_HOLE_BAND = REAM_SLIDE  # +.0015/+.0010: .3760-.3765
PIN_MATE_BAND = pivot_screw.SHOULDER_DIA_BAND
_hole_low, _hole_high = deviations(PIN_HOLE_BAND)
_mate_low, _mate_high = deviations(PIN_MATE_BAND)
PIN_CLEARANCE_MIN = _hole_low - _mate_high
PIN_CLEARANCE_MAX = _hole_high - _mate_low
# Owner Option B, #2151: table locations, not chained ±.0008 dimensions.
TABLE_LOCATION_PLACES = 3
TABLE_LOCATION_BAND = printed_band_mm(TABLE_LOCATION_PLACES, unit=UNIT)
OUTER_Y_NOMINAL = 0.964 * trammel.INCH
OUTER_Y_BAND = 0.002 * trammel.INCH
OUTER_Y_DEVIATIONS = (
    OUTER_Y_NOMINAL - A2_DY - OUTER_Y_BAND,
    OUTER_Y_NOMINAL - A2_DY + OUTER_Y_BAND,
)
OUTER_Y_NOTE = "A2, B2: Y .964 ±.002 FROM THE A1-B1 AXIS LINE"
PIN_NUMBER = "MHA-CH-06-TL-VN-77"
# Keep the current .4000 H7 bore. The new stud shank slips through it; its
# unchanged .4000 locating nose serves the strap, not the carrier fit.
HUB_HOLE_DIA = 10.16  # .4000
HUB_HOLE_BAND = REAM_H7  # +.0005/0
_hub_hole_low, _hub_hole_high = deviations(HUB_HOLE_BAND)
_hub_shank_low, _hub_shank_high = deviations(hub_stud.SHANK_DIA_BAND)
HUB_HOLE_LIMITS = (HUB_HOLE_DIA + _hub_hole_low, HUB_HOLE_DIA + _hub_hole_high)
HUB_STUD_LIMITS = (
    hub_stud.SHANK_DIA + _hub_shank_low,
    hub_stud.SHANK_DIA + _hub_shank_high,
)
HUB_SLIP_CLEARANCE_MIN = HUB_HOLE_LIMITS[0] - HUB_STUD_LIMITS[1]
HUB_SLIP_CLEARANCE_MAX = HUB_HOLE_LIMITS[1] - HUB_STUD_LIMITS[0]
if HUB_SLIP_CLEARANCE_MIN <= 0.0:
    raise AssertionError("hub clamp stud does not slip through the unchanged carrier bore")
# Finished assembly-machined state: the bore's location is still set by TL-00
# step 10, not independently located from the plate edges on this drawing.
HUB = trammel.HUB
HUB_CHAMFER = 0.508  # .02, ordinary .XX ±.01: no tightened band
HUB_CHAMFER_PLACES = 2
HUB_CHAMFER_BAND = printed_band_mm(HUB_CHAMFER_PLACES, unit=UNIT)
HUB_CHAMFER_MIN = HUB_CHAMFER - HUB_CHAMFER_BAND
HUB_CHAMFER_MAX = HUB_CHAMFER + HUB_CHAMFER_BAND
HUB_CHAMFER_ANGLE_BAND = angular_band_deg(unit=UNIT)
# Bound both legs irrespective of which chamfer leg SOLIDWORKS dimensions.
_HUB_CHAMFER_LEG_RATIO = math.tan(math.radians(45.0 - HUB_CHAMFER_ANGLE_BAND))
HUB_ROOT_CLEARANCE_MIN = (
    HUB_CHAMFER_MIN * _HUB_CHAMFER_LEG_RATIO - hub_stud.ROOT_FILLET_R
)
HUB_FLANGE_SEAT_WIDTH_MIN = (
    hub_stud.FLANGE_DIA_LIMITS[0] / 2.0
    - HUB_HOLE_LIMITS[1] / 2.0 - HUB_CHAMFER_MAX / _HUB_CHAMFER_LEG_RATIO
)
if HUB_ROOT_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the HUB underside mouth cannot clear the stud root fillet")
if HUB_FLANGE_SEAT_WIDTH_MIN < WALL_TARGET_MM:
    raise AssertionError("the HUB chamfer consumes the stud flange's bearing seat")
HUB_HOLE_CALLOUT = (
    "REAM THRU AT ASSEMBLY\nLOCATION: TL-00 STEP 10\nSLIP ON MHA-CH-06-TL-33"
)
HUB_CHAMFER_CALLOUT = "X 45° UNDERSIDE\nAT ASSEMBLY; CLEARS TL-33 ROOT"
# The mate's number and name print on rows of their own: on one row they
# made the block 91 mm wide, past the inner border and across the plate
# end's extension line.
PIN_HOLE_CALLOUT = (
    f"4X REAM THRU ({inch_text(PIN_CLEARANCE_MIN, 4)}-"
    f"{inch_text(PIN_CLEARANCE_MAX, 4)}\n"
    f"DIAMETRAL CLEARANCE ON\n{PIN_NUMBER}\nSHOULDER SCREW)"
)
# Functions are carried once by the table's NOTE column.
STRAP_NUMBER = "MHA-CH-13"
STRAP_DEPTH = trammel.R_OUTER - trammel.R_INNER

# Underside chamfer: clears the entry and leaves a spacer thrust seat.
PIN_CHAMFER = 0.3048  # .012
PIN_CHAMFER_BAND = (0.1016, 0.0)  # +.004/0
PIN_CHAMFER_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints ".012 MIN"
PIN_CHAMFER_PLACES = 3
_PIN_CHAMFER_MOUTH_MAX = (
    (PIN_HOLE_DIA + PIN_HOLE_BAND[0]) / 2.0 + PIN_CHAMFER + PIN_CHAMFER_BAND[0]
)
# The AS62-18-40 spacer's smallest OD (.625 -.005) bounds its thrust seat.
if _PIN_CHAMFER_MOUTH_MAX >= (pivot_spacer.OD + pivot_spacer.OD_BAND[1]) / 2.0:
    raise AssertionError("pin-hole chamfer consumes the spacer's thrust seat")
if not prints_exactly(PIN_CHAMFER, PIN_CHAMFER_PLACES):
    raise AssertionError("the pin-hole chamfer must print exactly at its places")
# The hidden reference sketch section A-A imports (fr_nameplate's
# SectionReference): the printed chamfer leg, which drives the chamfer
# feature's distance, and the finished thickness, driven from Plate's depth. A
# partial section imports a hidden sketch in its plane (pd_platen A-A, pivot
# block B-B) but not a body feature's depth: jig-r4/r5 asked it for Plate's
# and got nothing at all, as ms_stick's G-G did for its cut depth. It lies on
# SECTION_PLANE, a named hidden plane coincident with the Front plane (the
# A1-B1 pin line, model Z = 0): every fleet section that imports a sketch
# has it on a dedicated plane in the cut (pd_platen and the pivot block's
# CboreSectionPlane, fr_nameplate's SectionAPlane); on the bare Front plane
# jig-r6's import came back empty.
SECTION_PLANE = "SectionAPlane"
SECTION_REFERENCE = "SectionReference"
PIN_CHAMFER_CALLOUT = "X 45\u00b0, 4X UNDERSIDE\nSEATS ON TL-VN-78 SPACER"
# Section A-A cuts SECTION_HALF_SPAN either side of A1's axis; the stock line
# stands STOCK_REFERENCE_INSET inside the cut's +X end, so the thickness's
# extension lines leave the slab at its end.
SECTION_HALF_SPAN = 9.0
STOCK_REFERENCE_INSET = 0.5
STOCK_REFERENCE_DX = SECTION_HALF_SPAN - STOCK_REFERENCE_INSET
if not PIN_HOLE_DIA / 2.0 + 2.0 <= STOCK_REFERENCE_DX < SECTION_HALF_SPAN:
    raise AssertionError("the stock line must stand in A1's +X wall, inside the cut")

# --- Centre-drill spots (calc) ------------------------------------------------
CL = trammel.CL
SPOT_DIA = 3.048  # .12
SPOT_ANGLE = 90.0  # included, the centre drill's
SPOT_FLANK_ANGLE = 90.0 - SPOT_ANGLE / 2.0
# HUB is not spotted: it is drilled in situ at assembly (owner ruling 5).
SPOTS = {"Cl": CL}
# The hidden reference sketch carrying the spot's printed station and Ø3: a
# reference plane's offset cannot be imported into a drawing (farm jig-r1),
# so the spot plane and cone are driven from this sketch instead.
SPOT_REFERENCE = "SpotReference"
# Hidden model baseline drivers; only EdgeX remains a printed dimension.
STATION_REFERENCE = "StationReference"
REFERENCE_SKETCHES = (SECTION_REFERENCE, SPOT_REFERENCE, STATION_REFERENCE)
# The CL dowel is press-set from the actual riser once CL is finished in place:
# fit doc F19, the bought 1/4 x 1 dowel (+.0001/+.0003) in a .2490-.2495
# hole cut by the owned .2490 reamer.
CL_DOWEL_DIA = cl_dowel_stock.DOWEL_SIZE[0]  # .2500
CL_DOWEL_BAND = (
    cl_dowel_stock.DIA_BAND_IN[1] * trammel.INCH,
    cl_dowel_stock.DIA_BAND_IN[0] * trammel.INCH,
)  # (upper, lower): .2501-.2503
CL_HOLE_BAND = (-0.0127, -0.0254)  # -.0005/-.0010: .2490-.2495
_dowel_low, _dowel_high = deviations(CL_DOWEL_BAND)
_cl_low, _cl_high = deviations(CL_HOLE_BAND)
CL_DOWEL_INTERFERENCE = (
    round(_dowel_low - _cl_high, 6),
    round(_dowel_high - _cl_low, 6),
)
if CL_DOWEL_INTERFERENCE[0] <= 0.0:
    raise AssertionError("the CL dowel is not a press in its finished hole")

# --- Tapped holes (UNC Hole Wizard; repo fastener policy) ----------------------
CR = trammel.CR
CR_THREAD = "1/4-20"
CR_SPEC = HoleSpec("tapped", CR_THREAD)
CR_TAP_DRILL = TAP_DRILL_MM[CR_THREAD]
CR_HEAD_DIA_MAX = 0.375 * trammel.INCH  # ASME B18.3 1/4 SHCS
CR_HEAD_CLEAR_DIA = 12.0  # clears both cutter paths
if CR_HEAD_DIA_MAX > CR_HEAD_CLEAR_DIA:
    raise AssertionError("the CR clamp screw head fouls a cutter path")
# Machinist review mr3: the tap names what its kinematic station serves; mr4:
# and why its 15.195 and 1.156 are 3-place: CR is CL mirrored about the tap
# axis (the strap blank's two end-waste stations on the hub radius). The
# callout carries it for both: the CrY lane has no room for a row (between the
# pin line and CR, the HUB lane 9.5 sheet mm right), and a row on the CrX lane
# would cross the RiserX2R and CrX extension lines, 20.6 sheet mm apart.
CR_STATION_FUNCTION = "MIRRORS CL STATION"
CR_TAP_CALLOUT = f"CLAMPS {STRAP_NUMBER}\n{CR_STATION_FUNCTION}"

# Added clamp beside CL. The blind receiver preserves an unbroken underside:
# a flat-bottom pilot is end-milled, not made with a 118-degree drill point.
LEFT_CLAMP = trammel.LEFT_CLAMP
LEFT_CLAMP_THREAD = "#10-24"
LEFT_CLAMP_TAP_DRILL = TAP_DRILL_MM[LEFT_CLAMP_THREAD]
LEFT_CLAMP_DRILL_DEPTH = 9.398  # .37, .XX band
LEFT_CLAMP_THREAD_DEPTH = 7.874  # .310 MIN from entry face
LEFT_CLAMP_THREAD_TOL_TYPE = 5  # swTolMIN, authored on the Wizard's source dimension
LEFT_CLAMP_THREAD_PLACES = 3
LEFT_CLAMP_FULL_THREAD_MIN = LEFT_CLAMP_THREAD_DEPTH - 0.254  # .010 entry break
# Feature export keeps the pilot's .XX depth band in `depth` and cites these
# independent thread minima in the required `note`: prechips has no separate
# full-thread-depth field. The .310 MIN is not a bilateral depth tolerance;
# the .010 entry break leaves .300 MIN of usable full thread.
LEFT_CLAMP_FLOOR_MIN = (
    THICKNESS - THICKNESS_BAND - LEFT_CLAMP_DRILL_DEPTH - _XX
)
LEFT_CLAMP_SPEC = HoleSpec(
    "tapped_bottoming", LEFT_CLAMP_THREAD, end="blind",
    depth_mm=LEFT_CLAMP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": LEFT_CLAMP_THREAD_DEPTH},
    drill_angle_deg=180.0,
)
LEFT_CLAMP_TAP_CALLOUT = "FLAT BOTTOM\nTHREAD DEPTH MIN\nCLAMPS STRAP BESIDE CL"
if LEFT_CLAMP_FLOOR_MIN < WALL_TARGET_MM - 1e-9:
    raise AssertionError("left blind clamp pilot violates the .080 floor")
if LEFT_CLAMP_FULL_THREAD_MIN < 1.5 * THREAD_MAJOR_MM[LEFT_CLAMP_THREAD]:
    raise AssertionError("left blind clamp tap has under 1.5D full thread")
# A bottoming tap with at most one incomplete pitch fits beyond the required
# full thread even at the shallowest permitted pilot depth.
if LEFT_CLAMP_DRILL_DEPTH - _XX - LEFT_CLAMP_THREAD_DEPTH < trammel.INCH / 24.0:
    raise AssertionError("left blind clamp tap has no room for its bottoming lead")

RISER_SCREWS = trammel.RISER_SCREWS
RISER_THREAD = "#4-40"
RISER_SPEC = HoleSpec("tapped", RISER_THREAD)
RISER_TAP_DRILL = TAP_DRILL_MM[RISER_THREAD]
# The riser (MHA-CH-06-TL-24) is self-cut along the jig's band and its holes
# are spotted through these taps at assembly, so their stations set the
# screws' worst-case walls to its cut edges: trammel.RISER_SCREW_WALLS assumes
# them at RISER_TAP_STATION_PLACES' title-block band.
RISER_STATION_PLACES = trammel.RISER_TAP_STATION_PLACES
RISER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
RISER_TAP_CALLOUT = f"HOLDS {RISER_NUMBER} SCREWS\nCLEAR OF ITS CUT EDGES"

LEVER_THREAD = "5/16-18"
LEVER_SPEC = HoleSpec("tapped", LEVER_THREAD)
LEVER_TAP_DRILL = TAP_DRILL_MM[LEVER_THREAD]

# --- Hidden X drivers: unchanged nominal geometry, baselines from A1 ----------
# Hole Wizard placement sketches cannot contain a datum point. Keep the
# existing baseline driver sketch, but only EdgeX prints as a dimension.
# The native table reads actual hole axes, not these construction points.
STATIONS = {
    "EdgeX": (OUTLINE_X[0], OUTLINE_Y[0]),
    "ClX": CL,
    "LeverX": LEVER_HOLES[0],
    "RiserX1": RISER_SCREWS[0],
    "RiserX1R": RISER_SCREWS[1],
    "RiserX2": RISER_SCREWS[2],
    "RiserX2R": RISER_SCREWS[3],
    "CrX": CR,
    "LeftClampX": LEFT_CLAMP,
}

# --- Rule 18: full thread at the worst case ------------------------------------
# Every tap runs THRU the faced plate: its finished .XX low limit, less the
# tap mouth's title-block edge break and one pitch of incomplete lead.
TAP_MOUTH_BREAK = edge_break_chamfer_mm(unit=UNIT)


def _pitch(thread: str) -> float:
    return trammel.INCH / float(thread.rsplit("-", 1)[1])


ENGAGEMENT_MM = {
    thread: THICKNESS - THICKNESS_BAND - TAP_MOUTH_BREAK - _pitch(thread)
    for thread in (CR_THREAD, RISER_THREAD, LEVER_THREAD)
}
ENGAGEMENT_D = {
    thread: length / THREAD_MAJOR_MM[thread] for thread, length in ENGAGEMENT_MM.items()
}
# A finished .47 plate cannot hold 1.5D of 5/16-18: the lever taps are the one
# stated shortfall (rule 20), each value floored to its printed places (a MIN
# never rounds up, pd_transgear_arm_spec.engagement_line).
SHORT_ENGAGEMENT = (LEVER_THREAD,)
for _thread, _d in ENGAGEMENT_D.items():
    if (_d < 1.5) != (_thread in SHORT_ENGAGEMENT):
        raise AssertionError(f"{_thread} engagement {_d:.3f}D is not as stated")
_ENGAGED_IN = (
    math.floor(ENGAGEMENT_MM[LEVER_THREAD] / trammel.INCH * 1000.0 + 1e-9) / 1000.0
)
_ENGAGED_D = math.floor(ENGAGEMENT_D[LEVER_THREAD] * 100.0 + 1e-9) / 100.0
LEVER_TAP_CALLOUT = (
    f"ENGAGEMENT {inch_text(_ENGAGED_IN * trammel.INCH, 3)} MIN ({_ENGAGED_D:.2f}D)"
)

# --- Rule 17 walls at worst case (.XX stations and edge) -----------------------
_LEVER_MAJOR_R = THREAD_MAJOR_MM[LEVER_THREAD] / 2.0
WALLS_MM: dict[str, float] = {
    "lever tap to -Y edge": (PLATE_NEAR_Y - _XX)
    - (-LEVER_HOLES[1][1] + _XX)
    - _LEVER_MAJOR_R,
    "lever taps web": (LEVER_HOLES[0][1] - LEVER_HOLES[1][1] - 2.0 * _XX)
    - 2.0 * _LEVER_MAJOR_R,
}
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET_MM:
        raise AssertionError(f"carrier {_wall} wall {_mm:.3f} under rule 17's .080")

# --- No skid: sag between the pins -----------------------------------------------
E_6061 = 69_000.0  # N/mm^2
DENSITY_6061 = 2.70e-6  # kg/mm^3
_I = PLATE_WIDTH * THICKNESS**3 / 12.0
_Q = DENSITY_6061 * 9.81 * PLATE_WIDTH * THICKNESS  # N/mm
SAG_SELF_WEIGHT = 5.0 * _Q * D1**4 / (384.0 * E_6061 * _I)
CUTTING_LOAD_N = 10.0
SAG_CUTTING_LOAD = CUTTING_LOAD_N * D1**3 / (48.0 * E_6061 * _I)

# --- Drawing --------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateLength", "PlateWidth", "PlateNearY"},
    "PinHoleProfile": {"PinHoleDia"},
    SECTION_REFERENCE: {"PinChamferSize", "StockThick"},
    SPOT_REFERENCE: {"SpotDia"},
    STATION_REFERENCE: {"EdgeX"},
    "HubHoleProfile": {"HubHoleDia"},
    "HubChamfer": {"HubChamferSize"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "PlateLength": 1,
        "PlateWidth": 1,
        "PlateNearY": 2,
    },
    # Size remains four-place; unprinted kinematic drivers follow table places.
    "PinHoleProfile": {
        "PinSpacing": TABLE_LOCATION_PLACES,
        "PinHoleDia": 4,
        "A2DX": TABLE_LOCATION_PLACES,
        "A2DY": TABLE_LOCATION_PLACES,
        "B2DX": TABLE_LOCATION_PLACES,
        "B2DY": TABLE_LOCATION_PLACES,
    },
    SECTION_REFERENCE: {
        "PinChamferSize": PIN_CHAMFER_PLACES,
        "StockThick": THICKNESS_PLACES,
    },
    # The kinematic CL/CR stations (exempt from snapping) print 3 places.
    SPOT_REFERENCE: {"SpotDia": 2, "ClY": 3},
    # The left end at the outline's .X; the TL-24 stations at the walls' places.
    STATION_REFERENCE: {
        "EdgeX": 1,
        "ClX": 3,
        "LeverX": 3,
        "CrX": 3,
        "LeftClampX": 3,
        **{name: RISER_STATION_PLACES for name in STATIONS if name.startswith("Riser")},
    },
    "CrTap": {"CrY": 3},
    "LeftClampTap": {"LeftClampY": 3},
    "RiserTaps": {"RiserY1": RISER_STATION_PLACES, "RiserY2": RISER_STATION_PLACES},
    "LeverTaps": {"LeverY1": TABLE_LOCATION_PLACES, "LeverY2": TABLE_LOCATION_PLACES},
    "HubHoleProfile": {"HubHoleDia": 4},
    "HubChamfer": {"HubChamferSize": HUB_CHAMFER_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if not set().union(*DRAWING_DIMENSIONS.values()) <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every marked carrier dimension needs authored places")

# The HUB, reamed for the stud carrying the strap's pivot on the cut
# arcs' centreline (X = 0), moves the pivot radially 1:1 against the R800 top
# edge. Rule 19 (owner ruling 5, option A, 2026-11-01): it is drilled in situ
# on the running jig at the symmetric position, the table run from the apex
# (the spindle origin, on R_C1) +Y by HUB_OFFSET, so the pin spacing moves it
# with the cut and no carrier band reaches it. What still does, at the worst
# case: the DRO setting of that printed offset and the carrier's shift on its
# pins between drilling and cutting (trammel.RADIUS_FROM_SHOULDER_CLEARANCE).
# The symmetric position's own error moves the HUB along the arc, second
# order radially (dx² / 2R).
_TOP_EDGE_HALF_BAND = (max(rocker.TOP_EDGE_BAND) - min(rocker.TOP_EDGE_BAND)) / 2.0
HUB_OFFSET_PLACES = 4  # a .0001 DRO, as the alignment table
HUB_OFFSET_BAND = 0.0005 * trammel.INCH  # ±.0005 on the DRO setting
HUB_OFFSET_PRINTED = (
    round(trammel.HUB_OFFSET / trammel.INCH, HUB_OFFSET_PLACES) * trammel.INCH
)
HUB_RADIAL_STACK = (
    HUB_OFFSET_BAND
    + abs(HUB_OFFSET_PRINTED - trammel.HUB_OFFSET)
    + trammel.RADIUS_FROM_SHOULDER_CLEARANCE
)
if HUB_RADIAL_STACK >= _TOP_EDGE_HALF_BAND:
    raise AssertionError("the HUB fit-up stack exceeds half the strap's top-edge band")


def _trig_range(a: float, b: float, c: float, angle: float) -> tuple[float, float]:
    """Exact range of a*sin(t)+b*cos(t)+c on [-angle, angle]."""
    candidates = [-angle, angle]
    phase = math.atan2(a, b)
    candidates.extend(
        t for k in range(-2, 3)
        if -angle <= (t := phase + k * math.pi) <= angle
    )
    values = [a * math.sin(t) + b * math.cos(t) + c for t in candidates]
    return min(values), max(values)


def pin_coordinate_intervals(
    location_band: float = TABLE_LOCATION_BAND,
    outer_y_band: float = OUTER_Y_BAND,
    *, include_rounding: bool = True,
) -> tuple[tuple[float, float], ...]:
    """Errors of B1.X, A2.X, B2.X, A2.Y, B2.Y, in the A1 datum frame."""
    a1 = PIN_HOLES["A1"]
    values = (
        D1, PIN_HOLES["A2"][0] - a1[0], PIN_HOLES["B2"][0] - a1[0],
        A2_DY, A2_DY,
    )
    bands = (location_band,) * 3 + (outer_y_band,) * 2
    return tuple(
        (
            (round(value / trammel.INCH, TABLE_LOCATION_PLACES) * trammel.INCH
             - value if include_rounding else 0.0) - band,
            (round(value / trammel.INCH, TABLE_LOCATION_PLACES) * trammel.INCH
             - value if include_rounding else 0.0) + band,
        )
        for value, band in zip(values, bands, strict=True)
    )


def correlated_pin_budget(
    location_band: float = TABLE_LOCATION_BAND,
    outer_y_band: float = OUTER_Y_BAND,
    *, include_rounding: bool = True,
    angle: float = trammel.TIP_ANGLE,
) -> dict[str, tuple[float, float]]:
    """Enclose the entire tolerance box and continuous strap arc, in mm.

    C=(a+b)/2 + cot(alpha)/2*(dy,-dx), R=|b-a|/(2*sin(alpha)).
    The in-situ HUB follows the INNER apex: dH=(dD/2,k*dD),
    k=(1-cos(alpha))/(2*sin(alpha)). Both cuts use that SAME HUB.
    First-order edge error is u·(dH-dC)-dR, u=(sin(t),cos(t)).
    This is affine in the five errors, so extrema lie on box corners.
    Trig extrema are analytic, not sampled. The norm Hessian is bounded by
    1/(R-|dv|); the remainder encloses every interior error as well.
    The outer chord's norm remainder is charged independently. No RSS.
    """
    if location_band < 0.0 or outer_y_band < 0.0 or not 0.0 <= angle < math.pi / 2:
        raise ValueError("invalid carrier tolerance box or arc")
    intervals = pin_coordinate_intervals(
        location_band, outer_y_band, include_rounding=include_rounding
    )
    q = trammel.RADIUS_PER_SPACING
    h = 0.5 / math.tan(trammel.ALPHA)
    k = q - h
    corners = tuple(product(*intervals))
    result = {}
    for name, radius in (("inner", trammel.R_INNER), ("outer", trammel.R_OUTER)):
        lo, hi, v_max, chord_max = math.inf, -math.inf, 0.0, 0.0
        for d, ax, bx, ay, by in corners:
            if name == "inner":
                vx, vy, dr = 0.0, q * d, q * d
            else:
                vx = d / 2.0 - (ax + bx) / 2.0 - h * (by - ay)
                vy = k * d - (ay + by) / 2.0 + h * (bx - ax)
                dr = q * (bx - ax)
                chord_max = max(chord_max, math.hypot(bx - ax, by - ay))
            low, high = _trig_range(vx, vy, -dr, angle)
            lo, hi = min(lo, low), max(hi, high)
            v_max = max(v_max, math.hypot(vx, vy))
        if v_max >= radius or chord_max >= trammel.D2:
            raise AssertionError("carrier error box no longer supports the norm bound")
        radial_remainder = v_max**2 / (2.0 * (radius - v_max))
        chord_remainder = q * chord_max**2 / (2.0 * (trammel.D2 - chord_max))
        result[name] = (lo - chord_remainder, hi + radial_remainder)
    result["R800"] = tuple(q * value for value in intervals[0])
    dx = (intervals[2][0] - intervals[1][1], intervals[2][1] - intervals[1][0])
    dy = (intervals[4][0] - intervals[3][1], intervals[4][1] - intervals[3][0])
    dy_min = 0.0 if dy[0] <= 0.0 <= dy[1] else min(abs(v) for v in dy)
    result["R816"] = (
        q * math.hypot(trammel.D2 + dx[0], dy_min) - trammel.R_C2,
        q * math.hypot(trammel.D2 + dx[1], max(abs(v) for v in dy)) - trammel.R_C2,
    )
    return result


PIN_ONLY_BUDGET = correlated_pin_budget(include_rounding=False)
PIN_ROUNDED_BUDGET = correlated_pin_budget()
PIN_RELATIVE_ERROR = {
    name: max(abs(value) for value in PIN_ROUNDED_BUDGET[name])
    for name in ("inner", "outer")
}
# Owner's .010 half-band is two independent .005 allocations: setting and
# pin-shoulder clearance first; correlated shape plus both locating floats
# second. Never spend the first half's tiny remainder on the stud nose.
PIN_RELATIVE_ALLOWANCE = _TOP_EDGE_HALF_BAND - 0.005 * trammel.INCH
if HUB_RADIAL_STACK > 0.005 * trammel.INCH:
    raise AssertionError("HUB setting and clearance exceed the reserved .005")
HUB_SHANK_RADIAL_FLOAT = HUB_SLIP_CLEARANCE_MAX / 2.0
HUB_NOSE_RADIAL_FLOAT = hub_stud.NOSE_CLEARANCE[1] / 2.0
NOSE_FLOAT_ALLOWANCE = (
    PIN_RELATIVE_ALLOWANCE - max(PIN_RELATIVE_ERROR.values()) - HUB_SHANK_RADIAL_FLOAT
)


def require_pin_relative_budget(nose_radial_float: float) -> float:
    """Return the complete relative stack, refusing a nose fit beyond its half."""
    if not math.isfinite(nose_radial_float) or nose_radial_float < 0.0:
        raise ValueError("nose radial float must be finite and nonnegative")
    stack = max(PIN_RELATIVE_ERROR.values()) + HUB_SHANK_RADIAL_FLOAT + nose_radial_float
    if stack > PIN_RELATIVE_ALLOWANCE:
        raise AssertionError(
            "correlated pin error plus carrier/stud and strap/nose float exceed "
            f"the relative .005 budget: stack_mm={stack!r}, "
            f"allowance_mm={PIN_RELATIVE_ALLOWANCE!r}, "
            f"nose_float_mm={nose_radial_float!r}, "
            f"nose_allowance_mm={NOSE_FLOAT_ALLOWANCE!r}"
        )
    return stack


PIN_RELATIVE_STACK = require_pin_relative_budget(HUB_NOSE_RADIAL_FLOAT)
PIN_RELATIVE_REMAINING = PIN_RELATIVE_ALLOWANCE - PIN_RELATIVE_STACK
# Owner's approximate bounds: .0088/.0177 absolute, .0001/.0038 relative.
# The .0001 is rounded: the continuous top-edge enclosure is under .0002.
for _name, _expected in (("R800", .0089), ("R816", .0178), ("inner", .0002), ("outer", .0039)):
    if max(abs(v) for v in PIN_ONLY_BUDGET[_name]) >= _expected * trammel.INCH:
        raise AssertionError(f"pin-only {_name} exceeds the owner's expected bound")


def station_sweep_error(point: tuple[float, float], pass_name: str) -> float:
    """Bound hole-to-cutter displacement on the whole finite sweep, not radial only.

    A clamp outside the arc endpoint needs a Euclidean bound. For each box
    corner, |w-dr*u|² is a single sine/cosine expression; bound its entire
    sweep analytically, then include the outer chord's norm remainder.
    """
    ex, ey = table_coordinate_errors(point)
    q, h = trammel.RADIUS_PER_SPACING, .5 / math.tan(trammel.ALPHA)
    worst_squared, chord_max = 0.0, 0.0
    for d, ax, bx, ay, by in product(*pin_coordinate_intervals()):
        if pass_name == "inner":
            cx, cy, dr = d / 2.0, -h * d, q * d
        elif pass_name == "outer":
            cx, cy = (ax + bx) / 2.0 + h * (by - ay), (ay + by) / 2.0 - h * (bx - ax)
            dr = q * (bx - ax)
            chord_max = max(chord_max, math.hypot(bx - ax, by - ay))
        else:
            raise ValueError(pass_name)
        for px, py in product((-ex, ex), (-ey, ey)):
            wx, wy = px - cx, py - cy
            _low, high = _trig_range(
                -2.0 * dr * wx, -2.0 * dr * wy,
                wx * wx + wy * wy + dr * dr, trammel.SWEEP[pass_name],
            )
            worst_squared = max(worst_squared, high)
    return math.sqrt(worst_squared) + q * chord_max**2 / (2.0 * (trammel.D2 - chord_max))


def table_coordinate_errors(point: tuple[float, float]) -> tuple[float, float]:
    """Ordinary table row's X/Y errors, including its printed rounding."""
    return tuple(
        TABLE_LOCATION_BAND + abs(
            round(value / trammel.INCH, TABLE_LOCATION_PLACES) * trammel.INCH - value
        )
        for value in (point[0] - PIN_HOLES["A1"][0], point[1])
    )


def station_cut_error(point: tuple[float, float], pass_name: str) -> float:
    """Table-located hole versus self-cut edge, including printed rounding."""
    theta = math.atan2(point[0], point[1] + trammel.H1)
    sx, cy = math.sin(theta), math.cos(theta)
    station_errors = table_coordinate_errors(point)
    q, h = trammel.RADIUS_PER_SPACING, 0.5 / math.tan(trammel.ALPHA)
    worst, v_max, chord_max = 0.0, 0.0, 0.0
    for d, ax, bx, ay, by in product(*pin_coordinate_intervals()):
        if pass_name == "inner":
            cx, cy_shift, dr = d / 2.0, -h * d, q * d
        elif pass_name == "outer":
            cx = (ax + bx) / 2.0 + h * (by - ay)
            cy_shift = (ay + by) / 2.0 - h * (bx - ax)
            dr = q * (bx - ax)
            chord_max = max(chord_max, math.hypot(bx - ax, by - ay))
        else:
            raise ValueError(pass_name)
        worst = max(worst, abs(-sx * cx - cy * cy_shift - dr))
        v_max = max(v_max, math.hypot(
            abs(cx) + station_errors[0], abs(cy_shift) + station_errors[1]
        ))
    radius = math.dist(point, trammel.ARC_CENTRE)
    remainder = v_max**2 / (2.0 * (radius - v_max))
    remainder += q * chord_max**2 / (2.0 * (trammel.D2 - chord_max))
    return worst + abs(sx) * station_errors[0] + abs(cy) * station_errors[1] + remainder


_RISER_MOUTH_MAX = (
    trammel.RISER_CSK_DIA + printed_band_mm(trammel.RISER_CSK_PLACES, unit=trammel.RISER_UNIT)
) / 2.0
RISER_WALLS_FROM_A1 = min(
    min(
        math.dist(point, trammel.ARC_CENTRE) - trammel.RISER_INNER_RADIUS
        - station_cut_error(point, "inner"),
        trammel.RISER_OUTER_RADIUS - math.dist(point, trammel.ARC_CENTRE)
        - station_cut_error(point, "outer"),
    ) - _RISER_MOUTH_MAX
    for point in RISER_SCREWS
)
if RISER_WALLS_FROM_A1 < WALL_TARGET_MM:
    raise AssertionError("a riser countersink breaks rule 17's .080 wall from A1")


# The spot has its own leader and callout, naming the strap feature it
# becomes (machinist review mr3: the 3-place stations to it read as
# functional). mr8: it stands in the one band outside the plate its leader
# reaches crossing no dimension line (rule 14): under the 7.287 lane, between
# the RiserX2 and RiserX1 extension lines, ~37 mm wide, so each row stays
# within 13 characters.
SPOT_CALLOUT = "SPOT FOR"
SPOT_CALLOUTS = {"SpotDia": f"{SPOT_CALLOUT}\n{STRAP_NUMBER} CL"}
CALLOUTS_BELOW = {
    "PinHoleDia": PIN_HOLE_CALLOUT,
    **SPOT_CALLOUTS,
    "PinChamferSize": PIN_CHAMFER_CALLOUT,
}
_SPOT_SUFFIX = f" X {SPOT_ANGLE:.0f}\u00b0"
CALLOUT_SUFFIXES = {"SpotDia": _SPOT_SUFFIX}
CALLOUT_PREFIXES: dict[str, str] = {}

# Includes the finished in-situ HUB: its native LOC cells are reference only.
TABLE_HOLES = {
    **{key: (*point, PIN_HOLE_DIA) for key, point in PIN_HOLES.items()},
    "CL": (*CL, SPOT_DIA),
    "CR": (*CR, CR_TAP_DRILL),
    "LEFT": (*LEFT_CLAMP, LEFT_CLAMP_TAP_DRILL),
    **{f"R{i}": (*point, RISER_TAP_DRILL) for i, point in enumerate(RISER_SCREWS, 1)},
    **{f"L{i}": (*point, LEVER_TAP_DRILL) for i, point in enumerate(LEVER_HOLES, 1)},
    "HUB": (*trammel.HUB, HUB_HOLE_DIA),
}
TABLE_ROW_NOTES = {
    "A1": "ORIGIN; R800 / MHA-CH-13",
    "B1": "X AXIS; R800 / MHA-CH-13",
    "A2": "R816 / MHA-CH-13; NOTE 1",
    "B2": "R816 / MHA-CH-13; NOTE 1",
    "CL": "SPOT FOR MHA-CH-13 CL",
    "CR": "CLAMPS MHA-CH-13",
    "LEFT": "BLIND CLAMP; SEE CALLOUT",
    **{f"R{i}": "LOCATES TL-24 RISER" for i in range(1, 5)},
    **{f"L{i}": "FEED LEVER; SEE CALLOUT" for i in range(1, 3)},
    "HUB": "LOCATIONS REF; TL-00 STEP 10",
}
DRAWING_NOTES = OUTER_Y_NOTE
ISOMETRIC_VIEW_SCALE = (1, 8)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
