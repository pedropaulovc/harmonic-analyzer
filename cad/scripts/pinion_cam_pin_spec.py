r"""Pure-data dimensional contract shared by the pinion cam-follower pin and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A short bright-steel stud pressed into the
swing strap's west edge, riding on the eccentric cam collar.  The nominals drive
the part's named equation globals AND the drawing's coordinate math; the
marked-dimension map keeps the part marks and drawing keeps in lockstep
(``test_pinion_cam_pin_drawing.py``).
"""

from __future__ import annotations

PIN_DIA = 4.0  # press fit in the strap's blind edge bore (pinion_bracket PIN_BORE)
PIN_LEN = 15.0  # 4.0 seated + 11 proud west, over the cam collar
SEAT_LEN = 4.0  # into the blind edge bore (clear of the strap pivot bore)
CAP_SAG = 0.8  # domed outer end crown height
CAP_RADIUS = ((PIN_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia"},
    "Pin": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "TURN A STRAIGHT, STEP-FREE SHANK TO <MOD-DIAM>4 p6 (4.012-4.020), Ra 0.8.",
        "SEAT THE FLAT END 4.00 INTO THE STRAP BORE; 11.00 REMAINS PROUD.",
        f"CROWN THE OUTER END TO SPHERICAL R{CAP_RADIUS:.2f}, 0.80 AXIAL CROWN.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 8:1"
