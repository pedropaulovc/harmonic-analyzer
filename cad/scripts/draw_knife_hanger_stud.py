"""Create the manufacturing drawing for the modified McMaster 91247A720 stud.

The vendor bolt is purchased by SKU and shortened at the threaded end before
installation. The finished under-head and restored end deburr are native model
controls; undimensioned purchased head/thread geometry is reference.
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
    add_property_linked_note,
    check_drawing_layout,
    collect_layout_elements,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    offset_dimension_text,
    read_required_properties,
    rebuild_drawing,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _layout_geometry import estimate_text_box
from _stock_trim_drawing import TrimSheet
from build_knife_hanger_stud import SHANK_DIA, THREAD_TIP_Y_MM
from knife_hanger_stud_spec import (
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    CHAMFER_WIDTH_MM,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["knife_hanger_stud"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (2.0, 1.0)
# 1.5:1, not 2:1: ``GetOutline`` of the pictorial measures 72.4 x 135.2 mm at
# 2:1 (the rendered ink is only 52 x 99.5 mm -- the outline is NOT the ink),
# and no keep-in region tall enough for it leaves the 45 deg text block its
# pocket below. At 1.5:1 the outline is 54.3 x 101.4 mm and everything fits
# with margin (measured on leaf 20260922T152754Z, which failed loudly at 2:1).
ISO_SCALE = (1.5, 1.0)
FRONT_CENTER = (0.105, 0.175)
FRONT_KEEP = {"FinishedOverall": (0.070, 0.175)}
SHEET = TrimSheet(
    sheet_scale=SHEET_SCALE,
    detail_center=(0.265, 0.150),
    detail_scale=(12.0, 1.0),
    fence_radius_mm=2.5,
    cut_end_y_mm=THREAD_TIP_Y_MM,
    detail_offset_mm=1.0,
    # Right of the detail outline, never on it. The audit boxes the detail view
    # from ``GetOutline`` and the label from ``GetExtent``; at (0.310, 0.115) the
    # label box penetrated the outline's lower-right corner by 8.8 x 3.0 mm --
    # an overlap finding the layout gate rejects (its slack is 1.5 mm). The
    # extra drop to y = 0.108 buys the 45 deg text block a 34 mm pocket between
    # the label's top edge and the linked note below the pictorial.
    detail_label_xy=(0.335, 0.108),
    parent_letter_offset=(0.020, 0.014),
    detail_center_x_mm=SHANK_DIA / 2.0 - CHAMFER_WIDTH_MM / 2.0,
)

# The free upper-right cell the pictorial lives in, on this 0.4318 x 0.2794 m
# sheet: the detail outline ends at x = 0.303, the border's inner line is
# y = 0.2684 and the zone border keeps content under ~x 0.421. Sized for the
# MEASURED outline at 1.5:1 (54.3 x 101.4 mm) so the fit keeps >= 3 mm to every
# side and the callout pocket under it stays tall enough for the text block.
ISO_REGION = (0.290, 0.152, 0.415, 0.2625)
ISO_FIT_MARGIN_M = 0.003
# The linked "ISO SCALE 1.5:1" renders ~30 mm wide at its default text height and a note's
# SetPosition2 anchor is the text box's UPPER-LEFT (measured on this sheet), so
# it is centred under the fitted outline and kept just clear of it.
ISO_NOTE_WIDTH_M = 0.030
ISO_NOTE_BELOW_M = 0.004

# Clearance the 45 deg text block keeps from every surrounding box.
ANGLE_TEXT_GAP_M = 0.003
# How far PAST that clearance the block is parked. SetPosition2's block/anchor
# relation is not fixed behaviour, so parking exactly AT the limit re-measured
# 0.04 mm under it and the read-back guard failed a sheet that only needed
# margin (leaf 20260922T160352Z). The guard still demands ANGLE_TEXT_GAP_M.
ANGLE_TEXT_PARK_SLOP_M = 0.001

ROOT_FINISH_CALLOUT_TEXT = "CHAMFER TO EXISTING\nTHREAD ROOT"
# swDimensionTextParts_e: writing only the RESOLVED callout (3) leaves the
# stored definition empty, and the next rebuild re-resolves part 3 from it and
# the text disappears from the sheet. Write both compartments (the same
# resolved-vs-definition trap _drawing_common documents for hole-callout
# prefixes) and prove both survive a rebuild.
CALLOUT_ABOVE = 3  # swDimensionTextCalloutAbove (resolved)
CALLOUT_ABOVE_DEFINITION = 7  # swDimensionTextCalloutAboveDefinition (stored)
# The definition write also mirrors the text into the prefix lanes and turns
# the dimension value OFF (leaf 20260922T161521Z read parts 1/5 == the callout
# and the sheet printed no "45"). Clearing the resolved prefix clears its
# definition too (_drawing_common's hole-callout prefix proves 1 writes 5), and
# the value is switched back on -- the draw_tube_frame chamfer recipe.
PREFIX = 1  # swDimensionTextPrefix (resolved)
PREFIX_DEFINITION = 5  # swDimensionTextPrefixDefinition (stored)

# The angular dimension's ARC is laid out by the NON-offset position: SolidWorks
# draws it centred on the angle vertex through the text point, and a later
# ``OffsetText`` move carries only the text ("dimension line and extension
# lines ... do not move", types/IDisplayDimension/OffsetText.md). stud-4
# curated the dimension at a point 85 mm from the vertex and 8 deg outside the
# 0-45 deg span, so the arc swept the long way round the sheet at r = 84 mm.
# The arc is pinned first on the bisector, inside the 15.2 mm (12:1) chamfer
# leg so its 45 deg arrow lands on the chamfer itself; only then is the text
# offset to its pocket on a leader.
ANGLE_ARC_RADIUS_M = 0.013
ANGLE_ARC_RADIUS_TOLERANCE_M = 0.003
# Gate for every dimension arc on the sheet: stud-4's was 0.084 m.
ANGLE_ARC_RADIUS_MAX_M = 0.030
ANGLE_ARC_SWEEP_MAX_DEG = 60.0
ANGLE_ARC_HOLD_M = 0.0003
ANGLE_VERTEX_TOLERANCE_M = 0.0005
# The two legs as the cut-end detail draws them: the end face runs outward
# (+x) and the chamfer climbs outward toward the head at 45 deg.
ANGLE_BISECTOR_RAD = math.radians(CHAMFER_ANGLE_DEG / 2.0)
CHAMFER_VERTEX_MODEL_M = (
    (SHANK_DIA / 2.0 - CHAMFER_WIDTH_MM) / 1000.0,
    THREAD_TIP_Y_MM / 1000.0,
    0.0,
)
ARC_SAMPLES = 32

LAYOUT_REPORT = (
    Path(OUTPUTS.slddrw).parent.parent / "reports" / "layout-audit" / f"{SPEC.name}.json"
)
EXPECTED_CONTROLS = {
    "ChamferAngle": (
        math.radians(CHAMFER_ANGLE_DEG),
        -math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
        math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
    ),
}


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


def _clear_of(
    block: tuple[float, float, float, float],
    obstacle: tuple[float, float, float, float],
    gap: float,
) -> bool:
    """True when ``block`` keeps ``gap`` between itself and ``obstacle``."""
    return (
        block[0] >= obstacle[2] + gap
        or block[2] <= obstacle[0] - gap
        or block[1] >= obstacle[3] + gap
        or block[3] <= obstacle[1] - gap
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


def _display_text_box(adapter: Any, display: Any) -> tuple[float, float, float, float]:
    """The dimension's rendered text block, from its own display geometry.

    Each ``IDisplayData`` text item is boxed by :func:`estimate_text_box` at its
    REAL position, height and anchor corner, so a multi-item callout block is
    measured rather than guessed; the union is the block to park on the sheet.
    """
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    total = None
    for index in range(int(data.GetTextCount())):
        position = tuple(float(value) for value in (data.GetTextPositionAtIndex(index) or ()))
        if len(position) < 2:
            continue
        box = estimate_text_box(
            str(data.GetTextAtIndex(index) or ""),
            anchor=(position[0], position[1]),
            height=float(data.GetTextHeightAtIndex(index)),
            reference=int(data.GetTextRefPositionAtIndex(index)),
            angle=float(data.GetTextAngleAtIndex(index)),
            line_spacing=1.4,
        )
        if box is None:
            continue
        candidate = (box.xmin, box.ymin, box.xmax, box.ymax)
        total = candidate if total is None else (
            min(total[0], candidate[0]),
            min(total[1], candidate[1]),
            max(total[2], candidate[2]),
            max(total[3], candidate[3]),
        )
    if total is None:
        raise RuntimeError("45 deg dimension reports no text to place")
    return total


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
            "bounds_mm": None if bounds is None else [round(v * 1000.0, 2) for v in bounds],
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
) -> list[str]:
    """Every way ``ink`` escapes its own view or crosses something it must not."""
    problems = []
    for arc in ink.arcs:
        if arc.radius > ANGLE_ARC_RADIUS_MAX_M:
            problems.append(
                f"{ink.name} arc radius {arc.radius * 1000.0:.1f} mm exceeds "
                f"{ANGLE_ARC_RADIUS_MAX_M * 1000.0:.1f} mm"
            )
        if math.degrees(arc.sweep) > ANGLE_ARC_SWEEP_MAX_DEG:
            problems.append(
                f"{ink.name} arc sweeps {math.degrees(arc.sweep):.1f} deg "
                f"(> {ANGLE_ARC_SWEEP_MAX_DEG:.0f}): it runs the long way round"
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
    return problems


def _bisector_point(vertex: Point, radius: float) -> Point:
    """The point ``radius`` from the angle vertex on the 45 deg span's bisector."""
    return (
        vertex[0] + radius * math.cos(ANGLE_BISECTOR_RAD),
        vertex[1] + radius * math.sin(ANGLE_BISECTOR_RAD),
    )


