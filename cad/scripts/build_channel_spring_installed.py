r"""Reproduction script: channel spring, INSTALLED length (book ch. 17).

The p. 40-41 machine photos show the 20 channel springs visibly stretched
between the lever tabs and the summing-lever plate -- open coils, roughly
twice the free 32 mm body. This part is the same spring as
build_channel_spring.py (same wire, OD, coil count) at the installed
extension. The bottom does NOT thread through the plate: a separate little
open hook fastener (build_spring_hook.py) seats in the plate's O2.0 bore and
the spring's bottom eye links onto its arm just ABOVE the plate. So the bottom
lead is a normal short hook lead (symmetric with the top), not a plate-spanning
one, and the bottom eye sits above the plate:

    top eye centre    1062.52  (lever spring hole 1065.89 - drop 3.37)
    bottom eye centre 1019.89  (on the hook arm; its O5.5 ring bottom 1016.64
                                clears the plate top 1015.89 by 0.75)
    coil body bottom   998.54  (bottom eye + 2.0 bottom lead)
    body = 1062.52 - 2.0 (top lead) - 998.54             = 61.98
    bottom lead                                          = 2.0

    The plate is the coplanar .cs casting (top 1015.89, see build_summing_lever).
    The top eye is the LIVE neutral lever spring hole (level rest pose, ch14 ROM
    re-derive): the lever pivots about FULCRUM=(-206.7, 1099.8) with the spring
    hole 177.8 out along the arm, and the level rocker rest pose leaves the
    neutral lever tilt at -0.002 deg -- the hole sits essentially at the fulcrum
    height, 1065.89, NOT the tilted-era 1066.52/1066.62. build_channel_assembly is
    the authority: its verify:math gate (spring:neutral-body-canonical) fails loud
    if this drifts from the solver's neutral gap, so neutral always mates this one
    canonical body x20 instead of spawning a stretch variant.

The bottom eye is on the spring axis now (the hook reaches +X to it, not the
spring reaching down through the plate), so the summing-lever plate holes are
coaxial with the spring axis in Z (z_j + 0.8) and shifted one arm-offset -X to
seat the hook shank (see build_summing_lever.py and build_channel_assembly.py).

Dimensions: cad/DIMENSIONS.md ch. 17 + ch. 18 (M6.4).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_channel_spring_installed.py
"""

from __future__ import annotations

import sys

from _common import run_build, save_part_and_images
from _spring import COIL_BODY_LENGTH, HOOK_LEAD, build_spring
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from channel_spring_installed_notes import (
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
)
from channel_spring_installed_spec import INSTALLED_BODY_LENGTH

PART_NAME = "channel-spring-installed"

# LEVER_EYE_Y / PLATE_EYE_Y / INSTALLED_BODY_LENGTH moved to the spec (the
# assembly-facing placement contract; codex #354).
TOP_LEAD = HOOK_LEAD  # 2.0
BOTTOM_LEAD = HOOK_LEAD  # 2.0: normal hook lead (no longer spans the plate)
TOP_EYE_LOCAL_Y = INSTALLED_BODY_LENGTH + TOP_LEAD  # 63.98 above the part origin

assert INSTALLED_BODY_LENGTH > COIL_BODY_LENGTH, "installed spring must be stretched"


async def build(adapter) -> dict[str, str]:
    result = await build_spring(
        adapter, PART_NAME, INSTALLED_BODY_LENGTH, leads=(BOTTOM_LEAD, TOP_LEAD),
        eye_axes=True,
    )
    # Manufacturing spec-sheet support: a coil spring carries no graphical marked
    # dimensions (the data table governs), so no mark loop; stamp the
    # make-critical title-block properties + the spring data table, then re-save.
    # (build_spring already saved once; this re-stamps the canonical installed
    # part only -- the mass-produced stretch variants never take this path.)
    clear_dimensions_for_drawing(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes", "Isometric View Note",
        ),
    )
    return {**result, **artefacts}


if __name__ == "__main__":
    sys.exit(run_build(build))
