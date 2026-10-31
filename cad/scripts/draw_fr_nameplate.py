r"""Create the curated machinist drawing for the engraved brass nameplate (#628).

The SLDPRT remains authoritative.  This recipe supplies only the nameplate's
views, dimension layout, section and hole callout; sheet/template and export
behaviour lives in ``_drawing_common``.

One B sheet at 2:1: the decorated face (front) carries the outline's width
and height and each screw hole's station from its two adjacent edges; the
edge view (right) carries the plate thickness; section A-A, cut across the
whole plate and cropped to its left border and sunk field, carries the
field's depth, the engraving floor below the decorated face and, as a
reference, the floor left under the engraving.  Every dimension but that
reference is a model dimension imported with the places the part authored
(the outline's and the depths' from the part's hidden reference sketches,
``fr_nameplate_drawing_spec``).  The outline's corners, the sunk field's
notched edge and the engraving are the vendored DXF contours the build
imports (``fr_nameplate_drawing_spec.MANUFACTURING_NOTES`` names them).
The base's seats are spotted through this plate at assembly, so no datums.

Run with SolidWorks open::

    uv run python cad\scripts\draw_fr_nameplate.py fr-nameplate
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
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
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from fr_nameplate_drawing_spec import (
    DIMENSION_CALLOUTS,
    DIMENSION_PREFIXES,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    ENGRAVING_FLOOR_DEPTH,
    FIELD_DEPTH,
    FLOOR_UNDER_ENGRAVING,
    FLOOR_UNDER_ENGRAVING_CALLOUT,
    HOLE_CALLOUT_PROCESS,
    MINIMUM_NOTES,
    SCREW_HOLE_DIA,
    SECTION_CALLOUTS,
    SECTION_FIELD_X,
    SECTION_GROOVE_X,
    SECTION_REFERENCE,
    SECTION_Y,
)
from _part_properties import part_drawing_unit
from fr_nameplate_spec import PLATE_HEIGHT, PLATE_THICKNESS, PLATE_WIDTH, SCREW_XY

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["fr_nameplate"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 1)
SECTION_SCALE = (8, 1)
SECTION_LABEL = "A"
_M_PER_MM = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0

# Sheet layout (metres).  At 2:1 the face is 200 x 90.7 mm, x 0.050..0.250,
# y 0.125..0.215.  Third angle: the .063 edge view stands right of it, the
# isometric top-right, removed section A-A bottom-right above the title
# block (its crop centred on SECTION_CENTER, its caption hung below-left of
# it, clear of the floor reference's text below the cut), the notes
# bottom-left below the face's dimensions.
FRONT_CENTER = (0.150, 0.170)
RIGHT_CENTER = (0.276, 0.170)
ISO_CENTER = (0.366, 0.222)
ISO_NOTE_XY = (0.330, 0.183)
NOTES_XY = (0.030, 0.085)
# r4 review: the engraving DXF draws a whole slotted screw head round each
# hole, and the drilled hole removes its centre. Stated once, under the DXF
# rows (whose fourth row ends near y 0.064), as a fact of the part, not a
# method: the hole wins where the two meet.
SCREW_HEAD_NOTE = "SCREW HOLES CUT THROUGH THE ENGRAVED SCREW HEADS"
SCREW_HEAD_NOTE_XY = (0.030, 0.061)
# The stated worst-case minimums (fr-nameplate machinist exceptions RV-02 and
# RV-03), two rows a line below the screw-head note, in the empty bottom-left.
MINIMUM_NOTES_XY = (0.030, 0.050)
SECTION_CENTER = (0.350, 0.115)
# The native caption's top centre. r4 printed the floor reference's text
# right-aligned on its dimension line, its "(0.800)" row 0.88 mm into a
# caption whose top stood at 0.100; the caption now hangs 11 mm lower.
SECTION_CAPTION_XY = (0.288, 0.089)


def _front_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a plate-face point in the front view (2:1, bbox-centred)."""
    return (
        FRONT_CENTER[0] + (x_mm - PLATE_WIDTH / 2.0) * _M_PER_MM,
        FRONT_CENTER[1] + (y_mm - PLATE_HEIGHT / 2.0) * _M_PER_MM,
    )


