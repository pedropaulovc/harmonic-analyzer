r"""Create the curated machinist drawing for the pen square rod.

The SLDPRT remains authoritative.  This recipe supplies only the rod's views,
the placement of its imported model dimensions, the stud-tap callout, the
overall-length reference and the property-linked view notes; sheet/template
and export behavior lives in ``_drawing_common``.  Places, bands and mate
callouts are authored on the part (``pn_pen_rod_spec``).

The side view (1:1) lays the rod axis horizontal, as the bar sits in the
lathe (drawing-guidelines.md rule 11), and carries the square's and the
pivot's lengths from the shoulder, the pivot's banded diameter between its
flanks, the shoulder root's R MAX and the (122.5) end-to-end reference; the
end view (4:1) looks at the tapped top face and carries the square's banded
SQ size and the native Hole Wizard callout of the #0-80 stud tap; the shaded
isometric sits right.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_rod.py pn-pen-rod
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pn_pen_rod_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    PIVOT_DIA,
    PIVOT_LENGTH,
    ROD_SECTION,
    SHOULDER_FILLET_R,
    SHOULDER_FILLET_TOL_TYPE,
    SQUARE_LENGTH,
    STUD_TAP_DRILL_DIA,
    STUD_TAP_SPEC,
    TOTAL_LENGTH,
)


SPEC = DRAWINGS_BY_NAME["pn_pen_rod"]
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

SHEET_SCALE = (1.0, 1.0)  # the 122.5-long rod fits the sheet at full size
SIDE_SCALE = (1, 1)
END_SCALE = (4, 1)  # the 5 mm square's end: tap callout and SQ band need room
ISO_SCALE = (1, 1)
# The rod is modelled axis-along-+Y (its assembly pose), so the side view is
# "*Front" turned -90 deg before any import (IView.Angle,
# draw_dt_cylinder_gear_shaft's PROFILE_ROTATION): model +Y -> sheet +x,
# model +X -> sheet -y.  Pivot end left, tapped top face right; the shoulder
# (model y 0) both axial dimensions start from is near the left end.
SIDE_ROTATION = -math.pi / 2.0
_SIDE_K = SIDE_SCALE[0] / SIDE_SCALE[1] / 1000.0

# The view centres on the part's bounding box: model y -PIVOT_LENGTH to
# SQUARE_LENGTH, x and z +/- S/2.  _prove_side_view_frame reads the frame
# back before anything is placed by it.
_CY = (SQUARE_LENGTH - PIVOT_LENGTH) / 2.0

# Sheet layout (meters; title block x >= 0.2155, y <= 0.0655).  The side view
# spans the left half on y 0.180; the 4:1 end view of the top face stands on
# the same axis to its right, as a right-end projection would; the shaded
# isometric at the far right.
SIDE_CENTER = (0.140, 0.180)
END_CENTER = (0.255, 0.180)
ISO_CENTER = (0.375, 0.170)


def _sx(model_y_mm: float) -> float:
    """Sheet x of a station along the rod axis (model y) in the side view."""
    return SIDE_CENTER[0] + (model_y_mm - _CY) * _SIDE_K


def _sy(model_x_mm: float) -> float:
    """Sheet y of a model x in the side view (model +X points down)."""
    return SIDE_CENTER[1] - model_x_mm * _SIDE_K


def _end_x(center: tuple[float, float], model_x_mm: float) -> float:
    return center[0] + model_x_mm * END_SCALE[0] / END_SCALE[1] / 1000.0


_HALF = ROD_SECTION / 2.0
_END_HALF_M = _HALF * END_SCALE[0] / END_SCALE[1] / 1000.0

# Side view stations: pivot end x 0.07875, shoulder x 0.08925, top face
# x 0.20125; square y 0.1775..0.1825, pivot flanks y 0.178/0.182.
#
# Above the rod, three rows baselined from the shoulder / end faces, each
# sharing its extension lines with the row below at the common face:
#   row 1 (y 0.192, 9.5 mm over the square): 112.0, shoulder to top face,
#     text mid-span (x 0.145);
#   row 2 (y 0.202): 10.5, pivot end to shoulder.  The 10.5 mm span takes no
#     text, so it stands outside left (x 0.066, ~0.0615..0.0705); its
#     outside arrow past the shoulder reaches ~x 0.096, clear of row 1's
#     extension lines, which stop ~1 mm over y 0.192;
#   row 3 (y 0.212): the (122.5) reference, end face to end face.
# Below the rod, where the ShoulderRadius's arc is (model +X, the root the
# vertical layout's leader found):
#   Ø4.000 -0.010/-0.025 between the pivot flanks: the dimension line at
#     mid-pivot (x 0.084) runs down to the four-row block centred on
#     (0.084, 0.142), ~56 x 20 mm (farm PNG of the old bottom view):
#     x 0.056..0.112, y 0.132..0.152;
#   R0.2 MAX / SEATS ON PEN V-BLOCK / MHA-PN-005 down-right of the root:
#     farm audit 20261014T003619Z measured that block x a-0.0281..a+0.0265
#     with its shoulder 8.35 mm under the anchor, so at (0.155, 0.160) it
#     spans x 0.1269..0.1815, y 0.1517..0.1684 (9.1 mm under the square), and
#     its leader runs from the shoulder's left end (0.1269, 0.1517) up-left at
#     ~35 deg to the root (0.0893, 0.1779): right of the Ø's dimension line
#     (x 0.084) all the way, and at the Ø block's right edge (x 0.112) it is
#     at y ~0.162, 10 mm over that block's top.
SIDE_KEEP = {
    "Length": (_sx(SQUARE_LENGTH / 2.0), _sy(-_HALF) + 0.0095),
    "PivotLength": (_sx(-PIVOT_LENGTH) - 0.01275, _sy(-_HALF) + 0.0195),
    "PivotDia": (_sx(-PIVOT_LENGTH / 2.0), _sy(PIVOT_DIA / 2.0) - 0.036),
    "ShoulderRadius": (_sx(0.0) + 0.06575, _sy(_HALF) - 0.0175),
}
OVERALL_REF_XY = (_sx(_CY), _sy(-_HALF) + 0.0295)
# Picks are ENTITIES from the side view's edge scan, not sheet hit-tests:
# the pivot end is a circular edge seen edge-on, and a SelectByID2 point on
# it found nothing (farm leaf 20261014T002718Z: "failed to select pen-rod
# overall length reference edge 1 at sheet (0.069, 0.08875)").  The top face's
# near edge is the visible straight edge across the square at y 112; the
# pivot end is the circle of the pivot's diameter about the rod axis at
# y -10.5.  The sheet points passed beside them only document the layout.
OVERALL_TOP_SHEET_XY = (_sx(SQUARE_LENGTH), _sy(-_HALF + 1.0))
OVERALL_END_SHEET_XY = (_sx(-PIVOT_LENGTH), _sy(-PIVOT_DIA / 2.0 + 1.0))
_EDGE_TOL_MM = 1e-4
# How far the side view's projected stations may sit from the _sx/_sy frame
# every position above is computed in before the build stops.
_FRAME_TOL_M = 2.5e-4

# End view (square 0.245..0.265 x 0.170..0.190) keeps the previous sheet's
# 4:1 top view offsets, which the farm PNG of run 20261014T004931233Z shows
# clear: the banded SQ size (and its two-row mate callout) right of the
# square, its ~60 x 20 mm block (x ~0.270..0.330) standing between its own
# extension lines; the tap callout up-right, its ~46 mm text centred on
# x 0.277 (0.254..0.300, y 0.213..0.222, left of the iso at x >= 0.367), its
# leader dropping almost straight to the drill rim; the scale note (anchored
# at its top left) 7 mm under the square, x ~0.235..0.279, y ~0.159..0.163,
# left of and below the SQ block.
END_KEEP = {
    "Depth": (END_CENTER[0] + _END_HALF_M + 0.035, END_CENTER[1]),
}
TAP_CALLOUT_XY = (END_CENTER[0] + 0.022, END_CENTER[1] + 0.033)
END_NOTE_XY = (END_CENTER[0] - 0.020, END_CENTER[1] - 0.017)


def _lay_side_view_horizontal(adapter: Any, side: Any) -> None:
    """Turn "*Front" by SIDE_ROTATION (rod axis horizontal) and read it back."""
    native = _early_bound(side, "IView")
    native.Angle = SIDE_ROTATION
    rebuild_drawing(adapter, label="lay pen-rod side view horizontal")
    applied = float(native.Angle)
    if abs(math.remainder(applied - SIDE_ROTATION, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError(
            f"pen-rod side view rotation did not take: {applied!r} rad, "
            f"expected {SIDE_ROTATION!r}"
        )


def _prove_side_view_frame(adapter: Any, side: Any) -> None:
    """Every side-view keep, pick and text position is computed in the
    _sx/_sy frame; project the stations it rests on through the turned view
    (ModelToViewTransform) and stop if any lands off it -- the end faces
    prove the axis runs +x at scale and the view centres on its bounding
    box, the square's +X flat at the shoulder that model +X points down."""
    stations = {
        "pivot end": ((0.0, -PIVOT_LENGTH, 0.0), (_sx(-PIVOT_LENGTH), _sy(0.0))),
        "top face": ((0.0, SQUARE_LENGTH, 0.0), (_sx(SQUARE_LENGTH), _sy(0.0))),
        "shoulder +X flat": ((_HALF, 0.0, 0.0), (_sx(0.0), _sy(_HALF))),
    }
    projected = model_points_in_view(
        adapter,
        side,
        [tuple(value / 1000.0 for value in model) for model, _ in stations.values()],
        label="pen-rod side view frame",
        names=list(stations),
    )
    misses = {
        name: (sheet, expected)
        for (name, (_, expected)), sheet in zip(stations.items(), projected)
        if math.dist(sheet, expected) > _FRAME_TOL_M
    }
    if misses:
        raise RuntimeError(f"pen-rod side view is not in its layout frame: {misses}")
    _telemetry.info(f"pen-rod side view frame: {dict(zip(stations, projected))}")


