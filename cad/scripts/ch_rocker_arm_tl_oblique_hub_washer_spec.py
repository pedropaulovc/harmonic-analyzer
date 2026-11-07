r"""MHA-CH-06-TL-52: oblique-trammel hub clamp washer, dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  Shop fixture tooling
(cad/docs/subsystem-identities.md): the turned brass top-hat washer under the
common #8-32 x 3/4 SHCS (McMaster 91251A197) that clamps the MHA-CH-13 strap
at HUB.  Its flange bears on the strap's top face; its spigot drops into the
strap's hub hole, reamed in place on the jig, and locates the washer there.
Brass, softer than the strap's steel, takes the marks itself.

Owner R4 rulings (2026-11-07): the product hole stays main's Ø.4000 strap hub
hole (``ch_rocker_strap_spec.HOLE_DIA`` reamed ``ch_rocker_hub_fit
.STRAP_HOLE_BAND``); the spigot, about .35 mm long, is a loose locating fit
in that hole; the bore is a 13/64 drill; the flange keeps the owner's Ø11
with its edges broken .005 MAX.  Owner ruling 2026-11-07 (#2249, option A;
coordinator-approved) puts the spigot on the .001 grid at Ø.391 ±.002 and
keeps the .06 flange, accepting WALL .040 MIN at its .005-broken rims
(the part row's machinist exception RV-01): the small break is what keeps a
seat ring on the strap outside its hub hole.  Partial head bearing at 1 N·m
is accepted; this contract carries no bearing-load gate.

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

import math

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


# --- Flange: the owner's Ø11 -------------------------------------------------
# The O.D. keeps the .XXX row: the jig's holding proof charges its printed
# upper limit against the owner's 1.5 mm worst-case clearance to both 3/8
# strap-cutter flanks.  The sheet states that function at the size.  The
# model sits on the printed grid (the owner's 11 rounds to .433), so the
# native size is the printed nominal.
OD = 10.9982  # .433
OD_PLACES = 3
OD_LIMITS = _printed_limits(OD, OD_PLACES)
CUTTER_CLEARANCE_MIN = 1.5  # mm, the owner's worst-case floor (holding spec)
# The flange thickness is the only washer term in the screw's grip.
THICK = 1.524  # .06
THICK_PLACES = 2
THICK_LIMITS = _printed_limits(THICK, THICK_PLACES)
# Owner: "BREAK EDGES .005 MAX" on the flange's two rims.
FLANGE_EDGE_BREAK_MAX = 0.127  # .005
# The flange's wall at its rims: the thinnest printed flange less both
# breaks, .040, under the .060 floor; accepted by owner ruling 2026-11-07
# (#2249, option A), the part row's machinist exception RV-01.  Every
# thicker .XX flange either stays under the floor or costs the common #8-32 x
# 3/4 its 1.5D full thread in the carrier tap.
FLANGE_WALL_MIN = THICK_LIMITS[0] - 2.0 * FLANGE_EDGE_BREAK_MAX
FLANGE_WALL_MIN_TEXT = f"{math.floor(round(FLANGE_WALL_MIN / INCH * 1000.0, 6)) / 1000.0:.3f}".removeprefix("0")

# --- Spigot: Ø.391 ±.002 on the .001 grid --------------------------------------
# Owner ruling 2026-11-07 (#2249, option A): the owner's Ø9.95 ±.05 mm moves
# onto the .001 grid as Ø.391 ±.002 (9.8806-9.9822).  The model nominal sits
# on that grid, so the native tolerance's own limits are the printed limits.
SPIGOT_DIA = 9.9314  # .391
SPIGOT_DIA_PLACES = 3
SPIGOT_DIA_TOL = 0.0508  # ±.002
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
# The flange's seat ring on the strap outside its hub hole: the smallest
# O.D. at its .005 break over the largest hole, the washer floated fully to
# one side.  The title block's .010 break would leave none.
SEAT_RING_MIN = (
    (OD_LIMITS[0] - STRAP_HOLE_LIMITS[1]) / 2.0 - SPIGOT_FLOAT_MAX - FLANGE_EDGE_BREAK_MAX
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
if SEAT_RING_MIN <= 0.0:
    raise AssertionError("the hub washer flange keeps no seat ring on the strap")

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
# The owner's 1.5 mm floor in the sheet's inches, floored (never overstate a
# minimum): .059.
_CUTTER_MIN_TEXT = f"{math.floor(CUTTER_CLEARANCE_MIN / INCH * 1000.0) / 1000.0:.3f}".removeprefix("0")
# Rule 12: the bore says what to do; the title block's DRILLED HOLES row is
# its band.  The O.D. says what its .XXX row's upper limit protects (rule 4),
# never opening on "MAX", which read as a single limit under the .433.  The
# flange thickness carries the owner's .005 break with the function that
# needs it (the seat ring on the strap) and the floored wall the break leaves
# at the rims (machinist exception RV-01, owner ruling 2026-11-07, #2249).
# The spigot's band names its mate (rule 4), the strap hole's limits REF (the
# strap's sheet controls them).  The spigot length carries the two local edge
# limits and the reason they override the title block (rule 7).
FLANGE_WALL_CALLOUT = f"WALL {FLANGE_WALL_MIN_TEXT} MIN AT RIMS"
DIMENSION_CALLOUTS: dict[str, str] = {
    "WasherBore": f"{BORE_DRILL} DRILL THRU",
    "WasherOd": (
        "UPPER LIMIT KEEPS\n"
        f"{_CUTTER_MIN_TEXT} MIN TO 3/8 STRAP\n"
        f"CUTTER SWEEP ON JIG\n{JIG_NUMBER}"
    ),
    "WasherThickness": (
        f"BREAK EDGES {_EDGE_MAX} MAX:\n"
        "KEEPS SEAT RING ON STRAP;\n"
        f"{FLANGE_WALL_CALLOUT}"
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
