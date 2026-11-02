r"""Pure-data contract for the oblique-trammel jig's acetal riser (MHA-CH-06-TL-24).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). The riser
is screwed flat on the carrier top (MHA-CH-06-TL-21) under the strap blank,
so the cutter that profiles the strap runs out into acetal rather than the
aluminium carrier.

Material and stock: 1/4 in acetal (Delrin), supplier and stock width/length
unselected. Face to .24 (``RISER_THICK``) and mill the blank to 1.60 x 13.40
(``RISER_BLANK_WIDTH`` x ``RISER_BLANK_LENGTH``) at the .XX title-block band:
the rule-17 walls below read the blank's edges.

Issue #290: the sheet prints decimal inch (``UNIT``). Lengths stay physical
millimetres, each fabricated nominal the exact millimetre value of its printed
inch on the printed grid; the hole stations are the carrier's kinematic ones.

Frame (the SolidWorks model): origin at the blank corner, which sits at
``RISER_BLANK_ORIGIN`` ⚙ (y .63) in the carrier frame (origin at the
midpoint of A1-B1, +X A1 to B1, +Y toward the part, Z0 the carrier top).
+X runs along the 13.40 length, +Y across the 1.60 width, +Z up through the
.24 thickness; Z0 is the bottom face (the carrier seat). The axes are parallel
to the carrier's, so every hole position is its carrier-frame position minus
``RISER_BLANK_ORIGIN``.

Hole locations come from the carrier at assembly: the riser is cut in place
on the carrier, so its seven holes are spotted through the carrier's finished
holes and taps (the TL-00 assembly sequence). The sheet prints every station
as a REFERENCE value in parentheses at 2 places, with one note naming the
mate; the model retains the unrounded carrier stations so the clearance holes
and countersinks remain coaxial with the taps and screws. Only hole sizes
carry bands.

Holes, all THRU from the top face:

* 4 x #4 flat-head countersunk clearance (``RISER_SCREW`` ⚙ #4-40): a native
  Hole Wizard #4 normal-fit clearance (the #30 drill, Ø.1285; the repo's UNC
  policy, memory/fastener-policy-us-customary.md) with an 82 degree
  countersink Ø.25 for the ASME B18.6.3 #4-40 x 5/8 flat-head machine screw
  (Ø.225 max, ``RISER_SCREW_HEAD_DIA`` ⚙; a B18.3 socket flat head, Ø.255,
  does not fit), at ``RISER_SCREWS`` ⚙. They take the screws into the
  carrier's #4-40 tapped holes at the same stations. The wizard has no
  countersunk-clearance kind in ``_holes``, so the countersink is a revolved
  cut, as the rocker trammel pivot plate's. The sheet prints the hole size
  from a blanked reference sketch on the top face (``ScrewDia``), with the
  countersink in its callout: the plan shows only the countersink's edges of
  each hole, so a native hole callout there is not the wizard's (farm runs
  jig-r3/r4).
* HUB clearance Ø.47 at ``HUB`` ⚙: passes the purchased HUB gauge pin
  Ø.4000 -.0001/0 (MHA-CH-06-TL-VN-80).
* CL and CR clearance Ø.257 (letter F) at ``CL`` / ``CR`` ⚙: pass the CL
  1/4 dowel (.2503 max) and the CR 1/4-20 clamp screw (.250 major), and leave
  ``CLAMP_BAND_WALLS`` to the self-cut band at the top of the DRILLED HOLES
  band. The outer band wall falls under the .080 target, over the .060
  floor: a stated shortfall, ``CLAMP_WALL_MIN_TEXT`` on the CL/CR callout
  (owner ruling 6, 2026-11-01; RV-01).

The self-cut band (not modelled): the jig cuts the riser in place on its first
passes with the 9/16 riser cutter, leaving an arc band between
``RISER_INNER_RADIUS`` R802.381 ⚙ and ``RISER_OUTER_RADIUS`` R813.619 ⚙ (mm)
about the arc centre. This part models the faced and milled blank only. The
screws lie on the band's centreline ``RISER_SCREW_RADIUS`` R808.0 ⚙; the
rule-17 walls from each countersink mouth (``RISER_CSK_DIA`` ⚙ at its band's
top, the carrier tap at its station band's edges) to the band edges are
``RISER_SCREW_WALLS`` ⚙. The CL/CR walls take the carrier stations' error
about the cut's centre (``CLAMP_STATION_ERROR``): the holes are spotted
through the carrier's, which its sheet locates from A1. The HUB clearance hole
severs the band into two halves, each held by two screws.

No tight bands: every hole size is a clearance at title-block tolerance.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import angular_band_deg, drilled_oversize_mm, printed_band_mm

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-riser",
    _config.parts("ch-rocker-arm-tl-oblique-riser"),
)
if UNIT != trammel.RISER_UNIT:
    raise AssertionError("the riser row and the calculator disagree on its unit")

_XX = printed_band_mm(2, unit=UNIT)
DRILLED_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)
INCLUDED_ANGLE_TOL_DEG = angular_band_deg(unit=UNIT)
# Reference stations (located from TL-21 at assembly) print at 2 places.
STATION_PLACES = 2

# --- Blank (faced and milled from 1/4 in stock) -------------------------------
BLANK_LENGTH = trammel.RISER_BLANK_LENGTH  # 13.40 ⚙
BLANK_WIDTH = trammel.RISER_BLANK_WIDTH  # 1.60 ⚙
BLANK_PLACES = 2
THICKNESS = trammel.RISER_THICK  # .24 ⚙
THICKNESS_PLACES = trammel.RISER_THICK_PLACES
THICKNESS_BAND = trammel.RISER_THICK_BAND
BLANK_ORIGIN = trammel.RISER_BLANK_ORIGIN  # ⚙, carrier frame


def to_riser(point: tuple[float, float]) -> tuple[float, float]:
    """Carrier-frame point -> riser model frame, without presentation rounding."""
    return (
        point[0] - BLANK_ORIGIN[0],
        point[1] - BLANK_ORIGIN[1],
    )


# --- Holes ------------------------------------------------------------------
SCREW_HOLES = tuple(to_riser(p) for p in trammel.RISER_SCREWS)  # ⚙
HUB_HOLE = to_riser(trammel.HUB)  # ⚙
CL_HOLE = to_riser(trammel.CL)  # ⚙
CR_HOLE = to_riser(trammel.CR)  # ⚙

# "#4-40" -> the wizard's "#4" clearance size.
SCREW_SIZE = trammel.RISER_SCREW.split("-")[0]
SCREW_SPEC = HoleSpec(kind="clearance", size=SCREW_SIZE, fit="normal")
SCREW_DIA = CLEARANCE_MM[(SCREW_SIZE, "normal")]  # .1285, the wizard table's #30
# The DRILLED HOLES row bands the drill, so the size prints the #30 drill at 4
# places: Ø.1285 +.004/0 holds the wizard's cut.
SCREW_DIA_PLACES = 4
SCREW_DIA_PRINTED = round(SCREW_DIA / trammel.INCH, SCREW_DIA_PLACES) * trammel.INCH
if not SCREW_DIA_PRINTED - 1e-6 <= SCREW_DIA <= SCREW_DIA_PRINTED + DRILLED_BAND[0]:
    raise AssertionError("the wizard's #4 clearance falls outside its printed band")
SCREW_BODY_DIA = 0.112 * trammel.INCH  # #4 major diameter
SCREW_HEAD_DIA_MAX = trammel.RISER_SCREW_HEAD_DIA  # .225
CSK_ANGLE = 82.0  # the flat head's own included angle
CSK_FLANK_ANGLE = 90.0 - CSK_ANGLE / 2.0  # face to flank, the sketch's
CSK_DIA = trammel.RISER_CSK_DIA  # .25 ⚙
CSK_PLACES = trammel.RISER_CSK_PLACES  # 2 ⚙
HUB_DIA = 11.938  # .470
# Drilled sizes print 3 places so the DRILLED HOLES band lands on their grid.
HUB_PLACES = 3
# CL 1/4 dowel and CR 1/4-20 screw, on the self-cut band: the letter F drill.
CLAMP_DIA = 6.5278  # .257
CLAMP_PLACES = 3

if SCREW_DIA <= SCREW_BODY_DIA:
    raise AssertionError("riser screw hole does not clear the #4 body")
# The smallest printed countersink still sinks the largest head (no head
# proud of the riser top under the strap blank); the largest stays short of
# the bottom face.
if (CSK_DIA - _XX) / 2.0 < SCREW_HEAD_DIA_MAX / 2.0:
    raise AssertionError("#4 head stands proud of the riser top")
CSK_DEPTH_MAX = (CSK_DIA + _XX) / 2.0 / math.tan(math.radians(CSK_ANGLE / 2.0))
if CSK_DEPTH_MAX >= THICKNESS - THICKNESS_BAND:
    raise AssertionError("riser countersink breaks through the blank")
if HUB_DIA <= carrier.HUB_PIN_LIMITS[1]:
    raise AssertionError("the riser's HUB hole does not pass the gauge pin")

HOLES: dict[str, tuple[tuple[float, float], float]] = {
    **{f"screw {i}": (xy, SCREW_DIA) for i, xy in enumerate(SCREW_HOLES, start=1)},
    "HUB": (HUB_HOLE, HUB_DIA),
    "CL": (CL_HOLE, CLAMP_DIA),
    "CR": (CR_HOLE, CLAMP_DIA),
}

# Rule 17 at worst case: every hole (or its countersink) to the blank edges,
# the blank set on the carrier within its stations' 2-place band, on the
# shortest, narrowest blank.
_BLANK_BAND = printed_band_mm(BLANK_PLACES, unit=UNIT)
_POSITION = printed_band_mm(STATION_PLACES, unit=UNIT)
_LENGTH_MIN = BLANK_LENGTH - _BLANK_BAND
_WIDTH_MIN = BLANK_WIDTH - _BLANK_BAND
WALLS_MM: dict[str, float] = {}
for _name, ((_x, _y), _dia) in HOLES.items():
    _r = (
        (CSK_DIA + _XX) / 2.0
        if _name.startswith("screw")
        else (_dia + DRILLED_BAND[0]) / 2.0
    )
    WALLS_MM[f"{_name} to edges"] = min(
        _x - _POSITION - _r,
        _LENGTH_MIN - (_x + _POSITION) - _r,
        _y - _POSITION - _r,
        _WIDTH_MIN - (_y + _POSITION) - _r,
    )
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET_MM:
        raise AssertionError(f"riser {_wall} wall {_mm:.3f} under rule 17's .080")

# CL and CR sit on the hub radius inside the self-cut band, the drill at its
# band's top. Spotted through the carrier's holes, each carries the carrier
# station's error about the cut's centre C (trammel.ARC_CENTRE): its X and Y
# title-block bands, X also half the D1 band (C stands D1/2 from A1, as
# carrier.RISER_WALLS_FROM_A1), each times its direction cosine to C.
_CLAMP_R_MAX = (CLAMP_DIA + DRILLED_BAND[0]) / 2.0
_CLAMP_RADIUS = math.dist(trammel.CL, trammel.ARC_CENTRE)
if abs(math.dist(trammel.CR, trammel.ARC_CENTRE) - _CLAMP_RADIUS) > 1e-9:
    raise AssertionError("CL and CR are not on one radius")


def _radial_station_error(
    point: tuple[float, float], x_name: str, y_name: str
) -> float:
    """The carrier station's worst radial error about C at ``point``."""
    places = carrier.DRAWING_PRECISION_BY_NAME
    x_band = (
        printed_band_mm(places[x_name], unit=carrier.UNIT) + carrier.POSITION_BAND / 2.0
    )
    y_band = printed_band_mm(places[y_name], unit=carrier.UNIT)
    dx, dy = (abs(p - c) for p, c in zip(point, trammel.ARC_CENTRE, strict=True))
    return (dx * x_band + dy * y_band) / _CLAMP_RADIUS