def _dress_shoulder_radius(adapter: Any, annotations: list[Any]) -> None:
    """Prove the side view's imported ShoulderRadius prints the part's R MAX
    with its callout, and stop its leader at the corner.

    Read back: radial (not a diameter), measuring SHOULDER_FILLET_R, the
    native swTolMAX the part set, and the mate callout under the value.  The
    text stands down-right of the corner (the vertical layout's up-right,
    turned with the view), outside the arc's own quadrant, so the leader
    ends on the arc's extension; ``ArcExtensionLineOrOppositeSide`` False
    keeps it from running on through the arc centre into the pivot
    (draw_dt_arbor_pedestal's crown, draw_fr_harmonic_base's corner arcs).
    """
    found = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "ShoulderRadius"
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one ShoulderRadius on the side view, found {len(found)}"
        )
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported shoulder radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != SHOULDER_FILLET_TOL_TYPE:
        raise RuntimeError(
            f"ShoulderRadius lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), SHOULDER_FILLET_R / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("ShoulderRadius does not measure the shoulder fillet")
    callout = str(display.GetText(4) or "")  # swDimensionTextCalloutBelow
    if callout != DIMENSION_CALLOUTS["ShoulderRadius"]:
        raise RuntimeError(f"ShoulderRadius callout did not persist: {callout!r}")
    display.ArcExtensionLineOrOppositeSide = False
    if display.ArcExtensionLineOrOppositeSide is not False:
        raise RuntimeError("ShoulderRadius leader still runs to the opposite side")
    _telemetry.info(
        f"shoulder radius: text {display.GetText(1)!r}, MAX type, callout {callout!r}"
    )


def _edge_inventory(edges: ViewEdges, y_mm: float) -> str:
    """The scan's lines and circles near model y ``y_mm`` (1 mm either
    side), so a failed pick names what the view really holds there."""
    rows = []
    for item in edges.edges:
        if item.line is not None:
            start, end = item.line
            if min(abs(start[1] - y_mm), abs(end[1] - y_mm)) <= 1.0:
                rows.append(f"line {start}-{end}")
        elif item.circle is not None:
            if abs(item.circle[1] - y_mm) <= 1.0:
                rows.append(f"circle {item.circle}")
    return f"{len(rows)} of {len(edges.edges)} edges near y {y_mm:g}: {rows}"


def _top_face_edge(edges: ViewEdges) -> Any:
    """The square's top-face edge nearest the viewer: the visible straight
    edge from (-S/2, SQUARE_LENGTH, +S/2) to (+S/2, SQUARE_LENGTH, +S/2)
    (the far edge at z -S/2 projects onto it, so z pins the one picked)."""
    ends = ((-_HALF, SQUARE_LENGTH, _HALF), (_HALF, SQUARE_LENGTH, _HALF))
    found = [
        item
        for item in edges.lines
        if all(
            any(math.dist(point, end) <= _EDGE_TOL_MM for end in ends)
            for point in item.line
        )
        and item.length_mm > ROD_SECTION / 2.0
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one visible top-face edge across the square, found "
            f"{len(found)}; {_edge_inventory(edges, SQUARE_LENGTH)}"
        )
    return found[0].edge


def _pivot_end_edge(edges: ViewEdges) -> Any:
    """The pivot's end-face rim: the Ø PIVOT_DIA circle on the rod axis at
    y -PIVOT_LENGTH, seen edge-on in the side view."""
    try:
        return edges.circle_at(
            (0.0, -PIVOT_LENGTH, 0.0),
            PIVOT_DIA / 2.0,
            axis=(0.0, 1.0, 0.0),
            label="pivot end rim",
        ).edge
    except RuntimeError as error:
        raise RuntimeError(
            f"{error}; {_edge_inventory(edges, -PIVOT_LENGTH)}"
        ) from error


@_telemetry.traced("drawing.pen_rod.overall_reference")
def _overall_reference(adapter: Any, side: Any) -> None:
    """(122.5): top face to pivot end, a reference the square and pivot
    lengths own (rule 10); a drawing-added edge dimension between two
    scanned entities, proved attached to exactly them and measuring
    TOTAL_LENGTH before it is parenthesised."""
    label = "pen-rod overall length reference"
    # Scanned after every display change to the side view (turn, HLR).
    edges = scan_view_edges(side, label="pen-rod side")
    picks = (_top_face_edge(edges), _pivot_end_edge(edges))
    display = add_edge_dimension(
        adapter,
        side,
        # Documentation only: both picks are by entity.
        p0=OVERALL_TOP_SHEET_XY,
        p1=OVERALL_END_SHEET_XY,
        text_xy=OVERALL_REF_XY,
        label=label,
        # SHEET horizontal: the turned view's axis runs along sheet x (a
        # turned view's vertical measured its sheet-vertical model +Z in
        # draw_mg_magnifying_bracket's _arm_end_reference).
        orientation="horizontal",
        entities=picks,
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension_type = int(display.Type2)
    # swLinearDimension, swHorLinearDimension
    if dimension_type not in (2, 11):
        raise RuntimeError(
            f"{label}: expected a linear dimension, got type {dimension_type}"
        )
    # The rim lies in the plane y -10.5, so any arc end condition reads the
    # same distance; the attachments and the value prove the picks.
    assert_dimension_measures(
        adapter,
        display,
        expected_mm=TOTAL_LENGTH,
        label=label,
        entities=picks,
        tolerance_mm=1e-3,
    )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-rod source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen rod; square brass slide rod; turned pivot end; tapped top",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=SIDE_SCALE)
    # Turned before HLR, the edge scan and every import, so each lands in
    # the horizontal frame; proved against _sx/_sy before anything uses it.
    _lay_side_view_horizontal(adapter, side)
    _prove_side_view_frame(adapter, side)
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=END_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The iso too: a new view already reads Shaded With Edges, so
    # finalize_drawing's SetDisplayMode4 is a no-op that leaves its cosmetic
    # threads at draft quality (farm c0b95549c readback cosmetic_threads=False).
    # From HLR the shading call really changes the mode and takes precision.
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    # PivotDia imports straight into the side view: every farm leaf of the
    # vertical layout logged its targeted *Front import delivering it
    # (unrequested, then deleted), so the turned pivot's banded diameter is
    # dimensioned between its flanks where the lathe reads it (rule 11).
    annotations = [
        *curate_view_dimensions(
            adapter,
            side,
            keep=SIDE_KEEP,
            view_label="side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            end,
            keep=END_KEEP,
            view_label="end",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _dress_shoulder_radius(adapter, annotations)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the stud tap")

    # Pick the tap-drill rim, not the cosmetic thread or the hole centre.
    stud_callout = add_native_hole_callout(
        adapter,
        end,
        edge_xy=(_end_x(END_CENTER, STUD_TAP_DRILL_DIA / 2.0), END_CENTER[1]),
        callout_xy=TAP_CALLOUT_XY,
        label="adjuster stud blind tap",
        process="TAP",
    )
    # The title block's THREADS row owns the general thread class (rule 2).
    omit_title_block_thread_class(stud_callout, label="adjuster stud blind tap")

    _overall_reference(adapter, side)

    add_property_linked_note(adapter, "End View Note", *END_NOTE_XY)

    # Materialize the iso's cosmetic thread before the strict final note cleanup;
    # otherwise its descriptive label first appears during the native drawing save.
    import_cosmetic_threads(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Rod Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(f"{STUD_TAP_SPEC.size} Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
