r"""MHA-164 transgear-arm: the drawing contract of the made steel arm.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Every number is ``transgear_arm_geometry``'s (the numbers authority
the plate, the pivot hardware and the paper-drive assembly share); this
module adds only what the sheet needs: the printed places of each marked
dimension, the explicit model bands, and the printed callout text.

Part frame (``transgear_arm_geometry``): origin on the pivot axis P on the
FRONT face; +X along the centreline to the square end; +Y toward the upper
tangent edge; +Z through the thickness to the REAR face (z = THICKNESS).
"""

from __future__ import annotations

import transgear_pin_spec as PIN
from transgear_arm_geometry import (
    BAND_X,
    BAND_XX,
    BAND_XXX,
    HOLE_POSITION_BAND,
    PIN_BORE_DIA_MAX,
    PIN_BORE_DIA_MIN,
    PIN_HOLE_DEPTH_BAND,
    PIVOT_BORE_DIA_BAND,
    PIVOT_END_R,
    PLATE_TAP_CSK_DIA,
    SPOT_FACE_DIA_GROWTH,
    SPOT_FACE_FLOOR_BAND,
    STOCK_THICKNESS_IN,
    TAP_CSK_ANGLE_DEG,
    TIP_STATION,
    TIP_STATION_BAND,
)

# The general-tolerance band each printed place count claims (the title-block
# rows the geometry module hard-codes, policy rule 12).
BAND_BY_PLACES: dict[int, float] = {1: BAND_X, 2: BAND_XX, 3: BAND_XXX}

# Places each printed dimension carries (contract §3.1 / §12):
# the hull radius and the end-face width are routine .X; the tip station is
# .XX (R9-23: at .X the latch pin's full diameter can stop inside the hook
# strip, see ``transgear_arm_geometry.TIP_STATION``); the thickness is the
# ground stock's, printed to two places as a reference (the stock band
# governs it, ``STOCK_TEXT_PREFIX``); the pivot bore is a .XXX fit; the
# latch-pin hole and the pin bore print .XXX under their explicit ream
# bands; the hole stations and the pin height are .XXX positions under the
# explicit ±HOLE_POSITION_BAND; the spot face prints its explicit bands; the
# pin-hole depth is .XX, the band the pin's grip and proud range are judged
# at (``PIN_HOLE_DEPTH_BAND``).
OUTLINE_PLACES = 1
TIP_STATION_PLACES = 2
THICKNESS_PLACES = 2
PIVOT_BORE_PLACES = 3
SPOT_FACE_DIA_PLACES = 3
SPOT_FACE_FLOOR_PLACES = 2
STATION_PLACES = 3
PIN_HOLE_DIA_PLACES = 3
PIN_BORE_DIA_PLACES = 3
PIN_HOLE_DEPTH_PLACES = 2

# The places must claim the bands the geometry module's walls and the
# hanger joints were judged at.
for _label, _places, _band in (
    ("tip station", TIP_STATION_PLACES, TIP_STATION_BAND),
    ("pivot bore", PIVOT_BORE_PLACES, PIVOT_BORE_DIA_BAND),
    ("latch-pin hole depth", PIN_HOLE_DEPTH_PLACES, PIN_HOLE_DEPTH_BAND),
):
    if abs(BAND_BY_PLACES[_places] - _band) > 1e-9:
        raise AssertionError(
            f"MHA-164 {_label} prints {_places} places (±{BAND_BY_PLACES[_places]}),"
            f" not the ±{_band} its walls assume"
        )

# Explicit model bands, (upper, lower) deviations where one-sided.
# The counterbore only cuts oversize (drilled-hole row).
SPOT_FACE_DIA_BAND = (SPOT_FACE_DIA_GROWTH, 0.0)
# Floor from the FRONT face: the pivot head's end play (contract §13).
SPOT_FACE_FLOOR_TOLERANCE = SPOT_FACE_FLOOR_BAND
# Pin, plate-tap and latch-pin positions (contract §12 row 457).
HOLE_POSITION_TOLERANCE = HOLE_POSITION_BAND

# --- Printed text -------------------------------------------------------------
# The thickness is the stock's: it prints "5/16 (7.94) GROUND STOCK", prefix
# and suffix around the imported model value, which the parentheses mark as
# reference, so the title block's .XX band never applies to it.
STOCK_TEXT_PREFIX = f"{STOCK_THICKNESS_IN} ("
STOCK_TEXT_SUFFIX = ") GROUND STOCK"
_CSK = f"{TAP_CSK_ANGLE_DEG:.0f}\u00b0 CSK \u00d8"
PLATE_TAP_CSK_CALLOUT = f"{_CSK}{PLATE_TAP_CSK_DIA:.1f} MAX BOTH SIDES"
SPOT_FACE_CALLOUT = "COUNTERBORE, REAR FACE"
# Two short lines: the text stands under the section's pivot end, inside the
# left border.
FLOOR_DEPTH_CALLOUT = "FLOOR FROM\nFRONT FACE"
# The bore runs on the MHA-168 shoulder: a fit bore, so it is reamed.
PIVOT_BORE_CALLOUT = "REAM THRU"

