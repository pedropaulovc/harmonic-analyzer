"""Read-back ink boxes for laying drawing annotations out clear of each other.

The layout audit (``_drawing_layout_check``) gives dimensions and GD&T symbols
``CollisionScope.NONE``: a GD&T symbol sits by design beside its own frame, and
a dimension's box is only a nominal square around its text anchor.  So a
feature-control frame parked on a neighbouring dimension's callout text reads
clean.  It happened on MHA-DT-019 (pc-r7 eye pass): the cylindricity frame sat
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

For linear, radial, and note reservations use ``annotation_ink`` instead of
the shoulder-mirror reader. It reuses the unified audit's rendered text rows
and primitive classifier: a linear witness is not a callout shoulder, and a
foreshortened radius has a virtual-centre cross, not a text-box baseline.
Plain notes retain their exact native extent. Dimension row positions/heights
are native; the last glyph's width is the audit's calibrated estimate.
Reservations and clearance checks can be re-read by ``settled_checks`` after
the final rebuild, before export, without changing any annotation content.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
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
from _drawing_layout_audit import annotation_display
from _layout_audit import (
    OWN_ROW_INSET_M,
    annotation_geometry,
    calibrate_sheet_advance,
    group_rows,
    text_items,
)
from _layout_geometry import (
    DEFAULT_TEXT_TOUCH_TOL_M,
    Box as GeometryBox,
    Segment,
    segment_box_distance,
    segment_box_overlap_length,
    union_boxes,
)
from _drawing_layout_check import DrawableRegion, LeaderSegment, _segment_crosses_box
from solidworks_mcp.adapters import sw_type_info as _sw_type_info

Box = tuple[float, float, float, float]

# Two annotations closer than this read as one: one text height of air.
CLEAR_GAP_M = 0.002
# A move lands this far past the gap, so the read-back that proves it clear at
# CLEAR_GAP_M has room to settle.  Placed at exactly the gap, the #877 cold
# build's MHA-DT-019 callout read back a hair short and failed the proof (leaf
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


@dataclass(frozen=True)
class AnnotationInk:
    """Native row positions/heights and classified ink, never shoulder-mirrored."""

    label: str
    text: Box
    rows: tuple[Box, ...]
    lines: tuple[Segment, ...]
    texts: tuple[str, ...]
    heights: tuple[float, ...]
    row_count: int = 0


def annotation_ink_from_record(
    record: Mapping[str, Any], *, label: str, allow_no_text: bool = False
) -> AnnotationInk:
    """Read the audit's annotation record; useful for geometry-only regressions."""
    display = record.get("display") or {}
    items = text_items(display)
    if not items and not allow_no_text:
        raise RuntimeError(f"{label} has no readable rendered text rows")
    advance = calibrate_sheet_advance((record,), default=0.74)
    geometry = annotation_geometry(record, owner="", advance=advance)
    if geometry is None or (not geometry.text_boxes and not allow_no_text):
        raise RuntimeError(f"{label} has no readable rendered text box")
    box = union_boxes(list(geometry.text_boxes)) if geometry.text_boxes else geometry.box()
    if box is None:
        raise RuntimeError(f"{label} has no readable rendered ink")
    # A native leading blank is not a reliable glyph offset: R11 wheel-bar
    # " 10.00 " printed from x 10.8882 mm, while skipping the blank predicted
    # 13.4782 mm and falsely accepted the 12.7 mm frame. Include raw starts
    # for containment/placement, without inflating ordinary collision rows.
    if not geometry.exact:
        for item in items:
            if item.text[:1].isspace():
                box = box.union(GeometryBox(item.x, item.y, item.x, item.y))
    rows = tuple((row.xmin, row.ymin, row.xmax, row.ymax) for row in geometry.text_boxes)
    values = (*rows, *((line.x0, line.y0, line.x1, line.y1) for line in geometry.segments))
    if not all(math.isfinite(value) for row in values for value in row):
        raise RuntimeError(f"{label} has non-finite native ink")
    return AnnotationInk(
        label,
        (box.xmin, box.ymin, box.xmax, box.ymax),
        rows,
        geometry.segments,
        tuple(item.text for item in items),
        tuple(item.height for item in items),
        len(group_rows(items)),
    )


