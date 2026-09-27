"""Read-back ink boxes for laying drawing annotations out clear of each other.

The layout audit (``_drawing_layout_check``) gives dimensions and GD&T symbols
``CollisionScope.NONE``: a GD&T symbol sits by design beside its own frame, and
a dimension's box is only a nominal square around its text anchor.  So a
feature-control frame parked on a neighbouring dimension's callout text reads
clean.  It happened on MHA-062 (pc-r7 eye pass): the cylindricity frame sat
on the match-drill callout's "STRAPS" and "0.45", and the Ra 1.6 bar sat on the
callout's shoulder.

This module measures a leadered dimension callout from what SolidWorks
renders, and places a sheet's annotations from those measured boxes.  It
asserts the result, so a longer callout cannot quietly re-collide.  It is
opt-in: only the sheets that import it re-key, whereas an edit to
``_drawing_common`` re-keys every drawing.

A leadered dimension's text block sits on its shoulder, a horizontal line of
``IDisplayDimension::GetDisplayData`` (sheet space; see
``_drawing_common._display_dimension_leader_segments``).  The shoulder runs
under the full text width, and the text is centred on the annotation's
``GetPosition``.  The block is therefore the shoulder's x-span, from the
shoulder up to the mirror of the shoulder about that centre.  The other display
lines are the leader, kept apart as segments so a frame beside a sloped leader
is not reported as overlapping its whole bounding box.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import _telemetry
from _common import _early_bound
from _drawing_common import (
    _ANNOT_DIM,
    _GDT_TYPES,
    _gdt_element,
    rebuild_drawing,
    sheet_drawable_region,
)
from _drawing_layout_check import DrawableRegion, LeaderSegment, _segment_crosses_box
from solidworks_mcp.adapters import sw_type_info as _sw_type_info

Box = tuple[float, float, float, float]

# Two annotations closer than this read as one: one text height of air.
CLEAR_GAP_M = 0.002
_HORIZONTAL_M = 1e-6


@dataclass(frozen=True)
class CalloutInk:
    """A leadered dimension's text block and its leader, in sheet meters."""

    label: str
    text: Box
    leader: tuple[LeaderSegment, ...]


def boxes_clear(a: Box, b: Box, gap: float = CLEAR_GAP_M) -> bool:
    """True when ``a`` and ``b`` are at least ``gap`` apart on some axis."""
    return (
        a[2] + gap <= b[0]
        or b[2] + gap <= a[0]
        or a[3] + gap <= b[1]
        or b[3] + gap <= a[1]
    )


def callout_text_box(
    lines: list[tuple[float, float, float, float]], center: tuple[float, float]
) -> Box:
    """The text block of a leadered dimension from its display lines.

    ``lines`` are ``(x0, y0, x1, y1)`` in sheet meters, ``center`` is the
    annotation's ``GetPosition``.  The longest horizontal line is the shoulder;
    the text sits on it and is centred on ``center``.
    """
    horizontal = [line for line in lines if abs(line[1] - line[3]) < _HORIZONTAL_M]
    if not horizontal:
        raise RuntimeError(f"callout has no shoulder line among {lines}")
    shoulder = max(horizontal, key=lambda line: abs(line[2] - line[0]))
    base = shoulder[1]
    if center[1] <= base:
        raise RuntimeError(
            f"callout text centre {center} is not above its shoulder at y={base}"
        )
    return (
        min(shoulder[0], shoulder[2]),
        base,
        max(shoulder[0], shoulder[2]),
        2.0 * center[1] - base,
    )


def callout_ink(adapter: Any, annotation: Any, *, label: str) -> CalloutInk:
    """Read a leadered dimension callout's text block and leader off the sheet."""
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetType", "GetPosition", "GetSpecificAnnotation"
    )
    if int(annotation.GetType()) != _ANNOT_DIM:
        raise RuntimeError(f"{label} is not a display dimension")
    position = [float(value) for value in annotation.GetPosition()]
    display = _sw_type_info.early_bound_or_flag(
        annotation.GetSpecificAnnotation(), "IDisplayDimension", "GetDisplayData"
    )
    data = _sw_type_info.early_bound_or_flag(
        display.GetDisplayData(), "IDisplayData", "GetLineCount", "GetLineAtIndex2"
    )
    lines: list[tuple[float, float, float, float]] = []
    for index in range(int(data.GetLineCount())):
        # GetLineAtIndex2 -> [color, lineType, _, _, startPt[3], endPt[3]].
        raw = [float(value) for value in data.GetLineAtIndex2(index)]
        lines.append((raw[4], raw[5], raw[7], raw[8]))
    text = callout_text_box(lines, (position[0], position[1]))
    leader = tuple(
        LeaderSegment(label, "dim", *line, "")
        for line in lines
        if not (abs(line[1] - line[3]) < _HORIZONTAL_M and line[1] == text[1])
    )
    _telemetry.info(
        f"{label} callout ink: text={_fmt(text)} centre=({position[0]:.4f}, "
        f"{position[1]:.4f}) lines={[_fmt(line) for line in lines]}"
    )
    return CalloutInk(label, text, leader)


