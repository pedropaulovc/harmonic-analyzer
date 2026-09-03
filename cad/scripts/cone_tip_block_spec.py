r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations

# Re-exported for build_cone_tip_block: the passage matches the adjuster cup.
from cone_tip_adjuster_spec import CUP_DIA as SHAFT_PASSAGE_DIA  # noqa: F401


MM_PER_IN = 25.4

# Small black-steel clamp block on the swing platform that carries the axial
# end-play adjuster. See build_cone_tip_block.py for the derivation; this module
# is the drawing's single source of the marked dimensions.
BLOCK_X = 14.0  # plan width across the shaft
BLOCK_Z = 12.0  # plan depth along the shaft
BLOCK_HEIGHT = 40.718  # v2 post cascade: preserve the 1.000-mm crown above slit
ADJUSTER_AXIS_HEIGHT = 33.368  # coaxial with cone-pivot-post-v2 journal
ADJUSTER_THREAD = "5/16-18"  # blind tapped hole from the far (north) face
ADJUSTER_DEPTH = 8.0
# Non-bearing clearance passage from the south face into the adjuster bore. Its
# diameter matches the already-defined adjuster cup, so the shaft tip has one
# continuous envelope without reviving the removed fictional journal fit.
PINCH_THREAD = "#3-48"  # cross-bore tapped hole that squeezes the top slit
PINCH_HEIGHT = 38.918
PINCH_CLEARANCE_DIA = 2.946
SLIT_W = 1.2  # top clamp slit width
SLIT_DEPTH = 8.0  # slit cut down from the top face to 32.718

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Depth"},
    "Block": {"BlockHt"},
    "PassageProfile": {"PassageDiaDim", "PassageZ"},
    "PinchBore": {"PinchZ"},
    "SlitProfile": {"SlitW"},
    "TopSlit": {"SlitDepth"},
}

# The pinch cross-hole is flagged FROM the drawn +X face (the right view is
# that face): a leader note on the clearance rim says which jaw is drilled
# through and which is tapped.  The #3 normal clearance (2.946) is exactly
# the #32 drill.
PINCH_HOLE_NOTE = (
    f"#32 DRILL <MOD-DIAM>{PINCH_CLEARANCE_DIA:.2f} THRU THIS JAW\n"
    f"TAP {PINCH_THREAD} THRU FAR JAW"
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  The adjuster tap and
# the pinch hole carry their own callouts on the views.
DRAWING_NOTES = "\n".join(
    (
        "ADJUSTER: TAP AND DRILL THE PASSAGE IN ONE SETUP; PASSAGE MAY GRAZE THE THREAD CREST.",
        "SLIT MAY BREAK INTO THE PINCH HOLE.",
    )
)
