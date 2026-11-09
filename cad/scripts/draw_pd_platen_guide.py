r"""Create the curated machinist drawing for the platen guide.

The SLDPRT remains authoritative.  This recipe supplies only the platen-guide
views, dimensions, hole table, tap-wall note and surface symbol;
sheet/template and export behavior lives in ``_drawing_common``.
Leader behavior lives in ``_drawing_attachment``.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_platen_guide.py pd-platen-guide
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
    remove_notes_matching,
)

import _config
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_tables import insert_hole_table
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import THREAD_MAJOR_MM, blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from build_pd_platen_guide import (
    GUIDE_LENGTH,
    HOLE_X as REAR_X,
    ISOMETRIC_VIEW_SCALE,
    SCREW_STATION_X as FRONT_X,
    TAP_EDGE_WALL_TEXT,
)
from pd_platen_guide_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GUIDE_DEPTH_CALLOUT,
    GUIDE_HEIGHT,
    SURFACE_FINISHES,
    TAPPED_HOLE_SPEC,
    TAP_Y,
    TAP_Y_BAND_TEXT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_platen_guide"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# The 1:1 front view is centred at sheet X=0.190 m. Derive its left edge from
# the resized guide so the hole-table anchors follow the part geometry.
FRONT_VIEW_X_M = 0.190
FRONT_LEFT_X_M = FRONT_VIEW_X_M - GUIDE_LENGTH / 2000.0
FRONT_VIEW_Y_M = 0.110
# The view centres on the rail's outline: its bottom edge and the tap row
# stand from that centre by the model's height and TAP_Y.
FRONT_BOTTOM_Y_M = FRONT_VIEW_Y_M - GUIDE_HEIGHT / 2000.0
FRONT_HOLE_Y_M = FRONT_BOTTOM_Y_M + TAP_Y / 1000.0
# Every tap runs through the rail, so the front view shows all nine and one
# table locates them; no second (rear) face view.
HOLE_STATIONS_MM = tuple(sorted(FRONT_X + REAR_X))
# Each tag stands just under the bar, right of its hole, on a short leader to
# the rim: off the outline and the centre marks. A tag's text runs ~5.7 mm
# right of that, past the next hole of a 7.0 pitch pair, where the next tag's
# leader ran through it (farm layout audit after B2: A7 through A6). So in a
# close run every other tag stands above the bar instead.
HOLE_TAG_DX_M = 0.0015
HOLE_TAG_Y_M = FRONT_BOTTOM_Y_M - 0.0025
HOLE_TAG_ABOVE_Y_M = FRONT_BOTTOM_Y_M + GUIDE_HEIGHT / 1000.0 + 0.0061
HOLE_TAG_CLEAR_MM = 9.0


def _tags_above(stations: tuple[float, ...]) -> frozenset[float]:
    """The stations whose tag stands above the bar: in each run closer than
    HOLE_TAG_CLEAR_MM, every other tag after the first."""
    above: set[float] = set()
    for previous, station in zip(stations, stations[1:]):
        if station - previous < HOLE_TAG_CLEAR_MM and previous not in above:
            above.add(station)
    return frozenset(above)


HOLE_TAGS_ABOVE = _tags_above(HOLE_STATIONS_MM)
# The bar-slide finish lands on the bottom edge (model y 0, front face z 0)
# midway between the A1 and A2 axes, clear of both centre marks. The landing
# is projected from the model at draw time. The symbol is anchored at its
# lower-left. At the default text height its long leg crossed its own leader,
# which dropped from the landing past the symbol's right side (machinist
# review round 3). At 2.5 mm text (the house finish height,
# draw_ch_channel_lever) right of the landing, the leader reaches it from the
# left, clear of the long leg. Its "SLIDES ON MHA-PD-07" line tops out ~10 mm
# above the anchor: anchored at y 0.090 it ran under the A2/A4 tags (box
# bottom ~99.6 mm) and they printed on "MHA" and "-07" (round 4). At y 0.075
# it tops out ~85 mm, in the empty field under the front view.
BAR_SLIDE_STATION_MM = (FRONT_X[0] + REAR_X[0]) / 2.0
BAR_SLIDE_FINISH_XY = (FRONT_LEFT_X_M + BAR_SLIDE_STATION_MM / 1000.0 + 0.003, 0.075)
FINISH_CHAR_HEIGHT = 0.0025
# Owner ruling 2026-11-08 (Pedro, #2144 item 2.3): the taps are noncritical,
# so they print plain hole-table coordinates with no position frame, and the
# LOC columns are not basic (rule 5: a basic only feeds a frame). The
# stations take the title block's .XXX ±.005; the tap row prints its band
# (TAP_Y_BAND_TEXT, the shop's ±.005 row) on every Y LOC value (rule 3: a
# band goes on the dimension itself, never in a note; integration review
# 20261109T062834910Z). The native LOC
# cells are generated and cannot be edited (ITableAnnotation
# IsCellTextEditable: only the header row and custom columns can), so a
# custom Y LOC column after the native one prints each row's banded value
# and the native column, still model-linked and checked against TAP_Y, is
# hidden (as the oblique carrier hides its generated SIZE). That column's
# header points to numbered note 1, the taps' finished wall to the edges, .001
# under the floor (rule 7: a location's reason sits on a linked flag note;
# rule 20; RV-01 in pd-platen-guide.yaml, pending owner confirmation).
HOLE_TAGS = tuple(f"A{index}" for index in range(1, len(HOLE_STATIONS_MM) + 1))
PLATEN_NUMBER = _config.parts("pd-platen")["number"]
LOCK_NUMBER = _config.parts("pd-guide-lock")["number"]
TAP_WALL_NOTE_NUMBER = 1
TAP_WALL_NOTE = (
    f"{TAP_WALL_NOTE_NUMBER}. {HOLE_TAGS[0]}-{HOLE_TAGS[-1]}: {TAP_EDGE_WALL_TEXT}."
)
# Top-left anchored beside the table's top-right corner (the table ends
# ~0.195 with its MATE column; the banded Y LOC column takes the native
# one's width), level with its header; its ~91 mm line ends ~0.296, above
# the isometric (top ~0.216) and inside the top zone margin (0.2667).
TAP_WALL_NOTE_XY = (0.205, 0.255)
HOLE_TABLE_NATIVE_Y_COLUMN = 2
HOLE_TABLE_BANDED_Y_COLUMN = 3
HOLE_TABLE_BANDED_Y_HEADING = f"Y LOC\nSEE NOTE {TAP_WALL_NOTE_NUMBER}"
# The physical (IncludeHidden=True) columns once the banded Y LOC is in and
# the native one hidden.
HOLE_TABLE_PHYSICAL_COLUMNS = (
    "TAG",
    "X LOC",
    "Y LOC",
    " ".join(HOLE_TABLE_BANDED_Y_HEADING.split()),
    "SIZE",
    "MATE",
)
# Rule 10 / rule 4: the tagged table names each tap's mate in its own column,
# the platen's holes for the platen-screw taps and the guide lock's for the
# lock taps (round 2). The column follows the fr_harmonic_base NOTE column:
# inserted after SIZE, its cells written per row bound to its station; the
# table may widen right (it ends ~0.165, the isometric starts ~0.305).
HOLE_TABLE_MATE_COLUMN = "MATE"
HOLE_TABLE_MATE_COLUMN_WIDTH = 0.030  # "MHA-PD-02" prints ~22 mm
HOLE_TABLE_MATES: dict[float, str] = {
    station: PLATEN_NUMBER if station in FRONT_X else LOCK_NUMBER
    for station in HOLE_STATIONS_MM
}
_INSERT_COLUMN_AFTER = 3  # swTableItemInsertPosition_After
_INSERT_COLUMN_DEFAULT_WIDTH = 0  # swInsertColumn_DefaultWidth
_TABLE_SIZE_CAN_CHANGE = 0  # swTableRowColChange_TableSizeCanChange
# The right view's depth: its text stack (keep = its centre) left of the
# extension lines (x 0.365 and 0.375), its underline on its own dimension
# line (~0.075), under the height's ".29" (bottom ~0.108). The four rows
# span ~0.075..0.095 (round 6, shipped; a
# six-row stack raised to 0.088 read as the .29's limits, round 7).
DEPTH_TEXT_XY = (0.341, 0.085)
# The table fits above the front view; 0.020 also clears the 12.7 mm zone
# margin enforced by the sheet audit.
HOLE_TABLE_X_M = 0.020
HOLE_TABLE_Y_M = 0.258
# The isometric at 1:2 (~100 x 60 mm) fills the empty field over the right
# view, right of the hole table (ends x ~0.165) and inside the right border;
# its note (left-anchored, ~61 mm) stands centred under it, over the right
# view.
ISO_CENTER = (0.355, 0.185)
ISO_SCALE = ISOMETRIC_VIEW_SCALE
ISO_NOTE_XY = (0.3245, 0.150)
THREAD_DESIGNATION = f"{TAPPED_HOLE_SPEC.size} UNC-{TAPPED_HOLE_SPEC.thread_class}"
THREAD_MAJOR_DIA_MM = THREAD_MAJOR_MM[TAPPED_HOLE_SPEC.size]
THREAD_PITCH_MM = 25.4 / int(TAPPED_HOLE_SPEC.size.rsplit("-", 1)[1])
THREAD_TAP_DRILL_MM = blind_cut_dia_mm(TAPPED_HOLE_SPEC)


def _bottom_surface_edge(view: Any) -> Any:
    """Return the guide's full-length model edge on the bottom surface."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="platen-guide bottom edge"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        start = _early_bound(start, "IVertex")
        end = _early_bound(end, "IVertex")
        p0 = tuple(float(value) * 1000.0 for value in start.GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in end.GetPoint())
        if abs(p0[1]) > 0.01 or abs(p1[1]) > 0.01:
            continue
        candidates.append((abs(p1[0] - p0[0]), edge))
    if not candidates:
        raise RuntimeError("front view has no model edge on the guide bottom surface")
    span_mm, edge = max(candidates, key=lambda item: item[0])
    if span_mm < GUIDE_LENGTH - 0.1:
        raise RuntimeError(f"guide bottom edge span is only {span_mm:.3f} mm")
    return edge


