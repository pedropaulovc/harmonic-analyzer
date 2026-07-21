r"""Create the curated machinist drawing for the pinion turning handle.

A bright tee: a fat Ø23 grip cylinder on the arbor axis (Z) with a domed south
cap, a Ø6 cross rod through the grip (arms 42/43 along Y), and a blind tubular
hub (Ø10.5 OD, Ø8 ID) that swallows the Ø8 arbor stub.  The grip and tube
sketch on the Front plane (front view carries the grip OD and the concentric
tube bore); the cross rod sketches on the Top plane (top view carries the rod
diameter); the Z lengths import into the right view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_handle.py pinion-handle
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
from pinion_handle_spec import ROD_DOWN, ROD_UP, TUBE_ID
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_handle"]
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

SHEET_SCALE = (2.0, 1.0)

# Front view (XY, looking down the arbor axis Z): the grip Ø23 disc sits at the
# origin with the Ø6 cross rod running vertically through it (model y -42..+43).
# Lift the view a touch above centre so the rod bottom clears the notes band.
FRONT_BBOX_CY = (ROD_UP - ROD_DOWN) / 2.0
FRONT_CENTER = (0.072, 0.155)
RIGHT_CENTER = (0.158, 0.155)
# Keep the top view above the ASME-B title block (its rod span makes the view
# taller than its circular grip silhouette suggests).
TOP_CENTER = (0.270, 0.120)
ISO_CENTER = (0.320, 0.210)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


BORE_R_SHEET = TUBE_ID * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    "GripDia": (0.024, 0.196),
    "TubeOd": (0.024, 0.116),
    "TubeId": (0.035, 0.096),
    "RodSpan": (0.044, 0.232),
}
RIGHT_KEEP = {
    "GripLen": (0.148, 0.086),
    "TubeLen": (0.180, 0.105),
}
TOP_KEEP = {
    "RodDia": (0.300, 0.078),
}
DIMENSION_CALLOUTS = {
    "TubeId": "FINAL REAM LIMITS\n8.010/8.025\n10.00 MIN FULL-DIA\nFROM FLAT END\nRa 1.6",
    "GripLen": "+/-0.10",
    "TubeLen": "+/-0.10",
    "RodSpan": "42.00 DOWN / 43.00 UP\nFROM GRIP AXIS\nMATCH-MARK 43 SIDE",
    "RodDia": "ROD FINAL LIMITS\n6.012/6.020 PRESS FIT",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-handle source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Turning Handle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion turning handle; grip cylinder; cross rod; blind hub",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # HLV keeps the blind tube bore's hidden through-lines readable behind the
    # solid grip in the front and right views.
    for view in (front, right, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *right_annotations, *top_annotations],
        DIMENSION_CALLOUTS,
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.062)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.184)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Turning Handle Manufacturing Drawing",
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
