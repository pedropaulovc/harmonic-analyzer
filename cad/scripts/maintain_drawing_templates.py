"""Maintain the two hand-authored DRWDOTs through an already-held farm COM seat.

This edits copies, never the checked-in templates, and never opens a second
session. The CLI is a run_build entry point; farm bootstrap callers invoke
maintain_templates(adapter) inside their existing run_build instead. Website,
general-note ("inside-corner") and line-weight edits are independent
selectable operations.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import re
import sys
from typing import Any, Iterator

from solidworks_mcp.adapters.sw_type_info import constant

import _telemetry
from _com import _early_bound, _read_member
from _drawing_layout_audit import annotation_display
from _drawing_registry import DRAWING_TEMPLATES
from _drawing_scan import _zoomed_on
from _layout_audit import display_box
from _part_properties import title_block_properties
from _paths import CAD_ROOT

OLD_WEBSITE = "harmonic-analyzer.vza.net"
NEW_WEBSITE = "harmonicanalyzer.com"
INSIDE_CORNER_LINK = 'INSIDE CORNERS $PRPSHEET:"TOL_INSIDE_CORNER"'
THREAD_LINK = 'THREADS $PRPSHEET:"THREAD_TYPE" CLASS $PRPSHEET:"THREAD_CLASS"'
EDGE_BREAK_LINK = (
    'REMOVE BURRS AND BREAK SHARP EDGES $PRPSHEET:"TOL_EDGE_BREAK_R" '
    'OR CHAMFER $PRPSHEET:"TOL_CHAMFER_MAX" MAX'
)
# Issue #1636: ONE general-note text block, top to bottom, in one font run.
GENERAL_NOTE_LINES = (INSIDE_CORNER_LINK, THREAD_LINK, EDGE_BREAK_LINK)
GENERAL_NOTE_LINK = "\r\n".join(GENERAL_NOTE_LINES)
# The installed templates' two notes that the block replaces (native census,
# farm run 20261020T034919997Z): the edge-break/thread note, and the separate
# inside-corner row below the tolerance rows, which is deleted.
_SOURCE_GENERAL_NOTE = "\r\n".join((EDGE_BREAK_LINK, THREAD_LINK))
_SOURCE_INSIDE_CORNER_NOTE = "HA_INSIDE_CORNERS"
_SW_NOTE = 6  # swAnnotationType_e.swNote
_SW_SF_SYMBOL = 7  # swAnnotationType_e.swSFSymbol
OPERATIONS = ("website", "inside-corner", "line-weights")
OUTPUT_DIR = CAD_ROOT / "out" / "templates"
_CLEARANCE = 0.0004  # Native text-box clearance to existing notes and cell rules.
_UNIFORM_M = 1e-6  # Rendered rows share x and pitch to a micrometre.
_LINK = re.compile(r'\$PRPSHEET:"([^"]+)"')
_FONT_FIELDS = (
    "TypeFaceName",
    "CharHeight",
    "CharHeightInPts",
    "IsHeightSpecifiedInPts",
    "Bold",
    "Italic",
    "Underline",
    "Strikeout",
    "WidthFactor",
    "CharSpacingFactor",
    "LineSpacing",
    "LineLength",
    "Escapement",
    "ObliqueAngle",
    "BackWards",
    "UpsideDown",
    "Vertical",
)
_WEIGHT_SLOTS = (
    "Thin",
    "Normal",
    "Thick",
    "Thick2",
    "Thick3",
    "Thick4",
    "Thick5",
    "Thick6",
)
_THIN_FONTS = (
    "swLineFontHiddenEdgesThickness",
    "swLineFontTangentEdgesThickness",
    "swLineFontCosmeticThreadThickness",
    "swLineFontCrosshatchThickness",
    "swDetailingNoteLeaderLineThickness",
    "swDetailingGtolLeaderLineThickness",
    "swDetailingGtolFrameLineThickness",
    "swDetailingDatumLeaderLineThickness",
    "swDetailingDatumFrameLineThickness",
    "swDetailingSFSymbolLeaderLineThickness",
)
_NO_OPTION = "swDetailingNoOptionSpecified"
_DIMENSION_OPTIONS = (
    "swDetailingLinearDimension",
    "swDetailingDiameterDimension",
    "swDetailingRadiusDimension",
    "swDetailingAngleDimension",
    "swDetailingOrdinateDimension",
    "swDetailingHoleDimension",
    "swDetailingChamferDimension",
    "swDetailingArcLengthDimension",
    "swDetailingAngularRunningDimension",
)
# Radius, hole-callout and chamfer pages have no extension-thickness setting.
_EXTENSION_OPTIONS = tuple(
    option
    for option in _DIMENSION_OPTIONS
    if option
    not in (
        "swDetailingRadiusDimension",
        "swDetailingHoleDimension",
        "swDetailingChamferDimension",
    )
)
# DP_LineFont / DP_Annotations-Balloons / DP_Dimensions-* specify these scopes.
# Use the identical preference+option pairs for mutation AND the native census.
_LINE_FONT_SETTINGS = (
    ("swLineFontVisibleEdgesThickness", _NO_OPTION, "swLW_THICK"),
    *((name, _NO_OPTION, "swLW_THIN") for name in _THIN_FONTS),
    ("swDetailingBalloonLeaderLineThickness", "swDetailingBalloon", "swLW_THIN"),
    ("swDetailingBalloonFrameLineThickness", "swDetailingBalloon", "swLW_THIN"),
    *(
        ("swLineFontDimensionsThickness", option, "swLW_THIN")
        for option in _DIMENSION_OPTIONS
    ),
    *(
        ("swDimensionsExtensionLineStyleThickness", option, "swLW_THIN")
        for option in _EXTENSION_OPTIONS
    ),
)


def _numbers(values: Any) -> list[float]:
    return [round(float(value), 12) for value in values]


def _notes(drawing: Any) -> list[Any]:
    # The first view is the SHEET view: model-view GetNotes misses the format.
    view = _early_bound(drawing.GetFirstView(), "IView")
    if view is None:
        raise RuntimeError("drawing template has no sheet view")
    result = []
    note = view.GetFirstNote2()
    while note is not None:
        note = _early_bound(note, "INote")
        result.append(note)
        note = note.GetNext()
    return result


def _note_census(note: Any) -> dict[str, Any]:
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    formats = []
    for index in range(int(annotation.GetTextFormatCount())):
        fmt = _early_bound(annotation.GetTextFormat(index), "ITextFormat")
        if fmt is None:
            raise RuntimeError(f"note {note.GetName()!r} has no text format {index}")
        font_values = {}
        for name in _FONT_FIELDS:
            # The generated ITextFormat API exposes IsHeightSpecifiedInPts as
            # a zero-argument METHOD; the other census fields are properties.
            value = _read_member(fmt, name)
            if not isinstance(value, (str, bool, int, float)):
                raise TypeError(
                    f"ITextFormat.{name} returned {type(value).__name__}, "
                    "expected a primitive font value"
                )
            font_values[name] = value
        formats.append(
            {
                "document_default": bool(annotation.GetUseDocTextFormat(index)),
                **font_values,
            }
        )
    linked_text = str(note.PropertyLinkedText or "")
    text = str(note.GetText() or "")
    try:
        extent = _numbers(note.GetExtent() or ())
    except Exception:
        if text.strip():
            raise
        extent = []
    rendered = len(extent) == 6 and extent[3] > extent[0] and extent[4] > extent[1]
    if not rendered and text.strip():
        raise RuntimeError(f"populated note {note.GetName()!r} has no native extent")
    return {
        "name": str(note.GetName()),
        "linked_text": linked_text,
        "text": text,
        "position_m": _numbers(annotation.GetPosition()),
        "extent_m": extent if rendered else None,
        "extent_unavailable": None if rendered else "empty/unrendered note",
        "has_multiple_fonts": bool(note.HasMultipleFonts),
        "angle": float(note.Angle),
        "justification": int(note.GetTextJustification()),
        "formats": formats,
        "text_runs": [
            {
                "text": str(note.GetTextAtIndex(index) or ""),
                # GetTextAtIndex is 1-based; font/height accessors are 0-based.
                "font": str(note.GetTextFontAtIndex(index - 1) or ""),
                "height_m": float(note.GetTextHeightAtIndex(index - 1)),
            }
            for index in range(1, int(note.GetTextCount()) + 1)
        ],
    }


def _geometry(sheet: Any) -> dict[str, Any]:
    sketch = _early_bound(sheet.GetTemplateSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError("template has no embedded sheet-format sketch")
    segments = []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        record = {
            "id": list(segment.GetID()),
            "type": int(segment.GetType()),
            "length_m": round(float(segment.GetLength()), 12),
            "width": int(segment.Width),
            "style": int(segment.Style),
            "layer": str(segment.Layer or ""),
            "layer_override": int(segment.LayerOverride),
        }
        if record["type"] == 0:  # swSketchLINE
            line = _early_bound(raw, "ISketchLine")
            points = []
            for point in (line.GetStartPoint2(), line.GetEndPoint2()):
                point = _early_bound(point, "ISketchPoint")
                points.append(_numbers((point.X, point.Y, point.Z)))
            record["points_m"] = points
        segments.append(record)
    blocks = []
    for raw in sketch.GetSketchBlockInstances() or ():
        block = _early_bound(raw, "ISketchBlockInstance")
        transform = _early_bound(block.BlockToSketchTransform, "IMathTransform")
        blocks.append(_numbers(transform.ArrayData))
    return {
        "segments": sorted(segments, key=lambda item: item["id"]),
        "block_transforms": sorted(blocks),
    }


def _weights(model: Any) -> dict[str, Any]:
    extension = _early_bound(model.Extension, "IModelDocExtension")
    option = constant("swDetailingNoOptionSpecified")
    return {
        "thickness_m": {
            slot: float(
                extension.GetUserPreferenceDouble(
                    constant(f"swPageSetupPrinter{slot}LineWeight"), option
                )
            )
            for slot in _WEIGHT_SLOTS
        },
        "line_fonts": {
            f"{name}:{scope}": int(
                extension.GetUserPreferenceInteger(constant(name), constant(scope))
            )
            for name, scope, _weight in _LINE_FONT_SETTINGS
        },
    }


def _census(model: Any) -> dict[str, Any]:
    drawing = _early_bound(model, "IDrawingDoc")
    names = list(drawing.GetSheetNames() or ())
    if len(names) != 1:
        raise RuntimeError(f"expected one embedded template sheet, found {names!r}")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    model.GraphicsRedraw2()
    return {
        "sheet_names": names,
        "sheet_properties": _numbers(sheet.GetProperties2()),
        "geometry": _geometry(sheet),
        "notes": [_note_census(note) for note in _notes(drawing)],
        "line_weights": _weights(model),
    }


def _website(drawing: Any) -> None:
    notes = _notes(drawing)
    candidates = [note for note in notes if OLD_WEBSITE in note.PropertyLinkedText]
    if not candidates:
        candidates = [note for note in notes if NEW_WEBSITE in note.PropertyLinkedText]
    if len(candidates) != 1:
        raise RuntimeError(f"expected one website note, found {len(candidates)}")
    note = candidates[0]
    # Keep the native rich-text tags, anchor, fixed width and every font run.
    note.PropertyLinkedText = str(note.PropertyLinkedText).replace(
        OLD_WEBSITE, NEW_WEBSITE
    )
    if (
        OLD_WEBSITE in note.PropertyLinkedText
        or NEW_WEBSITE not in note.PropertyLinkedText
    ):
        raise RuntimeError("website replacement did not persist")


def _cell(geometry: dict[str, Any], point: list[float]) -> tuple[float, ...]:
    """Find the existing ruled cell around a sheet point, never move it."""
    x, y = point[0], point[1]
    horizontal, vertical = [], []
    for segment in geometry["segments"]:
        if "points_m" not in segment:
            continue
        (x1, y1, _), (x2, y2, _) = segment["points_m"]
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
        raise RuntimeError("cannot identify the existing ruled tolerance cell") from exc


@contextlib.contextmanager
def _resolved_links(model: Any, drawing: Any) -> Iterator[dict[str, str]]:
    """Show the configured title-block values in every linked note, then restore.

    A blank template resolves no $PRPSHEET link, so native extents and rendered
    rows are measured with the literal configured values. Every link is
    restored, and read back, before anything is saved.
    """
    props = title_block_properties()
    originals = [(note, str(note.PropertyLinkedText or "")) for note in _notes(drawing)]
    try:
        for note, text in originals:
            resolved = _LINK.sub(lambda match: props.get(match[1], match[0]), text)
            if resolved != text:
                note.PropertyLinkedText = resolved
        model.GraphicsRedraw2()
        yield props
    finally:
        for note, text in originals:
            if str(note.PropertyLinkedText or "") != text:
                note.PropertyLinkedText = text
        model.GraphicsRedraw2()
        unrestored = [
            str(note.GetName())
            for note, text in originals
            if str(note.PropertyLinkedText or "") != text
        ]
        if unrestored:
            raise RuntimeError(f"property links did not restore on {unrestored!r}")


def _rendered_rows(display: dict[str, Any]) -> list[dict[str, Any]]:
    """Rendered text rows top-down: display runs sharing a baseline, left to right."""
    rows: dict[float, list[dict[str, Any]]] = {}
    for run in sorted(display.get("texts", ()), key=lambda run: run["pos"][0]):
        rows.setdefault(round(run["pos"][1], 6), []).append(run)
    return [
        {
            "text": "".join(run["t"] for run in runs),
            "x_m": runs[0]["pos"][0],
            "y_m": y,
            "fonts": sorted({run["font"] for run in runs}),
            "heights_m": sorted({run["h"] for run in runs}),
            "line_spacings": sorted({run["ls"] for run in runs}),
        }
        for y, runs in sorted(rows.items(), reverse=True)
    ]


def _block_layout(
    adapter: Any, drawing: Any, geometry: dict[str, Any], name: str
) -> dict[str, Any]:
    """Measure the resolved block, its ruled cell and every other ink in that cell."""
    notes = _notes(drawing)
    block = next((note for note in notes if str(note.GetName()) == name), None)
    if block is None:
        raise RuntimeError(f"general-note block {name!r} is missing")
    annotation = _early_bound(block.GetAnnotation(), "IAnnotation")
    anchor = _numbers(annotation.GetPosition())
    left, bottom, right, top = _cell(geometry, anchor)
    # GetExtent reads to the window pixel: measure zoomed onto the cell.
    half = max(right - left, top - bottom) / 2 + 2 * _CLEARANCE
    with _zoomed_on(adapter, ((left + right) / 2, (bottom + top) / 2), half):
        measured = [_note_census(note) for note in notes]
    record = next(item for item in measured if item["name"] == name)
    display, refused = annotation_display(adapter, annotation)
    if refused:
        raise RuntimeError(f"general-note display data refused reads: {refused!r}")
    others = [
        (item["name"], item["extent_m"])
        for item in measured
        if item["name"] != name and item["extent_m"] is not None
    ]
    # The surface-finish vee is found explicitly (IView.GetFirstSFSymbol /
    # ISFSymbol.GetNext), never only through GetAnnotations: the cell's one
    # vee must be present with drawn ink, so its bounds cannot fail open.
    view = _early_bound(drawing.GetFirstView(), "IView")
    symbols = []
    raw = view.GetFirstSFSymbol()
    while raw is not None:
        symbol = _early_bound(raw, "ISFSymbol")
        other = _early_bound(symbol.GetAnnotation(), "IAnnotation")
        kind = int(other.GetType())
        label = f"{other.GetName()} (annotation type {kind})"
        ink, refused = annotation_display(adapter, other)
        if refused:
            raise RuntimeError(f"{label} display data refused reads: {refused!r}")
        box = display_box(ink)
        if kind != _SW_SF_SYMBOL or box is None:
            raise RuntimeError(f"surface-finish symbol {label} has no drawn ink")
        symbols.append(
            {"annotation": label, "box_m": [box.xmin, box.ymin, box.xmax, box.ymax]}
        )
        raw = symbol.GetNext()
    in_cell = [
        item
        for item in symbols
        if item["box_m"][0] < right
        and item["box_m"][2] > left
        and item["box_m"][1] < top
        and item["box_m"][3] > bottom
    ]
    if len(in_cell) != 1:
        raise RuntimeError(f"expected the cell's one surface-finish vee: {symbols!r}")
    for item in symbols:
        xmin, ymin, xmax, ymax = item["box_m"]
        others.append((item["annotation"], [xmin, ymin, 0.0, xmax, ymax, 0.0]))
    # Any other non-note sheet-format ink is read as the layout audit reads it.
    for raw in view.GetAnnotations() or ():
        other = _early_bound(raw, "IAnnotation")
        kind = int(other.GetType())
        if kind in (_SW_NOTE, _SW_SF_SYMBOL):
            continue
        label = f"{other.GetName()} (annotation type {kind})"
        ink, refused = annotation_display(adapter, other)
        if refused:
            raise RuntimeError(f"{label} display data refused reads: {refused!r}")
        box = display_box(ink)
        if box is not None:
            others.append((label, [box.xmin, box.ymin, 0.0, box.xmax, box.ymax, 0.0]))
    occupied = sorted(
        (max(bottom, extent[1]), min(top, extent[4]), label)
        for label, extent in others
        if extent[0] < right
        and extent[3] > left
        and extent[1] < top
        and extent[4] > bottom
    )
    free, cursor = [], bottom
    for low, high, _label in occupied:
        if low > cursor:
            free.append([cursor, low])
        cursor = max(cursor, high)
    if top > cursor:
        free.append([cursor, top])
    spans = [span for span in free if span[0] <= anchor[1] <= span[1]]
    if len(spans) != 1:
        raise RuntimeError(
            f"general-note anchor {anchor!r} is in no single free span: {free!r}"
        )
    return {
        "cell_m": [left, bottom, right, top],
        "free_spans_m": free,
        "span_m": spans[0],
        "occupied": [list(item) for item in occupied],
        "sf_symbols": symbols,
        "block": record,
        "rows": _rendered_rows(display),
    }


def _require_block(layout: dict[str, Any], props: dict[str, str]) -> None:
    """The block reads the exact ordered lines in one font, uniformly spaced,
    clear of the cell rules and of every other ink in its cell."""
    expected = [
        _LINK.sub(lambda match: props[match[1]], line) for line in GENERAL_NOTE_LINES
    ]
    record, rows = layout["block"], layout["rows"]
    if record["text"].splitlines() != expected:
        raise RuntimeError(f"general-note text {record['text']!r} is not {expected!r}")
    if [row["text"].rstrip() for row in rows] != expected:
        raise RuntimeError(f"general-note rendered rows {rows!r} are not {expected!r}")
    if len(record["formats"]) != 1 or record["has_multiple_fonts"]:
        raise RuntimeError(f"general-note block is not one font run: {record!r}")
    for key in ("fonts", "heights_m", "line_spacings"):
        values = {value for row in rows for value in row[key]}
        # A font must be named and a height drawn; spacing need only agree.
        if len(values) != 1 or (key != "line_spacings" and not all(values)):
            raise RuntimeError(f"general-note rows differ in {key}: {rows!r}")
    pitches = [upper["y_m"] - lower["y_m"] for upper, lower in zip(rows, rows[1:])]
    if (
        max(row["x_m"] for row in rows) - min(row["x_m"] for row in rows) > _UNIFORM_M
        or min(pitches) <= 0
        or max(pitches) - min(pitches) > _UNIFORM_M
    ):
        raise RuntimeError(f"general-note rows are not uniformly spaced: {rows!r}")
    left, _bottom, right, _top = layout["cell_m"]
    low, high = layout["span_m"]
    box = record["extent_m"]
    if not (
        box[0] >= left + _CLEARANCE
        and box[3] <= right - _CLEARANCE
        and box[1] >= low + _CLEARANCE
        and box[4] <= high - _CLEARANCE
    ):
        raise RuntimeError(
            f"general-note block does not clear its cell and neighbours: {layout!r}"
        )


def _inside_corner(
    adapter: Any,
    model: Any,
    drawing: Any,
    geometry: dict[str, Any],
    *,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Consolidate the general notes into one ordered, uniformly spaced block."""
    notes = _notes(drawing)
    blocks = [
        note
        for note in notes
        if "TOL_EDGE_BREAK_R" in str(note.PropertyLinkedText or "")
    ]
    if len(blocks) != 1:
        raise RuntimeError(f"expected one linked edge-break note, found {len(blocks)}")
    block = blocks[0]
    name = str(block.GetName())
    evidence["block"] = name
    linked = str(block.PropertyLinkedText)
    separate = [
        note
        for note in notes
        if str(note.GetName()) != name
        and "TOL_INSIDE_CORNER" in str(note.PropertyLinkedText or "")
    ]
    if linked == GENERAL_NOTE_LINK and not separate:
        evidence["already_present"] = True
        return evidence
    if (
        linked != _SOURCE_GENERAL_NOTE
        or [str(note.GetName()) for note in separate] != [_SOURCE_INSIDE_CORNER_NOTE]
        or str(separate[0].PropertyLinkedText) != INSIDE_CORNER_LINK
    ):
        raise RuntimeError(
            f"unexpected general-note source: {name}={linked!r}, separate "
            f"{[(str(n.GetName()), str(n.PropertyLinkedText)) for n in separate]!r}"
        )
    obsolete = _early_bound(separate[0].GetAnnotation(), "IAnnotation")
    model.ClearSelection2(True)
    if not obsolete.Select2(False, 0):
        raise RuntimeError("failed to select the separate inside-corner note")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    # DeleteSelection2 never prompts; 0 = no absorbed/child/advanced flags.
    if not extension.DeleteSelection2(0):
        raise RuntimeError("DeleteSelection2 refused the separate inside-corner note")
    model.ClearSelection2(True)
    survivors = [
        str(note.GetName())
        for note in _notes(drawing)
        if str(note.GetName()) == _SOURCE_INSIDE_CORNER_NOTE
        or (
            str(note.GetName()) != name
            and "TOL_INSIDE_CORNER" in str(note.PropertyLinkedText or "")
        )
    ]
    if survivors:
        raise RuntimeError(
            f"separate inside-corner note survived deletion: {survivors!r}"
        )
    # The same native note keeps its font, justification and anchor x.
    block.PropertyLinkedText = GENERAL_NOTE_LINK
    if str(block.PropertyLinkedText) != GENERAL_NOTE_LINK:
        raise RuntimeError("general-note property links did not persist")
    annotation = _early_bound(block.GetAnnotation(), "IAnnotation")
    with _resolved_links(model, drawing) as props:
        trial = _block_layout(adapter, drawing, geometry, name)
        evidence["trial"] = trial
        low, high = trial["span_m"]
        box = trial["block"]["extent_m"]
        x, y, z = trial["block"]["position_m"]
        # Centre the measured block in the free span the two old notes shared;
        # no neighbour moves and no font shrinks to make room.
        if not annotation.SetPosition2(x, y + (low + high - box[1] - box[4]) / 2, z):
            raise RuntimeError("failed to position the general-note block")
        model.GraphicsRedraw2()
        placed = _block_layout(adapter, drawing, geometry, name)
        evidence["placed"] = placed
        _require_block(placed, props)
    return evidence


