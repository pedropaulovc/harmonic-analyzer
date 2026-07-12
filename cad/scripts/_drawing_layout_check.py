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
  without touching any geometry.  Such views are marked ``loose`` and excluded
  from both the overlap and overflow tests -- their bounding box is not a
  faithful footprint.
"""

from __future__ import annotations

from dataclasses import dataclass


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

    ``loose`` marks an element whose axis-aligned box is NOT a faithful
    footprint (an isometric/pictorial view): it is skipped by both the overlap
    and overflow tests.
    """

    label: str
    kind: str  # "view" | "note" | "table"
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    loose: bool = False

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


def find_overlaps(
    elements: list[LayoutElement], *, overlap_tol: float = DEFAULT_OVERLAP_TOL_M
) -> list[Overlap]:
    """Every pair of elements that mutually penetrate by more than ``overlap_tol``.

    A real 2D collision needs positive penetration on BOTH axes; requiring the
    *smaller* penetration to clear the tolerance rejects the whitespace padding
    that ``GetOutline`` adds to adjacent views.  ``loose`` elements (pictorial
    views) are skipped -- their box is not a faithful footprint.
    """
    solid = [element for element in elements if not element.loose]
    overlaps: list[Overlap] = []
    for i in range(len(solid)):
        for j in range(i + 1, len(solid)):
            depth_x, depth_y = _penetration(solid[i], solid[j])
            if min(depth_x, depth_y) > overlap_tol:
                overlaps.append(Overlap(solid[i], solid[j], depth_x, depth_y))
    return overlaps


def find_overflows(
    elements: list[LayoutElement],
    sheet_width: float,
    sheet_height: float,
    *,
    allowance: float = DEFAULT_BOUNDARY_ALLOWANCE_M,
) -> list[Overflow]:
    """Every element whose box runs past the sheet edge by more than ``allowance``.

    The sheet origin is its lower-left corner (SolidWorks sheet space), so the
    usable region is ``[-allowance, width + allowance] x [-allowance, height +
    allowance]``.  ``loose`` elements are skipped -- their padded pictorial box
    routinely pokes past an edge without any geometry doing so.
    """
    overflows: list[Overflow] = []
    for element in elements:
        if element.loose:
            continue
        sides: list[tuple[str, float]] = []
        if element.xmin < -allowance:
            sides.append(("left", -allowance - element.xmin))
        if element.ymin < -allowance:
            sides.append(("bottom", -allowance - element.ymin))
        if element.xmax > sheet_width + allowance:
            sides.append(("right", element.xmax - (sheet_width + allowance)))
        if element.ymax > sheet_height + allowance:
            sides.append(("top", element.ymax - (sheet_height + allowance)))
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
