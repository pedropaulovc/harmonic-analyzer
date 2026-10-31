r"""Oblique-trammel calculator for the rocker strap's R800/R816 edges (route v3).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). The strap
MHA-CH-13 of the built-up rocker MHA-CH-06 has its two concentric edges cut
as true circles on the PM-30MV with the table locked. Two straight HGR15 rails,
fixed to the table, cross at the spindle axis at the acute angle ``ALPHA_DEG``.
A carrier plate (MHA-CH-06-TL-21) rides one pivot pin on each rail. The angle
the spindle subtends between the two pins is constant, so by the
inscribed-angle theorem the spindle traces a circle of radius
``R = D / (2 sin ALPHA)`` in the carrier's frame. The outer edge reuses the
same rails: with the spindle isolated, both shoulder screws are removed and
the carrier lifted, the carriages moved to the other stations, and the carrier
re-seated on A2/B2 before both screws are refitted.

This module is the one pure calculator: it derives every value marked ⚙ on
the jig sheets (MHA-CH-06-TL-20 to TL-26 and the TL-00 jig assembly) from:

* the strap's edge radii and the hub-to-top-edge aim, read from
  ``ch_rocker_arm_spec`` (R800/R816; ``TOP_EDGE_ABOVE_PIVOT`` (the strap's
  ``PIVOT_MID_Y``) plus the mid-point of ``TOP_EDGE_BAND`` = 8.25);
* the two cutters, both on hand in inventory ``tools.endmills-lms-6784``:
  the 3/8 in four-flute end mill for the part and the 9/16 in one for the
  riser (``test_ch_rocker_arm_tl_oblique_trammel_spec`` checks both against
  the inventory's size list, so this module never reads the inventory and
  an unrelated inventory edit does not rebuild the jig);
* ``ALPHA_DEG``, kept at the brief's 16.4405 degrees;
* the 350 mm blank (strap stock 1018 3 x 40 mm, OnlineMetals #22381);
* the bought hardware the jig is built round (HIWIN HGR15 rail cut to 440,
  HGH15CA Z0 carriage, shoulder screws and loose spacers) and the PM-30MV table (maker manual,
  macclab.com PM-30MV-v3-2020-10: table 33 x 8-1/4 in, three 14 mm T-slots at
  63.5 mm, spindle centreline 7-1/2 in from the pleated column cover).

Plain shoulder-screw pivots positively capture both supports during both
passes. Each 5/16-18 shoulder screw bottoms its shoulder on the block seat;
its head captures the carrier, which turns on the shoulder and slides on a
loose spacer over a selected shim. The carrier seat remains at Z80.2.
Heights alone do not prove spindle/toolholder clearance: installed-machine
acceptance needs the actual stepped tooling envelope over both complete sweeps.

Frames.

* Carrier frame: origin at the midpoint of A1-B1, +X along A1 -> B1, +Y
  toward the part, Z0 on the carrier's top face. The arc centre C is at
  (0, -H1). It is a reference only and is never drilled.
* Machine frame: origin on the spindle axis (DRO zero) at the table top, +X
  along the table, +Y toward the column, +Z up. The rail pin-lines pass
  through the origin at -/+ ALPHA/2 to -X/+X and diverge toward the
  operator (-Y). ``s`` is a pin's distance from the origin along its line.

Error sensitivity (printed next to the bands that carry it):

* rail angle: 0.1 degree of pin-line angle changes R by
  ``RADIUS_PER_TENTH_DEG`` (about 4.7 mm) and moves the arc centre about as
  far. That is why HUB and CL are reamed in place on the running jig, where
  the real circle sits.
* pin-pair Y: a Y error between the A1/B1 and A2/B2 pairs moves the second
  circle's centre 1:1, so the 16.00 band moves 1:1. A2/B2 are therefore
  dimensioned from A1/B1, never from a plate edge.
* pin spacing: a D error changes R by ``RADIUS_PER_SPACING`` (1.77) per unit
  of spacing error. The spacing is held by one DRO setting.
* shoulder/carrier clearance: the purchased Ø.375 shoulder (-.001/0) in the
  carrier's .3760-.3765 REAM_SLIDE hole gives .0010-.0025 (0.025-0.064 mm)
  diametral clearance. This can move the edge 1:1; it is not a
  bearing-internal-play budget. The two supports' opposite radial take-up can
  change spacing by one diametral clearance, so the radius contribution is
  ``RADIUS_FROM_SHOULDER_CLEARANCE`` (0.112 mm).
  The block's locating counterbore has its own shoulder-clearance budget;
  there are no rolling bearings, press fits or mounted C3-play assumptions.

Sweep (Main, 2026-10-16). The brief swept the cutter over the whole 350
blank, +/-13 degrees about C. Here each pass covers the part only. The
strap's tip lands are radial lines through the top arc's ends, at
``TIP_ANGLE`` = (TOP_ARC_LEN / 2) / R800 = 10.46 degrees. The cutter centre
runs until its trailing edge has passed the land by ``RUN_OUT``:
``theta = TIP_ANGLE + (r_cutter + RUN_OUT) / R_c``, which is 11.02 degrees
on R_c1 and 11.00 on R_c2. With the cutter centre at theta about C, the
chords from the spindle to the pins subtend ALPHA +/- theta, so each pin
runs ``s = 2 R_c sin((ALPHA +/- theta) / 2)`` from the spindle along its
rail: 75.2 to 389.4 over both passes. The riser's 9/16 in cutter rides the
same circle as the part cutter with a larger radius. The same stops
therefore cut the riser clear of every position the part cutter reaches.

Pivot pin offset (owner-approved 2026-10-23). Keep ``PIN_OFFSET`` 32 toward
the spindle along the rail, preserving both pass stations and the carrier
hole layout. The plain .375 reamed shoulder seat replaces the former bearing
cartridge. The carriage centre still runs 107.2 to 421.4 against the rail's
45.7 to 424.3 (half the 61.4 carriage from each end of the 440 rail).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
import ch_rocker_arm_spec as rocker
import _rocker_interface as rocker_interface

INCH = 25.4
BASE_BAR_UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-base-bar", _config.parts("ch-rocker-arm-tl-oblique-base-bar")
)
CARRIER_UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-carrier", _config.parts("ch-rocker-arm-tl-oblique-carrier")
)
RISER_UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-riser", _config.parts("ch-rocker-arm-tl-oblique-riser")
)


def _inch_fraction(text: str) -> float:
    """A '9/16'-style inch fraction in millimetres, rounded clear of float noise."""
    numerator, denominator = text.split("/")
    return round(int(numerator) / int(denominator) * INCH, 9)


# --- Inputs -------------------------------------------------------------------
R_INNER = rocker.R_TOP  # R800 top edge
R_OUTER = rocker_interface.R_BOTTOM  # R816 bottom edge
# Aim the hub at the middle of the one-sided top-edge band (8.0 +0.50/0).
HUB_TO_TOP_EDGE = rocker.TOP_EDGE_ABOVE_PIVOT + sum(rocker.TOP_EDGE_BAND) / 2.0
HUB_RADIUS = R_INNER + HUB_TO_TOP_EDGE  # rho, the hub (and CL/CR) radius about C
ALPHA_DEG = 16.4405
ALPHA = math.radians(ALPHA_DEG)
HALF_ALPHA = ALPHA / 2.0

# Inventory tools.endmills-lms-6784 sizes (2 and 4 flute), nominal diameters.
PART_CUTTER_IN = "3/8"
RISER_CUTTER_IN = "9/16"
PART_CUTTER_DIA = _inch_fraction(PART_CUTTER_IN)
RISER_CUTTER_DIA = _inch_fraction(RISER_CUTTER_IN)

# --- Cutter-centre circles and pin holes ⚙ -----------------------------------
R_C1 = R_INNER - PART_CUTTER_DIA / 2.0  # inner pass, A1/B1
R_C2 = R_OUTER + PART_CUTTER_DIA / 2.0  # outer pass, A2/B2
D1 = 2.0 * R_C1 * math.sin(ALPHA)
D2 = 2.0 * R_C2 * math.sin(ALPHA)
H1 = R_C1 * math.cos(ALPHA)  # pin-line A1B1 to the arc centre C
ARC_CENTRE = (0.0, -H1)
A1 = (-D1 / 2.0, 0.0)
B1 = (D1 / 2.0, 0.0)
# A2/B2 lie on the lines C -> A1 and C -> B1, R_C2 - R_C1 further out.
A2 = (-D2 / 2.0, R_C2 * math.cos(ALPHA) - H1)
B2 = (D2 / 2.0, A2[1])
PIN_HOLES = {"A1": A1, "B1": B1, "A2": A2, "B2": B2}
APEX_Y = R_C1 - H1  # the spindle on the carrier's +Y centreline (inner pass)

# In-situ HUB: from the apex, move the table +Y by HUB_OFFSET.
HUB = (0.0, HUB_RADIUS - H1)
HUB_OFFSET = HUB_RADIUS - R_C1

# --- Riser (6 mm acetal, cut on the jig by the 9/16 in cutter) ⚙ ------------
RISER_INNER_RADIUS = R_C1 + RISER_CUTTER_DIA / 2.0
RISER_OUTER_RADIUS = R_C2 - RISER_CUTTER_DIA / 2.0
# Acceptance on the riser: HUB pin to the riser's inner edge at the apex.
RISER_HUB_CHECK = HUB_RADIUS - RISER_INNER_RADIUS
SAGITTA_CHORD = 300.0


def sagitta(radius: float, chord: float = SAGITTA_CHORD) -> float:
    """Arc height over ``chord`` for a circle of ``radius``."""
    half = chord / 2.0
    return radius - math.sqrt(radius * radius - half * half)


RISER_SAGITTA = (sagitta(RISER_INNER_RADIUS), sagitta(RISER_OUTER_RADIUS))
PART_SAGITTA = (sagitta(R_INNER), sagitta(R_OUTER))


def on_hub_radius(chord_x: float) -> tuple[float, float]:
    """The carrier-frame point at chord X on the R``HUB_RADIUS`` centreline."""
    return (chord_x, math.sqrt(HUB_RADIUS**2 - chord_x**2) - H1)


def at_arc_station(
    arc_length: float, radius: float = HUB_RADIUS
) -> tuple[float, float]:
    """The carrier-frame point ``arc_length`` along ``radius`` from the apex."""
    angle = arc_length / radius
    return (radius * math.sin(angle), radius * math.cos(angle) - H1)


# Four countersunk screws hold the riser, two in each half (the HUB
# clearance cuts the self-cut band in two): 40 and 120 of arc either side of
# the apex on the band's centreline, RISER_SCREW_RADIUS. The repo's threads
# are UNC (memory/fastener-policy-us-customary.md), and they are ASME B18.6.3
# #4-40 x 5/8 82-degree flat-head machine screws (head Ø0.225 in max), not
# the plan's M4: an M4 countersunk head (Ø8.96 max) would leave under 1.5 of
# acetal to a self-cut edge. A B18.3 socket flat head (Ø0.255 in) does not fit
# the riser's countersink either (TrammelJig, jig-r5).
RISER_SCREW = "#4-40"
RISER_SCREW_HEAD_DIA = round(0.225 * INCH, 9)
# The riser's 82-degree countersink mouth, printed at 2 places (.25), and the
# places the carrier's riser taps (MHA-CH-06-TL-21) print their stations at:
# the riser's holes are spotted through those taps at assembly, so the tap's
# station band places each countersink. RISER_SCREW_WALLS judges both bands.
RISER_CSK_DIA = 6.35  # .25
RISER_CSK_PLACES = 2
RISER_TAP_STATION_PLACES = 3
RISER_SCREW_RADIUS = (RISER_INNER_RADIUS + RISER_OUTER_RADIUS) / 2.0
RISER_SCREW_ARC_STATIONS = (40.0, 120.0)
RISER_SCREWS = tuple(
    (sign * x, y)
    for x, y in (
        at_arc_station(s, RISER_SCREW_RADIUS) for s in RISER_SCREW_ARC_STATIONS
    )
    for sign in (-1.0, 1.0)
)
# Rule 17 at worst case: the countersink mouth at its band's top, the carrier
# tap's station at its X and Y band edges both pushed radially (|sin| + |cos|
# of the bearing from the arc centre), to the inner and outer self-cut edges.
_RISER_CSK_MOUTH_MAX = (RISER_CSK_DIA + printed_band_mm(RISER_CSK_PLACES, unit=RISER_UNIT)) / 2.0
_RISER_RADIAL_SHIFT = max(
    printed_band_mm(RISER_TAP_STATION_PLACES, unit=CARRIER_UNIT)
    * (abs(x) + abs(y + H1))
    / RISER_SCREW_RADIUS
    for x, y in RISER_SCREWS
)
RISER_SCREW_WALLS = (
    RISER_SCREW_RADIUS
    - RISER_INNER_RADIUS
    - _RISER_CSK_MOUTH_MAX
    - _RISER_RADIAL_SHIFT,
    RISER_OUTER_RADIUS
    - RISER_SCREW_RADIUS
    - _RISER_CSK_MOUTH_MAX
    - _RISER_RADIAL_SHIFT,
)
# The milled riser blank, 13.40 x 1.60 in, lies square on the carrier with its
# corner at RISER_BLANK_ORIGIN (carrier frame, y .63). The self-cut band runs
# from y 21.40 (inner edge at the blank's ends) to 50.90 (outer edge at the
# apex), nominally at least 5 inside both long edges. Rule 17 reads the
# blank's edges, so its size prints .XX (.X is for unread features only).
RISER_BLANK_LENGTH = 340.36  # 13.40
RISER_BLANK_WIDTH = 40.64  # 1.60
RISER_BLANK_ORIGIN = (-RISER_BLANK_LENGTH / 2.0, 16.002)  # y .63
RISER_BAND_Y = (
    math.sqrt(RISER_INNER_RADIUS**2 - (RISER_BLANK_LENGTH / 2.0) ** 2) - H1,
    RISER_OUTER_RADIUS - H1,
)

# --- Blank, tip lands, CL/CR ⚙ ------------------------------------------------
BLANK_LENGTH = 350.0
BLANK_WIDTH = 40.0
# The tip lands are radial lines through the top arc's ends.
TIP_ANGLE = (rocker.TOP_ARC_LEN / 2.0) / rocker.R_TOP
# CL (a 6 mm dowel in a tooling hole) and CR (the clamp screw) sit in the
# blank's end waste on the hub radius, angularly midway between the tip land
# and the blank's square end, so the saw cut that drops the waste has room on
# both sides of the hole.
_BLANK_END_ANGLE = math.asin((BLANK_LENGTH / 2.0) / HUB_RADIUS)
CL_ANGLE = (TIP_ANGLE + _BLANK_END_ANGLE) / 2.0
CR = on_hub_radius(HUB_RADIUS * math.sin(CL_ANGLE))
CL = (-CR[0], CR[1])
# The same points from the hub (the strap's own frame for the T1 setup):
CL_FROM_HUB = (CL[0] - HUB[0], CL[1] - HUB[1])
CR_FROM_HUB = (CR[0] - HUB[0], CR[1] - HUB[1])

# --- Sweep and stops ⚙ --------------------------------------------------------
# Each pass runs until the part cutter has passed the tip land by its own
# radius plus RUN_OUT. The riser's 9/16 cutter rides the same centre circle
# with a larger radius, so the same stops clear the part cutter's whole path.
RUN_OUT = 3.0


def sweep_angle(cutter_centre_radius: float) -> float:
    """Half sweep (radians, about C) of the cutter centre for one pass."""
    return TIP_ANGLE + (PART_CUTTER_DIA / 2.0 + RUN_OUT) / cutter_centre_radius


SWEEP = {"inner": sweep_angle(R_C1), "outer": sweep_angle(R_C2)}
PASS_RADIUS = {"inner": R_C1, "outer": R_C2}


def pin_station(radius: float, theta: float) -> tuple[float, float]:
    """(s_A, s_B): pin distances from the spindle along each rail.

    ``theta`` is the cutter centre's angle about C from the carrier's +Y
    centreline, positive toward B. Pin A sits on the circle ALPHA from the
    apex, so the chord from the spindle to A subtends ALPHA + theta.
    """
    return (
        2.0 * radius * math.sin((ALPHA + theta) / 2.0),
        2.0 * radius * math.sin((ALPHA - theta) / 2.0),
    )


def pin_travel(pass_name: str) -> tuple[float, float]:
    """(min, max) pin station along either rail over one pass's sweep."""
    radius, theta = PASS_RADIUS[pass_name], SWEEP[pass_name]
    s_a, s_b = pin_station(radius, theta)
    return (s_b, s_a)


