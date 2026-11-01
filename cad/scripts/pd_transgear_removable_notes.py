"""Drawing-only text for the MHA-PD-09 removable sprocket sheet.

Kept out of ``transgear_removable_spec``: the spec is imported by the chain
solver and the assemblies, and the web's printed worst case reads the title
block's DRILLED HOLES row, which must not enter their recipes.  Only the part
build (which stamps these as properties) and the tests import this module.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pd_transgear_removable_spec as spec
import _sprocket_seat_geometry as seat_geometry
from _printed_tolerance import drilled_oversize_mm

_IN = spec.MM_PER_IN
# A drilled hole may open by the title block's DRILLED HOLES row; it never
# closes (minus 0).
_DRILL_OVERSIZE = drilled_oversize_mm(unit=spec.UNIT)
# Thinnest bore/pin-hole web the printed limits allow: both holes at their
# drilled maximum, the pin centre moved its full location band toward the bore.
_WEB_WORST = (
    seat_geometry.PIN_CIRCLE_RADIUS
    - spec.PIN_LOCATION_TOL
    - (spec.PIN_HOLE_DIA + _DRILL_OVERSIZE) / 2.0
    - (spec.BORE_DIA + _DRILL_OVERSIZE) / 2.0
)  # 0.4849
# Rounded DOWN to .001 in, so the sheet never states more web than the
# limits give.
BORE_PIN_WEB_WORST_IN = math.floor(_WEB_WORST / _IN * 1000.0 + 1e-9) / 1000.0
if BORE_PIN_WEB_WORST_IN <= 0.0:
    raise AssertionError("the drive-pin holes break into the bore at print-worst")


def _inch(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch text, ASME style (no leading zero)."""
    return f"{value_mm / _IN:.{places}f}".removeprefix("0")


# The shortfall prints as a plain fact; its governance is the
# pending ruling issue #1377 and this tag, never the sheet.
# Pending exception ruling: MHA-PD-09 web (#1377).
BORE_PIN_WEB_NOTE = (
    f"BORE TO DRIVE-PIN HOLE WEB {_inch(BORE_PIN_WEB_WORST_IN * _IN, 3)} MIN."
)


def _per_configuration(render: Callable[[int], str]) -> str:
    """One value per configuration, in ``spec.CONFIGS`` order."""
    return "  /  ".join(render(teeth) for _name, teeth in spec.CONFIGS)


# The sheet's main views draw T24; this block is the whole difference between
# the three configurations, which differ only in their tooth count.  The
# outside diameter is not here: it is the part's BlankDia, printed natively on
# each configuration's view.  The pitch and bottom diameters follow from the
# supplied ANSI B29.1 tooth form, so they are reference values, printed to
# .001 in (exempt chain geometry, not snapped).
_GEAR_DATA_ROWS = (
    (
        "CHAIN",
        f"ANSI #25 ROLLER, PITCH {_inch(spec.CHAIN_PITCH, 3)}, "
        f"ROLLER Ø{_inch(spec.ANSI_ROLLER_DIA, 3)}",
    ),
    ("TOOTH FORM (REF)", "AS SUPPLIED, ANSI B29.1 #25 STANDARD FORM;"),
    ("", f"ROLLER SEAT R{_inch(spec.SEAT_CURVE_R, 3)} ON THE PITCH CIRCLE"),
    ("CONFIGURATION", "  /  ".join(name for name, _teeth in spec.CONFIGS)),
    ("NUMBER OF TEETH", _per_configuration(str)),
    (
        "PITCH DIAMETER (REF)",
        _per_configuration(lambda teeth: _inch(spec.pitch_dia(teeth), 3)),
    ),
    (
        "BOTTOM DIAMETER (REF)",
        _per_configuration(lambda teeth: _inch(spec.bottom_dia(teeth), 3)),
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

# The drive-pin holes' mates print at their location callouts (the drawing's
# CALLOUTS); the sheet draws T24 only, so it says what the other two share.
DRAWING_NOTES = "\n".join(
    (
        "BLANK, 1 EACH: McMASTER "
        + " / ".join(
            f"{spec.BLANK_SKUS[name]} ({name})" for name, _teeth in spec.CONFIGS
        )
        + ".",
        "TEETH, O.D. AND PLATE FACES AS SUPPLIED; HUB REMOVED FLUSH.",
        "BORE, DRIVE-PIN HOLES AND PLATE SAME ON "
        + " / ".join(name for name, _teeth in spec.CONFIGS)
        + ".",
        BORE_PIN_WEB_NOTE,
    )
)