def _angle_arc(annotation: Any) -> DimensionArc:
    """The 45 deg dimension's arc; an inline value may split it, never re-centre it."""
    ink = _read_dimension_ink(annotation, "ChamferAngle")
    if not ink.arcs:
        raise RuntimeError(f"45 deg dimension draws no arc: {ink.as_mm()!r}")
    first = ink.arcs[0]
    for arc in ink.arcs[1:]:
        if (
            math.dist(arc.center, first.center) > ANGLE_VERTEX_TOLERANCE_M
            or abs(arc.radius - first.radius) > ANGLE_VERTEX_TOLERANCE_M
        ):
            raise RuntimeError(f"45 deg dimension arcs disagree: {ink.as_mm()!r}")
    return first


def _pin_angle_arc(adapter: Any, annotation: Any, vertex_guess: Point) -> DimensionArc:
    """Lay the 45 deg arc on its bisector, close to the vertex, BEFORE offsetting.

    The arc centre IS the angle vertex, so it is read back rather than trusted
    from the model projection, and the non-offset text point is set at
    ``ANGLE_ARC_RADIUS_M`` along the bisector from it.
    """
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.OffsetText):
        display.OffsetText = False
    vertex = _angle_arc(annotation).center
    target = _bisector_point(vertex, ANGLE_ARC_RADIUS_M)
    placed = _early_bound(annotation, "IAnnotation")
    if not placed.SetPosition2(target[0], target[1], 0.0):
        raise RuntimeError("cannot pin the 45 deg dimension arc")
    rebuild_drawing(adapter, label="45 deg arc")
    ink = _read_dimension_ink(annotation, "ChamferAngle")
    arc = _angle_arc(annotation)
    _telemetry.info(
        "45 deg arc pinned: "
        + json.dumps(
            {
                "vertex_model_projection_mm": _mm(vertex_guess),
                "vertex_mm": _mm(vertex),
                "target_mm": _mm(target),
                "ink": ink.as_mm(),
            },
            sort_keys=True,
        )
    )
    if math.dist(arc.center, vertex) > ANGLE_VERTEX_TOLERANCE_M:
        raise RuntimeError(
            f"45 deg arc re-centred from {_mm(vertex)} to {_mm(arc.center)} mm"
        )
    if abs(arc.radius - ANGLE_ARC_RADIUS_M) > ANGLE_ARC_RADIUS_TOLERANCE_M:
        raise RuntimeError(
            f"45 deg arc radius {arc.radius * 1000.0:.1f} mm, wanted "
            f"{ANGLE_ARC_RADIUS_M * 1000.0:.1f} within "
            f"{ANGLE_ARC_RADIUS_TOLERANCE_M * 1000.0:.1f} mm"
        )
    return arc


