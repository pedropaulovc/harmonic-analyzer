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
PIN_LEN = 15.0  # cylindrical shank; the 0.8 crown is additional
SEAT_LEN = 4.0  # into the blind edge bore (clear of the strap pivot bore)
CAP_SAG = 0.8  # domed outer end crown height
CAP_RADIUS = ((PIN_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia"},
    "Pin": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "CYLINDRICAL SHANK: FINAL LIMITS <MOD-DIAM>4.012-4.020 (p6), Ra 0.8.",
        "SHANK LENGTH 15.00+/-0.05; 15.80 REF OVERALL INCLUDING CROWN.",
        "SEAT 4.00 FULL-DIAMETER SHANK IN MATING 4.000-4.012 BORE;",
        "  11.00 SHANK PLUS THE CROWN REMAINS PROUD.",
        f"OUTER SPHERICAL CROWN SR{CAP_RADIUS:.2f}, TANGENT TO SHANK, 0.80+/-0.05 AXIAL.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 8:1"
