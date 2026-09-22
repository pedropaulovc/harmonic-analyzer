"""Create the manufacturing drawing for the turned McMaster 91247A720 stud.

The vendor bolt is purchased by SKU, cut to length and turned at its threaded
end to a shouldered #10-24 tip, the knife-hanger joint
(``knife_hanger_interface``). The shoulder-to-end tip length and the tip
chamfer are native model controls; the overall length is a fit-to-stack
reference; undimensioned purchased head/thread geometry is reference.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import _stock_trim_drawing as trim_drawing
import _telemetry
from _common import _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    check_drawing_layout,
    collect_layout_elements,
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _stock_trim_drawing import TrimSheet
from build_knife_hanger_stud import (
    HEAD_AF,
    HEAD_H,
    SHANK_DIA,
    SHOULDER_Y_MM,
    TIP_END_Y_MM,
    TIP_RADIUS_MM,
    UNDERHEAD_Y_MM,
)
from diagnostics.diag_build_91247A720 import GB_WASHER_T
from knife_hanger_stud_spec import (
    DIMENSION_PRECISION,
    DRAWING_DIMENSIONS,
    DRAWING_REFERENCE_PRECISION,
    FINISHED_UNDERHEAD_MM,
    TIP_CHAMFER_CALLOUT_SUFFIX,
    TIP_CHAMFER_MM,
    TIP_CHAMFER_TOLERANCE_TYPE,
    TIP_LENGTH_DEVIATIONS_MM,
    TIP_LENGTH_MM,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["knife_hanger_stud"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (2.0, 1.0)
# 1.5:1, not 2:1: ``GetOutline`` of the pictorial measures 72.4 x 135.2 mm at
# 2:1 (the rendered ink is only 52 x 99.5 mm -- the outline is NOT the ink).
# At 1.5:1 the outline is 54.3 x 101.4 mm and fits its cell with margin
# (measured on leaf 20260922T152754Z, which failed loudly at 2:1).
ISO_SCALE = (1.5, 1.0)

# Policy rule 7: a turned part is drawn as it sits in the lathe -- axis
# horizontal, the head (chuck end) left, the turned tip right. The part's
# axis is model +Y, so ``*Front`` is turned until model -Y reads sheet +X.
# Its keep-in cell: left of the pictorial, above the tip detail and the notes.
FRONT_REGION = (0.020, 0.150, 0.280, 0.262)
FRONT_FIT_MARGIN_M = 0.003
# The projected unit axis may lean this much off horizontal (float residue).
AXIS_TOLERANCE_M = 1e-6

# The engagement-critical tip length is ONE direct dimension, shoulder face to
# faced end, carrying the interface's band (Main, 2026-09-22). Its text sits
# this far out from the shank's crest, over the tip; its legs are the turn
# profile's shoulder-crest and faced-end corners, both drawn.
TIP_LENGTH_TEXT_OUT_M = 0.012
# The overall bearing-face-to-end length is a fit-to-stack REFERENCE, a
# DRAWING dimension between the drawn bearing face and the drawn faced end.
# The model's FinishedOverall runs from the stock datum point on the AXIS to a
# corner of the trim CUTTER sketch (diagnostics/diag_mcmaster_lib.py): stud-12
# drew its witness lines into and across the part (leaf 20260922T212033Z).
# Its text sits this far out beyond the hex head's corners, on the far side.
FINISHED_TEXT_OUT_M = 0.010
HEAD_CORNER_MM = HEAD_AF / math.sqrt(3.0)
MODEL_FINISHED = "FinishedOverall@StockTrimProfile"
FINISHED_VALUE_TOLERANCE_M = 1e-9
SW_TOL_NONE = 0  # swTolType_e.swTolNONE: the build clears the native band
SW_TOL_BILATERAL = 2  # swTolType_e.swTolBILAT
# The two drawn edges are the model's circular edges, seen edge-on, found by
# radius and axial station: the washer face's bearing circle and the faced
# end's circle inside the tip chamfer. Coordinate picks are ambiguous at the
# bearing face: the hex underside's edge lies 0.2 mm above it all the way
# across, and stud-13 (leaf 20260922T213616Z) picked it and read (45.3).
BEARING_CIRCLE = (HEAD_AF / 2.0, UNDERHEAD_Y_MM)
FACED_END_CIRCLE = (TIP_RADIUS_MM - TIP_CHAMFER_MM, TIP_END_Y_MM)
CIRCLE_MATCH_MM = 0.01

# The tip chamfer is shown in a detail at 6:1 (Main, 2026-09-22): at 2:1 it
# is 1 mm of paper. The fence is centred on the axis 1 mm inside the faced
# end and reaches past the tip's crest far enough to hold the chamfer's
# dimension line. The detail's ``GetOutline`` is padded well past its fence:
# stud-14 (leaf 20260922T214220Z) measured an outline half of 51.56 mm for a
# 2.5 mm fence at 12:1, 1.72 x the nominal fence on the sheet (stud-4/6/12
# measured 1.39 x). The cell is sized for 1.72 x, between the notes block
# (right edge x 186.8 mm), the title block (top 66 mm), the lathe view's cell
# and the pictorial's note (y 147 mm).
TIP_DETAIL_SCALE = (6.0, 1.0)
DETAIL_OUTLINE_PER_FENCE = 1.72
SHEET = TrimSheet(
    sheet_scale=SHEET_SCALE,
    detail_center=(0.235, 0.109),
    detail_scale=TIP_DETAIL_SCALE,
    fence_radius_mm=TIP_RADIUS_MM + 1.2,
    cut_end_y_mm=TIP_END_Y_MM,
    detail_offset_mm=1.0,
    # Centred right of the padded outline; the anchor is the label's top.
    detail_label_xy=(0.295, 0.105),
    # Right of the fence, just below the axis: clear of the tip length above
    # the part and of the overall reference's witness line at the faced end.
    parent_letter_offset=(0.014, -0.004),
    detail_center_x_mm=0.0,
)
# The chamfer's dimension line runs this far out from the tip's crest.
CHAMFER_TEXT_OUT_M = 0.004
SUFFIX = 2  # swDimensionTextSuffix

# The free upper-right cell the pictorial lives in, on this 0.4318 x 0.2794 m
# sheet. Sized for the MEASURED outline at 1.5:1 (54.3 x 101.4 mm) so the fit
# keeps >= 3 mm to every side.
ISO_REGION = (0.290, 0.152, 0.415, 0.2625)
ISO_FIT_MARGIN_M = 0.003
# The linked "ISO SCALE 1.5:1" renders ~30 mm wide at its default text height
# and a note's SetPosition2 anchor is the text box's UPPER-LEFT (measured on
# this sheet), so it is centred under the fitted outline and kept just clear.
ISO_NOTE_WIDTH_M = 0.030
ISO_NOTE_BELOW_M = 0.004

# Every dimension arc on the sheet: stud-4 exported one of r 84 mm.
DIMENSION_ARC_RADIUS_MAX_M = 0.030
DIMENSION_ARC_SWEEP_MAX_DEG = 60.0
ARC_SAMPLES = 32
# Ink segments allowed to cross the tip detail's boundary circle, per
# dimension: none -- the chamfer's dimension line runs inside the fence.
DETAIL_BOUNDARY_CROSSINGS: dict[str, int] = {}
# Proper crossings between a dimension's own lines (e.g. its leader through
# its witness line) are measured apart from shared endpoints by this much.
SELF_CROSSING_END_M = 0.0005
# An extension line leaves the drawn edge nearest its dimension line with a
# gap: its far end may reach into the part's silhouette by at most this much.
# A row of the silhouette carries a line whose station is within the second.
EXTENSION_ENTRY_MAX_M = 0.0005
EXTENSION_ROW_TOLERANCE_M = 0.0003
LINE_AXIS_TOLERANCE_M = 1e-5

LAYOUT_REPORT = (
    Path(OUTPUTS.slddrw).parent.parent
    / "reports"
    / "layout-audit"
    / f"{SPEC.name}.json"
)
# The model's driving FinishedOverall, nominal SI length (no native band).
MODEL_FINISHED_CONTROL = FINISHED_UNDERHEAD_MM / 1000.0
# The imported machining controls, (nominal, lower, upper) signed SI values.
TIP_CONTROLS = {
    "TipLength": (
        TIP_LENGTH_MM / 1000.0,
        TIP_LENGTH_DEVIATIONS_MM[0] / 1000.0,
        TIP_LENGTH_DEVIATIONS_MM[1] / 1000.0,
    ),
    "TipChamfer": (TIP_CHAMFER_MM / 1000.0, 0.0, 0.0),
}
TIP_TOLERANCE_TYPES = {
    "TipLength": SW_TOL_BILATERAL,
    "TipChamfer": TIP_CHAMFER_TOLERANCE_TYPE,
}
# The chamfer's radial leg: equal to its axial leg, the 45 deg on the sheet.
MODEL_CHAMFER_RADIAL = "TipChamferRadial@StudTurnProfile"


def _fit_translation(
    box: tuple[float, float, float, float],
    region: tuple[float, float, float, float],
    margin: float,
) -> tuple[float, float]:
    """Shift that centres ``box`` inside ``region``, ``margin`` clear on all sides."""
    slack_x = (region[2] - region[0]) - (box[2] - box[0]) - 2.0 * margin
    slack_y = (region[3] - region[1]) - (box[3] - box[1]) - 2.0 * margin
    if slack_x < 0.0 or slack_y < 0.0:
        raise RuntimeError(
            f"view outline {_format_box(box)} cannot fit the keep-in region "
            f"{_format_box(region)} with {margin * 1000.0:.1f} mm clearance "
            f"(short {max(-slack_x, 0.0) * 1000.0:.1f} x "
            f"{max(-slack_y, 0.0) * 1000.0:.1f} mm) -- reduce the view scale"
        )
    return (
        ((region[0] + region[2]) - (box[0] + box[2])) / 2.0,
        ((region[1] + region[3]) - (box[1] + box[3])) / 2.0,
    )


def _format_box(box: tuple[float, float, float, float]) -> str:
    return (
        f"[{box[0] * 1000.0:.1f},{box[1] * 1000.0:.1f}].."
        f"[{box[2] * 1000.0:.1f},{box[3] * 1000.0:.1f}]mm"
    )


def _view_box(view: Any, *, label: str) -> tuple[float, float, float, float]:
    """``IView::GetOutline`` as an ``(xmin, ymin, xmax, ymax)`` sheet box."""
    outline = tuple(float(value) for value in (view.GetOutline() or ()))
    if len(outline) != 4:
        raise RuntimeError(f"{label} view has no outline: {outline!r}")
    return outline


def _note_box(note: Any, *, label: str) -> tuple[float, float, float, float]:
    """``INote::GetExtent`` as an ``(xmin, ymin, xmax, ymax)`` sheet box."""
    extent = tuple(float(value) for value in (_read_member(note, "GetExtent") or ()))
    if len(extent) != 6:
        raise RuntimeError(f"{label} note has no extent: {extent!r}")
    return (
        min(extent[0], extent[3]),
        min(extent[1], extent[4]),
        max(extent[0], extent[3]),
        max(extent[1], extent[4]),
    )


Point = tuple[float, float]

Box = tuple[float, float, float, float]


def _mm(point: Point) -> list[float]:
    return [round(value * 1000.0, 2) for value in point]


@dataclass(frozen=True)
class DimensionArc:
    """One ``IDisplayData::GetArcAtIndex2`` arc, in sheet metres."""

    center: Point
    start: Point
    end: Point
    ccw: bool

    @classmethod
    def from_display(cls, raw: Any) -> DimensionArc:
        # [color, lineType, unused, unused, startPt[3], endPt[3], centerPt[3],
        #  arcNormal[3], rotationDir (CCW = True)] -- types/IDisplayData/GetArcAtIndex2.md
        values = [float(value) for value in (raw or ())]
        if len(values) < 17:
            raise RuntimeError(f"incomplete dimension arc: {values!r}")
        return cls(
            center=(values[10], values[11]),
            start=(values[4], values[5]),
            end=(values[7], values[8]),
            ccw=values[16] != 0.0,
        )

    @property
    def radius(self) -> float:
        return math.dist(self.center, self.start)

    def _bearing(self, point: Point) -> float:
        return math.atan2(point[1] - self.center[1], point[0] - self.center[0])

    @property
    def sweep(self) -> float:
        """Radians drawn from start to end in the arc's own rotation direction."""
        turn = self._bearing(self.end) - self._bearing(self.start)
        # Coincident ends are a full circle, not an empty arc.
        return (turn if self.ccw else -turn) % math.tau or math.tau

    def samples(self) -> list[Point]:
        start = self._bearing(self.start)
        step = (self.sweep if self.ccw else -self.sweep) / ARC_SAMPLES
        return [
            (
                self.center[0] + self.radius * math.cos(start + index * step),
                self.center[1] + self.radius * math.sin(start + index * step),
            )
            for index in range(ARC_SAMPLES + 1)
        ]

    def as_mm(self) -> dict[str, Any]:
        return {
            "center_mm": _mm(self.center),
            "radius_mm": round(self.radius * 1000.0, 2),
            "start_mm": _mm(self.start),
            "end_mm": _mm(self.end),
            "sweep_deg": round(math.degrees(self.sweep), 2),
            "ccw": self.ccw,
        }


