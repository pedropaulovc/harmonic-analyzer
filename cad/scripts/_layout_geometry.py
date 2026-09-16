"""Sheet-space geometry for the ANNOTATION-level drawing layout audit.

``_drawing_layout_check`` audits the drawing at ELEMENT level: view outlines,
free notes, tables, and leader routes.  It deliberately boxes every dimension,
hole callout and GD&T symbol as a small nominal square with
``CollisionScope.NONE`` -- there is no bounding-box API for annotation text, so
those boxes are guesses and may only be overflow-checked, never collision-checked.

That leaves the defect class that actually cost six agents an afternoon
invisible to every gate: dimension TEXT sitting on a dimension LINE, two
callouts printing on top of each other, and one view's callouts crowding the
next view's.  Those are only visible in the exported PDF, five to thirteen
minutes after the mistake.

This module supplies the geometry for auditing them from the live document, and
is deliberately SolidWorks-free so the math is unit-testable without a COM
seat.  Everything here is SHEET space in METRES (the unit every SolidWorks
annotation API returns); findings are reported in millimetres because that is
what an author types back into ``IAnnotation::SetPosition2``.

Division of labour with ``_drawing_layout_check``:

* Leader-vs-view-outline and leader-vs-leader crossings are ITS questions, and
  :func:`find_leader_crossings` delegates to it rather than restating the
  tolerance reasoning (shared-terminus arrowheads, transversal-only crossings,
  ``GetOutline`` padding) that module already measured and calibrated.
* The primitive here that module does not have is a segment/box overlap
  LENGTH (:func:`segment_box_overlap_length`).  Its leader check asks a boolean
  "does this leader enter that padded view box"; a text box is an EXACT extent
  a few millimetres wide, so the question is how much ink actually runs through
  the text -- a line clipping a glyph corner by 20 um is not a collision, a
  line crossing the middle of the string is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations, product
from statistics import median

from _drawing_layout_check import (
    DEFAULT_CROSSING_INSET_M,
    DrawableRegion,
    LayoutElement,
    LeaderSegment,
    find_leader_crossings as _find_leader_view_crossings,
    find_leader_leader_crossings as _find_leader_leader_crossings,
)

MM = 1000.0

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
    """How much of ``segment``, in metres, runs inside ``box``."""
    span = clip_segment_to_box(segment, box)
    if span is None:
        return 0.0
    return (span[1] - span[0]) * segment.length


def union_boxes(boxes: list[Box]) -> Box | None:
    """The single box enclosing every box in ``boxes`` (None when empty)."""
    if not boxes:
        return None
    total = boxes[0]
    for box in boxes[1:]:
        total = total.union(box)
    return total


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
class AnnotationGeometry:
    """One annotation's on-sheet ink, as the audit sees it."""

    label: str
    kind: str
    owner: str
    text_boxes: tuple[Box, ...] = ()
    segments: tuple[Segment, ...] = ()
    position: tuple[float, float] | None = None
    exact: bool = False

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


def find_text_on_line(
    sheet: SheetGeometry, *, tol: float = DEFAULT_TEXT_TOUCH_TOL_M
) -> list[Finding]:
    """Every text box a line segment runs through that is not its own ink.

    Policy rule 8's "no text sits on a line", enforced at last: each
    annotation's dimension line, witness lines and leader come back from
    ``IDisplayDimension::GetDisplayData`` as real rendered segments, so a
    callout parked on a neighbour's extension line is a measurable overlap
    length rather than something only the PDF can show.
    """
    findings: list[Finding] = []
    for target in sheet.annotations:
        for box in target.text_boxes:
            for source in sheet.annotations:
                if source.label == target.label:
                    continue
                for segment in source.segments:
                    length = segment_box_overlap_length(segment, box)
                    if length <= tol:
                        continue
                    span = clip_segment_to_box(segment, box)
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
                            extra={"overlap_mm": length * MM},
                        )
                    )
    return findings


def find_text_on_text(
    sheet: SheetGeometry, *, tol: float = DEFAULT_TEXT_OVERLAP_TOL_M
) -> list[Finding]:
    """Every pair of annotation text boxes that print on top of each other."""
    findings: list[Finding] = []
    boxed = [
        (annotation, box)
        for annotation in sheet.annotations
        for box in annotation.text_boxes
    ]
    for (first, box_a), (second, box_b) in combinations(boxed, 2):
        if first.label == second.label:
            continue
        depth = box_a.overlaps(box_b, tol=tol)
        if depth is None:
            continue
        overlap_center = Box(
            max(box_a.xmin, box_b.xmin),
            max(box_a.ymin, box_b.ymin),
            min(box_a.xmax, box_b.xmax),
            min(box_a.ymax, box_b.ymax),
        ).center()
        findings.append(
            Finding(
                kind="text-on-text",
                sheet=sheet.name,
                a=first.label,
                b=second.label,
                detail=(
                    f"text of {first.label!r} {box_a.format_mm()} overlaps "
                    f"{second.label!r} {box_b.format_mm()} by "
                    f"{depth[0] * MM:.2f}x{depth[1] * MM:.2f}mm"
                ),
                at_mm=(overlap_center[0] * MM, overlap_center[1] * MM),
                move_target_mm=_free_direction_mm(box_a, box_b),
                extra={"depth_x_mm": depth[0] * MM, "depth_y_mm": depth[1] * MM},
            )
        )
    return findings