# --- The MHA-179 pin's press in the reamed bore at S (R9-68) -----------------
# This module imports both the arm geometry and the pin spec (the pin spec
# imports the geometry, so the geometry cannot import it back).
PIN_PRESS_INTERFERENCE = (
    round(PIN.DIA_MIN - PIN_BORE_DIA_MAX, 6),
    round(PIN.DIA_MAX - PIN_BORE_DIA_MIN, 6),
)
if PIN_PRESS_INTERFERENCE != (0.010, 0.026):
    raise AssertionError(
        f"MHA-164 pin bore press on MHA-179 is {PIN_PRESS_INTERFERENCE}, "
        "not 0.010..0.026"
    )
# Three short lines under the Ø: the operation, the mating pin, the press.
PIN_BORE_CALLOUT = "\n".join(
    (
        "REAM THRU",
        f"PRESS FIT PIN {PIN.PIN_NUMBER}",
        f"{PIN_PRESS_INTERFERENCE[0]:.3f}/{PIN_PRESS_INTERFERENCE[1]:.3f} INTERFERENCE",
    )
)


def engagement_line(worst_mm: float, worst_d: float) -> str:
    """The installed full-thread engagement a tap callout states: the
    worst-case length and its multiple of the major diameter, each floored
    to two places (a MIN never rounds up), as the policy's rows state it."""
    mm = int(worst_mm * 100.0 + 1e-9) / 100.0
    d = int(worst_d * 100.0 + 1e-9) / 100.0
    return f"ENGAGEMENT {mm:.2f} MIN ({d:.2f}D)"


# The true overall, pivot-end extreme to the square end, prints as a
# reference; a derived reference has no part-side places, so the spec owns
# its digit.
OVERALL_LENGTH = PIVOT_END_R + TIP_STATION
DRAWING_REFERENCE_PRECISION = 1
# The pin goes in to the hole's flat floor, which sets its proud length.
PIN_HOLE_CALLOUT = "\n".join(
    ("BLIND FLAT-BOTTOM REAM", "PRESS FIT LATCH PIN MHA-169", "TO HOLE FLOOR")
)

ISO_VIEW_SCALE = (1, 2)
ISOMETRIC_VIEW_NOTE = f"ISOMETRIC VIEW SCALE {ISO_VIEW_SCALE[0]}:{ISO_VIEW_SCALE[1]}"

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).  The hole stations live in the blanked
# ``StationReference`` sketch: the Hole Wizard placement sketches that drive
# the taps are not importable, and the pin bore's station prints with them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmOutline": {"PivotEndR", "TipStation", "EndWidth"},
    "Arm": {"Depth"},
    "PivotBoreProfile": {"PivotBoreDia"},
    "PinBoreProfile": {"PinBoreDia"},
    "SpotFaceProfile": {"SpotFaceDia", "FloorDepth"},
    "StationReference": {"PinStation", "PlateTapStation1", "PlateTapStation2"},
    "PinHoleProfile": {"PinHoleDia", "PinHoleZ"},
    "PinHole": {"PinHoleDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ArmOutline": {
        "PivotEndR": OUTLINE_PLACES,
        "TipStation": TIP_STATION_PLACES,
        "EndWidth": OUTLINE_PLACES,
    },
    "Arm": {"Depth": THICKNESS_PLACES},
    "PivotBoreProfile": {"PivotBoreDia": PIVOT_BORE_PLACES},
    "PinBoreProfile": {"PinBoreDia": PIN_BORE_DIA_PLACES},
    "SpotFaceProfile": {
        "SpotFaceDia": SPOT_FACE_DIA_PLACES,
        "FloorDepth": SPOT_FACE_FLOOR_PLACES,
    },
    "StationReference": {
        "PinStation": STATION_PLACES,
        "PlateTapStation1": STATION_PLACES,
        "PlateTapStation2": STATION_PLACES,
    },
    "PinHoleProfile": {
        "PinHoleDia": PIN_HOLE_DIA_PLACES,
        "PinHoleZ": STATION_PLACES,
    },
    "PinHole": {"PinHoleDepth": PIN_HOLE_DEPTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if {
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
} != {
    (feature, name) for feature, names in DRAWING_DIMENSIONS.items() for name in names
}:
    raise AssertionError("MHA-164 marked dimensions and authored places disagree")