@dataclass(frozen=True)
class DimensionInk:
    """A display dimension's RENDERED geometry, which the layout census omits.

    ``collect_layout_elements`` boxes a dimension by its text only (and
    ``GetExtent`` under-reports a displaced block), so an arc, witness line or
    leader can sweep the sheet under a clean census -- stud-4 exported an 84 mm
    arc that way. This is read from ``IDisplayData`` directly.
    """

    name: str
    lines: tuple[tuple[Point, Point], ...]
    arcs: tuple[DimensionArc, ...]
    triangles: tuple[tuple[Point, Point, Point], ...]
    arrowheads: int

    def segments(self) -> list[tuple[Point, Point]]:
        segments = list(self.lines)
        for arc in self.arcs:
            points = arc.samples()
            segments.extend(zip(points, points[1:]))
        for a, b, c in self.triangles:
            segments.extend(((a, b), (b, c), (c, a)))
        return segments

    def bounds(self) -> Box | None:
        points = [point for segment in self.segments() for point in segment]
        if not points:
            return None
        return (
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        )

    def as_mm(self) -> dict[str, Any]:
        bounds = self.bounds()
        return {
            "name": self.name,
            "bounds_mm": None
            if bounds is None
            else [round(v * 1000.0, 2) for v in bounds],
            "lines_mm": [[_mm(a), _mm(b)] for a, b in self.lines],
            "arcs": [arc.as_mm() for arc in self.arcs],
            "triangles": len(self.triangles),
            "arrowheads": self.arrowheads,
        }


