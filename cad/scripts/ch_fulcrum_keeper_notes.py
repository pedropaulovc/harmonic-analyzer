"""MHA-CH-07 fulcrum keeper: the print's words.

The callout rows and the notes live here, apart from ch_fulcrum_keeper_spec
(the ch_rocker_arm_notes split), so a wording change re-keys only the
keeper's own part and drawing, not the frame, shaft and assemblies that
import the spec's geometry. The spec keeps the two band-bearing captions
its own walls are computed with (BORE_CENTRE_CALLOUT, SUPPLY_HEIGHT_CALLOUT).

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
# True free-text facts only; the material and finish are the title block's.
# Note 1 is the quantity and that the two are one part, not handed; where
# each goes and how the second is turned is MHA-CH-00's (machinist r1: that
# placement on a part sheet is assembly narration). Note 2 states the tip
# wall shortfall rule 20 asks the sheet to print (Codjiflo #2108; owner
# exception RV-04). The foot hole stays located off the foot tip (owner
# ruling 2026-10-28, RV-03), and no note says why (MR-fleet r7: one drew
# three findings of its own).
DRAWING_NOTES = "\n".join(
    (
        "1. 2 REQUIRED, IDENTICAL.",
        f"2. FOOT-HOLE TIP WALL {FOOT_TIP_WALL_TEXT} MIN.",
    )
)
