r"""Pure-data contract for the oblique-trammel carrier (MHA-CH-06-TL-21).

R4 workholding uses three ordinary #8-32 THRU taps: two end-waste clamps
at CL/CR and a HUB clamp. All use the common 91251A197 screw. There is no
precision carrier HUB bore, underside flange seat, CL dowel or LEFT receiver.
The strap is registered by the riser's end-waste stops, clamped at both ends,
then drilled and reamed in place over the riser's relief. The product's hub
hole, not this plate's thread, locates the top-hat washer.

Carrier coordinates: origin midway between A1/B1, X along the pin line,
Y toward the strap, Z0 at the top face. The 6061 plate is faced to .47 in
from 1/2 x 6 in stock and finished to 20.5 x 5.1 in. The feed-lever taps
retain their stated short engagement. No new workholding dimension carries
a custom tolerance; tap locations use the ordinary .XX title-block band.

HUB_OFFSET is an assembly setting from the actual inner-pass apex. Its
HUB_RADIAL_STACK belongs to the product-hole location, not to a carrier
ream or a stud slip fit. The later carrier-table layer owns correlated
pin-relative errors; this module remains independent of that layer.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_spec as rocker
from _fit_deviations import deviations
from _fit_ream_slide import REAM_SLIDE
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
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
# Symmetric, on D1, dX and dY: the former +/-0.02 mm on the inch grid.
POSITION_BAND = 0.02032  # .0008
PIN_NUMBER = "MHA-CH-06-TL-VN-77"
# Ordinary receiver only. The strap's product bore is made at assembly;
# no precision carrier bore or underside seating feature survives R4.
HUB = trammel.HUB
CLAMP_THREAD = "#8-32"
CLAMP_SPEC = HoleSpec("tapped", CLAMP_THREAD)
CLAMP_TAP_DRILL = TAP_DRILL_MM[CLAMP_THREAD]
HUB_THREAD = CLAMP_THREAD
HUB_SPEC = HoleSpec("tapped", HUB_THREAD)
HUB_TAP_CALLOUT = "CLAMPS STRAP HUB\nLOCATION: TL-00 STEP 10"
# The mate's number and name print on rows of their own: on one row they
# made the block 91 mm wide, past the inner border and across the plate
# end's extension line.
PIN_HOLE_CALLOUT = (
    f"4X REAM THRU ({inch_text(PIN_CLEARANCE_MIN, 4)}-"
    f"{inch_text(PIN_CLEARANCE_MAX, 4)}\n"
    f"DIAMETRAL CLEARANCE ON\n{PIN_NUMBER}\nSHOULDER SCREW)"
)
# Rule 4: each pin band names what it sets and on which part (jig-r3 review);
# the error sensitivities stay in the docstring.
STRAP_NUMBER = "MHA-CH-13"
SPACING_CALLOUT = f"SETS R{trammel.R_INNER:.0f} ON\n{STRAP_NUMBER}"
DX_CALLOUT = f"SETS R{trammel.R_OUTER:.0f} ON\n{STRAP_NUMBER}"
DY_CALLOUT = DX_CALLOUT
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

# --- Ordinary workholding taps -----------------------------------------------
CL = trammel.CL
CR = trammel.CR
END_CLAMPS = {"CL": CL, "CR": CR}
CL_SPEC = HoleSpec("tapped", CLAMP_THREAD)
CR_SPEC = HoleSpec("tapped", CLAMP_THREAD)
CLAMP_STATION_PLACES = 2
CLAMP_STATION_BAND = printed_band_mm(CLAMP_STATION_PLACES, unit=UNIT)
END_CLAMP_TAP_CALLOUT = f"CLAMPS {STRAP_NUMBER}\nEND WASTE"
STATION_REFERENCE = "StationReference"
REFERENCE_SKETCHES = (SECTION_REFERENCE, STATION_REFERENCE)
# mr4: the tap axis's 8.861 is 3-place because it locates the lever taps;
# mr8: named by the feature it locates on the sheet, its row no wider than
# the 11-character one it replaced (draw: LeverX's lane).
LEVER_STATION_CALLOUT = "LEVER TAPS"
# Final review: the taps stand on the kinematic tap axis (8.861 from A1,
# exempt from snapping) but the lever needs no .XXX band, so the station
# prints its own two-place band (rule 3), set on the model dimension.
LEVER_STATION_BAND = _XX

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
# placements stay origin-based, driven from
# STATION_REFERENCE: one point on A1's axis and one on each station's feature
# (the left end's on the -X/-Y corner), each printed dimension the baseline
# from A1. The lever taps' axis (X = 0) prints as LeverX, its point on the
# upper lever tap: its extension line rises from the X lane through both
# taps, so one 8.861 visibly locates the pair. LeverX is driven equal to A1X,
# which stays the model's driving dimension, unprinted.
STATIONS = {
    "EdgeX": (OUTLINE_X[0], OUTLINE_Y[0]),
    "ClX": CL,
    "LeverX": LEVER_HOLES[0],
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
if trammel.ARC_CENTRE[0] != 0.0 or RISER_WALLS_FROM_A1 < WALL_TARGET_MM:
    raise AssertionError("a riser countersink breaks rule 17's .080 wall from A1")

# --- Rule 18: full thread at the worst case ------------------------------------
# Every tap runs THRU the faced plate: its finished .XX low limit, less the
# tap mouth's title-block edge break and one pitch of incomplete lead.
TAP_MOUTH_BREAK = edge_break_chamfer_mm(unit=UNIT)


def _pitch(thread: str) -> float:
    return trammel.INCH / float(thread.rsplit("-", 1)[1])


ENGAGEMENT_MM = {
    thread: THICKNESS - THICKNESS_BAND - TAP_MOUTH_BREAK - _pitch(thread)
    for thread in (CLAMP_THREAD, RISER_THREAD, LEVER_THREAD)
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
    "PinHoleProfile": {
        "PinSpacing",
        "PinHoleDia",
        "A2DX",
        "A2DY",
        "B2DX",
        "B2DY",
    },
    SECTION_REFERENCE: {"PinChamferSize", "StockThick"},
    "ClTap": {"ClY"},
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
    # The reamed size and the ±.0008 chain need four places.
    "PinHoleProfile": {
        "PinSpacing": 4,
        "PinHoleDia": 4,
        "A2DX": 4,
        "A2DY": 4,
        "B2DX": 4,
        "B2DY": 4,
    },
    SECTION_REFERENCE: {
        "PinChamferSize": PIN_CHAMFER_PLACES,
        "StockThick": THICKNESS_PLACES,
    },
    "ClTap": {"ClY": CLAMP_STATION_PLACES},
    # The left end at the outline's .X; the TL-24 stations at the walls' places.
    STATION_REFERENCE: {
        "EdgeX": 1,
        "ClX": CLAMP_STATION_PLACES,
        "LeverX": 3,
        "CrX": CLAMP_STATION_PLACES,
        **{name: RISER_STATION_PLACES for name in STATIONS if name.startswith("Riser")},
    },
    "CrTap": {"CrY": CLAMP_STATION_PLACES},
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

# The in-place STRAP hole follows the actual inner-pass apex. There is no
# stud/nose float in this location stack. Correlated pin-relative errors
# remain the responsibility of the later carrier-table layer.
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

# Symmetric ±.0008 on these (build: set_dimension_symmetric_tolerance).
POSITION_BANDED = ("PinSpacing", "A2DX", "A2DY", "B2DX", "B2DY")

CALLOUTS_BELOW = {
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "PinSpacing": SPACING_CALLOUT,
    "A2DX": DX_CALLOUT,
    "B2DX": DX_CALLOUT,
    "A2DY": DY_CALLOUT,
    "B2DY": DY_CALLOUT,
    "PinChamferSize": PIN_CHAMFER_CALLOUT,
    **{name: RISER_STATION_CALLOUT for name in RISER_STATIONS},
    "LeverX": LEVER_STATION_CALLOUT,
}
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
