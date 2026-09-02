r"""Create the curated machinist drawing for the crank arm.

The SLDPRT remains authoritative.  This recipe supplies only the crank-arm
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the arm is 84 mm end to end); the isometric carries an
explicit 1:1 override so it stays clear of the title block.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): the
arm is a pinned hand-crank lever, so it carries no datums, no feature-control
frames, no roughness symbols and no basic dimensions -- the title block's
general tolerances govern everything except the reamed bore, whose fit band
rides the model dimension.

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
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    find_edge_near,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_arc_endpoints_to_center,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from crank_arm_spec import (
    ARM_C2C,
    ARM_END_X,
    ARM_THICKNESS,
    DIMPLE_X,
    HALF_WIDTH,
    PIN_HOLE_DIA,
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
    "ShaftBoreDia": "REAM THRU (3/8 IN)",
    "DimpleDia": "FLAT-BOTTOM 0.5 DEEP",
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
            3: "crank arm; manufacturing drawing; straight cross-hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (Harvey #30 / Lipton):
    # the front view shows the far-side dimple, the top view the #14
    # cross-drill meeting the shaft bore, the right view the bore through the
    # 16 x 8 section.
    for view in (front, top, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    # Right view: the 16 x 8 stock section.  Thickness is the model Depth dim;
    # the 16 width is added as an explicit overall across the view's extremes.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    # Top view: cross-drill geometry is visible; its size is a native hole callout.
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    # The shaft bore is the one fitted feature (reamed 3/8 in, band on the
    # model dimension): three decimals say "hold it"; everything else stays at
    # the two-place block tolerance.
    set_dimension_precision(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        {"ShaftBoreDia": 3},
    )
    # Arm width (16): dimension the right view's flat top/bottom faces, placed
    # to the right of the section where the band is clear.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.016),
        p1=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.016),
        text_xy=(RIGHT_CENTER[0] + 0.050, RIGHT_CENTER[1]),
        label="arm-width overall",
    )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Shaft-to-handle-pivot centres: the one location a machinist sets the DRO
    # to, read from the bore axis (one origin per view).
    handle_edge = (
        _sheet_x(ARM_C2C),
        FRONT_CENTER[1] + (15.0 / 64.0 * 25.4) * SHEET_SCALE[0] / 2000.0,
    )
    add_edge_dimension(
        adapter,
        front,
        p0=(_sheet_x(0.0), FRONT_CENTER[1] + SHAFT_BORE_DIA / 1000.0),
        p1=(_sheet_x(ARM_C2C), FRONT_CENTER[1] + 15.0 / 64.0 * 25.4 / 1000.0),
        text_xy=(_sheet_x(ARM_C2C / 2.0), 0.102),
        label="shaft-to-handle-pivot location",
    )

    # The straight #14 cross-hole, seen in the top view: its station from the
    # broad face (mid-thickness) plus the native size callout.  The note says
    # its axis passes through the bore axis.
    pin_edge = (
        _sheet_x(0.0),
        TOP_CENTER[1] + PIN_HOLE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    pin_station = add_edge_dimension(
        adapter,
        top,
        p0=find_edge_near(
            adapter,
            top,
            (
                _sheet_x(ARM_C2C / 2.0),
                TOP_CENTER[1] + ARM_THICKNESS * SHEET_SCALE[0] / 2000.0,
            ),
            axis="y",
            label="cross-hole broad face",
            span_m=0.020,
            entity_type="EDGE",
        ),
        p1=pin_edge,
        text_xy=(0.045, TOP_CENTER[1] + 0.004),
        label="cross-hole station from broad face",
        orientation="vertical",
        entity_types=("EDGE", "EDGE"),
    )
    set_arc_endpoints_to_center(
        adapter, pin_station, label="cross-hole station from broad face"
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=pin_edge,
        callout_xy=(0.170, 0.230),
        label="crank-arm cross-hole",
    )
    # Handle pivot hole: below the arm, arrow on the hole's bottom rim, text
    # clear of the 76.00 extension line and the right view (measured layout).
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=handle_edge,
        callout_xy=(0.258, 0.110),
        label="handle pivot hole",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.060)
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