def _verify_general_note(
    adapter: Any, model: Any, drawing: Any, geometry: dict[str, Any]
) -> dict[str, Any]:
    """Prove the reopened template's block: exact links, then resolved layout."""
    linked = {
        str(note.GetName()): str(note.PropertyLinkedText or "")
        for note in _notes(drawing)
    }
    holders = [
        name
        for name, text in linked.items()
        if any(key in text for key in ("TOL_INSIDE_CORNER", "THREAD_TYPE", "TOL_EDGE"))
    ]
    if (
        len(holders) != 1
        or linked[holders[0]] != GENERAL_NOTE_LINK
        or _SOURCE_INSIDE_CORNER_NOTE in linked
    ):
        raise RuntimeError(
            f"reopened template lacks the one general-note block: {holders!r}"
        )
    with _resolved_links(model, drawing) as props:
        layout = _block_layout(adapter, drawing, geometry, holders[0])
        _require_block(layout, props)
    return layout


def _line_weights(model: Any) -> None:
    # Exact API: DP_LineThickness specifies METRES, using document-extension
    # preferences, NOT ISldWorks system/printer preferences. DP_LineFont selects
    # a swLineWeights_e slot. Thick is visible ink; Thin is annotation ink.
    extension = _early_bound(model.Extension, "IModelDocExtension")
    option = constant("swDetailingNoOptionSpecified")
    normal = extension.GetUserPreferenceDouble(
        constant("swPageSetupPrinterNormalLineWeight"), option
    )
    if not math.isclose(normal, 0.00018, abs_tol=1e-10):
        raise RuntimeError(
            "source template Normal thickness is not the expected 0.18 mm"
        )
    # Keep Normal and every unrelated slot intact; visible edges use Thick.
    for slot, value in (("Thin", 0.00013), ("Thick", 0.00035)):
        pref = constant(f"swPageSetupPrinter{slot}LineWeight")
        if not extension.SetUserPreferenceDouble(pref, option, value):
            raise RuntimeError(f"failed to set document {slot} thickness")
        if not math.isclose(
            extension.GetUserPreferenceDouble(pref, option), value, abs_tol=1e-10
        ):
            raise RuntimeError(f"document {slot} thickness readback differs")
    for name, scope, weight in _LINE_FONT_SETTINGS:
        pref = constant(name)
        option = constant(scope)
        value = constant(weight)
        if not extension.SetUserPreferenceInteger(pref, option, value):
            raise RuntimeError(f"failed to set document line font {name}")
        if int(extension.GetUserPreferenceInteger(pref, option)) != value:
            raise RuntimeError(f"document line font {name} readback differs")