PIN_TRAVEL = {name: pin_travel(name) for name in PASS_RADIUS}
PIN_S_MIN = min(lo for lo, _hi in PIN_TRAVEL.values())
PIN_S_MAX = max(hi for _lo, hi in PIN_TRAVEL.values())
SYMMETRIC_PIN_STATION = {
    name: pin_station(r, 0.0)[0] for name, r in PASS_RADIUS.items()
}

# --- Rail alignment targets ⚙ -------------------------------------------------
# Indicator readings of a pin in the pivot block, machine XY, at stations s:
# round inches (a free choice inside the feed carriage's travel).
ALIGNMENT_STATIONS = tuple(s * INCH for s in (4.0, 8.0, 12.0, 15.0))


def rail_point(rail: int, s: float, lateral: float = 0.0) -> tuple[float, float]:
    """Machine XY of a point ``s`` along rail ``rail`` (1 = -X side, 2 = +X).

    ``lateral`` is measured square to the pin-line, positive toward the
    column (+Y side of the line).
    """
    sign = -1.0 if rail == 1 else 1.0
    c, n = math.cos(HALF_ALPHA), math.sin(HALF_ALPHA)
    return (sign * (s * c + lateral * n), -s * n + lateral * c)


ALIGNMENT_TARGETS = {
    s: {"rail 1": rail_point(1, s), "rail 2": rail_point(2, s)}
    for s in ALIGNMENT_STATIONS
}

