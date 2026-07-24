r"""Create the curated machinist drawing for the fillister-head machine screw.

Uniform fastener slice: a side (profile) view carrying the head-height and
under-head length as inserted model dimensions, a head-end view carrying
the two marked model diameters (the head OD and the shank/thread minor Ø with
its UNC-2A designation), plus an isometric.  The thread designation and shank
nominals come from the fastener catalog via ``fillister_screw_spec``.
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
    set_dimension_text,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["fillister_screw"]
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

# A #4-40 x 4 mm screw is tiny; 8:1 draws the head OD (5.5) as ~44 mm and the
# whole length (~6.2) as ~50 mm -- big enough to pick edges and read text.
SHEET_SCALE = (8.0, 1.0)
# The screw is authored on the Front plane, axis along +Z: head at z in
# [-HEAD_H, 0], shank at z in [0, SHANK_LEN].  The head-end circle projects in
# the *Front view; the profile (axis horizontal) projects in the *Right view.
END_CENTER = (0.070, 0.150)
SIDE_CENTER = (0.185, 0.190)
ISO_CENTER = (0.300, 0.170)

# Head-end view: the two concentric marked diameters, leadered clear to the left.
END_KEEP = ("HeadDia",)
DIMENSION_CALLOUTS: dict[str, str] = {}
SIDE_DIMENSION_CALLOUTS = {"ShankLg": "UNDERHEAD LENGTH"}
SIDE_KEEP = (
    "HeadHt",
    "ShankLg",
    "ShankDia",
)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fillister-screw source", await adapter.open_model(str(SOURCE)))
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
            0: "Fillister Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fillister screw; slotted machine screw; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(8, 1))
    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=(8, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(8, 1))
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="head-end"
    )
    set_dimension_callouts(adapter, end_annotations, DIMENSION_CALLOUTS)

    side_annotations = curate_view_dimensions(
        adapter, side, keep=SIDE_KEEP, view_label="side"
    )
    set_dimension_callouts(adapter, side_annotations, SIDE_DIMENSION_CALLOUTS)
    set_dimension_text(
        adapter, side_annotations, {"ShankDia": "#4-40 UNC-2A"}
    )

    # 0.020: the note is left-aligned on its anchor, clearing the 12.7 mm zone
    # margin / re-centred frame rule (~0.0126), which the layout audit enforces.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.115)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.205)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fillister Screw Manufacturing Drawing",
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
