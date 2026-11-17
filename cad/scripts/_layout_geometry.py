"""Sheet-space geometry for the drawing layout audit.

The audit's findings are only visible in the exported PDF: dimension TEXT
sitting on a dimension LINE, two callouts printing on top of each other, a
leader driven across a neighbouring view.  This module supplies the geometry
for auditing them (``_layout_audit``) and for the drawing recipes that place
annotations clear of each other, and is deliberately SolidWorks-free so the
math is unit-testable without a COM seat.  Everything here is SHEET space in
METRES (the unit every SolidWorks annotation API returns); findings are
reported in millimetres because that is what an author types back into
``IAnnotation::SetPosition2``.

Two kinds of crossing test live here and answer different questions:

* Leader-vs-view-outline and leader-vs-leader crossings
  (:func:`segment_crosses_box`, :func:`find_leader_leader_crossings`) are
  booleans: does this leader enter that padded view box, do these two leaders
  cross transversally.
* A segment/box overlap LENGTH (:func:`segment_box_overlap_length`) for text:
  a text box is an EXACT extent a few millimetres wide, so the question is how
  much ink actually runs through it -- a line clipping a glyph corner by 20 um
  is not a collision, a line crossing the middle of the string is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from collections.abc import Iterable
from itertools import combinations
from statistics import median

MM = 1000.0


@dataclass(frozen=True)
class DrawableRegion:
    """The usable sheet region: inside the border/zone band, in sheet meters.

    The sheet format reserves a band around the paper edge for the zone grid
    (the ``A``/``B`` row labels and ``1``..``4`` column labels) and the border
    frame.  Content may not cross into it.

    Built by :meth:`from_margins` out of values QUERIED from the live sheet
    (``ISheet::GetZoneMargin``), so it follows the template rather than
    duplicating it -- edit the zone margins in the DRWDOT and the gate moves
    with them, no constant to re-measure.
    """

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @classmethod
    def from_margins(
        cls,
        sheet_width: float,
        sheet_height: float,
        *,
        left: float,
        right: float,
        bottom: float,
        top: float,
    ) -> "DrawableRegion":
        """The region inside ``ISheet::GetZoneMargin``'s four margins."""
        region = cls(left, bottom, sheet_width - right, sheet_height - top)
        if region.xmin >= region.xmax or region.ymin >= region.ymax:
            raise ValueError(
                "sheet zone margins leave no drawable region: "
                f"left={left} right={right} bottom={bottom} top={top} on a "
                f"{sheet_width} x {sheet_height} m sheet"
            )
        return region

    @classmethod
    def whole_sheet(cls, sheet_width: float, sheet_height: float) -> "DrawableRegion":
        """The full sheet -- the region when a sheet declares no zone margins."""
        return cls(0.0, 0.0, sheet_width, sheet_height)


@dataclass(frozen=True)
class LeaderSegment:
    """One straight run of an annotation's leader, in sheet meters.

    A bent leader is two segments (elbow + tail); a straight leader is one.
    ``owner`` is the view the annotation points at -- the leader is EXPECTED to
    land there, so that view is exempt.
    """

    label: str
    kind: str  # the owning annotation's kind: "gdt" | "note" | "dim"
    x0: float
    y0: float
    x1: float
    y1: float
    owner: str = ""


def segment_crosses_box(
    segment: LeaderSegment, box: tuple[float, float, float, float], *, inset: float
) -> bool:
    """True if ``segment`` passes through ``box``, shrunk by ``inset``.

    Liang-Barsky clipping.  The box is INSET so a leader that merely grazes a
    neighbouring view's padded ``GetOutline`` whitespace is not reported -- only
    a genuine run through the view's interior is.
    """
    xmin, ymin, xmax, ymax = box
    xmin, ymin = xmin + inset, ymin + inset
    xmax, ymax = xmax - inset, ymax - inset
    if xmin >= xmax or ymin >= ymax:  # inset collapsed a tiny box
        return False
    dx = segment.x1 - segment.x0
    dy = segment.y1 - segment.y0
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, segment.x0 - xmin),
        (dx, xmax - segment.x0),
        (-dy, segment.y0 - ymin),
        (dy, ymax - segment.y0),
    ):
        if p == 0:
            if q < 0:  # parallel to this edge and outside it
                return False
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return False
            t0 = max(t0, t)
        else:
            if t < t0:
                return False
            t1 = min(t1, t)
    return t0 < t1


# How far inside a view's padded outline a leader must run before it counts as
# crossing it.  ``GetOutline`` pads a few mm of whitespace, so a leader routed
# cleanly past a neighbouring view can clip the padding without touching any
# geometry; ~2 mm clears that while a leader driven across a view penetrates by
# centimetres.
DEFAULT_CROSSING_INSET_M = 0.002

