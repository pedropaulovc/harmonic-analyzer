r"""Pure-data dimensional contract shared by the crank pin and drawing."""

from __future__ import annotations


PIN_LENGTH = 45.0
# CUSTOM 1:48 self-holding taper (0.9375 on diameter over the 45 mm length),
# dimensioned by its two end diameters on the drawing -- NOT a standard No. 2
# taper pin (whose 0.193 in / Ø4.90 large end would not match these ends). The
# Ø5.0 small end sits at the crank-arm cross-hole nominal; the big end is the
# small end plus the 1:48 on-diameter rise, so the drive-fit taper contacts along
# its whole length. The crank arm's cross-hole is taper-reamed with the shaft to
# the same 1:48 to suit this pin at assembly.
SMALL_END_DIA = 5.0
BIG_END_DIA = SMALL_END_DIA + PIN_LENGTH / 48.0  # 5.9375

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"Length"},
}

DRAWING_NOTES = "\n".join(
    (
        "UOS, DIMENSIONS IN MM: LENGTH +/-0.25; DIAMETERS +/-0.05. DEBURR; BREAK "
        "BOTH ENDS 0.3 MAX.",
        "CUSTOM 1:48 SELF-HOLDING TAPER (0.9375 ON DIA OVER 45.0) BETWEEN THE END "
        "DIAMETERS SHOWN: TURN IN ONE CONTINUOUS PASS; NO STEPS.",
        "HAND-FIT TO THE CRANK-ARM CROSS-HOLE, TAPER-REAMED WITH THE SHAFT AT "
        "ASSEMBLY TO THE SAME 1:48; LIGHT DRIVE FIT, REMOVABLE BY TAP ON SMALL END.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
