"""Purchased reference sheet for MHA-CH-06-TL-VN-74.

Only this drawing widens and, if necessary, fits its existing linked PART and
MATERIAL notes inside their native ruled cells. The source properties, note
anchors, typefaces, saved template and four reference views remain unchanged.
"""
from __future__ import annotations

import argparse
import math
import sys
from typing import Any, Callable

import _telemetry
from _com import _early_bound
from _drawing_layout_audit import annotation_display
from _drawing_notes import property_link
from _drawing_scan import _zoomed_on
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_part_drawing import build_purchased_part_drawing
from _purchased_fastener_drawing import _box, _inside, _number_state, _rebuild
from ch_rocker_arm_tl_vn_oblique_pivot_clevis_pin_spec import CALLOUT

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_clevis_pin"]
ITEM = CALLOUT

# Native font metres, not authored points converted at 72 dpi. These are local
# readability floors; a note that cannot fit at its floor refuses the export.
_NAME_MIN_HEIGHT = 0.003
_MATERIAL_MIN_HEIGHT = 0.002
_CELL_CLEARANCE = 0.0006
_HEIGHT_STEP = 0.0001
_FORMAT_TOL = 1e-7


def _ruled_cell(sheet: Any, anchor: tuple[float, ...]) -> tuple[float, ...]:
    """The actual sheet-format rules surrounding this note's unchanged anchor."""
    sketch = _early_bound(sheet.GetTemplateSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError("clevis title block has no native sheet-format sketch")
    x, y = anchor[:2]
    horizontal, vertical = [], []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        if segment.GetType() != 0:  # swSketchLINE
            continue
        line = _early_bound(raw, "ISketchLine")
        start = _early_bound(line.GetStartPoint2(), "ISketchPoint")
        end = _early_bound(line.GetEndPoint2(), "ISketchPoint")
        if start is None or end is None:
            raise RuntimeError("clevis title-block rule has no endpoints")
        x1, y1, x2, y2 = map(float, (start.X, start.Y, end.X, end.Y))
        if abs(y1 - y2) < 1e-8 and min(x1, x2) < x < max(x1, x2):
            horizontal.append(y1)
        if abs(x1 - x2) < 1e-8 and min(y1, y2) < y < max(y1, y2):
            vertical.append(x1)
    try:
        return (
            max(value for value in vertical if value < x),
            max(value for value in horizontal if value < y),
            min(value for value in vertical if value > x),
            min(value for value in horizontal if value > y),
        )
    except ValueError as exc:
        raise RuntimeError("cannot identify the clevis note's native ruled cell") from exc


def _fit_title_note(
    adapter: Any, draw: Any, sheet: Any, note: Any, *, label: str, minimum: float
) -> Callable[[], None]:
    """Widen only this note; retain the largest native height fitting one row."""
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"clevis {label}: note has no annotation")
    link, text = str(note.PropertyLinkedText), str(note.GetText())
    anchor = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(anchor) != 3 or not all(map(math.isfinite, anchor)):
        raise RuntimeError(f"clevis {label}: invalid native anchor {anchor!r}")
    cell = _ruled_cell(sheet, anchor)
    limit = (
        cell[0] + _CELL_CLEARANCE,
        cell[1] + _CELL_CLEARANCE,
        cell[2] - _CELL_CLEARANCE,
        cell[3] - _CELL_CLEARANCE,
    )
    line_length = limit[2] - anchor[0] - 0.0003
    centre = ((cell[0] + cell[2]) / 2, (cell[1] + cell[3]) / 2)
    half = max(cell[2] - cell[0], cell[3] - cell[1]) / 2 + 0.002
    text_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
    if text_format is None:
        raise RuntimeError(f"clevis {label}: note has no native text format")
    height, face = float(text_format.CharHeight), str(text_format.TypeFaceName)
    if not math.isfinite(height) or height < minimum or not face.strip() or line_length <= 0:
        raise RuntimeError(f"clevis {label}: unreadable native format or cell")

    def record(phase: str) -> tuple[Any, Any, str]:
        actual_link, actual_text = note.PropertyLinkedText, note.GetText()
        # The first native refusal did not retain the differing strings. Record
        # every COM write boundary so a changed link, resolved value or format
        # can be attributed without weakening the complete-value contract.
        state = (
            f"clevis {label}: phase={phase!r}, expected_link={link!r}, "
            f"actual_link={actual_link!r}, expected_text={text!r}, "
            f"actual_text={actual_text!r}, requested_height_m={height!r}, "
            f"requested_line_length_m={line_length!r}, "
            f"native={_number_state(adapter, note, annotation)}"
        )
        _telemetry.info(state)
        _telemetry.event(
            "drawing.clevis_title_fit.state", label=label, phase=phase, state=state
        )
        return actual_link, actual_text, state

    def measure(phase: str) -> tuple[tuple[float, ...], int]:
        actual_link, actual_text, state = record(phase)
        if actual_link != link or actual_text != text:
            raise RuntimeError(
                f"clevis {label}: source link or complete value changed; {state}"
            )
        with _zoomed_on(adapter, centre, half):
            box = _box(note.GetExtent(), label=label, kind="note")
            display, refused = annotation_display(adapter, annotation)
        runs = display.get("texts", ())
        if refused or not runs:
            raise RuntimeError(f"clevis {label}: native text rows unavailable: {refused!r}")
        rows = len({round(float(run["pos"][1]), 6) for run in runs})
        return box, rows

    # The original material box wraps at about 60 mm although its ruled cell
    # is 92.45 mm wide. Use the real cell first, then reduce only this note in
    # bounded 0.1 mm native-height steps, measuring every candidate.
    record("before-format-properties")
    while True:
        text_format.LineLength = line_length
        record("after-line-length")
        text_format.CharHeight = height
        record("after-char-height")
        if annotation.SetTextFormat(0, False, text_format) is not True:
            raise RuntimeError(f"clevis {label}: local text format setter refused")
        record("after-set-text-format")
        _rebuild(draw, phase=f"clevis {label} title-cell fit")
        box, rows = measure("after-fit-rebuild")
        if rows == 1 and _inside(box, limit):
            break
        if height <= minimum + _FORMAT_TOL:
            raise RuntimeError(
                f"clevis {label}: complete linked value cannot fit its ruled cell "
                f"{cell!r} at {minimum!r} m: {rows} rows, extent {box!r}"
            )
        height = max(minimum, round(height - _HEIGHT_STEP, 7))

    def settled() -> None:
        actual_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
        actual_anchor = tuple(float(value) for value in (annotation.GetPosition() or ()))
        box, rows = measure("settled")
        if (
            actual_format is None
            or abs(float(actual_format.CharHeight) - height) > _FORMAT_TOL
            or abs(float(actual_format.LineLength) - line_length) > _FORMAT_TOL
            or str(actual_format.TypeFaceName) != face
            or annotation.GetUseDocTextFormat(0) is not False
            or len(actual_anchor) != 3
            or math.dist(actual_anchor, anchor) > _FORMAT_TOL
            or rows != 1
            or not _inside(box, limit)
        ):
            raise RuntimeError(
                f"clevis {label}: linked title-cell fit did not persist; "
                f"extent {box!r}, native cell {cell!r}"
            )
        _telemetry.info(
            f"clevis {label}: linked value {text!r}, height {height!r} m, "
            f"extent {box!r}, native ruled cell {cell!r}"
        )

    settled()
    return settled