# Two leaders that merely TOUCH are not a crossing, and the distinction has to
# be geometric rather than a fudge factor: a BENT leader's elbow and tail share
# an endpoint BY CONSTRUCTION, and two arrows landing on one edge is a stacking
# question, not a crossing.  Only a TRANSVERSAL crossing -- each segment
# strictly separating the other's endpoints -- is reported.
#
# The tolerance is a DISTANCE, not a raw cross-product.  The orientation
# determinant is twice a triangle's AREA, so its magnitude scales with segment
# length: one fixed area epsilon would be strict on a 5 mm leader and slack on a
# 200 mm one, and this sheet carries both.  Dividing by the segment length makes
# 0.1 mm mean 0.1 mm everywhere.  0.1 mm is also below the 300 dpi render's own
# resolution (1/300 in = 0.085 mm), so anything reported is ink a reader can see.
_CROSSING_TOUCH_TOL_M = 1e-4

# Two leaders that CONVERGE ON THE SAME ATTACHMENT POINT are STACKED, not
# crossing, and must not be reported here.  Arrowheads render ~2.4 mm long, so
# the last fraction of a millimetre before a shared terminus is buried under
# them: whatever the segments do in there, no reader can see a crossing.
#
# The threshold is MEASURED, not tuned.  Across the five crossings the gate found
# on its first fleet-wide sweep (2026-07-16), the distance between the nearest
# endpoint of one leader and the nearest of the other was:
#     platen-guide  0.2 mm   <- both leaders end at x=0.3650, 0.2 mm apart in y
#     pen-assembly  4.7 mm / 11.6 mm / 29.2 mm
#     pen-rod      10.3 mm
# The one false positive sits at 0.2 mm and the tightest TRUE positive at 4.7 mm,
# so 1 mm splits them with ~5x margin on the real side and ~5x on the artefact
# side.  If a future sheet legitimately crosses two leaders within 1 mm of a
# shared terminus, that crossing is invisible anyway and the stack is the finding.
_SHARED_TERMINUS_M = 1e-3


def _crossing_is_under_a_shared_terminus(
    a: LeaderSegment, b: LeaderSegment, x: float, y: float, *, tol: float
) -> bool:
    """True if the crossing at ``(x, y)`` is buried under a shared arrowhead.

    Testing "do they share an endpoint?" ALONE is not sound: two segments whose
    ends are a hair apart still cross once, and that crossing can be anywhere
    along the runs.  ``(0,0)->(10,0)`` and ``(0,0.0009)->(10,-0.0009)`` start
    0.9 mm apart (inside ``tol``) yet cross at ``(5, 0)``, 5 mm away (Codex
    #3601319580).  So the crossing POINT must itself be at the shared terminus,
    which is what "buried under the arrowhead" actually means.
    """
    for pa in ((a.x0, a.y0), (a.x1, a.y1)):
        for pb in ((b.x0, b.y0), (b.x1, b.y1)):
            if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) >= tol:
                continue  # not a shared terminus
            if (
                math.hypot(x - pa[0], y - pa[1]) < tol
                and math.hypot(x - pb[0], y - pb[1]) < tol
            ):
                return True
    return False


def _side(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float
) -> float:
    """Signed perpendicular distance of point ``c`` from the line ``ab``, in meters."""
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length == 0.0:  # degenerate segment: no side to be on
        return 0.0
    return (dx * (cy - ay) - dy * (cx - ax)) / length


def proper_crossing(
    a: LeaderSegment, b: LeaderSegment, *, tol: float
) -> tuple[float, float] | None:
    """Where ``a`` and ``b`` cross transversally, or None if they merely touch."""
    d1 = _side(b.x0, b.y0, b.x1, b.y1, a.x0, a.y0)
    d2 = _side(b.x0, b.y0, b.x1, b.y1, a.x1, a.y1)
    d3 = _side(a.x0, a.y0, a.x1, a.y1, b.x0, b.y0)
    d4 = _side(a.x0, a.y0, a.x1, a.y1, b.x1, b.y1)
    # Any endpoint sitting ON the other line (within tol) is a touch, not a
    # crossing -- this is what exempts a bent leader's shared elbow, and it is
    # deliberately the CONSERVATIVE call: a T-junction is ambiguous drafting and
    # a wrong failure here is worse than no call.
    if min(abs(d1), abs(d2), abs(d3), abs(d4)) < tol:
        return None
    if (d1 > 0) == (d2 > 0) or (d3 > 0) == (d4 > 0):
        return None
    # d3/d4 straddle line a with opposite signs, so this lands strictly inside b.
    s = d3 / (d3 - d4)
    return (b.x0 + s * (b.x1 - b.x0), b.y0 + s * (b.y1 - b.y0))


