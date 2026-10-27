"""Build TL-32 using the shared native shoulder-screw block model."""
from __future__ import annotations
import sys
from _drawing_marks import apply_drawing_properties
from _oblique_pivot_block_model import build_block_model
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
import ch_rocker_arm_tl_oblique_feed_block_spec as spec

PART_NAME = "ch-rocker-arm-tl-oblique-feed-block"
MATERIAL = "6061 Alloy"

async def build(adapter):
    await build_block_model(adapter, spec)
    apply_drawing_properties(adapter, PART_NAME)
    result = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, ("Number", "Material Specification", "Finish", "Quantity"))
    return result

if __name__ == "__main__":
    sys.exit(run_build(build))