# --- Sensitivities (for the notes beside the tight bands) --------------------
# dR/dalpha = -D cos(alpha) / (2 sin^2 alpha) at D1.
RADIUS_PER_TENTH_DEG = (
    D1 * math.cos(ALPHA) / (2.0 * math.sin(ALPHA) ** 2) * math.radians(0.1)
)
RADIUS_PER_SPACING = 1.0 / (2.0 * math.sin(ALPHA))  # dR/dD
# Diametral: the .3760-.3765 REAM_SLIDE carrier hole on the bought .375 -.001/0
# shoulder (carrier_spec PIN_CLEARANCE_MIN/MAX, .0010-.0025).
SHOULDER_CARRIER_CLEARANCE = (0.0254, 0.0635)
RADIUS_FROM_SHOULDER_CLEARANCE = (
    RADIUS_PER_SPACING * SHOULDER_CARRIER_CLEARANCE[1]
)

# --- Bought hardware (catalogue values; not modelled in detail) --------------
# HIWIN HGR15R rail, cut to 440 (inventory, Main 2026-10-16). The cut is a
# special order: the symmetric 40 end distance below is the order
# requirement the bars are drilled to, to be confirmed by the supplier.
RAIL_LENGTH = 440.0
RAIL_WIDTH = 15.0
RAIL_HEIGHT = 15.0
RAIL_HOLE_PITCH = 60.0
RAIL_HOLE_COUNT = 7
RAIL_HOLE_END = (RAIL_LENGTH - (RAIL_HOLE_COUNT - 1) * RAIL_HOLE_PITCH) / 2.0
# The rails' M4 holes (Ø4.5, Ø7.5 counterbore) take #8-32 UNC socket screws
# (Ø4.17), keeping the repo's UNC thread policy. A 3/4 in screw seats on the
# counterbore floor 9.7 above the rail base, so 9.35 of it engages the bar.
RAIL_SCREW = "#8-32"
RAIL_SCREW_LENGTH = round(0.75 * INCH, 9)
RAIL_SCREW_SEAT_ABOVE_BASE = 9.7
# HIWIN HGH15CA carriage (Z0 preload).
CARRIAGE_HEIGHT = 28.0  # rail seat to carriage top (H)
CARRIAGE_UNDER = 4.3  # rail seat to the carriage's underside (H1)
CARRIAGE_WIDTH = 34.0
CARRIAGE_LENGTH = 61.4  # over the end seals
CARRIAGE_BOLT_SPAN = (26.0, 26.0)  # (along, across), four M4 tapped
CARRIAGE_BOLT = "M4"