@dataclass(frozen=True)
class LeaderCrossing:
    """Two annotations whose leaders cross each other."""

    a: LeaderSegment
    b: LeaderSegment
    x: float
    y: float

    def describe(self) -> str:
        # The endpoints are part of the message, not debug noise: the labels are
        # SolidWorks' own ("DetailItem372"), which name nothing a reader can find
        # in the source, so without coordinates the finding is unactionable.
        return (
            f"{self.a.kind} {self.a.label!r} and {self.b.kind} {self.b.label!r} "
            f"cross their leaders at ({self.x:.4f}, {self.y:.4f}) -- move an "
            "anchor or a text placement so one routes clear of the other "
            f"[{self.a.label}: ({self.a.x0:.4f},{self.a.y0:.4f})->"
            f"({self.a.x1:.4f},{self.a.y1:.4f}); "
            f"{self.b.label}: ({self.b.x0:.4f},{self.b.y0:.4f})->"
            f"({self.b.x1:.4f},{self.b.y1:.4f})]"
        )


def find_leader_leader_crossings(
    segments: list[LeaderSegment],
    *,
    tol: float = _CROSSING_TOUCH_TOL_M,
    shared_terminus: float = _SHARED_TERMINUS_M,
) -> list[LeaderCrossing]:
    """Every pair of leaders that cross each other.

    ASME leaders may not cross (pen-rod's ``Ra 1.6`` crossing its own
    perpendicularity frame's leader, 2026-07-16).  Segments of the SAME
    annotation are skipped: a bent leader is two segments that meet at an
    elbow, and an annotation cannot cross itself.  Leaders converging on a
    SHARED terminus are skipped too -- see :data:`_SHARED_TERMINUS_M`.
    """
    crossings: list[LeaderCrossing] = []
    for a, b in combinations(segments, 2):
        if a.label == b.label:
            continue
        point = proper_crossing(a, b, tol=tol)
        if point is None:
            continue
        # Locate the crossing BEFORE exempting it: a shared terminus only excuses
        # a crossing that happens AT that terminus.
        if _crossing_is_under_a_shared_terminus(
            a, b, *point, tol=shared_terminus
        ):
            continue
        crossings.append(LeaderCrossing(a, b, *point))
    return crossings


# Two drawing views' footprints may touch but not interpenetrate deeper than
# this on BOTH axes.  ``GetOutline`` pads a view by a few millimetres of
# whitespace, so two legitimately adjacent views can overlap by the padding;
# ~1.5 mm clears that while a view dropped onto another penetrates by
# centimetres (the retired element audit's measured tolerance).
VIEW_OVERLAP_TOL_M = 0.0015

# How much of a line has to run through a text box before it is reported.  A
# 300 dpi render resolves 1/300 in = 0.085 mm, so anything below that is ink no
# reader can see; 0.15 mm gives that a factor of ~1.8 of margin while still
# catching a witness line grazing a digit.
DEFAULT_TEXT_TOUCH_TOL_M = 0.00015

# Two text boxes must penetrate each other by more than this on BOTH axes.  Text
# boxes are exact extents (notes) or width-estimated extents (dimensions), so
# the slack only has to swallow the estimate's error near a legitimate tight
# stack -- 0.3 mm, well under the ~2 mm a genuine text-on-text collision shows.
DEFAULT_TEXT_OVERLAP_TOL_M = 0.0003

# Extra air added to a suggested move, so the nudge clears the obstacle instead
# of landing flush against it: 2 mm reads as deliberate separation at 1:1 and
# still leaves a 3.5 mm text box room on a dense sheet.
DEFAULT_MOVE_CLEARANCE_M = 0.002

# An arrowhead, or an outside arrow's tail, nearer another annotation's text
# than this reads as part of that text (MHA-DT-21 round 2: the 5.56's arrow
# 0.4 mm from "Ra 3.2", the 10.7's inside the 3.97's tolerance stack). The
# fleet rule: the layout audit gates on it, and ``_drawing_leaders`` checks
# placed sheets against it -- one constant, so the two cannot drift.
ARROW_TEXT_CLEARANCE_M = 0.002

# Fallback glyph advance as a fraction of cap height, used to estimate a text
# box's WIDTH: no SolidWorks API returns the rendered width of annotation text
# (``IDisplayData::GetTextInBoxWidthAtIndex`` is table cells only and returns 0
# for everything else).  0.62 is the ratio measured across the shipped sheets'
# notes, whose exact box IS available from ``INote::GetExtent``.  Whenever such
# notes are on the sheet, :func:`calibrate_advance_ratio` replaces this constant
# with the live measurement, so the estimate tracks the template's font.
DEFAULT_ADVANCE_RATIO = 0.62

