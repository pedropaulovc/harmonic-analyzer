"""The one native general (setting) table helper for assembly sheets.

``insert_general_table`` prints a titled native general table, every cell
read back, and returns its sheet box; ``table_column_widths`` is the column
budget it applies, for callers that check a table's fit before placing it.
The free-note helpers it needs (``add_note_block``, ``note_extent``,
``anchor_note``) are public too.  Extracted from
``draw_dt_drive_train_assembly`` (sheet 15's setting tables); the import
closure stays narrow so a consumer's cache key pulls in only this module.

The calibration is that package's: 2.8 mm a character and a one-line title.
A title must be one line, and a cell whose glyphs print wider (the
dt_cone_gear_tl_arbor setup table measured 3.2 mm a character and keeps its
own placer) wraps without raising, so a consumer checks its print.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from solidworks_mcp.adapters.solidworks.drawing import add_note

from _com import _early_bound
import _telemetry

NOTE_FIELD_INSET = 0.0005
NOTE_ANCHOR_PASSES = 3
NOTE_ANCHOR_SETTLE = 0.00005
# Notes print at 4.525 mm a line (summing-assembly.pdf; the dt drive train
# package's telemetry: 47 lines measure 212.33 mm).
NOTE_LINE_PITCH = 0.004525
# A general table's cell text runs ~2.8 mm a character at the 3.5 mm note
# font (47 note lines measured 212.33 mm; 70 characters ~194 mm); each column
# is cut to its longest cell plus 2 mm a side.
TABLE_CHAR_WIDTH = 0.0028
TABLE_CELL_PAD = 0.004
# The air between a title's ink and its table: half the title's ink height
# (the layout audit's text-clearance, _layout_audit.TEXT_CLEARANCE_HEIGHTS),
# which for a title with a descending glyph is the whole line, plus one seat
# pixel (~0.45 mm at 2.1-2.3 px/mm) for its anchored box.  At 1.5 mm a title
# with parentheses printed its ink 1.44 mm over the table, needing 2.26 mm
# (pd_paper_drive_assembly SETTING TABLE, run 20261117T152142787Z; the dt
# drive train PEDESTAL RECHECK (CHECK 4) title 1.48 mm, run
# 20261117T130750991Z); "SETTING TABLE" alone has no descender and cleared.
TABLE_TITLE_GAP = 0.5 * NOTE_LINE_PITCH + 0.0005
# A table hangs a fixed drop under its title's requested top: the inset, the
# title's one line and the gap.  It used to hang off the title's
# INote.GetExtent bottom, which reads to the seat window's pixel, and each
# table carried the error down the stack: dt drive train sheet 15 put the
# pedestal recheck table's bottom at 172.53 mm on a 1010x598 px window (leaf
# 20261112T161937Z, 2.098 px/mm) and at 171.63 mm, inside the station table
# field, on a 1010x678 px one (leaf 20261113T025825Z, 2.325 px/mm; release
# v49 r2).  Only the table's own position and row heights, which SolidWorks
# holds in sheet metres, set the next table's top.
TABLE_TITLE_DROP = NOTE_FIELD_INSET + NOTE_LINE_PITCH + TABLE_TITLE_GAP


def add_note_block(
    adapter: Any, text: str, xy: tuple[float, float], *, label: str
) -> Any:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add {label}")
    note = _early_bound(note, "INote")
    actual = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    expected = text.replace("\r\n", "\n").replace("\r", "\n")
    if actual != expected:
        raise RuntimeError(
            f"{label} text did not persist "
            f"(actual_length={len(actual)}, expected_length={len(expected)})"
        )
    return note


def note_extent(adapter: Any, note: Any, *, label: str) -> tuple[float, ...]:
    """The rendered sheet-space box (x0, y0, x1, y1) of a free note."""
    adapter.currentModel.GraphicsRedraw2()
    extent = tuple(
        float(value) for value in (_early_bound(note, "INote").GetExtent() or ())
    )
    if len(extent) != 6 or extent[3] <= extent[0] or extent[4] <= extent[1]:
        raise RuntimeError(f"{label}: note has no rendered extent: {extent!r}")
    return (extent[0], extent[1], extent[3], extent[4])


def anchor_note(
    adapter: Any, note: Any, corner: tuple[float, float], *, label: str
) -> tuple[float, ...]:
    """Steer a note's RENDERED top-left corner toward ``corner`` (summing r10/r11:
    the text box neither sits on nor tracks the insertion point 1:1)."""
    target_x, target_y = corner
    annotation = _early_bound(
        _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
    )
    if annotation is None:
        raise RuntimeError(f"{label}: note has no annotation to move")
    extent = note_extent(adapter, note, label=label)
    moves = 0
    for _pass in range(NOTE_ANCHOR_PASSES):
        shift = (target_x - extent[0], target_y - extent[3])
        if max(abs(shift[0]), abs(shift[1])) <= NOTE_ANCHOR_SETTLE:
            break
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3:
            raise RuntimeError(f"{label}: note position is unreadable: {position!r}")
        if not annotation.SetPosition(
            position[0] + shift[0], position[1] + shift[1], position[2]
        ):
            raise RuntimeError(f"{label}: note SetPosition failed")
        extent = note_extent(adapter, note, label=label)
        moves += 1
    _telemetry.event(
        "drawing.note_anchor",
        block=label,
        moves=moves,
        target_mm=(target_x * 1000.0, target_y * 1000.0),
        extent_mm=tuple(value * 1000.0 for value in extent),
    )
    return extent


def table_column_widths(
    header: Sequence[str], rows: Sequence[Sequence[str]]
) -> tuple[float, ...]:
    """Each general-table column cut to its longest cell (metres)."""
    return tuple(
        max(len(text) for text in column) * TABLE_CHAR_WIDTH + TABLE_CELL_PAD
        for column in zip(header, *rows, strict=True)
    )


@_telemetry.traced("drawing.insert_general_table", label_param="label")
def insert_general_table(
    adapter: Any,
    *,
    title: str,
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    top_left: tuple[float, float],
    label: str,
) -> tuple[float, float, float, float]:
    """A titled native general table, every cell read back; returns its box
    (x0, y0, x1, y1) in sheet metres.

    The title's top-left is ``top_left``; the table's top is
    :data:`TABLE_TITLE_DROP` under it, whatever the title's rendered box reads
    on this seat's window."""
    x, top = top_left
    title_note = add_note_block(adapter, title, (x, top), label=f"{label} title")
    anchor_note(
        adapter,
        title_note,
        (x + NOTE_FIELD_INSET, top - NOTE_FIELD_INSET),
        label=f"{label} title",
    )
    table_top = top - TABLE_TITLE_DROP
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    # swBOMConfigurationAnchor_TopLeft = 1; no template: a plain general table.
    raw = ddoc.InsertTableAnnotation2(
        False, x, table_top, 1, "", len(rows) + 1, len(header)
    )
    if raw is None:
        raise RuntimeError(f"{label}: InsertTableAnnotation2 returned no table")
    table = _early_bound(raw, "ITableAnnotation")
    if (int(table.RowCount), int(table.ColumnCount)) != (len(rows) + 1, len(header)):
        raise RuntimeError(
            f"{label}: table is {table.RowCount}x{table.ColumnCount}, "
            f"expected {len(rows) + 1}x{len(header)}"
        )
    for column, width in enumerate(table_column_widths(header, rows)):
        # swTableRowColChange_TableSizeCanChange = 0
        if abs(float(table.SetColumnWidth(column, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"{label}: column {column} width did not persist")
    for row, cells in enumerate((header, *rows)):
        for column, text in enumerate(cells):
            table.SetText2(row, column, True, text)
            applied = str(table.DisplayedText2(row, column, True) or "")
            if applied != text:
                raise RuntimeError(
                    f"{label}: cell ({row}, {column}) did not persist: {applied!r} != {text!r}"
                )
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    heights = tuple(
        float(table.GetRowHeight(row)) for row in range(int(table.RowCount))
    )
    widths = tuple(
        float(table.GetColumnWidth(column)) for column in range(int(table.ColumnCount))
    )
    if len(position) != 3 or not all(
        map(math.isfinite, (*position, *heights, *widths))
    ):
        raise RuntimeError(f"{label}: table geometry is unreadable")
    box = (
        position[0],
        position[1] - sum(heights),
        position[0] + sum(widths),
        position[1],
    )
    _telemetry.event(
        "drawing.general_table",
        table=label,
        box_mm=tuple(value * 1000.0 for value in box),
        row_heights_mm=tuple(value * 1000.0 for value in heights),
        column_widths_mm=tuple(value * 1000.0 for value in widths),
    )
    return box