def _read_dimension_ink(annotation: Any, name: str) -> DimensionInk:
    """Lines, arcs and arrow triangles of one display dimension, on a fresh handle."""
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    lines = []
    for index in range(int(data.GetLineCount())):
        # [color, lineType, unused, unused, startPt[3], endPt[3]]
        line = [float(value) for value in (data.GetLineAtIndex2(index) or ())]
        if len(line) < 10:
            raise RuntimeError(f"{name}: incomplete dimension line {line!r}")
        lines.append(((line[4], line[5]), (line[7], line[8])))
    arcs = tuple(
        DimensionArc.from_display(data.GetArcAtIndex2(index))
        for index in range(int(data.GetArcCount()))
    )
    triangles = []
    for index in range(int(data.GetTriangleCount())):
        # [vertexPt1[3], vertexPt2[3], vertexPt3[3], isFilled, lineType]
        corner = [float(value) for value in (data.GetTriangleAtIndex(index) or ())]
        if len(corner) < 9:
            raise RuntimeError(f"{name}: incomplete dimension triangle {corner!r}")
        triangles.append(
            ((corner[0], corner[1]), (corner[3], corner[4]), (corner[6], corner[7]))
        )
    return DimensionInk(
        name=name,
        lines=tuple(lines),
        arcs=arcs,
        triangles=tuple(triangles),
        arrowheads=int(data.GetArrowHeadCount()),
    )


def _inside(point: Point, box: Box) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _segment_hits_box(p0: Point, p1: Point, box: Box) -> bool:
    """True when the segment p0-p1 touches ``box`` (Liang-Barsky clip)."""
    low, high = 0.0, 1.0
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    for p, q in (
        (-dx, p0[0] - box[0]),
        (dx, box[2] - p0[0]),
        (-dy, p0[1] - box[1]),
        (dy, box[3] - p0[1]),
    ):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        t = q / p
        if p < 0.0:
            low = max(low, t)
        else:
            high = min(high, t)
        if low > high:
            return False
    return True


