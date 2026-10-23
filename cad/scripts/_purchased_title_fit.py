"""Opt-in native title-cell fitting for purchased-part drawings.

Format and optionally align existing source-linked notes, never source properties
or saved templates.
A native SetTextFormat call removes the Name note's leading FONT size tag; only
that formatting syntax is excluded from property-expression identity checks.
The caller selects the existing material property; no alias or link is authored.
"""
from __future__ import annotations

import math
import re
from typing import Any, Callable, Literal

from _com import _early_bound
from _drawing_layout_audit import annotation_display
from _drawing_notes import property_link
from _drawing_registry import DrawingSpec
from _drawing_scan import _zoomed_on
from _purchased_fastener_drawing import (
    _box,
    _inside,
    _note_text_style,
    _number_state,
    _rebuild,
)
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
    """The actual sheet-format rules surrounding this note's existing anchor."""
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
    alignment: Literal["fixed", "label_right"] = "fixed",
    label_note: Any | None = None,
) -> Callable[[], None]:
    """Fit a linked value, optionally beside its immutable native MATERIAL label."""
    if alignment not in ("fixed", "label_right"):
        raise ValueError("alignment must be 'fixed' or 'label_right'")
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

    label_annotation = None
    label_anchor = label_style = label_layout = value_style = value_layout = None
    label_use_doc = value_use_doc = ()
    right_region = None
    accepted_style = None

    def layout_state(item: Any) -> tuple[float, int, int]:
        angle = item.Angle
        horizontal = item.GetTextJustification()
        vertical = item.GetTextVerticalJustification()
        if (
            type(angle) not in (int, float)
            or not math.isfinite(angle)
            or type(horizontal) is not int
            or type(vertical) is not int
        ):
            raise RuntimeError(f"{label}: unreadable native note angle or justification")
        return angle, horizontal, vertical

    def use_doc_state(item: Any, count: int) -> tuple[bool, ...]:
        flags = tuple(item.GetUseDocTextFormat(index) for index in range(count))
        if any(type(flag) is not bool for flag in flags):
            raise RuntimeError(f"{label}: unreadable native document-format flags")
        return flags

    if alignment == "label_right":
        if label_note is None:
            raise RuntimeError(f"{label}: label_right requires the unique MATERIAL label")
        if source_property_expression(link) != property_link(material_property):
            raise RuntimeError(f"{label}: label_right requires the selected Material source")
        label_annotation = _early_bound(label_note.GetAnnotation(), "IAnnotation")
        if (
            label_annotation is None
            or label_annotation.OwnerType != 2
            or annotation.OwnerType != 2  # swAnnotationOwner_DrawingTemplate
            or label_note.PropertyLinkedText != "MATERIAL"
            or label_note.GetText() != "MATERIAL"
        ):
            raise RuntimeError(f"{label}: MATERIAL label/value identity or format owner changed")
        label_anchor = tuple(float(value) for value in (label_annotation.GetPosition() or ()))
        if (
            len(label_anchor) != 3
            or not all(map(math.isfinite, label_anchor))
            or not all(map(math.isfinite, cell))
            or limit[0] >= limit[2]
            or limit[1] >= limit[3]
            or _ruled_cell(sheet, label_anchor) != cell
        ):
            raise RuntimeError(f"{label}: MATERIAL label must occupy the same valid ruled cell")
        label_style = _note_text_style(label_annotation)
        value_style = _note_text_style(annotation)
        label_layout, value_layout = layout_state(label_note), layout_state(note)
        label_use_doc = use_doc_state(label_annotation, len(label_style))
        value_use_doc = use_doc_state(annotation, len(value_style))

    def check_label_right_state(*, phase: str, formatted: bool) -> None:
        if alignment != "label_right":
            return
        actual_label_anchor = tuple(
            float(value) for value in (label_annotation.GetPosition() or ())
        )
        actual_anchor = tuple(float(value) for value in (annotation.GetPosition() or ()))
        actual_style = _note_text_style(annotation)
        # Only format zero's two height representations belong to the existing
        # height ladder. Every other format field, including the authority
        # method and LineLength, remains exactly as authored.
        protected_style = tuple(
            tuple(
                (name, value) for name, value in native_format
                if index != 0 or name not in ("CharHeight", "CharHeightInPts")
            )
            for index, native_format in enumerate(actual_style)
        )
        original_protected_style = tuple(
            tuple(
                (name, value) for name, value in native_format
                if index != 0 or name not in ("CharHeight", "CharHeightInPts")
            )
            for index, native_format in enumerate(value_style)
        )
        expected_use_doc = (False, *value_use_doc[1:]) if formatted else value_use_doc
        if (
            label_note.PropertyLinkedText != "MATERIAL"
            or label_note.GetText() != "MATERIAL"
            or label_annotation.OwnerType != 2
            or annotation.OwnerType != 2
            or len(actual_label_anchor) != 3
            or not all(map(math.isfinite, actual_label_anchor))
            or actual_label_anchor != label_anchor
            or len(actual_anchor) != 3
            or not all(map(math.isfinite, actual_anchor))
            or math.dist(actual_anchor, anchor) > _FORMAT_TOL
            or _ruled_cell(sheet, actual_label_anchor) != cell
            or _ruled_cell(sheet, actual_anchor) != cell
            or _note_text_style(label_annotation) != label_style
            or protected_style != original_protected_style
            or layout_state(label_note) != label_layout
            or layout_state(note) != value_layout
            or use_doc_state(label_annotation, len(label_style)) != label_use_doc
            or use_doc_state(annotation, len(actual_style)) != expected_use_doc
            or (accepted_style is not None and actual_style != accepted_style)
            or abs(dict(actual_style[0])["CharHeight"] - height) > _FORMAT_TOL
        ):
            # Diagnose only a refused candidate. Keep the predicate above and
            # its accepted-path native read surface unchanged; baseline styles
            # are detached primitives captured before any Material writes.
            differences: dict[str, dict[str, Any]] = {}

            def collect_difference(
                field: str, expected: Any, actual: Any, *, tolerance: float = 0,
            ) -> None:
                if expected == actual:
                    return
                change = {"expected": expected, "actual": actual, "tolerance": tolerance}
                if type(expected) in (int, float) and type(actual) in (int, float):
                    delta = actual - expected
                    if tolerance and abs(delta) <= tolerance:
                        return
                    change["delta"] = delta
                elif (
                    type(expected) is tuple
                    and type(actual) is tuple
                    and len(expected) == len(actual)
                    and all(type(value) in (int, float) for value in (*expected, *actual))
                ):
                    change["delta"] = tuple(
                        after - before for before, after in zip(expected, actual)
                    )
                    if tolerance:
                        distance = math.dist(expected, actual)
                        if distance <= tolerance:
                            return
                        change["distance"] = distance
                        change["comparison"] = "euclidean"
                differences[field] = change

            collect_difference("label.raw", "MATERIAL", label_note.PropertyLinkedText)
            collect_difference("label.resolved", "MATERIAL", label_note.GetText())
            collect_difference("label.OwnerType", 2, label_annotation.OwnerType)
            collect_difference("material.OwnerType", 2, annotation.OwnerType)
            collect_difference("label.anchor_m", label_anchor, actual_label_anchor)
            collect_difference(
                "material.anchor_m", anchor, actual_anchor, tolerance=_FORMAT_TOL,
            )
            for field, actual in (
                ("label.cell_m", actual_label_anchor), ("material.cell_m", actual_anchor),
            ):
                # Invalid anchors already differ above; do not invent a cell
                # or call the native grid extractor with an unreadable point.
                if len(actual) == 3 and all(map(math.isfinite, actual)):
                    collect_difference(field, cell, _ruled_cell(sheet, actual))
            style_pairs = (
                ("label.style", label_style, _note_text_style(label_annotation)),
                ("material.protected_style", original_protected_style, protected_style),
            )
            if accepted_style is not None:
                style_pairs += (("material.accepted_style", accepted_style, actual_style),)
            for field, expected, actual in style_pairs:
                collect_difference(f"{field}.count", len(expected), len(actual))
                for index, (before, after) in enumerate(zip(expected, actual)):
                    after_fields = dict(after)
                    for member, value in before:
                        collect_difference(
                            f"{field}[{index}].{member}", value, after_fields[member],
                        )
            for field, expected, actual in (
                ("label.layout", label_layout, layout_state(label_note)),
                ("material.layout", value_layout, layout_state(note)),
            ):
                for member, before, after in zip(
                    ("angle", "horizontal_justification", "vertical_justification"),
                    expected, actual, strict=True,
                ):
                    collect_difference(f"{field}.{member}", before, after)
            for field, expected, actual in (
                ("label.useDoc", label_use_doc,
                 use_doc_state(label_annotation, len(label_style))),
                ("material.useDoc", expected_use_doc,
                 use_doc_state(annotation, len(actual_style))),
            ):
                collect_difference(f"{field}.count", len(expected), len(actual))
                for index, (before, after) in enumerate(zip(expected, actual)):
                    collect_difference(f"{field}[{index}]", before, after)
            collect_difference(
                "material.height_m", height, dict(actual_style[0])["CharHeight"],
                tolerance=_FORMAT_TOL,
            )
            raise RuntimeError(
                f"{label}: MATERIAL label or protected value style/anchor changed; "
                f"phase={phase!r}, formatted={formatted!r}, differences={differences!r}"
            )

    def measure(phase: str, *, formatted: bool = True) -> tuple[tuple[float, ...], int]:
        nonlocal right_region
        actual_link, actual_text = note.PropertyLinkedText, note.GetText()
        try:
            assert_linked_value(link, text, actual_link, actual_text, label=label)
        except RuntimeError as exc:
            raise RuntimeError(
                f"{exc}; phase={phase!r}, native={_number_state(adapter, note, annotation)}"
            ) from exc
        check_label_right_state(phase=phase, formatted=formatted)
        with _zoomed_on(adapter, centre, half):
            box = _box(note.GetExtent(), label=label, kind="note")
            display, refused = annotation_display(adapter, annotation)
            label_box = (
                _box(label_note.GetExtent(), label=f"{label} MATERIAL label", kind="note")
                if alignment == "label_right" else None
            )
        runs = display.get("texts", ())
        if refused or not runs:
            raise RuntimeError(f"{label}: native text rows unavailable: {refused!r}")
        rows = len({round(float(run["pos"][1]), 6) for run in runs})
        if label_box is not None:
            right_region = (
                label_box[2] + _CELL_CLEARANCE, limit[1], limit[2], limit[3],
            )
            if (
                not _inside(label_box, limit)
                or not all(map(math.isfinite, right_region))
                or right_region[0] >= right_region[2]
                or right_region[1] >= right_region[3]
            ):
                raise RuntimeError(
                    f"{label}: MATERIAL label has no valid inset right region; "
                    f"label_extent={label_box!r}, cell={cell!r}"
                )
        _telemetry.event(
            "drawing.purchased_title_fit.candidate",
            label=label,
            phase=phase,
            height_m=height,
            rows=rows,
            extent=box,
            cell=cell,
            alignment=alignment,
            requested_anchor_m=anchor,
            label_extent=label_box,
            right_region=right_region,
            accepted_anchor_m=(
                anchor if note_fits_cell(
                    box, rows, right_region if alignment == "label_right" else limit,
                ) else None
            ),
            label_gap_m=box[0] - label_box[2] if label_box is not None else None,
        )
        return box, rows

    if alignment == "label_right":
        measure("before-title-fit", formatted=False)
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
        if alignment == "label_right" and (
            box[2] - box[0] <= right_region[2] - right_region[0]
            and box[3] - box[1] <= right_region[3] - right_region[1]
        ):
            # Centre the complete measured value in the actual region to the
            # label's right, not on the clearance boundary. Original cell
            # insets and the value's sheet Z remain unchanged.
            rows_before_move = rows
            target = (
                anchor[0] + (right_region[0] + right_region[2] - box[0] - box[2]) / 2,
                anchor[1] + (right_region[1] + right_region[3] - box[1] - box[3]) / 2,
                anchor[2],
            )
            if not all(map(math.isfinite, target)):
                raise RuntimeError(f"{label}: invalid label-right title position {target!r}")
            if annotation.SetPosition2(*target) is not True:
                raise RuntimeError(f"{label}: label-right title position setter refused")
            actual_anchor = tuple(float(value) for value in (annotation.GetPosition() or ()))
            if (
                len(actual_anchor) != 3
                or not all(map(math.isfinite, actual_anchor))
                or math.dist(actual_anchor, target) > _FORMAT_TOL
            ):
                raise RuntimeError(
                    f"{label}: label-right title position did not persist; "
                    f"expected {target!r}, actual {actual_anchor!r}"
                )
            anchor = target
            _rebuild(draw, phase=f"{label} title-cell label-right alignment")
            box, rows = measure("after-title-label-right-rebuild")
            if rows != rows_before_move:
                raise RuntimeError(f"{label}: moving the Material value changed its native rows")
            if not _inside(box, right_region):
                raise RuntimeError(
                    f"{label}: moved Material value leaves its measured right region; "
                    f"extent={box!r}, region={right_region!r}"
                )
        if note_fits_cell(box, rows, right_region if alignment == "label_right" else limit):
            break
        if height <= minimum + _FORMAT_TOL:
            raise RuntimeError(
                f"{label}: complete linked value {text!r} cannot fit its native "
                f"ruled cell {cell!r} at readable floor {minimum!r} m: "
                f"{rows} rows, extent {box!r}; "
                f"native={_number_state(adapter, note, annotation)}"
            )
        height = max(minimum, round(height - _HEIGHT_STEP, 7))

    if alignment == "label_right":
        accepted_style = _note_text_style(annotation)
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
            or not all(map(math.isfinite, actual_anchor))
            or math.dist(actual_anchor, anchor) > _FORMAT_TOL
            or not note_fits_cell(box, rows, limit)
            or (alignment == "label_right" and not _inside(box, right_region))
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
    material_alignment: Literal["fixed", "label_right"] = "fixed",
) -> Callable[[], None]:
    """Fit Name/selected Material/Number; return strict final-rebuild checks.

    ``material_property`` names the source property already linked by the sheet.
    The default preserves the captured-pivot and kit consumers unchanged.
    ``material_alignment="label_right"`` centres the complete Material value
    beside the unique, unchanged MATERIAL label in their original inset cell.
    The default retains every note's original fixed anchor and read surface.
    """
    if material_alignment not in ("fixed", "label_right"):
        raise ValueError("material_alignment must be 'fixed' or 'label_right'")
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
    material_labels = [] if material_alignment == "label_right" else None
    note = sheet_view.GetFirstNote2()
    while note is not None:
        note = _early_bound(note, "INote")
        expression = source_property_expression(str(note.PropertyLinkedText))
        if expression in found:
            found[expression].append(note)
        if material_alignment == "label_right" and (
            note.PropertyLinkedText == "MATERIAL" or note.GetText() == "MATERIAL"
        ):
            material_labels.append(note)
        note = note.GetNext()
    counts = {expression: len(notes) for expression, notes in found.items()}
    if any(count != 1 for count in counts.values()):
        raise RuntimeError(f"purchased title block requires one note per source field: {counts!r}")
    name = found[property_link("SW-Title(Title)")][0]
    if str(name.GetText()) != spec.artifact_stem:
        raise RuntimeError(
            f"purchased Name value {name.GetText()!r} is not source identity {spec.artifact_stem!r}"
        )
    if material_alignment == "label_right" and len(material_labels) != 1:
        raise RuntimeError(
            "purchased title block requires one exact MATERIAL label: "
            f"found {len(material_labels)}"
        )
    material_label_name = material_labels[0].GetName() if material_labels else None
    if material_alignment == "label_right" and (
        type(material_label_name) is not str or not material_label_name.strip()
    ):
        raise RuntimeError("purchased MATERIAL label has no native identity")
    checks = tuple(
        _fit_title_note(
            adapter,
            draw,
            sheet,
            found[expression][0],
            label=f"{spec.artifact_stem} {label}",
            minimum=minimum,
            material_property=material_property,
            alignment=(
                material_alignment
                if expression == property_link(material_property)
                else "fixed"
            ),
            label_note=(
                material_labels[0]
                if material_alignment == "label_right"
                and expression == property_link(material_property)
                else None
            ),
        )
        for expression, (label, minimum) in fields.items()
    )

    def settled() -> None:
        if material_alignment == "label_right":
            # Re-enumeration is read-only: a retained COM wrapper alone cannot
            # prove that this is still the unique label in the sheet view.
            labels = []
            current = sheet_view.GetFirstNote2()
            while current is not None:
                current = _early_bound(current, "INote")
                if current.PropertyLinkedText == "MATERIAL" or current.GetText() == "MATERIAL":
                    labels.append(current)
                current = current.GetNext()
            if len(labels) != 1 or labels[0].GetName() != material_label_name:
                raise RuntimeError("purchased MATERIAL label membership or native identity changed")
        for check in checks:
            check()

    return settled
