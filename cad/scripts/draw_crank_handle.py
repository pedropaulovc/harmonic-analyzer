r"""Create the curated machinist drawing for the crank handle.

A turned stained-oak pear grip (book ch. 11): an integral collar profile at the crank end,
a waisted neck, a smooth twin-arc swell to the Ø22 max, and a blunt domed butt
with a flat cap.  The pear silhouette is two internally-tangent arcs, so the
swell/neck/butt diameters derive from the profile and cannot be marked without
over-defining; the print dimensions the clean AXIAL stations (overall length,
collar length, peak station) in the front profile view and gives the diameters
as a turning-schedule note.  The profile sketches on the Front plane, so every
marked dimension imports into the front view (handle axis horizontal).

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_handle.py crank-handle
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
from crank_handle_spec import COLLAR_DIA, HANDLE_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_handle"]
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

# Front view (XY): the pear lies horizontal, axis along +X, collar at the left
# (x=0) and butt at the right (x=HANDLE_LENGTH).  Centre on the axial midspan.
FRONT_BBOX_CX = HANDLE_LENGTH / 2.0
FRONT_CENTER = (0.150, 0.178)
ISO_CENTER = (0.330, 0.150)

COLLAR_R = COLLAR_DIA / 2.0


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + model_y_mm * SHEET_SCALE[0] / 1000.0


COLLAR_R_SHEET = COLLAR_R * SHEET_SCALE[0] / 1000.0

FRONT_KEEP = {
    "HandleLength": (0.150, 0.128),
    "CollarLength": (0.070, 0.222),
    "PeakStation": (0.150, 0.242),
}
DIMENSION_CALLOUTS: dict[str, str] = {}
DIMENSION_CALLOUTS = {
    "HandleLength": "+/-0.25 OVERALL",
    "CollarLength": "+/-0.10 FROM COLLAR FACE",
    "PeakStation": "+/-0.25 FROM COLLAR FACE",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle source", await adapter.open_model(str(SOURCE)))
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
            0: "Crank Handle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle; turned oak pear grip; integral collar profile",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    set_hidden_lines_visible(adapter, front)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.116)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Manufacturing Drawing",
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
