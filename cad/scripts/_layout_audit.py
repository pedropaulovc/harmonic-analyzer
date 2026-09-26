"""The unified drawing layout audit: one sheet's COM dump in, findings out.

Every manufacturing drawing runs this from ``_drawing_common.finalize_drawing``
on every sheet. It replaces three partial audits that each missed real
collisions (2026-09-25: MHA-092's "20.8"/"8.42" and "Ø3.26 ⊽ 6.9"/"6.0" text
runs, ADJUSTER ENTRY crossed by a view edge; MHA-035's datum-origin axis
through a callout and a leader through "TOP VIEW SCALE 1:4"):

* ``_drawing_layout_check`` boxed every dimension as a +/-4 mm square with no
  collision scope, so dimension text never met other text;
* ``_layout_geometry`` + ``diagnostics/drawing_layout_audit`` estimated text
  WIDTH from character counts (``<MOD-DIAM>`` counted ten glyphs) and only
  reported text PENETRATING other text by 0.3 mm, so touching text passed;
* ``draw_harmonic_base``'s local checks were calibrated but ran on one sheet.

None of them compared text with the part's own drawn edges.

This module is SolidWorks-free. The live collector
(``_drawing_layout_audit.collect_sheet_dumps``) turns each sheet into a plain
JSON ``dump``; this module parses that dump into ``_layout_geometry`` objects
and audits it. The same code path therefore runs on the farm and in the offline
tests, which replay dumps captured from real leaves.

Text boxes come from ``IDisplayData`` text items, whose positions are the
LOWER-LEFT corner of each run in sheet space (supports' hb-callout-cal: a
callout's last row sits exactly on its shoulder line). Within one row, the gap
between consecutive items' x positions is that item's exact rendered advance
('<MOD-DIAM>' measured 5.28 mm at 3.5 mm, one glyph plus spacing), so only the
LAST item of a row needs an estimate, from a per-sheet advance measured on the
exact ones. A callout with a horizontal shoulder uses supports' rule instead:
every row is centred on the shoulder, which spans the widest row.

Every threshold here is provisional until the calibration run measures it
against the leaf's own vector PDF; the constants say what they were set from.
"""

from __future__ import annotations

import math
import os
import re
import tempfile
from dataclasses import dataclass, replace
from enum import Enum
from heapq import heappop, heappush
from itertools import combinations, product
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from _drawing_layout_check import (
    DEFAULT_CROSSING_INSET_M,
    DrawableRegion,
    LeaderSegment,
    _proper_crossing,
)
from _layout_geometry import (
    ARROW_TEXT_CLEARANCE_M,
    DEFAULT_ADVANCE_RATIO,
    DEFAULT_TEXT_TOUCH_TOL_M,
    MM,
    AnnotationGeometry,
    Box,
    Finding,
    Segment,
    SegmentGrid,
    SheetGeometry,
    ViewGeometry,
    find_border_breaches,
    find_leader_crossings,
    find_text_on_line,
    point_segment_distance,
    segment_box_distance,
    segment_circle_distance,
    text_overlap,
    union_boxes,
)

DUMP_SCHEMA = 1


class LayoutAuditMode(Enum):
    """What finalize_drawing does with findings.

    REPORT logs every finding and never fails the leaf: it exists so one fleet
    run can size the blast radius and hand each owner a finding list before the
    audit gates anything. GATE raises on any gating finding.
    """

    REPORT = "report"
    GATE = "gate"


LAYOUT_AUDIT_MODE = LayoutAuditMode.REPORT


class FindingSeverity(Enum):
    """GATING findings fail the drawing under GATE; ADVISORY ones never do."""

    GATING = "gating"
    ADVISORY = "advisory"


# Near-contact clearance between the text of two DISTINCT annotations, as a
# fraction of the smaller text height. Rule 8 requires visible air: two runs
# closer than a word space read as ONE string. Measured on MHA-092's own PDF
# (tight pdfium glyph boxes, 3.5 mm text): the word space in "SLOT DEPTH" is
# 1.77 mm (0.51 h), while "20.8" and "8.42" -- which print as "20.88.42" --
# are 0.64 mm apart. A penetration test (the old 0.3 mm) passes that pair.
# PROVISIONAL until the fleet calibration run's distribution confirms it.
TEXT_CLEARANCE_HEIGHTS = 0.5

# Separation between the text blocks of DISTINCT annotations, as a fraction of
# the smaller text height. Clear of each other but closer than this, two
# callouts read as one (hb-render-4: the cross-tap row 1.7 mm under the spring
# callout's underline). ADVISORY until the fleet report's distribution sets it.
TEXT_SEPARATION_HEIGHTS = 1.0

# Two callout blocks stacked in one column (their x spans overlap) read as ONE
# block unless the gap between them is wider than the spacing between their
# own rows. SolidWorks sets rows 5.556 mm apart at 3.5 mm text; the spring
# block 1.7 mm over the cross-tap block read as its fourth row (Main's
# hb-render-4 eye pass, supports' find_merged_blocks at 375bf2aad).
ROW_PITCH_HEIGHTS = 0.005556 / 0.0035

# A callout or note runs to four rows at most (Main's hb-render-4 ruling: the
# six-row cross-tap callout; supports' find_tall_callouts at 375bf2aad).
TEXT_ROW_LIMIT = 4

# A leader leaves its shoulder at the corner of the row sitting on it, so its
# own rows are tested shrunk by this much (supports' OWN_ROW_INSET_M).
OWN_ROW_INSET_M = 0.0002

# Items within this fraction of a text height in y belong to one row. Items on
# one rendered row differ by ~0.05 mm (hb-callout-cal: 0.25483 vs 0.25478).
ROW_Y_FRACTION = 0.3

# A horizontal annotation line within this distance of a row's baseline is the
# callout's SHOULDER (its underline), not a leader.
SHOULDER_Y_TOL_M = 0.0003

# PDF ink (``_pdf_ink``, stored in each dump's ``ink``) is the truth for WHERE
# text and model edges printed; COM display data says WHAT each one is.
# Calibration run layoutcal-d09c2b9eb: every COM text item with a string
# matched one PDF text object (208/208), while COM row boxes overshot the ink
# by a median 2.5 mm (p95 21 mm) and GetPolylines7 put 0-59% of a view's
# edges on its printed strokes. A text item and its PDF text object are the
# same run when their strings agree and their lower-left corners lie within
# this window (COM positions sit ~0.9 mm below the glyphs).
INK_MATCH_WINDOW_M = 0.003
# Model edges print as 0.25 mm solid black strokes (annotation ink 0.18 mm,
# section lines 0.35 mm, the frame and title block grey).
MODEL_EDGE_WIDTH_M = (0.00022, 0.00030)
# A dashed stroke whose ends both lie within this of an annotation's segment
# is that annotation's ink, not a hidden model edge.
HIDDEN_EDGE_ON_ANNOTATION_M = 0.0001

# Symbol tokens IDisplayData returns unresolved; each renders as ONE glyph.
_TOKEN = re.compile(r"<[^<>]+>")

# swAnnotationType_e (enums/swAnnotationType_e.md).
ANNOTATION_KINDS = {
    1: "cosmetic-thread",
    2: "datum",
    3: "datum-target",
    4: "dim",
    5: "gtol",
    6: "note",
    7: "surface-finish",
    8: "weld",
    9: "custom-symbol",
    10: "dowel",
    11: "leader",
    12: "block",
    13: "center-mark",
    14: "table",
    15: "centerline",
    16: "datum-origin",
    17: "weld-bead",
    18: "revision-cloud",
    19: "pmi-only",
}
# Annotations whose ink is a construction mark on the geometry, not a callout:
# their lines are obstacles for text, but they carry no text of their own.
_MARK_KINDS = frozenset({"center-mark", "centerline", "cosmetic-thread"})
# swTextPosition_e: where a text run's reference point sits on its box, as
# (x, y) fractions of the box. Unknown references read as lower-left.
_TEXT_ANCHORS = {0: (0.0, 1.0), 1: (0.0, 0.0), 2: (0.5, 0.5), 3: (1.0, 1.0), 4: (1.0, 0.0), 5: (0.5, 1.0)}
# Lines closer than this, over more than this, print as one stroke
# (crankhub's _drawing_leaders COLLINEAR_TOLERANCE, Main's ruling).
COLLINEAR_TOL_M = 1e-4
# Two leaders landing on one corner may converge within their last 5 mm
# (Main's ruling on cone-gear-shaft's Ra 1.6 and Sec4Dia): advisory there.
LANDING_CONVERGE_M = 0.005
# A dimension line crossing a foreign extension line gates only this close
# to a dimension's text, in text heights (Main's ruling b, ASME).
DIM_CROSSING_TEXT_HEIGHTS = 0.5
# Under this share of a sheet's COM strings matched to printed text, the page
# is not where the sheet is (origin, scale or page mapping): fail.
MIN_MATCH_SHARE = 0.5
# Line roles a leader must not cross.
# How far an outside arrow's tail runs from its tip, arrowhead included: the
# stand-alone tail of every outside arrow on the six d09c2b9eb calibration
# sheets is 6.35 mm (a 3.56 mm head plus 2.79 mm of line). A longer run from
# the tip is a run-out to parked text; only its first 6.35 mm is tail.
ARROW_TAIL_M = 0.00635

LINE_ROLES = frozenset({"line", "dim-line", "ext-line"})
# Annotation ink a leader may cross (see ``find_leader_across_lines``).
_NOT_CROSSING_TARGETS = frozenset({"geometry", "detail-circle"})
# swAnnotationVisibilityState_e: 2 = half hidden, 3 = hidden.
# Two annotations of one type anchored within this of each other print on top
# of each other. Every coincident pair on the run-2 calibration sheets
# (95a9e97ca: 30 centre-mark pairs over 5 drawings, #913) was exact, 0.0 um
# apart with identical display data; 0.01 mm leaves room for float noise only.
DUPLICATE_POSITION_TOL_M = 1e-5

_HIDDEN_STATES = (2, 3)
_OWNER_DRAWING_SHEET = 1

# A leader may cross a part's outline to reach a feature inside it. It
# reads as one of the part's lines when it runs much further over the part
# than the feature's shortest approach from outside: the tip's distance to
# the view's printed-edge box. Detour = run over the part minus that
# approach. PROVISIONAL (Main's ruling, 2026-09-26), from the
# layoutcal2/c2 replay and swing's 917-s1 sheet 2, in mm of detour: swing's
# RD2 22.2 at 24cbab237 and 3.8 at its fix 4dda16fd5; cone-gear's nine Ra
# 1.6 bore leaders -5.1..-1.9; cone-tip-block's RD1 25.9; knife-mount's
# position frame 9.8 (eyed: readable). The fleet report re-sizes it.
LEADER_DETOUR_PROVISIONAL_M = 0.010
# A leader running further than this over the part is reported even with
# no detour (advisory): 25 mm is the brief's first limit, which swing's 24cb
# RD2 (28.2 mm) passed and its fix (14.1 mm) cleared.
LEADER_OVER_PART_M = 0.025
# Leader ink that never runs to a feature over a view: dimensions draw their
# own lines, and the rest are construction or view ink.
_UNLEADERED_KINDS = frozenset({"dim", "geometry", "section-line", "detail-circle", "table", *_MARK_KINDS})
# A thread designation in callout text, keyed as printed: unified
# ("1/4-20", "#8-32", "10-24") or metric by its major diameter ("M6" of
# "M6x1.0"). Two leadered callouts in one view naming one thread call the
# same holes out twice (cone-swing-platform's "1/4-20 Tapped Hole" beside
# RD2's "2X ... 1/4-20 UNC - 2B THRU ALL", 24cbab237).
_THREAD = re.compile(r"(?<![\w/.#])(#?\d+(?:/\d+)?-\d+|M\d+(?:\.\d+)?)(?=[\s,;xX×]|$)")
# A hole callout's leading instance count: "2X " of RD2's first row.
_INSTANCES = re.compile(r"^\s*(\d+)\s*X(?![A-Za-z])")
# Printed edge pieces meeting here are one stroke chain. A PDF path's pieces
# share their end points exactly (_pdf_ink flattens each curve in place);
# this only absorbs float noise where two paths meet.
RING_JOIN_M = 1e-6
# HOLE_*: PROVISIONAL, from the printed rings of 24cbab237's
# cone-swing-platform View2 (the restored PDF, swing-24cb-raw). One hole's
# concentric rings fit centres this close: the two countersinks' rings fit
# 6 and 9 um apart.
HOLE_CENTER_TOL_M = 0.00005
# Two holes are one size when every ring's radius agrees this closely: the
# countersinks' outer rings fit 1.639 and 1.634 mm, the dowels 0.796 and
# 0.792 mm.
HOLE_RADIUS_TOL_M = 0.00002
# A leader lands on a ring when its end lies within a model-edge stroke
# width of it: RD2's arrow tip sits 0.009 mm off hole A's inner ring and
# DetailItem357's leader end 0.004 mm off hole B's outer one, while a
# countersink's two rings print 0.36 mm apart.
HOLE_LANDING_TOL_M = MODEL_EDGE_WIDTH_M[1]


def is_hidden(annotation: Mapping[str, Any]) -> bool:
    """A dumped annotation the sheet does not draw (swAnnotationHidden or
    half-hidden), which the audit leaves out."""
    return int(annotation.get("visible", 1) or 1) in _HIDDEN_STATES


def _prints(annotation: Mapping[str, Any], layers: Mapping[str, Mapping[str, bool]]) -> bool:
    state = layers.get(str(annotation.get("layer") or ""))
    return state is None or (bool(state.get("visible", True)) and bool(state.get("printable", True)))


def printed_dump(dump: Mapping[str, Any]) -> Mapping[str, Any]:
    """The dump without the annotations on a layer that does not print.

    COM reads such an annotation ``Visible`` 1, but it leaves no ink: the
    audit judges what prints (Main's ruling on cone-swing-platform's profile
    thread callout on COSMETIC-THREADS-HIDDEN, 24cbab237). A layer the dump
    has no state for prints. ``hidden_layer_count`` keeps the drop visible.
    """
    layers = dump.get("layers") or {}
    if not layers:
        return dump
    return {
        **dump,
        "views": [
            {**view, "annotations": [a for a in view.get("annotations") or () if _prints(a, layers)]}
            for view in dump.get("views", ())
        ],
        "sheet_annotations": [a for a in dump.get("sheet_annotations") or () if _prints(a, layers)],
    }


def hidden_layer_count(dump: Mapping[str, Any]) -> int:
    """How many of the sheet's annotations sit on a non-printing layer."""
    layers = dump.get("layers") or {}
    return sum(
        not _prints(annotation, layers)
        for annotations in (
            *(view.get("annotations") or () for view in dump.get("views", ())),
            dump.get("sheet_annotations") or (),
        )
        for annotation in annotations
    )