def _dimension_ink_problems(
    ink: DimensionInk,
    *,
    owner: Box,
    obstacles: dict[str, Box],
    region: Box,
    boundary: tuple[Point, float] | None = None,
    silhouette: tuple[Box, ...] = (),
) -> list[str]:
    """Every way ``ink`` escapes its own view or crosses something it must not.

    ``boundary`` is a detail view's circle (centre, radius): ink may cross it
    only as often as ``DETAIL_BOUNDARY_CROSSINGS`` allows for ``ink.name``.
    ``silhouette`` is the part as drawn, row by row: extension lines must stop
    at its edge (``_extension_line_problems``).
    """
    problems = []
    for arc in ink.arcs:
        if arc.radius > DIMENSION_ARC_RADIUS_MAX_M:
            problems.append(
                f"{ink.name} arc radius {arc.radius * 1000.0:.1f} mm exceeds "
                f"{DIMENSION_ARC_RADIUS_MAX_M * 1000.0:.1f} mm"
            )
        if math.degrees(arc.sweep) > DIMENSION_ARC_SWEEP_MAX_DEG:
            problems.append(
                f"{ink.name} arc sweeps {math.degrees(arc.sweep):.1f} deg "
                f"(> {DIMENSION_ARC_SWEEP_MAX_DEG:.0f}): it runs the long way round"
            )
        if not _inside(arc.center, owner):
            problems.append(
                f"{ink.name} arc centre {_mm(arc.center)} mm is outside its view "
                f"{_format_box(owner)}"
            )
    bounds = ink.bounds()
    if bounds is not None and not (
        _inside(bounds[:2], region) and _inside(bounds[2:], region)
    ):
        problems.append(
            f"{ink.name} ink {_format_box(bounds)} leaves the drawable region "
            f"{_format_box(region)}"
        )
    segments = ink.segments()
    for label, box in obstacles.items():
        if any(_segment_hits_box(a, b, box) for a, b in segments):
            problems.append(f"{ink.name} ink crosses {label} {_format_box(box)}")
    for index, (a, b) in enumerate(ink.lines):
        for c, d in ink.lines[index + 1 :]:
            point = _segment_intersection(a, b, c, d)
            if (
                point is not None
                and min(math.dist(point, end) for end in (a, b, c, d))
                > SELF_CROSSING_END_M
            ):
                problems.append(
                    f"{ink.name} lines {[_mm(a), _mm(b)]} and {[_mm(c), _mm(d)]} "
                    f"cross at {_mm(point)} mm"
                )
    if boundary is not None:
        crossings = sum(_segment_crosses_circle(a, b, *boundary) for a, b in segments)
        allowed = DETAIL_BOUNDARY_CROSSINGS.get(ink.name, 0)
        if crossings > allowed:
            problems.append(
                f"{ink.name} ink crosses the detail boundary circle "
                f"{_mm(boundary[0])} r {boundary[1] * 1000.0:.1f} mm "
                f"{crossings} time(s); {allowed} allowed"
            )
    problems.extend(_extension_line_problems(ink, silhouette))
    return problems


def _linear_dimension_lines(
    ink: DimensionInk,
) -> tuple[int, float, list[tuple[Point, Point]]] | None:
    """Split a linear dimension's lines: (axis, dimension-line coordinate, extensions).

    ``axis`` is the sheet coordinate (0 = x, 1 = y) the extension lines run
    along. The dimension line is the group of axis-parallel lines that are all
    collinear; the extension lines are the other group, parallel and offset by
    the measured distance. None when the ink is not a linear dimension.
    """
    groups: dict[int, list[tuple[Point, Point]]] = {0: [], 1: []}
    for a, b in ink.lines:
        for along in (0, 1):
            if abs(a[1 - along] - b[1 - along]) <= LINE_AXIS_TOLERANCE_M:
                groups[along].append((a, b))
                break

    def collinear(lines: list[tuple[Point, Point]], along: int) -> bool:
        return bool(lines) and all(
            abs(a[1 - along] - lines[0][0][1 - along]) <= LINE_AXIS_TOLERANCE_M
            for a, _b in lines
        )

    for along in (0, 1):
        dimension, extensions = groups[1 - along], groups[along]
        if (
            collinear(dimension, 1 - along)
            and extensions
            and not collinear(extensions, along)
        ):
            return along, dimension[0][0][along], extensions
    return None


def _extension_line_problems(
    ink: DimensionInk, silhouette: tuple[Box, ...]
) -> list[str]:
    """Extension lines of a linear dimension that enter the part.

    Every extension line's far end (away from the dimension line) must stop at
    the silhouette row it points into, not run into or across the part.
    """
    split = _linear_dimension_lines(ink) if silhouette else None
    if split is None:
        return []
    along, dimension_c, extensions = split
    across = 1 - along
    problems = []
    for a, b in extensions:
        near, far = sorted((a, b), key=lambda point: abs(point[along] - dimension_c))
        toward = 1.0 if far[along] >= near[along] else -1.0
        worst = None
        for box in silhouette:
            if not (
                box[across] - EXTENSION_ROW_TOLERANCE_M
                <= far[across]
                <= box[across + 2] + EXTENSION_ROW_TOLERANCE_M
            ):
                continue
            low, high = box[along], box[along + 2]
            near_side, far_side = (low, high) if toward > 0 else (high, low)
            entry = (far[along] - near_side) * toward
            if entry > EXTENSION_ENTRY_MAX_M and (worst is None or entry > worst[0]):
                worst = (entry, (far[along] - far_side) * toward, box)
        if worst is None:
            continue
        entry, past, box = worst
        where = (
            f"through the part and {past * 1000.0:.1f} mm past it"
            if past > 0.0
            else f"{entry * 1000.0:.1f} mm into the part"
        )
        problems.append(
            f"{ink.name} extension line {[_mm(near), _mm(far)]} runs {where} "
            f"(silhouette row {_format_box(box)})"
        )
    return problems


def _segment_intersection(a: Point, b: Point, c: Point, d: Point) -> Point | None:
    """Where segments a-b and c-d meet, or None (parallel or apart)."""
    r = (b[0] - a[0], b[1] - a[1])
    q = (d[0] - c[0], d[1] - c[1])
    denominator = r[0] * q[1] - r[1] * q[0]
    if denominator == 0.0:
        return None
    t = ((c[0] - a[0]) * q[1] - (c[1] - a[1]) * q[0]) / denominator
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / denominator
    if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
        return None
    return (a[0] + t * r[0], a[1] + t * r[1])


