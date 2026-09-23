r"""Pure-data dimensional contract shared by the pinion cam-follower pin and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A short drill-rod stud bonded into the
swing strap's west edge, riding on the eccentric cam collar.  The nominals drive
the part's named equation globals AND the drawing's coordinate math; the
marked-dimension map keeps the part marks and drawing keeps in lockstep
(``test_pinion_cam_pin_drawing.py``).
"""

from __future__ import annotations

from _fit_limits import REAM_H7
from _gtol_spec import SphereFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_cam_pin_geometry import (
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    PIN_DIA as PIN_DIA,
    PIN_LEN as PIN_LEN,
    SEAT_LEN as SEAT_LEN,
)

# U27 (Main, 2026-09-23): no press.  The stud is stock 4 mm drill rod (h9,
# 4.000-3.970) slipped into the MHA-056 strap's reamed H7 follower seat
# (4.000-4.012) and bonded with LOCTITE 638: 0.000-0.042 diametral clearance,
# inside the 0.25 mm bond gap the 638 data sheet allows (the U6 drum-to-arbor
# precedent).  A novice cannot hold the old +/-0.004 press band.
PIN_DIA_BAND = (0.0, -0.03)  # (upper, lower): h9 drill rod
SEAT_NUMBER = "MHA-056"
RETAINING_COMPOUND = "LOCTITE 638"
RETAINING_COMPOUND_MAX_GAP_MM = 0.25
PIN_LENGTH_TOLERANCE_MM = 0.05
CAP_RADIUS_TOLERANCE_MM = 0.05

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia"},
    "Pin": {"Depth"},
    "CapProfile": {"CapR"},
}

# Rule 5: the crown is the surface that runs (it rides the cam OD); the
# bonded shank is a static seat and carries no symbol.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        key="crown",
        roughness_um=MACHINED_UM,
        face=SphereFace(diameter_mm=2.0 * CAP_RADIUS),
    ),
)

SEAT_BAND = REAM_H7
BOND_CLEARANCE_MIN = round(SEAT_BAND[1] - PIN_DIA_BAND[0], 6)
BOND_CLEARANCE_MAX = round(SEAT_BAND[0] - PIN_DIA_BAND[1], 6)
if BOND_CLEARANCE_MIN < 0.0 or BOND_CLEARANCE_MAX > RETAINING_COMPOUND_MAX_GAP_MM:
    raise AssertionError(
        f"bonded pin gap {BOND_CLEARANCE_MIN}-{BOND_CLEARANCE_MAX} is outside the"
        f" 0-{RETAINING_COMPOUND_MAX_GAP_MM} {RETAINING_COMPOUND} window"
    )

DRAWING_NOTES = "\n".join(
    (
        "LEAVE THE CROWN ROOT CIRCLE SHARP, NO CHAMFER;",
        "  EXEMPT FROM TITLE-BLOCK EDGE-BREAK REQUIREMENT.",
        f"ON ASSEMBLY: BOND INTO {SEAT_NUMBER} FOLLOWER SEAT WITH {RETAINING_COMPOUND}.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
# The overall (seated end to crown apex) is a pure reference restatement;
# its places are specification (policy rule 2).
DRAWING_REFERENCE_PRECISION = 2