# Bounds on a calibrated ratio.  A condensed font runs ~0.45, a wide monospace
# ~1.0; anything outside this came from a note whose extent is leader-polluted
# or whose text is empty, and must not poison every dimension box on the sheet.
_ADVANCE_RATIO_BOUNDS = (0.35, 1.2)


@dataclass(frozen=True)
class Box:
    """An axis-aligned sheet-space box in metres."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @classmethod
    def from_points(cls, points: list[tuple[float, float]]) -> Box | None:
        if not points:
            return None
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return cls(min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    def union(self, other: Box) -> Box:
        return Box(
            min(self.xmin, other.xmin),
            min(self.ymin, other.ymin),
            max(self.xmax, other.xmax),
            max(self.ymax, other.ymax),
        )

    def center(self) -> tuple[float, float]:
        return ((self.xmin + self.xmax) / 2.0, (self.ymin + self.ymax) / 2.0)

    def mm(self) -> tuple[float, float, float, float]:
        return (
            self.xmin * MM,
            self.ymin * MM,
            self.xmax * MM,
            self.ymax * MM,
        )

    def format_mm(self) -> str:
        x0, y0, x1, y1 = self.mm()
        return f"[{x0:.1f},{y0:.1f}]..[{x1:.1f},{y1:.1f}]mm"

    def penetration(self, other: Box) -> tuple[float, float]:
        """Overlap depth against ``other`` per axis (negative = a gap)."""
        return (
            min(self.xmax, other.xmax) - max(self.xmin, other.xmin),
            min(self.ymax, other.ymax) - max(self.ymin, other.ymin),
        )

    def overlaps(self, other: Box, *, tol: float) -> tuple[float, float] | None:
        depth_x, depth_y = self.penetration(other)
        if depth_x > tol and depth_y > tol:
            return (depth_x, depth_y)
        return None

    def gap(self, other: Box) -> float:
        """Shortest distance to ``other``; 0.0 when the boxes overlap."""
        depth_x, depth_y = self.penetration(other)
        return math.hypot(max(-depth_x, 0.0), max(-depth_y, 0.0))

    def escape(self, region: DrawableRegion) -> tuple[str, float] | None:
        """The worst side this box crosses ``region`` on, and by how much."""
        breaches = {
            "left": region.xmin - self.xmin,
            "bottom": region.ymin - self.ymin,
            "right": self.xmax - region.xmax,
            "top": self.ymax - region.ymax,
        }
        side, amount = max(breaches.items(), key=lambda item: item[1])
        return (side, amount) if amount > 0 else None


@dataclass(frozen=True)
class Segment:
    """One straight run of annotation ink in sheet metres."""

    x0: float
    y0: float
    x1: float
    y1: float
    role: str = "line"

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    def box(self) -> Box:
        return Box(
            min(self.x0, self.x1),
            min(self.y0, self.y1),
            max(self.x0, self.x1),
            max(self.y0, self.y1),
        )

    def point_at(self, t: float) -> tuple[float, float]:
        return (
            self.x0 + t * (self.x1 - self.x0),
            self.y0 + t * (self.y1 - self.y0),
        )

    def format_mm(self) -> str:
        return (
            f"({self.x0 * MM:.1f},{self.y0 * MM:.1f})->"
            f"({self.x1 * MM:.1f},{self.y1 * MM:.1f})mm"
        )


def clip_segment_to_box(segment: Segment, box: Box) -> tuple[float, float] | None:
    """The ``[t0, t1]`` parameter range of ``segment`` that lies inside ``box``.

    Liang-Barsky slab clipping.  Returns None when the segment misses the box,
    and a degenerate range when it merely grazes a face -- callers gate on the
    resulting LENGTH, not on intersection, so grazing is not a finding.
    """
    t0, t1 = 0.0, 1.0
    for delta, lo, hi, start in (
        (segment.x1 - segment.x0, box.xmin, box.xmax, segment.x0),
        (segment.y1 - segment.y0, box.ymin, box.ymax, segment.y0),
    ):
        if abs(delta) < 1e-12:
            if start < lo or start > hi:
                return None
            continue
        near, far = (lo - start) / delta, (hi - start) / delta
        if near > far:
            near, far = far, near
        t0, t1 = max(t0, near), min(t1, far)
        if t0 > t1:
            return None
    return (t0, t1)


def segment_box_overlap_length(segment: Segment, box: Box) -> float:
    """How much of ``segment``, in metres, runs THROUGH ``box``.

    A run lying exactly on a box edge has zero depth -- a witness line ending
    along the text's edge, a leader tangent to a note -- and reads 0.0, the same
    as a perpendicular touch, so ``find_text_on_line`` cannot report it as ink
    through the text (CodeRabbit, #754).
    """
    span = clip_segment_to_box(segment, box)
    if span is None:
        return 0.0
    if _collinear_with_box_edge(segment, box):
        return 0.0
    return (span[1] - span[0]) * segment.length


def clip_segment_to_circle(
    segment: Segment, circle: tuple[float, float, float]
) -> tuple[float, float] | None:
    """The ``[t0, t1]`` parameter range of ``segment`` inside ``circle``'s disk."""
    cx, cy, radius = circle
    dx, dy = segment.x1 - segment.x0, segment.y1 - segment.y0
    fx, fy = segment.x0 - cx, segment.y0 - cy
    a = dx * dx + dy * dy
    if a == 0.0:
        return (0.0, 0.0) if math.hypot(fx, fy) <= radius else None
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    discriminant = b * b - 4.0 * a * c
    if discriminant <= 0.0:
        return None
    root = math.sqrt(discriminant)
    t0, t1 = max(0.0, (-b - root) / (2.0 * a)), min(1.0, (-b + root) / (2.0 * a))
    return (t0, t1) if t0 <= t1 else None


def text_overlap(
    segment: Segment, annotation: AnnotationGeometry, box: Box, *, inset: float = 0.0
) -> tuple[float, tuple[float, float] | None]:
    """How much of ``segment`` runs through one of ``annotation``'s text boxes.

    Returns the length in metres and the clipped ``[t0, t1]`` range. ``inset``
    shrinks the shape first. A balloon is tested against its circle, not
    against the circle's bounding square: a leader leaving the rim, or a line
    clipping a corner, crosses only blank paper.
    """
    if annotation.circle is not None:
        cx, cy, radius = annotation.circle
        span = clip_segment_to_circle(segment, (cx, cy, radius - inset))
        if span is None:
            return 0.0, None
        return (span[1] - span[0]) * segment.length, span
    test = Box(box.xmin + inset, box.ymin + inset, box.xmax - inset, box.ymax - inset)
    if test.xmin >= test.xmax or test.ymin >= test.ymax:
        return 0.0, None
    return segment_box_overlap_length(segment, test), clip_segment_to_box(segment, test)


def segment_box_distance(segment: Segment, box: Box) -> float:
    """Shortest distance from ``segment`` to ``box``; 0 when it touches or
    enters it."""
    if clip_segment_to_box(segment, box) is not None:
        return 0.0
    corners = ((box.xmin, box.ymin), (box.xmax, box.ymin), (box.xmax, box.ymax), (box.xmin, box.ymax))
    ends = ((segment.x0, segment.y0), (segment.x1, segment.y1))
    return min(
        *(_point_segment_distance(corner, segment) for corner in corners),
        *(math.hypot(max(box.xmin - x, 0.0, x - box.xmax), max(box.ymin - y, 0.0, y - box.ymax)) for x, y in ends),
    )


def point_segment_distance(point: tuple[float, float], segment: Segment) -> float:
    """Shortest distance from ``point`` to ``segment``."""
    return _point_segment_distance(point, segment)


def segment_circle_distance(segment: Segment, circle: tuple[float, float, float]) -> float:
    """Shortest distance from ``segment`` to the disc ``(cx, cy, radius)``;
    0 when it touches or enters it."""
    cx, cy, radius = circle
    return max(0.0, _point_segment_distance((cx, cy), segment) - radius)


def _point_segment_distance(point: tuple[float, float], segment: Segment) -> float:
    dx, dy = segment.x1 - segment.x0, segment.y1 - segment.y0
    squared = dx * dx + dy * dy
    t = 0.0 if squared == 0.0 else max(0.0, min(1.0, ((point[0] - segment.x0) * dx + (point[1] - segment.y0) * dy) / squared))
    return math.hypot(segment.x0 + t * dx - point[0], segment.y0 + t * dy - point[1])


def _collinear_with_box_edge(segment: Segment, box: Box) -> bool:
    """Axis-parallel ``segment`` lying on one of ``box``'s four edge lines."""
    if abs(segment.y1 - segment.y0) < 1e-12:
        return any(abs(segment.y0 - edge) < 1e-9 for edge in (box.ymin, box.ymax))
    if abs(segment.x1 - segment.x0) < 1e-12:
        return any(abs(segment.x0 - edge) < 1e-9 for edge in (box.xmin, box.xmax))
    return False


def union_boxes(boxes: list[Box]) -> Box | None:
    """The single box enclosing every box in ``boxes`` (None when empty)."""
    if not boxes:
        return None
    return Box(
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
    )


def estimate_text_box(
    text: str,
    *,
    anchor: tuple[float, float],
    height: float,
    reference: int = 0,
    angle: float = 0.0,
    advance_ratio: float = DEFAULT_ADVANCE_RATIO,
    line_spacing: float = 1.0,
) -> Box | None:
    """Box a run of annotation text around its anchor.

    ``height`` is the cap height SolidWorks reports
    (``IDisplayData::GetTextHeightAtIndex``, metres).  The WIDTH is estimated --
    see :data:`DEFAULT_ADVANCE_RATIO`; no API returns it.  ``reference`` is the
    anchor corner as ``swTextPosition_e`` (swUPPER_LEFT=0, swLOWER_LEFT=1,
    swCENTER=2, swUPPER_RIGHT=3, swLOWER_RIGHT=4, swUPPER_CENTER=5), which is
    what ``IDisplayData::GetTextRefPositionAtIndex`` returns.  A rotated string
    is boxed by its rotated corners' axis-aligned hull, so a vertical dimension
    is not audited as if it read left to right.
    """
    lines = text.split("\n") if text else []
    if not lines or height <= 0:
        return None
    width = max(len(line) for line in lines) * height * advance_ratio
    total_height = height * (1 + (len(lines) - 1) * max(line_spacing, 1.0))
    if width <= 0:
        return None

    # Local frame: +x along the text, +y up, origin at the anchor corner.
    left = {0: 0.0, 1: 0.0, 2: -width / 2.0, 3: -width, 4: -width, 5: -width / 2.0}[
        reference
    ]
    top = {
        0: 0.0,
        1: total_height,
        2: total_height / 2.0,
        3: 0.0,
        4: total_height,
        5: 0.0,
    }[reference]
    corners = [
        (left, top),
        (left + width, top),
        (left, top - total_height),
        (left + width, top - total_height),
    ]
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return Box.from_points(
        [
            (
                anchor[0] + x * cos_a - y * sin_a,
                anchor[1] + x * sin_a + y * cos_a,
            )
            for x, y in corners
        ]
    )


def calibrate_advance_ratio(
    samples: list[tuple[str, float, Box]],
    *,
    default: float = DEFAULT_ADVANCE_RATIO,
) -> float:
    """Measure the font's glyph advance from text whose box IS exact.

    A note reports BOTH its string and its true sheet extent
    (``INote::GetExtent``), so the sheet carries its own calibration for the one
    quantity :func:`estimate_text_box` cannot query.  Samples are
    ``(text, cap_height, exact_box)``; the median keeps one leader-polluted
    extent from moving the ratio, and out-of-range results fall back to
    ``default`` rather than poisoning every dimension box on the sheet.
    """
    ratios = []
    for text, height, box in samples:
        lines = [line for line in text.split("\n") if line] if text else []
        if not lines or height <= 0 or box.width <= 0:
            continue
        ratios.append(box.width / (max(len(line) for line in lines) * height))
    if not ratios:
        return default
    ratio = median(ratios)
    low, high = _ADVANCE_RATIO_BOUNDS
    return ratio if low <= ratio <= high else default


@dataclass(frozen=True)
class LeaderInkAmbiguity:
    """A balloon leader whose printed start the PDF does not settle: several
    printed strokes run from its first segment's far end (``tip``) to a start
    on or inside the printed ring (``starts``)."""

    tip: tuple[float, float]
    starts: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class AnnotationGeometry:
    """One annotation's on-sheet ink, as the audit sees it."""

    label: str
    kind: str
    owner: str
    text_boxes: tuple[Box, ...] = ()
    segments: tuple[Segment, ...] = ()
    position: tuple[float, float] | None = None
    exact: bool = False
    # A BOM balloon's printed body: ``(cx, cy, radius)``. Its one text box is
    # the circle's bounding square, whose corners are blank paper, so line and
    # gap tests read the circle instead (``text_overlap``).
    circle: tuple[float, float, float] | None = None
    # Balloon leaders whose printed start is ambiguous; each keeps its COM
    # start and is reported (``find_ambiguous_leader_ink``).
    leader_ink_ambiguities: tuple[LeaderInkAmbiguity, ...] = ()

    def box(self) -> Box | None:
        """The annotation's whole footprint: text plus its own ink."""
        return union_boxes(
            [*self.text_boxes, *(segment.box() for segment in self.segments)]
        )

    def leader_segments(self) -> tuple[Segment, ...]:
        return tuple(s for s in self.segments if s.role == "leader")


@dataclass(frozen=True)
class ViewGeometry:
    """A drawing view's sheet-space footprint and display settings."""

    name: str
    outline: Box | None
    scale: tuple[float, float] = (1.0, 1.0)
    display_mode: int = -1
    uses_parent_display: bool = False
    faceted_hlr: bool = False
    view_type: int = -1
    # An isometric/dimetric/trimetric or octant view: its axis-aligned outline is
    # mostly empty diagonal space, so a leader clipping that box is not a
    # crossing and nothing overlaps it.
    pictorial: bool = False


@dataclass(frozen=True)
class SheetGeometry:
    """Everything one drawing sheet contributes to the audit."""

    name: str
    width: float
    height: float
    region: DrawableRegion
    keep_outs: tuple[tuple[str, Box], ...] = ()
    views: tuple[ViewGeometry, ...] = ()
    annotations: tuple[AnnotationGeometry, ...] = ()
    advance_ratio: float = DEFAULT_ADVANCE_RATIO


@dataclass(frozen=True)
class Finding:
    """One layout defect, with the millimetre coordinates needed to fix it."""

    kind: str
    sheet: str
    detail: str
    a: str = ""
    b: str = ""
    at_mm: tuple[float, float] | None = None
    move_target_mm: tuple[float, float] | None = None
    extra: dict[str, float] = field(default_factory=dict)

    def format(self) -> str:
        where = f" at ({self.at_mm[0]:.1f},{self.at_mm[1]:.1f})mm" if self.at_mm else ""
        return f"[{self.kind}] {self.sheet}: {self.detail}{where}"

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "sheet": self.sheet,
            "a": self.a,
            "b": self.b,
            "detail": self.detail,
            "at_mm": list(self.at_mm) if self.at_mm else None,
            "move_target_mm": (
                list(self.move_target_mm) if self.move_target_mm else None
            ),
            **{key: value for key, value in self.extra.items()},
        }


