r"""Pure-data dimensional contract shared by the crank pin and drawing."""

from __future__ import annotations

import math

from _surface_finish import SurfaceFinishControl

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
# Keeper-ring cross-hole through the big end (ch11 p.14 page002_img01: the
# brass ring hangs from a hole in the pin's head), perpendicular to the axis.
RING_HOLE_DIA = 1.5
RING_HOLE_X = 3.0  # from the big end
TAPER_HALF_ANGLE_DEGREES = math.degrees(
    math.atan((BIG_END_DIA - SMALL_END_DIA) / (2.0 * PIN_LENGTH))
)

# No roughness callouts: the taper is a drive fit in the crank arm, not a
# running surface, so the title block's Ra 3.2 covers every face
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"Length"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). The end diameters and
# the length are on the views; the taper ratio is what the compound is set
# to. How the taper is cut (one pass, roughed and finished, ground) is the
# machinist's call -- the ends, the ratio and the hand fit already control it
# (machinist review, 2026-09-02).
DRAWING_NOTES = "\n".join(
    (
        "TAPER 1:48 ON DIA BETWEEN THE END DIAMETERS SHOWN.",
        "HAND-FIT TO THE CRANK ARM CROSS-HOLE AT ASSEMBLY; LIGHT DRIVE FIT.",
        f"DRILL DIA {RING_HOLE_DIA:.2f} THRU ACROSS THE AXIS {RING_HOLE_X:.2f} FROM THE BIG END "
        "FOR THE BRASS KEEPER RING.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