def annotation_ink(
    adapter: Any, annotation: Any, *, label: str, allow_no_text: bool = False
) -> AnnotationInk:
    """Measure dimensions of any kind or notes, failing closed on unreadable ink."""
    annotation = _early_bound(annotation, "IAnnotation")
    display, errors = annotation_display(adapter, annotation)
    if errors:
        raise RuntimeError(f"{label} native ink read failed: {errors}")
    kind = int(annotation.GetType())
    record: dict[str, Any] = {"type": kind, "name": label, "display": display}
    if kind == 4:
        native = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        record["dim"] = {"hole_callout": bool(native.IsHoleCallout())}
    elif kind == 6 and int(annotation.GetLeaderCount()) == 0:
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        extent = tuple(float(value) for value in (note.GetExtent() or ()))
        if len(extent) != 6 or not all(math.isfinite(value) for value in extent):
            raise RuntimeError(f"{label} has no finite native note extent")
        record["note"] = {"text": str(note.GetText()), "extent": extent}
    ink = annotation_ink_from_record(record, label=label, allow_no_text=allow_no_text)
    _telemetry.info(
        f"{label} native ink: text={_fmt(ink.text)} rows={ink.rows} "
        f"lines={ink.lines} runs={ink.texts!r} heights={ink.heights}"
    )
    return ink


def annotation_text_box(adapter: Any, annotation: Any, *, label: str) -> Box:
    """The generic native row union (or a plain note's exact native extent)."""
    return annotation_ink(adapter, annotation, label=label).text


def annotation_field_shift(text: Box, field: Box, margin: float = CLEAR_GAP_M) -> tuple[float, float]:
    """Smallest move into a reserved field; never shrink or reflow oversized text."""
    if (
        not all(math.isfinite(value) for value in (*text, *field, margin))
        or margin < 0.0
        or text[0] > text[2]
        or text[1] > text[3]
        or field[0] >= field[2]
        or field[1] >= field[3]
    ):
        raise ValueError("annotation field and text must be finite ordered boxes")
    if text[2] - text[0] > field[2] - field[0] - 2.0 * margin or text[3] - text[1] > field[3] - field[1] - 2.0 * margin:
        raise RuntimeError(f"text {_fmt(text)} cannot fit reserved field {_fmt(field)} with {margin:.4f} m margin")
    dx = max(0.0, field[0] + margin - text[0]) - max(0.0, text[2] - field[2] + margin)
    dy = max(0.0, field[1] + margin - text[1]) - max(0.0, text[3] - field[3] + margin)
    return dx, dy


def require_annotation_in_field(ink: AnnotationInk, field: Box, margin: float = 0.0) -> None:
    """Prove the complete text remains in its reservation after the final rebuild."""
    if annotation_field_shift(ink.text, field, margin) != (0.0, 0.0):
        raise RuntimeError(f"{ink.label} {_fmt(ink.text)} left reserved field {_fmt(field)}")


def place_annotation_in_field(
    adapter: Any, annotation: Any, *, label: str, field: Box, margin: float = CLEAR_GAP_M
) -> AnnotationInk:
    """Place from measured text, then re-read; preserve model/data/font/association."""
    ink = annotation_ink(adapter, annotation, label=label)
    dx, dy = annotation_field_shift(ink.text, field, margin)
    if dx or dy:
        move_annotation(adapter, annotation, dx, dy, label=label)
        ink = annotation_ink(adapter, annotation, label=label)
    require_annotation_in_field(ink, field, margin)
    return ink


def require_annotation_inside(ink: AnnotationInk, region: DrawableRegion) -> None:
    """Prove all text AND rendered ink contained, including remote radius centres."""
    require_inside(ink.label, ink.text, region)
    for line in ink.lines:
        box = line.box()
        require_inside(ink.label, (box.xmin, box.ymin, box.xmax, box.ymax), region)