# --- Rails on the bars --------------------------------------------------------
# Each rail's near end stops RAIL_NEAR_S from the spindle axis (brief); rail
# and bar are the same length and flush.
RAIL_NEAR_S = 15.0
RAIL_FAR_S = RAIL_NEAR_S + RAIL_LENGTH
# A carriage stays fully on its rail: centre within half its length of an end.
CARRIAGE_S_RANGE = (
    RAIL_NEAR_S + CARRIAGE_LENGTH / 2.0,
    RAIL_FAR_S - CARRIAGE_LENGTH / 2.0,
)
# The unchanged pivot station preserves the carrier's four holes and both
# sweeps; the simplified block locates a shoulder screw at that same station.
PIN_OFFSET = -32.0  # pin s minus carriage-centre s
CARRIAGE_TRAVEL = (PIN_S_MIN - PIN_OFFSET, PIN_S_MAX - PIN_OFFSET)
END_STOPS = {
    name: (lo - PIN_OFFSET, hi - PIN_OFFSET) for name, (lo, hi) in PIN_TRAVEL.items()
}

# --- Height stack (machine Z, table top = 0) ---------------------------------
# Issue #290: the jig's fabricated sheets print decimal inch. Each height is
# the exact millimetre value of its printed inch nominal (.XX grid).
# The base bars are faced on both large faces from the 1/2 in 6061-T6511 bar
# (BASE_BAR_STOCK_THICK) to BASE_BAR_THICK (owner ruling 2026-10-30, option A):
# each face is a static locating seat (the table under bar 1, the rail and the
# TL-28 brackets on it; bar 2 is the same part turned over). Like the carrier,
# the finished size takes its printed title-block band, not STOCK. A seat in
# the height stack prints .XX: the inch .X (+/-.1) is for unread features only.
BASE_BAR_STOCK_THICK = round(0.5 * INCH, 9)
BASE_BAR_THICK = 11.938  # .47
BASE_BAR_THICK_PLACES = 2
BASE_BAR_THICK_BAND = printed_band_mm(BASE_BAR_THICK_PLACES, unit=BASE_BAR_UNIT)
PIVOT_BLOCK_HEIGHT = 24.384  # .96, finished from 1 in stock
# Nominal fitted pack: five .008 shims (TL-VN-79) per support; the shoulder
# seat depth leaves .046 unshimmed, so the pack closes the nominal head gap
# to .006.
PIVOT_SHIM_PACK = 1.016  # 5 x .008
PIVOT_SPACER_LENGTH = 15.875  # .625 loose purchased spacer (TL-VN-78)
PIVOT_SUPPORT_HEIGHT = PIVOT_SHIM_PACK + PIVOT_SPACER_LENGTH
# Finished dimensions, not purchased stock: face 1/2 in 6061-T6511 bar to
# CARRIER_THICK and 1/4 in acetal to RISER_THICK (#1619). Both native drawing
# dimensions take their printed title-block band, not a supplier-stock
# tolerance. CL locator height is set from the actual riser at assembly.
CARRIER_THICK = 11.938  # .47
CARRIER_THICK_PLACES = 2
CARRIER_THICK_BAND = printed_band_mm(CARRIER_THICK_PLACES, unit=CARRIER_UNIT)
RISER_THICK = 6.096  # .24
RISER_THICK_PLACES = 2
RISER_THICK_BAND = printed_band_mm(RISER_THICK_PLACES, unit=RISER_UNIT)
# The strap is faced to its finished 2.5 (S0) before it goes on the jig (T3).
STRAP_THICK = rocker.ARM_THICKNESS
RAIL_SEAT_Z = BASE_BAR_THICK
CARRIAGE_TOP_Z = RAIL_SEAT_Z + CARRIAGE_HEIGHT
PIVOT_BLOCK_TOP_Z = CARRIAGE_TOP_Z + PIVOT_BLOCK_HEIGHT
CARRIER_UNDERSIDE_Z = PIVOT_BLOCK_TOP_Z + PIVOT_SUPPORT_HEIGHT
CARRIER_TOP_Z = CARRIER_UNDERSIDE_Z + CARRIER_THICK
# Vertical rail clearance for through-screw tips that are also clear of the
# pivot blocks in plan; their individual specs check that separate envelope.
CARRIER_TO_RAIL_GAP = CARRIER_UNDERSIDE_Z - (RAIL_SEAT_Z + RAIL_HEIGHT)