def _free_direction_mm(box: Box, obstacle: Box) -> tuple[float, float]:
    """Where to move ``box`` (in sheet mm) to clear ``obstacle`` the cheapest way.

    The four escapes are "push out past each of the obstacle's faces"; the
    shortest wins.  This is advice for the author, not a placement algorithm --
    it turns a finding into a concrete ``SetPosition2`` starting point instead
    of another round of guessing.
    """
    depth_x, depth_y = box.penetration(obstacle)
    moves = {
        (-(depth_x + DEFAULT_MOVE_CLEARANCE_M), 0.0): depth_x,
        (depth_x + DEFAULT_MOVE_CLEARANCE_M, 0.0): depth_x,
        (0.0, -(depth_y + DEFAULT_MOVE_CLEARANCE_M)): depth_y,
        (0.0, depth_y + DEFAULT_MOVE_CLEARANCE_M): depth_y,
    }
    dx, dy = min(moves, key=lambda move: moves[move])
    x, y = box.center()
    return ((x + dx) * MM, (y + dy) * MM)


# Cell size of the segment grid ``find_text_on_line`` buckets ink into: about
# one row of text, so a box touches a handful of cells.
SEGMENT_GRID_M = 0.005


class SegmentGrid:
    """Segments bucketed by the grid cells their bounding boxes cover.

    A PDF-measured sheet carries thousands of model-edge pieces; testing
    every text box against every one of them runs while the build holds the
    COM seat. ``near(box)`` returns only the segments whose cells the box
    touches, in insertion order, each once.
    """

    def __init__(self, segments: Iterable[tuple[int, Segment]], cell: float = SEGMENT_GRID_M) -> None:
        self.cell = cell
        self.cells: dict[tuple[int, int], list[int]] = {}
        self.items: list[tuple[int, Segment]] = []
        for owner, segment in segments:
            index = len(self.items)
            self.items.append((owner, segment))
            for key in self._keys(segment.box()):
                self.cells.setdefault(key, []).append(index)

    def _keys(self, box: Box) -> Iterable[tuple[int, int]]:
        for i in range(math.floor(box.xmin / self.cell), math.floor(box.xmax / self.cell) + 1):
            for j in range(math.floor(box.ymin / self.cell), math.floor(box.ymax / self.cell) + 1):
                yield (i, j)

    def near(self, box: Box) -> list[tuple[int, Segment]]:
        found = sorted({index for key in self._keys(box) for index in self.cells.get(key, ())})
        return [self.items[index] for index in found]