def audited_annotations(dump: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Every annotation the audit draws and matches to ink: each view's
    visible annotations, then the sheet's own visible ones (a sheet
    annotation owned by a view is already in that view's list). A hidden or
    template duplicate must not claim a visible annotation's printed text."""
    return [
        annotation
        for view in dump.get("views", ())
        for annotation in view.get("annotations", ())
        if not is_hidden(annotation)
    ] + [
        annotation
        for annotation in dump.get("sheet_annotations", ())
        if not is_hidden(annotation)
        and int(annotation.get("owner_type", _OWNER_DRAWING_SHEET)) == _OWNER_DRAWING_SHEET
    ]


# --------------------------------------------------------------------------
# display-data primitives -> segments
# --------------------------------------------------------------------------


def _floats(values: Any) -> list[float]:
    return [float(value) for value in (values or ())]


def line_segment(raw: Sequence[float], role: str = "line") -> Segment | None:
    """``GetLineAtIndex3`` ([4 scalars, start3, end3]) or ``GetLineAtIndex2``.

    The start index is read from the array LENGTH: both overloads end with the
    two points, and they differ only in how many scalars lead.
    """
    values = _floats(raw)
    if len(values) < 8:
        return None
    start = len(values) - 6
    return Segment(
        values[start], values[start + 1], values[start + 3], values[start + 4], role
    )


def _arc_points(
    center: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    ccw: bool,
    per_turn: int = 32,
) -> list[tuple[float, float]]:
    radius = math.hypot(start[0] - center[0], start[1] - center[1])
    a0 = math.atan2(start[1] - center[1], start[0] - center[0])
    a1 = math.atan2(end[1] - center[1], end[0] - center[0])
    if math.hypot(end[0] - start[0], end[1] - start[1]) < 1e-9:
        sweep = 2.0 * math.pi
    else:
        sweep = (a1 - a0) % (2.0 * math.pi)
        if not ccw:
            sweep -= 2.0 * math.pi
    steps = max(2, int(math.ceil(abs(sweep) / (2.0 * math.pi) * per_turn)))
    return [
        (
            center[0] + radius * math.cos(a0 + sweep * i / steps),
            center[1] + radius * math.sin(a0 + sweep * i / steps),
        )
        for i in range(steps + 1)
    ]


def arc_segments(raw: Sequence[float], role: str = "line") -> list[Segment]:
    """``GetArcAtIndex2``: [color, type, _, _, start3, end3, center3, normal3, dir].

    A closed arc (start == end) is a full circle -- a balloon, a detail circle.
    ``rotationDir`` is a boolean as a double, CCW = true (any non-zero, as a
    COM VARIANT_BOOL true may read -1) and CW = 0; a -Z normal flips it.
    """
    values = _floats(raw)
    if len(values) < 17:
        return []
    start = (values[4], values[5])
    end = (values[7], values[8])
    center = (values[10], values[11])
    normal_z = values[15]
    direction = values[16]
    ccw = (direction != 0) == (normal_z >= 0)
    points = _arc_points(center, start, end, ccw=ccw)
    return [
        Segment(a[0], a[1], b[0], b[1], role) for a, b in zip(points, points[1:])
    ]


def polyline_segments(raw: Sequence[float], role: str = "line") -> list[Segment]:
    """``IDisplayData::GetPolylineAtIndex2``: [type, size, color, font, _, _, n, xyz]."""
    values = _floats(raw)
    if len(values) < 7:
        return []
    count = int(values[6])
    points = values[7 : 7 + 3 * count]
    if len(points) != 3 * count:
        size = int(values[1])
        points = values[7 + size : 7 + size + 3 * count]
    xy = [(points[i], points[i + 1]) for i in range(0, len(points) - 2, 3)]
    return [Segment(a[0], a[1], b[0], b[1], role) for a, b in zip(xy, xy[1:])]


def polygon_segments(raw: Sequence[float], role: str = "line") -> list[Segment]:
    """``GetPolygonAtIndex``: [color, type, _, _, n, xyz...], closed."""
    values = _floats(raw)
    if len(values) < 5:
        return []
    count = int(values[4])
    points = values[5 : 5 + 3 * count]
    xy = [(points[i], points[i + 1]) for i in range(0, len(points) - 2, 3)]
    if len(xy) < 2:
        return []
    return [
        Segment(a[0], a[1], b[0], b[1], role) for a, b in zip(xy, [*xy[1:], xy[0]])
    ]


def triangle_segments(raw: Sequence[float], role: str = "arrow") -> list[Segment]:
    """``GetTriangleAtIndex``: [v1[3], v2[3], v3[3], isFilled, lineType]."""
    values = _floats(raw)
    if len(values) < 9:
        return []
    xy = [(values[0], values[1]), (values[3], values[4]), (values[6], values[7])]
    return [
        Segment(a[0], a[1], b[0], b[1], role) for a, b in zip(xy, [*xy[1:], xy[0]])
    ]


def arrowhead_segments(raw: Sequence[float], role: str = "arrow") -> list[Segment]:
    """``GetArrowHeadAtIndex2``: [tip3, dir3, width, height, style, normal3].

    Width runs along the arrow direction, height across it. ``dir`` points
    from the tip back along the shaft, toward the arrowhead's base: every
    unambiguous arrowhead on the six calibration PDFs (125 of 125, d09c2b9eb)
    printed its base there, none on the far side of the tip.
    """
    values = _floats(raw)
    if len(values) < 8:
        return []
    tip = (values[0], values[1])
    dx, dy = values[3], values[4]
    length = math.hypot(dx, dy)
    if length == 0.0:
        return []
    ux, uy = dx / length, dy / length
    width, height = values[6], values[7]
    base = (tip[0] + ux * width, tip[1] + uy * width)
    left = (base[0] - uy * height / 2.0, base[1] + ux * height / 2.0)
    right = (base[0] + uy * height / 2.0, base[1] - ux * height / 2.0)
    xy = [tip, left, right]
    return [
        Segment(a[0], a[1], b[0], b[1], role) for a, b in zip(xy, [*xy[1:], xy[0]])
    ]


# --------------------------------------------------------------------------
# text rows
# --------------------------------------------------------------------------


def ink_key(text: str) -> str:
    """A string as the PDF prints it: symbol tokens are paths, blanks no ink."""
    return re.sub(r"\s+", "", _TOKEN.sub("", text)).upper()


@dataclass(frozen=True)
class InkSpan:
    """One PDF text object: what it says and its tight glyph box."""

    key: str
    box: Box


def ink_spans(dump: Mapping[str, Any]) -> list[InkSpan]:
    spans = []
    for raw in (dump.get("ink") or {}).get("spans", ()):
        text, *box = raw
        spans.append(InkSpan(ink_key(str(text)), Box(*_floats(box)[:4])))
    return spans


def ink_annotation_strokes(dump: Mapping[str, Any]) -> list[Segment]:
    """The page's solid strokes thinner than a model edge: annotation ink."""
    low, _high = MODEL_EDGE_WIDTH_M
    return [
        Segment(*_floats(raw)[:4], "line")
        for raw in (dump.get("ink") or {}).get("strokes", ())
        if float(raw[4]) < low and not raw[5]
    ]


# A balloon's GetDisplayData circle sits up to 0.57 mm off the ring the PDF
# prints (layoutcal2-c, drive-train-assembly: 28 balloons, the COM leader
# start lands exactly on the printed ring), so the printed ring wins when
# the page's strokes trace one within this band of the COM circle.
BALLOON_RING_SEARCH_M = 0.001
# The printed ring is a polyline; every vertex lies this close to its fit.
BALLOON_RING_FIT_TOL_M = 0.0001


def _fit_circle(points: Sequence[tuple[float, float]]) -> tuple[float, float, float] | None:
    """Least-squares (Kasa) circle through ``points``; None when degenerate."""
    n = len(points)
    mx = sum(x for x, _y in points) / n
    my = sum(y for _x, y in points) / n
    # Centred coordinates keep the normal equations well conditioned.
    suu = svv = suv = suuu = svvv = suvv = svuu = 0.0
    for x, y in points:
        u, v = x - mx, y - my
        suu += u * u
        svv += v * v
        suv += u * v
        suuu += u * u * u
        svvv += v * v * v
        suvv += u * v * v
        svuu += v * u * u
    determinant = suu * svv - suv * suv
    if abs(determinant) < 1e-30:
        return None
    bu = 0.5 * (suuu + suvv)
    bv = 0.5 * (svvv + svuu)
    uc = (bu * svv - bv * suv) / determinant
    vc = (bv * suu - bu * suv) / determinant
    radius = math.sqrt(uc * uc + vc * vc + (suu + svv) / n)
    return (mx + uc, my + vc, radius)


def printed_circle(
    circle: tuple[float, float, float], strokes: Sequence[Segment]
) -> tuple[float, float, float]:
    """The ring a balloon PRINTED near its COM ``circle``, else ``circle``.

    Fits a circle to the stroke vertices within ``BALLOON_RING_SEARCH_M`` of
    the COM ring, dropping the worst-fitting vertex (a leader start or an
    arrowhead in the band) until every vertex lies within
    ``BALLOON_RING_FIT_TOL_M`` of the fit. The fit is kept only when it still
    traces a closed ring: at least 12 vertices, on every side.
    """
    cx, cy, radius = circle
    points = sorted(
        {
            point
            for segment in strokes
            for point in ((segment.x0, segment.y0), (segment.x1, segment.y1))
            if abs(math.hypot(point[0] - cx, point[1] - cy) - radius) <= BALLOON_RING_SEARCH_M
        }
    )
    while len(points) >= 12:
        fit = _fit_circle(points)
        if fit is None:
            return circle
        fx, fy, fr = fit
        residuals = [abs(math.hypot(x - fx, y - fy) - fr) for x, y in points]
        worst = max(range(len(points)), key=residuals.__getitem__)
        if residuals[worst] > BALLOON_RING_FIT_TOL_M:
            del points[worst]
            continue
        if len({(x >= fx, y >= fy) for x, y in points}) < 4:
            return circle
        return fit
    return circle


def _move_ring(
    segments: Sequence[Segment], com: tuple[float, float, float], printed: tuple[float, float, float]
) -> list[Segment]:
    """``segments`` with the balloon's own body moved onto the ``printed`` ring.

    The body is every plain ``line`` segment lying within the COM circle: the
    circumference and, for a split-circle balloon, its rim-to-rim separator.
    Each is mapped by the similarity that takes the COM circle onto the
    printed one, so the balloon as an obstacle reads where it printed. A
    leader, shoulder or arrowhead keeps its (exact) registered geometry, even
    when a short leader puts an arrowhead's base inside the circle.
    """
    if printed == com:
        return list(segments)
    cx, cy, radius = com
    px, py, pr = printed
    scale = pr / radius

    def inside(x: float, y: float) -> bool:
        return math.hypot(x - cx, y - cy) <= radius + 1e-7

    def moved(x: float, y: float) -> tuple[float, float]:
        return (px + (x - cx) * scale, py + (y - cy) * scale)

    out = []
    for segment in segments:
        if segment.role != "line" or not (inside(segment.x0, segment.y0) and inside(segment.x1, segment.y1)):
            out.append(segment)
            continue
        out.append(Segment(*moved(segment.x0, segment.y0), *moved(segment.x1, segment.y1), segment.role))
    return out


def ink_edges(dump: Mapping[str, Any]) -> list[Segment]:
    """The page's model-edge strokes (``MODEL_EDGE_WIDTH_M``, solid black)."""
    low, high = MODEL_EDGE_WIDTH_M
    return [
        Segment(*_floats(raw)[:4], "geometry")
        for raw in (dump.get("ink") or {}).get("strokes", ())
        if low <= float(raw[4]) <= high and not raw[5]
    ]


def ink_dashed_strokes(dump: Mapping[str, Any]) -> list[Segment]:
    """The page's dashed strokes no wider than a model edge: hidden edges
    (Hidden Lines Visible prints them at 0.18 mm) among centre marks,
    cosmetic threads and other annotations' dashes, which
    ``_hidden_model_edges`` separates."""
    return [
        Segment(*_floats(raw)[:4], "hidden")
        for raw in (dump.get("ink") or {}).get("strokes", ())
        if float(raw[4]) <= MODEL_EDGE_WIDTH_M[1] and raw[5]
    ]


def _hidden_model_edges(
    dashed: Sequence[Segment], annotations: Sequence[AnnotationGeometry], tol: float = HIDDEN_EDGE_ON_ANNOTATION_M
) -> list[Segment]:
    """The dashed strokes that are NOT an annotation's own ink: the pieces
    whose both ends lie on some annotation segment (a centre mark, a thread,
    a dimension's dashed extension) belong to that annotation."""
    own = [
        segment
        for annotation in annotations
        if annotation.kind != "geometry"
        for segment in annotation.segments
    ]
    grid = SegmentGrid(list(enumerate(own)))

    def on_annotation(dash: Segment) -> bool:
        reach = Box(
            min(dash.x0, dash.x1) - tol, min(dash.y0, dash.y1) - tol, max(dash.x0, dash.x1) + tol, max(dash.y0, dash.y1) + tol
        )
        return any(
            point_segment_distance((dash.x0, dash.y0), segment) <= tol
            and point_segment_distance((dash.x1, dash.y1), segment) <= tol
            for _index, segment in grid.near(reach)
        )

    return [dash for dash in dashed if not on_annotation(dash)]


def _anchor(box: Box, reference: int) -> tuple[float, float]:
    fx, fy = _TEXT_ANCHORS.get(reference, (0.0, 0.0))
    return box.xmin + fx * box.width, box.ymin + fy * box.height


def match_ink_indices(
    items: Sequence[tuple[Any, TextItem]],
    spans: Sequence[InkSpan],
    *,
    taken: Iterable[int] = (),
) -> dict[Any, tuple[int, ...]]:
    """One-to-one: each keyed COM text item to the PDF text object(s) that
    printed it, as span indices (``taken`` spans are already claimed).

    Candidates share the item's ink string and sit within ``INK_MATCH_WINDOW_M``
    plus one text height of its reference point, compared to the same point of
    the span's box (``GetTextRefPositionAtIndex``: lower-left, centre, ...).
    Each span serves one item, so six "13.12"s on one sheet cannot claim the
    same run, and the assignment is complete before it is short: as many
    items as possible are matched, then at the least total distance
    (``_assign``) -- nearest-first could hand a flexible item the one span a
    constrained item needed. Symbol-only items
    (``<MOD-DIAM>``) print as paths, not text, and never match. A run with a
    symbol INSIDE it may print as one text object per side of the symbol's
    path; it then matches those pieces in order along its baseline. Whole and
    split matches are chosen together (``_assign_all``), for the same reason:
    a plain "A" must not take the one "A" a split "A<TOKEN>B" needed when
    another "A" would serve it.
    """
    used = set(taken)
    by_key = _spans_by_key(spans)
    options = {key: ink_options(item, spans, by_key, used) for key, item in items}
    return _assign_all({key: found for key, found in options.items() if found})


def _spans_by_key(spans: Sequence[InkSpan]) -> dict[str, list[int]]:
    by_key: dict[str, list[int]] = {}
    for index, span in enumerate(spans):
        by_key.setdefault(span.key, []).append(index)
    return by_key


def ink_options(
    item: TextItem,
    spans: Sequence[InkSpan],
    by_key: Mapping[str, Sequence[int]],
    used: Iterable[int] = (),
) -> list[tuple[tuple[int, ...], float]]:
    """Every way ``item`` can have printed, as ``(span indices, cost)`` for
    ``_assign_all``: a whole span of its ink string within the match window of
    its reference point, or its pieces either side of an inline symbol."""
    used = set(used)
    wanted = ink_key(item.text)
    if not wanted:
        return []
    window = INK_MATCH_WINDOW_M + item.height
    options: list[tuple[tuple[int, ...], float]] = []
    for index in by_key.get(wanted, ()):
        if index in used:
            continue
        ax, ay = _anchor(spans[index].box, item.reference)
        dx, dy = abs(ax - item.x), abs(ay - item.y)
        if dx < window and dy < window:
            options.append(((index,), dx + dy))
    options.extend(_split_chains(item, spans, by_key, used))
    return options


def _split_chains(
    item: TextItem,
    spans: Sequence[InkSpan],
    by_key: Mapping[str, Sequence[int]],
    used: set[int],
) -> list[tuple[tuple[int, ...], float]]:
    """Every way a run split by an inline symbol can print: one free span per
    piece, in reading order along its baseline, each starting where the last
    one ended. Cost: the first piece's offset from the run's start, plus each
    gap and each baseline offset. Measured in the run's own frame
    (``_baseline_extent``), so a rotated run reads its pieces up the page."""
    parts = [ink_key(part) for part in _TOKEN.split(item.text) if ink_key(part)]
    if len(parts) < 2:
        return []
    window = INK_MATCH_WINDOW_M + item.height
    right = (glyph_count(item.text) + 1) * item.height
    chains: list[tuple[tuple[int, ...], float]] = []

    def extend(chain: tuple[int, ...], left: float, anchor: float, cost: float) -> None:
        if len(chain) == len(parts):
            chains.append((chain, cost))
            return
        for index in by_key.get(parts[len(chain)], ()):
            if index in used or index in chain:
                continue
            start, end, low, _high = _baseline_extent(item, spans[index].box)
            if not left <= start <= right or abs(low) >= window:
                continue
            step = abs(start - anchor) + abs(low)
            extend((*chain, index), end - INK_MATCH_WINDOW_M, end, cost + step)

    extend((), -window, 0.0, 0.0)
    return chains


def _baseline_extent(item: TextItem, box: Box) -> tuple[float, float, float, float]:
    """``box`` in the run's frame, from its start: ``(start, end)`` along the
    baseline and ``(low, high)`` across it. At angle 0 this is the box less
    the run's position."""
    cos_a, sin_a = math.cos(item.angle), math.sin(item.angle)
    corners = [(x - item.x, y - item.y) for x in (box.xmin, box.xmax) for y in (box.ymin, box.ymax)]
    along = [x * cos_a + y * sin_a for x, y in corners]
    across = [y * cos_a - x * sin_a for x, y in corners]
    return min(along), max(along), min(across), max(across)


def _from_baseline(item: TextItem, start: float, end: float, low: float, high: float) -> Box:
    """The page box around a rectangle given in the run's frame."""
    cos_a, sin_a = math.cos(item.angle), math.sin(item.angle)
    return Box.from_points(
        [
            (item.x + u * cos_a - v * sin_a, item.y + u * sin_a + v * cos_a)
            for u in (start, end)
            for v in (low, high)
        ]
    )


def _assign_all(
    options: Mapping[Any, Sequence[tuple[tuple[int, ...], float]]],
) -> dict[Any, tuple[int, ...]]:
    """The most items matched with no span shared, then the least total cost,
    over every item's options: a whole match is one span, a split run's is a
    set of spans (``_split_chains``). Items compete only within a group that
    shares candidate spans. A group with no split option is bipartite
    (``_assign``); one with split options is searched exactly over its split
    choices, the rest of it assigned bipartitely for each (``_pack_group``).
    """
    keys = list(options)
    parent = {key: key for key in keys}

    def find(key: Any) -> Any:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    owner: dict[int, Any] = {}
    for key in keys:
        for indices, _cost in options[key]:
            for index in indices:
                if index not in owner:
                    owner[index] = key
                    continue
                parent[find(key)] = find(owner[index])
    groups: dict[Any, list[Any]] = {}
    for key in keys:
        groups.setdefault(find(key), []).append(key)
    matched: dict[Any, tuple[int, ...]] = {}
    for group in groups.values():
        matched.update(_pack_group(group, options))
    return matched


def _pack_group(
    group: Sequence[Any],
    options: Mapping[Any, Sequence[tuple[tuple[int, ...], float]]],
) -> dict[Any, tuple[int, ...]]:
    """One group's best assignment: each split-capable item takes one of its
    split options or none, exhaustively, and every other item then takes a
    whole match from what is left, bipartitely."""
    split_keys = [key for key in group if any(len(indices) > 1 for indices, _ in options[key])]
    # A split item left without a split option still competes in ``whole``
    # when it has a one-span option, so the bound keeps counting it (Codex).
    whole_capable = {key for key in split_keys if any(len(indices) == 1 for indices, _ in options[key])}
    others = len(group) - len(split_keys)

    def whole(taken: frozenset[int], skip: Mapping[Any, Any]) -> tuple[list[tuple[Any, int]], float]:
        costs = {
            (key, indices[0]): cost
            for key in group
            if key not in skip
            for indices, cost in options[key]
            if len(indices) == 1 and indices[0] not in taken
        }
        pairs = _assign(costs) if costs else []
        return pairs, sum(costs[pair] for pair in pairs)

    best: dict[str, Any] = {"count": -1, "cost": 0.0, "pick": {}}
    pick: dict[Any, tuple[int, ...]] = {}

    def search(position: int, taken: frozenset[int], cost: float, skipped: int) -> None:
        # Most items this branch can still match: those picked, the split
        # items not yet decided, the whole-only items, and each skipped split
        # item that can still match whole.
        if len(pick) + len(split_keys) - position + others + skipped < best["count"]:
            return
        if position == len(split_keys):
            pairs, whole_cost = whole(taken, pick)
            count, total = len(pick) + len(pairs), cost + whole_cost
            if count > best["count"] or (count == best["count"] and total < best["cost"]):
                best.update(count=count, cost=total, pick={**pick, **{key: (index,) for key, index in pairs}})
            return
        key = split_keys[position]
        for indices, step in sorted(options[key], key=lambda option: option[1]):
            if len(indices) < 2 or not taken.isdisjoint(indices):
                continue
            pick[key] = indices
            search(position + 1, taken | frozenset(indices), cost + step, skipped)
            del pick[key]
        search(position + 1, taken, cost, skipped + (key in whole_capable))

    search(0, frozenset(), 0.0, 0)
    return best["pick"]


def _assign(costs: Mapping[tuple[Any, int], float]) -> list[tuple[Any, int]]:
    """The most (row, column) pairs of ``costs`` sharing no row or column, at
    the least total cost among those: the Hungarian method on a square
    matrix where a missing pair costs more than any complete assignment."""
    rows = sorted({row for row, _ in costs}, key=repr)
    cols = sorted({col for _, col in costs})
    size = max(len(rows), len(cols))
    forbidden = 1.0 + sum(costs.values())
    grid = [
        [costs.get((rows[i], cols[j]), forbidden) if i < len(rows) and j < len(cols) else forbidden
         for j in range(size)]
        for i in range(size)
    ]
    # e-maxx formulation, 1-based: u/v potentials, owner[j] = row on column j.
    u, v, owner, way = [0.0] * (size + 1), [0.0] * (size + 1), [0] * (size + 1), [0] * (size + 1)
    for i in range(1, size + 1):
        owner[0], j0 = i, 0
        low, done = [math.inf] * (size + 1), [False] * (size + 1)
        while owner[j0]:
            done[j0] = True
            i0, delta, j1 = owner[j0], math.inf, 0
            for j in range(1, size + 1):
                if done[j]:
                    continue
                reduced = grid[i0 - 1][j - 1] - u[i0] - v[j]
                if reduced < low[j]:
                    low[j], way[j] = reduced, j0
                if low[j] < delta:
                    delta, j1 = low[j], j
            for j in range(size + 1):
                if done[j]:
                    u[owner[j]] += delta
                    v[j] -= delta
                else:
                    low[j] -= delta
            j0 = j1
        while j0:
            j1 = way[j0]
            owner[j0] = owner[j1]
            j0 = j1
    return [
        (rows[owner[j] - 1], cols[j - 1])
        for j in range(1, size + 1)
        if owner[j] - 1 < len(rows) and j - 1 < len(cols) and (rows[owner[j] - 1], cols[j - 1]) in costs
    ]


def _union(boxes: Iterable[Box]) -> Box:
    boxes = list(boxes)
    box = boxes[0]
    for other in boxes[1:]:
        box = box.union(other)
    return box


def match_ink(
    items: Sequence[tuple[Any, TextItem]], spans: Sequence[InkSpan]
) -> dict[Any, Box]:
    """``match_ink_indices`` as glyph boxes: one box per matched item.

    The solver over a caller's own item set, for a unit test to drive. A
    SHEET's text is matched by ``assign_sheet_text`` alone, which adds the
    section and detail labels that compete for the same spans; the audit and
    the layout calibration both read that one assignment.
    """
    return {key: span_box(spans, indices) for key, indices in match_ink_indices(items, spans).items()}


def span_box(spans: Sequence[InkSpan], indices: Iterable[int]) -> Box:
    """The printed box of the spans one text item matched."""
    return _union(spans[index].box for index in indices)


def assign_sheet_text(
    dump: Mapping[str, Any], annotations: Sequence[Mapping[str, Any]], spans: Sequence[InkSpan]
) -> dict[Any, tuple[int, ...]]:
    """The sheet's ONE text-to-ink assignment, as span indices per key.

    Annotation runs (``(id(annotation), index)``), section-line labels
    (``("section", view, line, label)``) and detail-circle labels
    (``("detail", view, circle)``) compete for the same spans, so none may
    take a span another needed when a different one would have served it
    (Codex, #902). ``sheet_model`` and the layout calibration both read this,
    so the match rate and offsets the calibration reports are the audit's.
    """
    if not spans:
        return {}
    by_key = _spans_by_key(spans)
    options: dict[Any, list[tuple[tuple[int, ...], float]]] = {
        (id(annotation), index): ink_options(item, spans, by_key)
        for annotation in annotations
        for index, item in enumerate(text_items(annotation.get("display") or {}))
    }
    for v, view in enumerate(dump.get("views", ())):
        for s, section in enumerate(view.get("sections", ())):
            for t, item in enumerate(_section_label_items(section)):
                options[("section", v, s, t)] = ink_options(item, spans, by_key)
        for number, (*_arc, text_pt, (height, _)) in enumerate(_detail_circles(view.get("detail_circles_info") or ())):
            if height > 0.0:
                options[("detail", v, number)] = _detail_label_options(text_pt, height, spans)
    return _assign_all({key: found for key, found in options.items() if found})


def glyph_count(text: str) -> int:
    """Rendered glyphs in a display-data string: each ``<TOKEN>`` is one glyph."""
    return len(_TOKEN.sub("#", text))


@dataclass(frozen=True)
class TextItem:
    """One ``IDisplayData`` text run: string, lower-left corner, cap height."""

    text: str
    x: float
    y: float
    height: float
    angle: float = 0.0
    reference: int = -1


def text_items(display: Mapping[str, Any]) -> list[TextItem]:
    items = []
    for raw in display.get("texts", ()):
        text = str(raw.get("t", ""))
        position = _floats(raw.get("pos"))
        height = float(raw.get("h") or 0.0)
        if not text.strip() or height <= 0.0 or len(position) < 2:
            continue
        items.append(
            TextItem(
                text=text,
                x=position[0],
                y=position[1],
                height=height,
                angle=float(raw.get("ang") or 0.0),
                reference=int(raw.get("ref", -1)),
            )
        )
    return items


def group_rows(items: Sequence[TextItem]) -> list[list[TextItem]]:
    """Items on one printed row, top row first, each row left to right."""
    rows: list[list[TextItem]] = []
    for item in sorted(items, key=lambda it: (-it.y, it.x)):
        if rows and abs(rows[-1][0].y - item.y) < ROW_Y_FRACTION * item.height:
            rows[-1].append(item)
            continue
        rows.append([item])
    return [sorted(row, key=lambda it: it.x) for row in rows]


def exact_advances(items: Sequence[TextItem]) -> list[float]:
    """Glyph advance / height ratios measured from consecutive items in a row.

    An item's width is exact when another item follows it on the same
    horizontal row. Token-bearing items are skipped: a symbol glyph's advance
    is not the font's letter advance.
    """
    ratios = []
    for row in group_rows(items):
        for item, following in zip(row, row[1:]):
            if item.angle or _TOKEN.search(item.text):
                continue
            count = glyph_count(item.text)
            width = following.x - item.x
            if count and width > 0.0:
                ratios.append(width / (count * item.height))
    return ratios


def calibrate_sheet_advance(
    annotations: Iterable[Mapping[str, Any]], default: float = DEFAULT_ADVANCE_RATIO
) -> float:
    """One sheet's glyph advance ratio, from every exact item width on it."""
    ratios: list[float] = []
    for annotation in annotations:
        ratios.extend(exact_advances(text_items(annotation.get("display") or {})))
    if not ratios:
        return default
    ratio = median(ratios)
    return ratio if 0.35 <= ratio <= 1.2 else default


def _rotated_hull(item: TextItem, width: float) -> Box:
    cos_a, sin_a = math.cos(item.angle), math.sin(item.angle)
    corners = [(0.0, 0.0), (width, 0.0), (0.0, item.height), (width, item.height)]
    return Box.from_points(
        [(item.x + x * cos_a - y * sin_a, item.y + x * sin_a + y * cos_a) for x, y in corners]
    )


def _with_symbols(item: TextItem, box: Box, advance: float) -> Box:
    """A matched run's glyph box plus the symbols it prints as paths.

    ``"<MOD-DIAM>12.00"`` prints its text as a PDF text object and its "Ø" as
    a path the text object does not cover: a leading symbol reaches back to
    the run's COM start, a trailing one one glyph advance per token past it.
    Both reach along the run's baseline, so a rotated run grows up the page.
    """
    text = item.text.strip()
    lead = re.match(r"(?:<[^<>]+>\s*)*", text).group(0)
    trail = re.search(r"(?:\s*<[^<>]+>)*$", text[len(lead):]).group(0)
    start, end, low, high = _baseline_extent(item, box)
    if lead and item.reference in (-1, 0, 1):
        start = min(start, 0.0)
    end += len(_TOKEN.findall(trail)) * advance * item.height
    return box.union(_from_baseline(item, start, end, low, high))


def ink_row_boxes(
    items: Sequence[TextItem], ink: Mapping[int, Box], *, advance: float
) -> list[tuple[str, Box]]:
    """``(row text, box)`` per printed row, from the items' PDF glyph boxes.

    An item with no PDF text object (a symbol token, drawn as a path) is boxed
    from its COM position -- up to the next item on its row, else one advance --
    shifted by the offset its row's printed items show against their COM
    positions, so it lands where the glyphs did.
    """
    boxes: list[tuple[str, Box]] = []
    index_of = {id(item): index for index, item in enumerate(items)}
    for row in group_rows(items):
        text = "".join(item.text for item in row).strip()
        printed = [(item, ink[index_of[id(item)]]) for item in row if index_of[id(item)] in ink]
        shift = (
            median(box.ymin - item.y for item, box in printed),
            median(box.height for _item, box in printed),
        ) if printed else (0.0, 0.0)
        parts = [_with_symbols(item, box, advance) for item, box in printed]
        for position, item in enumerate(row):
            if index_of[id(item)] in ink:
                continue
            nxt = row[position + 1].x if position + 1 < len(row) else item.x + advance * item.height * glyph_count(item.text.strip())
            height = shift[1] or item.height
            parts.append(Box(item.x, item.y + shift[0], max(nxt, item.x), item.y + shift[0] + height))
        box = parts[0]
        for part in parts[1:]:
            box = box.union(part)
        boxes.append((text, box))
    return boxes


def row_boxes(
    items: Sequence[TextItem],
    *,
    advance: float,
    shoulders: Sequence[Segment] = (),
) -> list[tuple[str, Box]]:
    """``(row text, box)`` for each printed row of one annotation.

    Width: exact for every item but a row's last; the last uses ``advance``
    (trailing blanks carry no ink). With a SHOULDER under the block, supports'
    calibrated rule applies instead: rows are centred on the shoulder, which
    spans the widest row, so a row spans ``left .. 2*centre - left``.
    """
    boxes: list[tuple[str, Box]] = []
    shoulder_span = None
    if shoulders:
        xs = [x for s in shoulders for x in (s.x0, s.x1)]
        shoulder_span = (min(xs), max(xs))
    for row in group_rows(items):
        text = "".join(item.text for item in row).strip()
        rotated = [item for item in row if abs(item.angle) > 1e-6]
        if rotated:
            for item in rotated:
                width = advance * item.height * glyph_count(item.text.rstrip())
                boxes.append((item.text.strip(), _rotated_hull(item, width)))
            row = [item for item in row if item not in rotated]
            if not row:
                continue
        last = row[-1]
        right = last.x + advance * last.height * glyph_count(last.text.rstrip())
        first = row[0]
        # A run's position is where its first CHARACTER starts; leading blanks
        # (" 20.8 ") carry no ink.
        blanks = len(first.text) - len(first.text.lstrip())
        left = first.x + advance * first.height * blanks
        if shoulder_span is not None:
            centre = (shoulder_span[0] + shoulder_span[1]) / 2.0
            right = max(right, 2.0 * centre - left) if left < centre else right
        bottom = min(item.y for item in row)
        top = max(item.y + item.height for item in row)
        boxes.append((text, Box(left, bottom, max(right, left), top)))
    return boxes


# --------------------------------------------------------------------------
# dump -> AnnotationGeometry
# --------------------------------------------------------------------------


def _display_segments(display: Mapping[str, Any], *, arc_role: str = "line") -> list[Segment]:
    segments: list[Segment] = []
    for raw in display.get("lines", ()):
        segment = line_segment(raw)
        if segment is not None:
            segments.append(segment)
    for raw in display.get("arcs", ()):
        segments.extend(arc_segments(raw, role=arc_role))
    for raw in display.get("polylines", ()):
        segments.extend(polyline_segments(raw))
    for raw in display.get("polygons", ()):
        segments.extend(polygon_segments(raw))
    for raw in display.get("triangles", ()):
        segments.extend(triangle_segments(raw))
    for raw in display.get("arrows", ()):
        segments.extend(arrowhead_segments(raw))
    return segments


def _split_dimension_lines(segments: Sequence[Segment], arrows: Sequence[Any]) -> list[Segment]:
    """A dimension's straight lines as ``dim-line`` or ``ext-line``.

    The dimension line carries the arrowheads: a line parallel to an arrow's
    direction that runs through its tip is dimension line (including the run
    out to text parked beyond the arrows, and a diameter's leader-like line).
    Every other straight line of the dimension is an extension line. Arc
    pieces (angular dimensions) arrive already marked ``dim-line``. A
    dimension without arrowheads keeps plain ``line``.
    """
    tips = []
    for raw in arrows:
        values = _floats(raw)
        if len(values) < 8:
            continue
        length = math.hypot(values[3], values[4])
        if length:
            tips.append(((values[0], values[1]), (values[3] / length, values[4] / length)))
    if not tips:
        return list(segments)
    out = []
    for segment in segments:
        if segment.role != "line" or not segment.length:
            out.append(segment)
            continue
        ux, uy = (segment.x1 - segment.x0) / segment.length, (segment.y1 - segment.y0) / segment.length
        along = any(
            abs(ux * dy - uy * dx) < 0.02
            and abs((tip[0] - segment.x0) * uy - (tip[1] - segment.y0) * ux) < COLLINEAR_TOL_M
            for tip, (dx, dy) in tips
        )
        out.append(replace(segment, role="dim-line" if along else "ext-line"))
    return out


def _arrow_tails(segments: Sequence[Segment], arrows: Sequence[Any]) -> list[Segment]:
    """Each outside arrow's tail, as ``arrow-tail`` segments from its tip.

    An outside arrow's dimension line leaves its tip one way (``-dir``, toward
    the other extension line) and its tail the other (``dir``, on past the
    arrowhead's base). An inside arrow has no tail: the only line from its
    tip runs ``dir``, as dimension line. A run ``dir`` that ends on another
    arrow's tip is dimension line, not tail.
    """
    tips = []
    for raw in arrows:
        values = _floats(raw)
        if len(values) < 8:
            continue
        length = math.hypot(values[3], values[4])
        if length:
            tips.append(((values[0], values[1]), (values[3] / length, values[4] / length)))

    def at_tip(x: float, y: float) -> bool:
        return any(math.hypot(x - tx, y - ty) <= COLLINEAR_TOL_M for (tx, ty), _u in tips)

    tails = []
    for (tx, ty), (ux, uy) in tips:
        leaving = []
        for segment in segments:
            if segment.role != "dim-line" or not segment.length:
                continue
            ends = ((segment.x0, segment.y0), (segment.x1, segment.y1))
            for (sx, sy), (fx, fy) in (ends, ends[::-1]):
                if math.hypot(sx - tx, sy - ty) <= COLLINEAR_TOL_M:
                    dot = ((fx - sx) * ux + (fy - sy) * uy) / segment.length
                    leaving.append((dot, segment.length, (fx, fy)))
        if not any(dot < -0.98 for dot, _length, _far in leaving):
            continue
        for dot, length, far in leaving:
            if dot <= 0.98 or at_tip(*far):
                continue
            run = min(length, ARROW_TAIL_M)
            tails.append(Segment(tx, ty, tx + ux * run, ty + uy * run, "arrow-tail"))
    return tails


def _dimension_shoulders(segments: Sequence[Segment], items: Sequence[TextItem]) -> list[Segment]:
    """A dimension's text shoulder as ``shoulder``, not ``ext-line``.

    A diameter or radius dimension with its text parked off the feature
    draws a horizontal run on the baseline of its lowest text row, on from
    the free end of its dimension line, the way a callout does (knife-mount's
    Ø12.00 / THRU). It carries no arrow, so ``_split_dimension_lines`` calls
    it extension line. An extension line that merely passes the text's
    baseline (pinion-bracket's 7.000 witness at y 136) does not start where
    a dimension line ends, and stays ``ext-line``.
    """
    if not items:
        return list(segments)
    baseline = min(item.y for item in items)
    left = min(item.x for item in items)
    right = max(item.x + item.height for item in items)
    ends = [
        point
        for segment in segments
        if segment.role == "dim-line"
        for point in ((segment.x0, segment.y0), (segment.x1, segment.y1))
    ]

    def continues(segment: Segment) -> bool:
        return any(
            math.hypot(x - ex, y - ey) <= COLLINEAR_TOL_M
            for x, y in ((segment.x0, segment.y0), (segment.x1, segment.y1))
            for ex, ey in ends
        )

    return [
        replace(segment, role="shoulder")
        if segment.role == "ext-line"
        and _is_horizontal(segment)
        and abs(segment.y0 - baseline) < SHOULDER_Y_TOL_M
        and min(segment.x0, segment.x1) < right
        and max(segment.x0, segment.x1) > left
        and continues(segment)
        else segment
        for segment in segments
    ]


def _is_horizontal(segment: Segment) -> bool:
    return abs(segment.y1 - segment.y0) < 1e-7 and segment.length > 0.0


def _shoulders(segments: Sequence[Segment], items: Sequence[TextItem]) -> list[Segment]:
    """Horizontal lines on the baseline of an annotation's LOWEST text row."""
    if not items:
        return []
    baseline = min(item.y for item in items)
    return [
        segment
        for segment in segments
        if _is_horizontal(segment) and abs(segment.y0 - baseline) < SHOULDER_Y_TOL_M
    ]


def balloon_circle(display: Mapping[str, Any]) -> tuple[float, float, float] | None:
    """Centre and radius of the one full circle a balloon's display data draws."""
    circles = []
    for raw in display.get("arcs", ()):
        values = _floats(raw)
        if len(values) < 17:
            continue
        if math.hypot(values[4] - values[7], values[5] - values[8]) > 1e-9:
            continue
        radius = math.hypot(values[4] - values[10], values[5] - values[11])
        if radius > 0.0:
            circles.append((values[10], values[11], radius))
    return circles[0] if len(circles) == 1 else None


def _same_run(segment: Segment, leader: Segment, *, degrees: float = 2.0) -> bool:
    """A display-data run that is the registered ``leader``: it shares an end
    with it and runs the same way. The two can start apart -- cone-swing-
    platform's C'BORE note draws its display run from 0.5 mm off the attach
    point the registered leader (and the printed PDF stroke) starts at."""
    if not segment.length or not leader.length:
        return False
    ends = ((segment.x0, segment.y0), (segment.x1, segment.y1))
    shared = [
        (end, other)
        for end in ends
        for other in ((leader.x0, leader.y0), (leader.x1, leader.y1))
        if math.hypot(end[0] - other[0], end[1] - other[1]) <= COLLINEAR_TOL_M
    ]
    if not shared:
        return False
    a = math.atan2(segment.y1 - segment.y0, segment.x1 - segment.x0)
    b = math.atan2(leader.y1 - leader.y0, leader.x1 - leader.x0)
    turn = abs((a - b + math.pi) % (2.0 * math.pi) - math.pi)
    if min(turn, math.pi - turn) > math.radians(degrees):
        return False
    # Meeting end to end is a continuation (a shoulder running on from the
    # landing), not a copy: the two must overlap along the leader.
    ux, uy = (leader.x1 - leader.x0) / leader.length, (leader.y1 - leader.y0) / leader.length
    along = sorted((x - leader.x0) * ux + (y - leader.y0) * uy for x, y in ends)
    return min(along[1], leader.length) - max(along[0], 0.0) > COLLINEAR_TOL_M


def _registered_leaders(annotation: Mapping[str, Any]) -> list[Segment]:
    segments = []
    for raw in annotation.get("leaders", ()):
        values = _floats(raw)
        points = [(values[i], values[i + 1]) for i in range(0, len(values) - 2, 3)]
        segments.extend(
            Segment(a[0], a[1], b[0], b[1], "leader")
            for a, b in zip(points, points[1:])
        )
    return segments


def classify_segments(
    kind: str,
    annotation: Mapping[str, Any],
    segments: list[Segment],
    shoulders: Sequence[Segment],
) -> list[Segment]:
    """Give each display-data segment its role: shoulder, leader or line.

    * A hole callout's display data is its leader plus the shoulder under its
      text (supports' calibration): every other line is leader; its
      arrowhead stays an arrow.
    * Other annotations keep their display-data roles. Their leaders come
      from ``GetLeaderPointsAtIndex`` (``_registered_leaders``), and the
      display-data copy of each leader run is dropped (``_same_run``), so a
      leader is not reported twice, as line and as leader.
    """
    shoulder_ids = {id(s) for s in shoulders}
    hole_callout = bool((annotation.get("dim") or {}).get("hole_callout"))
    roles = []
    for segment in segments:
        if id(segment) in shoulder_ids:
            role = "shoulder"
        elif hole_callout and segment.role == "line":
            role = "leader"
        else:
            role = segment.role
        roles.append(replace(segment, role=role))
    return roles


@dataclass(frozen=True)
class AuditAnnotation(AnnotationGeometry):
    """An annotation plus the height of its TEXT.

    A free note's exact extent is its whole multi-row block and a balloon's is
    its circle, so neither box height is a text height; every threshold scaled
    by text height reads this instead.
    """

    text_height: float = 0.0
    arrow_tails: tuple[Segment, ...] = ()


def _cap_height(item: TextItem, box: Box) -> float:
    """One printed run's cap height. A level (or upside-down) run's glyph box
    is its cap height tall; a rotated run's axis-aligned box spans the
    string's length instead, so it keeps the COM height (a vertical
    dimension's text)."""
    if abs(math.sin(item.angle)) < 1e-6:
        return box.height
    return item.height


def text_height(annotation: AnnotationGeometry) -> float:
    height = getattr(annotation, "text_height", 0.0)
    if height > 0.0:
        return height
    return min((box.height for box in annotation.text_boxes), default=0.0)


def annotation_geometry(
    annotation: Mapping[str, Any],
    *,
    owner: str,
    advance: float,
    ink: Mapping[int, Box] | None = None,
    strokes: Sequence[Segment] = (),
) -> AnnotationGeometry | None:
    """One dumped annotation as the audit sees it: text rows plus its own ink.

    ``ink`` maps an item's index in ``text_items(display)`` to its printed PDF
    glyph box (``match_ink``); a sheet dumped with its PDF always passes it.
    ``strokes`` is the page's annotation ink (``ink_annotation_strokes``); a
    balloon's circle snaps to the ring it traces (``printed_circle``).
    """
    kind = ANNOTATION_KINDS.get(int(annotation.get("type", 0)), "other")
    if int(annotation.get("visible", 1) or 1) in _HIDDEN_STATES:
        return None
    label = str(annotation.get("name") or kind)
    display = annotation.get("display") or {}
    items = text_items(display)
    hole_callout = bool((annotation.get("dim") or {}).get("hole_callout"))
    segments = _display_segments(display, arc_role="dim-line" if kind == "dim" and not hole_callout else "line")
    if kind == "dim" and hole_callout:
        kind = "hole-callout"
    if kind == "note" and (annotation.get("note") or {}).get("balloon"):
        # A BOM balloon is a note with a leader, but a circle, not a callout.
        kind = "balloon"
    # A plain dimension's text sits on its own DIMENSION line; only a callout
    # (hole callout, leadered note) has a shoulder under its text.
    shoulders = _shoulders(segments, items) if kind in ("hole-callout", "note") else []
    segments = classify_segments(kind, annotation, segments, shoulders)
    tails: list[Segment] = []
    if kind == "dim":
        segments = _split_dimension_lines(segments, display.get("arrows", ()))
        segments = _dimension_shoulders(segments, items)
        tails = _arrow_tails(segments, display.get("arrows", ()))
    registered = _registered_leaders(annotation)
    segments = [s for s in segments if not any(_same_run(s, leader) for leader in registered)]
    segments.extend(registered)

    note = annotation.get("note") or {}
    exact = False
    rows: list[tuple[str, Box]]
    circle = balloon_circle(display) if note.get("balloon") else None
    if circle is not None and strokes:
        printed = printed_circle(circle, strokes)
        segments = _move_ring(segments, circle, printed)
        circle = printed
    if circle is not None:
        # A BOM balloon's GetExtent includes its leader; its rendered
        # full-circle arc is the balloon (``rendered_balloon_circle``).
        cx, cy, radius = circle
        rows = [(str(note.get("text", "")), Box(cx - radius, cy - radius, cx + radius, cy + radius))]
        exact = True
    elif ink:
        rows = ink_row_boxes(items, ink, advance=advance)
        exact = True
    elif kind == "note" and len(_floats(note.get("extent"))) >= 6 and not annotation.get("leaders"):
        # A free note's GetExtent is exact; a leadered one's includes its
        # leader, so leadered notes keep the row model.
        e = _floats(note["extent"])
        rows = [(str(note.get("text", "")), Box(min(e[0], e[3]), min(e[1], e[4]), max(e[0], e[3]), max(e[1], e[4])))]
        exact = True
    else:
        rows = row_boxes(items, advance=advance, shoulders=shoulders)
    if kind in _MARK_KINDS:
        rows = []
    if not rows and not segments:
        return None
    heights = [item.height for item in items]
    if ink:
        height = median(_cap_height(items[index], box) for index, box in ink.items())
    elif heights:
        height = max(heights)
    elif circle is not None:
        # No text items: a balloon circle is ~2.7 text heights across
        # (4.72 mm radius at 3.5 mm text, pen-assembly).
        height = 2.0 * circle[2] / 2.7
    elif exact and rows:
        # n rows of a free note span one text height plus n-1 row pitches.
        lines = max(1, len([t for t in str(note.get("text", "")).splitlines() if t.strip()]))
        height = rows[0][1].height / (1.0 + (lines - 1) * ROW_PITCH_HEIGHTS)
    else:
        height = 0.0
    position = _floats(annotation.get("pos"))
    # A table is also dumped whole under ``tables`` as ``table <name>``; its
    # grid lines must carry the SAME label or they read as a foreign line
    # through the table's own text.
    suffix = f" {rows[0][0]!r}" if rows and rows[0][0] and kind != "table" else ""
    return AuditAnnotation(
        label=f"{kind} {label}{suffix}",
        kind=kind,
        owner=owner,
        text_boxes=tuple(box for _text, box in rows),
        segments=tuple(segments),
        position=(position[0], position[1]) if len(position) >= 2 else None,
        exact=exact,
        circle=circle,
        text_height=height,
        arrow_tails=tuple(tails),
    )


def _section_label_items(section: Mapping[str, Any]) -> list[TextItem]:
    """A section line's labels as text items: its letter at each
    ``GetTextInfo`` upper-left origin, ``CharHeight`` tall."""
    label = str(section.get("label") or "")
    height = float(section.get("text_height") or 0.0)
    if not label or height <= 0.0:
        return []
    texts = _floats(section.get("texts"))
    return [TextItem(label, texts[i], texts[i + 1] - height, height) for i in range(0, len(texts) - 2, 3)]


def _section_geometry(
    section: Mapping[str, Any],
    *,
    owner: str,
    advance: float,
    spans: Sequence[InkSpan] = (),
    unmatched: list[tuple[str, str]] | None = None,
    printed: Mapping[int, tuple[int, ...]] | None = None,
) -> AnnotationGeometry | None:
    """A section line: cutting line + arrows as ink, its two labels as text.

    ``IDrSection::GetLineInfo`` answers in the VIEW's model space, not the
    sheet's (cone-tip-block A-A: (0, -8)..(0, 8) mm for a line printed at
    x 72 mm), so the cutting line is drawn between the two arrows' tails,
    which ``GetArrowInfo`` gives in sheet space. ``GetTextInfo`` gives each
    label's UPPER-LEFT origin (types/IDrSection/GetTextInfo.md); the label's
    box is the PDF text object ``printed`` gives for it (label index -> spans,
    from the sheet's one joint assignment), else ``CharHeight`` estimated and
    the label counted in ``unmatched``.
    """
    segments = []
    arrows = _floats(section.get("arrows"))
    tails = []
    for i in range(0, len(arrows) - 5, 6):
        segments.append(Segment(arrows[i], arrows[i + 1], arrows[i + 3], arrows[i + 4], "arrow"))
        tails.append((arrows[i], arrows[i + 1]))
    if len(tails) == 2:
        segments.append(Segment(*tails[0], *tails[1], "line"))
    label = str(section.get("label") or "")
    rows = []
    for i, item in enumerate(_section_label_items(section)):
        chosen = (printed or {}).get(i)
        if spans and chosen is None and unmatched is not None:
            unmatched.append((f"section-line {label}", label))
        if chosen is not None:
            rows.append(_union(spans[index].box for index in chosen))
            continue
        width = advance * item.height * max(1, glyph_count(label))
        rows.append(Box(item.x, item.y, item.x + width, item.y + item.height))
    if not segments and not rows:
        return None
    return AnnotationGeometry(
        label=f"section-line {label}",
        kind="section-line",
        owner=owner,
        text_boxes=tuple(rows),
        segments=tuple(segments),
    )


def _detail_label_options(
    text_pt: tuple[float, float], height: float, spans: Sequence[InkSpan]
) -> list[tuple[tuple[int, ...], float]]:
    """The PDF text objects that may print a detail circle's label at
    ``text_pt``, as ``_assign_all`` options costed by distance.

    ``GetDetailCircleInfo2`` gives the label's position but not its letter, so
    the candidates are the short all-letter runs a label prints as, within
    the match window.
    """
    x, y = text_pt[0], text_pt[1] - height
    window = INK_MATCH_WINDOW_M + height
    return [
        ((index,), abs(span.box.xmin - x) + abs(span.box.ymin - y))
        for index, span in enumerate(spans)
        if 0 < len(span.key) <= 2 and span.key.isalpha()
        and abs(span.box.xmin - x) < window and abs(span.box.ymin - y) < window
    ]


def _detail_circles(info: Sequence[float]) -> list[tuple[tuple[float, float], ...]]:
    """``(center, start, end, text_pt, (height, 0))`` per circle of
    ``IView::GetDetailCircleInfo2``."""
    values = _floats(info)
    if not values:
        return []
    count = int(values[0])
    index = 1
    circles = []
    for _number in range(count):
        if index + 15 > len(values):
            break
        circles.append(
            (
                (values[index + 1], values[index + 2]),
                (values[index + 4], values[index + 5]),
                (values[index + 7], values[index + 8]),
                (values[index + 11], values[index + 12]),
                (values[index + 14], 0.0),
            )
        )
        index += 16 + int(values[index + 15]) * 9
    return circles


def _detail_circle_geometries(
    info: Sequence[float],
    *,
    owner: str,
    advance: float,
    spans: Sequence[InkSpan] = (),
    unmatched: list[tuple[str, str]] | None = None,
    printed: Mapping[int, tuple[int, ...]] | None = None,
) -> list[AnnotationGeometry]:
    """``IView::GetDetailCircleInfo2``: [n, (layer, center3, start3, end3,
    lineType, textPt3, textHeight, numArrows, (tip3, comp3, w, h, style)*)*].

    The label is boxed from the PDF text object ``printed`` gives for it
    (circle number -> span, from the sheet's one joint assignment over
    ``_detail_label_options``); else estimated and counted in ``unmatched``.
    """
    geometries = []
    for number, (center, start, end, text_pt, (height, _)) in enumerate(_detail_circles(info)):
        points = _arc_points(center, start, end, ccw=True)
        segments = tuple(
            Segment(a[0], a[1], b[0], b[1], "line") for a, b in zip(points, points[1:])
        )
        rows = ()
        label = f"detail-circle {owner} #{number + 1}"
        if height > 0.0:
            chosen = (printed or {}).get(number)
            if spans and chosen is None and unmatched is not None:
                unmatched.append((label, "label"))
            rows = (
                spans[chosen[0]].box
                if chosen is not None
                else Box(text_pt[0], text_pt[1] - height, text_pt[0] + advance * height, text_pt[1]),
            )
        geometries.append(
            AnnotationGeometry(
                label=label,
                kind="detail-circle",
                owner=owner,
                text_boxes=rows,
                segments=segments,
            )
        )
    return geometries


# --------------------------------------------------------------------------
# dump -> SheetGeometry
# --------------------------------------------------------------------------


def view_edges(
    edges: Sequence[Segment], outlines: Sequence[tuple[str, Box]], *, pad: float = 0.001
) -> dict[str, list[Segment]]:
    """Each printed model edge to the view whose outline holds it -- the
    smallest one, when a detail or section outline sits inside another."""
    owned: dict[str, list[Segment]] = {}
    ranked = sorted(outlines, key=lambda view: view[1].width * view[1].height)
    for edge in edges:
        x, y = (edge.x0 + edge.x1) / 2.0, (edge.y0 + edge.y1) / 2.0
        for name, box in ranked:
            if box.xmin - pad <= x <= box.xmax + pad and box.ymin - pad <= y <= box.ymax + pad:
                owned.setdefault(name, []).append(edge)
                break
    return owned


@dataclass(frozen=True)
class SheetModel:
    geometry: SheetGeometry
    advance: float
    unmatched: tuple[tuple[str, str], ...] = ()  # (annotation label, item text)
    unclaimed: tuple[tuple[str, Box], ...] = ()  # printed text no COM item claims
    edgeless: tuple[tuple[str, bool], ...] = ()  # (view, pictorial) with no model edge


def sheet_model(dump: Mapping[str, Any]) -> SheetModel:
    """Parse one sheet dump into the geometry every finder reads."""
    dump = printed_dump(dump)
    width, height = float(dump["width"]), float(dump["height"])
    zone = dump.get("zone") or {}
    if any(float(zone.get(side, 0.0) or 0.0) for side in ("left", "right", "bottom", "top")):
        region = DrawableRegion.from_margins(
            width,
            height,
            left=float(zone["left"]),
            right=float(zone["right"]),
            bottom=float(zone["bottom"]),
            top=float(zone["top"]),
        )
    else:
        region = DrawableRegion.whole_sheet(width, height)
    title = _floats(dump.get("title_block"))
    keep_outs = (("title-block", Box(*title[:4])),) if len(title) >= 4 else ()

    views = list(dump.get("views", ()))
    every_annotation = [
        annotation
        for view in views
        for annotation in view.get("annotations", ())
    ] + list(dump.get("sheet_annotations", ()))
    advance = calibrate_sheet_advance(every_annotation)
    audited = audited_annotations(dump)

    spans = ink_spans(dump)
    printed_page = "ink" in dump
    keyed = [
        ((id(annotation), index), item)
        for annotation in audited
        for index, item in enumerate(text_items(annotation.get("display") or {}))
    ]
    matchable = [(key, item) for key, item in keyed if ink_key(item.text)]
    if printed_page and matchable and not spans:
        raise ValueError(
            f"layout audit: sheet {dump.get('sheet')!r} has {len(matchable)} COM text item(s) "
            "but its PDF page has no text"
        )
    chosen_all = assign_sheet_text(dump, audited, spans)
    indices = {key: chosen for key, chosen in chosen_all.items() if not isinstance(key[0], str)}
    if spans and len(matchable) >= 5 and len(indices) < MIN_MATCH_SHARE * len(matchable):
        raise ValueError(
            f"layout audit: sheet {dump.get('sheet')!r}: only {len(indices)} of {len(matchable)} COM "
            "strings found their printed text; the PDF page does not line up with the sheet"
        )
    claimed = {index for chosen in chosen_all.values() for index in chosen}
    printed = {key: span_box(spans, chosen) for key, chosen in indices.items()}

    def ink_of(annotation: Mapping[str, Any]) -> dict[int, Box] | None:
        if not spans:
            return None
        return {index: box for (owner_id, index), box in printed.items() if owner_id == id(annotation)}

    unmatched = [
        (str(annotation.get("name", "")), item.text)
        for annotation in audited
        if spans
        for index, item in enumerate(text_items(annotation.get("display") or {}))
        if ink_key(item.text) and (id(annotation), index) not in printed
    ]
    outlines = [
        (str(view.get("name", "")), Box(*_floats(view.get("outline"))[:4]))
        for view in views
        if len(_floats(view.get("outline"))) >= 4
    ]
    edges = view_edges(ink_edges(dump), outlines)
    annotation_strokes = ink_annotation_strokes(dump)

    view_geometry = []
    annotations: list[AnnotationGeometry] = []
    for v, view in enumerate(views):
        name = str(view.get("name", ""))
        outline = _floats(view.get("outline"))
        view_geometry.append(
            ViewGeometry(
                name=name,
                outline=Box(*outline[:4]) if len(outline) >= 4 else None,
                pictorial=bool(view.get("pictorial")),
            )
        )
        for annotation in view.get("annotations", ()):
            item = annotation_geometry(
                annotation, owner=name, advance=advance, ink=ink_of(annotation), strokes=annotation_strokes
            )
            if item is not None:
                annotations.append(item)
        for s, section in enumerate(view.get("sections", ())):
            item = _section_geometry(
                section,
                owner=name,
                advance=advance,
                spans=spans,
                unmatched=unmatched,
                printed={key[3]: chosen for key, chosen in chosen_all.items() if key[:3] == ("section", v, s)},
            )
            if item is not None:
                annotations.append(item)
        annotations.extend(
            _detail_circle_geometries(
                view.get("detail_circles_info") or (),
                owner=name,
                advance=advance,
                spans=spans,
                unmatched=unmatched,
                printed={key[2]: chosen for key, chosen in chosen_all.items() if key[:2] == ("detail", v)},
            )
        )
        if edges.get(name):
            annotations.append(
                AnnotationGeometry(
                    label=f"view {name} geometry",
                    kind="geometry",
                    owner=name,
                    segments=tuple(edges[name]),
                )
            )
    for annotation in dump.get("sheet_annotations", ()):
        if int(annotation.get("owner_type", _OWNER_DRAWING_SHEET)) != _OWNER_DRAWING_SHEET:
            continue
        item = annotation_geometry(
            annotation, owner="sheet", advance=advance, ink=ink_of(annotation), strokes=annotation_strokes
        )
        if item is not None:
            annotations.append(item)
    for table in dump.get("tables", ()):
        box = _floats(table.get("box"))
        if len(box) >= 4:
            annotations.append(
                AnnotationGeometry(
                    label=f"table {table.get('name', '')}",
                    kind="table",
                    owner="sheet",
                    text_boxes=(Box(*box[:4]),),
                    exact=True,
                )
            )
    # Hidden Lines Visible edges print dashed: they are view geometry too, so
    # text over one is text on a line. Attributed like the solid edges, once
    # every annotation's own dashes are known.
    hidden = view_edges(_hidden_model_edges(ink_dashed_strokes(dump), annotations), outlines)
    for name, dashes in hidden.items():
        index = next(
            (i for i, a in enumerate(annotations) if a.kind == "geometry" and a.owner == name), None
        )
        if index is None:
            annotations.append(
                AnnotationGeometry(label=f"view {name} geometry", kind="geometry", owner=name, segments=tuple(dashes))
            )
            continue
        annotations[index] = replace(annotations[index], segments=(*annotations[index].segments, *dashes))
    geometry = SheetGeometry(
        name=str(dump.get("sheet", "")),
        width=width,
        height=height,
        region=region,
        keep_outs=keep_outs,
        views=tuple(view_geometry),
        annotations=tuple(annotations),
        advance_ratio=advance,
    )
    tables = [a.text_boxes[0] for a in annotations if a.kind == "table"]
    unclaimed = tuple(
        (span.key, span.box)
        for index, span in enumerate(spans)
        if index not in claimed and span.key and _stray_text(span.box, region, keep_outs, tables)
    )
    edgeless = tuple(
        (view.name, view.pictorial)
        for view in view_geometry
        if printed_page
        and view.outline is not None
        and not edges.get(view.name)
        and not hidden.get(view.name)
    )
    return SheetModel(geometry, advance, tuple(unmatched), unclaimed, edgeless)


def _stray_text(box: Box, region: DrawableRegion, keep_outs: Sequence[tuple[str, Box]], tables: Sequence[Box]) -> bool:
    """Printed text the audit should have a COM owner for: inside the drawable
    region (the zone labels print in the border band), and not in the title
    block or a table, whose text COM reports as a whole."""
    x, y = box.center()
    if not (region.xmin <= x <= region.xmax and region.ymin <= y <= region.ymax):
        return False
    for _name, keep_out in keep_outs:
        if keep_out.xmin <= x <= keep_out.xmax and keep_out.ymin <= y <= keep_out.ymax:
            return False
    return not any(t.xmin <= x <= t.xmax and t.ymin <= y <= t.ymax for t in tables)


# --------------------------------------------------------------------------
# finders the older audits lacked
# --------------------------------------------------------------------------


def _text_items(sheet: SheetGeometry) -> list[tuple[AnnotationGeometry, Box]]:
    return [
        (annotation, box)
        for annotation in sheet.annotations
        if annotation.kind != "geometry"
        for box in annotation.text_boxes
    ]


def _move_mm(box: Box, other: Box) -> tuple[float, float]:
    depth_x, depth_y = box.penetration(other)
    moves = {
        (-(depth_x + 0.002), 0.0): depth_x,
        (depth_x + 0.002, 0.0): depth_x,
        (0.0, -(depth_y + 0.002)): depth_y,
        (0.0, depth_y + 0.002): depth_y,
    }
    dx, dy = min(moves, key=lambda move: moves[move])
    x, y = box.center()
    return ((x + dx) * MM, (y + dy) * MM)


def _shape_gap(first: AnnotationGeometry, a: Box, second: AnnotationGeometry, b: Box) -> float:
    """``_box_gap`` between two text blocks, measured to a balloon's circle.

    A balloon's block is its circle's bounding square; two balloons set
    diagonally have square corners 2 mm apart and circles 7 mm apart.
    """
    if first.circle is None and second.circle is None:
        return _box_gap(a, b)
    if first.circle is not None and second.circle is not None:
        (x0, y0, r0), (x1, y1, r1) = first.circle, second.circle
        return math.hypot(x1 - x0, y1 - y0) - r0 - r1
    circle, box = (first.circle, b) if first.circle is not None else (second.circle, a)
    cx, cy, radius = circle
    return math.hypot(max(box.xmin - cx, 0.0, cx - box.xmax), max(box.ymin - cy, 0.0, cy - box.ymax)) - radius


def _box_gap(a: Box, b: Box) -> float:
    """Signed clearance: the largest separating gap, negative when overlapping."""
    return max(a.xmin - b.xmax, b.xmin - a.xmax, a.ymin - b.ymax, b.ymin - a.ymax)


def find_text_clearance(
    sheet: SheetGeometry, *, heights: float = TEXT_CLEARANCE_HEIGHTS
) -> list[Finding]:
    """Text of two DISTINCT annotations closer than a word space -- or overlapping.

    The clearance is ``heights`` x the smaller row height. Two tables are
    exempt from each other only because a split table's pieces abut by design;
    a table's box is its whole grid, so its height is not a text height and the
    other row's height sets the clearance.
    """
    findings = []
    for (first, box_a), (second, box_b) in combinations(_text_items(sheet), 2):
        if first.label == second.label:
            continue
        if first.kind == second.kind == "table":
            continue
        rows = [text_height(item) for item in (first, second) if item.kind != "table"]
        clearance = heights * min(rows)
        gap = _shape_gap(first, box_a, second, box_b)
        if gap >= clearance:
            continue
        overlap = Box(
            max(box_a.xmin, box_b.xmin),
            max(box_a.ymin, box_b.ymin),
            min(box_a.xmax, box_b.xmax),
            min(box_a.ymax, box_b.ymax),
        ).center()
        findings.append(
            Finding(
                kind="text-clearance",
                sheet=sheet.name,
                a=first.label,
                b=second.label,
                detail=(
                    f"text of {first.label!r} {box_a.format_mm()} and "
                    f"{second.label!r} {box_b.format_mm()} are "
                    + (
                        f"{-gap * MM:.2f}mm overlapped"
                        if gap < 0
                        else f"only {gap * MM:.2f}mm apart"
                    )
                    + f" (needs {clearance * MM:.2f}mm of air)"
                ),
                at_mm=(overlap[0] * MM, overlap[1] * MM),
                move_target_mm=_move_mm(box_a, box_b),
                extra={"gap_mm": gap * MM},
            )
        )
    return findings


def find_text_separation(
    sheet: SheetGeometry, *, heights: float = TEXT_SEPARATION_HEIGHTS
) -> list[Finding]:
    """Clear text blocks of distinct annotations still close enough to read as one.

    ADVISORY: the gap is at least the near-contact clearance but under
    ``heights`` x the smaller text height. Measured on WHOLE blocks (the union
    of an annotation's rows), not rows, because the question is whether two
    callouts read as one.
    """
    blocks = []
    for annotation in sheet.annotations:
        if annotation.kind in ("geometry", "table") or not annotation.text_boxes:
            continue
        block = annotation.text_boxes[0]
        for box in annotation.text_boxes[1:]:
            block = block.union(box)
        row_height = text_height(annotation)
        blocks.append((annotation, block, row_height))
    findings = []
    for (first, a, ha), (second, b, hb) in combinations(blocks, 2):
        gap = _shape_gap(first, a, second, b)
        limit = heights * min(ha, hb)
        if gap < TEXT_CLEARANCE_HEIGHTS * min(ha, hb) or gap >= limit:
            continue
        findings.append(
            Finding(
                kind="text-separation",
                sheet=sheet.name,
                a=first.label,
                b=second.label,
                detail=(
                    f"{first.label!r} {a.format_mm()} and {second.label!r} "
                    f"{b.format_mm()} are {gap * MM:.2f}mm apart, under "
                    f"{limit * MM:.2f}mm: they read as one callout"
                ),
                at_mm=tuple(value * MM for value in a.center()),
                extra={"gap_mm": gap * MM, "limit_mm": limit * MM},
            )
        )
    return findings


def _callout_blocks(sheet: SheetGeometry) -> list[tuple[AnnotationGeometry, Box, float]]:
    """Each CALLOUT's whole text block and its text height.

    A callout is a hole callout or a leadered note. Free notes (view labels,
    general notes) are not callouts, balloons are circles, and plain
    dimensions stack in ladders at dimension-line spacing, which the
    clearance rule already covers.
    """
    blocks = []
    for annotation in sheet.annotations:
        if not annotation.text_boxes:
            continue
        leadered_note = annotation.kind == "note" and annotation.leader_segments()
        if annotation.kind != "hole-callout" and not leadered_note:
            continue
        block = annotation.text_boxes[0]
        for box in annotation.text_boxes[1:]:
            block = block.union(box)
        blocks.append((annotation, block, text_height(annotation)))
    return blocks


def find_merged_blocks(
    sheet: SheetGeometry, *, pitch_heights: float = ROW_PITCH_HEIGHTS
) -> list[Finding]:
    """Two callout blocks in one column, closer than a row pitch: they read as one."""
    findings = []
    for (first, a, ha), (second, b, hb) in combinations(_callout_blocks(sheet), 2):
        if first.label == second.label:
            continue
        if min(a.xmax, b.xmax) <= max(a.xmin, b.xmin):
            continue  # side by side, not stacked
        gap = max(a.ymin - b.ymax, b.ymin - a.ymax)
        limit = pitch_heights * min(ha, hb)
        if gap >= limit:
            continue
        findings.append(
            Finding(
                kind="merged-blocks",
                sheet=sheet.name,
                a=first.label,
                b=second.label,
                detail=(
                    f"{first.label!r} {a.format_mm()} and {second.label!r} "
                    f"{b.format_mm()} are stacked {gap * MM:.2f}mm apart, under "
                    f"the {limit * MM:.2f}mm row pitch: they read as one block"
                ),
                at_mm=tuple(value * MM for value in a.center()),
                extra={"gap_mm": gap * MM, "limit_mm": limit * MM},
            )
        )
    return findings


def find_tall_blocks(dump: Mapping[str, Any], *, limit: int = TEXT_ROW_LIMIT) -> list[Finding]:
    """Every CALLOUT -- hole callout or leadered note -- whose text runs over
    ``limit`` rows.

    Supports' rule is about callouts (``find_tall_callouts``): a block at the
    end of a leader stops reading as one label. A free general note (a
    process paragraph) is a text block by design, like ``_callout_blocks``.
    """
    owned = [
        (str(view.get("name", "")), annotation)
        for view in dump.get("views", ())
        for annotation in view.get("annotations", ())
    ] + [
        ("sheet", annotation)
        for annotation in dump.get("sheet_annotations", ())
        if int(annotation.get("owner_type", _OWNER_DRAWING_SHEET)) == _OWNER_DRAWING_SHEET
    ]
    findings = []
    for owner, annotation in owned:
        kind = ANNOTATION_KINDS.get(int(annotation.get("type", 0)), "other")
        note = annotation.get("note") or {}
        hole_callout = bool((annotation.get("dim") or {}).get("hole_callout"))
        leadered_note = kind == "note" and not note.get("balloon") and bool(annotation.get("leaders"))
        if not leadered_note and not hole_callout:
            continue
        if int(annotation.get("visible", 1) or 1) in _HIDDEN_STATES:
            continue
        items = text_items(annotation.get("display") or {})
        if items:
            rows = [" ".join(item.text.strip() for item in row) for row in group_rows(items)]
        else:
            rows = [line for line in str(note.get("text", "")).splitlines() if line.strip()]
        if len(rows) <= limit:
            continue
        label = f"{'hole-callout' if hole_callout else kind} {annotation.get('name') or kind}"
        position = _floats(annotation.get("pos"))
        findings.append(
            Finding(
                kind="tall-block",
                sheet=str(dump.get("sheet", "")),
                a=label,
                b=owner,
                detail=f"{label!r} runs {len(rows)} rows, over the {limit}-row limit: {rows[0]!r} ...",
                at_mm=(position[0] * MM, position[1] * MM) if len(position) >= 2 else None,
                extra={"rows": len(rows)},
            )
        )
    return findings


def find_leader_through_text(
    sheet: SheetGeometry,
    *,
    tol: float = DEFAULT_TEXT_TOUCH_TOL_M,
    own_inset: float = OWN_ROW_INSET_M,
) -> list[Finding]:
    """A leader running through another annotation's text, or its own rows.

    Its own rows are shrunk by ``own_inset`` so the joint where the leader
    leaves the shoulder's end (touching the row's corner) is not reported.
    """
    findings = []
    items = _text_items(sheet)
    for source in sheet.annotations:
        leaders = [s for s in source.segments if s.role == "leader"]
        if not leaders:
            continue
        for target, box in items:
            own = target.label == source.label
            for segment in leaders:
                length, span = text_overlap(segment, target, box, inset=own_inset if own else 0.0)
                if length <= tol:
                    continue
                mid = segment.point_at(sum(span) / 2.0) if span else box.center()
                findings.append(
                    Finding(
                        kind="leader-through-own-text" if own else "leader-through-text",
                        sheet=sheet.name,
                        a=source.label,
                        b=target.label,
                        detail=(
                            f"leader of {source.label!r} {segment.format_mm()} runs "
                            f"{length * MM:.2f}mm through "
                            + ("its own text " if own else f"the text of {target.label!r} ")
                            + box.format_mm()
                        ),
                        at_mm=(mid[0] * MM, mid[1] * MM),
                        extra={"overlap_mm": length * MM},
                    )
                )
                break
    return findings


def find_lines_through_own_text(
    sheet: SheetGeometry, *, tol: float = DEFAULT_TEXT_TOUCH_TOL_M, inset: float = OWN_ROW_INSET_M
) -> list[Finding]:
    """A dimension's own extension or dimension line struck through its own text.

    ``text-on-line`` skips an annotation's own ink, so text parked across its
    own witness line went unreported: MHA-014's "10.781", pushed outside its
    extension lines, printed with the collar-face witness through "0" and "7"
    (conegear, #916 388d1e3fb). Its own dimension line through its text had
    no finder either (Main's gate-gap sweep). The rows are shrunk by
    ``inset`` so a line that only touches a row's corner, or runs along the
    baseline the text sits on, is not reported.
    """
    findings = []
    for annotation in sheet.annotations:
        for role, (kind, what) in _OWN_LINE_KINDS.items():
            lines = [s for s in annotation.segments if s.role == role]
            for box in annotation.text_boxes if lines else ():
                for segment in lines:
                    length, span = text_overlap(segment, annotation, box, inset=inset)
                    if length <= tol:
                        continue
                    mid = segment.point_at(sum(span) / 2.0) if span else box.center()
                    findings.append(
                        Finding(
                            kind=kind,
                            sheet=sheet.name,
                            a=annotation.label,
                            b=annotation.label,
                            detail=(
                                f"{what} of {annotation.label!r} {segment.format_mm()} runs "
                                f"{length * MM:.2f}mm through its own text {box.format_mm()}"
                            ),
                            at_mm=(mid[0] * MM, mid[1] * MM),
                            extra={"overlap_mm": length * MM},
                        )
                    )
                    break
    return findings


# A dimension's own lines, by role, that must not strike its own text.
_OWN_LINE_KINDS = {
    "ext-line": ("extension-through-own-text", "extension line"),
    "dim-line": ("dim-line-through-own-text", "dimension line"),
}


def _past_arrow_zones(annotation: AnnotationGeometry) -> list[tuple[tuple[float, float], float]]:
    """``(end, radius)`` for each leader run that continues past its arrowhead.

    A hole callout's leader can run on from the arrow tip on the hole's edge
    to the hole's centre (cone-swing-platform's 6.76 and 5.11 callouts). A
    line crossing that stretch -- the hole's own centre or extension line --
    crosses inside the feature the arrow points at, not across the sheet. The
    arrow end of a run is the free end nearer its arrowhead than its text;
    the zone is that end's distance to the nearest arrowhead vertex (the tip).
    """
    leaders = [s for s in annotation.segments if s.role == "leader"]
    arrows = [(s.x0, s.y0) for s in annotation.segments if s.role == "arrow"]
    if not leaders or not arrows:
        return []
    ends: dict[tuple[float, float], int] = {}
    for segment in leaders:
        for point in ((segment.x0, segment.y0), (segment.x1, segment.y1)):
            key = (round(point[0], 5), round(point[1], 5))
            ends[key] = ends.get(key, 0) + 1
    zones = []
    for end, degree in ends.items():
        if degree != 1:
            continue
        to_arrow = min(math.hypot(x - end[0], y - end[1]) for x, y in arrows)
        to_text = min(
            (math.hypot(max(b.xmin - end[0], 0.0, end[0] - b.xmax), max(b.ymin - end[1], 0.0, end[1] - b.ymax))
             for b in annotation.text_boxes),
            default=math.inf,
        )
        if to_arrow < to_text:
            zones.append((end, to_arrow + 1e-4))
    return zones


def _converging(point: tuple[float, float], landings: Sequence[tuple[float, float]], line: Segment) -> bool:
    """The crossing lies within ``LANDING_CONVERGE_M`` of both the leader's
    landing and an end of the line it crosses: two leaders closing on one
    corner, not a leader cutting across a dimension."""
    near_landing = any(math.hypot(point[0] - x, point[1] - y) <= LANDING_CONVERGE_M for x, y in landings)
    near_end = min(
        math.hypot(point[0] - line.x0, point[1] - line.y0), math.hypot(point[0] - line.x1, point[1] - line.y1)
    ) <= LANDING_CONVERGE_M
    return near_landing and near_end


def find_leader_across_lines(sheet: SheetGeometry) -> list[Finding]:
    """A leader or callout shoulder transversally crossing another annotation's
    dimension/witness line.

    Rule 8: no leader crosses a dimension line. A callout's shoulder is its
    leader's last run under the text: MHA-092's 5.56 heel-height line crossed
    the ADJUSTER callout's shoulder (swing's gap diff, class d). Touches (a
    leader landing ON a line) are not crossings -- see
    ``_drawing_layout_check._proper_crossing``.

    Targets are dimension, extension and frame lines (Main's ruling a) and
    section cutting lines (``leader-crosses-section-line``, gating: the MHA-025
    finish leader was moved off its A-A line for this). A detail circle is no
    target: a leader to a feature inside it must cross it. A crossing on the
    stretch a leader runs past its arrow tip is inside the feature it points
    at (``_past_arrow_zones``). A crossing within ``LANDING_CONVERGE_M`` of
    both the leader's landing and the crossed line's end is two leaders
    closing on one corner: advisory ``leader-converges-at-landing``.
    """
    findings = []
    zones = {annotation.label: _past_arrow_zones(annotation) for annotation in sheet.annotations}
    landings = {label: [end for end, _radius in found] for label, found in zones.items()}
    leaders = [
        (annotation, segment)
        for annotation in sheet.annotations
        for segment in annotation.segments
        if segment.role in ("leader", "shoulder")
    ]
    lines = [
        (annotation, segment)
        for annotation in sheet.annotations
        if annotation.kind not in _NOT_CROSSING_TARGETS and annotation.kind not in _MARK_KINDS
        for segment in annotation.segments
        if segment.role in LINE_ROLES
    ]
    seen = set()
    for source, leader in leaders:
        for target, line in lines:
            # One crossing per line of the pair (audit_dump keeps one per
            # pair and kind): the dedupe against text-on-line needs to see
            # each line that crosses.
            key = (source.label, target.label, (line.x0, line.y0, line.x1, line.y1))
            if target.label == source.label or key in seen:
                continue
            point = _proper_crossing(
                LeaderSegment(source.label, source.kind, leader.x0, leader.y0, leader.x1, leader.y1),
                LeaderSegment(target.label, target.kind, line.x0, line.y0, line.x1, line.y1),
                tol=1e-4,
            )
            if point is None:
                continue
            if any(math.hypot(point[0] - end[0], point[1] - end[1]) <= radius for end, radius in zones[source.label]):
                continue
            kind = "shoulder-crosses-line" if leader.role == "shoulder" else "leader-crosses-line"
            if target.kind == "section-line":
                kind = "leader-crosses-section-line"
            elif _converging(point, landings[source.label], line):
                kind = "leader-converges-at-landing"
            if kind != "leader-converges-at-landing":
                seen.add(key)
            findings.append(
                Finding(
                    kind=kind,
                    sheet=sheet.name,
                    a=source.label,
                    b=target.label,
                    detail=(
                        f"{leader.role} of {source.label!r} {leader.format_mm()} crosses "
                        f"{target.label!r}'s line {line.format_mm()}"
                    ),
                    at_mm=(point[0] * MM, point[1] * MM),
                    extra={"line": (line.x0, line.y0, line.x1, line.y1)},
                )
            )
    return findings


def _arrow_heads(annotation: AnnotationGeometry) -> list[tuple[tuple[float, float], ...]]:
    """The vertices of each arrowhead or triangle an annotation drew: its
    ``arrow`` segments come three to a head (``arrowhead_segments``,
    ``triangle_segments``)."""
    arrows = [s for s in annotation.segments if s.role == "arrow"]
    return [
        tuple((s.x0, s.y0) for s in arrows[i : i + 3])
        for i in range(0, len(arrows) - 2, 3)
    ]


def _segment_crossing(a: Segment, b: Segment) -> tuple[float, float] | None:
    """Where ``a`` meets ``b``, ends included; None when they miss or run
    parallel. A model edge is a chain of short pieces (an arc flattens to
    ~0.35 mm ones), so a leader through a joint meets both pieces and the
    caller merges the two points."""
    rx, ry = a.x1 - a.x0, a.y1 - a.y0
    sx, sy = b.x1 - b.x0, b.y1 - b.y0
    denom = rx * sy - ry * sx
    if denom == 0.0:
        return None
    qx, qy = b.x0 - a.x0, b.y0 - a.y0
    t = (qx * sy - qy * sx) / denom
    u = (qx * ry - qy * rx) / denom
    if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
        return None
    return a.point_at(t)


def _leader_paths(annotation: AnnotationGeometry) -> list[tuple[list[tuple[float, float]], float]]:
    """Each leader run from its text end to an arrow tip, as
    ``(points from the text end to the tip, arrowhead length)``.

    The leader and shoulder pieces form a small graph. A tip is a node an
    arrowhead's vertex sits on; the text end is the node nearest the
    annotation's text (its attachment, or a shoulder under the text), so a
    branch never runs on into a sibling leader. A run past the arrow tip (a
    hole callout's run on to the hole's centre) is not on that path.
    """
    runs = [s for s in annotation.segments if s.role in ("leader", "shoulder") and s.length > 0.0]
    heads = _arrow_heads(annotation)
    if not runs or not heads:
        return []
    nodes: list[tuple[float, float]] = []

    def node(point: tuple[float, float]) -> int:
        for index, (x, y) in enumerate(nodes):
            if math.hypot(point[0] - x, point[1] - y) <= COLLINEAR_TOL_M:
                return index
        nodes.append(point)
        return len(nodes) - 1

    edges: dict[int, list[tuple[int, Segment]]] = {}
    for segment in runs:
        a, b = node((segment.x0, segment.y0)), node((segment.x1, segment.y1))
        edges.setdefault(a, []).append((b, segment))
        edges.setdefault(b, []).append((a, segment))
    tips = []
    for vertices in heads:
        for k, vertex in enumerate(vertices):
            hit = next(
                (i for i, (x, y) in enumerate(nodes) if math.hypot(vertex[0] - x, vertex[1] - y) <= COLLINEAR_TOL_M),
                None,
            )
            if hit is None:
                continue
            others = [v for j, v in enumerate(vertices) if j != k]
            base = (sum(v[0] for v in others) / len(others), sum(v[1] for v in others) / len(others))
            tips.append((hit, math.hypot(base[0] - nodes[hit][0], base[1] - nodes[hit][1])))
            break
    paths = []
    tip_nodes = {hit for hit, _length in tips}
    for tip, head in tips:
        distance = {tip: 0.0}
        back: dict[int, tuple[int, Segment]] = {}
        queue = [(0.0, tip)]
        while queue:
            here, at = heappop(queue)
            if here > distance[at]:
                continue
            for to, segment in edges.get(at, ()):
                there = here + segment.length
                if there < distance.get(to, math.inf):
                    distance[to] = there
                    back[to] = (at, segment)
                    heappush(queue, (there, to))
        ends = [i for i in distance if i not in tip_nodes]
        if not ends:
            continue
        # The walk stops at this leader's own attachment: the node nearest
        # the annotation's text, the nearer along the leader on a tie. The
        # farthest node could be a sibling leader's elbow, reached through a
        # shared attach point (Codex P2 on b49e13940).
        at = min(
            ends,
            key=lambda i: (
                round(min((_point_box_distance(nodes[i], box) for box in annotation.text_boxes), default=-distance[i]), 6),
                distance[i],
            ),
        )
        points = [nodes[at]]
        while at != tip:
            at, _segment = back[at]
            points.append(nodes[at])
        paths.append((points, head))
    return paths


def find_leaders_over_part(
    sheet: SheetGeometry,
    *,
    detour_limit: float = LEADER_DETOUR_PROVISIONAL_M,
    limit: float = LEADER_OVER_PART_M,
) -> list[Finding]:
    """A leader running over the part much further than its feature needs.

    ``leader-over-part`` (gating): the run over the part exceeds the tip's
    shortest approach from outside (its distance to the view's printed-edge
    box) by more than ``detour_limit``. ``leader-over-part-direct``
    (advisory): no such detour, but a run over ``limit`` (a bore in the
    middle of a gear has no shorter route).

    swing's 917-s1 sheet 2 eye pass: cone-swing-platform's RD2 leader crossed
    the plate's tapered edge and ran 28.2 mm over the plate to its hole, where
    it reads as an edge of the part. Measured along the leader from its first
    crossing of a printed model edge (walking from the text) to its arrow tip,
    against the edges of the leader's own view (every view's, for a sheet
    annotation). Crossings under the arrowhead are the landing, not the route
    (RD2 lands on a countersink's inner ring, 0.37 mm inside the outer one).
    A balloon, and any leader in a pictorial view, is skipped: an assembly
    balloon reaches its part across the parts in front of it
    (drive-train-assembly's exploded views, layoutcal2-c).

    The finding carries how many model edges the leader crossed. Crossing
    more than one is not a finding of its own: neither swing's evidence nor
    the layoutcal2/c2 replay has a part sheet where it is the defect (the only
    hits were assembly balloons), and no gate goes in without a positive case
    (Main's ruling).
    """
    pictorial = {view.name for view in sheet.views if view.pictorial}
    edges_of: dict[str, list[Segment]] = {}
    for annotation in sheet.annotations:
        if annotation.kind == "geometry" and annotation.owner not in pictorial:
            edges_of.setdefault(annotation.owner, []).extend(s for s in annotation.segments if s.role == "geometry")
    grids = {owner: SegmentGrid(list(enumerate(edges))) for owner, edges in edges_of.items()}
    boxes = {
        owner: Box.from_points([p for s in edges for p in ((s.x0, s.y0), (s.x1, s.y1))])
        for owner, edges in edges_of.items()
    }
    every = SegmentGrid(list(enumerate(edge for edges in edges_of.values() for edge in edges)))

    def approach(tip: tuple[float, float], owner: str) -> float:
        """The tip's distance to the nearest side of its view's edge box: a
        sheet annotation's view is the smallest box holding the tip."""
        holding = [boxes[owner]] if owner in boxes else sorted(
            (b for b in boxes.values() if b.xmin <= tip[0] <= b.xmax and b.ymin <= tip[1] <= b.ymax),
            key=lambda b: b.width * b.height,
        )[:1]
        if not holding:
            return 0.0
        [box] = holding
        return max(0.0, min(tip[0] - box.xmin, box.xmax - tip[0], tip[1] - box.ymin, box.ymax - tip[1]))

    findings = []
    for annotation in sheet.annotations:
        if annotation.kind in _UNLEADERED_KINDS or annotation.kind == "balloon":
            continue
        grid = every if annotation.owner == "sheet" else grids.get(annotation.owner)
        if grid is None:
            continue
        # The most severe branch: a gating detour first, then a long direct run.
        worst: tuple[tuple[int, float], float, float, int, tuple[float, float]] | None = None
        for points, head in _leader_paths(annotation):
            pieces = [Segment(*a, *b, "leader") for a, b in zip(points, points[1:])]
            remaining = sum(piece.length for piece in pieces)
            crossings: list[tuple[float, tuple[float, float]]] = []
            for piece in pieces:
                # Each piece runs from the text end toward the tip.
                for _index, edge in grid.near(piece.box()):
                    point = _segment_crossing(piece, edge)
                    if point is None:
                        continue
                    to_tip = remaining - math.hypot(point[0] - piece.x0, point[1] - piece.y0)
                    if to_tip > head:
                        crossings.append((to_tip, point))
                remaining -= piece.length
            crossings.sort(reverse=True)
            merged = [c for i, c in enumerate(crossings) if i == 0 or crossings[i - 1][0] - c[0] > MODEL_EDGE_WIDTH_M[1]]
            if not merged:
                continue
            over = merged[0][0]
            detour = over - approach(points[-1], annotation.owner)
            rank = (2 if detour > detour_limit else 1 if over > limit else 0, detour)
            if worst is None or rank > worst[0]:
                worst = (rank, over, detour, len(merged), merged[0][1])
        if worst is None or worst[0][0] == 0:
            continue
        (level, _detour), over, detour, count, point = worst
        kind = "leader-over-part" if level == 2 else "leader-over-part-direct"
        findings.append(
            Finding(
                kind=kind,
                sheet=sheet.name,
                a=annotation.label,
                b=f"view {annotation.owner}",
                detail=(
                    f"leader of {annotation.label!r} crosses a model edge at "
                    f"({point[0] * MM:.1f},{point[1] * MM:.1f})mm and runs {over * MM:.1f}mm over the part "
                    f"to its arrow, {detour * MM:.1f}mm further than its feature's shortest approach "
                    f"(detour limit {detour_limit * MM:.0f}mm), crossing {count} model edge(s)"
                ),
                at_mm=(point[0] * MM, point[1] * MM),
                extra={"over_part_mm": over * MM, "detour_mm": detour * MM, "edge_crossings": count},
            )
        )
    return findings


def _callout_text(annotation: Mapping[str, Any]) -> str:
    """What a callout prints: its display-data rows, else its note text (a
    cosmetic-thread callout dumps no display data)."""
    items = [str(item.get("t", "")) for item in (annotation.get("display") or {}).get("texts", ())]
    text = "\n".join(items) if any(t.strip() for t in items) else str((annotation.get("note") or {}).get("text", ""))
    return _TOKEN.sub(" ", text)


@dataclass(frozen=True)
class PrintedHole:
    """A circle printed in a view: its centre and its concentric rings' radii
    (a countersink prints two), smallest first."""

    center: tuple[float, float]
    radii: tuple[float, ...]

    def same_size(self, other: PrintedHole) -> bool:
        return len(self.radii) == len(other.radii) and all(
            abs(a - b) <= HOLE_RADIUS_TOL_M for a, b in zip(self.radii, other.radii)
        )


def printed_holes(edges: Sequence[Segment]) -> list[PrintedHole]:
    """The circles a view's printed model ``edges`` draw, concentric rings
    grouped into one hole.

    Pieces sharing an end point form a chain; a chain whose vertices all lie
    within ``BALLOON_RING_FIT_TOL_M`` of one circle is an arc of it. Arcs of
    one circle (a circle printed as two paths) pool; a circle is kept once
    its arcs reach every side of the centre. A slot or a filleted corner
    chains its arcs to straight edges, fits no circle and is not a hole.
    """
    parent = list(range(len(edges)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first: dict[tuple[int, int], int] = {}
    for index, edge in enumerate(edges):
        for x, y in ((edge.x0, edge.y0), (edge.x1, edge.y1)):
            other = first.setdefault((round(x / RING_JOIN_M), round(y / RING_JOIN_M)), index)
            parent[find(index)] = find(other)
    chains: dict[int, set[tuple[float, float]]] = {}
    for index, edge in enumerate(edges):
        chains.setdefault(find(index), set()).update(((edge.x0, edge.y0), (edge.x1, edge.y1)))
    arcs: list[tuple[float, float, float, set[tuple[bool, bool]]]] = []
    for points in chains.values():
        if len(points) < 6:
            continue
        fit = _fit_circle(list(points))
        if fit is None:
            continue
        fx, fy, fr = fit
        if max(abs(math.hypot(x - fx, y - fy) - fr) for x, y in points) > BALLOON_RING_FIT_TOL_M:
            continue
        sides = {(x >= fx, y >= fy) for x, y in points}
        same = next(
            (
                arc
                for arc in arcs
                if math.hypot(arc[0] - fx, arc[1] - fy) <= HOLE_CENTER_TOL_M and abs(arc[2] - fr) <= HOLE_RADIUS_TOL_M
            ),
            None,
        )
        if same is None:
            arcs.append((fx, fy, fr, sides))
            continue
        same[3].update(sides)
    holes: list[tuple[tuple[float, float], list[float]]] = []
    for cx, cy, radius, sides in arcs:
        if len(sides) < 4:
            continue
        hole = next((h for h in holes if math.hypot(h[0][0] - cx, h[0][1] - cy) <= HOLE_CENTER_TOL_M), None)
        if hole is None:
            holes.append(((cx, cy), [radius]))
            continue
        hole[1].append(radius)
    return [PrintedHole(center, tuple(sorted(radii))) for center, radii in holes]


def _landings(annotation: Mapping[str, Any]) -> list[tuple[float, float]]:
    """Where an annotation's leaders end: its arrow tips, else the last
    point of each COM leader (a cosmetic-thread callout dumps no display
    data, DetailItem357)."""
    arrows = (annotation.get("display") or {}).get("arrows") or ()
    tips = [(float(arrow[0]), float(arrow[1])) for arrow in arrows if len(arrow) >= 2]
    if tips:
        return tips
    return [(float(leader[-3]), float(leader[-2])) for leader in annotation.get("leaders") or () if len(leader) >= 3]


def _landed_hole(point: tuple[float, float], holes: Sequence[PrintedHole]) -> int | None:
    """The hole whose ring ``point`` lies on, the nearest ring's; None off
    every ring."""
    best = min(
        (
            (abs(math.hypot(point[0] - hole.center[0], point[1] - hole.center[1]) - radius), index)
            for index, hole in enumerate(holes)
            for radius in hole.radii
        ),
        default=None,
    )
    if best is None or best[0] > HOLE_LANDING_TOL_M:
        return None
    return best[1]


def find_duplicate_thread_callouts(dump: Mapping[str, Any], sheet: SheetGeometry) -> list[Finding]:
    """A leadered note restating the thread of the hole group a hole callout
    in its view already calls out.

    swing's 917-s1 sheet 2 eye pass: the model's cosmetic-thread callout
    "1/4-20 Tapped Hole" printed beside RD2's "2X <MOD-DIAM> 5.11 THRU ALL /
    1/4-20 UNC - 2B THRU ALL", its leader on the other hole of RD2's pair.
    A note without a leader ("1/4-20 TAPPED HOLES: DEBURR ONLY") calls out
    no hole, and two hole callouts naming one thread are two hole groups
    (harmonic-base's "2X ... 19.50" and "4X ... 15.00", both 8-32).

    One thread is not one group: a view can hold two groups of one thread
    (Codex P2 on b49e13940, PRRT_kwDOPHDy386mTAro). The dump records no
    leader's attached entity, so the two are associated by where their
    leaders land on the view's printed holes (``printed_holes``). They call
    out one group when both land on the same hole, or when the callout's
    "NX" names exactly the holes the view prints at the size both land on.
    A leader landing on no printed ring associates nothing: no finding.
    """
    owners = [(str(view.get("name", "")), view.get("annotations") or ()) for view in dump.get("views", ())]
    owners.append(
        (
            "sheet",
            [
                annotation
                for annotation in dump.get("sheet_annotations") or ()
                if int(annotation.get("owner_type", _OWNER_DRAWING_SHEET)) == _OWNER_DRAWING_SHEET
            ],
        )
    )
    edges_of: dict[str, list[Segment]] = {}
    for annotation in sheet.annotations:
        if annotation.kind == "geometry":
            edges_of.setdefault(annotation.owner, []).extend(s for s in annotation.segments if s.role == "geometry")
    holes_of: dict[str, list[PrintedHole]] = {}

    def holes(view: str) -> list[PrintedHole]:
        if view not in holes_of:
            holes_of[view] = printed_holes(edges_of.get(view, ()))
        return holes_of[view]

    def landed(annotation: Mapping[str, Any], owner: str) -> set[tuple[str, int]]:
        """The (view, hole) pairs an annotation's leaders land on; a sheet
        annotation's may be in any view."""
        views = sorted(edges_of) if owner == "sheet" else [owner]
        return {
            (view, index)
            for point in _landings(annotation)
            for view in views
            if (index := _landed_hole(point, holes(view))) is not None
        }

    def one_group(note: Mapping[str, Any], callout: Mapping[str, Any], owner: str) -> str | None:
        ours, theirs = landed(note, owner), landed(callout, owner)
        if ours & theirs:
            return "same hole"
        count = _INSTANCES.match(_callout_text(callout))
        if count is None:
            return None
        instances = int(count.group(1))
        for (view, mine), (their_view, other) in product(ours, theirs):
            printed = holes(view)
            if view != their_view or not printed[mine].same_size(printed[other]):
                continue
            if sum(hole.same_size(printed[other]) for hole in printed) == instances:
                return f"same {instances}X group"
        return None

    def threads(annotation: Mapping[str, Any]) -> list[str]:
        return list(dict.fromkeys(m.group(1).upper() for m in _THREAD.finditer(_callout_text(annotation))))

    findings = []
    for owner, members in owners:
        shown = [annotation for annotation in members if not is_hidden(annotation)]
        callouts = [a for a in shown if (a.get("dim") or {}).get("hole_callout")]
        notes = [
            a
            for a in shown
            if ANNOTATION_KINDS.get(int(a.get("type", 0))) == "note"
            and a.get("leaders")
            and not (a.get("note") or {}).get("balloon")
        ]
        for note, callout in product(notes, callouts):
            shared = [t for t in threads(note) if t in threads(callout)]
            group = one_group(note, callout, owner) if shared else None
            if group is None:
                continue
            findings.extend(
                Finding(
                    kind="duplicate-thread-callout",
                    sheet=str(dump.get("sheet", "")),
                    a=f"hole-callout {callout.get('name', '')}",
                    b=f"note {note.get('name', '')}",
                    detail=(
                        f"note {note.get('name', '')!r} in {owner!r} calls out thread {thread} on the "
                        f"{group} hole callout {callout.get('name', '')!r} already calls out: one feature, "
                        "called out twice"
                    ),
                    extra={"owner": owner, "thread": thread, "association": group},
                )
                for thread in shared
            )
    return findings


def _point_box_distance(point: tuple[float, float], box: Box) -> float:
    dx = max(box.xmin - point[0], 0.0, point[0] - box.xmax)
    dy = max(box.ymin - point[1], 0.0, point[1] - box.ymax)
    return math.hypot(dx, dy)


def find_dimension_line_crossings(
    sheet: SheetGeometry, *, heights: float = DIM_CROSSING_TEXT_HEIGHTS
) -> list[Finding]:
    """A dimension line crossing ANOTHER dimension's extension line.

    Main's ruling b: ASME allows it when unavoidable, so it is advisory
    (``dim-line-crosses-extension``), and gating only where the crossing is
    through, or within ``heights`` text heights of, either dimension's text
    (``dim-line-crosses-extension-at-text``). One finding per pair, the worse,
    whichever dimension's line crosses the other's extension line.
    """
    def runs(role: str) -> list[tuple[AnnotationGeometry, list[Segment], Box]]:
        found = []
        for annotation in sheet.annotations:
            chosen = [s for s in annotation.segments if s.role == role]
            if chosen:
                found.append((annotation, chosen, union_boxes([s.box() for s in chosen])))
        return found

    worst_of: dict[tuple[str, str], tuple[bool, tuple[float, float], Segment, Segment, str, str]] = {}
    extended = runs("ext-line")
    for source, lines, line_box in runs("dim-line"):
        for target, extensions, extension_box in extended:
            if source.label == target.label or line_box.gap(extension_box) > COLLINEAR_TOL_M:
                continue
            worst = None
            for line in lines:
                for extension in extensions:
                    point = _proper_crossing(
                        LeaderSegment(source.label, source.kind, line.x0, line.y0, line.x1, line.y1),
                        LeaderSegment(target.label, target.kind, extension.x0, extension.y0, extension.x1, extension.y1),
                        tol=1e-4,
                    )
                    if point is None:
                        continue
                    near = any(
                        _point_box_distance(point, box) <= heights * text_height(owner)
                        for owner in (source, target)
                        for box in owner.text_boxes
                    )
                    if worst is None or (near and not worst[0]):
                        worst = (near, point, line, extension)
            if worst is None:
                continue
            pair = tuple(sorted((source.label, target.label)))
            kept = worst_of.get(pair)
            if kept is not None and (kept[0] or not worst[0]):
                continue
            worst_of[pair] = (*worst, source.label, target.label)
    return [
        Finding(
            kind="dim-line-crosses-extension-at-text" if near else "dim-line-crosses-extension",
            sheet=sheet.name,
            a=a,
            b=b,
            detail=(
                f"dimension line of {a!r} {line.format_mm()} crosses "
                f"{b!r}'s extension line {extension.format_mm()}"
                + (" at its text" if near else "")
            ),
            at_mm=(point[0] * MM, point[1] * MM),
        )
        for near, point, line, extension, a, b in worst_of.values()
    ]


def _near_foreign_text(
    sheet: SheetGeometry,
    sources: Sequence[tuple[int, Segment]],
    *,
    kind: str,
    what: str,
    clearance: float,
) -> list[Finding]:
    """Each (source, text owner) pair where a source segment stands nearer
    than ``clearance`` to ANOTHER annotation's text box, at its nearest. A
    balloon is measured to its printed ring, not the ring's bounding square."""
    grid = SegmentGrid(sources)
    nearest: dict[tuple[int, int], tuple[float, Segment, Box]] = {}
    for target_index, target in enumerate(sheet.annotations):
        if target.kind == "geometry":
            continue
        for box in target.text_boxes:
            reach = Box(box.xmin - clearance, box.ymin - clearance, box.xmax + clearance, box.ymax + clearance)
            for owner, segment in grid.near(reach):
                if sheet.annotations[owner].label == target.label:
                    continue
                gap = (
                    segment_circle_distance(segment, target.circle)
                    if target.circle is not None
                    else segment_box_distance(segment, box)
                )
                key = (owner, target_index)
                if gap < clearance and (key not in nearest or gap < nearest[key][0]):
                    nearest[key] = (gap, segment, box)
    findings = []
    for (owner, target_index), (gap, segment, box) in nearest.items():
        source, target = sheet.annotations[owner], sheet.annotations[target_index]
        findings.append(
            Finding(
                kind=kind,
                sheet=sheet.name,
                a=source.label,
                b=target.label,
                detail=(
                    f"{what} of {source.label!r} {segment.format_mm()} stands {gap * MM:.2f}mm from "
                    f"{target.label!r}'s text {box.format_mm()} (clearance {clearance * MM:.1f}mm)"
                ),
                at_mm=tuple(value * MM for value in box.center()),
                extra={"gap_mm": gap * MM},
            )
        )
    return findings


def find_arrows_near_text(sheet: SheetGeometry, *, clearance: float = ARROW_TEXT_CLEARANCE_M) -> list[Finding]:
    """An arrowhead, or an outside arrow's tail, nearer than ``clearance`` to
    another annotation's text: gating, the fleet's arrow-to-text rule. That
    close the arrow reads as part of the text (MHA-092 round 2: the 15.2's
    tail 0.2 mm over ADJUSTER ENTRY, the 10.7's arrow inside the 3.97's
    tolerance stack)."""
    sources = [
        (owner, segment)
        for owner, annotation in enumerate(sheet.annotations)
        for segment in (
            *(s for s in annotation.segments if s.role == "arrow"),
            *getattr(annotation, "arrow_tails", ()),
        )
    ]
    return _near_foreign_text(sheet, sources, kind="arrow-near-text", what="arrow", clearance=clearance)


def find_extensions_near_text(sheet: SheetGeometry, *, clearance: float = ARROW_TEXT_CLEARANCE_M) -> list[Finding]:
    """An extension line within ``clearance`` of another annotation's text
    without running through it: advisory, since witnesses routinely pass
    close to neighbouring text (Main's ruling). Through it is
    ``text-on-line``, which gates."""
    sources = [
        (owner, segment)
        for owner, annotation in enumerate(sheet.annotations)
        for segment in annotation.segments
        if segment.role == "ext-line"
    ]
    return _near_foreign_text(sheet, sources, kind="extension-near-text", what="extension line", clearance=clearance)


def _collinear_overlap(segment: Segment, line: Segment, tol: float = COLLINEAR_TOL_M) -> tuple[tuple[float, float], float] | None:
    """Midpoint and length of the stretch where ``segment`` lies ON ``line``."""
    if not line.length or not segment.length:
        return None
    ux, uy = (line.x1 - line.x0) / line.length, (line.y1 - line.y0) / line.length
    offsets = [((x - line.x0) * uy - (y - line.y0) * ux) for x, y in ((segment.x0, segment.y0), (segment.x1, segment.y1))]
    if max(abs(o) for o in offsets) > tol:
        return None
    t0 = (segment.x0 - line.x0) * ux + (segment.y0 - line.y0) * uy
    t1 = (segment.x1 - line.x0) * ux + (segment.y1 - line.y0) * uy
    low, high = max(min(t0, t1), 0.0), min(max(t0, t1), line.length)
    if high - low <= tol:
        return None
    middle = (low + high) / 2.0
    return (line.x0 + ux * middle, line.y0 + uy * middle), high - low


def find_lines_on_dimension_lines(sheet: SheetGeometry) -> list[Finding]:
    """A leader, or a section line's arrow, lying ALONG another annotation's
    dimension line: the two print as one stroke (pinion-bracket's section
    arrow B down 28.00's dimension line). Main's ruling: gating, within
    ``COLLINEAR_TOL_M``. Shared extension lines are normal drafting and exempt.
    """
    sources = [
        (annotation, segment)
        for annotation in sheet.annotations
        for segment in annotation.segments
        if segment.role in ("leader", "shoulder")
        or (annotation.kind == "section-line" and segment.role in ("arrow", "line"))
    ]
    targets = [
        (annotation, segment)
        for annotation in sheet.annotations
        for segment in annotation.segments
        if segment.role == "dim-line"
    ]
    findings = []
    seen = set()
    for source, segment in sources:
        for target, line in targets:
            if source.label == target.label or (source.label, target.label) in seen:
                continue
            overlap = _collinear_overlap(segment, line)
            if overlap is None:
                continue
            seen.add((source.label, target.label))
            point, length = overlap
            findings.append(
                Finding(
                    kind="line-on-dimension-line",
                    sheet=sheet.name,
                    a=source.label,
                    b=target.label,
                    detail=(
                        f"{segment.role} of {source.label!r} {segment.format_mm()} lies along "
                        f"{target.label!r}'s dimension line {line.format_mm()} for {length * MM:.2f}mm"
                    ),
                    at_mm=(point[0] * MM, point[1] * MM),
                    extra={"overlap_mm": length * MM},
                )
            )
    return findings


def find_text_on_view(
    sheet: SheetGeometry, *, inset: float = DEFAULT_CROSSING_INSET_M
) -> list[Finding]:
    """Text printed over a view its annotation does not belong to.

    MHA-092's adjuster callout, owned by the front view, printed across the
    right view's face (swing's gap diff). Text-on-line only sees text that
    touches an edge; text sitting INSIDE a foreign view, between its edges, is
    just as wrong (policy rule 8). The outline is ``GetOutline``'s padded box,
    inset like the leader-crossing check; pictorial views are skipped because
    their box is mostly empty diagonal space.

    A view whose model edges were read from the PDF is bounded by those
    edges: ``GetOutline`` pads the part by a few millimetres, so a symbol
    parked beside a view read as over it (knife-mount's Ra 0.8, 2 mm into
    the outline, 1.5 mm clear of the first edge).
    """
    printed = {
        annotation.owner: list(annotation.segments)
        for annotation in sheet.annotations
        if annotation.kind == "geometry"
    }
    views = []
    for view in sheet.views:
        if view.outline is None or view.pictorial:
            continue
        edges = printed.get(view.name)
        if edges:
            views.append((view.name, Box.from_points([p for s in edges for p in ((s.x0, s.y0), (s.x1, s.y1))])))
            continue
        views.append(
            (
                view.name,
                Box(
                    view.outline.xmin + inset,
                    view.outline.ymin + inset,
                    view.outline.xmax - inset,
                    view.outline.ymax - inset,
                ),
            )
        )
    findings = []
    for annotation in sheet.annotations:
        if annotation.kind == "geometry":
            continue
        for name, inner in views:
            if name == annotation.owner or inner.xmin >= inner.xmax or inner.ymin >= inner.ymax:
                continue
            for box in annotation.text_boxes:
                depth = box.overlaps(inner, tol=0.0)
                if depth is None:
                    continue
                findings.append(
                    Finding(
                        kind="text-on-view",
                        sheet=sheet.name,
                        a=annotation.label,
                        b=f"view {name}",
                        detail=(
                            f"text of {annotation.label!r} {box.format_mm()} prints over "
                            f"view {name!r} by {depth[0] * MM:.2f}x{depth[1] * MM:.2f}mm"
                        ),
                        at_mm=tuple(value * MM for value in box.center()),
                        move_target_mm=_move_mm(box, inner),
                        extra={"depth_x_mm": depth[0] * MM, "depth_y_mm": depth[1] * MM},
                    )
                )
    return findings


def find_unclaimed_text(model: SheetModel) -> list[Finding]:
    """Printed text no COM item claims: an annotation whose COM read failed
    (``_Reader`` counts it, but it prints) is invisible to every other check."""
    return [
        Finding(
            kind="pdf-text-unclaimed",
            sheet=model.geometry.name,
            a=f"pdf {text!r}",
            b="",
            detail=f"printed text {text!r} {box.format_mm()} has no COM annotation claiming it",
            at_mm=tuple(value * MM for value in box.center()),
        )
        for text, box in model.unclaimed
    ]


def find_edgeless_views(model: SheetModel) -> list[Finding]:
    """A view that printed no model edge: text over it cannot be checked.

    Shaded and draft views print images or other weights, and a template with
    another edge weight would blank every view. A pictorial view is advisory
    (its text-on-view check is skipped anyway)."""
    return [
        Finding(
            kind="view-edges-missing-pictorial" if pictorial else "view-edges-missing",
            sheet=model.geometry.name,
            a=f"view {name}",
            b="",
            detail=f"view {name!r} has an outline but no printed 0.25 mm model edge",
        )
        for name, pictorial in model.edgeless
    ]


def find_read_errors(dump: Mapping[str, Any]) -> list[Finding]:
    """COM reads the collector was refused on this sheet: each can hide ink."""
    errors = dump.get("read_errors") or {}
    if not errors:
        return []
    return [
        Finding(
            kind="com-read-errors",
            sheet=str(dump.get("sheet", "")),
            a="collector",
            b=", ".join(sorted(errors)),
            detail=f"{sum(errors.values())} refused COM read(s): {dict(sorted(errors.items()))}",
            extra={"read_errors": dict(errors)},
        )
    ]


def find_duplicate_annotations(
    dump: Mapping[str, Any], *, tol: float = DUPLICATE_POSITION_TOL_M
) -> list[Finding]:
    """Two visible annotations of the same type, owned by the same view (or
    the sheet), anchored at the same position: the second prints over the
    first. Every cone-gear sheet carried its centre mark twice (#913), and
    the overdraw thickens the ink a reader sees."""
    owners = [(str(view.get("name", "")), view.get("annotations") or ()) for view in dump.get("views", ())]
    # Template annotations are the title block's, not the drawing's.
    owners.append(
        (
            "sheet",
            [
                annotation
                for annotation in dump.get("sheet_annotations") or ()
                if int(annotation.get("owner_type", _OWNER_DRAWING_SHEET)) == _OWNER_DRAWING_SHEET
            ],
        )
    )
    findings = []
    for owner, members in owners:
        placed = [
            (annotation, _floats(annotation.get("pos")))
            for annotation in members
            if int(annotation.get("visible", 1) or 1) not in _HIDDEN_STATES
        ]
        placed = [(annotation, pos) for annotation, pos in placed if len(pos) >= 2]
        for (first, a), (second, b) in combinations(placed, 2):
            if int(first.get("type", 0)) != int(second.get("type", 0)):
                continue
            if math.hypot(a[0] - b[0], a[1] - b[1]) > tol:
                continue
            kind = ANNOTATION_KINDS.get(int(first.get("type", 0)), "other")
            findings.append(
                Finding(
                    kind="duplicate-annotation",
                    sheet=str(dump.get("sheet", "")),
                    a=f"{kind} {first.get('name', '')}",
                    b=f"{kind} {second.get('name', '')}",
                    detail=(
                        f"{kind} {first.get('name', '')!r} and {second.get('name', '')!r} in {owner!r} are "
                        f"anchored at the same point ({a[0] * MM:.2f},{a[1] * MM:.2f})mm: one prints over the other"
                        + ("" if first.get("display") != second.get("display") else ", identically")
                    ),
                    at_mm=(a[0] * MM, a[1] * MM),
                    extra={"owner": owner, "identical": first.get("display") == second.get("display")},
                )
            )
    return findings


def find_unmatched_text(model: SheetModel) -> list[Finding]:
    """COM text the printed PDF has no text object for: the audit is blind there.

    Symbol tokens print as paths and are exempt; anything else unmatched means
    the sheet printed something other than what COM reports, or not at all.
    """
    return [
        Finding(
            kind="text-unmatched",
            sheet=model.geometry.name,
            a=label,
            b=text,
            detail=f"{label!r}'s text {text!r} has no printed PDF text object near its position",
        )
        for label, text in model.unmatched
    ]


# Which finding kinds gate once LAYOUT_AUDIT_MODE is GATE.
GATING_KINDS = frozenset(
    {
        "text-clearance",
        "text-on-line",
        "leader-through-text",
        "leader-through-own-text",
        "extension-through-own-text",
        "dim-line-through-own-text",
        "leader-crosses-line",
        "shoulder-crosses-line",
        "leader-crosses-view",
        "leader-crosses-leader",
        "outside-border",
        "keep-out",
        "text-unmatched",
        "pdf-text-unclaimed",
        "view-edges-missing",
        "com-read-errors",
        "duplicate-annotation",
        "duplicate-thread-callout",
        "leader-over-part",
        "leader-crosses-section-line",
        "dim-line-crosses-extension-at-text",
        "line-on-dimension-line",
        "arrow-near-text",
        "merged-blocks",
        "tall-block",
        "text-on-view",
    }
)


def severity(finding: Finding) -> FindingSeverity:
    if finding.kind in GATING_KINDS:
        return FindingSeverity.GATING
    return FindingSeverity.ADVISORY


def audit_dump(dump: Mapping[str, Any]) -> list[Finding]:
    """Every layout finding on one dumped sheet, gating and advisory."""
    dump = printed_dump(dump)
    model = sheet_model(dump)
    sheet = model.geometry
    # Leaders through text have their own finder (which knows own vs foreign
    # rows); strip them here so one defect is not reported twice.
    unled = replace(
        sheet,
        annotations=tuple(
            replace(a, segments=tuple(s for s in a.segments if s.role != "leader"))
            for a in sheet.annotations
        ),
    )
    clearance = find_text_clearance(sheet)
    touching = {frozenset((f.a, f.b)) for f in clearance}
    merged = [f for f in find_merged_blocks(sheet) if frozenset((f.a, f.b)) not in touching]
    reported = touching | {frozenset((f.a, f.b)) for f in merged}
    on_line = find_text_on_line(unled)
    through = {frozenset((f.a, f.b)) for f in on_line}
    through_lines = {(frozenset((f.a, f.b)), tuple(f.extra["segment"])) for f in on_line}
    return _one_per_pair([
        *clearance,
        *merged,
        *find_tall_blocks(dump),
        *on_line,
        *find_text_on_view(sheet),
        *find_leader_through_text(sheet),
        *find_lines_through_own_text(sheet),
        # A line through a callout's text crosses the shoulder under it too:
        # one defect, reported as text-on-line. Only the SAME line: another
        # line of that annotation crossing the shoulder is its own defect.
        *(
            f
            for f in find_leader_across_lines(sheet)
            if f.kind != "shoulder-crosses-line"
            or (frozenset((f.a, f.b)), tuple(f.extra["line"])) not in through_lines
        ),
        *find_leaders_over_part(sheet),
        *find_dimension_line_crossings(sheet),
        *find_lines_on_dimension_lines(sheet),
        *(f for f in find_arrows_near_text(sheet) if frozenset((f.a, f.b)) not in through),
        *(f for f in find_extensions_near_text(sheet) if frozenset((f.a, f.b)) not in through),
        *find_leader_crossings(sheet),
        *find_border_breaches(sheet),
        *find_unmatched_text(model),
        *find_unclaimed_text(model),
        *find_edgeless_views(model),
        *find_read_errors(dump),
        *find_duplicate_annotations(dump),
        *find_duplicate_thread_callouts(dump, sheet),
        *(f for f in find_text_separation(sheet) if frozenset((f.a, f.b)) not in reported),
    ])


def _one_per_pair(findings: Sequence[Finding]) -> list[Finding]:
    """The first finding of each kind per pair: moving one annotation clears
    them all, so a two-row callout crossed by one line is one defect, not two
    (knife-mount's Ø12.00 / THRU)."""
    kept: dict[tuple[str, str, str], Finding] = {}
    for finding in findings:
        kept.setdefault((finding.kind, finding.a, finding.b), finding)
    return list(kept.values())


def finding_record(stem: str, finding: Finding) -> dict[str, Any]:
    return {"stem": stem, "severity": severity(finding).value, **finding.to_dict()}


REPORT_SCHEMA = 1


def replace_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` whole or not at all: into a temporary file
    beside it, then renamed over it. A crash mid-write leaves no torn file
    at ``path`` and no temporary behind. The caller removes the previous
    file before the work that produces ``text`` (``run_layout_audit``), so
    a failed run leaves nothing to be read as its output (Codex, #902)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def report_sheet(dump: Mapping[str, Any]) -> dict[str, Any]:
    """A dump as the report keeps it: the page's strokes become a count.

    Thousands of strokes per sheet would dominate the cached report; the PDF
    they came from is itself a cached drawing output, and a replay re-reads
    it (``diagnostics/layout_calibration.py --pdf-dir``). Findings carry their
    offending segments in their detail.
    """
    sheet = dict(dump)
    ink = dict(dump.get("ink") or {})
    if "strokes" in ink:
        ink["stroke_count"] = len(ink.pop("strokes"))
        sheet["ink"] = ink
    return sheet


def audit_report(
    stem: str, mode: LayoutAuditMode, dumps: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], list[Finding]]:
    """One drawing's layout report and its gating findings.

    The report is the drawing task's cached ``layout-audit/<stem>.json``: the
    summary, every finding, and every sheet dump, so a leaf restored from the
    remote cache replays exactly what the building seat saw.
    """
    records = []
    gating = []
    counts: dict[str, int] = {}
    for dump in dumps:
        for finding in audit_dump(dump):
            records.append(finding_record(stem, finding))
            counts[finding.kind] = counts.get(finding.kind, 0) + 1
            if severity(finding) is FindingSeverity.GATING:
                gating.append(finding)
    report = {
        "schema": REPORT_SCHEMA,
        "stem": stem,
        "mode": mode.value,
        "summary": {
            "sheets": len(dumps),
            "findings": dict(sorted(counts.items())),
            "gating": len(gating),
            "hidden_layer": {
                str(dump.get("sheet", "")): hidden
                for dump in dumps
                if (hidden := hidden_layer_count(dump))
            },
        },
        "findings": records,
        "sheets": [report_sheet(dump) for dump in dumps],
    }
    return report, gating