def _segment_crosses_circle(p0: Point, p1: Point, center: Point, radius: float) -> bool:
    """True when the segment p0-p1 passes through the circle's outline."""
    d0, d1 = math.dist(p0, center), math.dist(p1, center)
    if min(d0, d1) < radius < max(d0, d1):
        return True
    if d0 <= radius or d1 <= radius:
        return False
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length2 = dx * dx + dy * dy
    if length2 == 0.0:
        return False
    t = ((center[0] - p0[0]) * dx + (center[1] - p0[1]) * dy) / length2
    t = min(max(t, 0.0), 1.0)
    return math.dist((p0[0] + t * dx, p0[1] + t * dy), center) < radius


def _detail_boundary(front: Any, detail_box: Box) -> tuple[Point, float]:
    """The cut-end detail's boundary circle on the sheet: (centre, radius).

    The radius is the parent circle's (``IView::GetDetailCircleInfo2`` on the
    front view: [count, layer, centerPt[3], startPt[3], ...]) times the
    detail-to-parent scale; ``end_detail`` centres the detail's outline on its
    circle, so the centre is the outline's.
    """
    info = [
        float(value)
        for value in (_early_bound(front, "IView").GetDetailCircleInfo2() or ())
    ]
    if len(info) < 8 or int(info[0]) != 1:
        raise RuntimeError(f"expected one parent detail circle: {info!r}")
    parent_radius = math.dist((info[2], info[3]), (info[5], info[6]))
    ratio = (SHEET.detail_scale[0] / SHEET.detail_scale[1]) / (
        SHEET_SCALE[0] / SHEET_SCALE[1]
    )
    center = (
        (detail_box[0] + detail_box[2]) / 2.0,
        (detail_box[1] + detail_box[3]) / 2.0,
    )
    radius = parent_radius * ratio
    half = min(detail_box[2] - detail_box[0], detail_box[3] - detail_box[1]) / 2.0
    _telemetry.info(
        "detail boundary: "
        + json.dumps(
            {
                "parent_center_mm": _mm((info[2], info[3])),
                "parent_radius_mm": round(parent_radius * 1000.0, 2),
                "center_mm": _mm(center),
                "radius_mm": round(radius * 1000.0, 2),
                "outline_half_mm": round(half * 1000.0, 2),
            },
            sort_keys=True,
        )
    )
    if not 0.0 < radius < half:
        raise RuntimeError(
            f"detail boundary radius {radius * 1000.0:.1f} mm does not fit its "
            f"outline {_format_box(detail_box)}"
        )
    return center, radius


def _audit_sheet_layout(
    adapter: Any,
    dimensions: dict[
        str,
        tuple[Any, Box, dict[str, Box], tuple[Point, float] | None, tuple[Box, ...]],
    ],
) -> None:
    """Census the sheet in millimetres, publish it, then gate the layout.

    The census is emitted BEFORE the gates so a failing leaf still publishes
    the numbers its fix is placed from. Every dimension's rendered ink (arcs,
    witness lines, leaders, arrows) is gated first -- ``check_drawing_layout``
    cannot see it -- then ``check_drawing_layout`` holds the sheet to zero
    overlaps, zero border crossings and zero leader crossings.
    ``dimensions`` maps each dimension name to its annotation, its owning
    view's outline, the boxes its ink must not cross and, for a detail
    view's dimension, the detail boundary circle, and the part silhouette
    its extension lines must stop at.
    """
    elements, leaders, region = collect_layout_elements(adapter, layout=SPEC.layout)
    template = DRAWING_TEMPLATES[SPEC.layout]
    title_block = (
        template.title_block_left_m,
        0.0,
        template.width_m,
        template.title_block_top_m,
    )
    drawable = (region.xmin, region.ymin, region.xmax, region.ymax)
    inks = {
        name: _read_dimension_ink(annotation, name)
        for name, (annotation, *_rest) in dimensions.items()
    }
    problems = [
        problem
        for name, (_annotation, owner, obstacles, boundary, silhouette) in (
            dimensions.items()
        )
        for problem in _dimension_ink_problems(
            inks[name],
            owner=owner,
            obstacles={**obstacles, "title block": title_block},
            region=drawable,
            boundary=boundary,
            silhouette=silhouette,
        )
    ]
    census = {
        "stem": SPEC.artifact_stem,
        "elements": [
            {
                "label": element.label,
                "kind": element.kind,
                "owner": element.owner,
                "scope": element.scope.name,
                "box_mm": [round(value * 1000.0, 3) for value in element.box],
            }
            for element in elements
        ],
        "leaders": [
            {
                "label": segment.label,
                "kind": segment.kind,
                "owner": segment.owner,
                "from_mm": [
                    round(segment.x0 * 1000.0, 3),
                    round(segment.y0 * 1000.0, 3),
                ],
                "to_mm": [round(segment.x1 * 1000.0, 3), round(segment.y1 * 1000.0, 3)],
            }
            for segment in leaders
        ],
        "drawable_region_mm": [
            round(value * 1000.0, 3)
            for value in (region.xmin, region.ymin, region.xmax, region.ymax)
        ],
        "dimension_ink": [ink.as_mm() for ink in inks.values()],
    }
    _telemetry.info("layout census: " + json.dumps(census, sort_keys=True))
    LAYOUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    LAYOUT_REPORT.write_text(
        json.dumps(census, indent=2, sort_keys=True), encoding="utf-8"
    )
    if problems:
        raise RuntimeError("dimension ink:\n" + "\n".join(problems))
    check_drawing_layout(adapter, layout=SPEC.layout, stem=SPEC.artifact_stem)