# --- PM-30MV table and hold-downs --------------------------------------------
TABLE_LENGTH = round(33.0 * INCH, 9)  # 838.2
TABLE_WIDTH = round(8.25 * INCH, 9)  # 209.55
TSLOT_PITCH = round(2.5 * INCH, 9)  # 63.5, three slots
TSLOT_WIDTH = 14.0
THROAT_TO_COVER = round(7.5 * INCH, 9)  # spindle centreline to the pleated cover
# Base bar: 6061-T6511 flat milled from the owned 1/2 x 6 bar (OnlineMetals
# 1173), rail-length long, the rail off its centreline. The user's 2026-10-17
# ruling (a) widened it from 1/2 x 4 so the leadscrew's TL-28 end brackets
# (PR C4) stand wholly on bar 1 instead of cantilevering past its edge: the
# column-side edge sits BASE_BAR_COLUMN_EDGE off the rail axis (+lateral,
# toward the column on both rails) and the operator-side edge takes the rest
# of the width. The 2026-10-30 ruling set the width to 5.50, inside the 6 in
# vise's stock hard jaws (5 3/4 in capacity, shop inventory
# ``fixtures.vise-pm-6.opening_in``); owner ruling #2083 mills it to width on
# edge in the vise from the 1/2 x 6 bar, no bandsaw rip.
BASE_BAR_WIDTH_IN = 5.5
BASE_BAR_WIDTH = round(BASE_BAR_WIDTH_IN * INCH, 9)  # 139.7, milled
BASE_BAR_COLUMN_EDGE = round(3.5 * INCH, 9)  # lateral +88.9
BASE_BAR_OPERATOR_EDGE = BASE_BAR_COLUMN_EDGE - BASE_BAR_WIDTH  # lateral -50.8
# The rail's 440 cut printed on the bar's .XX grid: the rail overhangs the
# bar's far end by .07 mm, inside the length's band.
BASE_BAR_LENGTH = 439.928  # 17.32
# Two 1/2-13 hold-down studs per bar in .53 slots across the bar, one each
# side of the rail, outside the carriage's sweep. Their stations put both on
# T-slots two pitches apart, the far one inside the table end by a T-nut.
HOLD_DOWN_SLOT_WIDTH = 13.462  # .53
HOLD_DOWN_LATERAL = 37.592  # 1.48: stud axis from the rail axis; + toward the column
# +/- stud travel along each slot (square to the rail). The 2026-10-30 ruling
# cut it from 3.0 so the narrower 5.50 bar keeps the far slot's rule-17 wall
# to its operator-side edge with every slot still located from -Y.
HOLD_DOWN_ADJUST = 2.032  # .08
# The far slot's bar station is 15.35 (389.89); the near one closes the
# T-slot pitch exactly (a kinematic closure, printed rounded on the bar).
HOLD_DOWN_FAR_S = RAIL_NEAR_S + 389.89
HOLD_DOWN_NEAR_S = HOLD_DOWN_FAR_S - (
    2.0 * TSLOT_PITCH - 2.0 * HOLD_DOWN_LATERAL * math.cos(HALF_ALPHA)
) / math.sin(HALF_ALPHA)
HOLD_DOWN_STUDS = (
    (HOLD_DOWN_NEAR_S, HOLD_DOWN_LATERAL),
    (HOLD_DOWN_FAR_S, -HOLD_DOWN_LATERAL),
)
# Machine Y of the studs (equal on both bars); the table sits centred on the
# middle T-slot.
STUD_Y = tuple(rail_point(1, s, lat)[1] for s, lat in HOLD_DOWN_STUDS)
TABLE_CENTRE_Y = (STUD_Y[0] + STUD_Y[1]) / 2.0


