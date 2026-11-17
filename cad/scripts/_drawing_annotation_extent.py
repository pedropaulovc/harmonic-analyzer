"""Read-back ink boxes for laying drawing annotations out clear of each other.

The layout audit (``_layout_audit``) measures every annotation on the
exported PDF, but only after the sheet is finished: a feature-control frame
parked on a neighbouring dimension's callout text would fail the leaf with no
way to move it.  It happened on MHA-DT-19 (pc-r7 eye pass): the cylindricity
frame sat on the match-drill callout's "STRAPS" and "0.45", and the Ra 1.6 bar
sat on the callout's shoulder.

This module measures a leadered dimension callout and GD&T symbols from what
SolidWorks renders, and places a sheet's annotations from those measured
boxes.  It asserts the result, so a longer callout cannot quietly re-collide.

A leadered dimension's text block sits on its shoulder, a horizontal line of
``IDisplayDimension::GetDisplayData`` (sheet space).  The shoulder runs under
the full text width, and the text is centred on the annotation's
``GetPosition``.  The block is therefore the shoulder's x-span, from the
shoulder up to the mirror of the shoulder about that centre.  The other display
lines are the leader, kept apart as segments so a frame beside a sloped leader
is not reported as overlapping its whole bounding box.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_layout_audit import annotation_display
from _drawing_sheet_region import sheet_drawable_region
from _layout_audit import display_box, estimated_text_runs
from _layout_geometry import DrawableRegion, LeaderSegment, segment_crosses_box
import _telemetry

Box = tuple[float, float, float, float]

# swAnnotationType_e: display dimensions (and native hole callouts), and the
# native GD&T symbols the recipes place at explicit sheet coordinates.
_ANNOT_DATUM = 2
_ANNOT_DIM = 4
_ANNOT_GTOL = 5
_ANNOT_SFSYM = 7
_GDT_TYPES = frozenset({_ANNOT_DATUM, _ANNOT_GTOL, _ANNOT_SFSYM})
_SEL_DIMENSION = 14  # swSelectType_e.swSelDIMENSIONS

# Fallback only, for a GD&T symbol whose geometry cannot be read. Every symbol
# that CAN be measured is (see _measured_gdt_box) -- a fixed square is wrong
# for an FCF by construction, since its width tracks its compartments.
_NOMINAL_GDT_HALF_M = 0.008

# A SURFACE-FINISH symbol is NOT centred on its anchor. ``GetPosition`` returns
# the LEADER'S ATTACHMENT POINT -- the bottom vertex of the check-mark triangle
# -- and the whole body draws UP and to the RIGHT of it: triangle
# x [ax-0.006, ax+0.006] y [ay, ay+0.011]; the "Ra 1.6" text
# x [ax+0.013, ax+0.039] y [ay+0.010, ay+0.017]; the arm at y ~= ay+0.018.
# Measured independently on 3+ sheets by three agents; every sample draws
# up-right regardless of which side the target sits on, so the offsets are
# orientation-stable for ``add_surface_finish``'s SetLeader3(BENT, SMART) call.
_SF_BOX_LEFT_M = 0.008
_SF_BOX_RIGHT_M = 0.039
_SF_BOX_UP_M = 0.018
_SF_BOX_DOWN_M = 0.0

# Two annotations closer than this read as one: one text height of air.
CLEAR_GAP_M = 0.002
# A move lands this far past the gap, so the read-back that proves it clear at
# CLEAR_GAP_M has room to settle.  Placed at exactly the gap, the #877 cold
# build's MHA-DT-19 callout read back a hair short and failed the proof (leaf
# 20260927T150045Z-1-3febc7c2, swmaker000006); the same frame read 0.2 mm
# apart between two seats (ymin 0.2148 vs 0.2150).
PLACE_SETTLE_M = 0.0002
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


def _datum_is_dimension_attached(annotation: Any) -> bool:
    """Whether a datum tag is attached to a display dimension.

    SolidWorks reports ``IDatumTag`` primitive coordinates for this attachment
    type in the dimension's local frame.  They must not be mixed with the
    sheet-space annotation position.
    """
    try:
        attachment_types = annotation.GetAttachedEntityTypes() or ()
    except Exception:  # noqa: BLE001 -- unreadable means not dimension-attached
        return False
    return _SEL_DIMENSION in (int(value) for value in attachment_types)


def _measured_gdt_box(adapter: Any, annotation: Any, kind: int, *, name: str) -> Box | None:
    """Box a datum tag or feature-control frame from the ink it renders.

    ``IAnnotation::GetDisplayData`` (``annotation_display``): lines, arcs,
    triangles and text runs where SolidWorks draws them, leader included. NOT
    the ``IGtol`` / ``IDatumTag`` primitives (``GetLineAtIndex`` and kin) -- on
    MHA-DT-19 at 4:1 (pc-gdt-ink-diag, a89a13a7a) a leadered FCF's primitives
    are a crossed 2h x 2h placeholder square at the leader's far end plus the
    leader's last run, never the frame, and a datum tag's box lies about
    (-9.9, -5.0) mm off its ink. The display data is where the PDF prints:
    knife-mount's datum A and its leadered three-compartment FCF match their PDF
    glyphs within 0.15 mm (layoutcal d09c2b9eb).

    ``None``, with a ``gdt_box.fallback`` event naming the symbol and the
    reason, when there is nothing to read. A DATUM attached to a display
    dimension is one such case: whether its display data is sheet space is
    unmeasured, so it keeps the nominal box.
    """
    if kind == _ANNOT_DATUM and _datum_is_dimension_attached(annotation):
        reason = "dimension-attached datum"
    else:
        display, refused = annotation_display(adapter, annotation)
        box = display_box(display) if display else None
        if box is not None:
            estimated = estimated_text_runs(display)
            if estimated:
                _telemetry.event("gdt_box.text_estimated", symbol=name, runs=estimated)
            return (box.xmin, box.ymin, box.xmax, box.ymax)
        if display:
            reason = "display data draws nothing"
        else:
            reason = f"no display data (refused {refused})" if refused else "no display data"
    _telemetry.event("gdt_box.fallback", symbol=name, reason=reason)
    _telemetry.debug(f"{name}: GD&T box falls back to the nominal square: {reason}")
    return None


def gdt_box(adapter: Any, annotation: Any, *, label: str) -> Box:
    """A GD&T symbol's box from its rendered geometry where possible.

    Datum tags and feature-control frames are MEASURED (``_measured_gdt_box``):
    an FCF's anchor is its frame's TOP-LEFT corner and its width grows with
    compartment count (41.6 mm for "Ø0.20|A|B|C" vs 32.2 mm for "0.10|A|B",
    both 7.0 mm tall), so no fixed box can be right. A surface-finish symbol
    keeps its measured ``_SF_BOX_*`` constants: its "Ra 1.6" text overhangs
    the bar drawn above it by ~1.3 mm and is not among the primitives, so a
    geometry-derived box would clip it. A symbol with no readable geometry
    falls back to a nominal square, which still catches one placed clear off
    the sheet.
    """
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetType", "GetName", "GetPosition"
    )
    kind = int(annotation.GetType())
    if kind not in _GDT_TYPES:
        raise RuntimeError(f"{label} is not a GD&T symbol (annotation type {kind})")
    position = annotation.GetPosition()
    if not position:
        raise RuntimeError(f"{label} has no readable position")
    x, y = float(position[0]), float(position[1])
    name = str(annotation.GetName() or label)
    if kind == _ANNOT_SFSYM:
        box = (x - _SF_BOX_LEFT_M, y - _SF_BOX_DOWN_M, x + _SF_BOX_RIGHT_M, y + _SF_BOX_UP_M)
    else:
        measured = _measured_gdt_box(adapter, annotation, kind, name=name)
        half = _NOMINAL_GDT_HALF_M
        box = measured if measured is not None else (x - half, y - half, x + half, y + half)
    _telemetry.info(f"{label} ink: {_fmt(box)}")
    return box


def leader_segments_of(annotation: Any, *, label: str, kind: str, owner: str) -> list[LeaderSegment]:
    """Every straight run of ``annotation``'s registered leader(s), in sheet meters.

    ``GetLeaderPointsAtIndex`` returns a flat x,y,z triple stream in sheet
    space; consecutive points are joined, so a bent leader yields its elbow AND
    its tail.
    """
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetLeaderCount", "GetLeaderPointsAtIndex"
    )
    segments: list[LeaderSegment] = []
    for index in range(int(annotation.GetLeaderCount() or 0)):
        raw = annotation.GetLeaderPointsAtIndex(index)
        if not raw:
            continue
        values = [float(v) for v in raw]
        points = [(values[i], values[i + 1]) for i in range(0, len(values) - 2, 3)]
        segments.extend(
            LeaderSegment(label, kind, start[0], start[1], end[0], end[1], owner)
            for start, end in zip(points, points[1:])
        )
    return segments


def sheet_region(adapter: Any) -> DrawableRegion:
    """The current sheet's region inside its zone frame, as the audit reads it.

    ``IDrawingDoc::GetCurrentSheet`` hands back a late-bound dispatch even from
    the early-bound document, and late binding auto-invokes a zero-argument
    method on attribute access: ``sheet.GetProperties`` is already the tuple,
    so calling it raised ``'tuple' object is not callable`` (pc-858x928, both
    MHA-DT-19 and MHA-DT-17).  Bind the sheet like every other object here.
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
        if any(segment_crosses_box(segment, box, inset=0.0) for segment in ink.leader)
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
    than re-colliding.  A move clears each neighbour by CLEAR_GAP_M plus
    PLACE_SETTLE_M.  After the move the callout is read back again: its text
    must clear every neighbour by CLEAR_GAP_M, its leader must not run through
    any of them, and it must stay inside the zone frame.
    """
    rebuild_drawing(adapter, label=f"measure {label}")
    region = sheet_region(adapter)
    ink = callout_ink(adapter, annotation, label=label)
    xmin, ymin, xmax, ymax = ink.text
    dy = max(
        [0.0]
        + [
            box[3] + CLEAR_GAP_M + PLACE_SETTLE_M - ymin
            for box in below.values()
            if box[0] < xmax and xmin < box[2]
        ]
    )
    raised = (xmin, ymin + dy, xmax, ymax + dy)
    dx = max(
        [0.0, region.xmin + CLEAR_GAP_M - xmin]
        + [
            box[2] + CLEAR_GAP_M + PLACE_SETTLE_M - xmin
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
