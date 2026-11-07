r"""MHA-CH-06-TL-52: oblique-trammel hub clamp washer, dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  Shop fixture tooling
(cad/docs/subsystem-identities.md): the turned brass top-hat washer under the
common #8-32 x 3/4 SHCS (McMaster 91251A197) that clamps the MHA-CH-13 strap
at HUB.  Its flange bears on the strap's top face; its spigot drops into the
strap's hub hole, reamed in place on the jig, and locates the washer there.
Brass, softer than the strap's steel, takes the marks itself.

Owner R4 rulings (2026-11-07): the product hole stays main's Ø.4000 strap hub
hole (``ch_rocker_strap_spec.HOLE_DIA`` reamed ``ch_rocker_hub_fit
.STRAP_HOLE_BAND``); the spigot is Ø9.95 ±.05 mm, about .35 mm long, a loose
locating fit in that hole; the bore is a 13/64 drill; the flange keeps the
owner's literal Ø11 with its edges broken .005 MAX.  Partial head bearing at
1 N·m is accepted; this contract carries no bearing-load gate.

Edge treatment keeps the spigot's cylindrical land.  The title block allows a
.010 edge break and an R.040 inside corner, either of which would consume a
.014 spigot, so both are overridden locally: the spigot's end edge is sharp
(no burr), its root to the flange a sharp-turned tool-nose R.003 MAX.  The
strap prints both hub-hole edges sharp, so the hole adds no entry break, and
the root's fillet must stay inside that sharp edge for the flange to seat
flat: at the largest spigot, centred, it does (``ROOT_SEAT_CLEARANCE_MIN``).
The land left under the root radius at the shortest printed spigot is
``SPIGOT_LAND_MIN``.

Part frame: washer axis +Z through the origin (``Axis1``, Top Plane x Right
Plane); the flange's seat (strap-side) face on the Front Plane (z = 0), its
head-side face at z = THICK, the spigot from z = 0 down to z = -SPIGOT_LENGTH.
"""

from __future__ import annotations

import _config
import ch_rocker_strap_spec as strap
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from ch_rocker_arm_spec import inch_text
from ch_rocker_hub_fit import STRAP_HOLE_BAND

STEM = "ch-rocker-arm-tl-oblique-hub-washer"
UNIT = drawing_unit(f"parts/{STEM}", _config.parts("ch-rocker-arm-tl-oblique-hub-washer"))
NUMBER = _config.parts("ch-rocker-arm-tl-oblique-hub-washer")["number"]
QUANTITY = 1
INCH = 25.4
STRAP_NUMBER = strap.NUMBER


def _printed_limits(
    model: float, places: int, band: tuple[float, float] | None = None
) -> tuple[float, float]:
    """(min, max) mm an accepted part may show: the printed nominal and band."""
    lower, upper = printed_deviations(model, places, band, unit=UNIT)
    return model + lower, model + upper


# --- Flange: the owner's literal Ø11 -----------------------------------------
# The O.D. keeps the .XXX row: the jig's holding proof charges half its
# printed band against the owner's 1.5 mm worst-case clearance to both 3/8
# strap-cutter flanks.  The sheet states that function at the size.
OD = 11.0  # the owner's literal; prints .433
OD_PLACES = 3
OD_LIMITS = _printed_limits(OD, OD_PLACES)
CUTTER_CLEARANCE_MIN = 1.5  # mm, the owner's worst-case floor (holding spec)
# The flange thickness is the only washer term in the screw's grip.
THICK = 1.524  # .06
THICK_PLACES = 2
THICK_LIMITS = _printed_limits(THICK, THICK_PLACES)
# Owner: "BREAK EDGES .005 MAX" on the flange's two rims.
FLANGE_EDGE_BREAK_MAX = 0.127  # .005

# --- Spigot: the owner's Ø9.95 ±.05 mm locating land -------------------------
# The owner's millimetre band printed in inch at four places, wholly inside
# 9.90-10.00 mm: Ø.3917 ±.0019 (9.9009-9.9974; ±.0020 would reach 9.8984).
# The model nominal sits on that printed grid (the owner's 9.95 rounds to
# .3917), so the native tolerance's own limits are the printed limits.
SPIGOT_DIA = 9.94918  # .3917
SPIGOT_DIA_PLACES = 4
SPIGOT_DIA_TOL = 0.04826  # ±.0019
SPIGOT_DIA_OWNER_LIMITS = (9.90, 10.00)
SPIGOT_DIA_LIMITS = (SPIGOT_DIA - SPIGOT_DIA_TOL, SPIGOT_DIA + SPIGOT_DIA_TOL)
_SPIGOT_PRINTED = _printed_limits(
    SPIGOT_DIA, SPIGOT_DIA_PLACES, (-SPIGOT_DIA_TOL, SPIGOT_DIA_TOL)
)
if any(abs(a - b) > 1e-9 for a, b in zip(SPIGOT_DIA_LIMITS, _SPIGOT_PRINTED)):
    raise AssertionError("the spigot's native limits differ from its printed limits")
# About .35 mm below the seat face, at the title block's .XXX row.
SPIGOT_LENGTH = 0.3556  # .014
SPIGOT_LENGTH_PLACES = 3
SPIGOT_LENGTH_LIMITS = _printed_limits(SPIGOT_LENGTH, SPIGOT_LENGTH_PLACES)
SPIGOT_END_EDGE_BREAK_MAX = 0.0  # sharp, no burr
SPIGOT_ROOT_RADIUS_MAX = 0.0762  # R.003 MAX sharp-turned tool nose
HEIGHT = THICK + SPIGOT_LENGTH  # seat-face origin: head face to spigot end