CLAMP_STATION_ERROR = max(
    _radial_station_error(trammel.CL, "ClX", "ClY"),
    _radial_station_error(trammel.CR, "CrX", "CrY"),
)
CLAMP_BAND_WALLS = (
    _CLAMP_RADIUS - _CLAMP_R_MAX - CLAMP_STATION_ERROR - trammel.RISER_INNER_RADIUS,
    trammel.RISER_OUTER_RADIUS - _CLAMP_RADIUS - _CLAMP_R_MAX - CLAMP_STATION_ERROR,
)
# Rule 17 / 20 (owner ruling 6, 2026-11-01, the PN-01 precedent): the outer
# wall's shortfall under the .080 target, over the .060 floor, is accepted and
# stated as plain fact on the CL/CR callout, floored to three places (a MIN
# never rounds up). The window refuses both a wall under the floor and a
# stale statement once the wall reaches the target.
if not WALL_FLOOR_MM < min(CLAMP_BAND_WALLS) < WALL_TARGET_MM:
    raise AssertionError(
        "the riser CL/CR band wall no longer matches its stated shortfall"
    )
CLAMP_WALL_MIN = (
    math.floor(min(CLAMP_BAND_WALLS) / trammel.INCH * 1000.0 + 1e-9)
    / 1000.0
    * trammel.INCH
)
CLAMP_WALL_MIN_TEXT = f"WALL {carrier.inch_text(CLAMP_WALL_MIN, 3)} MIN TO CUT EDGE"
# The smallest drilled hole passes the largest mate.
CL_DOWEL_MAX = carrier.CL_DOWEL_DIA + carrier.CL_DOWEL_BAND[0]
CR_SCREW_MAJOR = THREAD_MAJOR_MM[carrier.CR_THREAD]
if CLAMP_DIA <= max(CL_DOWEL_MAX, CR_SCREW_MAJOR):
    raise AssertionError("the riser CL/CR clearance does not pass its mate")

