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
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
) -> tuple[list[Overlap], list[Overflow], list[Crossing]]:
    """Return (overlaps, overflows, leader crossings) for a laid-out sheet."""
    return (
        find_overlaps(elements, overlap_tol=overlap_tol),
        find_overflows(elements, region, allowance=allowance),
        find_leader_crossings(leaders or [], elements, inset=crossing_inset),
    )


def format_findings(
    overlaps: list[Overlap],
    overflows: list[Overflow],
    crossings: list[Crossing] = (),
) -> str:
    """One human-readable block listing every layout finding."""
    lines = [finding.describe() for finding in overlaps]
    lines += [finding.describe() for finding in overflows]
    lines += [finding.describe() for finding in crossings]
    return "\n".join(f"  - {line}" for line in lines)