def _write_root_finish_callout(display: Any, text: str) -> None:
    """Store the callout in the DEFINITION lane first, then the resolved lane.

    Writing only the resolved lane (3) leaves the stored definition (7) empty
    and the next rebuild / save re-resolves the lane from it, so the text drops
    off the sheet -- the same resolved-vs-definition trap _drawing_common
    documents for hole-callout prefixes. The definition goes in first so no
    later write can clear what the resolved lane renders from.
    """
    display.SetText(CALLOUT_ABOVE_DEFINITION, text)
    display.SetText(CALLOUT_ABOVE, text)
    # Undo the definition write's side effects: the prefix copy and the hidden
    # value (see PREFIX above).
    display.SetText(PREFIX, "")
    display.ShowDimensionValue = True


def _callout_text_parts(display: Any) -> dict[str, str]:
    """Every ``swDimensionTextParts_e`` compartment, as the rebuild left it."""
    return {
        str(part): str(display.GetText(part) or "") for part in range(1, 9)
    }


def _assert_root_finish_callout(display: Any, text: str) -> None:
    """Fail unless the callout lanes carry the text and the value still prints."""
    parts = _callout_text_parts(display)
    shows_value = bool(display.ShowDimensionValue)
    _telemetry.info(
        "root-finish callout text parts: "
        + json.dumps({**parts, "show_value": shows_value}, sort_keys=True)
    )
    for part in (CALLOUT_ABOVE, CALLOUT_ABOVE_DEFINITION):
        if parts[str(part)] != text:
            raise RuntimeError(
                f"root-finish callout did not survive the rebuild in text part "
                f"{part}: {parts[str(part)]!r} != {text!r} (all parts: {parts!r})"
            )
    for part in (PREFIX, PREFIX_DEFINITION):
        if parts[str(part)]:
            raise RuntimeError(
                f"root-finish callout leaked into prefix part {part}: "
                f"{parts[str(part)]!r} (all parts: {parts!r})"
            )
    if not shows_value:
        raise RuntimeError("the 45 deg dimension value is hidden behind its callout")


