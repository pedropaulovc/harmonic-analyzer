"""Opt-in native title-cell fitting for purchased-part drawings.

Format existing source-linked notes, never source properties or saved templates.
A native SetTextFormat call removes the Name note's leading FONT size tag; only
that formatting syntax is excluded from property-expression identity checks.
The caller selects the existing material property; no alias or link is authored.
"""
from __future__ import annotations

import math
import re
from typing import Any, Callable

from _com import _early_bound
from _drawing_layout_audit import annotation_display
from _drawing_notes import property_link
from _drawing_registry import DrawingSpec
from _drawing_scan import _zoomed_on
from _purchased_fastener_drawing import _box, _inside, _number_state, _rebuild
import _telemetry

# Full-match one source-model property expression with, optionally, the native
# point-size prefix observed on these template notes. Do not strip arbitrary
# tags, literals, whitespace, extra expressions or property ownership markers.
_SOURCE_PROPERTY = re.compile(
    r'(?:<FONT size=(?P<points>[0-9]+(?:\.[0-9]+)?)PTS>)?'
    r'(?P<expression>\$PRPSHEET:"[^"<>\r\n]+")'
)
_CELL_CLEARANCE = 0.0006
_HEIGHT_STEP = 0.0001
_FORMAT_TOL = 1e-7


def source_property_expression(raw: str) -> str | None:
    """Identify one complete source link, independent only of its FONT size tag."""
    match = _SOURCE_PROPERTY.fullmatch(raw)
    if match is None:
        return None
    points = match["points"]
    if points is not None and (not math.isfinite(float(points)) or float(points) <= 0):
        return None
    return match["expression"]


def assert_linked_value(
    expected_link: str,
    expected_text: str,
    actual_link: str,
    actual_text: str,
    *,
    label: str,
) -> None:
    """Require exact property ownership/expression and complete resolved value."""
    expected = source_property_expression(expected_link)
    if (
        expected is None
        or source_property_expression(actual_link) != expected
        or actual_text != expected_text
    ):
        raise RuntimeError(
            f"{label}: source property expression or complete value changed; "
            f"expected_link={expected_link!r}, actual_link={actual_link!r}, "
            f"expected_text={expected_text!r}, actual_text={actual_text!r}"
        )


def note_fits_cell(
    box: tuple[float, ...], rows: int, limit: tuple[float, ...]
) -> bool:
    """The whole measured note must fit its inset ruled cell on one native row."""
    return rows == 1 and _inside(box, limit)


