r"""Pure-data dimensional contract shared by the crank pin and drawing."""

from __future__ import annotations


PIN_LENGTH = 45.0
BIG_END_DIA = 6.0
SMALL_END_DIA = 5.0

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"Length"},
}

DRAWING_NOTES = "\n".join(
    (
        "UOS, DIMENSIONS IN MM: LENGTH +/-0.25; DIAMETERS +/-0.05. DEBURR; BREAK "
        "BOTH ENDS 0.3 MAX.",
        "SELF-HOLDING TAPER 1.0 ON DIA OVER 45.0 (~1:45): TURN IN ONE CONTINUOUS "
        "PASS; NO STEPS.",
        "HAND-FIT TO CRANK ARM CROSS-HOLE AT ASSEMBLY; LIGHT DRIVE FIT, "
        "REMOVABLE BY TAP ON SMALL END.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