def _fit_view(
    adapter: Any, view: Any, region: Box, margin: float, *, label: str
) -> Box:
    """Translate ``view`` into ``region`` and prove it stayed there."""
    rebuild_drawing(adapter, label=f"{label} extents")
    box = _view_box(view, label=label)
    dx, dy = _fit_translation(box, region, margin)
    position = tuple(float(value) for value in view.Position)
    if len(position) != 2:
        raise RuntimeError(f"{label} view has no position: {position!r}")
    if not view.SetViewPosition(
        double_array([position[0] + dx, position[1] + dy]), False
    ):
        raise RuntimeError(f"cannot position the {label} view")
    rebuild_drawing(adapter, label=f"{label} fit")
    fitted = _view_box(view, label=label)
    if not (
        fitted[0] >= region[0] + margin
        and fitted[1] >= region[1] + margin
        and fitted[2] <= region[2] - margin
        and fitted[3] <= region[3] - margin
    ):
        raise RuntimeError(
            f"{label} outline {_format_box(fitted)} escaped its region "
            f"{_format_box(region)} at {margin * 1000.0:.1f} mm clearance"
        )
    _telemetry.info(
        f"{label} outline {_format_box(fitted)} fitted into {_format_box(region)}"
    )
    return fitted


def _iso_note_xy(iso_box: Box) -> Point:
    """The linked note's anchor, centred under the fitted pictorial."""
    return (
        (iso_box[0] + iso_box[2] - ISO_NOTE_WIDTH_M) / 2.0,
        iso_box[1] - ISO_NOTE_BELOW_M,
    )


def _station(adapter: Any, view: Any, radial_mm: float, axial_mm: float) -> Point:
    """Sheet point of the model point (x = radial, y = axial) in ``view``."""
    return model_point_in_view(
        adapter,
        view,
        (radial_mm / 1000.0, axial_mm / 1000.0, 0.0),
        label=f"stud r {radial_mm:.3f} y {axial_mm:.3f}",
    )


def _unit(origin: Point, toward: Point) -> Point:
    length = math.dist(origin, toward)
    if length == 0.0:
        raise RuntimeError(f"degenerate sheet direction at {_mm(origin)} mm")
    return ((toward[0] - origin[0]) / length, (toward[1] - origin[1]) / length)


def _tip_axis(adapter: Any, view: Any) -> Point:
    """Sheet direction of model -Y (head toward tip) in ``view``."""
    return _unit(_station(adapter, view, 0.0, 0.0), _station(adapter, view, 0.0, -10.0))


def _axis_problem(direction: Point) -> str | None:
    """Why ``direction`` (model -Y on the sheet) is not horizontal, tip right."""
    if direction[0] <= 0.0 or abs(direction[1]) > AXIS_TOLERANCE_M:
        return f"stud axis reads {direction!r} on the sheet, not (1, 0): tip must point right"
    return None


def _orient_as_in_the_lathe(adapter: Any, front: Any) -> None:
    """Turn the front view until the stud's axis reads head left, tip right."""
    view = _early_bound(front, "IView")
    direction = _tip_axis(adapter, front)
    view.Angle = float(view.Angle) - math.atan2(direction[1], direction[0])
    rebuild_drawing(adapter, label="lathe orientation")
    direction = _tip_axis(adapter, front)
    _telemetry.info(
        f"front view angle {float(view.Angle):.6f} rad, tip axis {direction!r}"
    )
    problem = _axis_problem(direction)
    if problem is not None:
        raise RuntimeError(problem)


def _out_from(
    adapter: Any, view: Any, radial_mm: float, axial_mm: float, gap: float
) -> Point:
    """``gap`` of paper beyond the model point (radial, axial), radially out."""
    point = _station(adapter, view, radial_mm, axial_mm)
    axis = _station(adapter, view, 0.0, axial_mm)
    out = _unit(axis, point)
    return (point[0] + out[0] * gap, point[1] + out[1] * gap)


def _projected_box(
    adapter: Any, view: Any, half_mm: float, low_mm: float, high_mm: float
) -> Box:
    """Sheet box of the model rectangle |x| <= half, low <= y <= high."""
    corners = [
        _station(adapter, view, x, y)
        for x in (-half_mm, half_mm)
        for y in (low_mm, high_mm)
    ]
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return (min(xs), min(ys), max(xs), max(ys))


def _part_silhouette(adapter: Any, front: Any) -> tuple[Box, ...]:
    """The stud as the front view draws it: head, shank, tip and faced-end rows."""
    rows = (
        (HEAD_AF / 2.0, UNDERHEAD_Y_MM, UNDERHEAD_Y_MM + GB_WASHER_T + HEAD_H),
        (SHANK_DIA / 2.0, SHOULDER_Y_MM, UNDERHEAD_Y_MM),
        (TIP_RADIUS_MM, TIP_END_Y_MM + TIP_CHAMFER_MM, SHOULDER_Y_MM),
        (TIP_RADIUS_MM - TIP_CHAMFER_MM, TIP_END_Y_MM, TIP_END_Y_MM + TIP_CHAMFER_MM),
    )
    return tuple(_projected_box(adapter, front, *row) for row in rows)


def _model_dimension(view: Any, name: str) -> Any:
    """The named dimension of the part ``view`` draws."""
    model = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")
    parameter = model.Parameter(name)
    if parameter is None:
        raise RuntimeError(f"{name} is missing from the referenced part")
    return _early_bound(parameter, "IDimension")


def _model_finished_problems(
    *, driven_state: int, value: float, tolerance_type: int
) -> list[str]:
    """How the model's FinishedOverall stopped being the driving control."""
    problems = []
    if driven_state != 2:  # swDimensionDrivenState_e.swDimensionDriving
        problems.append(f"{MODEL_FINISHED} is no longer driving (state {driven_state})")
    if not math.isclose(
        value, MODEL_FINISHED_CONTROL, abs_tol=FINISHED_VALUE_TOLERANCE_M
    ):
        problems.append(f"{MODEL_FINISHED} nominal {value * 1000.0!r} mm changed")
    if tolerance_type != SW_TOL_NONE:
        problems.append(
            f"{MODEL_FINISHED} gained a native band (type {tolerance_type})"
        )
    return problems


