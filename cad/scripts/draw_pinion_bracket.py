r"""Create the curated machinist drawing for the pinion swing bracket.

The SLDPRT remains authoritative.  This recipe supplies only the strap's
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the strap is 61 mm end to end); the isometric carries an
explicit 1:1 override so it stays clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_bracket.py pinion-bracket
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
from pinion_bracket_spec import (
    ARBOR_BORE,
    C2C as C2C,
    OVERALL_LENGTH,
    PIVOT_BORE,
    R_END,
    THICKNESS,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_bracket"]
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

# Sheet layout (meters).  The strap runs UP the sheet: the front view's model
# bbox is +/-9 in X and -9..52 in Y (61 tall); at 2:1 the view is 36 x 122 mm.
# The front view carries the face (both bores + the width caps); the right view
# is the 5-thick section carrying the pin-seat bore.  A top view is omitted --
# the strap's top face is a plain 18 x 5 rectangle with no feature to document,
# so it would render as an empty box.
FRONT_BBOX_CY = (OVERALL_LENGTH / 2.0) - R_END  # 21.5: (52 + -9) / 2
FRONT_CENTER = (0.110, 0.150)
RIGHT_CENTER = (0.200, 0.150)
ISO_CENTER = (0.330, 0.205)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


PIVOT_R_SHEET = PIVOT_BORE * SHEET_SCALE[0] / 2000.0
ARBOR_R_SHEET = ARBOR_BORE * SHEET_SCALE[0] / 2000.0
HALF_THICK_SHEET = THICKNESS * SHEET_SCALE[0] / 2000.0

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The bore-to-bore centre distance runs vertically LEFT of the view;
# the leadered diameters land in the clear sheet RIGHT of the strap; the pin
# seat's size + section carry on the right view.
FRONT_KEEP = {
    "ArborBoreCz": (0.070, 0.150),
    "ArborBoreDia": (0.156, 0.196),
    "PivotBoreDia": (0.162, 0.130),
    "BottomCapRadius": (0.098, 0.076),
    "PinSeatCy": (0.058, 0.128),
}
RIGHT_KEEP = {
    "Depth": (0.200, 0.082),
    "PinSeatDia": (0.262, 0.128),
    # Locates the pin seat through the thickness (mid-plane) in the section view.
    "PinSeatCz": (0.225, 0.180),
}
DIMENSION_CALLOUTS = {
    "ArborBoreCz": "+/-0.10",
    "PivotBoreDia": "PIVOT BORE; NOMINAL REF\nTHRU - REAM\n6.375 MAX / 6.360 MIN\nRa 1.6",
    "ArborBoreDia": "ARBOR BORE; NOMINAL REF\nTHRU - REAM\n8.025 MAX / 8.010 MIN\nRa 1.6",
    "PinSeatCy": "PIN-SEAT AXIS\n+/-0.05 BELOW\nPIVOT-BORE AXIS",
    "Depth": "+/-0.05 ONE STRAP THICKNESS",
    "PinSeatDia": (
        "NOMINAL REF\nH7: 4.012 MAX / 4.000 MIN\nBLIND; FLAT BOTTOM\n"
        "4.00 +0.10/-0.00 DEEP\nDRILL FROM LEFT EDGE SHOWN"
    ),
    "PinSeatCz": "+/-0.05 FROM EITHER BROAD FACE",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-bracket source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Swing Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion swing bracket; manufacturing drawing; pivot strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # The front view carries both bores as true circles; the right view shows
    # the pin-seat bore edge-on as a circle at mid-thickness.  HLV keeps the
    # blind pin seat's hidden circle readable.
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )

    for view, label in ((front, "front"), (right, "right")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.320, 0.178)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Swing Bracket Manufacturing Drawing",
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
