"""Property-linked drawing notes and aligned note schedules.

Recipes share property-linked notes and aligned schedules here without
depending on leader attachment or dimension-authoring code.
"""

from __future__ import annotations

from typing import Any, Sequence

from solidworks_mcp.adapters.solidworks.drawing import add_note

from _com import _early_bound
import _telemetry


def property_link(property_name: str) -> str:
    """Return a source-model property link suitable for a drawing note."""
    if not property_name or '"' in property_name:
        raise ValueError(f"invalid drawing property name: {property_name!r}")
    return f'$PRPSHEET:"{property_name}"'


def set_note_text_height(
    note: Any, height: float, *, label: str, remove_rich_text: bool = False,
) -> Any:
    """Format an existing note without replacing its property/view fields.

    IAnnotation.SetTextFormat cannot override embedded rich-text fonts.
    Its documented two-step route first removes those fonts with UseDoc=True,
    then applies the requested local format. The temporary document default
    is NOT the height source. Callers must redraw and verify native readbacks.
    Ordinary linked notes keep the original single-write path.
    """
    note = _early_bound(note, "INote")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label} has no annotation")
    annotation = _early_bound(annotation, "IAnnotation")
    if remove_rich_text and annotation.SetTextFormat(0, True, None) is not True:
        raise RuntimeError(f"failed to reset {label} rich-text fonts")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label} has no text format")
    text_format.CharHeight = float(height)
    if annotation.SetTextFormat(0, False, text_format) is not True:
        raise RuntimeError(f"failed to set {label} text height")
    return note


@_telemetry.traced("drawing.linked_note", label_param="property_name")
def add_property_linked_note(
    adapter: Any,
    property_name: str,
    x: float,
    y: float,
    *,
    char_height: float | None = None,
) -> Any:
    """Place one note whose displayed text resolves from the source SLDPRT."""
    note = add_note(adapter, property_link(property_name), x, y)
    if note is None:
        raise RuntimeError(f"failed to add linked drawing note {property_name!r}")
    if char_height is None:
        return note

    return set_note_text_height(
        note, char_height, label=f"linked drawing note {property_name!r}",
    )


def draw_note_table(
    adapter: Any,
    *,
    rows: Sequence[Sequence[str]],
    column_x: Sequence[float],
    row_y: Sequence[float],
) -> None:
    """Place a compact schedule using aligned notes.

    Geometry stays in the checked-in sheet format.  The drawing recipe supplies
    only row content, so future prints can reuse the same uncluttered schedule
    layout without adding table objects or template-specific anchors.
    """
    if len(rows) != len(row_y):
        raise ValueError("table row content and row positions differ")
    for y, row in zip(row_y, rows, strict=True):
        if len(row) != len(column_x):
            raise ValueError("table row has the wrong number of columns")
        for x, text in zip(column_x, row, strict=True):
            if add_note(adapter, text, x, y) is None:
                raise RuntimeError(f"failed to add schedule cell {text!r}")
