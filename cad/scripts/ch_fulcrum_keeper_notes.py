"""MHA-CH-07 fulcrum keeper: the print's words.

The drawing prose lives here, apart from ch_fulcrum_keeper_spec, so a wording
change re-keys only the keeper's own part and drawing, not every assembly,
frame and shaft that imports the spec's geometry.

Each callout keeps its size first and at most two rows of words
(drawing-guidelines rule 7); each mate is named on the feature it serves
(rule 4). Assembly instructions (staking, step numbers) stay in MHA-CH-00.
"""

from __future__ import annotations

from ch_fulcrum_keeper_spec import FOOT_TIP_WALL_TEXT

# The keeper is supplied square-topped and undrilled (SUPPLY_HEIGHT_CALLOUT);
# the two keepers' bores are line-reamed together on the frame at installed
# spacing (ch_channel_assembly_steps.KEEPERS_PAIR_REAMED_KEY): a ream at
# assembly with its mate is a requirement (rule 7), and the band its fit on
# the shaft (rule 4).
BORE_CALLOUT = "LINE-REAM WITH OTHER MHA-CH-07\nAT ASSEMBLY; SLIDING FIT ON MHA-CH-04"
# The crown is a full round tangent to both side faces (owner ruling Q10-B),
# centred on the bore, so it is cut with the bore at assembly (MHA-CH-00
# finishes each keeper's crown and tap on its bore's axis); the supplied
# blank is square-topped (SUPPLY_HEIGHT_CALLOUT).
CROWN_CALLOUT = "FULL R AT ASSEMBLY"
# The crown tap's rows under its native size and TO BORE extents: its mate,
# and the stage (the bore it stops in is made at assembly). Rows of at most
# 24 characters keep the block between the front view and the plan.
SET_SCREW_QUALIFIER = "FOR MHA-CH-VN-55 SET\nSCREW, AT ASSEMBLY"
# The foot hole's rows under its native counterbore: the screw it seats and
# the frame tap it is transferred to (the reason for the .275's three
# places). Rows of at most 21 characters keep the block clear of the tap
# callout's leader on its left and the crown radius on its right.
FOOT_HOLE_MATE = "FOR MHA-CH-VN-52;\nCENTERS MHA-FR-02 TAP"
# The second keeper is this part turned over, not an opposite hand. Note 2
# states the tip wall shortfall rule 20 asks the sheet to print (owner
# exception RV-04).
DRAWING_NOTES = "\n".join(
    (
        "1. 2 REQUIRED, ONE PER MHA-CH-04 FULCRUM-SHAFT END (SECOND",
        "   IS THIS PART FLIPPED 180\u00b0 ABOUT VERTICAL).",
        f"2. FOOT-HOLE TIP WALL {FOOT_TIP_WALL_TEXT} MIN.",
    )
)