def _reference_dimension(
    adapter: Any, annotations: list[Any], name: str, label: str
) -> Any:
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} reference dimension, found {len(matches)}")
    set_reference_dimension(adapter, matches[0], label=label)
    return matches[0]


def _attach_root_finish_callout(adapter: Any, annotations: list[Any]) -> Any:
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "ChamferAngle"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one native angle dimension, found {len(matches)}")
    display = _early_bound(
        matches[0].GetSpecificAnnotation(), "IDisplayDimension"
    )
    _write_root_finish_callout(display, ROOT_FINISH_CALLOUT_TEXT)
    rebuild_drawing(adapter, label="root finish callout")
    # EditRebuild3 can hand out a new IDisplayDimension: probing the old handle
    # reads the pre-rebuild state, so the proof runs on a FRESH one and both
    # handles' compartments land in the log for the next diagnosis.
    _telemetry.info(
        "root-finish callout parts on the pre-rebuild handle: "
        + json.dumps(_callout_text_parts(display), sort_keys=True)
    )
    fresh = _early_bound(
        matches[0].GetSpecificAnnotation(), "IDisplayDimension"
    )
    _assert_root_finish_callout(fresh, ROOT_FINISH_CALLOUT_TEXT)
    return matches[0]


def _place_angle_text(
    adapter: Any,
    annotation: Any,
    *,
    anchor: tuple[float, float],
    obstacles: dict[str, tuple[float, float, float, float]],
    arc: DimensionArc,
) -> tuple[float, float]:
    """Park the offset 45 deg text block in the free pocket, from measured boxes.

    ``SetPosition2`` on an offset dimension reports the leader attachment, whose
    relation to the rendered block is not fixed API behaviour -- so the block is
    measured from the dimension's own ``IDisplayData`` text items, moved as a
    whole, and re-measured after the rebuild. The final position is proven by
    ``GetPosition`` readback and by clearance to every surrounding box. The
    block sits as level with the pinned arc as the pocket allows, so the leader
    back to it is short, and the arc itself must not have moved.
    """
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    offset_dimension_text(adapter, [annotation], {"ChamferAngle": anchor})
    block = _display_text_box(adapter, display)
    gap = ANGLE_TEXT_GAP_M
    park = gap + ANGLE_TEXT_PARK_SLOP_M
    left = obstacles["cut-end detail"][2] + park
    bottom = obstacles["DETAIL A label"][3] + park
    top = min(obstacles["isometric"][1], obstacles["isometric note"][1]) - park
    height = block[3] - block[1]
    if top - bottom < height:
        raise RuntimeError(
            f"45 deg text pocket {(top - bottom) * 1000.0:.1f} mm is shorter than "
            f"its {height * 1000.0:.1f} mm block"
        )
    level = _bisector_point(arc.center, arc.radius)[1] - height / 2.0
    target = (left, min(max(level, bottom), top - height))
    anchor = (anchor[0] + target[0] - block[0], anchor[1] + target[1] - block[1])
    offset_dimension_text(adapter, [annotation], {"ChamferAngle": anchor})
    block = _display_text_box(adapter, display)
    for name, obstacle in obstacles.items():
        if not _clear_of(block, obstacle, gap):
            raise RuntimeError(
                f"45 deg text block {_format_box(block)} is not {gap * 1000.0:.1f} mm "
                f"clear of {name} {_format_box(obstacle)}"
            )
    position = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(position[:2], anchor) > 0.0001:
        raise RuntimeError(
            f"45 deg text position did not persist: {position[:2]!r} != {anchor!r}"
        )
    held = _angle_arc(annotation)
    if (
        math.dist(held.center, arc.center) > ANGLE_ARC_HOLD_M
        or abs(held.radius - arc.radius) > ANGLE_ARC_HOLD_M
    ):
        raise RuntimeError(
            f"offsetting the 45 deg text moved its arc: {arc.as_mm()!r} -> "
            f"{held.as_mm()!r}"
        )
    _telemetry.info(
        "45 deg text block placed: "
        + json.dumps(
            {
                "block_mm": [round(value * 1000.0, 1) for value in block],
                "anchor_mm": [round(value * 1000.0, 1) for value in anchor],
            },
            sort_keys=True,
        )
    )
    return anchor


