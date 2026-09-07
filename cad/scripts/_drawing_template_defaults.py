"""Raw blank-template inheritance witnesses; not a manufacturing-sheet proof.

Unlike the exploratory diagnostic, this receipt never rounds native floats.
Preferences, text, font definitions AND represented coordinates compare exactly.
Only extents of individually proven zero-ink linked notes are observational:
the committed template-default diagnostic established that those extents collapse
on template instantiation despite an empty native display/leader inventory.
"""

from dataclasses import asdict
import json
import math

from _common import _early_bound
from _drawing_annotation_bounds import _native_counts, annotation_box


def _plain(value):
    """JSON containers without precision reduction; reject non-finite data."""
    return json.loads(json.dumps(value, allow_nan=False))


def _empty_link(annotation, note):
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    if data is None:
        raise RuntimeError("blank linked note has no display inventory")
    counts = _native_counts(
        data,
        (
            "Text",
            "Line",
            "Arc",
            "PolyLine",
            "Triangle",
            "ArrowHead",
            "Polygon",
            "Ellipse",
            "Parabola",
            "Point",
        ),
    )
    leaders = [annotation.GetLeaderCount(), annotation.GetMultiJogLeaderCount()]
    if any(counts.values()) or any(type(n) is not int or n != 0 for n in leaders):
        raise RuntimeError("blank linked note contains native ink or leaders")
    if note.HasMultipleFonts or annotation.GetTextFormatCount() != 1:
        raise RuntimeError("unsupported blank linked-note compound formatting")
    fmt = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
    if fmt is None:
        raise RuntimeError("blank linked note has no font definition")
    anchor = list(annotation.GetPosition() or ())
    if len(anchor) != 3 or not all(math.isfinite(n) for n in anchor):
        raise RuntimeError("blank linked note has no finite XYZ anchor")
    font = {
        "font": str(fmt.TypeFaceName),
        "height_m": float(fmt.CharHeight),
        "height_points": int(fmt.CharHeightInPts),
        "height_in_points": bool(fmt.IsHeightSpecifiedInPts()),
        "width_factor": float(fmt.WidthFactor),
        "bold": bool(fmt.Bold),
        "italic": bool(fmt.Italic),
        "use_document_format": bool(annotation.GetUseDocTextFormat(0)),
    }
    if not font["font"] or any(
        not math.isfinite(font[key]) or font[key] <= 0
        for key in ("height_m", "width_factor")
    ):
        raise RuntimeError("blank linked note has invalid font dimensions")
    return {"native_counts": counts, "leaders": leaders, "anchor": anchor, "font": font}


def snapshot_defaults(adapter, spec):
    """Capture the existing blank-sheet setup contract, without native setters."""
    import _drawing_common as common

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(model, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if sheet is None:
        raise RuntimeError("template has no sheet")
    common.assert_asme_b_sheet(
        adapter, sheet, phase="prepared defaults", scale=spec.scale
    )
    groups = tuple(ddoc.GetViews() or ())
    if len(groups) != 1 or len(tuple(groups[0])) != 1:
        raise RuntimeError("preparation requires one blank sheet with no model views")
    units = {
        name: int(model.GetUserPreferenceIntegerValue(pref))
        for name, pref in (
            ("system", 263),
            ("linear", 47),
            ("decimals", 49),
        )
    }
    # set_units_mm's exact observed terminal state: Custom, millimetres, precision.
    if units != {"system": 4, "linear": 0, "decimals": spec.decimals}:
        raise RuntimeError(f"prepared template units differ: {units}")
    styles = {
        name: int(
            model.Extension.GetUserPreferenceInteger(
                common._PREF_DIM_TEXT_AND_LEADER_STYLE,
                option,
            )
        )
        for name, option in common._DIM_DETAILING_SCOPES.items()
    }
    if any(value != common._BROKEN_LEADER_HORIZONTAL_TEXT for value in styles.values()):
        raise RuntimeError(f"prepared dimension styles differ: {styles}")
    sheet_view = _early_bound(ddoc.GetFirstView(), "IView")
    notes, empty_extents, other_kinds = [], [], []
    for raw in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        kind = int(annotation.GetType())
        if kind != 6:
            other_kinds.append(kind)
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        extent = list(note.GetExtent() or ())
        if len(extent) != 6 or not all(math.isfinite(n) for n in extent):
            raise RuntimeError("sheet note has invalid native extent")
        row = {
            "text": str(note.GetText() or ""),
            "linked_text": str(note.PropertyLinkedText or ""),
            "extent": extent,
            "visible": int(annotation.Visible),
            "horizontal_justification": int(note.GetTextJustification()),
            "vertical_justification": int(note.GetTextVerticalJustification()),
            "position_lock": "locked" if note.LockPosition else "unlocked",
        }
        if not row["text"] and row["linked_text"]:
            row["zero_ink"] = _empty_link(annotation, note)
            empty_extents.append(
                {
                    "name": str(annotation.GetName()),
                    "linked_text": row["linked_text"],
                    "extent": row.pop("extent"),
                }
            )
        if row["text"] and row["visible"] == 1:
            measured = asdict(annotation_box(adapter, annotation))
            measured.pop("name")
            row["measured"] = measured
        notes.append(_plain(row))
    if other_kinds:
        raise RuntimeError(
            f"unsupported non-note blank-sheet annotations: {other_kinds}"
        )
    normalized = [" ".join(row["text"].upper().split()) for row in notes]
    if (
        normalized.count(common._METRIC_EDGE_BREAK_NOTE) != 1
        or common._OLD_EDGE_BREAK_NOTE in normalized
    ):
        raise RuntimeError("metric edge-break note did not persist exactly once")
    if not ddoc.GetEditSheet():
        raise RuntimeError("prepared drawing is not in sheet mode")
    return _plain(
        {
            "units": units,
            "dimension_styles": styles,
            "sheet_properties": list(sheet.GetProperties2() or ()),
            "sheet_format_visibility": "visible"
            if sheet.SheetFormatVisible
            else "hidden",
            "sheet_notes": sorted(
                notes, key=lambda row: json.dumps(row, sort_keys=True)
            ),
            "blank_linked_extent_observations": empty_extents,
            "sheet_mode": "edit_sheet",
        }
    )


def compare_defaults(before, after):
    """Exact native representation, except individually witnessed no-ink extents."""

    def semantic(row):
        return {
            key: value
            for key, value in row.items()
            if key != "blank_linked_extent_observations"
        }

    if semantic(before) != semantic(after):
        raise RuntimeError("prepared template raw defaults did not persist exactly")
