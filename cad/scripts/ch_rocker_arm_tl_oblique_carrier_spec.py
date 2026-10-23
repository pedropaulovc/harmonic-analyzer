r"""Pure-data contract for the oblique-trammel jig's carrier plate (MHA-CH-06-TL-21).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). The
carrier is the moving plate of the rocker arm's oblique-trammel mill jig
(``ch_rocker_arm_tl_oblique_trammel_spec``, imported as ``trammel``). It rides
on two pivot pins (MHA-CH-06-TL-23), one in each pivot block on the two
rails; for the inner pass the pins sit in A1/B1, for the outer pass in A2/B2.
The rocker blank, on its riser (MHA-CH-06-TL-24), is located on the HUB pin
(MHA-CH-06-TL-25) and the CL dowel and clamped by the CR screw; the feed
lever (MHA-CH-06-TL-26) bolts to the -Y edge.

Material and stock: 1/2 in 6061-T651 aluminium plate, OnlineMetals #1250
custom cut 5.5 x 21 in; faced to 12.0 (``CARRIER_THICK``) and milled to
520 x 130. Finished thickness takes the .X title-block band, not STOCK.

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
  for the TL-25 pin, and CL to Ø6 N7 (5.984/5.996) for the bought Ø6 x 20 m6
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

* Pin holes Ø10.000 +0.015/0 (H7), REAM THRU. Mate: MHA-CH-06-TL-23 PIVOT
  PIN, upper section Ø10 h6, so 0.000-0.024 diametral clearance. That
  clearance is edge error 1:1.
* D1 450.135 ±0.02: a spacing error x 1.77 (``trammel.RADIUS_PER_SPACING``)
  is the cut radius error on R800.
* dX 7.224 ±0.02: moves the outer pass's pin spacing D2 one to one, so x 1.77
  on R816.
* dY 24.481 ±0.02: 1:1 on the 16.00 strap depth (R816 - R800).
* Rail angle (not on this sheet): 0.1° of rail angle is about 4.7 mm of R
  (``trammel.RADIUS_PER_TENTH_DEG``); the rails are set by indicating.
* Bearing radial play (not on this sheet): the C3 6200-2RS play,
  0.008-0.023 unmounted, can open or close the pin spacing by up to 0.023, so
  up to 0.041 on R (``trammel.RADIUS_FROM_BEARING_PLAY``).

Position chains. X runs from the HUB spot's axis, which the 260.0 places from
the left end (A1 by an ordinary 225.07, B1 from A1 by the spacing); Y runs from
the A1-B1 pin line, the reamed pair's own axes, placed 45.00 from the -Y edge.
A2/B2 chain from A1/B1, never from an edge.

Pin-hole chamfer (``PIN_CHAMFER``, jig-r3 interference). Each pivot pin's
collar seats on the underside, and its R0.2 MAX collar fillet
(``ch_rocker_arm_tl_oblique_pivot_pin_spec.SHOULDER_FILLET_RADIUS``) met the
sharp edge of the Ø10 hole: 0.27 mm³ of overlap per pin. All four holes
carry a 0.3 MIN x 45° chamfer on that edge (every pair rides the pins on
some pass). The HUB does not: it is only a Ø3 spot here and is reamed to
Ø10.20 H7 in place on the running jig, so its break belongs to that in-place
step (the hub pin's R0.2 head fillet is cleared by the title block's edge
break, ``ch_rocker_arm_tl_oblique_hub_pin_spec``).

No skid (user ruling, option (b), 2026-10-16). The plate is carried on the two
pins only. Its centre sag between pins 450 apart, simply supported, E = 69 GPa,
I = 130·12³/12: 0.02 mm under its own weight and 0.015 mm under 10 N of
cutting load at mid-span (``SAG_SELF_WEIGHT``, ``SAG_CUTTING_LOAD``) - far
inside the cut's own tolerance, so nothing need bear under the plate.

Each pin-hole axis is inspected against the underside-plane normal in every
azimuth before assembly. PIN_AXIS_CALLOUT belongs to the native 4X REAM
dimension: its resultant lateral shift per normal height bounds the actual
vector angle by atan(0.05/10.50), not each projected component independently.
Section A-A measures the actual straight land as a native reference (11.7
nominal); PIN_LAND_CALLOUT separately requires 10.50 MIN of straight land.
The process row gives the surface-plate, fitted-arbor and indicator setup.
No geometric frame, reamed fit or chamfer geometry changes.

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
import ch_rocker_arm_tl_oblique_pivot_pin_spec as pivot_pin
import ch_rocker_arm_tl_oblique_retention_spec as retention
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
# Each pin hole's hidden named axis, which the jig assembly mates on the
# pivot pin's (pivot_pin_spec.AXIS_NAME).
PIN_HOLE_AXES = {hole: f"PinAxis{hole}" for hole in PIN_HOLES}
D1 = trammel.D1
A2_DX = trammel.A2[0] - trammel.A1[0]  # -7.224 (outward)
A2_DY = trammel.A2[1] - trammel.A1[1]  # 24.481
if abs(abs(A2_DX) - (trammel.D2 - trammel.D1) / 2.0) > 1e-9:
    raise AssertionError("A2 is not chained (D2 - D1)/2 outboard of A1")
PIN_HOLE_DIA = 10.0
PIN_HOLE_BAND = (0.015, 0.0)  # H7 on Ø10
PIN_MATE_BAND = (0.0, -0.009)  # h6 on the TL-23 pin's Ø10 upper section
_hole_low, _hole_high = deviations(PIN_HOLE_BAND)
_mate_low, _mate_high = deviations(PIN_MATE_BAND)
PIN_CLEARANCE_MIN = _hole_low - _mate_high
PIN_CLEARANCE_MAX = _hole_high - _mate_low
POSITION_BAND = 0.02  # symmetric, on D1, dX and dY
PIN_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-pivot-pin")["number"]
PIN_MATE = f"{PIN_NUMBER} PIVOT PIN"
PIN_HOLE_CALLOUT = (
    f"4X REAM THRU ({PIN_CLEARANCE_MIN:.3f}-{PIN_CLEARANCE_MAX:.3f}\n"
    f"DIAMETRAL CLEARANCE ON\n{PIN_MATE})"
)
# Source-visible aliases of the shared retention proof's actual inspection
# limits, not independent tolerances or extra bore geometry.
PIN_AXIS_DEVIATION_MAX = retention.CARRIER_AXIS_DEVIATION_MAX
PIN_AXIS_MEASUREMENT_SPAN = retention.CARRIER_AXIS_MEASUREMENT_SPAN
# Rule 4: each pin band names what it sets and on which part (jig-r3 review);
# the error sensitivities stay in the docstring.
STRAP_NUMBER = "MHA-CH-13"
SPACING_CALLOUT = f"SETS R{trammel.R_INNER:.0f} ON\n{STRAP_NUMBER}"
DX_CALLOUT = f"SETS R{trammel.R_OUTER:.0f} ON\n{STRAP_NUMBER}"
DY_CALLOUT = DX_CALLOUT
STRAP_DEPTH = trammel.R_OUTER - trammel.R_INNER

# 45° chamfer on each pin hole's underside (collar-side) edge: it clears the
# pivot pin's collar fillet.  Printed as a native single MIN limit: the title
# block's .X band would let it shrink to nothing.  (upper, lower): the
# nominal IS the MIN limit; the upper, which a MIN print does not show, is
# the native record of what still leaves the collar a seat (guard below).
PIN_CHAMFER = 0.3
PIN_CHAMFER_BAND = (0.1, 0.0)
PIN_CHAMFER_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints "0.3 MIN"
PIN_CHAMFER_PLACES = 1
# The modeled straight wall ends at the underside chamfer, not at an invented
# 10.50 station. Section A-A displays this derived length as reference only.
PIN_STRAIGHT_LAND = THICKNESS - PIN_CHAMFER
DRAWING_REFERENCE_PRECISION = {"PinStraightLand": 1}
# Against the hole edge the fillet's arc stands R (2 - sqrt 2) proud of a 45°
# chamfer's leg, so the MIN leg reaches it with 0.1 to spare; the chamfered
# mouth at its largest stays inside the collar.
if PIN_CHAMFER < pivot_pin.SHOULDER_FILLET_RADIUS * (2.0 - math.sqrt(2.0)) + 0.1:
    raise AssertionError("pin-hole chamfer does not clear the pivot pin's fillet")
_PIN_CHAMFER_MOUTH_MAX = (
    (PIN_HOLE_DIA + PIN_HOLE_BAND[0]) / 2.0 + PIN_CHAMFER + PIN_CHAMFER_BAND[0]
)
if _PIN_CHAMFER_MOUTH_MAX >= pivot_pin.COLLAR_DIA / 2.0:
    raise AssertionError("pin-hole chamfer eats the pivot pin collar's seat")
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
PIN_CHAMFER_CALLOUT = f"X 45\u00b0, 4X UNDERSIDE\nCLEARS {PIN_NUMBER}\nCOLLAR FILLET"
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
REFERENCE_SKETCHES = (SECTION_REFERENCE, SPOT_REFERENCE)
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
# Rule 4: each 3-place station names what it locates (carrier r11 review).
RISER_STATION_CALLOUT = f"LOCATES\n{RISER_NUMBER}"
RISER_STATIONS = ("RiserX1", "RiserX1R", "RiserY1", "RiserX2", "RiserX2R", "RiserY2")

LEVER_THREAD = "5/16-18"
LEVER_SPEC = HoleSpec("tapped", LEVER_THREAD)
LEVER_TAP_DRILL = TAP_DRILL_MM[LEVER_THREAD]

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
    "PlateProfile": {"PlateLength", "PlateWidth", "PlateHalfLength", "PlateNearY"},
    "PinHoleProfile": {
        "A1X",
        "PinSpacing",
        "PinHoleDia",
        "A2DX",
        "A2DY",
        "B2DX",
        "B2DY",
    },
    SECTION_REFERENCE: {"PinChamferSize", "StockThick"},
    SPOT_REFERENCE: {"SpotDia", "SpotDiaCl", "HubY", "ClX", "ClY"},
    "CrTap": {"CrX", "CrY"},
    "RiserTaps": set(RISER_STATIONS),
    "LeverTaps": {"LeverY1", "LeverY2"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "PlateLength": 1,
        "PlateWidth": 1,
        "PlateHalfLength": 1,
        "PlateNearY": 2,
    },
    "PinHoleProfile": {
        "A1X": 2,
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
    SPOT_REFERENCE: {"SpotDia": 2, "SpotDiaCl": 2, "HubY": 2, "ClX": 2, "ClY": 2},
    "CrTap": {"CrX": 2, "CrY": 2},
    "RiserTaps": {name: RISER_STATION_PLACES for name in RISER_STATIONS},
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
# The full orientation acceptance is on the actual reamed diameter, never on
# a separate leader note. "Resultant" controls the lateral vector magnitude;
# normal height makes its bound exactly atan(deviation/span), in any azimuth.
CAP_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-pivot-cap")["number"]
PIN_AXIS_CALLOUT = (
    "AXES TO UNDERSIDE NORMAL:\n"
    "RESULTANT LATERAL SHIFT:\n"
    f"{PIN_AXIS_DEVIATION_MAX:.2f} MAX PER {PIN_AXIS_MEASUREMENT_SPAN:.2f}\n"
    "NORMAL HEIGHT, ALL AZIMUTHS\n"
    f"CLEARS {CAP_NUMBER} CAP"
)
PIN_LAND_CALLOUT = f"4X STRAIGHT\nLAND\n{PIN_AXIS_MEASUREMENT_SPAN:.2f} MIN"
CALLOUTS_BELOW = {
    "PinHoleDia": f"{PIN_HOLE_CALLOUT}\n{PIN_AXIS_CALLOUT}",
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
# shared coordinate) and has its own X station from HUB, so each printed
# height covers both holes of its row (carrier-r1 review: the +X pair read as
# unlocated in Y).
CALLOUT_PREFIXES = {"RiserY1": "2X ", "RiserY2": "2X "}

DRAWING_NOTES = ""
ISOMETRIC_VIEW_SCALE = (1, 8)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
