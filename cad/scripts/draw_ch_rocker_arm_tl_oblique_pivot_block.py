"""Manufacturing sheets for the plain shoulder-screw pivot blocks.

Both sheets print decimal inch (each part's ``drawing_unit``). All sizes
import native model dimensions; no bearing/cartridge sheets survive.
Plan X locations run from the -X (left) edge through the hidden
``PlanDatumReference`` sketch; Y from the shoulder seat's axis. Section B-B
shows the floor from the carriage seat, not a competing counterbore-depth
tolerance chain. TL-32's nut face is VIEW D on its own 2:1 sheet, its arrow on
the plan. The layout notes below give sheet millimetres.
"""
from __future__ import annotations
import argparse
import sys
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _oblique_block_drawing import draw_block
from _paths import CAD_ROOT
from _session import run_build
import ch_rocker_arm_tl_oblique_pivot_block_spec as part

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME['ch_rocker_arm_tl_oblique_pivot_block']
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / 'out' / 'sldprt' / f'{PART_STEM}.SLDPRT'
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs['slddrw'],pdf=SPEC.outputs['pdf'],png=SPEC.outputs['png'])


async def build(adapter):
    return await draw_block(adapter,SPEC,part)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))
