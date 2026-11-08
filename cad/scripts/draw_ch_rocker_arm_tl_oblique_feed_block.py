"""Manufacturing drawing for TL-32, integral feed block; no match drilling."""
from __future__ import annotations
import argparse
import sys
from _drawing_common import read_required_properties
from _drawing_registry import DRAWINGS_BY_NAME
from _session import run_build
from _oblique_block_drawing import draw_block
import ch_rocker_arm_tl_oblique_feed_block_spec as part
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME['ch_rocker_arm_tl_oblique_feed_block']
PART_STEM = SPEC.artifact_stem
# VIEW D's printed text, drawing-side over the saved model's CALLOUTS_*
# (machinist review of the 957501d1 sheet 2). The clearance prints size,
# then process, on one row (rule 26) and names its mate once, by kit number
# in the same-parent short form, never a catalogue code (rule 4). The two
# location dimensions carry their value and band only (rule 7); the mm unit
# is RV-02's.
LEADSCREW_MATE = f"{part.feed_nut.NUMBER.removeprefix(part.NUMBER.rsplit('-TL-', 1)[0] + '-')} LEADSCREW"
# The Ø.351 is bored at its ±.002 station (owner ruling 2026-11-08 (Pedro),
# A2 option (i); the shop table holds ±.002 only for a bored or reamed hole).
CALLOUTS = {
    'NutClearanceDia': {'suffix': f' {part.NUT_CLEARANCE_PROCESS} THRU', 'above': '',
                        'below': f'FOR {LEADSCREW_MATE}\n{part.NUT_WALL_MIN_TEXT}'},
    'NutCentreY': {'above': '', 'below': ''},
    'NutCentreZ': {'above': '', 'below': ''},
}

def _read_source_properties(adapter):
    read_required_properties(
        adapter.currentModel, ("Number", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )

async def build(adapter):
    return await draw_block(adapter,SPEC,part,read_source_properties=_read_source_properties,callouts=CALLOUTS)
if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))
