"""Maintain the two hand-authored DRWDOTs through an already-held farm COM seat.

This edits copies, never the checked-in templates, and never opens a second
session. The CLI is a run_build entry point; farm bootstrap callers invoke
maintain_templates(adapter) inside their existing run_build instead. Website,
inside-corner and line-weight edits are independent selectable operations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.sw_type_info import constant

import _telemetry
from _com import _early_bound
from _drawing_registry import DRAWING_TEMPLATES
from _part_properties import title_block_properties
from _paths import CAD_ROOT

OLD_WEBSITE = "harmonic-analyzer.vza.net"
NEW_WEBSITE = "harmonicanalyzer.com"
INSIDE_CORNER_LINK = 'INSIDE CORNERS $PRPSHEET:"TOL_INSIDE_CORNER"'
OPERATIONS = ("website", "inside-corner", "line-weights")
OUTPUT_DIR = CAD_ROOT / "out" / "templates"
_CLEARANCE = 0.0004  # Native text-box clearance to existing notes and cell rules.
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
    "swLineFontDimensionsThickness",
    "swDimensionsExtensionLineStyleThickness",
    "swDetailingNoteLeaderLineThickness",
    "swDetailingGtolLeaderLineThickness",
    "swDetailingGtolFrameLineThickness",
    "swDetailingDatumLeaderLineThickness",
    "swDetailingDatumFrameLineThickness",
    "swDetailingSFSymbolLeaderLineThickness",
    "swDetailingBalloonLeaderLineThickness",
    "swDetailingBalloonFrameLineThickness",
)
_FONT_PREFS = ("swLineFontVisibleEdgesThickness", *_THIN_FONTS)


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
        formats.append(
            {
                "document_default": bool(annotation.GetUseDocTextFormat(index)),
                **{name: getattr(fmt, name) for name in _FONT_FIELDS},
            }
        )
    extent = _numbers(note.GetExtent() or ())
    if len(extent) != 6:
        raise RuntimeError(f"note {note.GetName()!r} has no visible native extent")
    return {
        "name": str(note.GetName()),
        "linked_text": str(note.PropertyLinkedText or ""),
        "text": str(note.GetText() or ""),
        "position_m": _numbers(annotation.GetPosition()),
        "extent_m": extent,
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
            name: int(extension.GetUserPreferenceInteger(constant(name), option))
            for name in _FONT_PREFS
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


def _cell(geometry: dict[str, Any], note: dict[str, Any]) -> tuple[float, ...]:
    """Find the existing ruled cell around the edge-break note, never move it."""
    x, y, _z = note["position_m"]
    extent = note["extent_m"]
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
            max(value for value in horizontal if value < extent[1]),
            min(value for value in vertical if value > x),
            min(value for value in horizontal if value > extent[4]),
        )
    except ValueError as exc:
        raise RuntimeError("cannot identify the existing ruled tolerance cell") from exc


def _inside_corner(
    model: Any, drawing: Any, geometry: dict[str, Any]
) -> dict[str, Any]:
    notes = _notes(drawing)
    existing = [
        note for note in notes if "TOL_INSIDE_CORNER" in note.PropertyLinkedText
    ]
    if existing:
        if (
            len(existing) != 1
            or str(existing[0].PropertyLinkedText) != INSIDE_CORNER_LINK
        ):
            raise RuntimeError(
                "inside-corner row is duplicated or has unexpected wording"
            )
        return {"already_present": True}
    edge_notes = [
        note for note in notes if "TOL_EDGE_BREAK_R" in note.PropertyLinkedText
    ]
    if len(edge_notes) != 1:
        raise RuntimeError(
            f"expected one linked edge-break note, found {len(edge_notes)}"
        )
    edge = edge_notes[0]
    props = title_block_properties()
    originals = [(note, str(note.PropertyLinkedText or "")) for note in notes]
    # Blank templates cannot resolve PRPSHEET links. Measure literal configured
    # values temporarily, then restore the links BEFORE saving the template.
    try:
        for note, text in originals:
            resolved = _LINK.sub(lambda match: props.get(match[1], match[0]), text)
            if resolved != text:
                note.PropertyLinkedText = resolved
        model.GraphicsRedraw2()
        measured = [_note_census(note) for note in notes]
        edge_data = _note_census(edge)
        left, bottom, right, top = _cell(geometry, edge_data)
        row = _early_bound(
            model.InsertNote(f"INSIDE CORNERS {props['TOL_INSIDE_CORNER']}"), "INote"
        )
        if row is None:
            raise RuntimeError("failed to insert inside-corner sheet-format row")
        annotation = _early_bound(row.GetAnnotation(), "IAnnotation")
        reference = _early_bound(edge.GetAnnotation(), "IAnnotation")
        if not annotation.SetTextFormat(0, False, reference.GetTextFormat(0)):
            raise RuntimeError(
                "failed to copy edge-break row font to inside-corner row"
            )
        if not row.SetName("HA_INSIDE_CORNERS"):
            raise RuntimeError("failed to name inside-corner row")
        if not annotation.SetPosition2(*edge_data["position_m"]):
            raise RuntimeError("failed to measure inside-corner row")
        model.GraphicsRedraw2()
        trial = _note_census(row)
        bounds = trial["extent_m"]
        height = bounds[4] - bounds[1]
        occupied = sorted(
            (max(bottom, item["extent_m"][1]), min(top, item["extent_m"][4]))
            for item in measured
            if item["extent_m"][0] < right
            and item["extent_m"][3] > left
            and item["extent_m"][1] < top
            and item["extent_m"][4] > bottom
        )
        gaps = []
        cursor = bottom
        for low, high in occupied:
            if low - cursor >= height + 2 * _CLEARANCE:
                gaps.append((cursor, low))
            cursor = max(cursor, high)
        if top - cursor >= height + 2 * _CLEARANCE:
            gaps.append((cursor, top))
        if not gaps:
            raise RuntimeError(
                "no native text gap for inside-corner row without moving existing content"
            )
        # Prefer the free row immediately below edge-break; otherwise the largest
        # free gap in that SAME ruled cell. No unrelated title-block cell is used.
        low, high = min(
            gaps,
            key=lambda gap: (
                abs(gap[1] - edge_data["extent_m"][1]),
                -(gap[1] - gap[0]),
            ),
        )
        position = trial["position_m"]
        target_y = position[1] + high - _CLEARANCE - bounds[4]
        if not annotation.SetPosition2(position[0], target_y, position[2]):
            raise RuntimeError("failed to position inside-corner row in native gap")
        model.GraphicsRedraw2()
        placed = _note_census(row)
        bounds = placed["extent_m"]
        if not (
            bounds[0] >= left + _CLEARANCE
            and bounds[3] <= right - _CLEARANCE
            and bounds[1] >= low + _CLEARANCE - 1e-8
            and bounds[4] <= high - _CLEARANCE + 1e-8
        ):
            raise RuntimeError(
                f"inside-corner row does not fit existing tolerance cell: {placed!r}"
            )
        row.PropertyLinkedText = INSIDE_CORNER_LINK
        if str(row.PropertyLinkedText) != INSIDE_CORNER_LINK:
            raise RuntimeError("inside-corner property link did not persist")
        return {
            "cell_m": [left, bottom, right, top],
            "gap_m": [low, high],
            "resolved_row": placed,
            "resolved_existing_notes": measured,
        }
    finally:
        for note, text in originals:
            if str(note.PropertyLinkedText or "") != text:
                note.PropertyLinkedText = text


def _line_weights(model: Any) -> None:
    # Exact API: DP_LineThickness specifies METRES, using document-extension
    # preferences, NOT ISldWorks system/printer preferences. DP_LineFont selects
    # a swLineWeights_e slot. Normal is visible ink; Thin is annotation ink.
    extension = _early_bound(model.Extension, "IModelDocExtension")
    option = constant("swDetailingNoOptionSpecified")
    for slot, value in (("Thin", 0.00013), ("Normal", 0.00035)):
        pref = constant(f"swPageSetupPrinter{slot}LineWeight")
        if not extension.SetUserPreferenceDouble(pref, option, value):
            raise RuntimeError(f"failed to set document {slot} thickness")
        if not math.isclose(
            extension.GetUserPreferenceDouble(pref, option), value, abs_tol=1e-10
        ):
            raise RuntimeError(f"document {slot} thickness readback differs")
    for name in _FONT_PREFS:
        pref = constant(name)
        value = constant("swLW_NORMAL" if name == _FONT_PREFS[0] else "swLW_THIN")
        if not extension.SetUserPreferenceInteger(pref, option, value):
            raise RuntimeError(f"failed to set document line font {name}")
        if int(extension.GetUserPreferenceInteger(pref, option)) != value:
            raise RuntimeError(f"document line font {name} readback differs")


def _preserved(before: dict[str, Any], after: dict[str, Any], *, website: bool) -> None:
    for key in ("sheet_names", "sheet_properties", "geometry"):
        if before[key] != after[key]:
            raise RuntimeError(f"template maintenance changed existing {key}")
    by_name = {note["name"]: note for note in after["notes"]}
    if len(by_name) != len(after["notes"]):
        raise RuntimeError("template contains duplicate native note names")
    for original in before["notes"]:
        current = by_name.get(original["name"])
        if current is None:
            raise RuntimeError(f"lost original template note {original['name']!r}")
        for key in ("position_m", "angle", "justification", "formats", "linked_text"):
            expected = original[key]
            if key == "linked_text" and website:
                expected = expected.replace(OLD_WEBSITE, NEW_WEBSITE)
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
                    report["inside_corner_placement"] = _inside_corner(
                        model, drawing, report["before"]["geometry"]
                    )
                if "line-weights" in operations:
                    _line_weights(model)
                drawing.EditSheet()
                model.ClearSelection2(True)
                model.GraphicsRedraw2()
                report["edited"] = _census(model)
            _preserved(
                report["before"], report["edited"], website="website" in operations
            )
            original_weights = report["before"]["line_weights"]
            edited_weights = report["edited"]["line_weights"]
            if "line-weights" not in operations and original_weights != edited_weights:
                raise RuntimeError("non-weight template operation changed line weights")
            for slot in _WEIGHT_SLOTS[2:]:
                if (
                    original_weights["thickness_m"][slot]
                    != edited_weights["thickness_m"][slot]
                ):
                    raise RuntimeError(
                        f"template maintenance changed {slot} border/symbol ink"
                    )
            with _telemetry.span("templates.save", layout=str(layout)):
                extension = _early_bound(model.Extension, "IModelDocExtension")
                ok, errors, warnings = extension.SaveAs3(str(output), 0, 1, None, None)
                report["save"] = {
                    "ok": bool(ok),
                    "errors": int(errors),
                    "warnings": int(warnings),
                }
                if not ok or errors or not output.is_file():
                    raise RuntimeError(f"template SaveAs3 failed: {report['save']!r}")
            with _telemetry.span("templates.reopen", layout=str(layout)):
                title = str(model.GetTitle())
                model = None
                adapter.currentModel = None
                sw.CloseDoc(title)
                model, errors, warnings = sw.OpenDoc6(str(output), 3, 1, "")
                if model is None or errors:
                    raise RuntimeError(
                        f"template reopen failed: errors={errors}, warnings={warnings}"
                    )
                model = _early_bound(model, "IModelDoc2")
                adapter.currentModel = model
                report["reopened"] = _census(model)
                _preserved(report["edited"], report["reopened"], website=False)
                if (
                    report["edited"]["line_weights"]
                    != report["reopened"]["line_weights"]
                ):
                    raise RuntimeError(
                        "saved template document line weights did not persist"
                    )
            if hashlib.sha256(source.read_bytes()).hexdigest() != source_digest:
                raise RuntimeError("checked-in source template was modified")
            report["output_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
            report["status"] = "readback-passed"
            outputs[f"template_{layout}"] = str(output)
            outputs[f"census_{layout}"] = str(report_path)
        except Exception as exc:
            report["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            report_path.write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
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