_LEFT, _BOTTOM = _front_xy(0.0, 0.0)
_RIGHT, _TOP = _front_xy(PLATE_WIDTH, PLATE_HEIGHT)

# The hole callout hangs on the top-left hole (SCREW_XY runs bottom-left,
# bottom-right, top-left, top-right) and rises to its text above the plate.
TOP_LEFT = SCREW_XY[2]
HOLE_R = SCREW_HOLE_DIA / 2.0

# Imported model dimensions on the decorated face. The Hole Wizard's S0X/S0Z
# place the bottom-left hole from the part origin, the plate's lower-left
# corner (text clear of the extension lines, the S0Z text below the top
# station's); FaceReference carries the outline's width and height and the
# right column's and the top row's stations from the right and top edges,
# each "2X".  The edge view carries the thickness with its reason over it.
# The .063 plate prints 3.2 mm wide, narrower than its value: centred, both
# extension lines ran up into the digits (ENFORCE review r1/r3, rule
# 14). The text stands left of the left arrow's tail, on the dimension line
# carried out (draw_ch_rocker_strap's thickness), its reason above it still
# clear of the face view's top-right corner.
FRONT_KEEP = {
    "S0X": (_LEFT + 0.025, _BOTTOM - 0.012),
    "S0Z": (_LEFT - 0.010, _BOTTOM + 0.018),
    "PlateWidth": (FRONT_CENTER[0], _BOTTOM - 0.022),
    # r2 audit: at _LEFT - 0.022 its line crossed both "2X" station
    # texts, which print left of their own dimension lines.
    "PlateHeight": (_LEFT - 0.029, FRONT_CENTER[1]),
    "RightHoleStation": (_RIGHT - 0.022, _BOTTOM - 0.012),
    "TopHoleStation": (_LEFT - 0.010, _TOP - 0.024),
}
RIGHT_KEEP = {"PlateThick": (RIGHT_CENTER[0] - 0.016, _TOP + 0.012)}
HOLE_CALLOUT_XY = (_LEFT + 0.045, _TOP + 0.021)
# The native Hole Wizard diameter prints .XXX (.120), like the pilot's.
HOLE_CALLOUT_PRECISION = {"hw-diam": 3}


def _hole_rim_edge(edges: ViewEdges, hole: tuple[float, float]) -> Any:
    """The visible rim circle of ``hole`` in the face view, picked by entity.

    A coordinate pick on the rim took a head-mark slot edge instead (r1 leaf,
    worker 10, 2026-10-14: AddHoleCallout2 refused the EngravingCut line), so
    the callout's edge is the scanned circle of the hole's own radius and
    centre; of its face and back rims, the decorated-face one (highest z).
    """
    rims = [
        item
        for item in edges.circles
        if abs(item.circle[6] - HOLE_R) < 0.01
        and math.dist(item.circle[:2], hole) < 0.02
    ]
    if not rims:
        raise RuntimeError(
            f"no visible r={HOLE_R:g} rim at {hole} in the {edges.label!r} scan; "
            f"{len(edges.circles)} circles: "
            + "; ".join(
                f"({item.circle[0]:.3f}, {item.circle[1]:.3f}, "
                f"{item.circle[2]:.3f}) r={item.circle[6]:.3f}"
                for item in edges.circles
            )
        )
    return max(rims, key=lambda item: item.circle[2]).edge