@dataclass(frozen=True)
class CarrierPose:
    """Where the carrier sits in the machine frame for one cutter position."""

    rotation: float  # radians, carrier +X to machine +X, CCW positive
    origin: tuple[float, float]  # machine XY of the carrier-frame origin

    def to_machine(self, point: tuple[float, float]) -> tuple[float, float]:
        c, s = math.cos(self.rotation), math.sin(self.rotation)
        x, y = point
        return (self.origin[0] + c * x - s * y, self.origin[1] + s * x + c * y)


def carrier_pose(pass_name: str, theta: float) -> CarrierPose:
    """The carrier's machine pose with the cutter centre at ``theta`` about C.

    The spindle (machine origin) is the carrier-frame point on the pass's
    cutter-centre circle at angle ``theta``. The carrier turns by theta/2:
    the inscribed angle at each pin rotates by half the central angle.
    """
    radius = PASS_RADIUS[pass_name]
    spindle = (radius * math.sin(theta), radius * math.cos(theta) - H1)
    rotation = theta / 2.0
    c, s = math.cos(rotation), math.sin(rotation)
    origin = (-(c * spindle[0] - s * spindle[1]), -(s * spindle[0] + c * spindle[1]))
    return CarrierPose(rotation, origin)


def pin_pair(pass_name: str) -> tuple[tuple[float, float], tuple[float, float]]:
    return (A1, B1) if pass_name == "inner" else (A2, B2)


