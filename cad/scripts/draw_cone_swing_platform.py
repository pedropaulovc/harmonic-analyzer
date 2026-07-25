r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  This recipe supplies only the platform's
views, the wedge envelope dimensions, and the machining notes; every shared
sheet/template, import, curation, and export behavior lives in ``_drawing_common``.

The platform is machined from black-oxide 5/16 in minimum steel stock to a
6.35 mm finished plate: an asymmetric wedge (214 long, 21.5 -> 57 wide) with a
Ø6.76 pivot hole at the narrow tip, an open lock notch through the west edge,
and rounded plan corners. The sheet and both views run 1:3 so the plan
dimensions remain inside the zone border.

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
    auto_center_marks,
    add_datum_feature,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)
from _holes import blind_cut_dia_mm
from build_cone_swing_platform import (
    NORTH_OVERHANG,
    PIVOT_HOLE_SPEC,
    PLATE_LEN,
    PLATE_T,
)


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

SHEET_SCALE = (1.0, 3.0)  # 1:3 keeps the 214 mm plan plus dimensions in-zone

# Sheet layout (meters).  The 1:2 plan is the main definition view; the
# isometric and an end view occupy the open right-hand field.
TOP_CENTER = (0.115, 0.210)
ISO_CENTER = (0.330, 0.175)
END_CENTER = (0.330, 0.095)

# Per-view survivor: overall axis length only. Axis-relative end offsets in the
# notes define both asymmetric end widths without redundant chained dimensions.
TOP_KEEP = ("PlateLenDim",)

# Fixed sheet placement from the last live positive control. SolidWorks moves
# the circular datum tag 3.574 mm toward its attached rim, so retain the same
# requested anchor while leaving the resulting leader geometry to SolidWorks.
DATUM_B_SYMBOL_XY = (0.101, 0.160)
_CENTERLINE_OVERRUN_MM = 5.0
_TOP_VIEW_SCALE = 1.0 / 2.0
_CENTERLINE_HALF_SPAN_M = (
    (PLATE_LEN / 2.0 + _CENTERLINE_OVERRUN_MM) * _TOP_VIEW_SCALE / 1000.0
)
CONE_AXIS_NORTH_XY = (
    TOP_CENTER[0],
    TOP_CENTER[1] - _CENTERLINE_HALF_SPAN_M,
)
CONE_AXIS_SOUTH_XY = (
    TOP_CENTER[0],
    TOP_CENTER[1] + _CENTERLINE_HALF_SPAN_M,
)


