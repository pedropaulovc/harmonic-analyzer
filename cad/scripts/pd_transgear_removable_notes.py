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
# The pin centres print as REF targets (owner ruling 2026-11-24, fit audit
# question 8): a wheel is accepted by dropping on both seats' pins.  That
# trial bounds the holes' spacing, not how far both lie toward the bore, so
# the web is charged spec.PIN_CENTRE_SHIFT_MAX, the shop's drilled-hole
# location row, never the spacing analysis spec.PIN_LOCATION_TOL (Codjiflo
# P1 on #3485).  The sheet names no easing drill: a wheel that binds is
# renewed (MHA-PD-00).


def _web_worst(pin_hole_dia: float) -> float:
    """Thinnest bore/pin-hole web: both holes at their drilled maximum, the
    pin centre at the shop's drilled-hole location row toward the bore."""
    return (
        seat_geometry.PIN_CIRCLE_RADIUS
        - spec.PIN_CENTRE_SHIFT_MAX
        - (pin_hole_dia + _DRILL_OVERSIZE) / 2.0
        - (spec.BORE_DIA + _DRILL_OVERSIZE) / 2.0
    )


def _floor_in(value_mm: float) -> float:
    """Rounded DOWN to .001 in, so the sheet never states more web than the
    limits give."""
    return math.floor(value_mm / _IN * 1000.0 + 1e-9) / 1000.0


_WEB_WORST = _web_worst(spec.PIN_HOLE_DIA)  # 0.3706 (.0146)
BORE_PIN_WEB_WORST_IN = _floor_in(_WEB_WORST)
if not 0.0 < BORE_PIN_WEB_WORST_IN:
    raise AssertionError("the drive-pin holes break into the bore at print-worst")


def _inch(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch text, ASME style (no leading zero)."""
    return f"{value_mm / _IN:.{places}f}".removeprefix("0")


# The shortfall prints as a plain fact; its governance is RV-01 in
# pd-transgear-removable.yaml (the owner's 2026-11-01 minor exception at
# .018, restated at this value by a delegated ruling 2026-11-24; revisit in
# #2141), never the sheet.
BORE_PIN_WEB_NOTE = (
    f"BORE TO DRIVE-PIN HOLE WEB {_inch(BORE_PIN_WEB_WORST_IN * _IN, 3)} MIN."
)
# The pin holes' location is made to its mates (rule 4): the offsets print as
# REF and the trial on the named pins, their acceptance, prints on the holes'
# own 2X callout (pd_transgear_removable_callouts.PIN_HOLE_CALLOUT), so no
# note line carries it.


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

# Four short lines (rule 7): the sheet draws T24 only, so the third says
# what the other two share; the fourth is the web between those holes.
DRAWING_NOTES = "\n".join(
    (
        "BLANK, 1 EACH: McMASTER "
        + " / ".join(
            f"{spec.BLANK_SKUS[name]} ({name})" for name, _teeth in spec.CONFIGS
        )
        + ".",
        "TEETH, O.D. AND PLATE FACES AS SUPPLIED; HUB REMOVED FLUSH.",
        "BORE AND DRIVE-PIN HOLES SAME ON "
        + " / ".join(name for name, _teeth in spec.CONFIGS)
        + ".",
        BORE_PIN_WEB_NOTE,
    )
)
