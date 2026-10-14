r"""Pure-data contract for the rocker trammel setting bar (MHA-CH-006-TL-17).

Shop gauge, not a machine part (cad/docs/subsystem-identities.md): inventory
``gauges.rocker-trammel-setting-bar``. The rocker outline template's trammel
(TL-14..16, TL-18) is set to its two scribing radii by dropping its points
into three seats on this bar: the pivot point in H0, the inner scriber in
H800 and the outer scriber in H816. The seat spacings ARE the scribed radii
(inventory members H0-H800 = 800 and H0-H816 = 816), so the two stations are
the bar's only critical sizes, held to the inventory's +-0.05 setting
resolution and dimensioned from H0.

Stock: Online Metals 1018 CF 1/4 x 1 x 36 in (part 7465), used at its supply
length; the seats sit on the bar's lateral centreline with H0 and H816 set
equally in from the ends.

Seats: a 60 deg included (#2 combined drill and countersink) cone over a
5/64 pilot drilled THRU. The pivot point (60 deg included, TL-18) bears on
the cone flank; the 30 deg scriber points (TL-16) centre on the pilot rim.
A blind pilot under the title-block bands could not guarantee either: the
pivot apex could reach a blind floor and the scriber would bottom on it
instead of centring. The through pilot also takes a 5/64 gauge pin for the
inventory's "fitted setting pins" check of the spacings.

Frame: origin on the H0 axis at the seat face; +X along the bar to H800 and
H816; +Y out of the seat face (the bar occupies y = -thickness..0); Z across
the bar, centred.
"""

from __future__ import annotations

import math

from _printed_tolerance import angular_band_deg, drilled_oversize_mm, printed_band_mm

INCH = 25.4
# Online Metals 7465: 1018 cold-finished flat 1/4 x 1 in, sold 36 in long.
BAR_LENGTH = 36.0 * INCH
BAR_WIDTH = 1.0 * INCH
BAR_THICKNESS = 0.25 * INCH
# Seat stations from H0: the trammel's two scribing radii (inventory members).
H800 = 800.0
H816 = 816.0
SEAT_STATIONS = {"H0": 0.0, "H800": H800, "H816": H816}
# The inventory's +-0.05 setting resolution, on each station from H0.
STATION_BAND = (0.05, -0.05)
# H0 and H816 equally in from the bar ends.
H0_FROM_END = (BAR_LENGTH - H816) / 2.0
H0_FROM_SIDE = BAR_WIDTH / 2.0  # seats on the lateral centreline

_X = printed_band_mm(1)
_XX = printed_band_mm(2)
# #2 combined drill and countersink: 3/16 body, 5/64 pilot, 60 deg included.
CENTRE_DRILL_BODY_DIA = 3.0 / 16.0 * INCH
SEAT_HALF_ANGLE_DEG = 30.0
# Printed from the seat face to the flank (a driven reference in the seat
# sketch): for a 60 deg included cone it reads the included angle's own 60.
SEAT_FLANK_ANGLE_DEG = 90.0 - SEAT_HALF_ANGLE_DEG
# Title-block general angular band (no native tolerance on the angle).
SEAT_ANGLE_BAND = (angular_band_deg(), -angular_band_deg())
SEAT_DIA = 4.0
# Model and export both use the printed two-place pilot (one fact).
PILOT_DIA = round(5.0 / 64.0 * INCH, 2)
# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(), 0.0)
_TAN = math.tan(math.radians(SEAT_HALF_ANGLE_DEG))
SEAT_CONE_DEPTH = (SEAT_DIA - PILOT_DIA) / 2.0 / _TAN
if SEAT_DIA + _XX >= CENTRE_DRILL_BODY_DIA:
    raise AssertionError("setting-bar seat mouth runs onto the #2 centre drill body")
if SEAT_DIA - _XX <= PILOT_DIA + DRILLED_BAND[0]:
    raise AssertionError("setting-bar seat cone vanishes into the pilot")
