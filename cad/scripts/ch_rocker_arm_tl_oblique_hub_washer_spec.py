r"""MHA-CH-06-TL-35: oblique-trammel hub clamp washer, dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  Shop fixture tooling
(cad/docs/subsystem-identities.md): the turned brass washer under the TL-VN-85
low-head screw's Ø5/16 head.  It bears on the MHA-CH-13 strap's top face over
the TL-33 stud's nose and spreads the screw's clamp, so the steel head never
marks the strap.  Brass, softer than the strap's steel, takes the marks itself.

The O.D. is the owner's literal Ø11 (parent ruling 2026-11-06: the model keeps
the exact millimetres; the inch sheet prints .433 at the title block's .XXX).
The bore is a #9 drill, the closest number drill that passes the #10 major,
so the washer stays nearly concentric with the screw.  It does not import the
fastener table (that table imports ``THICK`` from here).

Part frame: washer axis +Z through the origin (``Axis1``, Top Plane x Right
Plane); the strap-side face on the Front Plane (z = 0), the head-side face at
z = THICK.
"""

from __future__ import annotations

import _config
from _hole_spec import NUMBER_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

STEM = "ch-rocker-arm-tl-oblique-hub-washer"
UNIT = drawing_unit(f"parts/{STEM}", _config.parts("ch-rocker-arm-tl-oblique-hub-washer"))
NUMBER = _config.parts("ch-rocker-arm-tl-oblique-hub-washer")["number"]
QUANTITY = 1

OD = 11.0  # the owner's literal; prints .433
OD_PLACES = 3
BORE_DRILL = "#9"
ID = NUMBER_DRILL_MM[BORE_DRILL]  # .196
ID_PLACES = 3
THICK = 1.524  # .06
THICK_PLACES = 2

SCREW_MAJOR = THREAD_MAJOR_MM["#10-24"]
HEAD_DIA = 7.9375  # the TL-VN-85 92220A163 page's Ø5/16 low head

_OD_MIN = OD - printed_band_mm(OD_PLACES, unit=UNIT)
_ID_MAX = ID + drilled_oversize_mm(unit=UNIT)
WALL_MIN = (_OD_MIN - _ID_MAX) / 2.0
if WALL_MIN < WALL_TARGET_MM:
    raise AssertionError("the hub washer wall breaks rule 17's .080 target")
if ID <= SCREW_MAJOR:
    raise AssertionError("the hub washer bore does not pass the #10 screw")
if OD <= HEAD_DIA:
    raise AssertionError("the hub washer does not carry the whole screw head")

# Marked model dimensions and the places the part authors on them.  The end
# view's O.D. moves onto the side view with the thickness (rule 11); the bore
# keeps its DRILL THRU callout in the end view.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"WasherOd", "WasherBore"},
    "Washer": {"WasherThickness"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "WasherProfile": {"WasherOd": OD_PLACES, "WasherBore": ID_PLACES},
    "Washer": {"WasherThickness": THICK_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for names in DRAWING_PRECISION.values() for name, places in names.items()
}
# Rule 12: the bore says what to do; the title block's DRILLED HOLES row is
# its band.
DIMENSION_CALLOUTS: dict[str, str] = {
    "WasherBore": f"{BORE_DRILL} DRILL THRU",
}
