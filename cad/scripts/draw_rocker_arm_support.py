r"""Create the curated machinist drawing for the rocker-arm support.

The SLDPRT remains authoritative.  This recipe supplies only the support's
views, dimension layout, hole table, and casting/machining notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The support is a green-painted gray-iron casting: a trapezoidal wall with a
square window cut from both faces (leaving a central web), a rounded/chamfered
window rim, and four 1/2-13 UNC-2B tapped holes up through the foot. The sheet
runs 1:2, with each view's scale pinned explicitly.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm_support.py rocker-arm-support
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_rocker_arm_support import (
    BOSS_DEPTH,
    CHAMFER,
    HALF_Y,
    HOLES,
    HOLE_SSIZE,
    HOLE_TAP_DRILL_DIA,
    WIDE,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    iter_views,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm_support"]
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

SHEET_SCALE = (1.0, 2.0)

# Sheet layout (meters). A 177.8 mm casting with four views needs a 1:2 ASME B
# sheet. Third-angle projection keeps the taper beside the window face and the
# tapping setup below it. The projected group sits below the zone strip with
# enough separation for dimensions and leaders.
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.085, 0.185)
RIGHT_CENTER = (0.170, 0.185)
BOTTOM_CENTER = (0.085, 0.095)
ISO_CENTER = (0.360, 0.201)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters).
FRONT_KEEP = {
    "Depth": (0.085, 0.253),  # 177.8 overall cast width, above
    # Keep square callout text in the opening rather than on its boundary.
    "WinWidth": (0.085, 0.207),
    "CavWidth": (0.085, 0.173),
}
DIMENSION_CALLOUTS = {
    "WinWidth": "SQ POCKET",
    "CavWidth": "SQ CAVITY THRU",
}
MOUNTING_FACE_CALLOUT = "MACHINED MOUNTING FACE"
DIMENSION_PRECISION = {
    "Depth": 1,
    "WinWidth": 1,
    "CavWidth": 1,
    "WallHeight": 1,
    "FootSpan": 1,
    "TopSpan": 1,
}
RIGHT_KEEP = {
    "WallHeight": (0.197, 0.185),  # 177.8 wall height, right of the taper
    "FootSpan": (0.170, 0.133),  # 63.5 foot section, below the view
    "TopSpan": (0.170, 0.238),  # 16.93 top section, above the view
}

# Top-left anchor; the native four-row table grows down and right while
# remaining clear of the isometric and title block.
HOLE_TABLE_ANCHOR = (0.270, 0.130)


def _bottom_sheet_xy(hole_xz: tuple[float, float]) -> tuple[float, float]:
    """Sheet pick point on a foot-hole rim in the bottom view."""
    x_mm, z_mm = hole_xz
    return (
        BOTTOM_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + (z_mm + HOLE_TAP_DRILL_DIA / 2.0) * VIEW_SCALE / 1000.0,
    )


def _bottom_datum_axes(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the two chamfer-offset datum axes visible in the bottom view."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    x_axes: list[Any] = []
    y_axes: list[Any] = []
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1),
                default=(),
            )
            or ()
        )
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            parameters = tuple(float(value) for value in curve.LineParams)
            if (
                abs(parameters[2] + (WIDE - CHAMFER) / 1000.0) <= 2e-6
                and abs(parameters[3]) >= 0.99
            ):
                x_axes.append(edge)
            if (
                abs(parameters[0] + (BOSS_DEPTH / 2.0 - CHAMFER) / 1000.0) <= 2e-6
                and abs(parameters[5]) >= 0.99
            ):
                y_axes.append(edge)
    if not x_axes or not y_axes:
        raise RuntimeError("bottom view is missing a chamfer-offset foot datum edge")
    return x_axes[0], y_axes[0]


def _add_side_symmetry_centerline(adapter: Any) -> Any:
    """Draw the side-view centre plane that locates the taper and central web."""
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    drawing.EditSheet()
    sketch_manager = _early_bound(model.SketchManager, "ISketchManager")
    extension = 0.004
    half_height = HALF_Y * VIEW_SCALE / 1000.0
    centerline = sketch_manager.CreateCenterLine(
        RIGHT_CENTER[0],
        RIGHT_CENTER[1] - half_height - extension,
        0.0,
        RIGHT_CENTER[0],
        RIGHT_CENTER[1] + half_height + extension,
        0.0,
    )
    if centerline is None:
        raise RuntimeError("failed to create side-view symmetry centerline")
    model.ClearSelection2(True)
    model.EditRebuild3()
    return centerline


def _remove_automatic_thread_notes(adapter: Any) -> int:
    """Delete model-generated thread notes without touching table content."""
    drawing = adapter.currentModel
    drawing_doc = _early_bound(drawing, "IDrawingDoc")
    sheet_view = drawing_doc.GetFirstView()
    views = (
        [sheet_view, *iter_views(adapter)]
        if sheet_view is not None
        else list(iter_views(adapter))
    )
    target = HOLE_SSIZE.casefold()
    notes: list[Any] = []
    for view in views:
        view = _early_bound(view, "IView")
        annotation = adapter._attempt(
            lambda current=view: current.GetFirstAnnotation3(), default=None
        )
        while annotation is not None:
            annotation = _early_bound(annotation, "IAnnotation")
            next_annotation = adapter._attempt(
                lambda current=annotation: current.GetNext3(), default=None
            )
            annotation_type = int(
                adapter._attempt(
                    lambda current=annotation: current.GetType(), default=0
                )
                or 0
            )
            if annotation_type == 6:  # swNote
                specific = adapter._attempt(
                    lambda current=annotation: current.GetSpecificAnnotation(),
                    default=None,
                )
                if specific is not None:
                    note = _early_bound(specific, "INote")
                    text = str(
                        adapter._attempt(
                            lambda current=note: current.GetText(), default=""
                        )
                        or ""
                    )
                    if target in text.casefold():
                        notes.append(annotation)
            annotation = next_annotation

    for annotation in notes:
        drawing.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError("failed to select automatic thread note")
        drawing.EditDelete()
    drawing.ClearSelection2(True)
    drawing.EditRebuild3()
    return len(notes)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm-support source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker-Arm Support Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker-arm support; manufacturing drawing; casting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 2))
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, right, bottom):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    front_dimensions = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_dimensions = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    dimensions = [*front_dimensions, *right_dimensions]
    set_dimension_callouts(adapter, dimensions, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, dimensions, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to bottom view")
    _add_side_symmetry_centerline(adapter)

    add_attached_note(
        adapter,
        right,
        text=MOUNTING_FACE_CALLOUT,
        entity_xy=(
            RIGHT_CENTER[0],
            RIGHT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0,
        ),
        note_xy=(0.105, 0.122),
        label="machined mounting face",
    )

    removed_thread_notes = _remove_automatic_thread_notes(adapter)
    _telemetry.info(
        f"removed {removed_thread_notes} redundant automatic thread note(s)"
    )
    datum_x_axis, datum_y_axis = _bottom_datum_axes(adapter, bottom)
    insert_hole_table(
        adapter,
        bottom,
        datum_xy=(
            BOTTOM_CENTER[0] - BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0,
            BOTTOM_CENTER[1] - WIDE * VIEW_SCALE / 1000.0,
        ),
        hole_points=tuple(_bottom_sheet_xy(hole) for hole in HOLES),
        datum_axes=(datum_x_axis, datum_y_axis),
        expected_locations_mm=tuple(
            (x + BOSS_DEPTH / 2.0 - CHAMFER, z + WIDE - CHAMFER) for x, z in HOLES
        ),
        anchor_xy=HOLE_TABLE_ANCHOR,
        label="rocker-arm-support",
    )

    # x=0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker-Arm Support Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