# Section A-A: a cut across the whole plate at SECTION_Y (plate-local, the
# spec's), in the gap between the CHICAGO row and the scroll ornament, so the
# line meets no engraving but the border pinstripe on each side.  It starts
# and ends SECTION_OVERRUN outside the outline, so both arrows and both
# letters print off the plate (r2 review C3).  The removed section is cropped
# to its left end, SECTION_CROP (plate x, z corners): the raised border (x
# 0..3.15), the pinstripe groove (x 3.16..3.60, the engraving floor) and the
# sunk field.  Each depth is SectionReference's model dimension, on its own
# dimension line from the decorated face (the raised border top), its text
# above the cut; the floor left under the groove chains below the engraving
# depth as a sheet reference, its text below.
SECTION_OVERRUN = 3.0
SECTION_X_START = -SECTION_OVERRUN
SECTION_X_END = PLATE_WIDTH + SECTION_OVERRUN
SECTION_CROP = ((-0.6, 0.6), (8.0, -(PLATE_THICKNESS + 0.6)))
_SECTION_CROP_CENTER = (
    (SECTION_CROP[0][0] + SECTION_CROP[1][0]) / 2.0,
    (SECTION_CROP[0][1] + SECTION_CROP[1][1]) / 2.0,
)
_SECTION_M_PER_MM = SECTION_SCALE[0] / SECTION_SCALE[1] / 1000.0
# r4 review: the fragment's open right end read as no end at all. A long-break
# line (thin, one Z) stands on the crop's right edge across the cut there,
# the field's floor down to the back face, overrunning both by
# _SECTION_BREAK_OVERRUN; the Z sits mid-thickness, one tip each side of the
# edge (plate x, z in mm).
_SECTION_BREAK_X = SECTION_CROP[1][0]
_SECTION_BREAK_OVERRUN = 0.35
_SECTION_BREAK_MID = -(FIELD_DEPTH + PLATE_THICKNESS) / 2.0
SECTION_BREAK = (
    (_SECTION_BREAK_X, -FIELD_DEPTH + _SECTION_BREAK_OVERRUN),
    (_SECTION_BREAK_X, _SECTION_BREAK_MID + 0.3),
    (_SECTION_BREAK_X + 0.25, _SECTION_BREAK_MID + 0.15),
    (_SECTION_BREAK_X - 0.25, _SECTION_BREAK_MID - 0.15),
    (_SECTION_BREAK_X, _SECTION_BREAK_MID - 0.3),
    (_SECTION_BREAK_X, -PLATE_THICKNESS - _SECTION_BREAK_OVERRUN),
)


def _section_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a cut-plane point (plate x, z) in section A-A."""
    return (
        SECTION_CENTER[0] + (x_mm - _SECTION_CROP_CENTER[0]) * _SECTION_M_PER_MM,
        SECTION_CENTER[1] + (z_mm - _SECTION_CROP_CENTER[1]) * _SECTION_M_PER_MM,
    )


# SectionReference's depths, each on its own dimension line from the face.
# The field's callout is two rows, the feature and why it holds three places,
# so with its value the block is three rows tall (the r4 render's two-row
# blocks measured ~9 mm). It stands 0.3 higher than on that render and the
# engraving's block 0.6 higher, keeping a gap between the two blocks and the
# field's leader shelf above its outside arrow at the face.
SECTION_KEEP = {
    "FieldDepth": _section_xy(SECTION_FIELD_X, 1.7),
    "EngravingDepth": _section_xy(SECTION_GROOVE_X, 3.4),
}
# The floor under the groove: a sheet reference from the groove's floor to
# the back face (plate x, z), chained below the engraving depth.
FLOOR_REFERENCE_LABEL = "floor under engraving"
FLOOR_REFERENCE: dict[str, Any] = {
    "from": (SECTION_GROOVE_X, -ENGRAVING_FLOOR_DEPTH),
    "to": (SECTION_GROOVE_X, -PLATE_THICKNESS),
    "expected_mm": FLOOR_UNDER_ENGRAVING,
    "text_xy": _section_xy(SECTION_GROOVE_X, -2.9),
    "callout": FLOOR_UNDER_ENGRAVING_CALLOUT,
}


def _mm_to_m(point: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(value / 1000.0 for value in point)


def _set_prefix(display: Any, prefix: str, *, label: str) -> None:
    """Write a native dimension prefix and read it back."""
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(1, prefix)  # swDimensionTextPrefix
    if str(display.GetText(1) or "") != prefix:
        raise RuntimeError(f"{label}: dimension prefix {prefix!r} did not persist")


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        prefix = remaining.pop(name, None)
        if prefix is None:
            continue
        _set_prefix(annotation.GetSpecificAnnotation(), prefix, label=name)
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


def _set_reference_precision(display: Any, label: str) -> None:
    """Give the one sheet-derived reference its spec-authored decimal places.

    Every other dimension on this print is a model dimension whose places the
    part authored and ``assert_imported_precision`` reads back.  The floor
    under the engraving is a parenthesised reference with no band and no
    model dimension to import, so its places come from the spec's
    ``DRAWING_REFERENCE_PRECISION`` -- never a literal typed here.
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: do-not-change for the dual and both tolerance places.
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(f"{label}: prints {applied} decimal places, not {places}")