def _add_cone_axis_centerline(adapter: Any, view: Any) -> Any:
    """Draw the cone axis from its precomputed 1:2 plan-view endpoints."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    model = adapter.currentModel
    # IDrawingDoc.EditSheet explicitly makes subsequently created geometry
    # sheet-owned. The endpoints are already transformed into sheet space, so
    # this keeps the centerline coincident with the projected model axis.
    drawing.EditSheet()
    sketch_manager = _early_bound(model.SketchManager, "ISketchManager")
    centerline = sketch_manager.CreateCenterLine(
        *CONE_AXIS_NORTH_XY,
        0.0,
        *CONE_AXIS_SOUTH_XY,
        0.0,
    )
    if centerline is None:
        raise RuntimeError("failed to create cone-axis centerline in plan view")
    adapter.currentModel.ClearSelection2(True)
    return centerline


def _visible_broad_face_edges(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return bottom datum-A and top broad-face edges in the end view."""
    bottom: list[tuple[float, Any]] = []
    top: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            values = tuple(float(value) for value in curve.LineParams)
            if abs(values[3]) < 0.99:
                continue
            if abs(values[1]) <= 2e-6:
                bottom.append((values[2], edge))
            if abs(values[1] - PLATE_T / 1000.0) <= 2e-6:
                top.append((values[2], edge))
    if not bottom or not top:
        raise RuntimeError(
            "cone-platform end view is missing the broad-face datum edges"
        )
    # Prefer the south-end width edges; they are the longest unbroken
    # representatives of each broad planar face.
    return min(bottom, key=lambda item: item[0])[1], min(top, key=lambda item: item[0])[
        1
    ]


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any, Any]:
    """Return the pivot rim, north datum edge, and a long straight side."""
    expected_radius_m = blind_cut_dia_mm(PIVOT_HOLE_SPEC) / 2000.0
    pivot_edges: list[Any] = []
    north_edges: list[Any] = []
    straight_side_edges: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle():
                values = tuple(float(value) for value in curve.CircleParams)
                if abs(values[6] - expected_radius_m) <= 1e-6:
                    pivot_edges.append(edge)
                continue
            if not curve.IsLine():
                continue
            values = tuple(float(value) for value in curve.LineParams)
            if (
                abs(values[2] - NORTH_OVERHANG / 1000.0) <= 2e-6
                and abs(values[3]) >= 0.99
            ):
                north_edges.append(edge)
            start = adapter._attempt(lambda e=edge: e.GetStartVertex(), default=None)
            end = adapter._attempt(lambda e=edge: e.GetEndVertex(), default=None)
            if start is None or end is None:
                continue
            p0 = tuple(
                float(value) for value in _early_bound(start, "IVertex").GetPoint()
            )
            p1 = tuple(
                float(value) for value in _early_bound(end, "IVertex").GetPoint()
            )
            length = sum((a - b) ** 2 for a, b in zip(p0, p1, strict=True)) ** 0.5
            if abs(values[3]) < 0.99:
                straight_side_edges.append((length, edge))
    if not pivot_edges or not north_edges or len(straight_side_edges) < 2:
        raise RuntimeError(
            "cone-platform plan view is missing pivot/north/straight-side controls"
        )
    straight_side_edges.sort(key=lambda item: item[0], reverse=True)
    return pivot_edges[0], north_edges[0], straight_side_edges[0][1]


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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Plan View Note",
            "Isometric View Note",
            "End View Note",
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
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=(1, 2))

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(adapter, top_annotations, {"PlateLenDim": "+/-0.25"})
    if not auto_center_marks(adapter, top, holes=True):
        raise RuntimeError("failed to add ASME center mark to the pivot hole")
    _add_cone_axis_centerline(adapter, top)

    pivot_edge, north_edge, straight_side_edge = _visible_plan_controls(adapter, top)
    add_native_hole_callout(
        adapter,
        top,
        callout_xy=(0.170, 0.200),
        label="pivot-hole size",
        edge=pivot_edge,
    )
    # A datum tag attached to the Hole Wizard callout reports its native
    # annotation position as sheet (0, 0), so the fail-loud layout gate sees it
    # off-border even though SetPosition2 succeeds. Attach B to the cylindrical
    # feature itself instead, with a short radial leader that unmistakably ends
    # on the projected circumference rather than the centre mark/axis.
    # SolidWorks normalizes this restricted cylindrical tag by 3.574 mm; the
    # bound checks annotation placement only, not part geometry or GD&T.
    add_datum_feature(
        adapter,
        top,
        # Place the native tag one short radial leader from the projected hole
        # rim.  The former distant tag visually merged with the overall-length
        # extension line and could be read as a planar datum.
        symbol_xy=DATUM_B_SYMBOL_XY,
        datum="B",
        label="pivot-hole cylindrical datum feature",
        entity=pivot_edge,
    )
    add_datum_feature(
        adapter,
        top,
        symbol_xy=(0.100, 0.135),
        datum="C",
        label="north-end datum plane",
        entity=north_edge,
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.195, 0.245),
        characteristic="straightness",
        tolerance="0.25",
        quantity="2X LONG STRAIGHT PLAN EDGES",
        label="long-side straightness",
        entity=straight_side_edge,
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.150, 0.125),
        characteristic="perpendicularity",
        tolerance="0.10",
        datums=("A",),
        diameter=True,
        quantity="PIVOT-HOLE AXIS",
        label="pivot-hole-axis perpendicularity",
        entity=pivot_edge,
    )

    datum_a_edge, opposite_face_edge = _visible_broad_face_edges(adapter, end)
    add_datum_feature(
        adapter,
        end,
        symbol_xy=(0.330, 0.080),
        datum="A",
        label="lower broad face",
        entity=datum_a_edge,
    )
    add_feature_control_frame(
        adapter,
        end,
        frame_xy=(0.360, 0.080),
        characteristic="flatness",
        tolerance="0.10",
        quantity="DATUM A BROAD FACE",
        label="datum-A broad-face flatness",
        entity=datum_a_edge,
    )
    add_feature_control_frame(
        adapter,
        end,
        frame_xy=(0.355, 0.107),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("A",),
        quantity="OPPOSITE BROAD FACE",
        label="opposite broad-face parallelism",
        entity=opposite_face_edge,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.100)
    add_property_linked_note(adapter, "Plan View Note", 0.190, 0.205)
    add_property_linked_note(adapter, "Isometric View Note", 0.290, 0.135)
    add_property_linked_note(adapter, "End View Note", 0.300, 0.125)

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
