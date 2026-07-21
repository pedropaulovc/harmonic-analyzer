r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  This recipe supplies only the platform's
views, the wedge envelope dimensions, and the machining notes; every shared
sheet/template, import, curation, and export behavior lives in ``_drawing_common``.

The platform is a black-oxide 1/4 in steel plate: an asymmetric wedge (214 long,
21.5 -> 57 wide) with a Ø6.76 pivot hole at the narrow tip, an open lock notch
through the west edge, and rounded plan corners. The sheet and both views run
1:3 so the plan dimensions remain inside the zone border.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_swing_platform.py cone-swing-platform
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
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
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
)
from solidworks_mcp.adapters.com_variant import double_array
from build_cone_swing_platform import NORTH_OVERHANG, PLATE_LEN


SPEC = DRAWINGS_BY_NAME["cone_swing_platform"]
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

SHEET_SCALE = (1.0, 3.0)   # 1:3 keeps the 214 mm plan plus dimensions in-zone

# Sheet layout (meters).  The plan (top) is the main view (the wedge, ~28 x 107
# at 1:3); the isometric uses the same scale in the open right-hand field.
TOP_CENTER = (0.105, 0.178)
ISO_CENTER = (0.330, 0.175)

# Per-view survivor: overall axis length only. Axis-relative end offsets in the
# notes define both asymmetric end widths without redundant chained dimensions.
TOP_KEEP = {
    "PlateLenDim": (0.048, 0.178),
}


def _add_cone_axis_centerline(adapter: Any, view: Any) -> None:
    """Draw the model X=0 cone axis through the plan view."""
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    transform = _early_bound(view.ModelToViewTransform, "IMathTransform")

    def _sheet_xy(z_mm: float) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([0.0, 0.0, z_mm / 1000.0])),
            "IMathPoint",
        )
        mapped = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        values = tuple(float(value) for value in mapped.ArrayData)
        return values[0], values[1]

    north = _sheet_xy(NORTH_OVERHANG)
    south = _sheet_xy(NORTH_OVERHANG - PLATE_LEN)
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate cone-platform plan for axis centerline")
    sketch_manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    centerline = sketch_manager.CreateCenterLine(
        north[0], north[1], 0.0, south[0], south[1], 0.0
    )
    if centerline is None:
        raise RuntimeError("failed to create cone-axis centerline in plan view")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-swing-platform source", await adapter.open_model(str(SOURCE)))
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
            "Plan View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Plan View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Swing Platform Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone swing platform; wedge plate; pivot; lock notch",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 3))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    top_annotations = curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    set_dimension_callouts(adapter, top_annotations, {"PlateLenDim": "+/-0.25"})
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pivot hole")
    _add_cone_axis_centerline(adapter, top)

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.100)
    add_property_linked_note(adapter, "Plan View Note", 0.040, 0.036)
    add_property_linked_note(adapter, "Isometric View Note", 0.290, 0.108)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Swing Platform Manufacturing Drawing",
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