def find_border_breaches(sheet: SheetGeometry) -> list[Finding]:
    """Annotations crossing the inner border or landing in a keep-out.

    Notes / tables / dimension text are EXACT or width-estimated extents, not
    padded view outlines, so they get no outward allowance here -- the allowance
    in ``_drawing_layout_check`` exists for ``IView::GetOutline`` padding and
    would hide a real clip on text.
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


def find_view_crowding(sheet: SheetGeometry) -> list[Finding]:
    """Two views whose callouts are squeezed together -- the ADD-A-SHEET signal.

    Policy rule 8 names this exact diagnostic: "callouts, dimensions, or notes
    belonging to one view or section overlapping, or being squeezed against,
    those of another".  The remedy is a new sheet, not a smaller scale, so this
    is reported apart from an ordinary box collision.

    Measured as the shortest gap between an ACTUAL PAIR of text boxes owned by
    different views, and reported once per view pair (the closest pair).  The
    first cut of this check compared the UNION box of each view's text, which
    on tube-frame reported 'Drawing View1' against 'Drawing View2' because View1
    owns a note at the top of the sheet and dimensions at the bottom: the union
    spanned 320 mm of sheet that View1's text does not occupy.  A union box is
    not evidence of anything on a tall sparse sheet.

    The clearance demanded is one text height of the SMALLER box -- the air a
    reader needs to tell one view's callouts from the next one's, and it scales
    with the sheet's own text instead of hard-coding a millimetre count.  Boxes
    that actually overlap are left to :func:`find_text_on_text`; this finding is
    about the near miss that says the sheet is full.
    """
    owned: dict[str, list[tuple[str, Box]]] = {}
    for annotation in sheet.annotations:
        if annotation.owner in ("", "sheet"):
            continue
        box = union_boxes(list(annotation.text_boxes))
        if box is None:
            continue
        owned.setdefault(annotation.owner, []).append((annotation.label, box))

    findings: list[Finding] = []
    for (owner_a, items_a), (owner_b, items_b) in combinations(
        sorted(owned.items()), 2
    ):
        closest: tuple[float, str, str, Box, Box] | None = None
        for (label_a, box_a), (label_b, box_b) in product(items_a, items_b):
            clearance = min(box_a.height, box_b.height)
            gap = box_a.gap(box_b)
            if gap <= 0.0 or gap >= clearance:
                continue
            if closest is None or gap < closest[0]:
                closest = (gap, label_a, label_b, box_a, box_b)
        if closest is None:
            continue
        gap, label_a, label_b, box_a, box_b = closest
        findings.append(
            Finding(
                kind="view-crowding",
                sheet=sheet.name,
                a=label_a,
                b=label_b,
                detail=(
                    f"{label_a!r} of {owner_a!r} {box_a.format_mm()} and "
                    f"{label_b!r} of {owner_b!r} {box_b.format_mm()} are only "
                    f"{gap * MM:.2f}mm apart, under one text height "
                    f"({min(box_a.height, box_b.height) * MM:.2f}mm) -- move one "
                    "view, or its annotations, to another sheet"
                ),
                at_mm=tuple(value * MM for value in box_a.center()),
                extra={"gap_mm": gap * MM, "owner_a": owner_a, "owner_b": owner_b},
            )
        )
    return findings


def find_leader_crossings(
    sheet: SheetGeometry, *, inset: float = DEFAULT_CROSSING_INSET_M
) -> list[Finding]:
    """Leaders crossing a foreign view outline, or each other.

    Delegated to ``_drawing_layout_check`` so the calibrated tolerances
    (``GetOutline`` padding inset, shared-terminus arrowheads, transversal-only
    crossings) stay in the one module that measured them.
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
        LayoutElement(
            view.name,
            "view",
            view.outline.xmin,
            view.outline.ymin,
            view.outline.xmax,
            view.outline.ymax,
        )
        for view in sheet.views
        if view.outline is not None
    ]
    findings: list[Finding] = []
    for crossing in _find_leader_view_crossings(segments, views, inset=inset):
        findings.append(
            Finding(
                kind="leader-crosses-view",
                sheet=sheet.name,
                a=crossing.segment.label,
                b=crossing.view.label,
                detail=crossing.describe(),
            )
        )
    for crossing in _find_leader_leader_crossings(segments):
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


def audit_sheet(sheet: SheetGeometry) -> list[Finding]:
    """Every annotation-level layout finding on one sheet.

    Safe on a sheet with zero annotations: every finder iterates collections
    that are simply empty, and returns nothing.
    """
    return [
        *find_text_on_line(sheet),
        *find_text_on_text(sheet),
        *find_border_breaches(sheet),
        *find_leader_crossings(sheet),
        *find_view_crowding(sheet),
    ]


def format_findings(findings: list[Finding]) -> str:
    """One human-readable block, grouped by finding kind."""
    if not findings:
        return "  (none)"
    lines = []
    for kind in sorted({finding.kind for finding in findings}):
        matching = [finding for finding in findings if finding.kind == kind]
        lines.append(f"  {kind} ({len(matching)}):")
        for finding in matching:
            lines.append(f"    - {finding.format()}")
            if finding.move_target_mm is not None:
                x, y = finding.move_target_mm
                lines.append(
                    f"      try SetPosition2({x / MM:.5f}, {y / MM:.5f}, 0.0)"
                    f"  # ({x:.1f},{y:.1f})mm"
                )
    return "\n".join(lines)
