r"""Pure-data contract for the oblique-trammel jig's acetal riser (MHA-CH-06-TL-24).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). The riser
is screwed flat on the carrier top (MHA-CH-06-TL-21) under the strap blank,
so the cutter that profiles the strap runs out into acetal rather than the
aluminium carrier.

Material and stock: 1/4 in acetal (Delrin), supplier and stock width/length
unselected. Face to 6.0 (``RISER_THICK``) and mill the blank to 40.0 x 340.0
(``RISER_BLANK_WIDTH`` x ``RISER_BLANK_LENGTH``) at the .X title-block band.

Frame (the SolidWorks model): origin at the blank corner, which sits at
``RISER_BLANK_ORIGIN`` = (-170, 16) ⚙ in the carrier frame (origin at the
midpoint of A1-B1, +X A1 to B1, +Y toward the part, Z0 the carrier top).
+X runs along the 340 length, +Y across the 40 width, +Z up through the 6
thickness; Z0 is the bottom face (the carrier seat). The axes are parallel to
the carrier's, so every hole position is its carrier-frame position minus
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
  Hole Wizard #4 normal-fit clearance (the repo's UNC policy,
  memory/fastener-policy-us-customary.md) with an 82 degree countersink for
  the ASME B18.6.3 #4-40 x 5/8 flat-head machine screw (Ø0.225 in max,
  ``RISER_SCREW_HEAD_DIA`` ⚙; a B18.3 socket flat head, Ø0.255 in, does not
  fit), at ``RISER_SCREWS`` ⚙ = (±39.984, 44.287) and (±119.559, 36.382).
  They take the screws into the carrier's #4-40 tapped holes at the same
  stations. The wizard has no countersunk-clearance kind in ``_holes``, so the
  countersink is a revolved cut, as the rocker trammel pivot plate's. The
  sheet prints the hole size from a blanked reference sketch on the top face
  (``ScrewDia``), with the countersink in its callout: the plan shows only the
  countersink's edges of each hole, so a native hole callout there is not the
  wizard's (farm runs jig-r3/r4).
* HUB clearance Ø12 at ``HUB`` ⚙ = (0, 45.526): passes the purchased HUB
  gauge pin Ø10.2000 -0.00254/0 (MHA-CH-06-TL-VN-80).
* CL and CR clearance Ø6.60 at ``CL`` / ``CR`` ⚙ = (∓160.895, 29.350): pass
  the CL Ø6 m6 dowel (6.012 max, 0.29 radial) and the CR 1/4-20 clamp screw
  (6.35 major, 0.125 radial), and leave ``CLAMP_BAND_WALLS`` (2.52 inner, 2.02
  outer) to the self-cut band at the top of the DRILLED HOLES band.

The self-cut band (not modelled): the jig cuts the riser in place on its first
passes with the 9/16 riser cutter, leaving an arc band between
``RISER_INNER_RADIUS`` R802.381 ⚙ and ``RISER_OUTER_RADIUS`` R813.619 ⚙ about the
arc centre. This part models the faced and milled blank only. The screws lie on the
band's centreline ``RISER_SCREW_RADIUS`` R808.0 ⚙; the rule-17 walls from
each countersink mouth (``RISER_CSK_DIA`` ⚙ at its band's top, the carrier tap
at its station band's edges) to the band edges are ``RISER_SCREW_WALLS`` ⚙
(2.07 both). The CL/CR walls take no position error: the holes are spotted
from the carrier and the jig makes the cut. The HUB clearance hole severs the
band into two halves, each held by two screws.

No tight bands: every hole size is a clearance at title-block tolerance.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec
from _printed_tolerance import angular_band_deg, drilled_oversize_mm, printed_band_mm

_X = printed_band_mm(1)
_XX = printed_band_mm(2)
DRILLED_BAND = (drilled_oversize_mm(), 0.0)
INCLUDED_ANGLE_TOL_DEG = angular_band_deg()
# Reference stations (located from TL-21 at assembly) print at 2 places.
STATION_PLACES = 2

# --- Blank (faced and milled from 1/4 in stock) -------------------------------
BLANK_LENGTH = trammel.RISER_BLANK_LENGTH  # 340 ⚙
BLANK_WIDTH = trammel.RISER_BLANK_WIDTH  # 40 ⚙
THICKNESS = trammel.RISER_THICK  # 6 ⚙
THICKNESS_PLACES = trammel.RISER_THICK_PLACES
THICKNESS_BAND = trammel.RISER_THICK_BAND
BLANK_ORIGIN = trammel.RISER_BLANK_ORIGIN  # (-170, 16) ⚙, carrier frame


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
SCREW_DIA = CLEARANCE_MM[(SCREW_SIZE, "normal")]  # 3.264, the wizard table's
# The DRILLED HOLES row bands the drill, so the size prints at 2 places (review
# r5): Ø3.26 +0.10/0 holds the wizard's 3.264 cut.
SCREW_DIA_PLACES = 2
SCREW_DIA_PRINTED = round(SCREW_DIA, SCREW_DIA_PLACES)
if not SCREW_DIA_PRINTED <= SCREW_DIA <= SCREW_DIA_PRINTED + DRILLED_BAND[0]:
    raise AssertionError("the wizard's #4 clearance falls outside its printed band")
SCREW_BODY_DIA = 0.112 * trammel.INCH  # #4 major diameter
SCREW_HEAD_DIA_MAX = trammel.RISER_SCREW_HEAD_DIA  # 5.715, 0.225 in
CSK_ANGLE = 82.0  # the flat head's own included angle
CSK_FLANK_ANGLE = 90.0 - CSK_ANGLE / 2.0  # face to flank, the sketch's
CSK_DIA = trammel.RISER_CSK_DIA  # 6.3 ⚙
CSK_PLACES = trammel.RISER_CSK_PLACES  # 2 ⚙
HUB_DIA = 12.0
CLAMP_DIA = 6.6  # CL Ø6 dowel and CR 1/4-20 screw, on the self-cut band

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

HOLES: dict[str, tuple[tuple[float, float], float]] = {
    **{f"screw {i}": (xy, SCREW_DIA) for i, xy in enumerate(SCREW_HOLES, start=1)},
    "HUB": (HUB_HOLE, HUB_DIA),
    "CL": (CL_HOLE, CLAMP_DIA),
    "CR": (CR_HOLE, CLAMP_DIA),
}

# Rule 17 at worst case: every hole (or its countersink) to the blank edges,
# the blank set on the carrier within its stations' 2-place band, on the
# shortest, narrowest blank.
_POSITION = printed_band_mm(STATION_PLACES)
_LENGTH_MIN = BLANK_LENGTH - _X
_WIDTH_MIN = BLANK_WIDTH - _X
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
    if _mm < 2.0:
        raise AssertionError(f"riser {_wall} wall {_mm:.3f} under rule 17")

# CL and CR sit on the hub radius inside the self-cut band. Spotted from the
# carrier, cut by the jig: no position error, the drill at its band's top.
_CLAMP_R_MAX = (CLAMP_DIA + DRILLED_BAND[0]) / 2.0
_CLAMP_RADIUS = math.dist(trammel.CL, trammel.ARC_CENTRE)
if abs(math.dist(trammel.CR, trammel.ARC_CENTRE) - _CLAMP_RADIUS) > 1e-9:
    raise AssertionError("CL and CR are not on one radius")
CLAMP_BAND_WALLS = (
    _CLAMP_RADIUS - _CLAMP_R_MAX - trammel.RISER_INNER_RADIUS,
    trammel.RISER_OUTER_RADIUS - _CLAMP_RADIUS - _CLAMP_R_MAX,
)
if min(CLAMP_BAND_WALLS) < 2.0:
    raise AssertionError("a riser CL/CR hole breaks rule 17's 2.0 band wall")
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
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {
        name: STATION_PLACES
        if name in _STATIONS
        else SCREW_DIA_PLACES
        if name == "ScrewDia"
        else THICKNESS_PLACES
        if name == "BlankThick"
        else (2 if "Dia" in name else 1)
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
    _value = GLOBALS[_name]
    if abs(_value - round(_value, _places)) > 1e-9:
        raise AssertionError(f"riser {_name} {_value} does not print as modelled")

# Every hole is located from the TL-21 carrier at assembly, so its stations
# print as REFERENCE values, parenthesised and untoleranced, and each hole
# callout carries the mate in its last rows (review r7: one row per callout,
# not a general note); only the sizes carry bands. The rows name neither the
# assembly nor a step: the riser builds in the PR before the jig assembly, and
# the assembly's step numbers move as it gains steps.
REFERENCE_DIMENSIONS = frozenset(_STATIONS)
CARRIER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
LOCATE_CALLOUT = f"LOCATE FROM {CARRIER_NUMBER}\nAT ASSEMBLY"
CSK_CALLOUT = f"CSK<MOD-DIAM>{CSK_DIA:.{CSK_PLACES}f} X {CSK_ANGLE:.0f}\u00b0"
CALLOUTS_ABOVE = {"ScrewDia": "4X", "ClampDia": "2X"}
# A row height shared by a hole pair prints its count in the reference's
# prefix on one line, "2X (13.35)": stacked above the value it overflowed the
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
    "ClampDia": f"DRILL THRU\nCL AND CR HOLES\n{LOCATE_CALLOUT}",
}

SURFACE_FINISHES = ()
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