def find_text_on_line(
    sheet: SheetGeometry, *, tol: float = DEFAULT_TEXT_TOUCH_TOL_M
) -> list[Finding]:
    """Every text box a line segment runs through that is not its own ink.

    drawing-guidelines.md rule 14 (keep text off the part)'s "no text sits on a line", enforced at last: each
    annotation's dimension line, witness lines and leader come back from
    ``IDisplayDimension::GetDisplayData`` as real rendered segments, so a
    callout parked on a neighbour's extension line is a measurable overlap
    length rather than something only the PDF can show.
    """
    findings: list[Finding] = []
    grid = SegmentGrid(
        (owner, segment)
        for owner, annotation in enumerate(sheet.annotations)
        for segment in annotation.segments
    )
    for target in sheet.annotations:
        for box in target.text_boxes:
            for owner, segment in grid.near(box):
                source = sheet.annotations[owner]
                if source.label == target.label:
                    continue
                length, span = text_overlap(segment, target, box)
                if length <= tol:
                    continue
                mid = segment.point_at(sum(span) / 2.0) if span else box.center()
                findings.append(
                    Finding(
                        kind="text-on-line",
                        sheet=sheet.name,
                        a=target.label,
                        b=source.label,
                        detail=(
                            f"text of {target.label!r} {box.format_mm()} is "
                            f"crossed by {source.label!r}'s {segment.role} "
                            f"{segment.format_mm()} over "
                            f"{length * MM:.2f}mm"
                        ),
                        at_mm=(mid[0] * MM, mid[1] * MM),
                        move_target_mm=_free_direction_mm(box, segment.box()),
                        extra={
                            "overlap_mm": length * MM,
                            "segment": (segment.x0, segment.y0, segment.x1, segment.y1),
                        },
                    )
                )
    return findings