# --- Self-checks: the construction closes ------------------------------------
for _name in PASS_RADIUS:
    for _theta in (-SWEEP[_name], 0.0, SWEEP[_name]):
        _pose = carrier_pose(_name, _theta)
        _sa, _sb = pin_station(PASS_RADIUS[_name], _theta)
        for _pin, _rail, _s in zip(pin_pair(_name), (1, 2), (_sa, _sb)):
            _want = rail_point(_rail, _s)
            _got = _pose.to_machine(_pin)
            if math.dist(_want, _got) > 1e-9:
                raise AssertionError(
                    f"{_name} pass: a pin leaves its rail at theta={_theta}"
                )
if not (
    CARRIAGE_S_RANGE[0] <= CARRIAGE_TRAVEL[0]
    and CARRIAGE_TRAVEL[1] <= CARRIAGE_S_RANGE[1]
):
    raise AssertionError("a carriage runs off its rail inside the pass sweep")
if abs((STUD_Y[0] - STUD_Y[1]) - 2.0 * TSLOT_PITCH) > 1e-9:
    raise AssertionError("the hold-down studs do not land two T-slot pitches apart")
if min(RISER_SCREW_WALLS) < WALL_TARGET_MM:
    raise AssertionError("a riser countersink breaks rule 17's .080 wall target")
if not (
    RISER_BLANK_ORIGIN[1] + 5.0 <= RISER_BAND_Y[0]
    and RISER_BAND_Y[1] <= RISER_BLANK_ORIGIN[1] + RISER_BLANK_WIDTH - 5.0
):
    raise AssertionError("the riser's nominal band runs within 5 of a blank edge")
