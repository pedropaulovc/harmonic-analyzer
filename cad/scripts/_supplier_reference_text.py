"""Measured positive-axis text shelves for native supplier reference dimensions.

The caller owns the exact native dimension/source/attachment inventory through
``reacquire``. This module preserves physical arrow and witness stations while
moving the complete measured text block beyond its outside-arrow tail. Widths
and heights come from native display data, not estimated glyph advances.

Native font boxes are not printed glyph ink: even an empty or whitespace text
fragment can have measured advance, and a fraction bar may lie inside their
union. Every native fragment and line remains in ``record``; this core does not
prove clearance from other annotations or the part body.
The caller must retain its settled layout checks and the post-export drawing
layout audit with PDF ink. No font, value, tolerance, source or scale is edited.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
import json
from math import cos, dist, isfinite, sin
from typing import Any

from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _drawing_layout_audit import _Reader, _dump_annotation
from _layout_audit import TextItem, _rotated_hull, annotation_geometry, calibrate_sheet_advance
from _layout_geometry import Box, union_boxes
import _telemetry

# The existing shared-clamp native station/readback contract, not a new allowance.
_POSITION_TOLERANCE_M = 1e-5


def measured_native_text_bounds(
    texts: Collection[Mapping[str, Any]], *, label: str
) -> tuple[Box, tuple[Box, ...]]:
    """Return the union and one measured box per raw native fragment, in order.

    ``GetTextRefPositionAtIndex`` uses all six ``swTextPosition_e`` anchors;
    ``GetTextAngleAtIndex`` is CCW radians. Normalize each anchor to its rotated
    lower-left before the existing unfiltered font-rectangle hull, retaining
    measured metre widths/heights. Each BSTR fragment, including empty/whitespace
    advance, must have readable geometry and a finite derived box BEFORE union.
    No glyph estimate or lower-left fallback can hide malformed geometry.
    Raw records are never modified and fragment cardinality/order is preserved.
    """
    if not texts:
        raise RuntimeError(f"{label}: supplier reference text has no measured native size")
    fragments = []
    for index, raw in enumerate(texts):
        reference = raw.get("ref")
        fragment_label = f"{label} fragment {index} ref={reference!r}"
        value = raw.get("t")
        if not isinstance(value, str):
            raise RuntimeError(f"{fragment_label}: unreadable native text")
        try:
            width, height = (float(raw.get(key) or 0.0) for key in ("w", "h"))
        except (TypeError, ValueError, OverflowError) as error:
            raise RuntimeError(f"{fragment_label}: unreadable measured native size") from error
        if not all(isfinite(value) and value > 0.0 for value in (width, height)):
            raise RuntimeError(f"{fragment_label}: text has no measured native size")
        try:
            at = tuple(float(value) for value in raw.get("pos", ()))
            angle = float(raw["ang"])
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise RuntimeError(f"{fragment_label}: unreadable native position/angle") from error
        if len(at) != 3 or not all(map(isfinite, (*at, angle))):
            raise RuntimeError(f"{fragment_label}: unreadable native position/angle")
        if type(reference) is not int or reference not in range(6):
            raise RuntimeError(f"{fragment_label}: unreadable native reference position")
        # SDK swTextPosition_e: upper-left, lower-left, centre, upper-right,
        # lower-right, upper-centre. Rotate the LOCAL anchor offset, not the
        # raw sheet position; this is the existing measured-caption convention.
        dx, dy = {
            0: (0.0, -height), 1: (0.0, 0.0),
            2: (-width / 2, -height / 2), 3: (-width, -height),
            4: (-width, 0.0), 5: (-width / 2, -height),
        }[reference]
        cosine, sine = cos(angle), sin(angle)
        normalized = (
            at[0] + cosine * dx - sine * dy,
            at[1] + sine * dx + cosine * dy,
            at[2],
        )
        if not all(map(isfinite, normalized)):
            raise RuntimeError(f"{fragment_label}: non-finite normalized native position")
        # display_box intentionally excludes blank visible-ink runs. Native
        # font advances are different: retain every measured rectangle, using
        # that same hull primitive without its semantic text filter.
        fragment = _rotated_hull(
            TextItem(value, normalized[0], normalized[1], height, angle, 1), width
        )
        if not all(map(isfinite, (
            fragment.xmin, fragment.ymin, fragment.xmax, fragment.ymax
        ))):
            raise RuntimeError(f"{fragment_label}: no finite measured native bounds")
        fragments.append(fragment)
    text = union_boxes(fragments)
    if text is None or not all(map(isfinite, (text.xmin, text.ymin, text.xmax, text.ymax))):
        raise RuntimeError(f"{label}: supplier reference text has no finite measured native bounds")
    return text, tuple(fragments)


def _fontbox_failure_note(record: dict[str, Any], *, axis: int, label: str) -> str:
    """Bound already-read primitives only; never inspect or repr a native object."""
    def bounded(value: Any, depth: int = 0) -> Any:
        if value is None or type(value) in (bool, int):
            return value
        if type(value) is float:
            return value if isfinite(value) else {"non_finite": repr(value)}
        if type(value) is str:
            if len(value) <= 128:
                return value
            return {"prefix": value[:128], "omitted_characters": len(value) - 128}
        if depth < 3 and type(value) in (tuple, list):
            return {
                "items": [bounded(item, depth + 1) for item in value[:16]],
                "omitted_items": max(0, len(value) - 16),
            }
        if depth < 3 and type(value) is dict:
            fields = list(value.items())
            return {
                "fields": {
                    key[:128] if type(key) is str else "<non-string-key>":
                    bounded(item, depth + 1)
                    for key, item in fields[:16]
                },
                "omitted_fields": max(0, len(fields) - 16),
            }
        return {"unreadable_type": type(value).__name__[:128]}

    texts = (record.get("display") or {}).get("texts") or ()
    census = {
        "label": bounded(label),
        "axis": axis,
        "annotation": {
            key: bounded(record.get(key))
            for key in ("type", "name", "owner_type", "pos", "visible", "layer")
        },
        "fragment_count": len(texts),
        "omitted_fragments": max(0, len(texts) - 16),
        "fragments": [
            {"index": index, "raw": bounded(raw),
             "reference_python_type": type(raw.get("ref")).__name__[:128]}
            for index, raw in enumerate(texts[:16])
        ],
    }
    return "supplier_reference_native_fontbox_fields " + json.dumps(census, allow_nan=False)


def measure_reference_text(
    adapter: Any, display: Any, *, axis: int, label: str
) -> dict[str, Any]:
    """Read all native text and the physical stations of one linear reference.

    ``axis`` is 0 for a horizontal dimension, 1 for a vertical dimension. The
    returned record retains all native lines, including fraction bars and
    offset-text connectors. ``reach`` is only the maximum positive-axis reach
    of tip-incident dimension lines and arrowheads, not text-format strokes.
    ``witnesses`` contains one primitive ``(station, low, high)`` triple per
    disjoint perpendicular coverage interval, sorted by station and interval.
    This is a read, not a rebuild; callers needing settled pre-transition data
    must rebuild first. :func:`shelve_reference_text` does that itself.
    """
    if isinstance(axis, bool) or not isinstance(axis, int) or axis not in (0, 1):
        raise ValueError(f"{label}: reference axis must be 0 or 1")
    display = _early_bound(display, "IDisplayDimension")
    reader = _Reader(adapter)
    record = _dump_annotation(reader, display.GetAnnotation())
    errors = reader.take_errors()
    if errors or record is None or int(record.get("type", 0)) != 4:
        raise RuntimeError(f"{label}: unreadable supplier reference annotation: {errors}")
    data = record.get("display") or {}
    texts = data.get("texts") or ()
    try:
        text, _ = measured_native_text_bounds(texts, label=label)
    except RuntimeError as error:
        try:
            error.add_note(_fontbox_failure_note(record, axis=axis, label=label))
        except Exception as diagnostic_error:
            error.add_note(
                "supplier reference fontbox field census formatting failed "
                f"({type(diagnostic_error).__name__}); original failure retained"
            )
        raise
    arrows = data.get("arrows") or ()
    if (
        len(arrows) != 2
        or any(
            len(row) < 8 or not all(isfinite(float(value)) for value in row)
            for row in arrows
        )
    ):
        raise RuntimeError(f"{label}: unreadable supplier reference arrow/text geometry")
    tips = tuple(
        sorted((tuple(map(float, row[:2])) for row in arrows), key=lambda p: p[axis])
    )
    if (
        tips[1][axis] <= tips[0][axis]
        or abs(tips[0][1 - axis] - tips[1][1 - axis]) > _POSITION_TOLERANCE_M
    ):
        raise RuntimeError(f"{label}: supplier reference dimension line changed orientation")
    geometry = annotation_geometry(
        record, owner=label, advance=calibrate_sheet_advance((record,))
    )
    if geometry is None or any(
        not all(isfinite(value) for value in (run.x0, run.y0, run.x1, run.y1))
        for run in geometry.segments
    ):
        raise RuntimeError(f"{label}: unreadable supplier reference native line geometry")
    physical = [
        segment
        for segment in geometry.segments
        if segment.role == "dim-line"
        and abs((segment.y1 - segment.y0) if axis == 0 else (segment.x1 - segment.x0))
        <= _POSITION_TOLERANCE_M
        and any(
            dist(tip, endpoint) <= _POSITION_TOLERANCE_M
            for tip in tips
            for endpoint in ((segment.x0, segment.y0), (segment.x1, segment.y1))
        )
    ]
    # OffsetText connectors can be classified as ext-line too. Only the
    # perpendicular runs on actual arrow stations are physical witnesses.
    witnesses = []
    for tip in tips:
        runs = [
            segment
            for segment in geometry.segments
            if segment.role == "ext-line"
            and abs(
                (segment.x1 - segment.x0) if axis == 0 else (segment.y1 - segment.y0)
            )
            < 1e-7
            and abs((segment.x0 if axis == 0 else segment.y0) - tip[axis])
            <= _POSITION_TOLERANCE_M
        ]
        if not runs:
            raise RuntimeError(f"{label}: supplier reference lost a native witness")
        intervals = sorted(
            tuple(sorted(
                (segment.y0, segment.y1) if axis == 0 else (segment.x0, segment.x1)
            ))
            for segment in runs
        )
        coverage = []
        for low, high in intervals:
            if coverage and low <= coverage[-1][1] + _POSITION_TOLERANCE_M:
                coverage[-1] = (coverage[-1][0], max(coverage[-1][1], high))
            else:
                coverage.append((low, high))
        witnesses.extend((tip[axis], low, high) for low, high in coverage)
    if any(
        not any(
            dist(tip, endpoint) <= _POSITION_TOLERANCE_M
            for segment in physical
            for endpoint in ((segment.x0, segment.y0), (segment.x1, segment.y1))
        )
        for tip in tips
    ):
        raise RuntimeError(f"{label}: supplier reference lost native witness/line ink")
    reach = max(
        coordinate
        for segment in (
            *physical,
            *(segment for segment in geometry.segments if segment.role == "arrow"),
        )
        for coordinate in (
            (segment.x0, segment.x1) if axis == 0 else (segment.y0, segment.y1)
        )
    )
    return dict(
        record=record,
        text=text,
        axis=axis,
        tips=tips,
        witnesses=tuple(witnesses),
        reach=reach,
    )


def assert_reference_text_stations(
    before: dict[str, Any], after: dict[str, Any], *, label: str
) -> None:
    """Require unchanged native arrow tips and complete physical witness runs."""
    for key in ("tips", "witnesses"):
        if len(before[key]) != len(after[key]) or any(
            dist(old, new) > _POSITION_TOLERANCE_M
            for old, new in zip(before[key], after[key], strict=True)
        ):
            raise RuntimeError(f"{label}: supplier reference native {key} moved")


def _position(annotation: Any, *, label: str) -> tuple[float, ...]:
    position = tuple(float(value) for value in annotation.GetPosition())
    if len(position) != 3 or not all(map(isfinite, position)):
        raise RuntimeError(f"{label}: unreadable supplier reference text position")
    return position


@_telemetry.traced("drawing.shelve_reference_text", label_param="label")
def shelve_reference_text(
    adapter: Any,
    *,
    reacquire: Callable[[], Mapping[str, Any]],
    axes: Mapping[str, int],
    label: str,
    force: Collection[str] = (),
    audit_records: Callable[[Mapping[str, Mapping[str, Any]]], None] | None = None,
) -> Callable[[], None]:
    """Shelve short references in the +axis direction; return a read-only proof.

    ``reacquire`` must validate the caller's exact identities, attachments and
    source ownership and return fresh displays on every invocation. Its keys
    must exactly match ``axes`` throughout. ``force`` also shelves named text
    that fits its own span, for an authored multi-row reference placement.

    The sequence retains the proven shared-clamp measurement rebuild and three
    batched transition rebuilds. The returned proof performs no writes or
    rebuilds; its original measured stations stay private to the closure.
    ``audit_records``, if supplied, receives the same freshly measured raw
    records once every row passes the settled proof, initially and on each
    later invocation. It must be read-only: no native or record mutation.
    Records are local to that checkpoint, never copied or cached by this core.
    Callers retain complete native/PDF layout collision enforcement.
    """
    axes = dict(axes)
    if not axes or any(
        isinstance(axis, bool) or not isinstance(axis, int) or axis not in (0, 1)
        for axis in axes.values()
    ):
        raise ValueError(f"{label}: reference axes must be a nonempty 0/1 mapping")
    force = frozenset(force)
    if force - axes.keys():
        raise ValueError(f"{label}: forced shelves must name actual references")

    def current_displays() -> Mapping[str, Any]:
        found = reacquire()
        if set(found) != set(axes) or any(value is None for value in found.values()):
            raise RuntimeError(
                f"{label}: supplier reference inventory changed: "
                f"expected={sorted(axes)}, actual={sorted(found)}"
            )
        return found

    rebuild_drawing(adapter, label=f"{label} reference text measured")
    found = current_displays()
    before = {
        name: measure_reference_text(adapter, found[name], axis=axis, label=f"{label} {name}")
        for name, axis in axes.items()
    }
    positions = {}
    anchors = {}
    for name, geometry in before.items():
        axis = geometry["axis"]
        extent = geometry["text"].width if axis == 0 else geometry["text"].height
        span = geometry["tips"][1][axis] - geometry["tips"][0][axis]
        if name not in force and extent + 2 * (CLEAR_GAP_M + PLACE_SETTLE_M) <= span:
            continue
        display = _early_bound(found[name], "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        position = _position(annotation, label=f"{label} {name}")
        positions[name] = position
        anchor = list(position)
        anchor[1 - axis] = sum(tip[1 - axis] for tip in geometry["tips"]) / 2
        anchors[name] = tuple(anchor)
        if display.OffsetText is not False or not annotation.SetPosition2(*anchor):
            raise RuntimeError(f"{label} {name}: cannot seed supplier reference offset text")
    if positions:
        rebuild_drawing(adapter, label=f"{label} reference offset anchors")
        found = current_displays()
        for name, anchor in anchors.items():
            display = _early_bound(found[name], "IDisplayDimension")
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            actual = _position(annotation, label=f"{label} {name}")
            if dist(actual, anchor) > _POSITION_TOLERANCE_M:
                raise RuntimeError(f"{label} {name}: measured reference anchor did not settle")
            display.OffsetText = True
            if not annotation.SetPosition2(*anchor):
                raise RuntimeError(f"{label} {name}: cannot enable supplier reference offset text")
        rebuild_drawing(adapter, label=f"{label} reference native offset mode")
        found = current_displays()
        for name, position in positions.items():
            display = _early_bound(found[name], "IDisplayDimension")
            if display.OffsetText is not True:
                raise RuntimeError(f"{label} {name}: native reference offset mode did not persist")
            geometry = measure_reference_text(
                adapter, display, axis=axes[name], label=f"{label} {name}"
            )
            assert_reference_text_stations(before[name], geometry, label=f"{label} {name}")
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            target = list(_position(annotation, label=f"{label} {name}"))
            axis = axes[name]
            text = geometry["text"]
            low = text.xmin if axis == 0 else text.ymin
            target[axis] += geometry["reach"] + CLEAR_GAP_M + PLACE_SETTLE_M - low
            target[1 - axis] = position[1 - axis]
            if not annotation.SetPosition2(target[0], target[1], 0.0):
                raise RuntimeError(f"{label} {name}: cannot shelf supplier reference text")
        rebuild_drawing(adapter, label=f"{label} measured reference text shelves")

    stations = {
        name: {key: geometry[key] for key in ("tips", "witnesses")}
        for name, geometry in before.items()
    }

    def settled() -> None:
        found = current_displays()
        records = {}
        for name, original in stations.items():
            display = _early_bound(found[name], "IDisplayDimension")
            actual = measure_reference_text(
                adapter, display, axis=axes[name], label=f"{label} {name}"
            )
            assert_reference_text_stations(original, actual, label=f"{label} {name}")
            records[name] = actual["record"]
            if name not in positions:
                continue
            axis = axes[name]
            text = actual["text"]
            low = text.xmin if axis == 0 else text.ymin
            if display.OffsetText is not True or low < actual["reach"] + CLEAR_GAP_M:
                raise RuntimeError(f"{label} {name}: supplier reference text crowds its native line")
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            position = _position(annotation, label=f"{label} {name}")
            if abs(position[1 - axis] - positions[name][1 - axis]) > _POSITION_TOLERANCE_M:
                raise RuntimeError(f"{label} {name}: supplier reference transverse position moved")
        if audit_records is not None:
            audit_records(records)

    settled()
    return settled