def find_border_breaches(sheet: SheetGeometry) -> list[Finding]:
    """Annotations crossing the inner border or landing in a keep-out.

    Notes / tables / dimension text are EXACT or width-estimated extents, not
    padded view outlines, so they get no outward allowance here: an allowance
    for ``IView::GetOutline`` padding would hide a real clip on text.
    """
    findings: list[Finding] = []
    for annotation in sheet.annotations:
        box = annotation.box()
        if box is None:
            continue
        escape = box.escape(sheet.region)
        if escape is not None:
            side, amount = escape
            findings.append(
                Finding(
                    kind="outside-border",
                    sheet=sheet.name,
                    a=annotation.label,
                    b=f"{side} border",
                    detail=(
                        f"{annotation.kind} {annotation.label!r} {box.format_mm()} "
                        f"crosses the {side} inner border by {amount * MM:.2f}mm"
                    ),
                    at_mm=tuple(value * MM for value in box.center()),
                    extra={"breach_mm": amount * MM},
                )
            )
        for keep_out_name, keep_out in sheet.keep_outs:
            depth = box.overlaps(keep_out, tol=DEFAULT_TEXT_OVERLAP_TOL_M)
            if depth is None:
                continue
            findings.append(
                Finding(
                    kind="keep-out",
                    sheet=sheet.name,
                    a=annotation.label,
                    b=keep_out_name,
                    detail=(
                        f"{annotation.kind} {annotation.label!r} {box.format_mm()} "
                        f"intrudes into {keep_out_name} {keep_out.format_mm()} by "
                        f"{depth[0] * MM:.2f}x{depth[1] * MM:.2f}mm"
                    ),
                    at_mm=tuple(value * MM for value in box.center()),
                    move_target_mm=_free_direction_mm(box, keep_out),
                )
            )
    return findings


