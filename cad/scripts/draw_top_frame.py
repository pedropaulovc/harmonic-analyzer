r"""Create the curated machinist drawing for the green-painted top-frame casting.

The SLDPRT remains authoritative.  This recipe supplies only native model
dimensions, associative hole callouts, and the views of the casting; shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``. GEOMETRY defines the frame windows and T-rail section;
HOLES-SOCKETS carries the hole/station plan; CROSS-TAPS carries the front
cross-tap elevation with section A-A through a corner boss; HUB-SET-SCREW
holds the hub location, true-axis side view and the removed set-pocket
section; UNDERSIDE holds the underside locator and its enlarged native
detail.  A group gets its own sheet rather than a crowded corner of one:
qualifiers then park clear of cutting lines, centrelines and each other.
Projected top/front pairs stay aligned; removed and section views carry scales.

Run with SolidWorks open::

    uv run python cad\scripts\draw_top_frame.py top-frame
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from solidworks_mcp.adapters.com_variant import double_array
from _drawing_common import (
    DrawingOutputs,
    FaceLabel,
    PictorialView,
    place_pictorial_sheet,
    add_native_hole_callout,
    assert_imported_precision,
    add_edge_dimension,
    add_surface_finish,
    dimension_name,
    set_arc_endpoints_to_center,
    set_arc_endpoints_to_max,
    set_reference_dimension,
    add_property_linked_note,
    create_section_view,
    create_blank_drawing_sheets,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    offset_dimension_text,
    _select_view_entity,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hole_callout_precision,
    view_name,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    ViewEdges,
    rebuild_drawing,
    scan_view_edges,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _part_pmi import _resolve_faces
from _surface_finish import surface_finish_by_key
from build_top_frame import (
    BAR_X0,
    BAR_X1,
    BORE_DIA,
    BORE_CHAMFER,
    CAP_RECESS_DIAMETER,
    CAP_RECESS_FLOOR_Y,
    BOSS_ABOVE,
    BOSS_BELOW,
    FLANGE,
    FLANGE_BOT_Y,
    EDGE_CHAMFER,
    ROOT_FILLET_R,
    OUTER_Z,
    RAIL_W_FR,
    RAIL_W_SIDE,
    INNER_X,
    INNER_Z,
    LAND_X0,
    LAND_X1,
    RING_HEIGHT,
    WEB_T,
    WEB_IN_X,
    WEB_OUT_X,
    WEB_IN_Z,
    WEB_OUT_Z,
    REAR_COLUMN_Z,
    BOSS_DIA,
    COLUMN_X,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    GOOSENECK_Z,
    HALF_H,
    HUB_BOSS_DIA,
    HUB_BOSS_DROP,
    HUB_GUSSET_T,
    HUB_GUSSET_HALF_IN,
    HUB_GUSSET_HALF_OUT,
    KEEPER_TAP_SPEC,
    KEEPER_TAP_X,
    KEEPER_TAP_Z_FRONT,
    KEEPER_TAP_Z_REAR,
    OUTER_X,
    SET_POCKET_DEPTH,
    SPOTFACE_DIA,
    SET_TAP_SPEC,
    SIDE_TAP_DRILL_DIA,
    STUD_HOLE_DIA,
    STUD_Z_FRONT,
    STUD_Z_REAR,
    TAP_DRILL_MM,
    TOP_SCREW_SEAT_Z,
)
from top_frame_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["top_frame"]
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

SHEET_NAMES = (
    "PICTORIAL",
    "GEOMETRY",
    "HOLES-SOCKETS",
    "CROSS-TAPS",
    "HUB-SET-SCREW",
    "UNDERSIDE",
)
SHEET_SCALE = (1.0, 3.0)
# Sheet scale is a per-sheet property, and the title block's SCALE field
# reads it: a sheet whose views all sit at one scale gets THAT scale, so the
# block states it and no "... SCALE 1:2" note has to.  Only a sheet mixing
# scales (HUB-SET-SCREW: 1:3 plan, 1:2 removed view, 1:1 section) still
# labels the views that differ from its block.
SHEET_SCALES = {
    "PICTORIAL": (1.0, 4.0),
    "GEOMETRY": SHEET_SCALE,
    "HOLES-SOCKETS": (1.0, 2.0),
    "CROSS-TAPS": (1.0, 2.0),
    "HUB-SET-SCREW": SHEET_SCALE,
    "UNDERSIDE": SHEET_SCALE,
}
# The station plan is drawn half size, so its centre-mark axes and label
# lanes derive from its own scale and never from the title block's.
DETAIL_TOP_SCALE = SHEET_SCALES["HOLES-SOCKETS"]
GEOMETRY_VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
DETAIL_VIEW_SCALE = DETAIL_TOP_SCALE[0] / DETAIL_TOP_SCALE[1]

# Plan extents including the proud corner bosses (the straight rails alone
# stop at x +/-214.1 / z +/-131.0): x +/-223.1 -> 446.2 and z +/-138.1 ->
# 276.2 envelope; the boss stack is 47.3 tall around the 36.5 rail band.
PLAN_HALF_X = COLUMN_X + BOSS_DIA / 2.0
PLAN_HALF_Z = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0
GEOMETRY_PLAN_HALF_W = PLAN_HALF_X * GEOMETRY_VIEW_SCALE / 1000.0
GEOMETRY_PLAN_HALF_D = PLAN_HALF_Z * GEOMETRY_VIEW_SCALE / 1000.0
DETAIL_PLAN_HALF_W = PLAN_HALF_X * DETAIL_VIEW_SCALE / 1000.0
DETAIL_PLAN_HALF_D = PLAN_HALF_Z * DETAIL_VIEW_SCALE / 1000.0


# Sheet 1: two octant pictorials, opposite corners, so every face is seen
# once and named once.  Drawn at 1:4 -- two 1:3 isometrics of a 428 x 262
# plan would not fit side by side inside the B-sheet border.
PICTORIAL_SCALE = SHEET_SCALES["PICTORIAL"]
ORIENTATION_KEY_XY = (0.030, 0.052)
ORIENTATION_KEY_TEXT = (
    "FACE NAMES ABOVE ARE THE PRINT'S: FRONT IS THE FACE THE FRONT VIEW SHOWS.\n"
    "MACHINE FRONT (OPERATOR SIDE) IS THE OPPOSITE RAIL, AT THE TOP OF THE PLAN;\n"
    "SHEET 3 'FRONT' / 'REAR' HANGER AND KEEPER NAMES ARE THE MACHINE'S."
)
_LABEL_X = (BAR_X1 + INNER_X) / 2.0  # over the right window, clear of the web
PICTORIAL_VIEWS = (
    PictorialView(
        octant=(-1, 1, 1),  # FRONT-TOP-LEFT
        center_xy=(0.115, 0.165),
        labels=(
            FaceLabel("TOP", (_LABEL_X, HALF_H, (INNER_Z + OUTER_Z) / 2.0), (0.028, 0.232)),
            FaceLabel("FRONT", (_LABEL_X, 0.0, OUTER_Z), (0.170, 0.088)),
            FaceLabel("LEFT", (-OUTER_X, 0.0, 40.0), (0.024, 0.092)),
        ),
    ),
    PictorialView(
        octant=(1, -1, 1),  # FRONT-BOTTOM-RIGHT
        center_xy=(0.305, 0.165),
        labels=(
            FaceLabel("FRONT", (_LABEL_X, 0.0, OUTER_Z), (0.222, 0.228)),
            FaceLabel("RIGHT", (OUTER_X, 0.0, 40.0), (0.392, 0.226)),
            FaceLabel("BOTTOM", (_LABEL_X, -HALF_H, (WEB_IN_Z + WEB_OUT_Z) / 2.0), (0.352, 0.096)),
        ),
    ),
)

# Sheet 2: overall envelope and non-hole geometry.  Top/front remain
# horizontally projected.
GEOMETRY_TOP_CENTER = (0.145, 0.1685)
GEOMETRY_FRONT_CENTER = (0.145, 0.090)

# Sheet 3: the hole/station plan, centred on the sheet it now fills at
# 1:2.  The 25.5 sockets and their 52.2 bosses are the features a machinist
# sets up from, and at 1:3 they were 8.5 mm of paper.
DETAIL_TOP_CENTER = (0.215, 0.160)
# The socket Ra symbol reads off the near-side rim of the rear east socket,
# in the sheet's own empty lower-left corner, so its leader crosses neither
# the 224.00 pitch lane nor the 4X socket qualifier above the view.
SOCKET_FINISH_SYMBOL_XY = (0.050, 0.090)
FINISH_LEADER_TAIL = 0.035

# Sheet 4: the cross-tap elevation across the sheet's upper band with
# section A-A below it, both half size.  A-A carries the cap recess, the
# cap seat and the 47.3 boss stack, so it gets the sheet's whole lower
# half instead of a quarter of its right edge.
DETAIL_FRONT_SCALE = SHEET_SCALES["CROSS-TAPS"]
DETAIL_FRONT_CENTER = (0.145, 0.228)
DETAIL_SECTION_SCALE = (1, 2)
DETAIL_SECTION_CENTER = (0.290, 0.135)
DETAIL_SECTION_CAPTION_XY = (0.240, 0.088)
CAP_SEAT_FINISH_SYMBOL_XY = (0.175, 0.114)
BOSS_ABOVE_RAIL_LINE_XY = (0.3665, 0.1423)
# Above the dimension's own upper arrow, not 51 mm below it -- see the
# boss-height comment in the A-A recipe for what the long leader crossed.
BOSS_ABOVE_RAIL_TEXT_XY = (0.380, 0.176)

# Sheet 5: hub location, true-axis side view, removed set-pocket section.
HUB_TOP_CENTER = (0.145, 0.200)
HUB_LEFT_CENTER = (0.145, 0.095)
HUB_LEFT_SCALE = (1, 2)
HUB_SECTION_CENTER = (0.330, 0.210)
HUB_SECTION_SCALE = (1, 1)
HUB_SECTION_CAPTION_XY = (0.330, 0.178)
POCKET_DEPTH_TEXT_XY = (0.330, 0.238)
POCKET_DEPTH_OFFSET_XY = (0.378, 0.242)
HUB_BORE_FINISH_SYMBOL_XY = (0.030, 0.160)
# One ramp, three numbers: the 60.0 feather span, the 8.0 drop below the
# rail underside and the 20 DEG ramp all park in the band under the hub
# side view, so nobody has to hold one of them on another sheet.
HUB_GUSSET_SPAN_TEXT_XY = (0.180, 0.0810)
HUB_BOSS_DROP_TEXT_XY = (0.120, 0.0848)
HUB_BOSS_DROP_OFFSET_XY = (0.085, 0.0600)
# 186, not 190: MERGES INTO BOSS WALL is 54.8mm of text, and centred any
# further right its block crosses the title block's left edge at x=216.
HUB_GUSSET_ANGLE_TEXT_XY = (0.186, 0.0645)
HUB_LEFT_NOTE_XY = (0.093, 0.0455)

# Sheet 6: the underside locator and its enlarged native detail.  The
# locator sits at the title block's own scale; the detail is the print's
# only 2:1 view because the 7.0 gusset and its 8.0 feather drop are the
# smallest features on the casting.
HUB_BOTTOM_CENTER = (0.110, 0.200)
HUB_BOTTOM_SCALE = (1, 3)
HUB_BOTTOM_NOTE_XY = (0.060, 0.120)
HUB_DETAIL_CENTER = (0.300, 0.174)
HUB_DETAIL_SCALE = (2, 1)
HUB_DETAIL_CAPTION_XY = (0.300, 0.090)
HUB_BOSS_DIA_TEXT_XY = (0.210, 0.100)
HUB_GUSSET_T_TEXT_XY = (0.300, 0.212)
HUB_GUSSET_T_OFFSET_XY = (0.390, 0.243)
LAND_TEXT_OFFSET_XY = (0.155, 0.145)

# Sheet 1, Section E-E: the side rails and the full-height central web, cut
# clear of every hole station (keeper taps at z -70.9 / 77.1, hangers at
# -84.0 / 90.1, corner bosses at z +/-112), so the section carries rail and
# web stock only.
SIDE_SECTION_Z = -56.0
# Removed sections are centred on the cut span, so each centre puts the
# dimensioned profile where it sat when the full cut drew its twin as well:
# B-B's single T at the old right-hand T (the web/flange/chamfer callouts
# keep their lanes), E-E's left rail + web pair where those two stood.
RAIL_SECTION_CENTER = (0.3566, 0.205)
# The lone T is 12 mm tall at 1:3, so the native caption climbs to the web
# width callout unless it is pinned; the column under the T then reads
# caption, B-B note, E-E note, each a text height clear of the next.
RAIL_SECTION_CAPTION_XY = (0.3566, 0.169)
RAIL_SECTION_NOTE_XY = (0.270, 0.1525)
SIDE_SECTION_CENTER = (0.3183, 0.106)
SIDE_SECTION_SCALE = (1, 4)
SIDE_SECTION_CAPTION_XY = (0.3183, 0.0915)
SIDE_SECTION_NOTE_XY = (0.290, 0.133)
SIDE_WEB_TEXT_XY = (0.335, 0.120)

# Only views drawn at a scale the title block does not state carry a label,
# and every label sits under its own view - centred where the dimension
# lanes below the view leave room, offset within that band where they do not.

POCKET_RISE_LINE_XY = (0.070, 0.0785)
POCKET_RISE_TEXT_XY = (0.0422, 0.0785)

# The first sheet contains only the frame/window and T-rail definition.
GEOMETRY_TOP_KEEP = {
    "Width": (
        GEOMETRY_TOP_CENTER[0],
        0.2435,
    ),
    "Depth": (0.046, 0.1335),
    "WinWidth": (
        GEOMETRY_TOP_CENTER[0],
        0.2305,
    ),
    "WinDepth": (0.059, GEOMETRY_TOP_CENTER[1] - 0.012),
    "GussetRunE": (GEOMETRY_TOP_CENTER[0], 0.2205),
}
# The 36.5 rail height is a native WebRing dimension, so the front view
# imports it instead of deriving the same length off two of its own edges:
# one rail height on the print, owned by the model, and B-B stops repeating
# it beside its own flange thickness.
GEOMETRY_FRONT_KEEP = {"RingHeight": (0.238, 0.091)}
GEOMETRY_CALLOUTS = {
    "Width": "RAIL FLANGE EXTENT",
    "Depth": "RAIL FLANGE EXTENT",
    "GussetRunE": "4X 45 DEG GUSSET",
    "RingHeight": "RAIL HEIGHT",
}

# The boss/socket diameters leave the socket they qualify in opposite
# directions so neither leader crosses the other's text.  The hole STATIONS
# are not imported: the model's Hole Wizard placement dims measure from the
# origin -- mid-air on the print, a centre the shop would first have to
# derive from the socket pattern -- so sheet 3 dimensions every hole from
# the socket bore axes instead (``HOLE_STATIONS``, policy rule 7).
DETAIL_TOP_KEEP = {
    "C0Dia": (0.035, 0.232),
    "B0Dia": (0.050, 0.252),
}
# Baseline stations from the socket bores the shop picks up: X from the left
# socket pair's axis plane, Z from the upper pair's, each dimension picked on
# a socket rim and a hole rim (centre to centre).  The Z stations stand in
# the margins beside the socket they measure from, the hanger X above the
# plan, the keeper X under the socket pitch it parallels -- its text pulled
# left along the line, clear of the title block the 396.9 span reaches over.
# The origin note sits in the sheet's empty lower-left, off the left
# socket's extension lines; the boss callout reads from the left of its boss
# so its leader never crosses the hanger X row.
HOLE_STATION_NOTE_XY = (0.030, 0.0585)
# One coordinate system, not two origins: the upper-left socket bore is
# the origin and the line joining the upper socket centres is the X
# direction, so a keeper Z picked up from the upper-RIGHT socket lies on the
# same baseline by construction (advisor review, 2026-09-16).
HOLE_STATION_NOTE = (
    "HOLE X, Z ORIGIN: UPPER-LEFT SOCKET\n"
    "X ALONG THE LINE JOINING THE UPPER SOCKET CENTRES"
)
# Both are native.  The gooseneck bore diameter is GooseneckProfile's own
# circle dimension, and the 27.0 rail pad is RibProfile's -- a Top-plane
# sketch, so it imports into a plan view and not into the 1:2 side view
# that used to derive the same width from the pad's own two edges.
HUB_TOP_KEEP = {
    "GnDia": (0.040, 0.185),
    "RibWidth": (0.060, 0.1465),
}
HUB_LEFT_KEEP = {
    "PocketRise": POCKET_RISE_LINE_XY,
}
HUB_TOP_CALLOUTS = {
    "GnDia": "DRILL THRU\nSAME X AS\nLEFT SOCKETS",
    "RibWidth": "FULL-HEIGHT PAD\nCENTRED ON BORE",
}
DETAIL_FRONT_KEEP = {"S1Dia": (0.045, 0.256)}
DETAIL_SECTION_KEEP = {
    "CapRecessDia": (0.140, 0.170),
    # The cap-seat depth reads beside its own band, not under it: the column
    # below belongs to the 47.3 boss height, whose three-line text is 37 mm
    # wide and has nowhere else to sit on this sheet.
    "CapRecessDepth": (0.386, 0.155),
}
DETAIL_CALLOUTS = {
    "C0Dia": "4X BOSS",
    "B0Dia": "4X SOCKET / REF\nMATCH-FIT ASSIGNED TUBE",
}
FRONT_CALLOUTS = {"S1Dia": "4X SPOTFACE"}
SECTION_CALLOUTS = {
    "CapRecessDia": "4X CAP RECESS",
    "CapRecessDepth": "4X\nCAP SEAT",
}


def _add_view_centerlines(
    adapter: Any,
    view: Any,
    axes: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...],
) -> list[Any]:
    """Create only the owned axes, in the target view's actual sketch frame.

    Returns the ``ISketchSegment`` per axis, in order, so a recipe can
    dimension FROM one (``add_edge_dimension`` with ``"SKETCHSEGMENT"``).
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate drawing centreline view")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    segments = []
    for start, end in axes:
        points = []
        for xyz in (start, end):
            x, y = model_point_in_view(
                adapter, view, tuple(value/1000.0 for value in xyz),
                label="drawing centreline endpoint",
            )
            point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
            points.append(tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData))
        segment = manager.CreateCenterLine(*points[0], *points[1])
        if segment is None:
            raise RuntimeError("failed to create owned drawing centreline")
        segment = _early_bound(segment, "ISketchSegment")
        segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
        if int(segment.Color) != 0:
            raise RuntimeError("owned drawing centreline color did not persist")
        segments.append(segment)
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_add_view_centerlines")
    return segments


