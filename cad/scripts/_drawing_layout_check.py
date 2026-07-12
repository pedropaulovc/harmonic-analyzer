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
  A pictorial view's axis-aligned outline is mostly empty diagonal space, so it
  collides with ``NONE``.  A leadered callout / GD&T symbol / on-view tag
  legitimately sits over the view geometry it points at, but must NOT overlap a
  free note, a table, or the title block -- it collides with ``NON_VIEW``
  elements only.  Everything else (ortho views, free notes, tables, the reserved
  title block) collides with ``ALL``.
* The OVERFLOW allowance applies only to ``view`` boxes.  ``IView.GetOutline``
  pads whitespace, so an on-sheet view can poke a millimetre or two past an edge;
  notes / tables / GD&T carry EXACT extents, so any overhang is a real clip and
  gets zero slack.

Every element -- whatever its scope -- is still checked for OVERFLOW, so a
pictorial view or leadered note mis-placed off the sheet is always caught.
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
    kind: str  # "view" | "note" | "table" | "gdt" | "titleblock"
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    scope: CollisionScope = CollisionScope.ALL

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.xmin, self.ymin, self.xmax, self.ymax)


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
            f"{self.element.kind} {self.element.label!r} overflows the sheet: "
            f"{breaches}"
        )


def _penetration(a: LayoutElement, b: LayoutElement) -> tuple[float, float]:
    """Overlap depth of two boxes on each axis (negative = a gap on that axis)."""
    depth_x = min(a.xmax, b.xmax) - max(a.xmin, b.xmin)
    depth_y = min(a.ymax, b.ymax) - max(a.ymin, b.ymin)
    return depth_x, depth_y


def _may_collide(a: LayoutElement, b: LayoutElement) -> bool:
    """True if the pair ``(a, b)`` is eligible for overlap auditing.

    A ``NONE``-scope element never collides.  A ``NON_VIEW`` element collides
    with anything except a ``view`` (its overlap with the view geometry it
    points at / attaches to is intended), so a leadered callout or GD&T symbol
    that strays onto a free note, a table, or the title block is still caught.
    """
    if a.scope is CollisionScope.NONE or b.scope is CollisionScope.NONE:
        return False
    if a.scope is CollisionScope.NON_VIEW and b.kind == "view":
        return False
    if b.scope is CollisionScope.NON_VIEW and a.kind == "view":
        return False
    return True


def find_overlaps(
    elements: list[LayoutElement], *, overlap_tol: float = DEFAULT_OVERLAP_TOL_M
) -> list[Overlap]:
    """Every eligible pair of elements that mutually penetrate by > ``overlap_tol``.

    A real 2D collision needs positive penetration on BOTH axes; requiring the
    *smaller* penetration to clear the tolerance rejects the whitespace padding
    that ``GetOutline`` adds to adjacent views.  Pair eligibility follows each
    element's ``CollisionScope`` (see :func:`_may_collide`).
    """
    overlaps: list[Overlap] = []
    for i in range(len(elements)):
        for j in range(i + 1, len(elements)):
            a, b = elements[i], elements[j]
            if not _may_collide(a, b):
                continue
            depth_x, depth_y = _penetration(a, b)
            if min(depth_x, depth_y) > overlap_tol:
                overlaps.append(Overlap(a, b, depth_x, depth_y))
    return overlaps


def find_overflows(
    elements: list[LayoutElement],
    sheet_width: float,
    sheet_height: float,
    *,
    allowance: float = DEFAULT_BOUNDARY_ALLOWANCE_M,
) -> list[Overflow]:
    """Every element whose box runs past the sheet edge by more than its slack.

    The sheet origin is its lower-left corner (SolidWorks sheet space), so the
    usable region is ``[-slack, width + slack] x [-slack, height + slack]``.
    EVERY element is checked -- a pictorial view or leadered callout can still be
    mis-placed off the sheet.  The outward ``allowance`` applies ONLY to ``view``
    boxes, which ``IView.GetOutline`` pads a millimetre or two past an on-sheet
    edge; notes / tables / GD&T carry EXACT extents, so they get zero slack and
    any real off-sheet clip is flagged (Codex #269 thread 7).
    """
    overflows: list[Overflow] = []
    for element in elements:
        slack = allowance if element.kind == "view" else 0.0
        sides: list[tuple[str, float]] = []
        if element.xmin < -slack:
            sides.append(("left", -slack - element.xmin))
        if element.ymin < -slack:
            sides.append(("bottom", -slack - element.ymin))
        if element.xmax > sheet_width + slack:
            sides.append(("right", element.xmax - (sheet_width + slack)))
        if element.ymax > sheet_height + slack:
            sides.append(("top", element.ymax - (sheet_height + slack)))
        if sides:
            overflows.append(Overflow(element, tuple(sides)))
    return overflows


def audit_layout(
    elements: list[LayoutElement],
    sheet_width: float,
    sheet_height: float,
    *,
    overlap_tol: float = DEFAULT_OVERLAP_TOL_M,
    allowance: float = DEFAULT_BOUNDARY_ALLOWANCE_M,
) -> tuple[list[Overlap], list[Overflow]]:
    """Return (overlaps, overflows) for a laid-out sheet."""
    return (
        find_overlaps(elements, overlap_tol=overlap_tol),
        find_overflows(elements, sheet_width, sheet_height, allowance=allowance),
    )


def format_findings(overlaps: list[Overlap], overflows: list[Overflow]) -> str:
    """One human-readable block listing every layout finding."""
    lines = [finding.describe() for finding in overlaps]
    lines += [finding.describe() for finding in overflows]
    return "\n".join(f"  - {line}" for line in lines)
