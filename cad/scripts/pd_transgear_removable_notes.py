"""Drawing-only text for the MHA-PD-009 removable sprocket sheet.

Kept out of ``transgear_removable_spec``: the spec is imported by the chain
solver and the assemblies, and the web's printed worst case reads the title
block's DRILLED HOLES row, which must not enter their recipes.  Only the part
build (which stamps these as properties) and the tests import this module.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import _config
import pd_transgear_removable_spec as spec

# A drilled hole may open by the title block's DRILLED HOLES row; it never
# closes (minus 0).
_DRILL_OVERSIZE = float(_config.title_block("drilled_hole")["plus_mm"])
# Thinnest bore/pin-hole web the printed limits allow: both holes at their
# drilled maximum, the pin centre moved its full location band toward the bore.
_WEB_WORST = (
    spec.PIN_CIRCLE_RADIUS
    - spec.DRIVE_PIN_OFFSET_TOL
    - (spec.PIN_HOLE_DIA + _DRILL_OVERSIZE) / 2.0
    - (spec.BORE_DIA + _DRILL_OVERSIZE) / 2.0
)
# Rounded DOWN, so the sheet never states more web than the limits give.
BORE_PIN_WEB_WORST = math.floor(_WEB_WORST * 100.0 + 1e-9) / 100.0
if BORE_PIN_WEB_WORST <= 0.0:
    raise AssertionError("the drive-pin holes break into the bore at print-worst")
if abs(BORE_PIN_WEB_WORST - 0.47) > 1e-9:
    raise AssertionError("bore/pin-hole web moved off its 0.47 worst case")

# The shortfall prints as a plain fact; its governance is the policy's Named
# exceptions row and this tag, never the sheet.
# Named exception: MHA-PD-009 web (drawing-simplicity-policy.md, "Named exceptions").
BORE_PIN_WEB_NOTE = f"BORE TO DRIVE-PIN HOLE WEB {BORE_PIN_WEB_WORST:.2f} MIN."

CRANKSHAFT_NUMBER = "MHA-DT-011"
KNOB_COLLAR_NUMBER = "MHA-PD-022"


def _per_configuration(render: Callable[[int], str]) -> str:
    """One value per configuration, in ``spec.CONFIGS`` order."""
    return "  /  ".join(render(teeth) for _name, teeth in spec.CONFIGS)


# The sheet's main views draw T24; this block is the whole difference between
# the three configurations, which differ only in their tooth count.  The
# outside diameter is not here: it is the part's BlankDia, printed natively on
# each configuration's view.  The pitch and bottom diameters follow from the
# chain and the ANSI B29.1 tooth form a #25 cutter reproduces, so they are
# reference values.
_GEAR_DATA_ROWS = (
    (
        "CHAIN",
        f"ANSI #25 ROLLER, PITCH {spec.CHAIN_PITCH:.2f}, ROLLER Ø{spec.ROLLER_DIA:.2f}",
    ),
    ("TOOTH FORM (REF)", "ANSI B29.1 #25 STANDARD FORM,"),
    ("", f"ROLLER SEAT R{spec.SEAT_CURVE_R:.2f} ON THE PITCH CIRCLE"),
    ("CONFIGURATION", "  /  ".join(name for name, _teeth in spec.CONFIGS)),
    ("NUMBER OF TEETH", _per_configuration(str)),
    (
        "PITCH DIAMETER (mm, REF)",
        _per_configuration(lambda teeth: f"{spec.pitch_dia(teeth):.2f}"),
    ),
    (
        "BOTTOM DIAMETER (mm, REF)",
        _per_configuration(lambda teeth: f"{spec.bottom_dia(teeth):.2f}"),
    ),
)
GEAR_DATA = "\n".join(
    [
        "SPROCKET DATA",
        *(
            f"{label}:  {value}" if label else f"    {value}"
            for label, value in _GEAR_DATA_ROWS
        ),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "MAKE ONE SPROCKET OF EACH CONFIGURATION IN SPROCKET DATA.",
        f"DRIVE-PIN HOLES SLIP OVER THE PRESSED PINS OF CRANKSHAFT {CRANKSHAFT_NUMBER}",
        f"    AND KNOB DRIVE COLLAR {KNOB_COLLAR_NUMBER}.",
        BORE_PIN_WEB_NOTE,
    )
)