def _exact_linear_entities(
    edges: ViewEdges, points: tuple[tuple[float, float, float], ...], *, label: str
) -> list[Any]:
    """The visible straight edges passing exactly through each of ``points``."""
    return [edges.exact_line_through(point, label=label).edge for point in points]


def _set_derived_precision(display: Any, *, label: str) -> int:
    """Give one SHEET-DERIVED dimension the places the part's spec owns.

    Policy rule 2 puts the decimal places on the model dimension, and every
    dimension the part carries is imported and read back
    (``assert_imported_precision``).  What is left on this print are distances
    between two model faces that no single model dimension expresses -- a web
    thickness that is the difference of two profile offsets, a flange between
    two extrude extents, a boss stack that sums three, a chamfer leg, a ramp
    angle.  Their places come from ``top_frame_spec`` all the same, so no place
    count is ever typed into this recipe.
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: swDimensionPrecisionSettings_e do-not-change, for the dual and both
    # tolerance places -- the part owns those too.
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{label}: part-authored precision did not persist -- asked for "
            f"{places} decimal places, dimension reads {applied}"
        )
    return applied


def _cut_face_edge(
    edges: ViewEdges,
    *,
    fixed: dict[int, float],
    near: tuple[int, float, float] | None = None,
    label: str,
) -> tuple[Any, tuple[float, float, float]]:
    """The longest visible cut-face line pinned to ``fixed`` model mm axes.

    ``SetDisplayOnlySurfaceCut`` leaves a section showing its cut faces only,
    so every visible line carries the cut plane's own coordinate.  Pinning
    that axis plus one face level -- a rail top, a boss top, a pocket floor --
    names the face itself instead of a hand-written station a geometry change
    would silently invalidate.  ``near`` is ``(axis, value, window)`` and
    picks between parallel faces (the front boss rather than the rear); the
    longest line wins so a chamfer tangent can never stand in for the face.
    Returns the edge and its midpoint in model mm, ready for ``entities=``.
    """
    candidates = []
    for item in edges.lines:
        start, end = item.line
        if any(
            max(abs(start[axis]-value), abs(end[axis]-value)) > 1e-6
            for axis, value in fixed.items()
        ):
            continue
        midpoint = item.midpoint_mm
        if near is not None and abs(midpoint[near[0]]-near[1]) > near[2]:
            continue
        candidates.append((item.length_mm, item.edge, midpoint))
    if not candidates:
        # Name what IS there: the five lines closest to the pinned axes, so a
        # seat that shows different cut geometry (worker 6, 2026-09-18:
        # D-D outer rail face absent) is diagnosable from the leaf log.
        def deviation(item: Any) -> float:
            start, end = item.line
            return max(
                max(abs(start[axis]-value), abs(end[axis]-value))
                for axis, value in fixed.items()
            )
        nearest = sorted(edges.lines, key=deviation)[:5]
        seen = "; ".join(
            f"{tuple(round(v, 3) for v in item.line[0])}->"
            f"{tuple(round(v, 3) for v in item.line[1])} dev={deviation(item):.3g}"
            for item in nearest
        )
        raise RuntimeError(
            f"{label}: no visible cut-face line at {fixed} (near={near}); "
            f"{len(edges.lines)} visible lines, nearest: {seen}"
        )
    _span, edge, midpoint = max(candidates, key=lambda item: item[0])
    return edge, midpoint


def _checked_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    orientation: str,
    center: bool = False,
    maximum: bool = False,
    reference: bool = False,
    entity_types: tuple[str, str] = ("EDGE", "EDGE"),
    suffix: str = "",
    exact_linear: bool = False,
    exact_vertices: bool = False,
    entities: tuple[Any, Any] | None = None,
    offset_text: tuple[float, float] | None = None,
    edges: ViewEdges | None = None,
) -> Any:
    """Dimension ``p0``-``p1`` on ``view`` and prove it measures ``expected_mm``.

    ``exact_linear`` / ``exact_vertices`` pick the entities off ``edges`` --
    the view's :class:`ViewEdges`, scanned once after its display state is
    final -- so a print with twenty picks off one view sweeps it once.
    """
    selected = list(entities) if entities is not None else None
    if (exact_vertices or exact_linear) and edges is None:
        raise ValueError(f"{label}: an exact pick needs the view's ViewEdges scan")
    if exact_vertices:
        selected = [edges.exact_vertex_at(point, label=label) for point in (p0, p1)]
    elif exact_linear:
        selected = _exact_linear_entities(edges, (p0, p1), label=label)
    points = [
        model_point_in_view(
            adapter, view, tuple(value/1000.0 for value in point), label=label
        )
        for point in (p0, p1)
    ]
    display = add_edge_dimension(
        adapter, view, p0=points[0], p1=points[1], text_xy=text_xy,
        label=label, orientation=orientation,
        entity_types=("VERTEX", "VERTEX") if exact_vertices else entity_types,
        entities=tuple(selected) if selected is not None else None,
    )
    if center:
        set_arc_endpoints_to_center(adapter, display, label=label)
    elif maximum:
        set_arc_endpoints_to_max(adapter, display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    dimension_type = int(native.Type2)
    if dimension_type not in (2, 11, 12):  # linear, horizontal linear, vertical linear
        raise RuntimeError(f"{label}: expected linear dimension, received type {dimension_type}")
    measured = abs(float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue)) * 1000.0
    if abs(measured - expected_mm) > 1e-5:
        raise RuntimeError(f"{label}: measured {measured:g}, expected {expected_mm:g} mm")
    annotation = _early_bound(native.GetAnnotation(), "IAnnotation")
    _set_derived_precision(native, label=label)
    if suffix:
        set_dimension_callouts(adapter, [annotation], {dimension_name(adapter, annotation): suffix})
    if reference:
        set_reference_dimension(adapter, annotation, label=label)
    if offset_text is not None:
        # A short run (4.5 mm at 1:4 is 1.1 mm of paper) cannot hold its own
        # text between the arrows, and text parked past them leaves
        # SolidWorks drawing the dimension line straight through the value.
        # OffsetText buys a leader, so ``offset_text`` parks the text beside
        # the dimension line at ``text_xy`` -- never above or below it, which
        # would only move the same line into the qualifier.
        offset_dimension_text(
            adapter, [annotation], {dimension_name(adapter, annotation): offset_text}
        )
    return native


def _orient_cut_section(
    adapter: Any, view: Any, horizontal_axis: tuple[float, float, float]
) -> None:
    """Show only the cut faces, with model Y up and the named axis right."""
    view = _early_bound(view, "IView")
    section = _early_bound(view.GetSection(), "IDrSection")
    section.SetDisplayOnlySurfaceCut(True)
    if not section.GetDisplayOnlySurfaceCut():
        raise RuntimeError("section retained geometry behind the cutting plane")
    def projected_axes() -> tuple[tuple[float, float], tuple[float, float]]:
        origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="section origin")
        points = [
            model_point_in_view(
                adapter, view, tuple(value/1000.0 for value in axis),
                label="section orientation axis",
            )
            for axis in (horizontal_axis, (0.0, 1.0, 0.0))
        ]
        return tuple(tuple(point[i]-origin[i] for i in range(2)) for point in points)

    horizontal, vertical = projected_axes()
    if horizontal[0]*vertical[1]-horizontal[1]*vertical[0] < 0.0:
        reversed_cut = not bool(section.GetReversedCutDirection())
        section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="projected_axes")
        if bool(section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section cutting direction did not persist")
        horizontal, vertical = projected_axes()
    view.Angle = float(view.Angle)-math.atan2(horizontal[1], horizontal[0])
    rebuild_drawing(adapter, label="projected_axes")
    horizontal, vertical = projected_axes()
    if (
        horizontal[0] <= 0.0 or abs(horizontal[1]) > 1e-8
        or vertical[1] <= 0.0 or abs(vertical[0]) > 1e-8
    ):
        raise RuntimeError(
            f"section model-axis orientation did not persist: {horizontal=}, {vertical=}"
        )


_SECTION_HLR_MODE = 2  # swDisplayMode_e.swHIDDEN


def _assert_section_display(
    adapter: Any,
    view: Any,
    *,
    label: str,
    cut_surface_only: bool,
    removed: bool = False,
) -> None:
    """Read one section view's display mode and cut state back off the sheet.

    Policy rule 7: hidden lines belong only in a view whose features are
    communicated by them.  A section already exposes its interior by cutting,
    so the removed half redrawn as dashed ghosts was the one thing on the view
    saying nothing -- every section on this print is hidden-lines-removed.
    Nothing is lost by it: every line these sections dimension lies IN the cut
    plane and is part of a cut face (see ``_cut_face_edge``).

    Cut-faces-only is the separate question of what lies BEYOND the plane.
    B-B, E-E and D-D cut across a closed rail band whose far side would print
    over the cut faces they exist to dimension; A-A cuts a corner boss with
    open air behind it and stays a full section.  Both flags are read back
    because SolidWorks accepts either silently.

    ``GetPartialSection`` is read against ``removed``: a REMOVED section (B-B,
    E-E -- ``create_section_view(partial=True)``) is partial by definition,
    its line deliberately stopping past the one profile it dimensions; on a
    full section the same flag means the line fell short and the cut did not
    close (no hatch, line and labels in the dangling colour).
    """
    bound = _early_bound(view, "IView")
    mode = int(bound.GetDisplayMode2())
    if mode != _SECTION_HLR_MODE:
        raise RuntimeError(
            f"{label}: section is not hidden-lines-removed (display mode {mode})"
        )
    if bool(bound.GetUseParentDisplayMode()):
        raise RuntimeError(f"{label}: section still follows its parent's display mode")
    section = _early_bound(bound.GetSection(), "IDrSection")
    cut_only = bool(section.GetDisplayOnlySurfaceCut())
    if cut_only != cut_surface_only:
        raise RuntimeError(
            f"{label}: cut-faces-only reads {cut_only}, expected {cut_surface_only}"
        )
    partial = bool(section.GetPartialSection())
    if partial != removed:
        raise RuntimeError(
            f"{label}: partial-section flag reads {partial}; "
            + ("a removed section's line must stop inside the view" if removed
               else "the cutting line stops inside the view (cut did not close)")
        )


_COSMETIC_THREAD_LAYER = "COSMETIC-THREADS-HIDDEN"


def _hide_cosmetic_threads(adapter: Any, view: Any, *, label: str) -> int:
    """Hide SolidWorks' own cosmetic-thread ink in one view.

    A section carries its cut faces and the solid edges beyond the plane.  The
    set tap is neither: its thread is an ANNOTATION SolidWorks attaches to the
    view (measured on D-D: seven ``Hole Thread`` annotations of type 1), so
    hidden-lines-removed does not touch it and it prints as a dashed circle
    over the cut faces, 4 mm from the tap's own axis, describing a thread the
    hub side view already calls out as 1/4-20 UNC - 2B THRU.

    Two routes were measured and refused on this seat: ``Select2`` +
    ``EditDelete`` left all seven in place (build16 -- in a drawing of a PART
    the threads belong to the part's features, as
    ``IDrawingDoc::DeleteAllCosmeticThreads`` documents), and
    ``IAnnotation::Visible = swAnnotationHidden`` read back unchanged
    (build17).  What does hold is the LAYER: each thread annotation is moved
    onto a drawing layer created invisible (``ILayerMgr::AddLayer`` +
    ``ILayer::Visible``), the documented way to hide a class of annotations
    without touching the model.  Both the layer state and every annotation's
    layer are read back, so a refused move fails the build, never prints.
    """
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        # COLORREF black, swLineCONTINUOUS (0), swLW_THIN (0).
        if int(manager.AddLayer(_COSMETIC_THREAD_LAYER, "cosmetic thread ink hidden per view", 0, 0, 0)) != 1:
            raise RuntimeError(f"{label}: failed to add the hidden cosmetic-thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError(
            f"{label}: cosmetic-thread layer did not hide "
            f"(visible={layer.Visible!r}, printable={layer.Printable!r})"
        )
    hidden = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError(f"{label}: a cosmetic thread refused the hidden layer")
        hidden += 1
    if not hidden:
        raise RuntimeError(f"{label}: no cosmetic thread to hide; the set tap moved?")
    rebuild_drawing(adapter, label="_hide_cosmetic_threads")
    return hidden


def _hub_pocket_section(adapter: Any, parent_view: Any) -> Any:
    """A removed section through the hub rail at the bore/set-tap axis.

    The cutting line runs from outside the hub (-X) rail to just past its
    inner face, so ``partial=True`` sections that rail alone: the D arrows sit
    on the hub end of the plan and the view carries the one profile the
    pocket depth hangs on -- the same treatment as B-B/E-E.  (History: a
    full-width cut then ``Crop2`` to the hub, whose leftover construction
    midlines had to be hunted down and whose position had to be re-derived
    from the cropped outline.)
    """
    line = [
        model_point_in_view(
            adapter, parent_view, (x/1000.0, 0.0, GOOSENECK_Z/1000.0),
            label="set-pocket section cutting line",
        )
        for x in (-PLAN_HALF_X-6.0, -INNER_X+5.0)
    ]
    view = create_section_view(
        adapter, parent_view, line_start=line[0], line_end=line[1],
        view_xy=HUB_SECTION_CENTER, section_label="D", scale=HUB_SECTION_SCALE,
        partial=True, label="set-pocket manufacturing section",
    )
    _orient_cut_section(adapter, view, (1.0, 0.0, 0.0))
    set_hidden_lines_removed(adapter, view)
    # A section's position is its cut-plane origin, not the middle of what it
    # shows: the boss hangs below the rail, so centre the OUTLINE on the
    # sheet target instead.
    outline = tuple(float(value) for value in view.GetOutline())
    position = tuple(float(value) for value in view.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("set-pocket section has invalid bounds")
    target = [
        position[axis]+HUB_SECTION_CENTER[axis]-(outline[axis]+outline[axis+2])/2
        for axis in range(2)
    ]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position set-pocket section")
    rebuild_drawing(adapter, label="_hub_pocket_section")
    outline = tuple(float(value) for value in view.GetOutline())
    center = tuple((outline[axis]+outline[axis+2])/2 for axis in range(2))
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if math.dist(center, HUB_SECTION_CENTER) > 0.0001:
        raise RuntimeError("set-pocket section centre did not persist")
    if not math.isclose(ratio[0]/ratio[1], HUB_SECTION_SCALE[0]/HUB_SECTION_SCALE[1]):
        raise RuntimeError("set-pocket section scale did not persist")
    _add_view_centerlines(
        adapter, view,
        (
            ((GOOSENECK_X, -HALF_H-HUB_BOSS_DROP-2.0, GOOSENECK_Z),
             (GOOSENECK_X, HALF_H+2.0, GOOSENECK_Z)),
            ((-OUTER_X-2.0, 0.0, GOOSENECK_Z), (-INNER_X+2.0, 0.0, GOOSENECK_Z)),
        ),
    )
    # The cut plane runs through the pocket centre, so the outer rail face and
    # the pocket floor both appear in it as lines the pocket walls interrupt --
    # picked as faces, since their Y extents depend on the cast rim breaks.
    section_edges = scan_view_edges(view, label="D-D set-pocket section")
    pocket_face_edge, pocket_face_point = _cut_face_edge(
        section_edges, fixed={0: -OUTER_X, 2: GOOSENECK_Z},
        label="set-pocket outer rail face",
    )
    pocket_floor_edge, pocket_floor_point = _cut_face_edge(
        section_edges, fixed={0: -OUTER_X+SET_POCKET_DEPTH, 2: GOOSENECK_Z},
        label="set-pocket floor",
    )
    _checked_dimension(
        adapter, view,
        p0=pocket_face_point, p1=pocket_floor_point,
        text_xy=POCKET_DEPTH_TEXT_XY, label="set-pocket depth from outer rail face",
        expected_mm=SET_POCKET_DEPTH, orientation="horizontal",
        entities=(pocket_face_edge, pocket_floor_edge),
        suffix="POCKET DEPTH\nFROM OUTER FACE",
        offset_text=POCKET_DEPTH_OFFSET_XY,
    )
    _hide_cosmetic_threads(adapter, view, label="D-D set-pocket section")
    _assert_section_display(
        adapter, view, label="D-D set-pocket section", cut_surface_only=True,
        removed=True,
    )
    return view

def _hub_underside_detail(adapter: Any, parent_view: Any) -> Any:
    """Enlarge the native underside; the circular fence is presentation only."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent_view, "IView")
    if not drawing.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError("failed to activate underside detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter, parent_view,
        (GOOSENECK_X/1000.0, (-HALF_H-HUB_BOSS_DROP)/1000.0, GOOSENECK_Z/1000.0),
        label="underside detail centre",
    )
    radius = (HUB_GUSSET_HALF_OUT+HUB_BOSS_DROP)*HUB_BOTTOM_SCALE[0]/HUB_BOTTOM_SCALE[1]/1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0]+radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        points.append(tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create native underside detail fence")
    detail = drawing.CreateDetailViewAt4(
        *HUB_DETAIL_CENTER, 0.0, 0, *HUB_DETAIL_SCALE, "C", 1, True, False, False, 5,
    )
    if detail is None:
        raise RuntimeError("failed to create native underside detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in HUB_DETAIL_SCALE])
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_hub_underside_detail")
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("native underside detail has invalid initial bounds")
    target = [
        position[axis]+HUB_DETAIL_CENTER[axis]-(outline[axis]+outline[axis+2])/2
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position native underside detail")
    rebuild_drawing(adapter, label="_hub_underside_detail")
    outline = tuple(float(value) for value in detail.GetOutline())
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if len(outline) != 4 or len(ratio) != 2:
        raise RuntimeError("native underside detail has invalid final bounds")
    center = tuple((outline[axis]+outline[axis+2])/2 for axis in range(2))
    if not math.isclose(ratio[0]/ratio[1], HUB_DETAIL_SCALE[0]/HUB_DETAIL_SCALE[1]):
        raise RuntimeError("native underside detail scale did not persist")
    if math.dist(center, HUB_DETAIL_CENTER) > 0.0001:
        raise RuntimeError(f"native underside detail centre did not persist: {center}")
    return detail




def _finish_leader_tail(symbol: Any, *, label: str) -> None:
    """Give one surface-finish symbol the horizontal tail its text needs.

    The roughness value hangs to the right of the symbol, so a short bent
    leader draws its own tail straight through "Ra 3.2".
    """
    annotation = _early_bound(symbol.GetAnnotation(), "IAnnotation")
    annotation.BentLeaderLength = FINISH_LEADER_TAIL
    if abs(float(annotation.BentLeaderLength)-FINISH_LEADER_TAIL) > 1e-7:
        raise RuntimeError(f"{label} finish leader did not clear its roughness text")


def _machined_faces(view: Any) -> dict[str, Any]:
    """Resolve every part-owned surface-finish face through ``view``'s model.

    A plan view shows four identical sockets and four identical cap seats,
    so a coordinate pick cannot say which face a symbol qualifies.  The
    part-owned face specs can: each resolves to exactly one model face, and
    ``add_surface_finish`` then re-checks the selected face against the same
    control before it writes the symbol.
    """
    document = _early_bound(
        _early_bound(view, "IView").ReferencedDocument, "IModelDoc2"
    )
    return _resolve_faces(
        document, {control.key: control.face for control in SURFACE_FINISHES}
    )


def _position_view_caption(
    adapter: Any, view: Any, target: tuple[float, float]
) -> None:
    """Move a native section/detail caption without replacing its linked fields."""
    view = _early_bound(view, "IView")
    if int(view.Type) not in (2, 3):  # swDrawingSectionView, swDrawingDetailView
        raise RuntimeError("caption target is not a native section or detail")
    candidates = []
    for raw_note in view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        # GetText is blank at this point; the native view-label fields persist.
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")):
            candidates.append((note, linked_text))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one native linked view caption, found {len(candidates)}")
    note, linked_text = candidates[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position native view caption")
    rebuild_drawing(adapter, label="_position_view_caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("native view caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("view caption lost its native view-label fields")


def _gusset_ramp_angle(adapter: Any, view: Any, view_edges: ViewEdges) -> None:
    """Define the exposed ramp, not the buried sketch flat inside the boss."""
    ramp_points = (
        (-WEB_OUT_X, -HALF_H, GOOSENECK_Z+HUB_GUSSET_HALF_OUT+HUB_BOSS_DROP),
        (GOOSENECK_X-HUB_GUSSET_T/2, -HALF_H-HUB_BOSS_DROP/2,
         GOOSENECK_Z+(HUB_GUSSET_HALF_IN+HUB_GUSSET_HALF_OUT)/2),
    )
    edges = _exact_linear_entities(view_edges, ramp_points, label="hub gusset ramp angle")
    sector = model_point_in_view(
        adapter, view,
        ((GOOSENECK_X-HUB_GUSSET_T/2)/1000.0,
         (-HALF_H-HUB_BOSS_DROP/8)/1000.0,
         (GOOSENECK_Z+HUB_GUSSET_HALF_OUT-HUB_BOSS_DROP)/1000.0),
        label="gusset acute angular sector",
    )
    points = [
        model_point_in_view(
            adapter, view, tuple(value/1000.0 for value in point),
            label="gusset angular pick",
        )
        for point in ramp_points
    ]
    display = add_edge_dimension(
        adapter, view, p0=points[0], p1=points[1], text_xy=sector,
        label="hub gusset ramp angle", orientation="smart", entities=tuple(edges),
    )
    draw = adapter.currentModel
    display = _early_bound(display, "IDisplayDimension")
    if int(display.Type2) != 3:
        raise RuntimeError("gusset ramp dimension is not angular")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    expected = math.atan2(HUB_BOSS_DROP, HUB_GUSSET_HALF_OUT-HUB_GUSSET_HALF_IN)
    if abs(float(dimension.SystemValue)-expected) > 1e-7:
        raise RuntimeError(f"gusset ramp angle measured {dimension.SystemValue} radians, expected {expected}")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*HUB_GUSSET_ANGLE_TEXT_XY, 0.0):
        raise RuntimeError("failed to position native gusset ramp angle")
    _set_derived_precision(display, label="hub gusset ramp angle")
    set_dimension_callouts(
        adapter, [annotation],
        {
            dimension_name(adapter, annotation): (
                "2X GUSSET RAMP\nTO RAIL UNDERSIDE\nMERGES INTO BOSS WALL"
            )
        },
    )
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_gusset_ramp_angle")
    if abs(float(dimension.SystemValue)-expected) > 1e-7:
        raise RuntimeError("gusset ramp angle changed after text positioning")


# SolidWorks attaches one of its own automatic "Tapped Hole" notes to a view
# that imports a tapped feature's marked dimensions.  ``finalize_drawing``
# deletes every one of them before export -- the sheet states each thread in
# its own associative feature callout, which carries the process too.
#
# Neither the COUNT nor the SET of views is specification, and both have been
# tried as the gate.  The count was the bare literal 7, explained by a comment
# claiming the seven came from "five sheets with two of them drawn
# hidden-lines-removed"; both were wrong -- a note arrives once per VIEW that
# imports a tapped feature, and this package has printed 7, then 8, then 5
# across three builds of the same geometry.  The view set replaced it and
# lasted exactly one build: the next run, whose only change was three
# annotation text positions, attached one to GEOMETRY/Section View B-B.  The
# reason is the same for both: SolidWorks attaches a feature's note to
# whichever view imports that feature FIRST, and which instance a re-pick
# lands on is not ours to choose.
#
# So the inventory is evidence, not a gate: it is logged by view so a build
# that changes which views import a tapped feature says so, and it hands
# ``finalize_drawing`` the count this run actually found.  The invariant that
# reaches the print is the deletion -- exactly the inventoried notes must go,
# so a note arriving after the inventory or a deletion pass that misses one
# still fails the build.


@_telemetry.traced("drawing.auto_tapped_hole_notes")
def _auto_tapped_hole_notes(adapter: Any) -> dict[str, int]:
    """Delete SolidWorks' own Hole Wizard notes, named per view, on every sheet.

    Importing model items brings SolidWorks' descriptive thread note ("10-32
    Tapped Hole") along with the geometry, and this recipe replaces every one
    of them with an associative feature callout that also carries the process.
    A bare count cannot say WHICH view changed, and the count is not one per
    sheet: a note arrives once per view that imported a tapped feature, so a
    view added, re-scaled or switched to hidden-lines-removed moves it.  This
    names them, and deletes them here rather than handing the substring to
    ``finalize_drawing``'s sweep: that sweep re-walked every annotation of
    every view, sheet by sheet (13 s of a 270 s build), to find the notes this
    walk -- ``ISheet::GetViews`` off the sheet objects, no sheet activation --
    already holds.  Each deletion is proved by the view's note list read back.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    counts: dict[str, int] = {}
    for sheet_name in drawing.GetSheetNames() or ():
        sheet = _early_bound(drawing.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            hits = [
                note for note in (
                    _early_bound(raw_note, "INote") for raw_note in (view.GetNotes() or ())
                )
                if "tapped hole" in str(note.GetText() or "").lower()
            ]
            if not hits:
                continue
            label = f"{sheet_name}/{view_name(adapter, view)}"
            for note in hits:
                draw.ClearSelection2(True)
                if not _early_bound(note.GetAnnotation(), "IAnnotation").Select2(False, 0):
                    raise RuntimeError(f"{label}: failed to select an automatic tapped-hole note")
                draw.EditDelete()  # VT_VOID: the re-read below is the proof
            draw.ClearSelection2(True)
            survivors = sum(
                1 for raw_note in (view.GetNotes() or ())
                if "tapped hole" in str(_early_bound(raw_note, "INote").GetText() or "").lower()
            )
            if survivors:
                raise RuntimeError(
                    f"{label}: {survivors} automatic tapped-hole note(s) survived deletion"
                )
            counts[label] = len(hits)
    return counts


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open top-frame source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="top-frame package")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Top Frame Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top frame; webbed gray iron ring casting; column bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 0):
        raise RuntimeError("failed to set connected section cutting lines")
    if extension.GetUserPreferenceInteger(542, 0) != 0:
        raise RuntimeError("section cutting-line style did not persist")
    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    # Sheet 1 primes the reader: two octant pictorials with the six faces
    # named where they are seen, so FRONT/TOP/LEFT on the orthographic
    # sheets that follow need no orientation key.  The old 1:5 isometric
    # tucked under the geometry sheet's front view is gone with it.
    if not ddoc.ActivateSheet("PICTORIAL"):
        raise RuntimeError("failed to activate top-frame pictorial sheet")
    place_pictorial_sheet(
        adapter, str(SOURCE), PICTORIAL_VIEWS, scale=PICTORIAL_SCALE,
        label="top-frame pictorials",
    )
    # The face names are the PRINT's (FRONT is the face the front view
    # shows, +Z; RIGHT is +X), the ASME orientation-key reading and the one
    # every *Front/*Right projection in the fleet follows.  The MACHINE's
    # front is the operator side, model -Z -- the opposite rail, at the top
    # of the plan -- and the model-owned hanger/keeper dimension names on
    # sheet 3 (StudFrontZ -> "FRONT HANGER Z") keep that word.  A blind
    # review read the two as conflicting hole locations (codex round 3), so
    # the key says which is which once, here, where the reader starts.
    if add_note(adapter, ORIENTATION_KEY_TEXT, *ORIENTATION_KEY_XY) is None:
        raise RuntimeError("failed to add the pictorial sheet orientation key")

    if not ddoc.ActivateSheet("GEOMETRY"):
        raise RuntimeError("failed to activate top-frame geometry sheet")
    geometry_top = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *GEOMETRY_TOP_CENTER,
        scale=SHEET_SCALE,
    )
    geometry_front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *GEOMETRY_FRONT_CENTER,
        scale=SHEET_SCALE,
    )
    # Policy rule 7: the plan view's hidden rail undersides and land
    # pads repeat what sections B-B and E-E plus the sheet 6 underside
    # view already describe, so they come off the dimensioned plan.
    set_hidden_lines_removed(adapter, geometry_top)
    set_hidden_lines_removed(adapter, geometry_front)
    geometry_top_edges = scan_view_edges(geometry_top, label="geometry top")
    geometry_top_dimensions = curate_view_dimensions(
        adapter,
        geometry_top,
        keep=GEOMETRY_TOP_KEEP,
        view_label="geometry top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    geometry_front_dimensions = curate_view_dimensions(
        adapter,
        geometry_front,
        keep=GEOMETRY_FRONT_KEEP,
        view_label="geometry front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    geometry_annotations = [*geometry_top_dimensions, *geometry_front_dimensions]
    geometry_callouts = {
        name: "" for name in (*GEOMETRY_TOP_KEEP, *GEOMETRY_FRONT_KEEP)
    }
    geometry_callouts.update(GEOMETRY_CALLOUTS)
    set_dimension_callouts(adapter, geometry_annotations, geometry_callouts)
    # Every imported dimension's places are the part's; the whole print's
    # imports are collected here and read back once, before export.
    imported_annotations = [*geometry_annotations]
    _checked_dimension(
        adapter, geometry_top,
        p0=(-PLAN_HALF_X, HALF_H+BOSS_ABOVE, FRONT_COLUMN_Z),
        p1=(PLAN_HALF_X, HALF_H+BOSS_ABOVE, FRONT_COLUMN_Z),
        text_xy=(GEOMETRY_TOP_CENTER[0], 0.2565), label="overall casting width",
        expected_mm=2*PLAN_HALF_X, orientation="horizontal", maximum=True,
        reference=True, suffix="OVERALL",
    )
    _checked_dimension(
        adapter, geometry_top,
        p0=(-COLUMN_X, HALF_H+BOSS_ABOVE, -PLAN_HALF_Z),
        p1=(-COLUMN_X, HALF_H+BOSS_ABOVE, PLAN_HALF_Z),
        text_xy=(0.022, 0.145), label="overall casting depth",
        expected_mm=2*PLAN_HALF_Z, orientation="vertical", maximum=True,
        reference=True,
    )
    _checked_dimension(
        adapter, geometry_top,
        p0=(INNER_X, HALF_H-EDGE_CHAMFER, 0.0),
        p1=(OUTER_X, HALF_H-EDGE_CHAMFER, 0.0),
        text_xy=(0.240, 0.120), label="side flange width",
        expected_mm=RAIL_W_SIDE, orientation="horizontal", exact_linear=True,
        suffix="SIDE FLANGE\nWIDTH", edges=geometry_top_edges,
    )
    for left_x, right_x, text_x, label in (
        (-INNER_X, BAR_X0, 0.105, "left window clear width"),
        (BAR_X1, INNER_X, 0.190, "right window clear width"),
    ):
        _checked_dimension(
            adapter, geometry_top,
            p0=(left_x, HALF_H - EDGE_CHAMFER, 0.0),
            p1=(right_x, HALF_H - EDGE_CHAMFER, 0.0),
            text_xy=(text_x, 0.118), label=label,
            expected_mm=right_x-left_x, orientation="horizontal", exact_linear=True,
            edges=geometry_top_edges,
        )
    _checked_dimension(
        adapter, geometry_top,
        p0=(BAR_X0, HALF_H-EDGE_CHAMFER, 0.0),
        p1=(BAR_X1, HALF_H-EDGE_CHAMFER, 0.0),
        text_xy=(GEOMETRY_TOP_CENTER[0], 0.1095), label="central web width",
        expected_mm=BAR_X1-BAR_X0, orientation="horizontal", exact_linear=True,
        suffix="CENTRAL WEB", edges=geometry_top_edges,
    )
    # B-B is a REMOVED section: the cutting line crosses the +Z rail alone
    # (the -Z rail is its mirror), so the section shows the one T profile the
    # web, flange, chamfer and root dimensions hang on instead of that
    # profile beside an identical twin 80 mm away carrying nothing.
    rail_cut_x = COLUMN_X / 2.0
    rail_cut = [
        model_point_in_view(
            adapter, geometry_top, (rail_cut_x/1000.0, 0.0, z/1000.0),
            label="front rear rail section station",
        )
        for z in (PLAN_HALF_Z+6.0, INNER_Z-6.0)
    ]
    rail_section = create_section_view(
        adapter, geometry_top,
        line_start=rail_cut[0],
        line_end=rail_cut[1],
        view_xy=RAIL_SECTION_CENTER, section_label="B", scale=(1, 3),
        partial=True, label="T rail manufacturing section",
    )
    _orient_cut_section(adapter, rail_section, (0.0, 0.0, 1.0))
    # The display mode comes before any pick: ``scan_view_edges``
    # answers for the mode the view is in, so an edge picked while the
    # ghosts were drawn would dimension a line the print does not carry.
    set_hidden_lines_removed(adapter, rail_section)
    rail_section_edges = scan_view_edges(rail_section, label="B-B rail section")
    # Each text parks clear of every witness line: the two widths sit beside
    # their extension lines.  The 8.0 flange run is 2.7 mm of paper, so it
    # needs a leader, and the lane the 36.5 rail height used to occupy is
    # now free for it -- that height is imported into the front view.
    for p0, p1, expected, xy, orientation, label, qualifier, offset in (
        ((rail_cut_x, 0.0, WEB_IN_Z), (rail_cut_x, 0.0, WEB_OUT_Z),
         WEB_T, (0.380, 0.192), "horizontal", "rail web thickness", "WEB WIDTH", None),
        ((rail_cut_x, (FLANGE_BOT_Y+HALF_H-EDGE_CHAMFER)/2, INNER_Z),
         (rail_cut_x, (FLANGE_BOT_Y+HALF_H-EDGE_CHAMFER)/2, OUTER_Z),
         RAIL_W_FR, (0.328, 0.230), "horizontal", "front rear flange width",
         "FLANGE WIDTH", None),
        ((rail_cut_x, HALF_H, (INNER_Z+WEB_IN_Z)/2),
         (rail_cut_x, FLANGE_BOT_Y, (INNER_Z+WEB_IN_Z)/2),
         FLANGE, (0.372, 0.2117), "vertical", "top flange thickness", "TOP FLANGE",
         (0.389, 0.2245)),
    ):
        _checked_dimension(
            adapter, rail_section, p0=p0, p1=p1, text_xy=xy,
            label=label, expected_mm=expected, orientation=orientation, exact_linear=True,
            suffix=qualifier, offset_text=offset, edges=rail_section_edges,
        )
    _checked_dimension(
        adapter, rail_section,
        p0=(rail_cut_x, HALF_H, INNER_Z + EDGE_CHAMFER),
        p1=(rail_cut_x, HALF_H-EDGE_CHAMFER, INNER_Z),
        text_xy=(0.290, 0.250), label="top rim chamfer",
        expected_mm=EDGE_CHAMFER, orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"), exact_vertices=True,
        suffix="X 45 DEG TOP RIMS", edges=rail_section_edges,
    )
    root_arcs = [
        item.edge for item in rail_section_edges.circles
        if abs(item.circle[6]-ROOT_FILLET_R) < 1e-6
    ]
    if not root_arcs:
        raise RuntimeError("T rail section has no source root fillet")
    _select_view_entity(
        adapter, rail_section, "EDGE", None, label="T rail root radius",
        entity=root_arcs[0],
    )
    root_display = drawing_model.AddRadialDimension2(0.305, 0.1955, 0.0)
    if root_display is None:
        raise RuntimeError("failed to dimension T rail root radius")
    root_display = _early_bound(root_display, "IDisplayDimension")
    root_value = float(_early_bound(root_display.GetDimension2(0), "IDimension").SystemValue)*1000.0
    if abs(root_value-ROOT_FILLET_R) > 1e-6:
        raise RuntimeError(f"T rail root radius measured {root_value:g}")
    root_annotation = _early_bound(root_display.GetAnnotation(), "IAnnotation")
    set_dimension_callouts(adapter, [root_annotation], {dimension_name(adapter, root_annotation): "TYP WEB ROOT"})
    _set_derived_precision(root_display, label="T rail root radius")
    drawing_model.ClearSelection2(True)
    _position_view_caption(adapter, rail_section, RAIL_SECTION_CAPTION_XY)
    if add_note(
        adapter, "B-B: FRONT / REAR RAILS, IDENTICAL\nWEB CENTRED UNDER TOP FLANGE",
        *RAIL_SECTION_NOTE_XY,
    ) is None:
        raise RuntimeError("failed to identify the cut rails and centred webs")
    _assert_section_display(
        adapter, rail_section, label="B-B T rail section", cut_surface_only=True, removed=True
    )
    # B-B cuts the front/rear rails only, so the 34.2 side rails and the
    # 22.0 central web had no web thickness, root radius or rim chamfer
    # anywhere on the print, yet the keeper taps and the hanger holes are cut
    # into exactly that stock.  E-E is a second removed section: its cutting
    # line runs from outside the left side rail to just past the central web,
    # so the print shows the one side rail it dimensions and the full-height
    # web beside it -- not the right rail's identical, unannotated twin.
    side_cut = [
        model_point_in_view(
            adapter, geometry_top, (x/1000.0, 0.0, SIDE_SECTION_Z/1000.0),
            label="side rail section station",
        )
        for x in (BAR_X1+6.0, -PLAN_HALF_X-6.0)
    ]
    side_section = create_section_view(
        adapter, geometry_top,
        line_start=side_cut[0], line_end=side_cut[1],
        view_xy=SIDE_SECTION_CENTER, section_label="E", scale=SIDE_SECTION_SCALE,
        partial=True, label="side rail manufacturing section",
    )
    _orient_cut_section(adapter, side_section, (1.0, 0.0, 0.0))
    set_hidden_lines_removed(adapter, side_section)
    _checked_dimension(
        adapter, side_section,
        p0=(-WEB_OUT_X, 0.0, SIDE_SECTION_Z),
        p1=(-WEB_IN_X, 0.0, SIDE_SECTION_Z),
        text_xy=SIDE_WEB_TEXT_XY, label="side rail web thickness",
        expected_mm=WEB_T, orientation="horizontal", exact_linear=True,
        suffix="2X SIDE RAIL WEB",
        edges=scan_view_edges(side_section, label="E-E side rail section"),
    )
    _position_view_caption(adapter, side_section, SIDE_SECTION_CAPTION_XY)
    if add_note(
        adapter, "E-E: LEFT SIDE RAIL AND FULL-HEIGHT CENTRAL WEB\nRIGHT SIDE RAIL IDENTICAL",
        *SIDE_SECTION_NOTE_XY,
    ) is None:
        raise RuntimeError("failed to identify the cut side rail and central web")
    _assert_section_display(
        adapter, side_section, label="E-E side rail section", cut_surface_only=True, removed=True
    )
    # The plan and front views are projected at the title block's own scale,
    # so a label restating it would be the one thing on the sheet saying
    # nothing.

    if not ddoc.ActivateSheet("HOLES-SOCKETS"):
        raise RuntimeError("failed to activate top-frame holes/sockets sheet")
    detail_top = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *DETAIL_TOP_CENTER,
        scale=DETAIL_TOP_SCALE,
    )
    set_hidden_lines_removed(adapter, detail_top)
    detail_top_dimensions = curate_view_dimensions(
        adapter,
        detail_top,
        keep=DETAIL_TOP_KEEP,
        view_label="holes/sockets top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail_top_callouts = {name: "" for name in DETAIL_TOP_KEEP}
    detail_top_callouts.update(DETAIL_CALLOUTS)
    set_dimension_callouts(adapter, detail_top_dimensions, detail_top_callouts)
    imported_annotations += detail_top_dimensions
    socket_annotations = [
        annotation for annotation in detail_top_dimensions
        if dimension_name(adapter, annotation) == "B0Dia"
    ]
    if len(socket_annotations) != 1:
        raise RuntimeError("expected one native socket nominal for reference display")
    socket_display = set_reference_dimension(
        adapter, socket_annotations[0], label="matched socket nominal", diameter=True,
    )
    socket_dimension = _early_bound(socket_display.GetDimension2(0), "IDimension")
    if int(socket_dimension.GetToleranceType()) != 0:  # swTolNONE
        raise RuntimeError("socket source still carries a fixed fit tolerance; rebuild the part")
    if not auto_center_marks(adapter, detail_top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top-frame hole pattern")
    # No origin centrelines or X/Z axis tags on this sheet: nothing here is
    # dimensioned from the frame centre any more, and drawn axes would
    # invite reading it as the datum.
    # The title block names no finish grade ("CAST/MACHINED"), so every
    # surface that must be cut says so on the face: the tube sockets and
    # their cap seats locate the columns, the hub bore locates the
    # gooseneck.  Each symbol carries the part's own control and attaches
    # to the one model face that control names.
    machined_faces = _machined_faces(detail_top)
    socket_finish = add_surface_finish(
        adapter,
        detail_top,
        symbol_xy=SOCKET_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "socket_east_rear"),
        label="tube socket bore finish",
        entity_type="FACE",
        entity=machined_faces["socket_east_rear"],
        leader_attach_xy=model_point_in_view(
            adapter,
            detail_top,
            (-COLUMN_X/1000.0, 0.0, (REAR_COLUMN_Z+BORE_DIA/2)/1000.0),
            label="socket bore finish leader",
        ),
        char_height=0.0025,
    )
    _finish_leader_tail(socket_finish, label="tube socket bore")
    _checked_dimension(
        adapter, detail_top,
        p0=(-COLUMN_X, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z + BORE_DIA/2),
        p1=(COLUMN_X, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z + BORE_DIA/2),
        text_xy=(0.190, 0.0885), label="socket horizontal pitch",
        expected_mm=2*COLUMN_X, orientation="horizontal", center=True,
        suffix="MATCHES MHA-035",
    )
    _checked_dimension(
        adapter, detail_top,
        p0=(COLUMN_X + BORE_DIA/2, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z),
        p1=(COLUMN_X + BORE_DIA/2, HALF_H + BOSS_ABOVE, REAR_COLUMN_Z),
        text_xy=(0.083, 0.168), label="socket vertical pitch",
        expected_mm=REAR_COLUMN_Z-FRONT_COLUMN_Z, orientation="vertical",
        center=True,
        suffix="MATCHES MHA-035",
    )
    stud_edge = model_point_in_view(
        adapter,
        detail_top,
        (
            ((BAR_X0 + BAR_X1) / 2.0) / 1000.0,
            HALF_H / 1000.0,
            (STUD_Z_FRONT + STUD_HOLE_DIA / 2.0) / 1000.0,
        ),
        label="top-frame hanger-stud hole edge",
    )
    add_native_hole_callout(
        adapter,
        detail_top,
        edge_xy=stud_edge,
        # Right of the 182.0 hanger-X row's end, so the leader reaches the
        # hole past that row instead of across it (codex round 5).
        callout_xy=(0.262, 0.258),
        label="2X hanger-stud clearance holes",
        process="HANGER DRILL",
    )
    keeper_edge = model_point_in_view(
        adapter,
        detail_top,
        (
            KEEPER_TAP_X / 1000.0,
            HALF_H / 1000.0,
            (KEEPER_TAP_Z_FRONT + TAP_DRILL_MM[KEEPER_TAP_SPEC.size] / 2.0)
            / 1000.0,
        ),
        label="top-frame fulcrum-keeper tap edge",
    )
    keeper_callout = add_native_hole_callout(
        adapter,
        detail_top,
        edge_xy=keeper_edge,
        callout_xy=(0.3660, 0.247),
        label="2X fulcrum-keeper blind taps",
        process="KEEPER TAP",
    )
    # Blind depths under the general .X band, not the .XX the native two
    # places would ask for (codex round 4); the 3.45 drill keeps its places.
    set_hole_callout_precision(
        keeper_callout, {"hw-tapdrldepth": 1, "hw-threaddepth": 1},
        label="keeper tap depths",
    )
    upper_left_rim = (-COLUMN_X, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z + BORE_DIA/2)
    upper_right_rim = (COLUMN_X, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z + BORE_DIA/2)
    hanger_x = (BAR_X0 + BAR_X1) / 2.0
    keeper_drill_r = TAP_DRILL_MM[KEEPER_TAP_SPEC.size] / 2.0
    for p0, p1, expected, xy, orientation, label, suffix in (
        (upper_left_rim, (hanger_x, HALF_H, STUD_Z_FRONT + STUD_HOLE_DIA/2),
         COLUMN_X + hanger_x, (0.162, 0.240), "horizontal",
         "hanger x from left sockets", "2X HANGER X"),
        (upper_left_rim, (hanger_x, HALF_H, STUD_Z_FRONT + STUD_HOLE_DIA/2),
         STUD_Z_FRONT - FRONT_COLUMN_Z, (0.062, 0.209), "vertical",
         "front hanger z from upper sockets", "FRONT HANGER Z"),
        (upper_left_rim, (hanger_x, HALF_H, STUD_Z_REAR + STUD_HOLE_DIA/2),
         STUD_Z_REAR - FRONT_COLUMN_Z, (0.040, 0.165), "vertical",
         "rear hanger z from upper sockets", "REAR HANGER Z"),
        (upper_left_rim, (KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_FRONT + keeper_drill_r),
         KEEPER_TAP_X + COLUMN_X, (0.150, 0.0745), "horizontal",
         "keeper x from left sockets", "KEEPER X"),
        (upper_right_rim, (KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_FRONT + keeper_drill_r),
         KEEPER_TAP_Z_FRONT - FRONT_COLUMN_Z, (0.350, 0.205), "vertical",
         "front keeper z from upper sockets", "FRONT KEEPER Z"),
        (upper_right_rim, (KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_REAR + keeper_drill_r),
         KEEPER_TAP_Z_REAR - FRONT_COLUMN_Z, (0.372, 0.160), "vertical",
         "rear keeper z from upper sockets", "REAR KEEPER Z"),
    ):
        _checked_dimension(
            adapter, detail_top, p0=p0, p1=p1, text_xy=xy, label=label,
            expected_mm=expected, orientation=orientation, center=True,
            suffix=suffix,
        )
    detail_top_note = add_note(adapter, HOLE_STATION_NOTE, *HOLE_STATION_NOTE_XY)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.040, 0.045, char_height=0.0035,
    )
    if not ddoc.ActivateSheet("CROSS-TAPS"):
        raise RuntimeError("failed to activate top-frame cross-tap sheet")
    detail_front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *DETAIL_FRONT_CENTER,
        scale=DETAIL_FRONT_SCALE,
    )
    cut_x = model_point_in_view(
        adapter,
        detail_front,
        (COLUMN_X / 1000.0, 0.0, 0.0),
        label="top-frame corner-section axis",
    )[0]
    detail_section = create_section_view(
        adapter,
        detail_front,
        line_start=(cut_x, DETAIL_FRONT_CENTER[1] - 0.020),
        line_end=(cut_x, DETAIL_FRONT_CENTER[1] + 0.030),
        view_xy=DETAIL_SECTION_CENTER,
        section_label="A",
        scale=DETAIL_SECTION_SCALE,
        label="top-frame corner section",
    )
    # Rule 7: hidden lines only where they inform.  The cross-taps this
    # elevation calls out are spotfaced from the face it looks at, so the
    # Ø9.0 spotface rim and the tap drill circle inside it are VISIBLE ink
    # and the 10-32 callout, its 48.00/46.00 depths (text, not drawn) and the
    # 22.7 tap-axis-below-boss-top dimension keep their attachments without
    # them.  What the dashed lines added was the far end's sockets, cap
    # recesses and hanger-stud stacks -- none of them dimensioned here, all of
    # them cut open by A-A or specified by their own callouts -- crossing the
    # leaders that reach the taps.
    set_hidden_lines_removed(adapter, detail_front)
    set_hidden_lines_removed(adapter, detail_section)
    detail_front_edges = scan_view_edges(detail_front, label="holes/sockets front")
    detail_section_edges = scan_view_edges(detail_section, label="A-A socket section")
    # A-A's owned axes: the screw axis the section cuts along, and the two
    # socket bore axes it crosses -- the datum the spotface floors are
    # located from.
    _screw_axis, *bore_axes = _add_view_centerlines(
        adapter, detail_section,
        (
            ((COLUMN_X, 0.0, -PLAN_HALF_Z), (COLUMN_X, 0.0, PLAN_HALF_Z)),
            ((COLUMN_X, -HALF_H-BOSS_BELOW-3.0, FRONT_COLUMN_Z),
             (COLUMN_X, HALF_H+BOSS_ABOVE+3.0, FRONT_COLUMN_Z)),
            ((COLUMN_X, -HALF_H-BOSS_BELOW-3.0, REAR_COLUMN_Z),
             (COLUMN_X, HALF_H+BOSS_ABOVE+3.0, REAR_COLUMN_Z)),
        ),
    )
    _position_view_caption(adapter, detail_section, DETAIL_SECTION_CAPTION_XY)
    detail_front_dimensions = curate_view_dimensions(
        adapter,
        detail_front,
        keep=DETAIL_FRONT_KEEP,
        view_label="holes/sockets front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail_section_dimensions = curate_view_dimensions(
        adapter,
        detail_section,
        keep=DETAIL_SECTION_KEEP,
        view_label="holes/sockets section A-A",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = [*detail_front_dimensions, *detail_section_dimensions]
    section_callouts = {
        name: "" for name in (*DETAIL_FRONT_KEEP, *DETAIL_SECTION_KEEP)
    }
    section_callouts.update(FRONT_CALLOUTS)
    section_callouts.update(SECTION_CALLOUTS)
    set_dimension_callouts(adapter, section_annotations, section_callouts)
    imported_annotations += section_annotations
    spotface_annotations = [
        annotation for annotation in detail_front_dimensions
        if dimension_name(adapter, annotation) == "S1Dia"
    ]
    if len(spotface_annotations) != 1:
        raise RuntimeError("expected one native spotface profile diameter")
    spotface_display = _early_bound(
        spotface_annotations[0].GetSpecificAnnotation(), "IDisplayDimension"
    )
    spotface_dimension = _early_bound(spotface_display.GetDimension2(0), "IDimension")
    if not str(spotface_dimension.FullName).startswith("S1Dia@SpotFaceRearProfile@"):
        raise RuntimeError(f"wrong native spotface feature: {spotface_dimension.FullName}")
    spotface_value = abs(float(spotface_dimension.SystemValue))*1000.0
    if abs(spotface_value-SPOTFACE_DIA) > 1e-6:
        raise RuntimeError(f"native spotface profile diameter measured {spotface_value:g}")
    boss_pick_z = REAR_COLUMN_Z+(CAP_RECESS_DIAMETER+BOSS_DIA)/4
    # Both boss-height callouts used to park their text across the sheet from
    # the dimension line it belongs to, and the leader back paid for it: the
    # 47.3's ran 22 mm up-left through this boss's own top extension line, the
    # 4.5's 51 mm down through its bottom one (both measured off the exported
    # PDF, y=146.8 and y=123.2).  Each text now stays in its own dimension's
    # column: the 47.3 beside its dimension line, inside the band its arrows
    # bracket, so the leader is the width of the gap and crosses nothing; the
    # 4.5 above its upper arrow, where its leader leaves the line's top stub.
    # Neither may drift left of x=378 or the extension lines run under the
    # text, nor below y=137 or the cap-seat callout's do.
    #
    # One crossing survives and is accepted: the 47.3, the 4.5 and the 16.30
    # cap-seat depth all measure FROM the boss top face, so their upper
    # extension lines are collinear at y=146.8 and each runs right to its own
    # dimension line (x=366.5, 377, 387).  The 4.5's leader leaves its line
    # mid-band at y=145.7 -- below that shared face -- so any text it can
    # reach costs one crossing of a line collinear with its own, 0.3 mm from
    # where its own extension line ends.  The layout audit reports it as
    # leader-crosses-leader at (366.2,146.8); the alternatives measured worse
    # (text over the cut faces, or the cap-seat callout's stub through this
    # text), and no arrangement of three dimensions off one face avoids it.
    _checked_dimension(
        adapter, detail_section,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, boss_pick_z),
        p1=(COLUMN_X, -HALF_H-BOSS_BELOW, boss_pick_z),
        text_xy=(0.377, 0.135), label="socket boss overall height",
        expected_mm=RING_HEIGHT+BOSS_ABOVE+BOSS_BELOW,
        orientation="vertical", exact_linear=True, suffix="4X BOSS\nOVERALL HEIGHT",
        offset_text=(0.398, 0.130), edges=detail_section_edges,
    )
    # The 47.3 boss stack and the 36.5 rail band never said where the extra
    # 10.8 sits.  One native rail-top-to-boss-top dimension splits it: 4.5
    # above, and the 6.3 below then follows from the overall height.
    boss_top_edge_section, boss_top_point = _cut_face_edge(
        detail_section_edges, fixed={0: COLUMN_X, 1: HALF_H+BOSS_ABOVE},
        near=(2, REAR_COLUMN_Z, BOSS_DIA), label="section boss top face",
    )
    rail_top_edge_section, rail_top_point = _cut_face_edge(
        detail_section_edges, fixed={0: COLUMN_X, 1: HALF_H},
        near=(2, 0.0, BOSS_DIA), label="section rail top face",
    )
    _checked_dimension(
        adapter, detail_section,
        p0=boss_top_point, p1=rail_top_point,
        text_xy=BOSS_ABOVE_RAIL_LINE_XY, label="boss top above rail top",
        expected_mm=BOSS_ABOVE, orientation="vertical",
        entities=(boss_top_edge_section, rail_top_edge_section),
        suffix="4X BOSS TOP\nABOVE RAIL TOP", offset_text=BOSS_ABOVE_RAIL_TEXT_XY,
    )
    _checked_dimension(
        adapter, detail_section,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z+CAP_RECESS_DIAMETER/2+BORE_CHAMFER),
        p1=(COLUMN_X, HALF_H+BOSS_ABOVE-BORE_CHAMFER, REAR_COLUMN_Z+CAP_RECESS_DIAMETER/2),
        text_xy=(0.335, 0.162), label="top bore mouth chamfer",
        expected_mm=BORE_CHAMFER, orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"), exact_vertices=True,
        suffix="X 45 DEG\nCAP / GOOSENECK TOP", edges=detail_section_edges,
    )
    upper_boss_edge = detail_front_edges.circle_at(
        (COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z), BOSS_DIA/2, axis=(0.0, 1.0, 0.0),
        label="front view outer boss rim on the upper boss plane",
        center_tol_mm=1e-4, radius_tol_mm=1e-4,
    ).edge
    front_tap_edge = detail_front_edges.circle_at(
        (COLUMN_X, 0.0, TOP_SCREW_SEAT_Z), SIDE_TAP_DRILL_DIA/2, axis=(0.0, 0.0, 1.0),
        label="front view column cross-tap circle",
    ).edge
    section_floor_edges = [
        (item.edge, item.midpoint_mm)
        for item in detail_section_edges.lines
        if not (
            max(abs(item.line[0][0]-COLUMN_X), abs(item.line[1][0]-COLUMN_X)) > 1e-6
            or abs(item.line[0][2]-item.line[1][2]) > 1e-6
            or abs(item.line[0][1]-item.line[1][1]) < 1e-6
        )
    ]
    opposed_floors = []
    for plane_z in (-TOP_SCREW_SEAT_Z, TOP_SCREW_SEAT_Z):
        candidates = [item for item in section_floor_edges if abs(item[1][2]-plane_z) < 1e-6]
        if not candidates:
            raise RuntimeError(
                f"section has no native spotface floor edge on Z={plane_z:g}; "
                f"native vertical edge midpoints={[point for _, point in section_floor_edges]}"
            )
        opposed_floors.append(max(candidates, key=lambda item: item[1][1]))
    # The spotface floors are located from the socket bore AXIS the shop
    # indicates, not from the frame midplane (a centre it would first have
    # to derive from the socket pattern -- codex round 5, policy rule 7):
    # the rear floor from the rear bore axis, the front pair being its
    # mirror at the 224.00 pitch sheet 3 states.  The floor-to-floor span
    # stays as a parenthesised reference.
    floor_from_axis = add_edge_dimension(
        adapter, detail_section,
        p0=(0.0, 0.0), p1=(0.0, 0.0),
        text_xy=(0.3535, 0.112), label="spotface floor from socket axis",
        orientation="horizontal",
        entity_types=("SKETCHSEGMENT", "EDGE"),
        entities=(bore_axes[1], opposed_floors[1][0]),
    )
    floor_from_axis = _early_bound(floor_from_axis, "IDisplayDimension")
    measured = abs(float(
        _early_bound(floor_from_axis.GetDimension2(0), "IDimension").SystemValue
    )) * 1000.0
    expected = TOP_SCREW_SEAT_Z - REAR_COLUMN_Z
    if abs(measured - expected) > 1e-5:
        raise RuntimeError(
            f"spotface floor from socket axis: measured {measured:g}, expected {expected:g} mm"
        )
    _set_derived_precision(floor_from_axis, label="spotface floor from socket axis")
    floor_annotation = _early_bound(floor_from_axis.GetAnnotation(), "IAnnotation")
    set_dimension_callouts(
        adapter, [floor_annotation],
        {dimension_name(adapter, floor_annotation): "4X SPOTFACE FLOOR\nFROM SOCKET AXIS"},
    )
    offset_dimension_text(
        adapter, [floor_annotation],
        {dimension_name(adapter, floor_annotation): (0.392, 0.112)},
    )
    _checked_dimension(
        adapter, detail_section,
        p0=opposed_floors[0][1], p1=opposed_floors[1][1],
        text_xy=(0.290, 0.100), label="opposed spotface floor separation",
        expected_mm=2*TOP_SCREW_SEAT_Z, orientation="horizontal",
        suffix="2 PAIRS SPOTFACE FLOORS",
        entities=(opposed_floors[0][0], opposed_floors[1][0]),
        reference=True,
    )
    cross_tap_callout = add_native_hole_callout(
        adapter,
        detail_front,
        edge=front_tap_edge,
        # Left-below the tap, so the leader leaves the block's right end and
        # climbs to the tap clear of every line of the process text; centred
        # under the tap it attached at the far corner and crossed the text,
        # and crowded A-A's cap-recess callout (codex round 5).
        callout_xy=(0.148, 0.202),
        label="front/rear column-retention bottoming taps",
        # The native "2X" is the count in THIS view (one tap per end on the
        # face shown); the process lines carry the four-place scope for the
        # spotface, drill depth and thread depth alike, since the machinist
        # sets up from the total (codex round 3).
        process="4X TOTAL: 2X PER END, BOTH WALLS\nALL DEPTHS FROM SPOTFACE\nBOTTOMING TAP, 4X TOTAL",
    )
    set_hole_callout_precision(
        cross_tap_callout, {"hw-tapdrldepth": 1, "hw-threaddepth": 1},
        label="cross tap depths",
    )
    _checked_dimension(
        adapter, detail_front,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z),
        p1=(COLUMN_X+SIDE_TAP_DRILL_DIA/2, 0.0, TOP_SCREW_SEAT_Z),
        text_xy=(0.2605, 0.229), label="cross screw axis from boss top",
        expected_mm=HALF_H+BOSS_ABOVE, orientation="vertical", center=True,
        # Two taps per column end, opposed across the boss, at both ends of
        # the casting: the count a machinist sets up from is the total.
        suffix="TAP AXIS BELOW BOSS TOP",
        entities=(upper_boss_edge, front_tap_edge), offset_text=(0.300, 0.229),
    )
    cap_seat_finish = add_surface_finish(
        adapter,
        detail_section,
        symbol_xy=CAP_SEAT_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "cap_seat_west_front"),
        label="cap seat floor finish",
        entity_type="FACE",
        entity=machined_faces["cap_seat_west_front"],
        leader_attach_xy=model_point_in_view(
            adapter,
            detail_section,
            (
                COLUMN_X/1000.0,
                CAP_RECESS_FLOOR_Y/1000.0,
                (FRONT_COLUMN_Z+(BORE_DIA+CAP_RECESS_DIAMETER)/4)/1000.0,
            ),
            label="cap seat finish leader",
        ),
        char_height=0.0025,
    )
    _finish_leader_tail(cap_seat_finish, label="cap seat floor")
    _assert_section_display(
        adapter, detail_section, label="A-A corner section",
        cut_surface_only=False,
    )
    cap_fit_note = add_note(
        adapter,
        "CAP RECESSES FOR MHA-133 / 9275K141",
        0.040,
        0.055,
    )
    if add_note(adapter, "A-A: THREAD BOTH CASTING WALLS IN PHASE FOR MHA-132", 0.040, 0.025) is None:
        raise RuntimeError("failed to identify section cross-screw relation")
    if not ddoc.ActivateSheet("HUB-SET-SCREW"):
        raise RuntimeError("failed to activate top-frame hub sheet")
    hub_top = place_view(
        adapter, str(SOURCE), "*Top", *HUB_TOP_CENTER, scale=SHEET_SCALE,
    )
    detail_left = place_view(
        adapter, str(SOURCE), "*Left", *HUB_LEFT_CENTER, scale=HUB_LEFT_SCALE,
    )
    set_hidden_lines_removed(adapter, hub_top)
    # The set pocket is a recess in the face this view looks at and the set tap
    # breaks its floor, so both read as visible ink; the dashed sockets at the
    # rail ends were the only thing hidden lines added here, and sheets 3 and 4
    # own those.  The re-assertions below are not redundant: creating the D-D
    # section and picking its faces both put the parent back in its default.
    set_hidden_lines_removed(adapter, detail_left)
    hub_top_dimensions = curate_view_dimensions(
        adapter, hub_top, keep=HUB_TOP_KEEP,
        view_label="hub location", dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    hub_left_dimensions = curate_view_dimensions(
        adapter, detail_left, keep=HUB_LEFT_KEEP,
        view_label="hub side", dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter, [*hub_top_dimensions, *hub_left_dimensions],
        {name: "" for name in (*HUB_TOP_KEEP, *HUB_LEFT_KEEP)},
    )
    set_dimension_callouts(
        adapter, hub_left_dimensions,
        {"PocketRise": "SQ POCKET\nOUTER LEFT FACE\nCENTRED ON SET TAP"},
    )
    set_dimension_callouts(adapter, hub_top_dimensions, HUB_TOP_CALLOUTS)
    imported_annotations += [*hub_top_dimensions, *hub_left_dimensions]
    offset_dimension_text(
        adapter, hub_left_dimensions, {"PocketRise": POCKET_RISE_TEXT_XY},
    )
    _add_view_centerlines(
        adapter, hub_top,
        (
            ((-COLUMN_X, 0.0, -PLAN_HALF_Z), (-COLUMN_X, 0.0, PLAN_HALF_Z)),
            ((-PLAN_HALF_X, 0.0, FRONT_COLUMN_Z), (PLAN_HALF_X, 0.0, FRONT_COLUMN_Z)),
        ),
    )
    if add_note(adapter, "HUB LOCATION", 0.107, 0.1435) is None:
        raise RuntimeError("failed to label hub location view")
    hub_top_edges = scan_view_edges(hub_top, label="hub location")
    # The socket rim is matched on X/Z only: which of the bore's rims (top or
    # bottom, same X/Z) the plan shows is the view's choice, not the print's.
    left_socket_edge = min(
        (
            item for item in hub_top_edges.circles
            if abs(item.circle[0]+COLUMN_X) < 1e-4
            and abs(item.circle[2]-FRONT_COLUMN_Z) < 1e-4
            and abs(item.circle[6]-BORE_DIA/2) < 1e-4
            and abs(item.circle[3])+abs(abs(item.circle[4])-1.0)+abs(item.circle[5]) < 1e-6
        ),
        key=lambda item: item.circle[1],
        default=None,
    )
    if left_socket_edge is None:
        raise RuntimeError("hub view has no exact left front socket circle")
    left_socket_edge = left_socket_edge.edge
    gooseneck_edge = min(
        hub_top_edges.circles,
        key=lambda item: abs(item.circle[6]-GOOSENECK_BORE_DIA/2)
        + abs(item.circle[0]-GOOSENECK_X) + abs(item.circle[2]-GOOSENECK_Z),
        default=None,
    )
    if gooseneck_edge is None or (
        abs(gooseneck_edge.circle[6]-GOOSENECK_BORE_DIA/2) > 0.01
        or abs(gooseneck_edge.circle[0]-GOOSENECK_X)
        + abs(gooseneck_edge.circle[2]-GOOSENECK_Z) > 0.02
    ):
        raise RuntimeError(
            "top view has no gooseneck clearance-bore circle at "
            f"({GOOSENECK_X:g}, {GOOSENECK_Z:g}) mm with "
            f"{GOOSENECK_BORE_DIA / 2.0:g} mm radius"
        )
    gooseneck_edge = gooseneck_edge.edge
    _checked_dimension(
        adapter, hub_top,
        p0=(-COLUMN_X, HALF_H+BOSS_ABOVE, FRONT_COLUMN_Z),
        p1=(GOOSENECK_X, HALF_H, GOOSENECK_Z),
        text_xy=(0.040, 0.225), label="hub from left front socket",
        expected_mm=GOOSENECK_Z-FRONT_COLUMN_Z, orientation="vertical",
        center=True, entities=(left_socket_edge, gooseneck_edge),
    )
    hub_bore_finish = add_surface_finish(
        adapter,
        hub_top,
        symbol_xy=HUB_BORE_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "hub_bore"),
        label="gooseneck hub bore finish",
        entity_type="FACE",
        entity=machined_faces["hub_bore"],
        leader_attach_xy=model_point_in_view(
            adapter,
            hub_top,
            (GOOSENECK_X/1000.0, 0.0, (GOOSENECK_Z+GOOSENECK_BORE_DIA/2)/1000.0),
            label="hub bore finish leader",
        ),
        char_height=0.0025,
    )
    _finish_leader_tail(hub_bore_finish, label="gooseneck hub bore")
    set_hidden_lines_removed(adapter, detail_left)
    detail_left_edges = scan_view_edges(detail_left, label="hub side")
    tap_x = -(OUTER_X - SET_POCKET_DEPTH)
    tap_radius = TAP_DRILL_MM[SET_TAP_SPEC.size] / 2.0
    rail_top_edge = None
    for item in detail_left_edges.lines:
        start, end = item.line
        if (
            max(
                abs(start[0]+OUTER_X-EDGE_CHAMFER),
                abs(end[0]+OUTER_X-EDGE_CHAMFER),
                abs(start[1]-HALF_H),
                abs(end[1]-HALF_H),
            ) < 1e-4
            and min(start[2], end[2]) < GOOSENECK_Z < max(start[2], end[2])
        ):
            rail_top_edge = item.edge
    set_tap_edge = detail_left_edges.circle_at(
        (tap_x, 0.0, GOOSENECK_Z), tap_radius, axis=(1.0, 0.0, 0.0),
        label="left view set-tap circle",
    ).edge
    if rail_top_edge is None:
        raise RuntimeError("left view has no exact upper rail edge at the gooseneck station")
    add_native_hole_callout(
        adapter,
        detail_left,
        edge=set_tap_edge,
        callout_xy=(
            HUB_LEFT_CENTER[0] - 0.075,
            HUB_LEFT_CENTER[1] + 0.030,
        ),
        label="gooseneck set-screw through-to-bore tap",
        process="TAP",
    )
    _checked_dimension(
        adapter, detail_left,
        p0=(-OUTER_X, HALF_H, GOOSENECK_Z),
        p1=(tap_x, 0.0, GOOSENECK_Z+tap_radius),
        text_xy=(0.230, 0.1125), label="set screw axis from rail top",
        expected_mm=HALF_H, orientation="vertical", center=True,
        suffix="FROM RAIL TOP\nON BORE CENTRE",
        entities=(rail_top_edge, set_tap_edge), offset_text=(0.252, 0.1125),
    )
    # Both picks are entities, not sheet hit-tests: under hidden-lines-removed
    # the boss's bottom rim and the rail underside beyond the feather are the
    # only ink at those stations, and a coordinate pick that lands on nothing
    # fails without saying which edge it wanted.
    rail_underside_point = (-WEB_OUT_X, -HALF_H, GOOSENECK_Z+HUB_GUSSET_HALF_OUT+HUB_BOSS_DROP)
    boss_bottom_center = (GOOSENECK_X, -HALF_H-HUB_BOSS_DROP, GOOSENECK_Z)
    _checked_dimension(
        adapter, detail_left,
        p0=rail_underside_point, p1=boss_bottom_center,
        text_xy=HUB_BOSS_DROP_TEXT_XY, label="hub boss underside drop",
        expected_mm=HUB_BOSS_DROP, orientation="vertical",
        suffix="BOSS\nBELOW RAIL\nUNDERSIDE",
        offset_text=HUB_BOSS_DROP_OFFSET_XY,
        entities=(
            detail_left_edges.exact_line_through(
                rail_underside_point, label="hub boss underside drop, rail underside"
            ).edge,
            detail_left_edges.circle_at(
                boss_bottom_center, HUB_BOSS_DIA/2, axis=(0.0, 1.0, 0.0),
                label="hub boss underside drop, boss bottom rim",
            ).edge,
        ),
    )
    # The 8.0 drop and the 20 DEG ramp only close against the span the
    # feathers actually run: 60.0, outer corner to outer corner.  The ramp
    # rises over the outer 22.0 of each side and the inner 16.0 stays a
    # full-depth flat buried inside the 30.0 boss, which is why the drop
    # does not appear within the ramp's own run.
    _checked_dimension(
        adapter, detail_left,
        p0=(GOOSENECK_X-HUB_GUSSET_T/2, -HALF_H, GOOSENECK_Z-HUB_GUSSET_HALF_OUT),
        p1=(GOOSENECK_X-HUB_GUSSET_T/2, -HALF_H, GOOSENECK_Z+HUB_GUSSET_HALF_OUT),
        text_xy=HUB_GUSSET_SPAN_TEXT_XY, label="hub gusset feather span",
        expected_mm=2*HUB_GUSSET_HALF_OUT, orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"), exact_vertices=True,
        suffix="GUSSET SPAN", edges=detail_left_edges,
    )
    _gusset_ramp_angle(adapter, detail_left, detail_left_edges)
    set_hidden_lines_removed(adapter, detail_left)
    left_note = add_note(
        adapter, "HUB SIDE / REMOVED VIEW SCALE 1:2",
        *HUB_LEFT_NOTE_XY,
    )
    if (
        detail_top_note is None
        or cap_fit_note is None
        or left_note is None
    ):
        raise RuntimeError("failed to label top-frame holes/sockets sheet")
    hub_section = _hub_pocket_section(adapter, hub_top)
    _position_view_caption(adapter, hub_section, HUB_SECTION_CAPTION_XY)
    # The one thing left in D-D that is neither a cut face nor a dimension is
    # the set tap's cosmetic thread, drawn dashed because the tap runs into the
    # page. It is annotation, not geometry, so no display mode removes it and
    # nothing in the view measures it -- it says WHERE the tap breaks into the
    # pocket, and the callout that specifies it is one view up on this sheet.
    if not ddoc.ActivateSheet("UNDERSIDE"):
        raise RuntimeError("failed to activate top-frame underside sheet")
    hub_bottom_parent = place_view(
        adapter, str(SOURCE), "*Bottom", *HUB_BOTTOM_CENTER, scale=HUB_BOTTOM_SCALE,
    )
    set_hidden_lines_removed(adapter, hub_bottom_parent)
    geometry_bottom = _hub_underside_detail(adapter, hub_bottom_parent)
    # SolidWorks refuses hidden-lines-removed on this native detail view, so
    # the enlarged underside keeps its parent's hidden lines.
    set_hidden_lines_visible(adapter, geometry_bottom)
    hub_bottom_edges = scan_view_edges(hub_bottom_parent, label="underside locator")
    geometry_bottom_edges = scan_view_edges(geometry_bottom, label="enlarged underside")
    bottom_dimensions = curate_view_dimensions(
        adapter, geometry_bottom,
        keep={"HubDia": HUB_BOSS_DIA_TEXT_XY},
        view_label="enlarged underside geometry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, bottom_dimensions, {"HubDia": "CYLINDRICAL BOSS"})
    imported_annotations += bottom_dimensions
    # The locator is drawn at the title block's own scale, so it names
    # itself and says nothing a reader can already read off the title block.
    if add_note(adapter, "UNDERSIDE LOCATOR", *HUB_BOTTOM_NOTE_XY) is None:
        raise RuntimeError("failed to label underside locator")
    _checked_dimension(
        adapter, hub_bottom_parent,
        p0=(LAND_X0, -HALF_H, -(INNER_Z+WEB_IN_Z)/2),
        p1=(LAND_X1, -HALF_H, -(INNER_Z+WEB_IN_Z)/2),
        text_xy=(0.105, 0.145), label="crossbar junction land",
        expected_mm=LAND_X1-LAND_X0, orientation="horizontal",
        exact_linear=True, edges=hub_bottom_edges,
        suffix="FULL-THICKNESS LAND\n2X CENTRED ON CENTRAL WEB",
        # The 23 mm land is narrower than its own qualifier, so the text
        # between the extension lines had both running through it (codex
        # round 4): pull it out to the right, on a jog, clear of them.
        offset_text=LAND_TEXT_OFFSET_XY,
    )
    gusset_z = GOOSENECK_Z + (HUB_GUSSET_HALF_IN+HUB_GUSSET_HALF_OUT)/2
    gusset_y = -HALF_H-HUB_BOSS_DROP/2
    _checked_dimension(
        adapter, geometry_bottom,
        p0=(GOOSENECK_X-HUB_GUSSET_T/2, gusset_y, gusset_z),
        p1=(GOOSENECK_X+HUB_GUSSET_T/2, gusset_y, gusset_z),
        text_xy=HUB_GUSSET_T_TEXT_XY, label="underside gusset thickness",
        expected_mm=HUB_GUSSET_T, orientation="horizontal", exact_linear=True,
        suffix="2X GUSSET\nCENTRED ON BORE",
        offset_text=HUB_GUSSET_T_OFFSET_XY, edges=geometry_bottom_edges,
    )
    # The 60.0 feather span is dimensioned once, on the hub side view that
    # also carries the drop and the ramp angle; repeating it here would be
    # the same length stated twice on two sheets.
    _position_view_caption(adapter, geometry_bottom, HUB_DETAIL_CAPTION_XY)
    for sheet_index, sheet_name in enumerate(SHEET_NAMES, start=1):
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to label drawing sheet {sheet_name}")
        if add_note(adapter, f"SHEET {sheet_index} OF {len(SHEET_NAMES)}", 0.350, 0.263) is None:
            raise RuntimeError(f"failed to stamp sheet count on {sheet_name}")

    auto_tapped_notes = _auto_tapped_hole_notes(adapter)
    _telemetry.info(f"automatic tapped-hole notes per view: {auto_tapped_notes}")
    assert_imported_precision(
        adapter, imported_annotations, DRAWING_PRECISION_BY_NAME
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Frame Ring Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales=SHEET_SCALES,
        # The associative feature callouts replace SolidWorks' own descriptive
        # thread notes: every note the inventory above found must go, and the
        # count it hands over is this run's own, logged per view with it.
        # The automatic "Tapped Hole" notes are already gone, deleted and
        # proved per view by ``_auto_tapped_hole_notes`` above.
        redundant_note_substrings=(),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
