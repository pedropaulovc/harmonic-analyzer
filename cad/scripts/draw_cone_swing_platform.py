r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  This recipe supplies only the platform's
views, the wedge envelope dimensions, and the machining notes; every shared
sheet/template, import, curation, and export behavior lives in ``_drawing_common``.

The platform is machined from black-oxide 5/16 in minimum steel stock to a
6.35 mm finished plate: an asymmetric wedge (223.35 long, 20 -> 61 wide) with a
Ø6.76 pivot hole at the narrow tip, paired 1/4-20 post-mount taps, an open
lock notch through the west edge, and rounded plan corners. The main plan and
end views run 1:2; the isometric runs 1:3.

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
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)
from _holes import blind_cut_dia_mm
from build_cone_swing_platform import (
    PIVOT_HOLE_SPEC,
    POST_MOUNT_SPEC,
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

SHEET_SCALE = (1.0, 3.0)   # 1:2 plan keeps the 266 mm envelope in-zone

# Sheet layout (meters).  The 1:2 plan is the main definition view; the
# isometric and an end view occupy the open right-hand field.
TOP_CENTER = (0.115, 0.195)
ISO_CENTER = (0.330, 0.175)
END_CENTER = (0.330, 0.095)

# Per-view survivor: overall axis length only. Axis-relative end offsets in the
# notes define both asymmetric end widths without redundant chained dimensions.
TOP_KEEP = {
    "PlateLenDim": (0.048, TOP_CENTER[1]),
}


def _view_xy_mapper(adapter: Any, view: Any) -> Any:
    """Return a model-XYZ -> sheet-XY mapper for ``view``.

    Sheet coordinates are what every annotation placement is expressed in, so
    anything derived from model geometry (a rim centre, a leader attachment on
    an edge) has to come through this transform rather than a hand-measured
    literal -- a literal silently goes stale the next time the part is refitted.
    """
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    transform = _early_bound(view.ModelToViewTransform, "IMathTransform")

    def _view_xy(point_xyz: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array(point_xyz)),
            "IMathPoint",
        )
        mapped = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        values = tuple(float(value) for value in mapped.ArrayData)
        return values[0], values[1]

    return _view_xy


def _add_cone_axis_centerline(adapter: Any, view: Any) -> tuple[float, float]:
    """Draw the plan-view cone axis through the modeled pivot-hole center."""
    _view_xy = _view_xy_mapper(adapter, view)

    expected_radius_m = blind_cut_dia_mm(PIVOT_HOLE_SPEC) / 2000.0
    pivot_centers: list[tuple[float, float]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1), default=()
        ) or ()
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            parameters = tuple(float(value) for value in curve.CircleParams)
            if abs(parameters[6] - expected_radius_m) > 1e-6:
                continue
            pivot_centers.append(_view_xy(parameters[:3]))
    if not pivot_centers:
        raise RuntimeError(
            "cone-platform plan view has no visible pivot-hole rim at "
            f"radius {expected_radius_m:g} m"
        )

    pivot = pivot_centers[0]
    if any(
        abs(center[0] - pivot[0]) > 1e-6 or abs(center[1] - pivot[1]) > 1e-6
        for center in pivot_centers[1:]
    ):
        raise RuntimeError(
            f"cone-platform plan view has conflicting pivot centers: {pivot_centers!r}"
        )
    outline = tuple(float(value) for value in view.GetOutline())
    margin = 0.001
    if not (
        outline[0] - margin <= pivot[0] <= outline[2] + margin
        and outline[1] - margin <= pivot[1] <= outline[3] + margin
    ):
        raise RuntimeError(
            f"projected pivot center {pivot!r} falls outside plan-view outline "
            f"{outline!r}"
        )
    north = (pivot[0], outline[3])
    south = (pivot[0], outline[1])
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    model = adapter.currentModel
    # IDrawingDoc.EditSheet explicitly makes subsequently created geometry
    # sheet-owned. The endpoints are already transformed into sheet space, so
    # this keeps the centerline coincident with the projected model axis.
    drawing.EditSheet()
    sketch_manager = _early_bound(model.SketchManager, "ISketchManager")
    centerline = sketch_manager.CreateCenterLine(
        north[0], north[1], 0.0, south[0], south[1], 0.0
    )
    if centerline is None:
        raise RuntimeError("failed to create cone-axis centerline in plan view")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    return pivot


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the pivot and post-mount rims from the plan view.

    The north-end and long-straight-side edges were dropped with the GD&T that
    referenced them (see ``build``) -- nothing else on this sheet attaches to
    them.
    """
    expected_radius_m = blind_cut_dia_mm(PIVOT_HOLE_SPEC) / 2000.0
    expected_mount_radius_m = blind_cut_dia_mm(POST_MOUNT_SPEC) / 2000.0
    pivot_edges: list[Any] = []
    mount_edges: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1), default=()
        ) or ()
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            values = tuple(float(value) for value in curve.CircleParams)
            if abs(values[6] - expected_radius_m) <= 1e-6:
                pivot_edges.append(edge)
            if abs(values[6] - expected_mount_radius_m) <= 1e-6:
                mount_edges.append(edge)
    if not pivot_edges or len(mount_edges) < 2:
        raise RuntimeError("cone-platform plan view is missing pivot/mount controls")
    return pivot_edges[0], mount_edges[0]


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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=(1, 2))
    for view in (top, iso, end):
        set_hidden_lines_removed(adapter, view)

    top_annotations = curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pivot hole")
    _add_cone_axis_centerline(adapter, top)

    pivot_edge, mount_edge = _visible_plan_controls(adapter, top)
    add_native_hole_callout(
        adapter,
        top,
        callout_xy=(0.170, 0.135),
        label="pivot-hole size",
        edge=pivot_edge,
    )
    add_native_hole_callout(
        adapter,
        top,
        # Below the pair, not level with it: the model's own "1/4-20 Tapped
        # Hole" note drops a leader onto the east hole, and a callout placed
        # level with the holes routes its leader straight across that descent
        # (fail-loud layout gate, 2 leader crossings). Coming up from below
        # keeps this leader clear of the note for the whole span.
        callout_xy=(0.175, 0.225),
        label="v2 post-mount tapped holes",
        edge=mount_edge,
    )
    # NO GD&T on this sheet. The datum tags (A/B/C) and the straightness,
    # perpendicularity, flatness and parallelism frames were removed: the
    # plan-view cluster packs the pivot rim, the north-end plane and the south
    # end of the long straight edge into ~1.4 mm of sheet space, so their
    # leaders cross whenever the wedge is refitted -- and datum B cannot be
    # moved out of the way (SolidWorks snaps the restricted cylindrical tag
    # back to the rim, which trips the placement-persistence bound). Every
    # tolerance those frames carried is now stated in the manufacturing notes
    # instead, so the sheet keeps the intent without the fragile geometry.

    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.100, char_height=0.0025
    )
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
