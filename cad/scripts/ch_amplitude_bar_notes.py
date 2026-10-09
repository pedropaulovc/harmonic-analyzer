r"""Amplitude-bar drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT and the view labels.

Split OUT of ``amplitude_bar_spec`` (the ``rocker_arm_notes`` treatment, codex
#354): the channel kinematics, the rocker-bank layout and the spring specs
import the bar's geometry, so drawing prose in that import closure re-keyed
the channel, magnifier and summing assemblies on every notes edit.  Imported
ONLY by ``build_amplitude_bar`` and the offline tests.
"""

from __future__ import annotations

from ch_amplitude_bar_spec import TOP_PIN_HOLE_BAND, TOP_PIN_HOLE_DIA

# The pin pressed into the top pin hole (test_ch_amplitude_bar_drawing pins it
# to the part registry). The hole is dimensioned in the notes, so its reamed
# band (the model's, native on TopPinDia) is stated with it.
TOP_PIN_NUMBER = "MHA-CH-011"
_HOLE_UPPER, _HOLE_LOWER = TOP_PIN_HOLE_BAND
if _HOLE_LOWER != 0.0:
    raise AssertionError("note 3 prints the reamed band as +upper/0")

# The title-block QTY cell owns the 20-off count; notch orientation and
# coplanarity are stated because no view resolves them at 1:4 (machinist
# round 1): both notches live in ONE profile sketch cut thru the full depth,
# so open-to-opposite-ends / common-plane IS the model truth, and the pin
# hole runs thru the top-notch cheeks at mid-depth. Each notch's centring
# ledge, width and depth -- the bottom depth with its one-sided band
# (amplitude_bar_spec.BOTTOM_NOTCH_DEPTH_BAND), each ledge with
# NOTCH_OFFSET_TOLERANCE_MM -- print as model dimensions in its end's detail,
# and the floor's Ra is a native symbol there (amplitude_bar_drawing_spec),
# never here (policy rule 2, Codex #936 PRRT_kwDOPHDy386mWF0L).
# "ROOTS R0.40 MAX." is a Main-ruled exception (2026-09-27): it limits the
# cutter's corner at an unmodelled root, so nothing in the model can carry it.
DRAWING_NOTES = "\n".join(
    (
        "1. BAR SECTION 6.35 SQUARE.",
        "2. END NOTCHES (DETAILS A, B):",
        "   BOTH THRU THE FULL DEPTH, OPEN TO",
        "   OPPOSITE ENDS, IN ONE COMMON PLANE;",
        "   ROOTS R0.40 MAX.",
        f"3. TOP PIN HOLE \u00d8{TOP_PIN_HOLE_DIA:.3f} +{_HOLE_UPPER:.3f}/0 REAM",
        "   THRU BOTH TOP-NOTCH CHEEKS AT",
        "   MID-DEPTH, 6.35 BELOW THE BAR TOP;",
        f"   PRESS FIT PIN {TOP_PIN_NUMBER}.",
        "4. DIMS APPLY AFTER PLATING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:8"
END_VIEW_NOTE = "END VIEW SCALE 4:1"
