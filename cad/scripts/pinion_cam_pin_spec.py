r"""Pure-data dimensional contract shared by the pinion cam-follower pin and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A short bright-steel stud pressed into the
swing strap's west edge, riding on the eccentric cam collar.  The nominals drive
the part's named equation globals AND the drawing's coordinate math; the
marked-dimension map keeps the part marks and drawing keeps in lockstep
(``test_pinion_cam_pin_drawing.py``).
"""

from __future__ import annotations

from _surface_finish import SurfaceFinishControl
from pinion_cam_pin_geometry import (
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    PIN_DIA as PIN_DIA,
    PIN_LEN as PIN_LEN,
    SEAT_LEN as SEAT_LEN,
)

# Symmetric final-size band about the PIN_DIA mid nominal (4.020 MAX /
# 4.012 MIN press band); the drawing callout derives its limits from these
# two constants so a retuned press fit can never ship stale limit text.
PIN_DIA_TOL = 0.004
PIN_DIA_BAND = (PIN_DIA_TOL, -PIN_DIA_TOL)
PIN_LENGTH_TOLERANCE_MM = 0.05
CAP_RADIUS_TOLERANCE_MM = 0.05

# Seated flat end to the crown apex: the stock length nobody may saw short
# (a REFERENCE sheet dimension; the 17.00 to the crown root controls).
OVERALL_LEN = PIN_LEN + CAP_SAG  # 17.80

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia"},
    "Pin": {"Depth"},
    "CapProfile": {"CapR"},
}

# No roughness callouts: the shank is pressed into the strap and the crown is
# a turned dome; the title block's Ra 3.2 covers both
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Notes: process facts only, never a tolerance (policy rule 6).
DRAWING_NOTES = "\n".join(
    (
        "SEATED END FLAT; OPPOSITE END ONE SPHERICAL CROWN.",
        "CROWN ROOT CIRCLE STAYS SHARP: R0.10 MAX, NO CHAMFER.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 8:1"
