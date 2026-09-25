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

import base64
import json
import math
import re
import zlib
from dataclasses import dataclass, replace
from enum import Enum
from itertools import combinations
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from _drawing_layout_check import DrawableRegion, LeaderSegment, _proper_crossing
from _layout_geometry import (
    DEFAULT_ADVANCE_RATIO,
    DEFAULT_TEXT_TOUCH_TOL_M,
    MM,
    AnnotationGeometry,
    Box,
    Finding,
    Segment,
    SheetGeometry,
    ViewGeometry,
    clip_segment_to_box,
    find_border_breaches,
    find_leader_crossings,
    find_text_on_line,
    segment_box_overlap_length,
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
# swAnnotationVisibilityState_e: 2 = half hidden, 3 = hidden.
_HIDDEN_STATES = (2, 3)
_OWNER_DRAWING_SHEET = 1


# --------------------------------------------------------------------------
# dump transport: one sheet dump per log record set, grep-able from task.log
# --------------------------------------------------------------------------

DUMP_PREFIX = "layout-audit-dump"
FINDING_PREFIX = "layout-audit-finding"
SUMMARY_PREFIX = "layout-audit-summary"
# Farm leaves upload the console log; keep each record well under any
# collector's per-record limit.
_DUMP_CHUNK = 60_000


def encode_dump_lines(stem: str, dump: Mapping[str, Any]) -> list[str]:
    """``dump`` as grep-able, chunked log lines: prefix, stem, sheet, i/n, b64."""
    payload = base64.b64encode(
        zlib.compress(json.dumps(dump, separators=(",", ":")).encode("utf-8"), 9)
    ).decode("ascii")
    chunks = [
        payload[index : index + _DUMP_CHUNK]
        for index in range(0, len(payload), _DUMP_CHUNK)
    ] or [""]
    sheet = str(dump.get("sheet", "")).replace(" ", "_")
    return [
        f"{DUMP_PREFIX} {stem} {sheet} {index + 1}/{len(chunks)} {chunk}"
        for index, chunk in enumerate(chunks)
    ]


def decode_dump_lines(lines: Iterable[str]) -> list[dict[str, Any]]:
    """Every complete dump in ``lines`` (any text containing the log records)."""
    parts: dict[tuple[str, str], dict[int, tuple[int, str]]] = {}
    for line in lines:
        at = line.find(DUMP_PREFIX + " ")
        if at < 0:
            continue
        fields = line[at:].split()
        if len(fields) < 5:
            continue
        _, stem, sheet, position, chunk = fields[:5]
        index, _, total = position.partition("/")
        parts.setdefault((stem, sheet), {})[int(index)] = (int(total), chunk)
    dumps = []
    for (_stem, _sheet), chunks in parts.items():
        total = next(iter(chunks.values()))[0]
        if sorted(chunks) != list(range(1, total + 1)):
            continue
        payload = "".join(chunks[index][1] for index in range(1, total + 1))
        dumps.append(json.loads(zlib.decompress(base64.b64decode(payload))))
    return dumps


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
    The rotation direction sign is honoured, flipped by a -Z normal.
    """
    values = _floats(raw)
    if len(values) < 17:
        return []
    start = (values[4], values[5])
    end = (values[7], values[8])
    center = (values[10], values[11])
    normal_z = values[15]
    direction = values[16]
    ccw = (direction >= 0) == (normal_z >= 0)
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

    Width runs along the arrow direction, height across it.
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
    base = (tip[0] - ux * width, tip[1] - uy * width)
    left = (base[0] - uy * height / 2.0, base[1] + ux * height / 2.0)
    right = (base[0] + uy * height / 2.0, base[1] - ux * height / 2.0)
    xy = [tip, left, right]
    return [
        Segment(a[0], a[1], b[0], b[1], role) for a, b in zip(xy, [*xy[1:], xy[0]])
    ]


def view_polyline_segments(raw: Sequence[float], role: str = "geometry") -> list[Segment]:
    """``IView::GetPolylines7`` out-array: repeated records of

    ``[Type, GeomDataSize, GeomData[size], LineColor, LineStyle, LineFont,
    LineWeight, LayerID, LayerOverride, NumPolyPoints, xyz * n]``.

    Every record is tessellated already (arcs too), so the points are joined.
    """
    values = _floats(raw)
    segments: list[Segment] = []
    index = 0
    while index + 2 <= len(values):
        size = int(values[index + 1])
        count_at = index + 2 + size + 6
        if count_at >= len(values):
            break
        count = int(values[count_at])
        points = values[count_at + 1 : count_at + 1 + 3 * count]
        if len(points) != 3 * count:
            break
        xy = [(points[i], points[i + 1]) for i in range(0, len(points), 3)]
        segments.extend(
            Segment(a[0], a[1], b[0], b[1], role) for a, b in zip(xy, xy[1:])
        )
        index = count_at + 1 + 3 * count
    return segments


def apply_transform(
    array_data: Sequence[float], x: float, y: float, z: float
) -> tuple[float, float]:
    """Map a point through a SolidWorks ``IMathTransform.ArrayData``.

    ArrayData is [r00..r22 (row-major 3x3), tx, ty, tz, scale, 0, 0, 0] and a
    point p maps to ``scale * (p @ R) + t`` (row vector convention).
    """
    r = _floats(array_data)
    scale = r[12] if len(r) > 12 and r[12] else 1.0
    px = x * r[0] + y * r[3] + z * r[6]
    py = x * r[1] + y * r[4] + z * r[7]
    return (scale * px + r[9], scale * py + r[10])


# --------------------------------------------------------------------------
# text rows
# --------------------------------------------------------------------------


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


def _display_segments(display: Mapping[str, Any]) -> list[Segment]:
    segments: list[Segment] = []
    for raw in display.get("lines", ()):
        segment = line_segment(raw)
        if segment is not None:
            segments.append(segment)
    for raw in display.get("arcs", ()):
        segments.extend(arc_segments(raw))
    for raw in display.get("polylines", ()):
        segments.extend(polyline_segments(raw))
    for raw in display.get("polygons", ()):
        segments.extend(polygon_segments(raw))
    for raw in display.get("triangles", ()):
        segments.extend(triangle_segments(raw))
    for raw in display.get("arrows", ()):
        segments.extend(arrowhead_segments(raw))
    return segments


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


def _classify(
    kind: str,
    annotation: Mapping[str, Any],
    segments: list[Segment],
    shoulders: Sequence[Segment],
) -> list[Segment]:
    """Give each display-data segment its role: shoulder, leader or line.

    * A hole callout's display data is its leader plus the shoulder under its
      text (supports' calibration): every non-shoulder line is leader.
    * Other annotations: a run that touches the annotation's own text is its
      leader, everything else is dimension/witness/frame ink.
    """
    shoulder_ids = {id(s) for s in shoulders}
    hole_callout = bool((annotation.get("dim") or {}).get("hole_callout"))
    roles = []
    for segment in segments:
        if id(segment) in shoulder_ids:
            role = "shoulder"
        elif hole_callout:
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


def text_height(annotation: AnnotationGeometry) -> float:
    height = getattr(annotation, "text_height", 0.0)
    if height > 0.0:
        return height
    return min((box.height for box in annotation.text_boxes), default=0.0)


def annotation_geometry(
    annotation: Mapping[str, Any], *, owner: str, advance: float
) -> AnnotationGeometry | None:
    """One dumped annotation as the audit sees it: text rows plus its own ink."""
    kind = ANNOTATION_KINDS.get(int(annotation.get("type", 0)), "other")
    if int(annotation.get("visible", 1) or 1) in _HIDDEN_STATES:
        return None
    label = str(annotation.get("name") or kind)
    display = annotation.get("display") or {}
    items = text_items(display)
    segments = _display_segments(display)
    if kind == "dim" and (annotation.get("dim") or {}).get("hole_callout"):
        kind = "hole-callout"
    shoulders = _shoulders(segments, items) if kind in ("dim", "hole-callout", "note") else []
    segments = _classify(kind, annotation, segments, shoulders)
    segments.extend(_registered_leaders(annotation))

    note = annotation.get("note") or {}
    exact = False
    rows: list[tuple[str, Box]]
    circle = balloon_circle(display) if note.get("balloon") else None
    if circle is not None:
        # A BOM balloon's GetExtent includes its leader; its rendered
        # full-circle arc is the balloon (``rendered_balloon_circle``).
        cx, cy, radius = circle
        rows = [(str(note.get("text", "")), Box(cx - radius, cy - radius, cx + radius, cy + radius))]
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
    if heights:
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
    return AuditAnnotation(
        label=f"{kind} {label}" + (f" {rows[0][0]!r}" if rows and rows[0][0] else ""),
        kind=kind,
        owner=owner,
        text_boxes=tuple(box for _text, box in rows),
        segments=tuple(segments),
        position=(position[0], position[1]) if len(position) >= 2 else None,
        exact=exact,
        text_height=height,
    )


def _section_geometry(section: Mapping[str, Any], *, owner: str, advance: float) -> AnnotationGeometry | None:
    """A section line: cutting line + arrows as ink, its two labels as text.

    ``IDrSection::GetTextInfo`` gives each label's UPPER-LEFT origin
    (types/IDrSection/GetTextInfo.md); its height is the section text format's
    ``CharHeight``.
    """
    segments = []
    line = _floats(section.get("line"))
    for i in range(0, len(line) - 5, 6):
        segments.append(Segment(line[i], line[i + 1], line[i + 3], line[i + 4], "line"))
    arrows = _floats(section.get("arrows"))
    for i in range(0, len(arrows) - 5, 6):
        segments.append(Segment(arrows[i], arrows[i + 1], arrows[i + 3], arrows[i + 4], "arrow"))
    label = str(section.get("label") or "")
    height = float(section.get("text_height") or 0.0)
    texts = _floats(section.get("texts"))
    rows = []
    if label and height > 0.0:
        width = advance * height * max(1, glyph_count(label))
        for i in range(0, len(texts) - 2, 3):
            x, y = texts[i], texts[i + 1]
            rows.append(Box(x, y - height, x + width, y))
    if not segments and not rows:
        return None
    return AnnotationGeometry(
        label=f"section-line {label}",
        kind="section-line",
        owner=owner,
        text_boxes=tuple(rows),
        segments=tuple(segments),
    )


def _detail_circle_geometries(info: Sequence[float], *, owner: str, advance: float) -> list[AnnotationGeometry]:
    """``IView::GetDetailCircleInfo2``: [n, (layer, center3, start3, end3,
    lineType, textPt3, textHeight, numArrows, (tip3, comp3, w, h, style)*)*]."""
    values = _floats(info)
    if not values:
        return []
    count = int(values[0])
    index = 1
    geometries = []
    for number in range(count):
        if index + 15 > len(values):
            break
        center = (values[index + 1], values[index + 2])
        start = (values[index + 4], values[index + 5])
        end = (values[index + 7], values[index + 8])
        text_pt = (values[index + 11], values[index + 12])
        height = values[index + 14]
        arrows = int(values[index + 15])
        index += 16 + arrows * 9
        points = _arc_points(center, start, end, ccw=True)
        segments = tuple(
            Segment(a[0], a[1], b[0], b[1], "line") for a, b in zip(points, points[1:])
        )
        rows = ()
        if height > 0.0:
            rows = (Box(text_pt[0], text_pt[1] - height, text_pt[0] + advance * height, text_pt[1]),)
        geometries.append(
            AnnotationGeometry(
                label=f"detail-circle {owner} #{number + 1}",
                kind="detail-circle",
                owner=owner,
                text_boxes=rows,
                segments=segments,
            )
        )
    return geometries


# --------------------------------------------------------------------------
# view geometry: which coordinate space GetPolylines7 answers in
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ViewInk:
    """One view's projected model edges in sheet metres, and how they got there."""

    name: str
    segments: tuple[Segment, ...]
    space: str  # "sheet" | "transformed" | "unresolved" | "none" | "omitted"
    inside_fraction: float


def _inside_fraction(segments: Sequence[Segment], outline: Box) -> float:
    if not segments:
        return 0.0
    pad = 0.001
    inside = 0
    for s in segments:
        for x, y in ((s.x0, s.y0), (s.x1, s.y1)):
            if outline.xmin - pad <= x <= outline.xmax + pad and outline.ymin - pad <= y <= outline.ymax + pad:
                inside += 1
    return inside / (2 * len(segments))


def view_ink(view: Mapping[str, Any]) -> ViewInk:
    """The view's visible model edges, in SHEET space.

    ``GetPolylines7`` does not document its coordinate space. The points are
    accepted as sheet space when they land inside the view's ``GetOutline``;
    otherwise the view's ``ModelToViewTransform`` is applied and re-tested.
    Neither landing inside is reported (``space == "unresolved"``) rather than
    guessed -- the calibration run fixes the answer from real data.
    """
    name = str(view.get("name", ""))
    if view.get("polylines_omitted"):
        # A logged replay copy whose polylines were too large to log; the leaf
        # audited the full array in process.
        return ViewInk(name, (), "omitted", 0.0)
    outline_values = _floats(view.get("outline"))
    raw = view.get("polylines") or []
    segments = view_polyline_segments(raw)
    if not segments or len(outline_values) < 4:
        return ViewInk(name, (), "none", 0.0)
    outline = Box(*outline_values[:4])
    direct = _inside_fraction(segments, outline)
    if direct >= 0.95:
        return ViewInk(name, tuple(segments), "sheet", direct)
    transform = _floats(view.get("transform"))
    if len(transform) >= 13:
        mapped = []
        for s in segments:
            x0, y0 = apply_transform(transform, s.x0, s.y0, 0.0)
            x1, y1 = apply_transform(transform, s.x1, s.y1, 0.0)
            mapped.append(Segment(x0, y0, x1, y1, "geometry"))
        fraction = _inside_fraction(mapped, outline)
        if fraction >= 0.95:
            return ViewInk(name, tuple(mapped), "transformed", fraction)
    return ViewInk(name, (), "unresolved", direct)


# --------------------------------------------------------------------------
# dump -> SheetGeometry
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SheetModel:
    geometry: SheetGeometry
    view_ink: tuple[ViewInk, ...]
    advance: float


def sheet_model(dump: Mapping[str, Any]) -> SheetModel:
    """Parse one sheet dump into the geometry every finder reads."""
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

    view_geometry = []
    annotations: list[AnnotationGeometry] = []
    inks = []
    for view in views:
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
            item = annotation_geometry(annotation, owner=name, advance=advance)
            if item is not None:
                annotations.append(item)
        for section in view.get("sections", ()):
            item = _section_geometry(section, owner=name, advance=advance)
            if item is not None:
                annotations.append(item)
        annotations.extend(
            _detail_circle_geometries(view.get("detail_circles_info") or (), owner=name, advance=advance)
        )
        ink = view_ink(view)
        inks.append(ink)
        if ink.segments:
            annotations.append(
                AnnotationGeometry(
                    label=f"view {name} geometry",
                    kind="geometry",
                    owner=name,
                    segments=ink.segments,
                )
            )
    for annotation in dump.get("sheet_annotations", ()):
        if int(annotation.get("owner_type", _OWNER_DRAWING_SHEET)) != _OWNER_DRAWING_SHEET:
            continue
        item = annotation_geometry(annotation, owner="sheet", advance=advance)
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
    return SheetModel(geometry, tuple(inks), advance)


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
        gap = _box_gap(box_a, box_b)
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
        gap = _box_gap(a, b)
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
        leadered_note = (
            annotation.kind == "note" and not annotation.exact and annotation.leader_segments()
        )
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
    """Every note or hole callout whose text runs over ``limit`` rows."""
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
        if not (kind == "note" and not note.get("balloon")) and not hole_callout:
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
            test = (
                Box(box.xmin + own_inset, box.ymin + own_inset, box.xmax - own_inset, box.ymax - own_inset)
                if own
                else box
            )
            if test.xmin >= test.xmax or test.ymin >= test.ymax:
                continue
            for segment in leaders:
                length = segment_box_overlap_length(segment, test)
                if length <= tol:
                    continue
                span = clip_segment_to_box(segment, test)
                mid = segment.point_at(sum(span) / 2.0) if span else test.center()
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


def find_leader_across_lines(sheet: SheetGeometry) -> list[Finding]:
    """A leader transversally crossing another annotation's dimension/witness line.

    Rule 8: no leader crosses a dimension line. Touches (a leader landing ON a
    line) are not crossings -- see ``_drawing_layout_check._proper_crossing``.
    """
    findings = []
    leaders = [
        (annotation, segment)
        for annotation in sheet.annotations
        for segment in annotation.segments
        if segment.role == "leader"
    ]
    lines = [
        (annotation, segment)
        for annotation in sheet.annotations
        if annotation.kind not in ("geometry",) and annotation.kind not in _MARK_KINDS
        for segment in annotation.segments
        if segment.role == "line"
    ]
    seen = set()
    for source, leader in leaders:
        for target, line in lines:
            if target.label == source.label or (source.label, target.label) in seen:
                continue
            point = _proper_crossing(
                LeaderSegment(source.label, source.kind, leader.x0, leader.y0, leader.x1, leader.y1),
                LeaderSegment(target.label, target.kind, line.x0, line.y0, line.x1, line.y1),
                tol=1e-4,
            )
            if point is None:
                continue
            seen.add((source.label, target.label))
            findings.append(
                Finding(
                    kind="leader-crosses-line",
                    sheet=sheet.name,
                    a=source.label,
                    b=target.label,
                    detail=(
                        f"leader of {source.label!r} {leader.format_mm()} crosses "
                        f"{target.label!r}'s line {line.format_mm()}"
                    ),
                    at_mm=(point[0] * MM, point[1] * MM),
                )
            )
    return findings


def find_unresolved_views(sheet: SheetModel) -> list[Finding]:
    """A view whose model edges could not be placed on the sheet.

    The text-vs-geometry check is blind for that view; reporting it is the
    only honest outcome (the fail-loud coordinate-space assertion).
    """
    return [
        Finding(
            kind="view-geometry-unresolved",
            sheet=sheet.geometry.name,
            a=ink.name,
            detail=(
                f"view {ink.name!r}: GetPolylines7 points land inside its outline "
                f"{ink.inside_fraction:.0%} of the time untransformed and not "
                "after ModelToViewTransform either -- text vs model edges is "
                "unchecked for this view"
            ),
        )
        for ink in sheet.view_ink
        if ink.space == "unresolved"
    ]


# Which finding kinds gate once LAYOUT_AUDIT_MODE is GATE.
GATING_KINDS = frozenset(
    {
        "text-clearance",
        "text-on-line",
        "leader-through-text",
        "leader-through-own-text",
        "leader-crosses-line",
        "leader-crosses-view",
        "leader-crosses-leader",
        "outside-border",
        "keep-out",
        "view-geometry-unresolved",
        "merged-blocks",
        "tall-block",
    }
)


def severity(finding: Finding) -> FindingSeverity:
    if finding.kind in GATING_KINDS:
        return FindingSeverity.GATING
    return FindingSeverity.ADVISORY


def audit_dump(dump: Mapping[str, Any]) -> list[Finding]:
    """Every layout finding on one dumped sheet, gating and advisory."""
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
    return [
        *clearance,
        *merged,
        *find_tall_blocks(dump),
        *find_text_on_line(unled),
        *find_leader_through_text(sheet),
        *find_leader_across_lines(sheet),
        *find_leader_crossings(sheet),
        *find_border_breaches(sheet),
        *find_unresolved_views(model),
        *(f for f in find_text_separation(sheet) if frozenset((f.a, f.b)) not in reported),
    ]


def finding_record(stem: str, finding: Finding) -> dict[str, Any]:
    return {"stem": stem, "severity": severity(finding).value, **finding.to_dict()}
