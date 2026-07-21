r"""Create the curated machinist drawing for the pinion engage lever.

A clamp hub (Ø13 OD, Ø6.35 bore) with a tapered grip rod (Ø4 at the hub to Ø6
at the tip) rising 86 mm out of it.  The rod-revolve and hub sketches both live
on the Front plane, so every marked dimension imports into the FRONT view; the
right view carries the hub length and domed cap as a reference silhouette.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_lever.py pinion-lever
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
from pinion_lever_spec import BORE, HUB_OD, ROD_LEN
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_lever"]
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

# Front view (XY): the hub is a Ø13 circle at the origin with the tapered rod
# rising +Y to the tip (model y=ROD_LEN).  bbox y runs -HUB_OD/2..ROD_LEN.
FRONT_BBOX_CY = (ROD_LEN - HUB_OD / 2.0) / 2.0
# The 86 mm rod runs the full sheet height at 2:1, so the hub sits low.  Lift
# both views ~10 mm above centre so the hub clears the bottom notes band while
# the rod tip still stays inside the top border.
FRONT_CENTER = (0.078, 0.160)
RIGHT_CENTER = (0.165, 0.160)
ISO_CENTER = (0.330, 0.205)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


HUB_R_SHEET = HUB_OD * SHEET_SCALE[0] / 2000.0
BORE_R_SHEET = BORE * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    "HubOd": (0.028, 0.086),
    "HubBore": (0.028, 0.066),
    "RodTipY": (0.044, 0.170),
    "RodRootR": (0.120, 0.108),
    "RodTipR": (0.120, 0.232),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "HubBore": "8.0 DEEP FROM FLAT FACE\nREAM 6.360-6.375\nRa 1.6",
    "RodRootR": "RADIUS - <MOD-DIAM>4.00 AT HUB",
    "RodTipR": "RADIUS - <MOD-DIAM>6.00 AT TIP",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-lever source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Engage Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion engage lever; clamp hub; tapered grip rod",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Front carries the hub bore as a true circle; the right view shows the hub
    # length and the domed cap in section-like silhouette.  HLV keeps the bore's
    # hidden through-line readable in the right view.
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.158)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Engage Lever Manufacturing Drawing",
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