def _model_finished_overall(view: Any) -> float:
    """Re-prove the part's driving FinishedOverall and return it (metres)."""
    dimension = _model_dimension(view, MODEL_FINISHED)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    problems = _model_finished_problems(
        driven_state=int(dimension.DrivenState),
        value=float(dimension.SystemValue),
        tolerance_type=int(tolerance.Type),
    )
    if problems:
        raise RuntimeError("; ".join(problems))
    return float(dimension.SystemValue)


def _chamfer_angle_problem(radial_m: float, axial_m: float) -> str | None:
    """Why the model's tip chamfer does not print as `` X 45°``."""
    if not math.isclose(radial_m, axial_m, abs_tol=FINISHED_VALUE_TOLERANCE_M):
        return (
            f"tip chamfer legs {radial_m * 1000.0!r} (radial) and "
            f"{axial_m * 1000.0!r} (axial) mm are not a 45 deg chamfer"
        )
    return None


def _assert_chamfer_is_45(view: Any) -> None:
    radial = float(_model_dimension(view, MODEL_CHAMFER_RADIAL).SystemValue)
    problem = _chamfer_angle_problem(radial, TIP_CHAMFER_MM / 1000.0)
    if problem is not None:
        raise RuntimeError(problem)


def _circle_edge(view: Any, radius_mm: float, axial_mm: float, *, label: str) -> Any:
    """The visible circular model edge of ``radius_mm`` at axial station ``axial_mm``."""
    candidates = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} circles"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        candidates.append((params[6], params[1], edge))
    if not candidates:
        raise RuntimeError(f"{label}: the view has no visible circular model edges")
    radius, axial, edge = min(
        candidates,
        key=lambda item: abs(item[0] - radius_mm) + abs(item[1] - axial_mm),
    )
    if (
        abs(radius - radius_mm) > CIRCLE_MATCH_MM
        or abs(axial - axial_mm) > CIRCLE_MATCH_MM
    ):
        raise RuntimeError(
            f"{label}: no circle of r {radius_mm:.3f} mm at y {axial_mm:.3f} mm; "
            f"nearest is r {radius:.3f} mm at y {axial:.3f} mm"
        )
    _telemetry.info(f"{label}: circle r {radius:.3f} mm at y {axial:.3f} mm")
    return edge


def _add_finished_reference(adapter: Any, front: Any) -> Any:
    """Dimension the drawn bearing face to the drawn faced end, as a reference.

    It runs on the far side of the axis from the tip length, beyond the hex
    head's corners, so the two never share a witness line or a text lane.
    """
    bearing = _circle_edge(front, *BEARING_CIRCLE, label="washer-face bearing edge")
    faced_end = _circle_edge(front, *FACED_END_CIRCLE, label="faced end edge")
    middle = (UNDERHEAD_Y_MM + TIP_END_Y_MM) / 2.0
    display = _early_bound(
        add_edge_dimension(
            adapter,
            front,
            p0=_station(adapter, front, -BEARING_CIRCLE[0], BEARING_CIRCLE[1]),
            p1=_station(adapter, front, -FACED_END_CIRCLE[0], FACED_END_CIRCLE[1]),
            text_xy=_out_from(
                adapter, front, -HEAD_CORNER_MM, middle, FINISHED_TEXT_OUT_M
            ),
            label="overall bearing-face-to-end reference",
            orientation="horizontal",
            entity_types=("EDGE", "EDGE"),
            entities=(bearing, faced_end),
        ),
        "IDisplayDimension",
    )
    # A drawing dimension has no part-authored places: the spec supplies them.
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION["FinishedOverall"], -1, -1, -1)
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    set_reference_dimension(adapter, annotation, label="overall length reference")
    rebuild_drawing(adapter, label="overall length reference")
    return annotation


def _finished_text_problem(
    places: int, texts: list[str], model_mm: float
) -> str | None:
    """Why the overall reference does not print as the spec's parenthesized value."""
    wanted = DRAWING_REFERENCE_PRECISION["FinishedOverall"]
    if places != wanted:
        return f"overall reference prints {places} places, the spec says {wanted}"
    expected = f"({model_mm:.{wanted}f})"
    rendered = "".join("".join(texts).split())
    if rendered != expected:
        return f"overall reference renders {texts!r}, expected {expected!r}"
    return None


def _assert_finished_display(annotation: Any, model_value: float) -> None:
    """Value, places and parentheses of the sheet's overall reference, fresh handle."""
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    value = float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue)
    places = int(_read_member(display, "GetPrimaryPrecision2"))
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    texts = [
        str(data.GetTextAtIndex(index) or "")
        for index in range(int(data.GetTextCount()))
    ]
    state = {
        "value_mm": value * 1000.0,
        "model_mm": model_value * 1000.0,
        "places": places,
        "texts": texts,
    }
    _telemetry.info("overall reference: " + json.dumps(state, sort_keys=True))
    if abs(value - model_value) > FINISHED_VALUE_TOLERANCE_M:
        raise RuntimeError(
            f"overall reference disagrees with {MODEL_FINISHED}: {state!r}"
        )
    problem = _finished_text_problem(places, texts, state["model_mm"])
    if problem is not None:
        raise RuntimeError(f"{problem}: {state!r}")


