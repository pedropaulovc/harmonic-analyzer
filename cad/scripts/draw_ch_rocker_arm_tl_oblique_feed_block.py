"""Manufacturing drawing for TL-32, integral feed block; no match drilling."""
from __future__ import annotations
import argparse
import sys
from _drawing_common import read_required_properties
from _drawing_registry import DRAWINGS_BY_NAME
from _session import run_build
from draw_ch_rocker_arm_tl_oblique_pivot_block import draw_block
import ch_rocker_arm_tl_oblique_feed_block_spec as part
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME['ch_rocker_arm_tl_oblique_feed_block']
PART_STEM = SPEC.artifact_stem
def _read_source_properties(adapter):
    read_required_properties(
        adapter.currentModel, ("Number", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )

async def build(adapter):
    return await draw_block(adapter,SPEC,part,read_source_properties=_read_source_properties)
if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))