if not (
    SCREW_HOLES[0][1] == SCREW_HOLES[1][1]
    and SCREW_HOLES[2][1] == SCREW_HOLES[3][1]
    and CL_HOLE[1] == CR_HOLE[1]
):
    raise AssertionError("riser hole pairs are not on common rows")

# Model globals: name -> value (mm). The build sets each and drives from it.
GLOBALS: dict[str, float] = {
    "BlankLength": BLANK_LENGTH,
    "BlankWidth": BLANK_WIDTH,
    # Never a bare "Thickness": SolidWorks refused that global (farm run
    # jig-r1, Add2/Add3 -1); the jig's parts prefix theirs (BarThick, LeverThick).
    "BlankThick": THICKNESS,
    "Screw1X": SCREW_HOLES[0][0],
    "Screw2X": SCREW_HOLES[1][0],
    "Screw3X": SCREW_HOLES[2][0],
    "Screw4X": SCREW_HOLES[3][0],
    "ScrewInnerY": SCREW_HOLES[0][1],
    "ScrewOuterY": SCREW_HOLES[2][1],
    "HubX": HUB_HOLE[0],
    "HubY": HUB_HOLE[1],
    "ClX": CL_HOLE[0],
    "CrX": CR_HOLE[0],
    "ClampY": CL_HOLE[1],
    "HubDia": HUB_DIA,
    "ClampDia": CLAMP_DIA,
    "CskDia": CSK_DIA,
    # The reference circle prints the drill's size; the wizard cuts SCREW_DIA.
    "ScrewDia": SCREW_DIA_PRINTED,
}