def _import_tip_controls(adapter: Any, front: Any, detail: Any) -> tuple[Any, Any]:
    """Import TipChamfer into the tip detail and TipLength into the lathe view.

    The detail claims its control first (as in ``draw_spring_hook``), then
    both are re-proved as the model's driving, banded controls.
    """
    chamfer_mid = TIP_END_Y_MM + TIP_CHAMFER_MM / 2.0
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep={
            "TipChamfer": _out_from(
                adapter, detail, TIP_RADIUS_MM, chamfer_mid, CHAMFER_TEXT_OUT_M
            )
        },
        view_label="tip chamfer",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    tip_mid = (SHOULDER_Y_MM + TIP_END_Y_MM) / 2.0
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep={
            "TipLength": _out_from(
                adapter, front, SHANK_DIA / 2.0, tip_mid, TIP_LENGTH_TEXT_OUT_M
            )
        },
        view_label="tip length",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    if len(front_annotations) != 1 or len(detail_annotations) != 1:
        raise RuntimeError(
            f"expected one tip control per view, got {len(front_annotations)} in the "
            f"lathe view and {len(detail_annotations)} in the tip detail"
        )
    trim_drawing.verify_machining_controls(
        adapter,
        [*front_annotations, *detail_annotations],
        expected=TIP_CONTROLS,
        tolerance_types=TIP_TOLERANCE_TYPES,
        precision={name: DIMENSION_PRECISION[name] for name in TIP_CONTROLS},
    )
    _assert_chamfer_is_45(detail)
    chamfer = _early_bound(
        detail_annotations[0].GetSpecificAnnotation(), "IDisplayDimension"
    )
    chamfer.SetText(SUFFIX, TIP_CHAMFER_CALLOUT_SUFFIX)
    rebuild_drawing(adapter, label="tip chamfer callout")
    fresh = _early_bound(
        detail_annotations[0].GetSpecificAnnotation(), "IDisplayDimension"
    )
    suffix = str(fresh.GetText(SUFFIX) or "")
    if suffix != TIP_CHAMFER_CALLOUT_SUFFIX:
        raise RuntimeError(f"tip chamfer callout suffix reads {suffix!r}")
    return front_annotations[0], detail_annotations[0]


def _import_tip_thread(adapter: Any, front: Any) -> None:
    """The tip's cosmetic #10-24 thread and its callout, on the lathe view."""
    seeds, instances = import_cosmetic_threads(adapter, front)
    _telemetry.info(f"tip cosmetic threads: {seeds} seed(s), {instances} instance(s)")
    if (seeds, instances) != (1, 1):
        raise RuntimeError(
            f"expected the tip's one cosmetic thread, got {seeds}/{instances}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open turned stud", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Knife-Hanger Stud — Turned Stock Drawing",
            1: "Native controls for turned purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-119; McMaster-Carr 91247A720",
            4: "Tip length and tip chamfer are native controls",
        },
    )
    front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        (FRONT_REGION[0] + FRONT_REGION[2]) / 2.0,
        (FRONT_REGION[1] + FRONT_REGION[3]) / 2.0,
        scale=SHEET_SCALE,
    )
    iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        (ISO_REGION[0] + ISO_REGION[2]) / 2.0,
        (ISO_REGION[1] + ISO_REGION[3]) / 2.0,
        scale=ISO_SCALE,
    )
    _orient_as_in_the_lathe(adapter, front)
    _fit_view(adapter, front, FRONT_REGION, FRONT_FIT_MARGIN_M, label="front")
    set_hidden_lines_removed(adapter, front)
    detail = trim_drawing.end_detail(adapter, front, SHEET)
    set_hidden_lines_removed(adapter, detail)
    # Import against the new geometry without waiting for a window repaint.
    _early_bound(detail, "IView").UpdateViewDisplayGeometry()
    iso_box = _fit_view(adapter, iso, ISO_REGION, ISO_FIT_MARGIN_M, label="isometric")
    iso_note = add_property_linked_note(
        adapter, "Isometric View Note", *_iso_note_xy(iso_box)
    )
    model_finished = _model_finished_overall(front)
    add_property_linked_note(adapter, "Supplier", 0.016, 0.056, char_height=0.003)
    add_property_linked_note(adapter, "Supplier SKUs", 0.016, 0.047, char_height=0.003)
    add_property_linked_note(adapter, "Stock Name", 0.016, 0.038, char_height=0.003)
    manufacturing_notes = add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.085, char_height=0.003
    )
    tip_length, tip_chamfer = _import_tip_controls(adapter, front, detail)
    _import_tip_thread(adapter, front)
    finished = _add_finished_reference(adapter, front)
    _assert_finished_display(finished, model_finished)
    silhouette = _part_silhouette(adapter, front)
    # Refusal (e) of the layout-tuning doc: re-assert the mode after the last
    # annotation lands on each view.
    for view in (front, detail):
        set_hidden_lines_removed(adapter, view)
    trim_drawing.position_detail_label(adapter, detail, SHEET)
    trim_drawing.position_parent_detail_letter(adapter, front, SHEET)
    front_box = _view_box(front, label="front")
    detail_box = _view_box(detail, label="tip detail")
    iso_note_box = _note_box(_early_bound(iso_note, "INote"), label="isometric note")
    detail_label_box = _note_box(
        _early_bound(_read_member(detail, "GetNotes")[0], "INote"), label="detail label"
    )
    notes_box = _note_box(
        _early_bound(manufacturing_notes, "INote"), label="manufacturing notes"
    )
    _assert_finished_display(finished, model_finished)
    _audit_sheet_layout(
        adapter,
        {
            "TipLength": (
                tip_length,
                front_box,
                {"tip detail": detail_box, "isometric": iso_box},
                None,
                silhouette,
            ),
            "TipChamfer": (
                tip_chamfer,
                detail_box,
                {
                    "front view": front_box,
                    "manufacturing notes": notes_box,
                    "isometric": iso_box,
                    "isometric note": iso_note_box,
                    "detail label": detail_label_box,
                },
                _detail_boundary(front, detail_box),
                (),
            ),
            "FinishedOverall": (
                finished,
                front_box,
                {"tip detail": detail_box, "isometric": iso_box},
                None,
                silhouette,
            ),
        },
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Hanger Stud — Turned Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