def _hole_rim_entities(
    view: Any, stations: tuple[float, ...], *, label: str
) -> tuple[Any, ...]:
    """Return the visible tap-drill rims at the requested model-X stations."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=label):
        edge = _early_bound(raw_edge, "IEdge")
        raw_curve = edge.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if not curve.IsCircle():
            continue
        parameters = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        candidates.append((parameters[0], parameters[6], edge))

    rims: list[Any] = []
    target_radius = THREAD_TAP_DRILL_MM / 2.0
    for station in stations:
        matches = [
            edge
            for x, radius, edge in candidates
            if abs(x - station) <= 0.02 and abs(radius - target_radius) <= 0.02
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"{label} station {station:g} mm has {len(matches)} visible "
                f"tap-drill rims; expected 1"
            )
        rims.append(matches[0])
    return tuple(rims)


def _table_cells(table: Any, columns: int) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(
            str(table.DisplayedText2(row, column, False) or "").strip()
            for column in range(columns)
        )
        for row in range(int(table.RowCount))
    )


def _hole_table_rows(table: Any) -> dict[float, tuple[int, str]]:
    """Bind every native row to exactly one model station: station -> (row, tag)."""
    if int(table.RowCount) != len(HOLE_STATIONS_MM) + 1:
        raise RuntimeError(
            f"platen-guide hole table has {int(table.RowCount)} rows; "
            f"expected {len(HOLE_STATIONS_MM) + 1}"
        )
    rows: dict[float, tuple[int, str]] = {}
    tags: set[str] = set()
    for row in range(1, int(table.RowCount)):
        tag = str(table.DisplayedText2(row, 0, False) or "").strip()
        x_mm = float(str(table.DisplayedText2(row, 1, False))) * 25.4
        station = min(HOLE_STATIONS_MM, key=lambda s: abs(s - x_mm))
        if not tag or tag in tags or abs(station - x_mm) > 0.02 or station in rows:
            raise RuntimeError(
                f"hole-table row {row} {tag!r} has no unique station: {x_mm:g}"
            )
        tags.add(tag)
        rows[station] = (row, tag)
    return rows


def _add_mate_column(table: Any) -> tuple[tuple[tuple[str, ...], ...], bool | None]:
    """Write HOLE_TABLE_MATES into a custom MATE column after SIZE.

    Returns the generated TAG/X LOC/Y LOC/SIZE cells, which the column must
    leave in place through the rebuild (``_check_mate_column``), and whether
    the SIZE cells were merged before it went in.
    """
    if int(table.ColumnCount) != 4:
        raise RuntimeError("the MATE column expects the native four-column hole table")
    rows = _hole_table_rows(table)
    generated = _table_cells(table, 4)
    size_merged = _size_cells_merged(table)
    inserted = table.InsertColumn2(
        _INSERT_COLUMN_AFTER, 3, HOLE_TABLE_MATE_COLUMN, _INSERT_COLUMN_DEFAULT_WIDTH
    )
    if inserted is not True:
        raise RuntimeError("native hole table refused the MATE column")
    if table.SetColumnTitle2(4, HOLE_TABLE_MATE_COLUMN, False) is not True:
        raise RuntimeError("native hole-table MATE column title did not set")
    for station, (row, tag) in rows.items():
        if table.IsCellTextEditable(row, 4) is not True:
            raise RuntimeError(f"native hole-table MATE cell of {tag} is not editable")
        table.SetText2(row, 4, False, HOLE_TABLE_MATES[station])
    actual = float(
        table.SetColumnWidth(4, HOLE_TABLE_MATE_COLUMN_WIDTH, _TABLE_SIZE_CAN_CHANGE)
    )
    if abs(actual - HOLE_TABLE_MATE_COLUMN_WIDTH) > 1e-6:
        raise RuntimeError(f"hole-table MATE column width did not persist: {actual!r}")
    return generated, size_merged


def _normalised(cells: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, ...], ...]:
    """Cells with their whitespace (SolidWorks' CRLF and wraps) collapsed."""
    return tuple(tuple(" ".join(value.split()) for value in row) for row in cells)


def _size_cells_merged(table: Any, column: int = 3) -> bool | None:
    """Whether every hole row's SIZE cell (``column``) is one merged cell;
    None when SolidWorks will not report it (the probe is telemetry only)."""
    last = int(table.RowCount) - 1
    try:
        for row in range(2, last + 1):
            state = table.IsCellMerged(row, column)
            merged = state[0] if isinstance(state, tuple) else state
            if not merged:
                return False
    except Exception as error:  # noqa: BLE001 - a probe, logged and not relied on
        _telemetry.info(f"hole-table SIZE merge state unreadable: {error!r}")
        return None
    return True


def _row_key(row: tuple[str, ...]) -> tuple[str, float, float]:
    """A hole row's tag and X/Y LOC, the locations compared as numbers
    (SolidWorks may print .140 or 0.140 for the same cell)."""
    return row[0], round(float(row[1]), 4), round(float(row[2]), 4)


def _check_mate_column(
    table: Any, generated: tuple[tuple[str, ...], ...], size_merged: bool | None
) -> None:
    """Only the MATE column changed: each row keeps its tag, location and
    size, and names its tap's mate.  The native table's one SIZE for the
    tag group (rule 10) is merged again if the inserted column split it."""
    if int(table.ColumnCount) != 5:
        raise RuntimeError("hole table lost or duplicated the MATE column")
    cells = _table_cells(table, 5)
    before = _normalised(generated)
    after = _normalised(tuple(row[:4] for row in cells))
    _telemetry.info(f"hole-table cells before MATE: {before!r}; after: {after!r}")
    if tuple(map(_row_key, after[1:])) != tuple(map(_row_key, before[1:])):
        raise RuntimeError(f"MATE column changed hole-table tags or locations: {cells!r}")
    # The nine taps keep one size, still the #4-40 tap (its native text may
    # re-render, so the compare is on the one size, not its exact string).
    sizes_after = {row[3] for row in after[1:]} - {""}
    if len(sizes_after) != 1 or "4-40" not in next(iter(sizes_after)):
        raise RuntimeError(f"MATE column changed the hole-table size: {cells!r}")
    rows = _hole_table_rows(table)
    mates = {row: HOLE_TABLE_MATES[station] for station, (row, _tag) in rows.items()}
    expected = tuple(
        HOLE_TABLE_MATE_COLUMN if index == 0 else mates[index]
        for index in range(len(cells))
    )
    if tuple(row[4] for row in cells) != expected:
        raise RuntimeError(f"hole-table MATE cells differ: {cells!r}")
    merged_after = _restore_size_merge(table, size_merged, 3, stage="the MATE column")
    _telemetry.info(
        "hole-table mates: "
        f"{ {tag: HOLE_TABLE_MATES[station] for station, (_row, tag) in rows.items()}!r}; "
        f"SIZE merged before={size_merged!r} after={merged_after!r}"
    )


def _restore_size_merge(
    table: Any, size_merged: bool | None, column: int, *, stage: str
) -> bool | None:
    """Merge the tag group's one SIZE again if an inserted column split it."""
    merged_after = _size_cells_merged(table, column)
    if size_merged and merged_after is False:
        try:
            restored = table.MergeCells(1, column, int(table.RowCount) - 1, column)
        except Exception as error:  # noqa: BLE001 - logged; the table stays valid
            restored = repr(error)
        merged_after = _size_cells_merged(table, column)
        _telemetry.info(
            f"hole-table SIZE merge restored after {stage}: "
            f"MergeCells={restored!r}, merged={merged_after!r}"
        )
    return merged_after


def _band_y_column(table: Any) -> None:
    """Print the tap row's band on every Y LOC value (rule 3).

    The custom column goes in after the native Y LOC at that column's width,
    each row reads TAP_Y_BAND_TEXT, the SIZE merge the insert may split is
    restored, and the native column is hidden last, so every index here is
    the same in the visible and the physical domain.
    """
    if int(table.ColumnCount) != 5:
        raise RuntimeError("the banded Y LOC column expects TAG/X LOC/Y LOC/SIZE/MATE")
    native, banded = HOLE_TABLE_NATIVE_Y_COLUMN, HOLE_TABLE_BANDED_Y_COLUMN
    width = float(table.GetColumnWidth(native))
    size_merged = _size_cells_merged(table, 3)
    inserted = table.InsertColumn2(
        _INSERT_COLUMN_AFTER,
        native,
        HOLE_TABLE_BANDED_Y_HEADING,
        _INSERT_COLUMN_DEFAULT_WIDTH,
    )
    if inserted is not True:
        raise RuntimeError("native hole table refused the banded Y LOC column")
    if table.SetColumnTitle2(banded, HOLE_TABLE_BANDED_Y_HEADING, False) is not True:
        raise RuntimeError("native hole-table banded Y LOC title did not set")
    for _station, (row, tag) in _hole_table_rows(table).items():
        if table.IsCellTextEditable(row, banded) is not True:
            raise RuntimeError(f"native hole-table banded Y LOC cell of {tag} is not editable")
        table.SetText2(row, banded, False, TAP_Y_BAND_TEXT)
    actual = float(table.SetColumnWidth(banded, width, _TABLE_SIZE_CAN_CHANGE))
    if abs(actual - width) > 1e-6:
        raise RuntimeError(f"hole-table banded Y LOC width did not persist: {actual!r}")
    merged = _restore_size_merge(table, size_merged, 4, stage="the banded Y LOC column")
    _telemetry.info(
        f"hole-table banded Y LOC: width={width!r}, SIZE merged "
        f"before={size_merged!r} after={merged!r}"
    )
    table.SetColumnHidden(native, True)  # VT_VOID; _check_banded_y_column reads it back


def _check_banded_y_column(table: Any) -> None:
    """After the rebuild, only the native Y LOC is hidden; every row keeps its
    tag, X LOC and mate, its native Y LOC is the model's tap row, and its
    printed Y LOC is that row with its band."""
    columns = int(table.TotalColumnCount)
    hidden = tuple(table.ColumnHidden(column) for column in range(columns))
    cells = _normalised(
        tuple(
            tuple(
                str(table.DisplayedText2(row, column, True) or "").strip()
                for column in range(columns)
            )
            for row in range(int(table.RowCount))
        )
    )
    _telemetry.info(f"hole-table banded Y LOC cells: {cells!r}; hidden={hidden!r}")
    if columns != len(HOLE_TABLE_PHYSICAL_COLUMNS) or hidden != tuple(
        column == HOLE_TABLE_NATIVE_Y_COLUMN for column in range(columns)
    ):
        raise RuntimeError(f"hole table is not native-Y-only hidden: hidden={hidden!r}")
    if tuple(value.upper() for value in cells[0]) != HOLE_TABLE_PHYSICAL_COLUMNS:
        raise RuntimeError(f"hole-table header after the banded Y LOC: {cells[0]!r}")
    tap_y_in = round(TAP_Y / 25.4, 3)
    rows = _hole_table_rows(table)
    for station, (row, tag) in rows.items():
        native_y, banded_y, mate = (
            cells[row][HOLE_TABLE_NATIVE_Y_COLUMN],
            cells[row][HOLE_TABLE_BANDED_Y_COLUMN],
            cells[row][5],
        )
        if round(float(native_y), 4) != tap_y_in or banded_y != TAP_Y_BAND_TEXT:
            raise RuntimeError(
                f"hole-table {tag} Y LOC native={native_y!r} printed={banded_y!r}; "
                f"expected {tap_y_in:.3f} and {TAP_Y_BAND_TEXT!r}"
            )
        if mate != HOLE_TABLE_MATES[station]:
            raise RuntimeError(f"hole-table {tag} lost its MATE: {cells[row]!r}")


def _place_hole_tags(view: Any, table: Any) -> None:
    """Move each native hole tag beside its own hole, on a leader to its rim."""
    stations_by_tag = {tag: station for station, (_row, tag) in _hole_table_rows(table).items()}
    moved: set[str] = set()
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:  # swNote
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText()).strip()
        if tag not in stations_by_tag:
            continue
        if tag in moved:
            raise RuntimeError(f"duplicate native hole tag {tag}")
        station = stations_by_tag[tag]
        hole_x = FRONT_LEFT_X_M + station / 1000.0
        tag_y = HOLE_TAG_ABOVE_Y_M if station in HOLE_TAGS_ABOVE else HOLE_TAG_Y_M
        if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
            raise RuntimeError(f"failed to give native hole tag {tag} a leader")
        if not annotation.SetPosition2(hole_x + HOLE_TAG_DX_M, tag_y, 0.0):
            raise RuntimeError(f"failed to reposition native hole tag {tag}")
        points = tuple(float(v) for v in annotation.GetLeaderPointsAtIndex(0) or ())
        if len(points) < 6 or math.dist(points[-3:-1], (hole_x, FRONT_HOLE_Y_M)) > (
            THREAD_MAJOR_DIA_MM / 2000.0 + 0.0005
        ):
            raise RuntimeError(
                f"native hole tag {tag} leader misses its hole: {points!r}"
            )
        moved.add(tag)
    if moved != set(stations_by_tag):
        raise RuntimeError(
            f"hole tags not found on the front view: {sorted(set(stations_by_tag) - moved)}"
        )
    _telemetry.info(f"hole tags placed beside their holes: {sorted(moved)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open platen-guide source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        source_model,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Isometric View Note",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    # Three places by default: the hole table's stations sit on the .001
    # grid (the platen's guide holes) and print in full.
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        layout=SPEC.layout,
        decimals=3,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Platen Guide Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen guide; manufacturing drawing; #4-40 UNC",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(
        adapter, str(SOURCE), "*Front", FRONT_VIEW_X_M, FRONT_VIEW_Y_M, scale=(1, 1)
    )
    right = place_view(adapter, str(SOURCE), "*Right", 0.370, 0.110, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    thread_seeds, thread_instances = import_cosmetic_threads(adapter, front)
    expected_thread_instances = len(REAR_X) + len(FRONT_X)
    if thread_instances != expected_thread_instances:
        raise RuntimeError(
            f"front view has {thread_seeds} cosmetic-thread seed(s) / "
            f"{thread_instances} instance(s); expected {expected_thread_instances}"
        )
    removed_thread_notes = remove_notes_matching(adapter, "#4-40")
    _telemetry.info(
        f"front view imported {thread_seeds} cosmetic-thread seed(s) as "
        f"{thread_instances} instance(s); removed {removed_thread_notes} "
        "automatic callout note(s)"
    )

    # Keep only the overall length and height; hole coordinates live in the
    # native hole table.
    # The bar's height sits off the front view's east end (the dimension
    # measures the x=Length edge's endpoints, sheet x 0.3248), not beside the
    # right view, where its extension lines would fence the section. At
    # x 0.338 the text clears the front view's box (0.3304). y 0.110 centres
    # the 3.5 mm text in the 7.4 mm gap between the
    # extension lines (the rail's edges) so neither runs through it. Both
    # dimensions live in the
    # GuideProfile sketch (Front plane). Their places, and the depth's, are the
    # part's (platen_guide_spec.DRAWING_PRECISION); the sheet proves the import
    # kept them. The depth's value, limits and two-line reason stack above its
    # dimension line; between its extension lines (10 mm apart) both lines
    # struck the 44 mm stack (machinist review round 3), so the stack stands
    # left of them, below the height's text.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep={"Length": (FRONT_VIEW_X_M, 0.135), "Height": (0.338, 0.110)},
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep={"Depth": DEPTH_TEXT_XY},
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The depth's one-sided band names what it protects (rule 4).
    set_dimension_callouts(adapter, annotations, {"Depth": GUIDE_DEPTH_CALLOUT})
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    hole_table = insert_hole_table(
        adapter,
        front,
        datum_xy=(FRONT_LEFT_X_M, FRONT_BOTTOM_Y_M),
        hole_points=tuple(
            (FRONT_LEFT_X_M + station / 1000.0, FRONT_HOLE_Y_M)
            for station in HOLE_STATIONS_MM
        ),
        hole_entities=_hole_rim_entities(
            front, HOLE_STATIONS_MM, label="platen-guide front"
        ),
        # X LOC = the station from the left face at .XXX (the title block's
        # ±.005); Y LOC = the tap row above the bottom face, printed with its
        # ±.005 by the banded column below. Neither is basic: no frame.
        expected_locations_mm=tuple((station, TAP_Y) for station in HOLE_STATIONS_MM),
        anchor_xy=(HOLE_TABLE_X_M, HOLE_TABLE_Y_M),
        label="platen-guide taps",
        unit="in",
        location_places=3,
        basic_locations=False,
    )
    # The nine taps are one size: the table prints that size once, the SIZE
    # cells of tag group A merged natively (rule 10: the size callout once per
    # tag group), each hole keeping its own tag and X/Y LOC row.  The shared
    # helper inserts the table uncombined; draw_fr_harmonic_base combines it
    # the same way.
    hole_feature = _early_bound(
        _early_bound(hole_table, "IHoleTableAnnotation").HoleTable, "IHoleTable"
    )
    hole_feature.CombineSameSize = True
    if not hole_feature.CombineSameSize or hole_feature.CombineTags:
        raise RuntimeError("platen-guide hole table did not keep one tag per hole")
    drawing_model.EditRebuild3()
    if int(hole_table.RowCount) != len(HOLE_STATIONS_MM) + 1:
        raise RuntimeError("combining the platen-guide tap sizes changed the table rows")
    # Each tap's mate in its own column (rule 10), checked after a rebuild as
    # draw_fr_harmonic_base checks its NOTE column.
    generated, size_merged = _add_mate_column(hole_table)
    drawing_model.EditRebuild3()
    _check_mate_column(hole_table, generated, size_merged)
    _place_hole_tags(front, hole_table)
    # The tap row's band on every printed Y LOC (rule 3), the native column
    # hidden; read back after a rebuild.
    _band_y_column(hole_table)
    drawing_model.EditRebuild3()
    _check_banded_y_column(hole_table)
    # Note 1, which the banded Y LOC header cites: the taps' finished wall.
    if add_note(adapter, TAP_WALL_NOTE, *TAP_WALL_NOTE_XY) is None:
        raise RuntimeError("tap wall note 1 was not inserted")
    # The platen hangs by the top rail's bottom face on the bar's top
    # edge and slides along it: the one running surface takes the part-owned
    # Ra symbol, landed on that face's edge in the front view.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=BAR_SLIDE_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "bar_slide"),
        label="bar-slide face finish",
        entity=_bottom_surface_edge(front),
        char_height=FINISH_CHAR_HEIGHT,
        leader_attach_xy=model_point_in_view(
            adapter,
            front,
            (BAR_SLIDE_STATION_MM / 1000.0, 0.0, 0.0),
            label="bar-slide face finish landing",
        ),
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Guide Manufacturing Drawing",
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