def _audit_sheet_layout(
    adapter: Any,
    dimensions: dict[str, tuple[Any, Box, dict[str, Box]]],
) -> None:
    """Census the sheet in millimetres, publish it, then gate the layout.

    The census is emitted BEFORE the gates so a failing leaf still publishes
    the numbers its fix is placed from. Every dimension's rendered ink (arcs,
    witness lines, leaders, arrows) is gated first -- ``check_drawing_layout``
    cannot see it -- then ``check_drawing_layout`` holds the sheet to zero
    overlaps, zero border crossings and zero leader crossings.
    ``dimensions`` maps each dimension name to its annotation, its owning
    view's outline and the boxes its ink must not cross.
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
        for name, (annotation, _owner, _obstacles) in dimensions.items()
    }
    problems = [
        problem
        for name, (_annotation, owner, obstacles) in dimensions.items()
        for problem in _dimension_ink_problems(
            inks[name],
            owner=owner,
            obstacles={**obstacles, "title block": title_block},
            region=drawable,
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


def _verify_controls(adapter: Any, annotations: list[Any]) -> None:
    trim_drawing.verify_machining_controls(
        adapter,
        annotations,
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )


def _fit_iso_view(adapter: Any, iso: Any) -> tuple[float, float, float, float]:
    """Translate the pictorial into ``ISO_REGION`` and prove it stayed there."""
    rebuild_drawing(adapter, label="isometric extents")
    box = _view_box(iso, label="isometric")
    dx, dy = _fit_translation(box, ISO_REGION, ISO_FIT_MARGIN_M)
    position = tuple(float(value) for value in iso.Position)
    if len(position) != 2:
        raise RuntimeError(f"isometric view has no position: {position!r}")
    if not iso.SetViewPosition(double_array([position[0] + dx, position[1] + dy]), False):
        raise RuntimeError("cannot position the isometric view")
    rebuild_drawing(adapter, label="isometric fit")
    fitted = _view_box(iso, label="isometric")
    margin = ISO_FIT_MARGIN_M
    if not (
        fitted[0] >= ISO_REGION[0] + margin
        and fitted[1] >= ISO_REGION[1] + margin
        and fitted[2] <= ISO_REGION[2] - margin
        and fitted[3] <= ISO_REGION[3] - margin
    ):
        raise RuntimeError(
            f"isometric outline {_format_box(fitted)} escaped ISO_REGION "
            f"{_format_box(ISO_REGION)} at {margin * 1000.0:.1f} mm clearance"
        )
    _telemetry.info(
        f"isometric outline {_format_box(fitted)} fitted into "
        f"{_format_box(ISO_REGION)}"
    )
    return fitted


def _iso_note_xy(iso_box: tuple[float, float, float, float]) -> tuple[float, float]:
    """The linked note's anchor, centred under the fitted pictorial."""
    return (
        (iso_box[0] + iso_box[2] - ISO_NOTE_WIDTH_M) / 2.0,
        iso_box[1] - ISO_NOTE_BELOW_M,
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified stud", await adapter.open_model(str(SOURCE)))
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
            0: "Knife-Hanger Stud — Modified Stock Drawing",
            1: "Native controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-119; McMaster-Carr 91247A720",
            4: "Finished under-head and cut-end deburr are native controls",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        (ISO_REGION[0] + ISO_REGION[2]) / 2.0,
        (ISO_REGION[1] + ISO_REGION[3]) / 2.0,
        scale=ISO_SCALE,
    )
    set_hidden_lines_visible(adapter, front)
    detail = trim_drawing.end_detail(adapter, front, SHEET)
    set_hidden_lines_visible(adapter, detail)
    _early_bound(detail, "IView").UpdateViewDisplayGeometry()
    iso_box = _fit_iso_view(adapter, iso)
    iso_note = add_property_linked_note(
        adapter, "Isometric View Note", *_iso_note_xy(iso_box)
    )
    detail_box = _view_box(detail, label="cut end detail")
    # Curate the 45 deg dimension ON its span, near the vertex: this first,
    # non-offset position is what fixes the arc radius (_pin_angle_arc).
    vertex_guess = model_point_in_view(
        adapter, detail, CHAMFER_VERTEX_MODEL_M, label="chamfer angle vertex"
    )
    detail_keep = {"ChamferAngle": _bisector_point(vertex_guess, ANGLE_ARC_RADIUS_M)}
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=detail_keep,
        view_label="cut end detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="finished under-head length",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *detail_annotations]
    angle_annotations = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "ChamferAngle"
    ]
    _verify_controls(adapter, angle_annotations)
    if len(angle_annotations) != 1:
        raise RuntimeError(
            f"expected one native angle dimension, found {len(angle_annotations)}"
        )
    arc = _pin_angle_arc(adapter, angle_annotations[0], vertex_guess)
    angle = _attach_root_finish_callout(adapter, angle_annotations)
    finished = _reference_dimension(
        adapter,
        front_annotations,
        "FinishedOverall",
        "finished under-head length reference",
    )
    add_property_linked_note(adapter, "Supplier", 0.016, 0.056, char_height=0.003)
    add_property_linked_note(adapter, "Supplier SKUs", 0.016, 0.047, char_height=0.003)
    add_property_linked_note(adapter, "Stock Name", 0.016, 0.038, char_height=0.003)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.085, char_height=0.003
    )
    for view in (front, detail):
        set_hidden_lines_removed(adapter, view)
    trim_drawing.position_detail_label(adapter, detail, SHEET)
    trim_drawing.position_parent_detail_letter(adapter, front, SHEET)
    iso_note_box = _note_box(_early_bound(iso_note, "INote"), label="isometric note")
    detail_label_box = _note_box(
        _early_bound(_read_member(detail, "GetNotes")[0], "INote"),
        label="detail label",
    )
    _place_angle_text(
        adapter,
        angle,
        anchor=detail_keep["ChamferAngle"],
        obstacles={
            "cut-end detail": detail_box,
            "isometric": iso_box,
            "isometric note": iso_note_box,
            "DETAIL A label": detail_label_box,
        },
        arc=arc,
    )
    front_box = _view_box(front, label="front")
    _audit_sheet_layout(
        adapter,
        {
            "ChamferAngle": (
                angle,
                detail_box,
                {
                    "front view": front_box,
                    "isometric": iso_box,
                    "isometric note": iso_note_box,
                    "DETAIL A label": detail_label_box,
                },
            ),
            "FinishedOverall": (
                finished,
                front_box,
                {"cut-end detail": detail_box, "isometric": iso_box},
            ),
        },
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Hanger Stud — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