def _preserved(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    website: bool,
    consolidated: bool,
) -> None:
    for key in ("sheet_names", "sheet_properties", "geometry"):
        if before[key] != after[key]:
            raise RuntimeError(f"template maintenance changed existing {key}")
    by_name = {note["name"]: note for note in after["notes"]}
    if len(by_name) != len(after["notes"]):
        raise RuntimeError("template contains duplicate native note names")
    added = sorted(set(by_name) - {note["name"] for note in before["notes"]})
    if added:
        raise RuntimeError(f"template maintenance added notes {added!r}")
    # The one intentional exception: the edge-break/thread note becomes the
    # general-note block (its lines, and its anchor's height in the cell), and
    # the separate inside-corner note is deleted.
    block = None
    if consolidated:
        blocks = [
            note["name"]
            for note in before["notes"]
            if note["linked_text"] == _SOURCE_GENERAL_NOTE
        ]
        if len(blocks) != 1:
            raise RuntimeError(f"expected one source general note, found {blocks!r}")
        block = blocks[0]
    for original in before["notes"]:
        current = by_name.get(original["name"])
        if consolidated and original["name"] == _SOURCE_INSIDE_CORNER_NOTE:
            if current is not None:
                raise RuntimeError("separate inside-corner note was not deleted")
            continue
        if current is None:
            raise RuntimeError(f"lost original template note {original['name']!r}")
        for key in (
            "position_m",
            "angle",
            "justification",
            "formats",
            "linked_text",
            "has_multiple_fonts",
        ):
            expected = original[key]
            if key == "linked_text" and website:
                expected = expected.replace(OLD_WEBSITE, NEW_WEBSITE)
            if original["name"] == block:
                if key == "linked_text":
                    expected = GENERAL_NOTE_LINK
                elif key == "position_m":
                    expected = [expected[0], current[key][1], expected[2]]
            if current[key] != expected:
                raise RuntimeError(f"template note {original['name']!r} changed {key}")