def require_annotation_clear(
    ink: AnnotationInk,
    neighbours: Sequence[AnnotationInk],
    *,
    check_own_lines: bool = False,
    line_gap: float = CLEAR_GAP_M,
) -> None:
    """Check rows in both directions, with visible air from foreign native ink."""
    for other in neighbours:
        if other.label == ink.label:
            continue
        for row in ink.rows:
            for box in other.rows:
                require_clear(ink.label, row, {other.label: box})
            box = GeometryBox(*row)
            if any(
                segment_box_distance(line, box) < line_gap
                or segment_box_overlap_length(line, box) > DEFAULT_TEXT_TOUCH_TOL_M
                for line in other.lines
            ):
                raise RuntimeError(
                    f"{other.label} native line crowds/crosses {ink.label} text {_fmt(row)}"
                )
        for row in other.rows:
            box = GeometryBox(*row)
            if any(
                segment_box_distance(line, box) < line_gap
                or segment_box_overlap_length(line, box) > DEFAULT_TEXT_TOUCH_TOL_M
                for line in ink.lines
            ):
                raise RuntimeError(
                    f"{ink.label} native line crowds/crosses {other.label} text {_fmt(row)}"
                )
    if check_own_lines:
        for row in ink.rows:
            box = GeometryBox(
                row[0] + OWN_ROW_INSET_M,
                row[1] + OWN_ROW_INSET_M,
                row[2] - OWN_ROW_INSET_M,
                row[3] - OWN_ROW_INSET_M,
            )
            own_lines = (
                line
                for line in ink.lines
                if line.role in {"ext-line", "dim-line", "line", "leader"}
            )
            if any(
                segment_box_overlap_length(line, box) > DEFAULT_TEXT_TOUCH_TOL_M
                for line in own_lines
            ):
                raise RuntimeError(f"{ink.label} native line crosses its own text {_fmt(row)}")


def require_annotation_rows(ink: AnnotationInk, limit: int = 4) -> None:
    """Refuse a five-row process block even if its text still fits the sheet."""
    if ink.row_count > limit:
        raise RuntimeError(f"{ink.label} runs {ink.row_count} rendered rows, over its {limit}-row limit")


def assert_annotation_reservations(
    adapter: Any,
    annotations: Mapping[str, Any],
    fields: Mapping[str, Box],
    *,
    row_limits: Mapping[str, int] | None = None,
    text_heights: Mapping[str, float] | None = None,
    check_own_lines: Sequence[str] = (),
    line_gap: float = CLEAR_GAP_M,
) -> dict[str, AnnotationInk]:
    """Final measured reservations and selected ink checks, independent of audit mode.

    Include the neighbouring dimensions/notes in ``annotations`` so their
    actual lines, not coordinate predictions, must clear each reserved row.
    ``row_limits`` apply to physical rendered rows; a toleranced model size's
    upper/lower stack must not be mistaken for extra process-note rows.
    """
    missing = set(fields) - set(annotations)
    if missing:
        raise RuntimeError(f"reserved annotations missing: {sorted(missing)}")
    inks = {
        label: annotation_ink(adapter, annotation, label=label, allow_no_text=label not in fields)
        for label, annotation in annotations.items()
    }
    region = sheet_region(adapter)
    for label, field in fields.items():
        ink = inks[label]
        require_annotation_in_field(ink, field)
        require_annotation_inside(ink, region)
        require_annotation_clear(
            ink, list(inks.values()), check_own_lines=label in check_own_lines, line_gap=line_gap
        )
    for label, limit in (row_limits or {}).items():
        if label not in inks:
            raise RuntimeError(f"row-limited annotation {label} is missing")
        require_annotation_rows(inks[label], limit)
    for label, height in (text_heights or {}).items():
        if label not in inks or any(abs(value - height) > 1e-7 for value in inks[label].heights):
            raise RuntimeError(f"{label} did not retain its {height * 1000.0:.3f} mm text height")
    return inks


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
    MHA-DT-019 and MHA-DT-017).  Bind the sheet like every other object here.
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