def gdt_box(adapter: Any, annotation: Any, *, label: str) -> Box:
    """A GD&T symbol's box as the layout audit measures it."""
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetType", "GetName"
    )
    kind = int(annotation.GetType())
    if kind not in _GDT_TYPES:
        raise RuntimeError(f"{label} is not a GD&T symbol (annotation type {kind})")
    element = _gdt_element(
        adapter, annotation, str(annotation.GetName() or label), kind
    )
    if element is None:
        raise RuntimeError(f"{label} has no readable position")
    _telemetry.info(f"{label} ink: {_fmt(element.box)}")
    return element.box


def sheet_region(adapter: Any) -> DrawableRegion:
    """The current sheet's region inside its zone frame, as the audit reads it.

    ``IDrawingDoc::GetCurrentSheet`` hands back a late-bound dispatch even from
    the early-bound document, and late binding auto-invokes a zero-argument
    method on attribute access: ``sheet.GetProperties`` is already the tuple,
    so calling it raised ``'tuple' object is not callable`` (pc-858x928, both
    MHA-062 and MHA-060).  Bind the sheet like every other object here.
    """
    sheet = _sw_type_info.early_bound_or_flag(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(),
        "ISheet",
        "GetProperties2",
    )
    # GetProperties2 -> [paperSize, templateIn, scale1, scale2, firstAngle,
    # width, height, sameCustomProp].
    properties = [float(value) for value in sheet.GetProperties2()]
    return sheet_drawable_region(
        adapter, sheet, width=properties[5], height=properties[6]
    )


def move_annotation(
    adapter: Any, annotation: Any, dx: float, dy: float, *, label: str
) -> None:
    """Move an annotation's text by ``(dx, dy)`` and rebuild so it re-renders."""
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetPosition", "SetPosition2"
    )
    x, y, z = (float(value) for value in annotation.GetPosition())
    if not annotation.SetPosition2(x + dx, y + dy, z):
        raise RuntimeError(f"failed to move {label} by ({dx:.4f}, {dy:.4f})")
    rebuild_drawing(adapter, label=f"move {label}")


def require_clear(label: str, box: Box, others: dict[str, Box]) -> None:
    """Raise when ``box`` comes within ``CLEAR_GAP_M`` of any of ``others``."""
    hits = [name for name, other in others.items() if not boxes_clear(box, other)]
    if hits:
        raise RuntimeError(
            f"{label} {_fmt(box)} crowds {hits}: "
            + ", ".join(f"{name} {_fmt(others[name])}" for name in hits)
        )


def require_leader_clear(ink: CalloutInk, others: dict[str, Box]) -> None:
    """Raise when the callout's leader runs through any of ``others``."""
    hits = [
        name
        for name, box in others.items()
        if any(_segment_crosses_box(segment, box, inset=0.0) for segment in ink.leader)
    ]
    if hits:
        raise RuntimeError(f"{ink.label} leader runs through {hits}")


def require_inside(label: str, box: Box, region: DrawableRegion) -> None:
    """Raise when ``box`` crosses the sheet's zone frame."""
    if (
        box[0] < region.xmin
        or box[1] < region.ymin
        or box[2] > region.xmax
        or box[3] > region.ymax
    ):
        raise RuntimeError(
            f"{label} {_fmt(box)} crosses the zone frame "
            f"{_fmt((region.xmin, region.ymin, region.xmax, region.ymax))}"
        )


def place_callout_clear(
    adapter: Any,
    annotation: Any,
    *,
    label: str,
    below: dict[str, Box],
    beside: dict[str, Box],
) -> CalloutInk:
    """Move a leadered dimension callout clear of its neighbours, then prove it.

    ``below`` are symbols the callout's shoulder must clear from above: their
    lane runs under the text.  ``beside`` are symbols the text must clear from
    the right.  The zone frame's left edge is always one of them.  The move is
    computed from the read-back boxes, so a longer callout moves further rather
    than re-colliding.  After the move the callout is read back again: its text
    must clear every neighbour, its leader must not run through any of them,
    and it must stay inside the zone frame.
    """
    rebuild_drawing(adapter, label=f"measure {label}")
    region = sheet_region(adapter)
    ink = callout_ink(adapter, annotation, label=label)
    xmin, ymin, xmax, ymax = ink.text
    dy = max(
        [0.0]
        + [
            box[3] + CLEAR_GAP_M - ymin
            for box in below.values()
            if box[0] < xmax and xmin < box[2]
        ]
    )
    raised = (xmin, ymin + dy, xmax, ymax + dy)
    dx = max(
        [0.0, region.xmin + CLEAR_GAP_M - xmin]
        + [
            box[2] + CLEAR_GAP_M - xmin
            for box in beside.values()
            if not boxes_clear(raised, box)
        ]
    )
    if dx or dy:
        move_annotation(adapter, annotation, dx, dy, label=label)
        ink = callout_ink(adapter, annotation, label=label)
        _telemetry.success(
            f"{label} moved ({dx:.4f}, {dy:.4f}) m clear of its neighbours"
        )
    neighbours = {**below, **beside}
    require_clear(label, ink.text, neighbours)
    require_leader_clear(ink, neighbours)
    require_inside(label, ink.text, region)
    return ink


def _fmt(box: tuple[float, ...]) -> str:
    return "(" + ", ".join(f"{value:.4f}" for value in box) + ")"