@_telemetry.traced("templates.maintain")
def maintain_templates(
    adapter: Any, *, operations: tuple[str, ...] = OPERATIONS
) -> dict[str, str]:
    """Write both output templates and persisted native readback census JSONs."""
    if not operations or set(operations) - set(OPERATIONS):
        raise ValueError(f"unknown template operations: {operations!r}")
    sw = _early_bound(adapter.swApp, "ISldWorks")
    previous_model = adapter.currentModel
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for layout, spec in DRAWING_TEMPLATES.items():
        source = spec.path.resolve()
        output = OUTPUT_DIR / source.name
        report_path = OUTPUT_DIR / f"harmonic-analyzer-{layout}.census.json"
        source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
        report: dict[str, Any] = {
            "source": source.name,
            "source_sha256": source_digest,
            "operations": list(operations),
            "status": "incomplete",
        }
        model = None
        try:
            # Instantiate the source rather than opening it writable: SaveAs can
            # never accidentally persist edits to a checked-in source DRWDOT.
            model = _early_bound(sw.NewDocument(str(source), 0, 0.0, 0.0), "IModelDoc2")
            if model is None or int(model.GetType()) != 3:  # swDocDRAWING
                raise RuntimeError(f"failed to instantiate {source.name}")
            adapter.currentModel = model
            drawing = _early_bound(model, "IDrawingDoc")
            report["before"] = _census(model)
            if report["before"]["sheet_properties"][5:7] != _numbers(
                (spec.width_m, spec.height_m)
            ):
                raise RuntimeError(
                    f"template {source.name} has unexpected sheet dimensions"
                )
            report_path.write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            with _telemetry.span("templates.edit", layout=str(layout)):
                drawing.EditTemplate()
                if "website" in operations:
                    _website(drawing)
                if "inside-corner" in operations:
                    model.ClearSelection2(True)
                    placement: dict[str, Any] = {}
                    report["inside_corner_placement"] = placement
                    _inside_corner(
                        adapter,
                        model,
                        drawing,
                        report["before"]["geometry"],
                        evidence=placement,
                    )
                if "line-weights" in operations:
                    _line_weights(model)
                drawing.EditSheet()
                model.ClearSelection2(True)
                model.GraphicsRedraw2()
                report["edited"] = _census(model)
            placement = report.get("inside_corner_placement")
            _preserved(
                report["before"],
                report["edited"],
                website="website" in operations,
                consolidated=bool(placement) and not placement.get("already_present"),
            )
            original_weights = report["before"]["line_weights"]
            edited_weights = report["edited"]["line_weights"]
            if "line-weights" not in operations and original_weights != edited_weights:
                raise RuntimeError("non-weight template operation changed line weights")
            for slot in _WEIGHT_SLOTS:
                if slot in ("Thin", "Thick"):
                    continue
                if (
                    original_weights["thickness_m"][slot]
                    != edited_weights["thickness_m"][slot]
                ):
                    raise RuntimeError(
                        f"template maintenance changed {slot} border/symbol ink"
                    )
            with _telemetry.span("templates.save", layout=str(layout)):
                extension = _early_bound(model.Extension, "IModelDocExtension")
                ok, errors, warnings = extension.SaveAs3(
                    str(output), 0, 1, None, None, 0, 0
                )
                report["save"] = {
                    "ok": bool(ok),
                    "errors": int(errors),
                    "warnings": int(warnings),
                }
                if not ok or errors or not output.is_file():
                    raise RuntimeError(f"template SaveAs3 failed: {report['save']!r}")
                report["output_sha256"] = hashlib.sha256(
                    output.read_bytes()
                ).hexdigest()
            with _telemetry.span("templates.reopen", layout=str(layout)):
                title = str(model.GetTitle())
                adapter.currentModel = None
                sw.CloseDoc(title)
                if sw.GetOpenDocumentByName(str(output)) is not None:
                    raise RuntimeError("saved template remained open after CloseDoc")
                model = None
                model, errors, warnings = sw.OpenDoc6(str(output), 3, 1, "", 0, 0)
                if model is None or errors:
                    raise RuntimeError(
                        f"template reopen failed: errors={errors}, warnings={warnings}"
                    )
                model = _early_bound(model, "IModelDoc2")
                adapter.currentModel = model
                report["reopened"] = _census(model)
                _preserved(
                    report["edited"],
                    report["reopened"],
                    website=False,
                    consolidated=False,
                )
                if "inside-corner" in operations:
                    # Resolved readback of the PERSISTED block; never saved.
                    reopened = _early_bound(model, "IDrawingDoc")
                    reopened.EditTemplate()
                    try:
                        report["inside_corner_reopened"] = _verify_general_note(
                            adapter, model, reopened, report["reopened"]["geometry"]
                        )
                    finally:
                        reopened.EditSheet()
                        model.ClearSelection2(True)
                if (
                    report["edited"]["line_weights"]
                    != report["reopened"]["line_weights"]
                ):
                    raise RuntimeError(
                        "saved template document line weights did not persist"
                    )
            if hashlib.sha256(source.read_bytes()).hexdigest() != source_digest:
                raise RuntimeError("checked-in source template was modified")
            saved = hashlib.sha256(output.read_bytes()).hexdigest()
            if saved != report["output_sha256"]:
                raise RuntimeError("saved template changed after its readback")
            report["status"] = "readback-passed"
            outputs[f"template_{layout}"] = str(output)
            outputs[f"census_{layout}"] = str(report_path)
        except Exception as exc:
            report["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            report_json = json.dumps(report, indent=2) + "\n"
            report_path.write_text(report_json, encoding="utf-8")
            if report["status"] != "readback-passed":
                # Failed leaves do not publish cache outputs. This existing
                # failure tree is returned by the worker even when the leaf fails.
                failure_path = (
                    CAD_ROOT
                    / "out"
                    / "reports"
                    / "failures"
                    / "templates"
                    / report_path.name
                )
                failure_path.parent.mkdir(parents=True, exist_ok=True)
                failure_path.write_text(report_json, encoding="utf-8")
            if model is not None:
                sw.CloseDoc(str(model.GetTitle()))
            adapter.currentModel = previous_model
    return outputs


def _main() -> int:
    from _session import run_build

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", action="append", choices=OPERATIONS)
    args = parser.parse_args()

    async def build(adapter: Any) -> dict[str, str]:
        return maintain_templates(
            adapter, operations=tuple(args.operation or OPERATIONS)
        )

    return run_build(build)


if __name__ == "__main__":
    sys.exit(_main())
