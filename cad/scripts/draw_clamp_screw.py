r"""Create the curated machinist drawing for the clamp screw.

Uniform fastener slice (see draw_fillister_screw.py): a profile side view with
the head-height and under-head length as inserted model dimensions, a head-end view
carrying the two marked model diameters (head OD and the shank/thread minor Ø
with its UNC-2A designation), plus an isometric.  Built on the Front plane (axis
+Z), so the profile lies HORIZONTAL with the head at the right end.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["clamp_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# #8-32 x 28 mm: 4:1 draws the ~30.5 mm length as ~122 mm and the head OD (8)
# as ~32 mm.
SHEET_SCALE = (4.0, 1.0)
# Built on the Front plane, axis +Z: head at z in [-HEAD_H, 0], shank at
# z in [0, SHANK_LEN].  Head-end circle in the *Front view; profile (axis
# HORIZONTAL) in the *Right view, which MIRRORS z (head at HIGH-x, shank tip
# at LOW-x).
END_CENTER = (0.065, 0.150)
SIDE_CENTER = (0.190, 0.150)
ISO_CENTER = (0.320, 0.180)

END_KEEP = {
    "HeadDia": (0.028, END_CENTER[1] + 0.024),
}
DIMENSION_CALLOUTS: dict[str, str] = {}
SIDE_KEEP = {
    "HeadHt": (SIDE_CENTER[0], SIDE_CENTER[1] + 0.030),
    "ShankLg": (SIDE_CENTER[0] - 0.052, SIDE_CENTER[1] - 0.030),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open clamp-screw source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Clamp Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "clamp screw; slotted machine screw; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(4, 1))
    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    set_hidden_lines_removed(adapter, side)
    set_hidden_lines_removed(adapter, iso)
    set_hidden_lines_visible(adapter, end)

    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="head-end"
    )
    set_dimension_callouts(adapter, end_annotations, DIMENSION_CALLOUTS)

    curate_view_dimensions(adapter, side, keep=SIDE_KEEP, view_label="side")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.115)
    add_property_linked_note(adapter, "End View Note", END_CENTER[0] - 0.018, 0.200)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Clamp Screw Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
