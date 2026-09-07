r"""Create the curated machinist drawing for the rig hold-down slotted screw.

The profile imports the named head-height and under-head length dimensions
HeadHt/ShankLg. The head-end view carries the marked head diameter, and the
linked manufacturing note defines the thread. An isometric completes the sheet.
SolidWorks arranges the dimensions before measured whole-sheet packing.
Authored on the Top plane
(axis +Y), so it stands VERTICAL in the profile view (head up).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check
from _drawing_build import ProjectDrawingFactory, TemplateSpec, run_drawing_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    auto_arrange_view_dimensions,
    curate_view_dimensions,
    finalize_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_native_layout import LayoutNote
from _drawing_project_layout import repair_project_drawing_layout
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_packing import Axis, AxisOrder
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

# Keep the production scale; native measurement includes dimension-line tails
# when packing the complete view, not just the solid's projected size.
SHEET_SCALE = (6.0, 1.0)
TEMPLATE_SPEC = TemplateSpec(scale=SHEET_SCALE, decimals=2)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Authored on the Top plane, axis +Y: head at y in [0, HEAD_H] (top), shank at
# y in [-SHANK_LEN, 0] (bottom).  Head-end circle in the *Top view; the profile
# (axis VERTICAL, head up) in the *Front view.
# These positions seed native arrangement. Measured packing moves complete
# decorated views and their captions clear of notes and sheet-zone boundaries.
END_CENTER = (0.075, 0.190)
SIDE_CENTER = (0.190, 0.190)
ISO_CENTER = (0.315, 0.175)

_Y_MID = (HEAD_H - SHANK_LEN) / 2.0


def _side_y(model_y: float) -> float:
    return SIDE_CENTER[1] + (model_y - _Y_MID) * _S


_HEAD_END_Y = _side_y(HEAD_H)  # head outer face (top)
_JUNCTION_Y = _side_y(0.0)  # head/shank step
_SHANK_END_Y = _side_y(-SHANK_LEN)  # shank tip (bottom)

# Head-end view: the marked head diameter, initially placed to the left.
END_KEEP = {
    "HeadDia": (0.030, END_CENTER[1] + 0.026),
}
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: named head-height and under-head extrude-depth model dimensions.
SIDE_KEEP = {
    "HeadHt": (SIDE_CENTER[0] + 0.052, (_HEAD_END_Y + _JUNCTION_Y) / 2.0),
    "ShankLg": (SIDE_CENTER[0] + 0.052, (_JUNCTION_Y + _SHANK_END_Y) / 2.0),
}


async def build(
    adapter: Any, *, drawing_factory: ProjectDrawingFactory
) -> dict[str, str]:
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
    drawing_model, _sheet = drawing_factory(
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

    manufacturing = add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.105)
    caption = add_property_linked_note(adapter, "End View Note", END_CENTER[0] - 0.020, 0.250)

    auto_arrange_view_dimensions(adapter, (side, end, iso))
    repair_project_drawing_layout(
        adapter,
        views={"side": side, "end": end, "iso": iso},
        orderings=(
            AxisOrder(Axis.X, "end", "side"),
            AxisOrder(Axis.X, "side", "iso"),
        ),
        notes=(
            LayoutNote("manufacturing", manufacturing.GetAnnotation()),
            LayoutNote("end-caption", caption.GetAnnotation(), "end"),
        ),
    )

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
    sys.exit(run_drawing_build(build, spec=TEMPLATE_SPEC))
