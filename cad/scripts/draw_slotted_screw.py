r"""Create the curated machinist drawing for the rig hold-down slotted screw.

Uniform fastener slice (see draw_fillister_screw.py): a profile side view with
the head-height and under-head length (the vertical profile cannot point-select
the edge-on shoulder/tip, so both ship as the head/shank extrude-DEPTH model
dimensions HeadHt/ShankLg in the side view), a head-end view
carrying the two marked model diameters (head OD and the shank/thread minor Ø
with its UNC-2A designation), plus an isometric.  Authored on the Top plane
(axis +Y), so it stands VERTICAL in the profile view (head up).
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
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from slotted_screw_spec import (
    HEAD_H,
    SHANK_LEN,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["slotted_screw"]
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

# #8-32 x 18 mm: 6:1 draws the ~20.5 mm length as ~123 mm and the head OD (8)
# as ~48 mm.
SHEET_SCALE = (6.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Authored on the Top plane, axis +Y: head at y in [0, HEAD_H] (top), shank at
# y in [-SHANK_LEN, 0] (bottom).  Head-end circle in the *Top view; the profile
# (axis VERTICAL, head up) in the *Front view.
# The side view sits high so the ~108 mm profile clears the wide manufacturing
# note that anchors just above the title block.
END_CENTER = (0.075, 0.190)
SIDE_CENTER = (0.190, 0.190)
ISO_CENTER = (0.315, 0.175)

_Y_MID = (HEAD_H - SHANK_LEN) / 2.0


def _side_y(model_y: float) -> float:
    return SIDE_CENTER[1] + (model_y - _Y_MID) * _S


_HEAD_END_Y = _side_y(HEAD_H)  # head outer face (top)
_JUNCTION_Y = _side_y(0.0)  # head/shank step
_SHANK_END_Y = _side_y(-SHANK_LEN)  # shank tip (bottom)

# Head-end view: the two concentric marked diameters, leadered clear to the left.
END_KEEP = {
    "HeadDia": (0.030, END_CENTER[1] + 0.026),
}
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: the head-height and under-head length as the extrude-depth model
# dims (the vertical profile cannot point-select the edge-on shoulder/tip).
SIDE_KEEP = {
    "HeadHt": (SIDE_CENTER[0] + 0.052, (_HEAD_END_Y + _JUNCTION_Y) / 2.0),
    "ShankLg": (SIDE_CENTER[0] + 0.052, (_JUNCTION_Y + _SHANK_END_Y) / 2.0),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open slotted-screw source", await adapter.open_model(str(SOURCE)))
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
            0: "Slotted Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "slotted screw; fillister-head machine screw; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=(6, 1))
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(6, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(6, 1))
    set_hidden_lines_removed(adapter, side)
    set_hidden_lines_removed(adapter, iso)
    set_hidden_lines_removed(adapter, end)

    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="head-end"
    )
    set_dimension_callouts(adapter, end_annotations, DIMENSION_CALLOUTS)

    # Side-view lengths: the head/shank extrude-depth model dims (HeadHt/ShankLg),
    # inserted and positioned to the right of the vertical profile.
    curate_view_dimensions(adapter, side, keep=SIDE_KEEP, view_label="side")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.105)
    add_property_linked_note(adapter, "End View Note", END_CENTER[0] - 0.020, 0.250)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Slotted Screw Manufacturing Drawing",
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
