r"""Pure-data dimensional contract shared by the crank pin and drawing."""

from __future__ import annotations


PIN_LENGTH = 45.0
# No. 2 taper pin, 1:48 (0.9375 on diameter over the 45 mm length), matching the
# crank-arm cross-hole reamed "FOR NO. 2 TAPER PIN, 1:48" (crank_arm_spec.py). The
# small end stays at the ~Ø5 cross-hole nominal; the big end is the small end plus
# the 1:48 on-diameter rise so the drive-fit taper contacts along its whole length
# instead of at one end only.
SMALL_END_DIA = 5.0
BIG_END_DIA = SMALL_END_DIA + PIN_LENGTH / 48.0  # 5.9375

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"Length"},
}

DRAWING_NOTES = "\n".join(
    (
        "UOS, DIMENSIONS IN MM: LENGTH +/-0.25; DIAMETERS +/-0.05. DEBURR; BREAK "
        "BOTH ENDS 0.3 MAX.",
        "NO. 2 TAPER PIN, 1:48 (0.9375 ON DIA OVER 45.0), SELF-HOLDING: TURN IN "
        "ONE CONTINUOUS PASS; NO STEPS. MATES CRANK-ARM CROSS-HOLE REAMED FOR "
        "NO. 2 TAPER, 1:48.",
        "HAND-FIT TO CRANK ARM CROSS-HOLE AT ASSEMBLY; LIGHT DRIVE FIT, "
        "REMOVABLE BY TAP ON SMALL END.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