# Plain clearance circles on one sketch: (centre, dia, (x, y, size) names,
# (x, y, size) drives). CR's row and size repeat CL's and stay off the print.
CIRCLES: tuple[
    tuple[tuple[float, float], float, tuple[str, str, str], tuple[str, str, str]], ...
] = (
    (HUB_HOLE, HUB_DIA, ("HubX", "HubY", "HubDia"), ('"HubX"', '"HubY"', '"HubDia"')),
    (CL_HOLE, CLAMP_DIA, ("ClX", "ClampY", "ClampDia"),
     ('"ClX"', '"ClampY"', '"ClampDia"')),
    (CR_HOLE, CLAMP_DIA, ("CrX", "CrY", "ClampDia2"),
     ('"CrX"', '"ClampY"', '"ClampDia"')),
)  # fmt: skip

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlankProfile": {"BlankLength", "BlankWidth"},
    "Blank": {"BlankThick"},
    "ScrewHoles": {
        "Screw1X",
        "Screw2X",
        "Screw3X",
        "Screw4X",
        "ScrewInnerY",
        "ScrewOuterY",
    },
    "HoleProfile": {"HubX", "HubY", "ClX", "CrX", "ClampY", "HubDia", "ClampDia"},
    "ScrewHoleReference": {"ScrewDia"},
}
_STATIONS = DRAWING_DIMENSIONS["ScrewHoles"] | {"HubX", "HubY", "ClX", "CrX", "ClampY"}
_SIZE_PLACES = {
    "BlankLength": BLANK_PLACES,
    "BlankWidth": BLANK_PLACES,
    "BlankThick": THICKNESS_PLACES,
    "ScrewDia": SCREW_DIA_PLACES,
    "HubDia": HUB_PLACES,
    "ClampDia": CLAMP_PLACES,
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {
        name: STATION_PLACES if name in _STATIONS else _SIZE_PLACES[name]
        for name in names
    }
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
for _name, _places in DRAWING_PRECISION_BY_NAME.items():
    # Reference stations display at 2 places without moving the model axes.
    if _name in _STATIONS:
        continue
    if not carrier.prints_exactly(GLOBALS[_name], _places):
        raise AssertionError(
            f"riser {_name} {GLOBALS[_name]} does not print as modelled"
        )
if not carrier.prints_exactly(CSK_DIA, CSK_PLACES):
    raise AssertionError("the riser countersink does not print as modelled")

# Every hole is located from the TL-21 carrier at assembly, so its stations
# print as REFERENCE values, parenthesised and untoleranced, and each hole
# callout carries the mate in its last rows (review r7: one row per callout,
# not a general note); only the sizes carry bands. The rows name neither the
# assembly nor a step: the riser builds in the PR before the jig assembly, and
# the assembly's step numbers move as it gains steps.
REFERENCE_DIMENSIONS = frozenset(_STATIONS)
CARRIER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
LOCATE_CALLOUT = f"LOCATE FROM {CARRIER_NUMBER}\nAT ASSEMBLY"
CSK_CALLOUT = (
    f"CSK<MOD-DIAM>{carrier.inch_text(CSK_DIA, CSK_PLACES)} X {CSK_ANGLE:.0f}\u00b0"
)
CALLOUTS_ABOVE = {"ScrewDia": "4X", "ClampDia": "2X"}
# A row height shared by a hole pair prints its count in the reference's
# prefix on one line, "2X (.53)": stacked above the value it overflowed the
# short spans (jig-r6).
ROW_COUNTS = {"ScrewInnerY": "2X", "ScrewOuterY": "2X", "ClampY": "2X"}
if not set(ROW_COUNTS) <= REFERENCE_DIMENSIONS:
    raise AssertionError("a counted row height is not a reference station")
# The hole callouts, one per hole size: the screw hole's carries its
# countersink, and each its location from the carrier.
HOLE_CALLOUTS = ("ScrewDia", "HubDia", "ClampDia")
CALLOUTS_BELOW = {
    "ScrewDia": f"DRILL THRU\n{CSK_CALLOUT}\n{LOCATE_CALLOUT}",
    "HubDia": f"DRILL THRU\nHUB HOLE\n{LOCATE_CALLOUT}",
    "ClampDia": (
        f"DRILL THRU\nCL AND CR HOLES\n{CLAMP_WALL_MIN_TEXT}\n{LOCATE_CALLOUT}"
    ),
}

SURFACE_FINISHES = ()
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