def _orient_section(adapter: Any, view: Any) -> None:
    """Cut faces only, plate X to the right and the decorated face (+Z) up."""
    view = _early_bound(view, "IView")
    section = _early_bound(view.GetSection(), "IDrSection")
    section.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="section A-A cut surface")
    if not section.GetDisplayOnlySurfaceCut() or not section.GetPartialSection():
        raise RuntimeError("section A-A must be a removed, cut-surface-only section")

    def axes() -> tuple[tuple[float, float], tuple[float, float]]:
        origin, east, up = model_points_in_view(
            adapter,
            view,
            [(0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.0, 0.001)],
            label="section A-A orientation",
        )
        return (
            (east[0] - origin[0], east[1] - origin[1]),
            (up[0] - origin[0], up[1] - origin[1]),
        )

    horizontal, vertical = axes()
    if horizontal[0] * vertical[1] - horizontal[1] * vertical[0] < 0.0:
        reversed_cut = not bool(section.GetReversedCutDirection())
        section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section A-A cut direction")
        if bool(section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section A-A cut direction did not persist")
        horizontal, vertical = axes()
    view.Angle = float(view.Angle) - math.atan2(horizontal[1], horizontal[0])
    rebuild_drawing(adapter, label="section A-A angle")
    horizontal, vertical = axes()
    if (
        horizontal[0] <= 0.0
        or abs(horizontal[1]) > 1e-8
        or vertical[1] <= 0.0
        or abs(vertical[0]) > 1e-8
    ):
        raise RuntimeError(
            f"section A-A orientation did not persist: {horizontal=}, {vertical=}"
        )


def _crop_section(adapter: Any, view: Any) -> None:
    """Crop A-A to SECTION_CROP: the border, the groove and the field's start.

    The full cut is the plate's whole width (848 mm at 8:1); the fence is a
    rectangle sketched in the section's own sketch round the projected crop
    corners (``draw_fr_rocker_arm_support._crop_view_b_to_rail``'s sequence),
    with no crop outline, so the cut face simply stops on the field.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(view, "IView")
    rebuild_drawing(adapter, label="section A-A before crop")
    sheet_corners = model_points_in_view(
        adapter,
        view,
        [_mm_to_m((x, SECTION_Y, z)) for x, z in SECTION_CROP],
        label="section A-A crop corners",
    )
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate section A-A for its crop")
    draw.ClearSelection2(True)
    before = tuple(float(value) for value in view.GetOutline())
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    corners = []
    for x, y in sheet_corners:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        corners.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    segments = tuple(
        sketch_manager.CreateCornerRectangle(*corners[0], *corners[1]) or ()
    )
    if len(segments) != 4:
        raise RuntimeError(f"section A-A crop fence has {len(segments)} segments")
    for segment in segments:
        if not _early_bound(segment, "ISketchSegment").Select4(True, None):
            raise RuntimeError("failed to select the section A-A crop fence")
    # Crop2(jagged, no outline, intensity) returns swCropViewErrors_e; 1 is
    # NoError.
    status = int(view.Crop2(False, True, 0))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section A-A crop")
    view.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"section A-A Crop2 status {status}: outline {before!r} -> {outline!r}, "
        f"fence corners {sheet_corners!r}"
    )
    # r3: a 68.8 mm fence read back an 88.0 mm outline (from 811 mm), so the
    # outline carries a margin past the fence; the proof is the shrink.
    width = (SECTION_CROP[1][0] - SECTION_CROP[0][0]) * _SECTION_M_PER_MM
    if (
        status != 1
        or not bool(view.IsCropped())
        or outline[2] - outline[0] > width + 0.025
        or outline[2] - outline[0] > 0.25 * (before[2] - before[0])
    ):
        raise RuntimeError(
            f"section A-A did not crop to {width * 1000.0:.1f} mm: status {status}, "
            f"outline {before!r} -> {outline!r}"
        )


def _sketch_section_break(adapter: Any, view: Any) -> None:
    """Draw SECTION_BREAK into A-A's own sketch as thin lines.

    Projected like the crop fence (model point -> sheet -> the view sketch's
    ModelToSketchTransform). AddToDB keeps sketch inference from snapping the
    short Z segments onto the cut face's edges.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(view, "IView")
    sheet_points = model_points_in_view(
        adapter,
        view,
        [_mm_to_m((x, SECTION_Y, z)) for x, z in SECTION_BREAK],
        label="section A-A break line",
    )
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate section A-A for its break line")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_points:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        for index in range(len(points) - 1):
            if sketch_manager.CreateLine(*points[index], *points[index + 1]) is None:
                raise RuntimeError(f"section A-A break line segment {index} failed")
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section A-A break line")


def _place_crop_on_center(adapter: Any, view: Any) -> None:
    """Move A-A so the crop's centre (a cut-plane point) lands on SECTION_CENTER.

    Placed by a projected model point, not the outline, so every text
    position ``_section_xy`` derives holds whatever margin the outline adds.
    """
    view = _early_bound(view, "IView")
    point = _mm_to_m((_SECTION_CROP_CENTER[0], SECTION_Y, _SECTION_CROP_CENTER[1]))
    for _attempt in range(3):
        (center,) = model_points_in_view(
            adapter, view, [point], label="section A-A crop centre"
        )
        if math.dist(center, SECTION_CENTER) < 1e-5:
            return
        position = tuple(float(value) for value in view.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - center[axis] for axis in range(2)
        ]
        if not view.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to position section A-A")
        rebuild_drawing(adapter, label="place section A-A")
    raise RuntimeError(f"section A-A crop centre did not settle on {SECTION_CENTER!r}")


def _section(adapter: Any, front: Any) -> Any:
    """Section A-A across the plate, cropped to the left border and field."""
    line = model_points_in_view(
        adapter,
        front,
        [
            _mm_to_m((SECTION_X_START, SECTION_Y, 0.0)),
            _mm_to_m((SECTION_X_END, SECTION_Y, 0.0)),
        ],
        label="section A-A line",
    )
    view = create_section_view(
        adapter,
        front,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label=SECTION_LABEL,
        scale=SECTION_SCALE,
        partial=True,
        label="nameplate field and engraving depths",
    )
    view = _early_bound(view, "IView")
    view.UseParentScale = False
    view.ScaleRatio = double_array([float(value) for value in SECTION_SCALE])
    _orient_section(adapter, view)
    set_hidden_lines_removed(adapter, view)
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if bool(view.UseParentScale) or ratio != tuple(float(v) for v in SECTION_SCALE):
        raise RuntimeError(f"section A-A must keep its own {SECTION_SCALE} scale")
    _crop_section(adapter, view)
    _place_crop_on_center(adapter, view)
    _sketch_section_break(adapter, view)
    position_section_caption(
        adapter, view, SECTION_CAPTION_XY, label="nameplate section A-A"
    )
    return view


def _cut_face_line(
    edges: ViewEdges, *, x_mm: float, z_mm: float, label: str
) -> tuple[Any, tuple[float, float, float]]:
    """The visible cut-face line at height ``z_mm`` spanning ``x_mm``.

    A cut-surface-only section shows its cut face alone, so every visible line
    lies in the plane y = SECTION_Y; the decorated face, the field floor and
    an engraving floor are its horizontal lines at their own heights.
    """
    for item in edges.lines:
        start, end = item.line
        if max(abs(start[1] - SECTION_Y), abs(end[1] - SECTION_Y)) > 1e-4:
            continue
        if max(abs(start[2] - z_mm), abs(end[2] - z_mm)) > 1e-4:
            continue
        if min(start[0], end[0]) <= x_mm <= max(start[0], end[0]):
            return item.edge, (x_mm, SECTION_Y, z_mm)
    seen = sorted(
        (
            tuple(round(value, 3) for value in item.line[0]),
            tuple(round(value, 3) for value in item.line[1]),
        )
        for item in edges.lines
    )
    raise RuntimeError(f"{label}: no cut-face line at x={x_mm}, z={z_mm}; lines {seen}")


def _floor_reference(adapter: Any, section: Any) -> None:
    """The floor under the groove, chained below the engraving depth."""
    label = FLOOR_REFERENCE_LABEL
    edges = scan_view_edges(section, label="section A-A")
    (from_edge, from_point), (to_edge, to_point) = (
        _cut_face_line(edges, x_mm=x, z_mm=z, label=f"{label} {end}")
        for end, (x, z) in (
            ("from", FLOOR_REFERENCE["from"]),
            ("to", FLOOR_REFERENCE["to"]),
        )
    )
    points = model_points_in_view(
        adapter, section, [_mm_to_m(from_point), _mm_to_m(to_point)], label=label
    )
    display = add_edge_dimension(
        adapter,
        section,
        p0=points[0],
        p1=points[1],
        text_xy=FLOOR_REFERENCE["text_xy"],
        label=label,
        orientation="vertical",
        entities=(from_edge, to_edge),
    )
    # Both ends are scanned cut-face lines; 1e-3 mm absorbs the section's
    # projected-geometry noise in the measured value.
    assert_dimension_measures(
        adapter,
        display,
        expected_mm=FLOOR_REFERENCE["expected_mm"],
        label=label,
        entities=(from_edge, to_edge),
        tolerance_mm=1e-3,
    )
    native = _early_bound(display, "IDisplayDimension")
    _set_reference_precision(native, label)
    annotation = _early_bound(native.GetAnnotation(), "IAnnotation")
    set_reference_dimension(adapter, annotation, label=label)
    set_dimension_callouts(
        adapter,
        [annotation],
        {dimension_name(adapter, annotation): FLOOR_REFERENCE["callout"]},
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open nameplate source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    properties = (
        "Number",
        "Revision",
        "Title",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        source_model,
        properties,
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("fr-nameplate"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Nameplate Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "engraved brass nameplate; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # Places live on the part; the sheet only proves the import kept them.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="above")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    holes = add_native_hole_callout(
        adapter,
        front,
        edge=_hole_rim_edge(scan_view_edges(front, label="front"), TOP_LEFT),
        callout_xy=HOLE_CALLOUT_XY,
        label="nameplate screw holes",
        process=HOLE_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(holes, HOLE_CALLOUT_PRECISION, label="nameplate screw holes")

    # SectionReference lies in A-A's cutting plane, saved hidden: a derived
    # view takes it from the part as it stands when it is cut and selects it
    # through its base view, so the section is cut and curated while the part
    # shows it (the pen v-block's recipe).
    with part_sketches_shown(
        adapter,
        source_model,
        (SECTION_REFERENCE,),
        label="section A-A references",
        base_view=front,
    ):
        section = _section(adapter, front)
        depths = curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    annotations += depths
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, depths, SECTION_CALLOUTS)
    _floor_reference(adapter, section)

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    if add_note(adapter, SCREW_HEAD_NOTE, *SCREW_HEAD_NOTE_XY) is None:
        raise RuntimeError("failed to place the screw-head engraving note")
    # Named exceptions: fr-nameplate RV-02 (floor) and RV-03 (screw thread).
    if add_note(adapter, MINIMUM_NOTES, *MINIMUM_NOTES_XY) is None:
        raise RuntimeError("failed to place the stated-minimum notes")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    _telemetry.info("nameplate drawing views, dimensions and notes placed")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Nameplate Manufacturing Drawing",
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