# The spigot's mate: main's strap hub hole, both edges sharp on its sheet.
STRAP_HOLE_LIMITS = (
    strap.HOLE_DIA + STRAP_HOLE_BAND[1],
    strap.HOLE_DIA + STRAP_HOLE_BAND[0],
)
STRAP_HOLE_ENTRY_BREAK_MAX = 0.0
SPIGOT_FLOAT_MAX = (STRAP_HOLE_LIMITS[1] - SPIGOT_DIA_LIMITS[0]) / 2.0  # radial
SPIGOT_FLOAT_MIN = (STRAP_HOLE_LIMITS[0] - SPIGOT_DIA_LIMITS[1]) / 2.0
SPIGOT_LAND_MIN = (
    SPIGOT_LENGTH_LIMITS[0]
    - SPIGOT_ROOT_RADIUS_MAX
    - SPIGOT_END_EDGE_BREAK_MAX
    - STRAP_HOLE_ENTRY_BREAK_MAX
)
# The root's fillet runs SPIGOT_ROOT_RADIUS_MAX out onto the seat face; the
# sharp hole edge must lie outside it for the flange to seat flat.  Largest
# spigot centred in the smallest hole.
ROOT_SEAT_CLEARANCE_MIN = (
    (STRAP_HOLE_LIMITS[0] - SPIGOT_DIA_LIMITS[1]) / 2.0 - SPIGOT_ROOT_RADIUS_MAX
)

# --- Bore: 13/64 drilled through -----------------------------------------------
BORE_DRILL = "13/64"
ID = 13.0 / 64.0 * INCH  # 5.159; prints .203
ID_PLACES = 3
BORE_LIMITS = _printed_limits(ID, ID_PLACES, (0.0, drilled_oversize_mm(unit=UNIT)))

WALL_MIN = (SPIGOT_DIA_LIMITS[0] - BORE_LIMITS[1]) / 2.0
if WALL_MIN < WALL_TARGET_MM:
    raise AssertionError("the hub washer spigot wall breaks rule 17's .080 target")
if SPIGOT_FLOAT_MIN <= 0.0:
    raise AssertionError("the hub washer spigot does not enter the strap's hub hole")
if SPIGOT_LAND_MIN <= 0.0:
    raise AssertionError("the hub washer spigot keeps no cylindrical locating land")
if ROOT_SEAT_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the hub washer root fillet holds the flange off the strap")
if OD_LIMITS[0] - 2.0 * FLANGE_EDGE_BREAK_MAX <= STRAP_HOLE_LIMITS[1]:
    raise AssertionError("the hub washer flange does not cover the strap's hub hole")
if not (
    SPIGOT_DIA_OWNER_LIMITS[0] <= SPIGOT_DIA_LIMITS[0]
    and SPIGOT_DIA_LIMITS[1] <= SPIGOT_DIA_OWNER_LIMITS[1]
):
    raise AssertionError("the printed spigot band leaves the owner's 9.95 ±.05 mm")

# Marked model dimensions and the places the part authors on them.  The
# turned outline's diameters and lengths are one Right-plane profile, so the
# side view carries them all (rule 11); the bore keeps its DRILL THRU callout
# in the face view.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"WasherOd", "WasherThickness", "SpigotDia", "SpigotLength"},
    "BoreProfile": {"WasherBore"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "WasherProfile": {
        "WasherOd": OD_PLACES,
        "WasherThickness": THICK_PLACES,
        "SpigotDia": SPIGOT_DIA_PLACES,
        "SpigotLength": SPIGOT_LENGTH_PLACES,
    },
    "BoreProfile": {"WasherBore": ID_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for names in DRAWING_PRECISION.values() for name, places in names.items()
}
# The jig assembly's drawing number (ch_rocker_arm_tl_oblique_jig_assembly_spec
# .DRAWING_NUMBER, not imported: that module imports this one).
JIG_NUMBER = "MHA-CH-06-TL-00"
_EDGE_MAX = inch_text(FLANGE_EDGE_BREAK_MAX, 3)
_ROOT_MAX = inch_text(SPIGOT_ROOT_RADIUS_MAX, 3)
# Rule 12: the bore says what to do; the title block's DRILLED HOLES row is
# its band.  The O.D. says what its .XXX row protects (rule 4) and carries the
# owner's flange edge break.  The spigot's band names its mate (rule 4), the
# strap hole's limits REF (the strap's sheet controls them).  The spigot
# length carries the two local edge limits and the reason they override the
# title block (rule 7).
DIMENSION_CALLOUTS: dict[str, str] = {
    "WasherBore": f"{BORE_DRILL} DRILL THRU",
    "WasherOd": (
        f"MAX KEEPS {CUTTER_CLEARANCE_MIN:.1f} MM MIN TO\n"
        f"3/8 STRAP CUTTER SWEEP\nON JIG {JIG_NUMBER}\n"
        f"BREAK EDGES {_EDGE_MAX} MAX"
    ),
    "SpigotDia": (
        f"LOCATES IN STRAP {STRAP_NUMBER}\n"
        f"HUB HOLE ({inch_text(STRAP_HOLE_LIMITS[0], 4)}-"
        f"{inch_text(STRAP_HOLE_LIMITS[1], 4)} REF)"
    ),
    "SpigotLength": (
        "END EDGE SHARP, NO BURR;\n"
        f"ROOT R{_ROOT_MAX} MAX: SEATS\n"
        "FLAT, KEEPS LOCATING LAND"
    ),
}
