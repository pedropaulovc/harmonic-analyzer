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

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia"},
    "Pin": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "TURN FROM BRIGHT STEEL ROD; NO STEPS ALONG THE SHANK.",
        "SEAT END 4.0 PRESS FIT INTO THE STRAP WEST-EDGE BORE, 11 PROUD.",
        "CROWN THE OUTER END TO A SHALLOW SPHERICAL DOME, 0.8 HIGH (REF).",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 8:1"
