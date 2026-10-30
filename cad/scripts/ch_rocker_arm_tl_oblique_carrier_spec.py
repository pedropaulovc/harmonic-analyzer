r"""Pure-data contract for the oblique-trammel jig's carrier plate (MHA-CH-06-TL-21).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). The
carrier is the moving plate of the rocker arm's oblique-trammel mill jig
(``ch_rocker_arm_tl_oblique_trammel_spec``, imported as ``trammel``). It rides
on two purchased shoulder screws (MHA-CH-06-TL-VN-77), supported by loose
spacers; for the inner pass they sit in A1/B1, for the outer pass in A2/B2.
The rocker blank, on its riser (MHA-CH-06-TL-24), is located on the HUB pin
(MHA-CH-06-TL-VN-80) and the CL dowel and clamped by the CR screw; the feed
lever (MHA-CH-06-TL-26) bolts to the -Y edge.

Material and stock: 1/2 x 6 in 6061-T6511 aluminium bar, the owned OnlineMetals
1173 (shop inventory); sawn to length and ripped to about 135 wide, since the
6 in width does not fit the 5 3/4 in vise jaws, then faced to 12.0
(``CARRIER_THICK``) and milled to 520 x 130. Finished thickness takes the .X
title-block band, not STOCK.

Frame (the calculator's carrier frame, and the model frame): origin at the
midpoint of A1-B1; +X runs A1 -> B1, +Y points toward the part, Z0 is the
carrier's TOP face. The plate occupies X -260..+260, Y -45..+85, Z -12..0.
SolidWorks axes: model X = carrier X, model Y (up) = carrier Z, model Z =
-carrier Y, so a Top-plane sketch reads (carrier X, carrier Y) directly.

Values marked (calc) are read from ``trammel``, never retyped:

* (calc) Pivot-pin holes A1/B1 at (-/+D1/2, 0), D1 = 450.135; A2/B2 at
  ``trammel.A2``/``B2``, chained FROM A1/B1 by dX = (D2 - D1)/2 = 7.224 and
  dY = 24.481. Never from a plate edge.
* (calc) HUB (0, 45.526) and CL (-160.895, 29.350): Ø3 x 90° centre-drill
  spots only. Both are finished in place on the running jig: HUB to Ø10.20 H7
  for the bonded TL-VN-80 gauge pin, and CL to Ø6 N7 (5.984/5.996) for the bought Ø6 x 20 m6
  dowel (6.004/6.012, inventory ``fixtures.trammel-cl-dowel``), a
  0.008-0.028 diametral press (``CL_DOWEL_INTERFERENCE``). The traveler
  carries these sizes, not this sheet, so the spots locate at title-block
  tolerance.
* (calc) CR (+160.895, 29.350): 1/4-20 UNC tapped THRU for the clamp screw;
  its SHCS head (Ø0.375 in = 9.53) is under the Ø12 that clears both cutter
  paths.
* (calc) Riser screws: 4 x #4-40 UNC tapped THRU at ``trammel.RISER_SCREWS``,
  (±39.984, 44.287) and (±119.559, 36.382), on the R808.0 centreline of the
  riser's self-cut band (``trammel.RISER_SCREW_RADIUS``). Their stations
  print at ``trammel.RISER_TAP_STATION_PLACES``: the riser's holes are spotted
  through them, so they set its screws' walls to its cut edges
  (``RISER_TAP_CALLOUT``).
* Feed lever: 2 x 5/16-18 UNC tapped THRU at ``LEVER_HOLES`` (0, -22) and
  (0, -38), 16 pitch (TrammelJig ruling) so the Ø11.9 SHCS heads keep a gap.

Tight bands (drawing-guidelines.md rule 4). The print names each band's
function and mate (``SPACING_CALLOUT``, ``DX_CALLOUT``, ``DY_CALLOUT``: the
pair sets R800 or R816 on the MHA-CH-13 strap); the sensitivities stay here:

* Pin holes Ø10.000 +0.015/0 (H7), REAM THRU. Mate: MHA-CH-06-TL-VN-77
  shoulder, Ø10 -0.025/0, so 0.000-0.040 diametral clearance. That
  clearance is edge error 1:1.
* D1 450.135 ±0.02: a spacing error x 1.77 (``trammel.RADIUS_PER_SPACING``)
  is the cut radius error on R800.
* dX 7.224 ±0.02: moves the outer pass's pin spacing D2 one to one, so x 1.77
  on R816.
* dY 24.481 ±0.02: 1:1 on the 16.00 strap depth (R816 - R800).
* Rail angle (not on this sheet): 0.1° of rail angle is about 4.7 mm of R
  (``trammel.RADIUS_PER_TENTH_DEG``); the rails are set by indicating.

Position chains (rule 10: one datum per view). X runs from A1's axis, the
left lower ream that carries the ±0.02 pair: the left end 34.9 from it, B1 by
the spacing, and every spot and tap by a baseline of its own
(``STATION_REFERENCE``), the tap axis (lever taps and HUB) by the 225.07. Y
runs from the A1-B1 pin line, the reamed pair's own axes, placed 45.00 from
the -Y edge. A2/B2 chain from A1/B1, never from an edge.

Pin-hole chamfer (``PIN_CHAMFER``): retain the existing 0.3 MIN x 45°
underside edge breaks on all four holes. Each active pair slides on the
purchased TL-VN-78 spacer's top face, rather than a pin collar. The HUB
is still finished in place to Ø10.20 H7 for the bonded gauge pin.

No skid (user ruling, option (b), 2026-10-16). The plate is carried on the two
pins only. Its centre sag between pins 450 apart, simply supported, E = 69 GPa,
I = 130·12³/12: 0.02 mm under its own weight and 0.015 mm under 10 N of
cutting load at mid-span (``SAG_SELF_WEIGHT``, ``SAG_CUTTING_LOAD``) - far
inside the cut's own tolerance, so nothing need bear under the plate.


Rule 17 (walls) at worst case: the lever tap's thread major to the -45 edge
is 3.03 nominal, 2.01 at the stations' and the edge's .XX bands
(``WALLS_MM``). Rule 18 (engagement): every tap runs THRU the 12 plate, so its
full thread at the worst case is the plate at its .X low limit less the tap
mouth's title-block edge break and one pitch of incomplete lead
(``ENGAGEMENT_MM``, build_pd_platen_clip's count). These are the carrier's
available full threads, not the screws' actual engagement: #4-40 offers
10.31 and 1/4-20 offers 9.68. The 5/16-18 feed-lever tap offers 9.53 of the
11.91 needed (1.20D); its existing RV-01 callout states that shortfall.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer
import ch_rocker_arm_tl_vn_oblique_hub_pin_spec as hub_pin
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _fit_deviations import deviations
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

_XX = printed_band_mm(2)
# Title-block DRILLED HOLES: the tap drills print with no band of their own.
DRILLED_BAND = (drilled_oversize_mm(), 0.0)

# --- Interface (TL-26 feed lever and the jig assembly import these) ---------
OUTLINE_X = (-260.0, 260.0)
OUTLINE_Y = (-45.0, 85.0)
THICKNESS = trammel.CARRIER_THICK
THICKNESS_PLACES = trammel.CARRIER_THICK_PLACES
THICKNESS_BAND = trammel.CARRIER_THICK_BAND
LEVER_HOLES = ((0.0, -22.0), (0.0, -38.0))
LEVER_INNER_END_Y = -15.0

PLATE_LENGTH = OUTLINE_X[1] - OUTLINE_X[0]  # 520
PLATE_WIDTH = OUTLINE_Y[1] - OUTLINE_Y[0]  # 130
PLATE_NEAR_Y = -OUTLINE_Y[0]  # 45: the pin line to the -Y (operator) edge
PLATE_HALF_LENGTH = OUTLINE_X[1]  # 260: the centreline to either end

# --- Pivot-pin holes (calc) -------------------------------------------------
PIN_HOLES = trammel.PIN_HOLES
# Each unchanged pivot bore has a named axis for the shoulder-screw mate.
PIN_HOLE_AXES = {hole: f"PinAxis{hole}" for hole in PIN_HOLES}
D1 = trammel.D1
A2_DX = trammel.A2[0] - trammel.A1[0]  # -7.224 (outward)
A2_DY = trammel.A2[1] - trammel.A1[1]  # 24.481
if abs(abs(A2_DX) - (trammel.D2 - trammel.D1) / 2.0) > 1e-9:
    raise AssertionError("A2 is not chained (D2 - D1)/2 outboard of A1")
PIN_HOLE_DIA = 10.0
PIN_HOLE_BAND = (0.015, 0.0)  # H7 on Ø10
PIN_MATE_BAND = pivot_screw.SHOULDER_DIA_BAND
_hole_low, _hole_high = deviations(PIN_HOLE_BAND)
_mate_low, _mate_high = deviations(PIN_MATE_BAND)
PIN_CLEARANCE_MIN = _hole_low - _mate_high
PIN_CLEARANCE_MAX = _hole_high - _mate_low
POSITION_BAND = 0.02  # symmetric, on D1, dX and dY
PIN_NUMBER = "MHA-CH-06-TL-VN-77"
HUB_HOLE_DIA = 10.20
HUB_HOLE_BAND = (0.018, 0.0)  # unchanged in-place H7 bore for bonded gauge pin
_hub_hole_low, _hub_hole_high = deviations(HUB_HOLE_BAND)
_hub_pin_low, _hub_pin_high = deviations(hub_pin.DIA_BAND)
HUB_HOLE_LIMITS = (HUB_HOLE_DIA + _hub_hole_low, HUB_HOLE_DIA + _hub_hole_high)
HUB_PIN_LIMITS = (hub_pin.DIA + _hub_pin_low, hub_pin.DIA + _hub_pin_high)
HUB_BOND_CLEARANCE_MIN = HUB_HOLE_LIMITS[0] - HUB_PIN_LIMITS[1]
HUB_BOND_CLEARANCE_MAX = HUB_HOLE_LIMITS[1] - HUB_PIN_LIMITS[0]
if HUB_BOND_CLEARANCE_MIN < 0.0:
    raise AssertionError("bonded gauge pin interferes with the unchanged carrier H7 bore")
# The mate's number and name print on rows of their own: on one row they
# made the block 91 mm wide, past the inner border and across the plate
# end's extension line.
PIN_HOLE_CALLOUT = (
    f"4X REAM THRU ({PIN_CLEARANCE_MIN:.3f}-{PIN_CLEARANCE_MAX:.3f}\n"
    f"DIAMETRAL CLEARANCE ON\n{PIN_NUMBER}\nSHOULDER SCREW)"
)
# Rule 4: each pin band names what it sets and on which part (jig-r3 review);
# the error sensitivities stay in the docstring.
STRAP_NUMBER = "MHA-CH-13"
SPACING_CALLOUT = f"SETS R{trammel.R_INNER:.0f} ON\n{STRAP_NUMBER}"
DX_CALLOUT = f"SETS R{trammel.R_OUTER:.0f} ON\n{STRAP_NUMBER}"
DY_CALLOUT = DX_CALLOUT
STRAP_DEPTH = trammel.R_OUTER - trammel.R_INNER

# Existing underside chamfer: clears the entry and leaves a spacer thrust seat.
PIN_CHAMFER = 0.3
PIN_CHAMFER_BAND = (0.1, 0.0)
PIN_CHAMFER_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints "0.3 MIN"
PIN_CHAMFER_PLACES = 1
_PIN_CHAMFER_MOUTH_MAX = (
    (PIN_HOLE_DIA + PIN_HOLE_BAND[0]) / 2.0 + PIN_CHAMFER + PIN_CHAMFER_BAND[0]
)
if _PIN_CHAMFER_MOUTH_MAX >= (pivot_spacer.OD + pivot_spacer.OD_BAND[1]) / 2.0:
    raise AssertionError("pin-hole chamfer consumes the spacer's thrust seat")
if round(PIN_CHAMFER, PIN_CHAMFER_PLACES) != PIN_CHAMFER:
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
HUB = trammel.HUB
CL = trammel.CL
SPOT_DIA = 3.0
SPOT_ANGLE = 90.0  # included, the centre drill's
SPOT_FLANK_ANGLE = 90.0 - SPOT_ANGLE / 2.0
SPOTS = {"Hub": HUB, "Cl": CL}
# The hidden reference sketch carrying the spots' printed stations and Ø3: a
# reference plane's offset cannot be imported into a drawing (farm jig-r1),
# so the spot planes and cones are driven from this sketch instead.
SPOT_REFERENCE = "SpotReference"
# The hidden sketch of points carrying every printed X station from A1
# (``STATIONS``).
STATION_REFERENCE = "StationReference"
REFERENCE_SKETCHES = (SECTION_REFERENCE, SPOT_REFERENCE, STATION_REFERENCE)
# The CL dowel is press-set from the actual riser once CL is finished in place:
# a bought Ø6 m6 dowel in an N7 hole (ISO 286, 3-6 mm row).
CL_DOWEL_DIA = 6.0
CL_DOWEL_BAND = (0.012, 0.004)  # m6
CL_HOLE_BAND = (-0.004, -0.016)  # N7
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
# Rule 4: each 3-place station names what it locates (carrier r11 review), on
# one row by the riser's tool number (the A1 baselines leave no room for the
# full number's 39 mm; RISER_TAP_CALLOUT spells it out).
RISER_TOOL_ID = "-".join(RISER_NUMBER.split("-")[-2:])
RISER_STATION_CALLOUT = f"LOCATES {RISER_TOOL_ID}"
RISER_STATIONS = ("RiserX1", "RiserX1R", "RiserY1", "RiserX2", "RiserX2R", "RiserY2")

LEVER_THREAD = "5/16-18"
LEVER_SPEC = HoleSpec("tapped", LEVER_THREAD)
LEVER_TAP_DRILL = TAP_DRILL_MM[LEVER_THREAD]

# --- X stations: baselines from A1 (rule 10, one datum per view) ---------------
# A Hole Wizard placement sketch cannot carry a datum point, so the taps'
# and SpotReference's placements stay origin-based, driven from
# STATION_REFERENCE: one point on A1's axis and one on each station's feature
# (the left end's on the -X/-Y corner), each printed dimension the baseline
# from A1. The tap axis (lever taps and HUB, X = 0) prints as HubX, its point
# on the HUB spot: its extension line rises from the X lane through the lever
# taps to the spot, so one 225.07 visibly locates all three (machinist review
# 54e5c9a: A1X's line stopped at the pin line, short of HUB). HubX is driven
# equal to A1X, which stays the model's driving dimension, unprinted.
STATIONS = {
    "EdgeX": (OUTLINE_X[0], OUTLINE_Y[0]),
    "ClX": CL,
    "HubX": HUB,
    "RiserX1": RISER_SCREWS[0],
    "RiserX1R": RISER_SCREWS[1],
    "RiserX2": RISER_SCREWS[2],
    "RiserX2R": RISER_SCREWS[3],
    "CrX": CR,
}
# Rule 17 (riser walls): C, the cut's centre (trammel.ARC_CENTRE), stands D1/2
# from A1, so each riser station's error about C adds half the spacing band to
# the station band trammel.RISER_SCREW_WALLS assumes, radially x |x|/R.
_RISER_X_MAX = max(abs(x) for x, _y in RISER_SCREWS)
RISER_WALLS_FROM_A1 = min(trammel.RISER_SCREW_WALLS) - (
    POSITION_BAND / 2.0 * _RISER_X_MAX / trammel.RISER_SCREW_RADIUS
)
if trammel.ARC_CENTRE[0] != 0.0 or RISER_WALLS_FROM_A1 < 2.0:
    raise AssertionError("a riser countersink breaks rule 17's 2.0 wall from A1")

# --- Rule 18: full thread at the worst case ------------------------------------
# Every tap runs THRU the faced plate: its finished .X low limit, less the
# tap mouth's title-block edge break and one pitch of incomplete lead.
TAP_MOUTH_BREAK = float(_config.title_block("edge_break")["chamfer_max_mm"])


def _pitch(thread: str) -> float:
    return trammel.INCH / float(thread.rsplit("-", 1)[1])


ENGAGEMENT_MM = {
    thread: THICKNESS - THICKNESS_BAND - TAP_MOUTH_BREAK - _pitch(thread)
    for thread in (CR_THREAD, RISER_THREAD, LEVER_THREAD)
}
ENGAGEMENT_D = {
    thread: length / THREAD_MAJOR_MM[thread] for thread, length in ENGAGEMENT_MM.items()
}
# A finished 12 plate cannot hold 1.5D of 5/16-18: the lever taps are the one
# stated shortfall (rule 20), each value floored to two places (a MIN never
# rounds up, pd_transgear_arm_spec.engagement_line).
SHORT_ENGAGEMENT = (LEVER_THREAD,)
for _thread, _d in ENGAGEMENT_D.items():
    if (_d < 1.5) != (_thread in SHORT_ENGAGEMENT):
        raise AssertionError(f"{_thread} engagement {_d:.3f}D is not as stated")
_ENGAGED_MM = math.floor(ENGAGEMENT_MM[LEVER_THREAD] * 100.0 + 1e-9) / 100.0
_ENGAGED_D = math.floor(ENGAGEMENT_D[LEVER_THREAD] * 100.0 + 1e-9) / 100.0
LEVER_TAP_CALLOUT = f"ENGAGEMENT {_ENGAGED_MM:.2f} MIN ({_ENGAGED_D:.2f}D)"

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
    if _mm < 2.0:
        raise AssertionError(f"carrier {_wall} wall {_mm:.3f} under rule 17")

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
    "PinHoleProfile": {
        "PinSpacing",
        "PinHoleDia",
        "A2DX",
        "A2DY",
        "B2DX",
        "B2DY",
    },
    SECTION_REFERENCE: {"PinChamferSize", "StockThick"},
    SPOT_REFERENCE: {"SpotDia", "SpotDiaCl", "HubY", "ClY"},
    STATION_REFERENCE: set(STATIONS),
    "CrTap": {"CrY"},
    "RiserTaps": {"RiserY1", "RiserY2"},
    "LeverTaps": {"LeverY1", "LeverY2"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "PlateLength": 1,
        "PlateWidth": 1,
        "PlateNearY": 2,
    },
    "PinHoleProfile": {
        "PinSpacing": 3,
        "PinHoleDia": 3,
        "A2DX": 3,
        "A2DY": 3,
        "B2DX": 3,
        "B2DY": 3,
    },
    SECTION_REFERENCE: {
        "PinChamferSize": PIN_CHAMFER_PLACES,
        "StockThick": THICKNESS_PLACES,
    },
    SPOT_REFERENCE: {"SpotDia": 2, "SpotDiaCl": 2, "HubY": 2, "ClY": 2},
    # The left end at the outline's .X; the TL-24 stations at the walls' places.
    STATION_REFERENCE: {
        "EdgeX": 1,
        "ClX": 2,
        "HubX": 2,
        "CrX": 2,
        **{name: RISER_STATION_PLACES for name in STATIONS if name.startswith("Riser")},
    },
    "CrTap": {"CrY": 2},
    "RiserTaps": {"RiserY1": RISER_STATION_PLACES, "RiserY2": RISER_STATION_PLACES},
    "LeverTaps": {"LeverY1": 2, "LeverY2": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked carrier dimension needs authored places")

# Symmetric ±0.02 on these (build: set_dimension_symmetric_tolerance).
POSITION_BANDED = ("PinSpacing", "A2DX", "A2DY", "B2DX", "B2DY")

# Each spot has its own leader and callout (jig-r3: a "2X" with one leader
# read as one spot).
SPOT_CALLOUT = "CENTRE DRILL SPOT"
CALLOUTS_BELOW = {
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "PinSpacing": SPACING_CALLOUT,
    "A2DX": DX_CALLOUT,
    "B2DX": DX_CALLOUT,
    "A2DY": DY_CALLOUT,
    "B2DY": DY_CALLOUT,
    "SpotDia": SPOT_CALLOUT,
    "SpotDiaCl": SPOT_CALLOUT,
    "PinChamferSize": PIN_CHAMFER_CALLOUT,
    **{name: RISER_STATION_CALLOUT for name in RISER_STATIONS},
}
_SPOT_SUFFIX = f" X {SPOT_ANGLE:.0f}\u00b0"
CALLOUT_SUFFIXES = {"SpotDia": _SPOT_SUFFIX, "SpotDiaCl": _SPOT_SUFFIX}
# Each riser row's +X screw shares its -X twin's height (the tap sketch's
# shared coordinate) and has its own X station from A1, so each printed
# height covers both holes of its row (carrier-r1 review: the +X pair read as
# unlocated in Y).
CALLOUT_PREFIXES = {"RiserY1": "2X ", "RiserY2": "2X "}

DRAWING_NOTES = ""
ISOMETRIC_VIEW_SCALE = (1, 8)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
