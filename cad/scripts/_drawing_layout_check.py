"""Pure-geometry layout audit for manufacturing drawings.

Every finished print must lay out cleanly on its sheet: no two drawing
elements (views, standalone notes, tables) may collide, and nothing may run
off the sheet.  A drawing can pass every dimensional/format gate and still be
unreadable because a note landed on a view or a schedule overhangs the border.

This module is deliberately SolidWorks-free: it operates on plain
``(xmin, ymin, xmax, ymax)`` boxes in sheet meters so the collision/containment
logic is unit-testable without a COM seat.  ``_drawing_common.check_drawing_layout``
supplies the boxes from live ``IView.GetOutline`` / ``INote.GetExtent`` /
``ITableAnnotation`` calls and raises on any finding, right before the drawing
is saved.

Two calibration facts drive the tolerances (both measured on the shipped
drawings):

* ``IView.GetOutline`` pads a few millimetres of whitespace around the geometry
  and around any attached dimensions, so an on-sheet view can report an outline
  that pokes ~1-2 mm past the sheet edge.  The overflow test therefore allows a
  small OUTWARD ``allowance`` before flagging, rather than insetting a margin.
* An isometric (or other pictorial) view's axis-aligned outline is mostly empty
  diagonal space, so a note sitting in that empty corner "overlaps" the box
  without touching any geometry.

Two axes of element behaviour, both driven by *why* a box is not a faithful
collision footprint, keep the audit from either false-positiving or missing a
real defect (Codex #269):

* ``CollisionScope`` says *which* other elements an element may collide with.
  A pictorial view's axis-aligned outline is mostly empty diagonal space, and a
  GD&T symbol / dimension carries only a coarse nominal box, so both collide with
  ``NONE``.  A leadered callout / on-view tag legitimately sits over the ONE view
  it points at (its ``owner``) but must NOT overlap a free note, a table, a
  DIFFERENT view, or the title block -- it collides with ``NON_VIEW``.  Everything
  else (ortho views, free notes, tables) collides with ``ALL``.  The reserved
  ``titleblock`` boxes are a hard KEEP-OUT: every element is checked against them
  regardless of its scope (so an otherwise-exempt pictorial view / GD&T / dim
  dropped on the title block is still caught), and they never collide with each
  other.
* The OVERFLOW allowance applies only to ``view`` boxes.  ``IView.GetOutline``
  pads whitespace, so an on-sheet view can poke a millimetre or two past an edge;
  notes / tables / GD&T carry EXACT extents, so any overhang is a real clip and
  gets zero slack.

Every element -- whatever its scope -- is still checked for OVERFLOW, so a
pictorial view or leadered note mis-placed off the sheet is always caught.

Two further audits keep a print readable rather than merely well-boxed:

* OVERFLOW is measured against the sheet's ZONE FRAME (:class:`DrawableRegion`),
  not the raw sheet rectangle.  The border/zone band carrying the A/B and 1..4
  zone labels is reserved by the sheet format, so an element that stops inside
  the paper but crosses into that band is still a defect.  The region is QUERIED
  from the live sheet (``ISheet::GetZoneMargin``) -- it is sheet metadata, never
  a measured constant, so it tracks a template edit automatically.
* LEADER CROSSINGS (:func:`find_leader_crossings`).  A bounding box cannot see a
  leader line: the shipped crank-arm sheet ran its ``Ra 1.6`` leader as one long
  diagonal straight THROUGH the top view to reach the front view's bore, and
  every box-based check passed.  A leader may land on the view it annotates (its
  ``owner``), but crossing any OTHER view's interior is a defect -- fix it by
  moving the anchor or the text placement.
* LEADER-vs-LEADER crossings (:func:`find_leader_leader_crossings`).  ASME
  leaders may not cross each other, and this fell between the other checks: the
  box audits cannot see a leader, and the check above compares leaders only
  against VIEW outlines.  Two independent findings in one review round proved
  the gap real -- pen-rod's ``Ra 1.6`` crossing its own perpendicularity frame's
  leader, and ``_spread_balloons``' docstring promising non-crossing balloon
  leaders that it never delivered.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from itertools import combinations


class CollisionScope(Enum):
    """Which other elements an element is allowed to collide with.

    Overlap is symmetric: a pair is audited only when *both* elements admit the
    other (see :func:`_may_collide`).
    """

    ALL = "all"  # ortho views, free notes, tables, the reserved title block
    NON_VIEW = "non_view"  # leadered callouts, GD&T, on-view tags: not vs views
    NONE = "none"  # pictorial views: box is empty diagonal space, never collides


# A collision is only reported when two boxes penetrate each other by more than
# this depth on BOTH axes, so the ``GetOutline`` padding on two legitimately
# adjacent views cannot masquerade as interference.  ~1.5 mm clears the padding
# while a note dropped onto a view penetrates by centimetres.
DEFAULT_OVERLAP_TOL_M = 0.0015

# How far an element's (padded) box may extend past the physical sheet edge
# before it counts as running off the sheet.  Absorbs ``GetOutline`` padding; a
# grossly mis-placed note/table still overhangs by far more than this.
DEFAULT_BOUNDARY_ALLOWANCE_M = 0.003


@dataclass(frozen=True)
class LayoutElement:
    """One laid-out drawing object and its sheet-space bounding box (meters).

    ``scope`` says which other elements this one may collide with (a pictorial
    view collides with ``NONE``; a leadered callout / GD&T / on-view tag with
    ``NON_VIEW`` only; everything else with ``ALL``).  ``kind == "view"`` boxes
    are ``GetOutline``-padded, so only they receive the OVERFLOW allowance.
    """

    label: str
    kind: str  # "view" | "note" | "table" | "dim" | "gdt" | "titleblock"
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    scope: CollisionScope = CollisionScope.ALL
    # For a NON_VIEW annotation, the label of the view it points at / sits on --
    # it is exempt from colliding with THAT view only, not other drawing views.
    owner: str = ""

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.xmin, self.ymin, self.xmax, self.ymax)


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
class Overlap:
    a: LayoutElement
    b: LayoutElement
    depth_x: float
    depth_y: float

    def describe(self) -> str:
        return (
            f"{self.a.kind} {self.a.label!r} overlaps {self.b.kind} "
            f"{self.b.label!r} by {self.depth_x * 1000:.1f} x "
            f"{self.depth_y * 1000:.1f} mm"
        )


@dataclass(frozen=True)
class Overflow:
    element: LayoutElement
    # signed metre overruns per side; only sides that breach are populated
    sides: tuple[tuple[str, float], ...]

    def describe(self) -> str:
        breaches = ", ".join(
            f"{side} by {amount * 1000:.1f} mm" for side, amount in self.sides
        )
        return (
            f"{self.element.kind} {self.element.label!r} crosses the sheet zone "
            f"border: {breaches}"
        )


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


@dataclass(frozen=True)
class Crossing:
    segment: LeaderSegment
    view: LayoutElement

    def describe(self) -> str:
        return (
            f"{self.segment.kind} {self.segment.label!r} runs its leader across "
            f"view {self.view.label!r} -- move the anchor or the text placement"
        )


def _segment_crosses_box(
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


def find_leader_crossings(
    segments: list[LeaderSegment],
    elements: list[LayoutElement],
    *,
    inset: float = DEFAULT_CROSSING_INSET_M,
) -> list[Crossing]:
    """Every leader segment that runs through a view it does not annotate.

    An annotation's leader must reach its own view (``owner``), so that view is
    skipped.  Any OTHER view's interior is off limits: a leader crossing it is
    the defect a bounding-box audit structurally cannot see.

    Scope, stated honestly: this compares leaders against view OUTLINES, not
    against the actual drawn edges inside a view.  It therefore catches a leader
    driven across a NEIGHBOURING view (the real, repeated defect) and does not
    attempt to judge a leader's path within its own view -- that needs real
    geometry, and a wrong call there would be worse than no call.

    PICTORIAL views are skipped, for exactly the reason ``_view_scope`` already
    gives them ``CollisionScope.NONE``: an isometric view's axis-aligned outline
    is mostly EMPTY diagonal space, so its box is not evidence of ink.  Judging
    leaders against it would fail a leader that merely clips an empty corner --
    re-introducing, in this audit, the false positive the overlap audit
    deliberately avoids.  Keying on ``kind == "view"`` alone is what let that in
    (codex #334).
    """
    views = [
        element
        for element in elements
        if element.kind == "view" and element.scope is not CollisionScope.NONE
    ]
    crossings: list[Crossing] = []
    for segment in segments:
        for view in views:
            if view.label == segment.owner:
                continue
            if _segment_crosses_box(segment, view.box, inset=inset):
                crossings.append(Crossing(segment, view))
    return crossings


# Two leaders that merely TOUCH are not a crossing, and the distinction has to
# be geometric rather than a fudge factor: a BENT leader's elbow and tail share
# an endpoint BY CONSTRUCTION, and two arrows landing on one edge is a stacking
# question the overlap audit owns.  Only a TRANSVERSAL crossing -- each segment
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
# them: whatever the segments do in there, no reader can see a crossing.  Stacked
# arrows ARE a defect -- just a different one, that a human owns (the audit has
# no view of arrowhead geometry).
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


def _shares_a_terminus(a: LeaderSegment, b: LeaderSegment, *, tol: float) -> bool:
    """True if any endpoint of ``a`` coincides with any endpoint of ``b``."""
    ends_a = ((a.x0, a.y0), (a.x1, a.y1))
    ends_b = ((b.x0, b.y0), (b.x1, b.y1))
    return any(
        math.hypot(pa[0] - pb[0], pa[1] - pb[1]) < tol
        for pa in ends_a
        for pb in ends_b
    )


def _side(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float
) -> float:
    """Signed perpendicular distance of point ``c`` from the line ``ab``, in meters."""
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length == 0.0:  # degenerate segment: no side to be on
        return 0.0
    return (dx * (cy - ay) - dy * (cx - ax)) / length


def _proper_crossing(
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

    ASME leaders may not cross.  Nothing was watching for this: the box audits
    cannot see a leader at all, and :func:`find_leader_crossings` compares
    leaders against VIEW outlines -- so leader-vs-LEADER fell between them.  Two
    independent findings landed in the same review round (2026-07-16): pen-rod's
    ``Ra 1.6`` crossing its own perpendicularity frame's leader at (0.0805,
    0.0959), and ``_spread_balloons`` promising non-crossing balloon leaders it
    never delivered.  Both are this gate's shape.

    The pen-rod case is the instructive one -- its source comment reasoned that
    the Ra "passes below ... the squareness frame, [which starts] at y>=0.095",
    which is TRUE OF THE BOX and false of the box's LEADER, descending from it to
    the rod at y~0.091.  Reasoning about an annotation while forgetting its
    leader is exactly the error a machine check does not make.

    Segments of the SAME annotation are skipped: a bent leader is two segments
    that meet at an elbow, and an annotation cannot cross itself.  Leaders
    converging on a SHARED terminus are skipped too -- see
    :data:`_SHARED_TERMINUS_M`; that pair is stacked, not crossed, and the gate's
    first sweep proved the difference is 0.2 mm vs 4.7 mm rather than a judgement
    call.
    """
    crossings: list[LeaderCrossing] = []
    for a, b in combinations(segments, 2):
        if a.label == b.label:
            continue
        if _shares_a_terminus(a, b, tol=shared_terminus):
            continue
        point = _proper_crossing(a, b, tol=tol)
        if point is not None:
            crossings.append(LeaderCrossing(a, b, *point))
    return crossings


def _penetration(a: LayoutElement, b: LayoutElement) -> tuple[float, float]:
    """Overlap depth of two boxes on each axis (negative = a gap on that axis)."""
    depth_x = min(a.xmax, b.xmax) - max(a.xmin, b.xmin)
    depth_y = min(a.ymax, b.ymax) - max(a.ymin, b.ymin)
    return depth_x, depth_y


def _may_collide(a: LayoutElement, b: LayoutElement) -> bool:
    """True if the pair ``(a, b)`` is eligible for overlap auditing.

    A ``titleblock`` element is a hard KEEP-OUT: nothing may cover it whatever
    its scope (a pictorial view, GD&T symbol, or dimension dropped on the title
    block is caught even though it is otherwise overlap-exempt) -- but two
    keep-out boxes do not collide with each other.

    Otherwise a ``NONE``-scope element never collides.  A ``NON_VIEW`` element
    collides with anything except the ONE view it owns (points at / sits on),
    so a leadered callout or tag that strays onto a free note, a table, or a
    DIFFERENT drawing view is still caught.
    """
    a_keep, b_keep = a.kind == "titleblock", b.kind == "titleblock"
    if a_keep and b_keep:
        return False
    if a_keep or b_keep:
        return True
    if a.scope is CollisionScope.NONE or b.scope is CollisionScope.NONE:
        return False
    if a.scope is CollisionScope.NON_VIEW and b.kind == "view" and b.label == a.owner:
        return False
    if b.scope is CollisionScope.NON_VIEW and a.kind == "view" and a.label == b.owner:
        return False
    return True


# Kinds whose box is an EXACT extent -- no GetOutline padding, no nominal guess.
# Two of them overlapping by any real amount is a true collision, so the padding
# tolerance (calibrated for fuzzy view outlines) must NOT apply: a note shifted
# 1 mm into a table or the title block has to be caught (Codex #269).
_EXACT_KINDS = frozenset({"note", "table", "titleblock"})
# A hair of slack for exact pairs too, only to swallow floating-point noise on
# boxes that merely touch -- far below the ~1 mm real overlaps we must catch.
_EXACT_OVERLAP_TOL_M = 0.0002


def _pair_overlap_tol(a: LayoutElement, b: LayoutElement, padded_tol: float) -> float:
    """The padding tolerance applies only when a FUZZY box (a padded view outline
    or a nominal GD&T / dimension box) is in the pair; two EXACT boxes (note /
    table / title block) get near-zero slack."""
    if a.kind in _EXACT_KINDS and b.kind in _EXACT_KINDS:
        return _EXACT_OVERLAP_TOL_M
    return padded_tol


def find_overlaps(
    elements: list[LayoutElement], *, overlap_tol: float = DEFAULT_OVERLAP_TOL_M
) -> list[Overlap]:
    """Every eligible pair of elements that mutually penetrate past their slack.

    A real 2D collision needs positive penetration on BOTH axes; requiring the
    *smaller* penetration to clear the tolerance rejects the whitespace padding
    that ``GetOutline`` adds to adjacent views.  That padding slack applies only
    to pairs involving a fuzzy box -- two EXACT boxes get near-zero slack (see
    :func:`_pair_overlap_tol`).  Pair eligibility follows each element's
    ``CollisionScope`` (see :func:`_may_collide`).
    """
    overlaps: list[Overlap] = []
    for i in range(len(elements)):
        for j in range(i + 1, len(elements)):
            a, b = elements[i], elements[j]
            if not _may_collide(a, b):
                continue
            depth_x, depth_y = _penetration(a, b)
            if min(depth_x, depth_y) > _pair_overlap_tol(a, b, overlap_tol):
                overlaps.append(Overlap(a, b, depth_x, depth_y))
    return overlaps


def find_overflows(
    elements: list[LayoutElement],
    region: DrawableRegion,
    *,
    allowance: float = DEFAULT_BOUNDARY_ALLOWANCE_M,
) -> list[Overflow]:
    """Every element whose box crosses the sheet's ZONE BORDER past its slack.

    The bound is the sheet's :class:`DrawableRegion` -- the area inside the
    border/zone band -- NOT the paper rectangle.  The band carries the zone grid
    labels and the border frame, so an element that stays on the paper but runs
    into the band is still a defect (it prints over the zone letters and reads as
    a clipped sheet).

    EVERY element is checked -- a pictorial view or leadered callout can still be
    mis-placed off the sheet.  The outward ``allowance`` applies ONLY to ``view``
    boxes, which ``IView.GetOutline`` pads a millimetre or two; notes / tables /
    GD&T carry EXACT extents, so they get zero slack and any real breach is
    flagged (Codex #269 thread 7).
    """
    overflows: list[Overflow] = []
    for element in elements:
        # The title-block keep-out is a RESERVED REGION, not content: it is
        # defined to run to the sheet's bottom-right corner, so measuring it
        # against the zone frame just re-reports its own definition.
        if element.kind == "titleblock":
            continue
        slack = allowance if element.kind == "view" else 0.0
        sides: list[tuple[str, float]] = []
        if element.xmin < region.xmin - slack:
            sides.append(("left", region.xmin - slack - element.xmin))
        if element.ymin < region.ymin - slack:
            sides.append(("bottom", region.ymin - slack - element.ymin))
        if element.xmax > region.xmax + slack:
            sides.append(("right", element.xmax - (region.xmax + slack)))
        if element.ymax > region.ymax + slack:
            sides.append(("top", element.ymax - (region.ymax + slack)))
        if sides:
            overflows.append(Overflow(element, tuple(sides)))
    return overflows


def audit_layout(
    elements: list[LayoutElement],
    region: DrawableRegion,
    *,
    leaders: list[LeaderSegment] | None = None,
    overlap_tol: float = DEFAULT_OVERLAP_TOL_M,
    allowance: float = DEFAULT_BOUNDARY_ALLOWANCE_M,
    crossing_inset: float = DEFAULT_CROSSING_INSET_M,
) -> tuple[list[Overlap], list[Overflow], list[Crossing | LeaderCrossing]]:
    """Return (overlaps, overflows, leader crossings) for a laid-out sheet.

    The third list mixes both leader defects -- a leader driven across a foreign
    VIEW, and two leaders crossing EACH OTHER.  They are one bucket because they
    are one class to the reader ("a leader is where it should not be") and one
    fix ("move the anchor or the text placement"); both types answer
    ``describe()``, which is all the caller needs.
    """
    segments = leaders or []
    return (
        find_overlaps(elements, overlap_tol=overlap_tol),
        find_overflows(elements, region, allowance=allowance),
        [
            *find_leader_crossings(segments, elements, inset=crossing_inset),
            *find_leader_leader_crossings(segments),
        ],
    )


def format_findings(
    overlaps: list[Overlap],
    overflows: list[Overflow],
    crossings: list[Crossing | LeaderCrossing] = (),
) -> str:
    """One human-readable block listing every layout finding."""
    lines = [finding.describe() for finding in overlaps]
    lines += [finding.describe() for finding in overflows]
    lines += [finding.describe() for finding in crossings]
    return "\n".join(f"  - {line}" for line in lines)
