r"""Create the curated machinist drawing for the crank arm.

The SLDPRT remains authoritative.  This recipe supplies only the crank-arm
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the arm is 84 mm end to end); the isometric carries an
explicit 1:1 override so it stays clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_arm.py crank-arm
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from crank_arm_spec import (
    ARM_C2C,
    ARM_END_X,
    DIMPLE_X,
    HALF_WIDTH,
    SHAFT_BORE_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_arm"]
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

# Sheet layout (meters).  The front view's model bbox runs -boss..arm-end in X
# (84 mm) and +/-8 in Y; at 2:1 the view is 168 x 32 mm.  Third angle: the top
# view (arm seen edge-on, carrying the cross-pin hole) sits ABOVE the front
# view; the right view (16 x 8 stock section) sits to its right.
FRONT_CENTER = (0.145, 0.135)
TOP_CENTER = (0.145, 0.205)
RIGHT_CENTER = (0.300, 0.135)
ISO_CENTER = (0.360, 0.230)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (2:1, bbox-centred)."""
    bbox_center = (ARM_END_X - HALF_WIDTH) / 2.0
    return FRONT_CENTER[0] + (model_x_mm - bbox_center) * SHEET_SCALE[0] / 1000.0


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Leadered diameters sit above the arm at each feature's station;
# the linear chain stacks below the view, smallest span nearest the geometry.
FRONT_KEEP = {
    "ArmEndX": (0.190, 0.086),
    "DimpleX": (_sheet_x(DIMPLE_X / 2.0), 0.112),
    "BossRadius": (0.052, 0.162),
    "ShaftBoreDia": (_sheet_x(0.0), 0.172),
    "DimpleDia": (_sheet_x(DIMPLE_X), 0.172),
}
RIGHT_KEEP = {"Depth": (0.300, 0.108)}
TOP_KEEP = {}
DIMENSION_CALLOUTS = {
    "ShaftBoreDia": "THRU - REAM 3/8 IN",
    "DimpleDia": "0.5 DEEP",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-arm source", await adapter.open_model(str(SOURCE)))
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
            0: "Crank Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank arm; manufacturing drawing; taper pin",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    # The front view carries the far-side dimple dimensions; HLV exposes its
    # circular edge. The top view exposes the #9 cross-drill meeting the shaft bore.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    # Right view: the 16 x 8 stock section.  Thickness is the model Depth dim;
    # the 16 width is added as an explicit overall across the view's extremes.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    # Top view: cross-drill geometry is visible; its ANSI size/location are in note 6.
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    # The shaft bore is an exact 3/8 in (Ø9.525) reamed bore; notes 2 & 5 cite it
    # to 3 places, so display it to 3 as well (the sheet default is 2). Otherwise
    # the view reads Ø9.53 against the notes' Ø9.525 — a false contradiction.
    set_dimension_precision(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        {"ShaftBoreDia": 3},
    )
    # Arm width (16): dimension the right view's flat top/bottom faces.  At 2:1
    # the 16 x 8 stock section spans +/-0.016 (Y) x +/-0.008 (Z) around the view
    # center, so the two horizontal silhouette edges sit exactly here.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.016),
        p1=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.016),
        text_xy=(RIGHT_CENTER[0] - 0.024, RIGHT_CENTER[1]),
        label="arm-width overall",
    )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Native datum/GD&T/surface annotations replace the former prose notes 5/8/9.
    # Right view is the 16 x 8 stock section: its left broad face is datum A.
    add_datum_feature(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] - 0.008, RIGHT_CENTER[1]),
        symbol_xy=(RIGHT_CENTER[0] - 0.024, RIGHT_CENTER[1]),
        datum="A",
        label="crank broad face",
    )
    shaft_edge = (
        _sheet_x(0.0),
        FRONT_CENTER[1] + SHAFT_BORE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=shaft_edge,
        symbol_xy=(shaft_edge[0] - 0.022, FRONT_CENTER[1] + 0.025),
        datum="B",
        label="crank shaft axis",
    )
    handle_edge = (
        _sheet_x(ARM_C2C),
        FRONT_CENTER[1] + (15.0 / 64.0 * 25.4) * SHEET_SCALE[0] / 2000.0,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=handle_edge,
        frame_xy=(0.222, 0.158),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B"),
        diameter=True,
        label="handle pivot position",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.008, RIGHT_CENTER[1]),
        frame_xy=(0.316, 0.118),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("A",),
        label="crank broad-face parallelism",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=shaft_edge,
        symbol_xy=(0.070, 0.190),
        roughness_ra="1.6",
        label="shaft bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.185)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Arm Manufacturing Drawing",
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
