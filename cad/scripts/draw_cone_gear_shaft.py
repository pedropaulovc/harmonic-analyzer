r"""Create the cone-gear-shaft manufacturing drawing under the simplicity policy.

The turned shaft is shown horizontally at 1:1 with baseline lengths from the
large (faced) end and every diameter on that side view, each one standing on
the shoulder it belongs to.  The last 36 mm carry three short lands down to a
Ø1.588 tip, far too small to read at sheet scale, so a native 3:1 detail
enlarges them and carries their diameters.  A standard isometric supplies
pictorial clarity.  Source geometry and native model fits stay authoritative:
the sheet types no tolerance, no precision and no notes.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_gear_shaft.py cone-gear-shaft
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_surface_finish,
    add_view_centerline,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_gear_shaft_spec import (
    FILLET_CALLOUT,
    JOURNAL_DIA,
    SECTION_DIAS,
    SECTION_ENDS,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    delete_view,
    iter_views,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_gear_shaft"]
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

SHEET_SCALE = (1.0, 1.0)
SIDE_SCALE = (1, 1)
ISO_SCALE = (1, 2)
DETAIL_SCALE = (3, 1)

# Landscape sheet, 0.4318 x 0.2794 m, title block bottom right (x > ~0.216,
# y < ~0.066).  The 205.17 mm shaft at 1:1 spans 0.0474..0.2526 about
# SIDE_CENTER, leaving the right third for the pictorial and the lower left
# for the tip detail.
SIDE_CENTER = (0.150, 0.200)
DETAIL_CENTER = (0.103, 0.082)
ISO_CENTER = (0.345, 0.210)
# Off-sheet-left donor: the five diameters are model dimensions of circular
# profile sketches, so they can only be IMPORTED into a view that faces those
# circles.  They are imported here, dragged onto the shoulder each one
# belongs to, and this view is then deleted.
DONOR_CENTER = (0.360, 0.090)

# The detail fences the tip cluster: from just ahead of the Ø9.525 shoulder
# to past the end of the shaft.
DETAIL_MODEL_Z = (SECTION_ENDS[1] + SECTION_ENDS[4]) / 2.0
DETAIL_RADIUS_MM = (SECTION_ENDS[4] - SECTION_ENDS[1]) / 2.0 + 2.0

# Axial step stations (extrude depths Sec{i}End), all measured from the
# large-end datum face: baseline dimensioning, shortest nearest the part.
SIDE_KEEP = {
    "Sec0End": (0.2311, 0.1855),
    "Sec1End": (0.1672, 0.1765),
    "Sec2End": (0.1638, 0.1675),
    "Sec3End": (0.1603, 0.1585),
    "Sec4End": (0.1499, 0.1495),
    "ShoulderR": (0.1600, 0.2280),
}
# Diameters, imported on the donor and dragged onto their own shoulder: the
# two long lands onto the side view, the three tip lands into the detail.
SIDE_DIAMETERS = {
    "Sec0Dia": (0.2720, 0.2090),
    "Sec1Dia": (0.0819, 0.2150),
}
DETAIL_DIAMETERS = {
    "Sec2Dia": (0.1340, 0.0520),
    "Sec3Dia": (0.1133, 0.0380),
    "Sec4Dia": (0.0513, 0.0520),
}
DONOR_KEEP = {
    name: (DONOR_CENTER[0], DONOR_CENTER[1] - 0.012 * index)
    for index, name in enumerate((*SIDE_DIAMETERS, *DETAIL_DIAMETERS))
}
# Four identical shoulder roots, one modelled fillet, one radius dimension.
DIMENSION_CALLOUTS = {"ShoulderR": FILLET_CALLOUT}


def _project_mm(
    adapter: Any, view: Any, xyz_mm: tuple[float, float, float], *, label: str
) -> tuple[float, float]:
    return model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in xyz_mm), label=label
    )


@_telemetry.traced("drawing.cylindrical_face_scan")
def _cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the visible cylindrical face for one shaft diameter."""
    candidates: list[tuple[float, Any]] = []
    for face in visible_view_entities(view, 3, label="gear-shaft side faces"):
        face = _early_bound(face, "IFace2")
        surface = face.GetSurface()
        if surface is None:
            continue
        surface = _early_bound(surface, "ISurface")
        if not surface.IsCylinder():
            continue
        radius_mm = float(surface.CylinderParams[6]) * 1000.0
        candidates.append((radius_mm, face))
    if not candidates:
        raise RuntimeError("side view has no visible cylindrical faces")
    target_radius = diameter_mm / 2.0
    radius_mm, face = min(candidates, key=lambda item: abs(item[0] - target_radius))
    if abs(radius_mm - target_radius) > 0.01:
        raise RuntimeError(
            f"no cylindrical face matches radius {target_radius:.4f} mm; "
            f"nearest is {radius_mm:.4f} mm"
        )
    return face