def _fit_title_block(adapter: Any) -> Callable[[], None]:
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    sheet_view = _early_bound(ddoc.GetFirstView(), "IView")
    if sheet is None or sheet_view is None:
        raise RuntimeError("clevis drawing has no native sheet or sheet view")
    names, materials = [], []
    note = sheet_view.GetFirstNote2()
    while note is not None:
        note = _early_bound(note, "INote")
        raw = str(note.PropertyLinkedText)
        # The template's Name note reads the model's summary Title, not a
        # custom property named Name. Discover its actual link, never replace it.
        if str(note.GetText()) == SPEC.artifact_stem and "$PRPSHEET:" in raw:
            names.append(note)
        if raw == property_link("Material Specification"):
            materials.append(note)
        note = note.GetNext()
    if len(names) != 1 or len(materials) != 1:
        raise RuntimeError(
            "clevis title block requires one source-linked Name and Material note: "
            f"{len(names)} Name, {len(materials)} Material"
        )
    checks = (
        _fit_title_note(
            adapter, draw, sheet, names[0], label="Name", minimum=_NAME_MIN_HEIGHT
        ),
        _fit_title_note(
            adapter, draw, sheet, materials[0], label="Material", minimum=_MATERIAL_MIN_HEIGHT
        ),
    )

    def settled() -> None:
        for check in checks:
            check()

    return settled


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_part_drawing(
        adapter, SPEC, item=ITEM, title_block_setup=_fit_title_block
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