def find_leader_crossings(
    sheet: SheetGeometry, *, inset: float = DEFAULT_CROSSING_INSET_M
) -> list[Finding]:
    """Leaders crossing a foreign view outline, or each other.

    An annotation's leader must reach its own view (``owner``), so that view is
    skipped; any OTHER view's interior, inset by ``inset`` for ``GetOutline``'s
    padding, is off limits. PICTORIAL views are skipped: an isometric view's
    axis-aligned outline is mostly EMPTY diagonal space, so its box is not
    evidence of ink (codex #334).
    """
    segments = [
        LeaderSegment(
            annotation.label,
            annotation.kind,
            segment.x0,
            segment.y0,
            segment.x1,
            segment.y1,
            annotation.owner,
        )
        for annotation in sheet.annotations
        for segment in annotation.leader_segments()
    ]
    views = [
        (view.name, (view.outline.xmin, view.outline.ymin, view.outline.xmax, view.outline.ymax))
        for view in sheet.views
        if view.outline is not None and not view.pictorial
    ]
    findings: list[Finding] = []
    for segment in segments:
        for name, outline in views:
            if name == segment.owner or not segment_crosses_box(segment, outline, inset=inset):
                continue
            findings.append(
                Finding(
                    kind="leader-crosses-view",
                    sheet=sheet.name,
                    a=segment.label,
                    b=name,
                    detail=(
                        f"{segment.kind} {segment.label!r} runs its leader across "
                        f"view {name!r} -- move the anchor or the text placement"
                    ),
                )
            )
    for crossing in find_leader_leader_crossings(segments):
        findings.append(
            Finding(
                kind="leader-crosses-leader",
                sheet=sheet.name,
                a=crossing.a.label,
                b=crossing.b.label,
                detail=crossing.describe(),
                at_mm=(crossing.x * MM, crossing.y * MM),
            )
        )
    return findings