def _tip_detail(adapter: Any, side: Any) -> Any:
    """Enlarge the tip cluster natively, rather than redrawing it."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(side, "IView")
    if not ddoc.ActivateView(view_name(adapter, side)):
        raise RuntimeError("failed to activate tip-detail parent")
    draw.ClearSelection2(True)
    center = _project_mm(
        adapter, side, (0.0, 0.0, DETAIL_MODEL_Z), label="tip detail center"
    )
    radius = DETAIL_RADIUS_MM * SIDE_SCALE[0] / SIDE_SCALE[1] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if sketch_manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create tip-detail fence")
    detail = ddoc.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        "A",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create native tip detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    initial_outline = tuple(float(value) for value in detail.GetOutline())
    initial_position = tuple(float(value) for value in detail.Position)
    if len(initial_outline) != 4 or len(initial_position) != 2:
        raise RuntimeError(
            f"invalid native tip detail bounds: {initial_outline!r}, "
            f"{initial_position!r}"
        )
    # A cropped view's Position is not its visible crop center: translate the
    # native origin by the measured outline-center error.
    positioned_origin = tuple(
        initial_position[axis]
        + DETAIL_CENTER[axis]
        - (initial_outline[axis] + initial_outline[axis + 2]) / 2.0
        for axis in range(2)
    )
    if not detail.SetViewPosition(double_array(list(positioned_origin)), False):
        raise RuntimeError("failed to position tip detail")
    draw.EditRebuild3()
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if len(ratio) != 2 or not math.isclose(
        ratio[0] / ratio[1], DETAIL_SCALE[0] / DETAIL_SCALE[1]
    ):
        raise RuntimeError(f"tip detail scale did not persist: {ratio!r}")
    return detail


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move, never copy, a fitted model dimension and verify its new owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
    ]
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-gear-shaft source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Gear Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear shaft; stepped turned steel; gear seats",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SIDE_SCALE)
    donor = place_view(adapter, str(SOURCE), "*Front", *DONOR_CENTER, scale=SIDE_SCALE)
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, donor):
        set_hidden_lines_removed(adapter, view)
    # The detail inherits the parent's display mode, so it is created after
    # the side view is already hidden-lines-removed.
    detail = _tip_detail(adapter, side)

    pivot_face = _cylindrical_face(adapter, side, JOURNAL_DIA)
    tip_face = _cylindrical_face(adapter, side, SECTION_DIAS[-1])
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0] + 0.050, SIDE_CENTER[1]),
        label="shaft longitudinal axis",
        entity=pivot_face,
    )

    # The donor is curated FIRST so the diameters cannot be claimed (and then
    # deleted) by a view that cannot show them.
    donor_annotations = curate_view_dimensions(
        adapter, donor, keep=DONOR_KEEP, view_label="diameter donor"
    )
    side_annotations = curate_view_dimensions(
        adapter, side, keep=SIDE_KEEP, view_label="side"
    )
    annotations = list(side_annotations)
    for annotation in donor_annotations:
        name = dimension_name(adapter, annotation)
        target, text_xy = (
            (side, SIDE_DIAMETERS[name])
            if name in SIDE_DIAMETERS
            else (detail, DETAIL_DIAMETERS[name])
        )
        annotations.append(
            _move_dimension(adapter, annotation, target, text_xy, source_view=donor)
        )
    # Every diameter is now native to the view that shows its shoulder; an
    # empty end view carries no manufacturing information.
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)

    # Leader anchors for the two lands that RUN (sheet metres).
    big_end_x = SIDE_CENTER[0] + SHAFT_LENGTH / 2000.0
    pivot_top = (big_end_x - 0.020, SIDE_CENTER[1] + SECTION_DIAS[0] / 2000.0)
    tip_top = (
        big_end_x - SECTION_ENDS[-2] / 1000.0 - 0.006,
        SIDE_CENTER[1] + SECTION_DIAS[-1] / 2000.0,
    )
    add_surface_finish(
        adapter,
        side,
        symbol_xy=(0.2400, 0.2300),
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_journal"),
        label="pivot journal finish",
        entity_type="FACE",
        entity=pivot_face,
        leader_attach_xy=pivot_top,
    )
    add_surface_finish(
        adapter,
        side,
        symbol_xy=(0.0480, 0.2300),
        control=surface_finish_by_key(SURFACE_FINISHES, "tip_journal"),
        label="tip journal finish",
        entity_type="FACE",
        entity=tip_face,
        leader_attach_xy=tip_top,
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Shaft Manufacturing Drawing",
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