if SEAT_CONE_DEPTH + _XX >= BAR_THICKNESS:
    raise AssertionError("setting-bar seat cone breaks through the bar")

# Trammel points (TL-16, TL-18): 1/4 in drill rod, pivot 60 deg, scribers
# 30 deg included. Each point's cone, not its body, enters the seat.
TRAMMEL_POINT_DIA = 0.25 * INCH
PIVOT_POINT_HALF_ANGLE_DEG = 30.0
SCRIBER_POINT_HALF_ANGLE_DEG = 15.0
if TRAMMEL_POINT_DIA <= SEAT_DIA + _XX:
    raise AssertionError("a trammel point body enters the setting-bar seat")
# The scriber is sharper than the seat, so it centres on the pilot rim.
if SCRIBER_POINT_HALF_ANGLE_DEG >= SEAT_HALF_ANGLE_DEG - SEAT_ANGLE_BAND[0]:
    raise AssertionError("scriber point no longer centres on the pilot rim")
# Through the bar: deepest pivot apex (largest mouth, steepest flank) with
# no floor to reach.
_PIVOT_APEX_MAX = (
    (SEAT_DIA + _XX)
    / 2.0
    / math.tan(math.radians(PIVOT_POINT_HALF_ANGLE_DEG - SEAT_ANGLE_BAND[0]))
)
if _PIVOT_APEX_MAX >= BAR_THICKNESS:
    raise AssertionError("pivot point apex passes the bar's far face")
# The stations stay inside the bar with a full seat wall at each end.
if H0_FROM_END - _X - (SEAT_DIA + _XX) / 2.0 < 2.0:
    raise AssertionError(
        "end seat wall under drawing-guidelines.md rule 17 (walls and webs)"
    )

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    # H0FromSide locates every seat across the bar from its long edge.
    "BarProfile": {"BarLength", "BarWidth", "H0FromEnd", "H0FromSide"},
    "Bar": {"BarThickness"},
    "H0SeatProfile": {"SeatDia", "SeatFlankAngle", "PilotDia"},
    "H800Reference": {"H800X"},
    "H816Reference": {"H816X"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {"BarLength": 1, "BarWidth": 1, "H0FromEnd": 1, "H0FromSide": 1},
    "Bar": {"BarThickness": 2},
    "H0SeatProfile": {"SeatDia": 2, "SeatFlankAngle": 0, "PilotDia": 2},
    "H800Reference": {"H800X": 2},
    "H816Reference": {"H816X": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked setting-bar dimension needs authored places")
# (feature, dimension) -> (upper, lower) native band.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("H800Reference", "H800X"): STATION_BAND,
    ("H816Reference", "H816X"): STATION_BAND,
}
# Childless dimension-carrying sketches the part saves hidden.
REFERENCE_SKETCHES = ("H800Reference", "H816Reference")

SURFACE_FINISHES = ()
DRAWING_NOTES = "NO NICKS OR BURRS AT THE SEATS."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:10"

# prechips fixture solids (prechips.model.FixtureSolid), model frame: the bar
# and each seat's through pilot (the cone is a #2 centre-drill mouth on it).
PRECHIPS_SOLIDS: list[dict] = [
    {
        "name": "bar",
        "shape": "box",
        "note": "1018 CF 1/4 x 1 flat, supply length; seats on the top face",
        "at_mm": [-H0_FROM_END, -BAR_THICKNESS, -BAR_WIDTH / 2.0],
        "size_mm": [BAR_LENGTH, BAR_THICKNESS, BAR_WIDTH],
    },
    *(
        {
            "name": f"{label.lower()}-seat",
            "shape": "cylinder",
            "label": label,
            "note": "60 deg #2 centre-drill seat over a 5/64 pilot drilled through",
            "at_mm": [x, 0.0, 0.0],
            "axis": [0.0, -1.0, 0.0],
            "dia_mm": PILOT_DIA,
            "length_mm": BAR_THICKNESS,
            "void": True,
        }
        for label, x in SEAT_STATIONS.items()
    ),
]