def _ruled_cell(sheet: Any, anchor: tuple[float, ...]) -> tuple[float, ...]:
    """The actual sheet-format rules surrounding this note's unchanged anchor."""
    sketch = _early_bound(sheet.GetTemplateSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError("purchased title block has no native sheet-format sketch")
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
            raise RuntimeError("purchased title-block rule has no endpoints")
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
        raise RuntimeError("cannot identify the purchased note's native ruled cell") from exc


def _fit_title_note(
    adapter: Any, draw: Any, sheet: Any, note: Any, *, label: str, minimum: float,
    material_property: str = "Material Specification",
) -> Callable[[], None]:
    """Fit this existing linked note on a bounded native-height ladder."""
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{label}: note has no annotation")
    link, text = str(note.PropertyLinkedText), str(note.GetText())
    anchor = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(anchor) != 3 or not all(map(math.isfinite, anchor)):
        raise RuntimeError(f"{label}: invalid native anchor {anchor!r}")
    cell = _ruled_cell(sheet, anchor)
    limit = (
        cell[0] + _CELL_CLEARANCE,
        cell[1] + _CELL_CLEARANCE,
        cell[2] - _CELL_CLEARANCE,
        cell[3] - _CELL_CLEARANCE,
    )
    # In this fixture the Material LineLength write persisted but did not
    # widen the wrapped text. Leave that note's authored wrap metadata alone;
    # keep the bounded length used by the successful Name path and DWG. NO.
    line_length = (
        None
        if source_property_expression(link) == property_link(material_property)
        else limit[2] - anchor[0] - 0.0003
    )
    centre = ((cell[0] + cell[2]) / 2, (cell[1] + cell[3]) / 2)
    half = max(cell[2] - cell[0], cell[3] - cell[1]) / 2 + 0.002
    text_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
    if text_format is None:
        raise RuntimeError(f"{label}: note has no native text format")
    height, face = float(text_format.CharHeight), str(text_format.TypeFaceName)
    if (
        not math.isfinite(height)
        or height < minimum
        or not face.strip()
        or (line_length is not None and line_length <= 0)
    ):
        raise RuntimeError(f"{label}: unreadable native format or cell")

    def measure(phase: str) -> tuple[tuple[float, ...], int]:
        actual_link, actual_text = note.PropertyLinkedText, note.GetText()
        try:
            assert_linked_value(link, text, actual_link, actual_text, label=label)
        except RuntimeError as exc:
            raise RuntimeError(
                f"{exc}; phase={phase!r}, native={_number_state(adapter, note, annotation)}"
            ) from exc
        with _zoomed_on(adapter, centre, half):
            box = _box(note.GetExtent(), label=label, kind="note")
            display, refused = annotation_display(adapter, annotation)
        runs = display.get("texts", ())
        if refused or not runs:
            raise RuntimeError(f"{label}: native text rows unavailable: {refused!r}")
        rows = len({round(float(run["pos"][1]), 6) for run in runs})
        _telemetry.event(
            "drawing.purchased_title_fit.candidate",
            label=label,
            phase=phase,
            height_m=height,
            rows=rows,
            extent=box,
            cell=cell,
        )
        return box, rows

    # Measure every candidate; no source text is rewritten or cut. The material
    # property's semantic content is owned by the registry, not by this fitter.
    while True:
        if line_length is not None:
            text_format.LineLength = line_length
        text_format.CharHeight = height
        if annotation.SetTextFormat(0, False, text_format) is not True:
            raise RuntimeError(f"{label}: local text format setter refused")
        _rebuild(draw, phase=f"{label} title-cell fit")
        box, rows = measure("after-fit-rebuild")
        if note_fits_cell(box, rows, limit):
            break
        if height <= minimum + _FORMAT_TOL:
            raise RuntimeError(
                f"{label}: complete linked value {text!r} cannot fit its native "
                f"ruled cell {cell!r} at readable floor {minimum!r} m: "
                f"{rows} rows, extent {box!r}; "
                f"native={_number_state(adapter, note, annotation)}"
            )
        height = max(minimum, round(height - _HEIGHT_STEP, 7))

    def settled() -> None:
        actual_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
        actual_anchor = tuple(float(value) for value in (annotation.GetPosition() or ()))
        box, rows = measure("settled")
        if (
            actual_format is None
            or abs(float(actual_format.CharHeight) - height) > _FORMAT_TOL
            or (
                line_length is not None
                and abs(float(actual_format.LineLength) - line_length) > _FORMAT_TOL
            )
            or str(actual_format.TypeFaceName) != face
            or annotation.GetUseDocTextFormat(0) is not False
            or len(actual_anchor) != 3
            or math.dist(actual_anchor, anchor) > _FORMAT_TOL
            or not note_fits_cell(box, rows, limit)
        ):
            raise RuntimeError(
                f"{label}: linked title-cell fit did not persist; "
                f"extent {box!r}, native cell {cell!r}; "
                f"native={_number_state(adapter, note, annotation)}"
            )
        _telemetry.info(
            f"{label}: linked value {text!r}, height {height!r} m, "
            f"extent {box!r}, native ruled cell {cell!r}"
        )

    settled()
    return settled


def fit_purchased_title_block(
    adapter: Any, *, spec: DrawingSpec,
    material_property: str = "Material Specification",
) -> Callable[[], None]:
    """Fit Name/selected Material/Number; return strict final-rebuild checks.

    ``material_property`` names the source property already linked by the sheet.
    The default preserves the captured-pivot and kit consumers unchanged.
    """
    # Native metres, not authored points converted at 72 dpi. The material floor
    # remains 2 mm even if the complete purchased specification cannot fit.
    fields = {
        property_link("SW-Title(Title)"): ("Name", 0.003),
        property_link(material_property): ("Material", 0.002),
        property_link("Number"): ("DWG. NO.", 0.003),
    }
    if len(fields) != 3:
        raise RuntimeError(
            "purchased title block requires three distinct source fields; "
            f"material_property={material_property!r} overlaps Name or Number"
        )
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    sheet_view = _early_bound(ddoc.GetFirstView(), "IView")
    if sheet is None or sheet_view is None:
        raise RuntimeError("purchased drawing has no native sheet or sheet view")
    found: dict[str, list[Any]] = {expression: [] for expression in fields}
    note = sheet_view.GetFirstNote2()
    while note is not None:
        note = _early_bound(note, "INote")
        expression = source_property_expression(str(note.PropertyLinkedText))
        if expression in found:
            found[expression].append(note)
        note = note.GetNext()
    counts = {expression: len(notes) for expression, notes in found.items()}
    if any(count != 1 for count in counts.values()):
        raise RuntimeError(f"purchased title block requires one note per source field: {counts!r}")
    name = found[property_link("SW-Title(Title)")][0]
    if str(name.GetText()) != spec.artifact_stem:
        raise RuntimeError(
            f"purchased Name value {name.GetText()!r} is not source identity {spec.artifact_stem!r}"
        )
    checks = tuple(
        _fit_title_note(
            adapter,
            draw,
            sheet,
            found[expression][0],
            label=f"{spec.artifact_stem} {label}",
            minimum=minimum,
            material_property=material_property,
        )
        for expression, (label, minimum) in fields.items()
    )

    def settled() -> None:
        for check in checks:
            check()

    return settled
