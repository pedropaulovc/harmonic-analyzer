r"""Create the three-sheet oblique-trammel jig fitter package (MHA-CH-006-TL-000).

Sheet 1 shows the jig assembled at the symmetric inner pass in the machine
frame: the plan (camera down Z) above the operator's elevation, each titled,
the plan tagging the carrier's pass holes A1-B2, both rails and the spindle
origin, beside the pose caption and the rail-alignment targets the fitter
indicates the pivot pins to. Sheet 2 is the builder-owned ``JIG_EXPLODED``
presentation with the BOM: the seven made parts from the part registry, each
ballooned (both base bars, both pivot blocks and both pivot pins included),
then the bought items the model does not carry, by shop-inventory id. Sheet 3
is the finished isometric beside the assembly order and checks. Every view is
one the builder named in the machine frame (``spec.VIEW_AXES``), its mapping
proven on the sheet before anything is placed by it. Every text,
pose and reference value comes from
``ch_rocker_arm_tl_oblique_jig_assembly_spec`` (and through it the calculator
``ch_rocker_arm_tl_oblique_trammel_spec``) or the part registry; this recipe
only lays the sheets out. It never edits the source assembly or its explodes.
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

import _config
import _telemetry
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
from _check import check
from _com import _early_bound
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _drawing_balloon_display import rendered_balloon_circle
from _drawing_balloons import (
    BalloonAnchor,
    BalloonLanding,
    _spread_balloons,
    add_component_bom_balloons,
    assert_balloon_landings,
)
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_tables import insert_bom_table
from _drawing_view_configuration import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
    set_view_exploded_state,
)
from _drawing_view_display import set_hidden_lines_removed
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _simplified_names import simplified_name
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_points_in_view
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_jig_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_NAMES = (
    "ASSEMBLED AT INNER PASS",
    "EXPLODED VIEW + BOM",
    "ASSEMBLY STEPS",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the jig's primary sheet must remain landscape")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
# The jig is about 915 x 400 in plan: 1:4 for the arrangement, 1:8 for the
# finished isometric and 1:10 for the exploded one. Its stack stands about
# 340 high, and jig-r5 measured its outline at 127.4 x 113.2 mm at 1:8: with
# the balloon rings, too wide for the room left of the BOM.
ASSEMBLED_SCALE = (1.0, 4.0)
ISOMETRIC_SCALE = (1.0, 8.0)
EXPLODED_SCALE = (1.0, 10.0)
SHEET_SCALES = dict(
    zip(SHEET_NAMES, (ASSEMBLED_SCALE, EXPLODED_SCALE, ISOMETRIC_SCALE))
)
SHEET_SCALE = SHEET_SCALES[SHEET_NAMES[0]]

# Sheet geometry, metres: the template's inner border and the title block in
# its lower-right corner. Every view outline and balloon ring stays inside the
# border and out of the title block (drawing-guidelines.md rule 13).
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
SHEET_INNER_BORDER = (
    0.0127,
    0.0127,
    _TEMPLATE.width_m - 0.0127,
    _TEMPLATE.height_m - 0.0127,
)
TITLE_BLOCK = (
    _TEMPLATE.title_block_left_m,
    0.0,
    _TEMPLATE.width_m,
    _TEMPLATE.title_block_top_m,
)

# Sheet 1: the plan over the operator's elevation, third-angle and on one
# vertical, right of the pose caption; the alignment targets under the
# elevation, left of the title block. At 1:4 the plan is about 229 x 100 and
# the elevation 229 x 22. Each view's title stands centred under it.
PLAN_CENTER = (0.270, 0.205)
ELEVATION_CENTER = (0.270, 0.125)
CAPTION_XY = (0.018, 0.255)
CAPTION_WIDTH = 46  # characters; default-format note text, left of the plan
ALIGNMENT_XY = (0.018, 0.105)
ALIGNMENT_WIDTH = 68  # characters; stops left of the title block
# Default-format note text: about 2.9 mm a character on the farm's templates.
NOTE_CHAR_M = 0.0029
VIEW_LABEL_GAP = 0.003


def _label_under(center: tuple[float, float], height_mm: float, text: str):
    """Top-left of ``text`` centred under a 1:4 view ``height_mm`` tall."""
    half = height_mm / 1000.0 * ASSEMBLED_SCALE[0] / ASSEMBLED_SCALE[1] / 2.0
    return (
        center[0] - len(text) * NOTE_CHAR_M / 2.0,
        center[1] - half - VIEW_LABEL_GAP,
    )


(_EX0, _EX1), (_EY0, _EY1), (_EZ0, _EZ1) = spec.MODEL_EXTENT
PLAN_LABEL_XY = _label_under(PLAN_CENTER, _EY1 - _EY0, spec.PLAN_VIEW_LABEL)
ELEVATION_LABEL_XY = _label_under(
    ELEVATION_CENTER, _EZ1 - _EZ0, spec.ELEVATION_VIEW_LABEL
)

# Sheet 2: the exploded isometric left, its balloon ring inside the border,
# the caption under it; the BOM right, five columns to the inner border.
BALLOON_MARGIN = 0.024
# Table text runs about 2.9 mm a character (default format). The INVENTORY ID
# column takes the longest id whole: ids carry no spaces, so a narrower cell
# would overflow rather than wrap, and the id must print exactly.
BOM_CHAR_M = 0.0029
BOM_CELL_PADDING_M = 0.004
BOM_COLUMN_WIDTHS = {
    "item": 0.010,
    "part": 0.050,
    "description": 0.058,  # wraps at spaces, clear of the exploded view's ring
    "inventory": round(
        max(len(item.inventory_id) for item in spec.BOUGHT_ITEMS) * BOM_CHAR_M
        + BOM_CELL_PADDING_M,
        3,
    ),
    "quantity": 0.012,
}
BOM_INVENTORY_TITLE = "INVENTORY ID"
NO_ENTRY = "-"  # a made part has no inventory id; a bought item no part number
BOM_ANCHOR = (SHEET_INNER_BORDER[2] - sum(BOM_COLUMN_WIDTHS.values()), 0.262)
EXPLODED_CAPTION = spec.EXPLODED_CAPTION
EXPLODED_CAPTION_XY = (0.018, 0.030)
# The exploded view's room: inside the border, left of the BOM and over the
# caption. Its measured outline is centred in it and, ringed by the outer
# balloons, must stay in it.
EXPLODED_REGION = (
    SHEET_INNER_BORDER[0],
    EXPLODED_CAPTION_XY[1] + 0.003,
    BOM_ANCHOR[0],
    SHEET_INNER_BORDER[3],
)
EXPLODED_ISO_CENTER = (
    (EXPLODED_REGION[0] + EXPLODED_REGION[2]) / 2.0,
    (EXPLODED_REGION[1] + EXPLODED_REGION[3]) / 2.0,
)

# Sheet 3: the order and checks down the left; the finished isometric right.
ASSEMBLY_ISO_CENTER = (0.340, 0.175)
STEPS_XY = (0.018, 0.262)
# Under the steps, over the title block's top (y 0.066): 6 mm lower since
# c3-r7, whose step 8 names the HUB hole's press fit on one more line.
CHECKS_XY = (0.018, 0.116)
STEPS_LINE_WIDTH = 80  # characters; stops left of the isometric

BOM_QUANTITIES = {stem: spec.QUANTITIES[stem] for stem in spec.BOM_ORDER}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "ch-rocker-arm-tl-oblique-base-bar": _config.parts(
        "ch-rocker-arm-tl-oblique-base-bar"
    ),
    "ch-rocker-arm-tl-oblique-pivot-block": _config.parts(
        "ch-rocker-arm-tl-oblique-pivot-block"
    ),
    "ch-rocker-arm-tl-oblique-pivot-pin": _config.parts(
        "ch-rocker-arm-tl-oblique-pivot-pin"
    ),
    "ch-rocker-arm-tl-oblique-carrier": _config.parts(
        "ch-rocker-arm-tl-oblique-carrier"
    ),
    "ch-rocker-arm-tl-oblique-riser": _config.parts("ch-rocker-arm-tl-oblique-riser"),
    "ch-rocker-arm-tl-oblique-hub-pin": _config.parts(
        "ch-rocker-arm-tl-oblique-hub-pin"
    ),
    "ch-rocker-arm-tl-oblique-feed-lever": _config.parts(
        "ch-rocker-arm-tl-oblique-feed-lever"
    ),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the assembly families")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
BOM_DESCRIPTIONS = dict(spec.BOM_DESCRIPTIONS)
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}
# The bought items follow the made parts, numbered on from them; the model
# does not carry them, so they take no balloon (the steps name them).
BOUGHT_ITEM_NUMBERS = tuple(
    str(len(BOM_COMPONENTS) + index) for index in range(1, len(spec.BOUGHT_ITEMS) + 1)
)
_INSERT_ROW_LAST = 4  # swTableItemInsertPosition_Last

# One balloon per component: the two-off families (bars, blocks, pins)
# balloon their first instance with the others and their second on a later
# pass; then every balloon shares one ring (_ring_balloons).
TWO_OFF = tuple(stem for stem in BOM_COMPONENTS if BOM_QUANTITIES[stem] == 2)
if set(BOM_QUANTITIES.values()) != {1, 2}:
    raise AssertionError("every jig family is one- or two-off")
BALLOON_ANCHORS = {
    stem: BalloonAnchor(instance=f"{stem}-1") if stem in TWO_OFF else BalloonAnchor()
    for stem in BOM_COMPONENTS
}
SECOND_INSTANCE_BALLOON_ANCHORS = {
    stem: BalloonAnchor(instance=f"{stem}-2") for stem in TWO_OFF
}

EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: spec.EXPLODED_VIEW_NAME,
    SIMPLIFIED_VIEW_CONFIGURATION: simplified_name(spec.EXPLODED_VIEW_NAME),
}
if spec.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the jig explode is authored in Default")


def _wrapped(lines: tuple[str, ...], *, width: int, heading: str | None = None) -> str:
    """Wrap each numbered line under its own number; one note per block. A
    hyphenated word (HOLD-DOWNS, A1-B1) stays whole on its line."""
    out = [heading] if heading else []
    for line in lines:
        number, sep, rest = line.partition(". ")
        if sep and number.isdigit():
            out += textwrap.wrap(
                rest,
                width=width,
                initial_indent=f"{number}. ",
                subsequent_indent=" " * (len(number) + 2),
                break_on_hyphens=False,
            )
        else:
            out += textwrap.wrap(
                line, width=width, subsequent_indent="   ", break_on_hyphens=False
            )
    return "\n".join(out)


ASSEMBLED_CAPTION = _wrapped((spec.ASSEMBLED_CAPTION,), width=CAPTION_WIDTH)
ALIGNMENT_NOTE = _wrapped(spec.ALIGNMENT_NOTE_LINES, width=ALIGNMENT_WIDTH)
ASSEMBLY_STEPS = _wrapped(
    spec.ASSEMBLY_STEPS, width=STEPS_LINE_WIDTH, heading="ASSEMBLY SEQUENCE"
)
ASSEMBLY_CHECKS = _wrapped(spec.ASSEMBLY_CHECKS, width=STEPS_LINE_WIDTH)


def _activate_sheet(adapter: Any, name: str) -> Any:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")
    return current


def _add_note_block(
    adapter: Any, sheet_name: str, text: str, xy: tuple[float, float], *, label: str
) -> Any:
    """A sheet-owned note: activate the sheet so no view owns it."""
    _activate_sheet(adapter, sheet_name)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the jig {label}")
    note = _early_bound(note, "INote")
    printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if printed != text:
        raise RuntimeError(f"jig {label} printed as {printed!r}")
    return note


def _view_outline(view: Any, *, label: str) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"{label}: invalid view outline {outline!r}")
    return outline[0], outline[1], outline[2], outline[3]


def _assert_view_on_sheet(
    view: Any,
    *,
    margin: float = 0.0,
    bounds: tuple[float, float, float, float] = SHEET_INNER_BORDER,
    label: str,
) -> None:
    """The view's outline, grown by ``margin`` (a balloon ring), stays inside
    ``bounds`` (the inner border unless given) and clear of the title block."""
    x0, y0, x1, y1 = _view_outline(view, label=label)
    x0, y0, x1, y1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
    left, bottom, right, top = bounds
    findings = []
    if x0 < left or y0 < bottom or x1 > right or y1 > top:
        findings.append(f"leaves {bounds}")
    tx0, ty0, tx1, ty1 = TITLE_BLOCK
    if x1 > tx0 and x0 < tx1 and y0 < ty1 and y1 > ty0:
        findings.append(f"enters the title block {TITLE_BLOCK}")
    if findings:
        raise RuntimeError(
            f"{label}: outline {(x0, y0, x1, y1)!r} " + "; ".join(findings)
        )


def _center_view_outline(
    adapter: Any, view: Any, center: tuple[float, float], *, label: str
) -> None:
    """Translate the actual exploded outline using the current native origin."""
    view = _early_bound(view, "IView")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    before = tuple(float(value) for value in view.Position)
    target = (
        before[0] + center[0] - (x0 + x1) / 2.0,
        before[1] + center[1] - (y0 + y1) / 2.0,
    )
    if not view.SetViewPosition(double_array(list(target)), False):
        raise RuntimeError(f"{label}: SetViewPosition refused {target!r}")
    adapter.currentModel.EditRebuild3()
    after = tuple(float(value) for value in view.Position)
    if len(after) != 2 or any(abs(a - b) > 1e-6 for a, b in zip(after, target)):
        raise RuntimeError(f"{label}: view moved to {after!r}, expected {target!r}")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    if (
        abs((x0 + x1) / 2.0 - center[0]) > 1e-6
        or abs((y0 + y1) / 2.0 - center[1]) > 1e-6
    ):
        raise RuntimeError(f"{label}: measured outline did not centre at {center!r}")


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _validate_source(source_model: Any) -> None:
    """The builder-owned explodes exist, and the source opens collapsed with
    exactly the contracted families."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != ASSEMBLY_VIEW_CONFIGURATION:
        raise RuntimeError("jig source must open in its Default configuration")
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(f"jig {owner} exploded views {names!r} != {(wanted,)!r}")
    counts: dict[str, int] = {}
    for raw in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw, "IComponent2")
        stem = _component_stem(component)
        counts[stem] = counts.get(stem, 0) + 1
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform")
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform")
        if any(
            abs(float(actual) - float(expected)) > 1e-9
            for actual, expected in zip(total.ArrayData, base.ArrayData, strict=True)
        ):
            raise RuntimeError(
                f"jig source must open collapsed: {component.Name2!r} is displaced"
            )
    if counts != BOM_QUANTITIES:
        raise RuntimeError(f"jig families {counts!r} != contract {BOM_QUANTITIES!r}")


_INSERT_COLUMN_AFTER = 3  # swTableItemInsertPosition_After
_INSERT_COLUMN_DEFAULT_WIDTH = 0  # swInsertColumn_DefaultWidth


def _bom_cells(table: Any) -> tuple[tuple[str, ...], ...]:
    """Every displayed BOM cell, header row first."""
    return tuple(
        tuple(
            str(table.DisplayedText(row, column) or "").strip()
            for column in range(int(table.ColumnCount))
        )
        for row in range(int(table.RowCount))
    )


def _bom_column(
    header: tuple[str, ...], predicate: Callable[[str], bool], label: str
) -> int:
    matches = [index for index, cell in enumerate(header) if predicate(cell.upper())]
    if len(matches) != 1:
        raise RuntimeError(f"jig BOM has no unique {label} column: {header!r}")
    return matches[0]


def _bom_columns(header: tuple[str, ...]) -> dict[str, int]:
    return {
        "item": _bom_column(
            header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
        ),
        "part": _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER"),
        "description": _bom_column(
            header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
        ),
        "inventory": _bom_column(
            header, lambda cell: cell == BOM_INVENTORY_TITLE, BOM_INVENTORY_TITLE
        ),
        "quantity": _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY."),
    }


def _set_cell(table: Any, row: int, column: int, text: str, *, label: str) -> None:
    if not table.IsCellTextEditable(row, column):
        raise RuntimeError(f"jig BOM {label} cell is locked")
    table.SetText2(row, column, False, text)


def _bought_row_cells() -> tuple[dict[str, str], ...]:
    """The bought items' BOM cells, item numbers continuing the made parts';
    each is named by its shop-inventory id, never a vendor SKU."""
    return tuple(
        {
            "item": number,
            "part": NO_ENTRY,
            "description": item.description,
            "inventory": item.inventory_id,
            "quantity": str(item.quantity),
        }
        for number, item in zip(BOUGHT_ITEM_NUMBERS, spec.BOUGHT_ITEMS, strict=True)
    )


def _validate_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    """Rewrite part numbers, prove identities/descriptions/quantities, add the
    INVENTORY ID column after DESCRIPTION, then append the bought items by
    inventory id; return (stem, item number) for the made parts in BOM order."""
    table = _early_bound(table, "ITableAnnotation")
    contents = _bom_cells(table)
    rows = len(contents)
    columns = len(contents[0]) if contents else 0
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"jig BOM is {rows}x{columns}; expected "
            f"{len(BOM_COMPONENTS) + 1} rows and at least four columns"
        )
    header = contents[0]
    for title in ("MATERIAL", BOM_INVENTORY_TITLE):
        if title in (cell.upper() for cell in header):
            raise RuntimeError(f"jig BOM template already has {title!r}")
    item_column = _bom_column(
        header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
    )
    part_column = _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = _bom_column(
        header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
    )
    quantity_column = _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY.")

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        text = row[part_column].casefold()
        stem = BOM_NORMALIZED_ALIASES.get(text, text)
        if stem in actual:
            raise RuntimeError(f"jig BOM repeats component family {stem!r}")
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"jig BOM identities {sorted(actual)!r} != {sorted(BOM_COMPONENTS)!r}"
        )
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(BOM_COMPONENTS) + 1)}:
        raise RuntimeError(f"jig BOM item numbers {sorted(items)!r} are not contiguous")
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            _set_cell(
                table, row_index, part_column, number, label=f"{stem} part-number"
            )
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"jig BOM description mismatch for {stem!r}")
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"jig BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )

    # Made parts have no inventory id; they print NO_ENTRY there.
    if not table.InsertColumn2(
        _INSERT_COLUMN_AFTER,
        description_column,
        BOM_INVENTORY_TITLE,
        _INSERT_COLUMN_DEFAULT_WIDTH,
    ):
        raise RuntimeError("jig BOM refused the INVENTORY ID column")
    inventory_column = description_column + 1
    if not table.SetColumnTitle2(inventory_column, BOM_INVENTORY_TITLE, False):
        raise RuntimeError("jig BOM INVENTORY ID column title did not set")
    for stem, (row_index, *_rest) in actual.items():
        _set_cell(
            table, row_index, inventory_column, NO_ENTRY, label=f"{stem} INVENTORY ID"
        )

    widths = _bom_columns(_bom_cells(table)[0])
    if int(table.ColumnCount) != len(BOM_COLUMN_WIDTHS) or set(widths) != set(
        BOM_COLUMN_WIDTHS
    ):
        raise RuntimeError("jig BOM columns are not the contract")

    # The bought items: one appended row each, every cell written.
    bought_rows = []
    for cells in _bought_row_cells():
        if not table.InsertRow(_INSERT_ROW_LAST, 0):
            raise RuntimeError(f"jig BOM refused the row for {cells['inventory']!r}")
        row_index = int(table.RowCount) - 1
        for key, text in cells.items():
            _set_cell(
                table, row_index, widths[key], text, label=f"{cells['inventory']} {key}"
            )
        bought_rows.append((row_index, cells))

    for key, column in widths.items():
        width = BOM_COLUMN_WIDTHS[key]
        if abs(float(table.SetColumnWidth(column, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"jig BOM {key} column width did not persist")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("jig BOM rebuild failed")
    settled = _bom_cells(table)
    if len(settled) != len(BOM_COMPONENTS) + len(spec.BOUGHT_ITEMS) + 1:
        raise RuntimeError(f"jig BOM settled with {len(settled)} rows")
    expected_cells = [
        (row_index, {"part": BOM_PART_NUMBERS[stem], "inventory": NO_ENTRY})
        for stem, (row_index, *_rest) in actual.items()
    ] + bought_rows
    for row_index, cells in expected_cells:
        for key, text in cells.items():
            applied = settled[row_index][widths[key]]
            if applied != text:
                raise RuntimeError(
                    f"jig BOM row {row_index} {key} reads {applied!r}, expected {text!r}"
                )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


_PROJECTION_TOLERANCE_M = 1e-5
_MAPPING_STATIONS = ((0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.0, 0.1, 0.0), (0.0, 0.0, 0.1))


def _require_view_axes(
    adapter: Any, view: Any, name: str, scale: tuple[float, float], *, label: str
) -> None:
    """Fail unless ``view`` draws machine X/Y/Z the way ``spec.VIEW_AXES[name]``
    says at ``scale`` (``draw_fr_harmonic_base._require_bottom_view_mapping``'s
    proof): every title, tag and explode reading on the sheet assumes it."""
    right, up, _sight = spec.VIEW_AXES[name]
    origin, *ends = model_points_in_view(
        adapter,
        view,
        _MAPPING_STATIONS,
        label=f"{label} mapping",
        names=("origin", "+X", "+Y", "+Z"),
    )
    length = 0.1 * scale[0] / scale[1]
    for axis, end in enumerate(ends):
        expected = (right[axis] * length, up[axis] * length)
        drawn = (end[0] - origin[0], end[1] - origin[1])
        if max(abs(d - e) for d, e in zip(drawn, expected)) > _PROJECTION_TOLERANCE_M:
            raise RuntimeError(
                f"{label}: 100 mm along machine {'XYZ'[axis]} draws {drawn}, "
                f"not {expected}: {name!r} is not the spec's view"
            )


def _place_named_view(
    adapter: Any,
    name: str,
    center: tuple[float, float],
    scale: tuple[float, float],
    *,
    label: str,
) -> Any:
    view = place_view(adapter, str(SOURCE), name, *center, scale=scale)
    _require_view_axes(adapter, view, name, scale, label=label)
    return view


def _add_plan_tags(adapter: Any, plan: Any) -> None:
    """Each ``spec.PLAN_TAGS`` text with a leader to its machine point, owned
    by the plan; both ends projected through the plan's measured mapping."""
    names = [tag.text.split("\n")[0] for tag in spec.PLAN_TAGS]
    tips = model_points_in_view(
        adapter,
        plan,
        [tuple(value / 1000.0 for value in tag.tip) for tag in spec.PLAN_TAGS],
        label="jig plan tag tips",
        names=names,
    )
    texts = model_points_in_view(
        adapter,
        plan,
        [(x / 1000.0, y / 1000.0, 0.0) for x, y in (t.text_xy for t in spec.PLAN_TAGS)],
        label="jig plan tag texts",
        names=names,
    )
    for tag, name, tip, text_xy in zip(spec.PLAN_TAGS, names, tips, texts):
        add_leader_note(
            adapter,
            tag.text,
            text_xy=text_xy,
            attach_xy=tip,
            label=f"jig plan tag {name}",
            view=plan,
        )


def _place_assembled_sheet(adapter: Any) -> None:
    """Plan over the operator's elevation at the modelled pose, each titled,
    the plan's tags, the pose caption, and the rail-alignment targets."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    plan = _place_named_view(
        adapter, spec.PLAN_VIEW, PLAN_CENTER, ASSEMBLED_SCALE, label="jig plan"
    )
    elevation = _place_named_view(
        adapter,
        spec.ELEVATION_VIEW,
        ELEVATION_CENTER,
        ASSEMBLED_SCALE,
        label="jig elevation",
    )
    for view, label in ((plan, "jig plan"), (elevation, "jig elevation")):
        set_hidden_lines_removed(adapter, view)
        apply_view_configuration(adapter, view, label=label)
        _assert_view_on_sheet(view, label=label)
    _add_plan_tags(adapter, plan)
    for text, xy, label in (
        (spec.PLAN_VIEW_LABEL, PLAN_LABEL_XY, "plan title"),
        (spec.ELEVATION_VIEW_LABEL, ELEVATION_LABEL_XY, "elevation title"),
    ):
        _add_note_block(adapter, SHEET_NAMES[0], text, xy, label=label)
    _add_note_block(
        adapter, SHEET_NAMES[0], ASSEMBLED_CAPTION, CAPTION_XY, label="pose caption"
    )
    _add_note_block(
        adapter,
        SHEET_NAMES[0],
        ALIGNMENT_NOTE,
        ALIGNMENT_XY,
        label="rail-alignment targets",
    )


@contextmanager
def _source_configuration_active(view: Any, *, label: str) -> Iterator[None]:
    """Make the exploded view's configuration the source's active one.

    The balloons read the explode's steps from that configuration
    (``_drawing_balloons._view_explode_offsets``). A non-active one read all
    of them on the first jig drawing but none on jig-r6, and that reader
    refuses a non-active configuration that reads none; an active one's
    steps are made readable by showing its named explode on the source, the
    path the measuring-stick drawing's identical exploded sheet takes. Only
    the open session's active configuration changes; the source is never
    saved, and ``Default`` is active again on exit. Each switch is read
    back.
    """
    bound = _early_bound(view, "IView")
    wanted = str(bound.ReferencedConfiguration)
    model = _early_bound(bound.ReferencedDocument, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")

    def active() -> str:
        return str(_early_bound(manager.ActiveConfiguration, "IConfiguration").Name)

    rest = active()
    if rest != ASSEMBLY_VIEW_CONFIGURATION:
        raise RuntimeError(
            f"{label}: the source is in {rest!r}, not {ASSEMBLY_VIEW_CONFIGURATION!r}"
        )
    if not bool(model.ShowConfiguration2(wanted)) or active() != wanted:
        raise RuntimeError(f"{label}: the source did not activate {wanted!r}")
    try:
        if not bool(bound.IsExploded()) or str(bound.ReferencedConfiguration) != wanted:
            raise RuntimeError(
                f"{label}: activating {wanted!r} on the source changed the view"
            )
        yield
    finally:
        primary_error = sys.exception()
        try:
            if not bool(model.ShowConfiguration2(rest)) or active() != rest:
                raise RuntimeError(f"{label}: the source did not re-activate {rest!r}")
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(f"{label}: restoring {rest!r}: {cleanup_error}")


# Two rings failed the layout audit on both item sets (jig-r7 and c4-r2): a
# second instance attaches near its first, so its outer-ring leader runs in
# across the inner ring at about that angle, through a balloon parked there
# (balloon 3's leader ran 6.32 mm through balloon 4 on jig-r7). One ring,
# ordered by attachment angle, has no balloon inside another's leader path:
# replayed on both runs' logged attachments, every leader stays over 8 mm
# clear of every other balloon. Pushing crowded circles apart can still
# leave two leaders crossed; swapping their slots uncrosses them and
# strictly shortens their total length (the triangle inequality), so
# repeated swaps end. The cap only bounds a wrong input.
# draw_pd_paper_drive_assembly's transgear sheet rings its balloons by the
# same rule.
_UNCROSS_SWAPS_MAX = 64
# jig-r8: balloons 1 and 2 passed the swap step, then the audit found their
# leaders crossed 0.5 mm from balloon 2's attachment (0.16 mm across balloon
# 1's leader at their 19 degree meet). An end that sits on, or a hair short
# of, another leader is a "touch" to find_leader_leader_crossings, and the
# rebuild after the move settles attachments by more than its 0.1 mm. So once
# no leader crosses another, each is run on past its attachment by an
# arrowhead's length (~2.4 mm rendered) and a pair crossing there swaps too,
# but only when the swap crosses nothing and leaves fewer such near-crossings.
# That count falls with every such swap, so this phase ends as well; it has
# to be conditional, because two leaders converging on attachments under
# 2.4 mm apart (c4-r4: 13 balloons, second instances attaching near their
# first) cross once run on whichever slots they take, and unconditional
# swaps toggled that pair until the cap.
_UNCROSS_END_CLEARANCE_M = 2.4e-3


def _leader_past_attachment(
    centre: tuple[float, float], attach: tuple[float, float], run_on: float
) -> tuple[float, float]:
    """``attach`` moved ``run_on`` further from ``centre`` along the leader
    (unchanged for a zero-length leader)."""
    dx, dy = attach[0] - centre[0], attach[1] - centre[1]
    length = math.hypot(dx, dy)
    if length == 0.0:
        return attach
    scale = run_on / length
    return (attach[0] + dx * scale, attach[1] + dy * scale)


def _ring_crossings(
    centres: Sequence[tuple[float, float]],
    attachments: Sequence[tuple[float, float]],
    slots: Sequence[int],
    *,
    run_on: float,
) -> list[tuple[int, int]]:
    """The balloon pairs whose leaders, each from its slot's centre to
    ``run_on`` past its attachment, cross."""
    segments = []
    for index, attach in enumerate(attachments):
        centre = centres[slots[index]]
        end = _leader_past_attachment(centre, attach, run_on)
        segments.append(
            LeaderSegment(
                label=str(index),
                kind="balloon",
                x0=centre[0],
                y0=centre[1],
                x1=end[0],
                y1=end[1],
            )
        )
    return [
        (int(crossing.a.label), int(crossing.b.label))
        for crossing in find_leader_leader_crossings(segments)
    ]


def _swapped(slots: Sequence[int], first: int, second: int) -> list[int]:
    trial = list(slots)
    trial[first], trial[second] = trial[second], trial[first]
    return trial


def uncrossed_ring_slots(
    centres: Sequence[tuple[float, float]],
    attachments: Sequence[tuple[float, float]],
) -> list[int]:
    """Which ring slot (an index into ``centres``, the circle centres as
    placed) each balloon takes so that no two leaders, each from its circle's
    centre to its attachment, cross; then, while a swap that crosses nothing
    can, fewer of them cross within ``_UNCROSS_END_CLEARANCE_M`` past an
    attachment. Leaders that do not cross keep their slots, so the slots, and
    the circles' clearances, are the ring's own."""
    if len(centres) != len(attachments):
        raise ValueError("one ring slot per balloon attachment")
    slots = list(range(len(centres)))
    for _swap in range(_UNCROSS_SWAPS_MAX + 1):
        crossed = _ring_crossings(centres, attachments, slots, run_on=0.0)
        if crossed:
            slots = _swapped(slots, *crossed[0])
            continue
        run_on = _UNCROSS_END_CLEARANCE_M
        near = _ring_crossings(centres, attachments, slots, run_on=run_on)
        for pair in near:
            trial = _swapped(slots, *pair)
            if _ring_crossings(centres, attachments, trial, run_on=0.0):
                continue
            left = _ring_crossings(centres, attachments, trial, run_on=run_on)
            if len(left) < len(near):
                slots = trial
                break
        else:
            return slots
    raise RuntimeError(
        f"balloon ring: leaders still cross after {_UNCROSS_SWAPS_MAX} slot swaps: "
        f"centres {[tuple(round(v, 5) for v in c) for c in centres]}, "
        f"attachments {[tuple(round(v, 5) for v in a) for a in attachments]}, "
        f"slots {slots}"
    )


def _ring_balloons(
    adapter: Any, view: Any, landings: Sequence[BalloonLanding], *, label: str
) -> None:
    """Ring every one of ``view``'s balloons together, ``BALLOON_MARGIN``
    outside its outline, then move them between their own ring slots until no
    two leaders cross (:func:`uncrossed_ring_slots`); attachments stay."""
    _spread_balloons(
        adapter, view, [landing.note for landing in landings], margin=BALLOON_MARGIN
    )
    rebuild_drawing(adapter, label=f"{label} ring")
    annotations, centres, offsets, attachments = [], [], [], []
    for landing in landings:
        x, y, _radius = rendered_balloon_circle(landing.note, label=label)
        annotation = _early_bound(
            _early_bound(landing.note, "INote").GetAnnotation(), "IAnnotation"
        )
        anchor = tuple(float(value) for value in (annotation.GetPosition() or ()))
        points = tuple(
            float(value) for value in (annotation.GetLeaderPointsAtIndex(0) or ())
        )
        if len(anchor) < 2 or len(points) < 6:
            raise RuntimeError(f"{label}: {landing.instance} balloon is unreadable")
        annotations.append(annotation)
        centres.append((x, y))
        offsets.append((anchor[0] - x, anchor[1] - y))
        attachments.append((points[-3], points[-2]))
    slots = uncrossed_ring_slots(centres, attachments)
    moved = [index for index, slot in enumerate(slots) if slot != index]
    for index in moved:
        x, y = centres[slots[index]]
        if not annotations[index].SetPosition(
            x + offsets[index][0], y + offsets[index][1], 0.0
        ):
            raise RuntimeError(
                f"{label}: failed to move {landings[index].instance} balloon"
            )
    if moved:
        _telemetry.info(
            f"{label}: swapped ring slots to uncross leaders: "
            + ", ".join(
                f"{landings[index].instance} -> {landings[slots[index]].instance}'s"
                for index in moved
            )
        )
        rebuild_drawing(adapter, label=f"{label} uncrossed")


def _place_exploded_sheet(adapter: Any) -> Callable[[], None]:
    """The exploded isometric, its BOM (with the bought items by inventory id)
    and one balloon per modelled component; returns the check that proves
    every balloon again after the last rebuild."""
    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = _place_named_view(
        adapter,
        spec.ISOMETRIC_VIEW,
        EXPLODED_ISO_CENTER,
        EXPLODED_SCALE,
        label="jig exploded",
    )
    set_high_quality_shaded_with_edges(adapter, exploded, label="jig exploded")
    # Configuration, then its own explode, then the BOM and balloons bind.
    configuration = apply_view_configuration(adapter, exploded, label="jig exploded")
    set_view_exploded_state(
        adapter,
        exploded,
        True,
        configuration=configuration,
        label="jig exploded",
    )
    _center_view_outline(adapter, exploded, EXPLODED_ISO_CENTER, label="jig exploded")
    _assert_view_on_sheet(
        exploded,
        margin=BALLOON_MARGIN,
        bounds=EXPLODED_REGION,
        label="jig exploded",
    )
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        label="jig",
    )
    items = _validate_bom(adapter, table)
    with _source_configuration_active(exploded, label="jig exploded"):
        landings = add_component_bom_balloons(
            adapter,
            exploded,
            items=items,
            anchors=BALLOON_ANCHORS,
            label="jig exploded-view BOM coverage",
            margin=BALLOON_MARGIN,
        )
        # The helper balloons one instance per family per pass; each second
        # instance takes its own pass.
        numbers = dict(items)
        landings += add_component_bom_balloons(
            adapter,
            exploded,
            items=tuple((stem, numbers[stem]) for stem in TWO_OFF),
            anchors=SECOND_INSTANCE_BALLOON_ANCHORS,
            label="jig second-instance balloons",
            margin=BALLOON_MARGIN,
        )
    _ring_balloons(adapter, exploded, landings, label="jig exploded balloons")
    if len(landings) != sum(BOM_QUANTITIES.values()):
        raise RuntimeError(
            f"jig exploded view carries {len(landings)} balloons, "
            f"expected one per component ({sum(BOM_QUANTITIES.values())})"
        )
    _add_note_block(
        adapter,
        SHEET_NAMES[1],
        EXPLODED_CAPTION,
        EXPLODED_CAPTION_XY,
        label="exploded-view caption",
    )
    return lambda: assert_balloon_landings(adapter, landings)


def _place_steps_sheet(adapter: Any) -> None:
    """The finished assembly in full detail beside the order and checks."""
    _activate_sheet(adapter, SHEET_NAMES[2])
    finished = _place_named_view(
        adapter,
        spec.ISOMETRIC_VIEW,
        ASSEMBLY_ISO_CENTER,
        ISOMETRIC_SCALE,
        label="jig finished",
    )
    set_high_quality_shaded_with_edges(adapter, finished, label="jig finished")
    configuration = apply_view_configuration(
        adapter, finished, role=ViewRole.FULL_DETAIL, label="jig finished"
    )
    set_view_exploded_state(
        adapter,
        finished,
        False,
        configuration=configuration,
        label="jig finished",
    )
    _assert_view_on_sheet(finished, label="jig finished")
    assert_full_detail_view(adapter, label="jig assembly")
    _add_note_block(
        adapter, SHEET_NAMES[2], ASSEMBLY_STEPS, STEPS_XY, label="assembly sequence"
    )
    _add_note_block(
        adapter, SHEET_NAMES[2], ASSEMBLY_CHECKS, CHECKS_XY, label="assembly checks"
    )


def _activate_package(adapter: Any, target: Any) -> None:
    title = str(target.GetTitle() or "")
    if not title:
        raise RuntimeError("jig package drawing has no title")
    activation = adapter.swApp.ActivateDoc3(title, False, 2, 0)
    if not activation:
        raise RuntimeError("failed to reactivate jig package")
    activated, errors = activation
    if int(errors) != 0:
        raise RuntimeError(f"failed to reactivate jig package: {errors}")
    if activated is None:
        activated = adapter.swApp.ActiveDoc
    if activated is None or int(adapter.swApp.IsSame(activated, target)) != 1:
        raise RuntimeError("reactivated document is not the jig package")
    adapter.currentModel = _early_bound(activated, "IModelDoc2")


def _append_template_sheet(adapter: Any, target: Any, *, name: str) -> None:
    """Copy a real project-template sheet, closing its donor even on failure."""
    donor_title = ""
    try:
        donor, donor_sheet = new_project_drawing(
            adapter, layout=SHEET_LAYOUTS[name], scale=SHEET_SCALES[name]
        )
        donor = _early_bound(donor, "IModelDoc2")
        donor_sheet = _early_bound(donor_sheet, "ISheet")
        donor_title = str(donor.GetTitle() or "")
        donor_name = str(donor_sheet.GetName() or "")
        if not donor_title or not donor_name:
            raise RuntimeError(f"{name}: donor drawing is incomplete")
        donor.ClearSelection2(True)
        if not donor.Extension.SelectByID2(
            donor_name, "SHEET", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        ):
            raise RuntimeError(f"{name}: failed to select donor sheet")
        donor.EditCopy()
        _activate_package(adapter, target)
        ddoc = _early_bound(target, "IDrawingDoc")
        before = tuple(ddoc.GetSheetNames() or ())
        returned = bool(ddoc.PasteSheet(2, 2))  # append; preserve view names
        after = tuple(ddoc.GetSheetNames() or ())
        added = tuple(sheet for sheet in after if sheet not in before)
        if len(after) != len(before) + 1 or len(added) != 1:
            raise RuntimeError(
                f"{name}: sheet paste failed ({returned=}, {before=}, {after=})"
            )
        if not returned:
            _telemetry.warn(
                f"{name}: PasteSheet returned false but created {added[0]!r}"
            )
        if not ddoc.ActivateSheet(added[0]):
            raise RuntimeError(f"{name}: failed to activate pasted sheet")
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        sheet.SetName(name)
        if str(sheet.GetName() or "") != name:
            raise RuntimeError(f"{name}: failed to rename pasted sheet")
    finally:
        primary_error = sys.exception()
        if donor_title:
            try:
                adapter.swApp.CloseDoc(donor_title)
                _activate_package(adapter, target)
            except Exception as exc:
                if primary_error is None:
                    raise
                _telemetry.warn(f"{name}: donor cleanup failed: {exc}")


def _create_package_sheets(adapter: Any) -> None:
    """The primary sheet, then native template copies for the other two."""
    target, initial = new_project_drawing(
        adapter,
        layout=SHEET_LAYOUTS[SHEET_NAMES[0]],
        scale=SHEET_SCALES[SHEET_NAMES[0]],
    )
    target = _early_bound(target, "IModelDoc2")
    initial = _early_bound(initial, "ISheet")
    initial.SetName(SHEET_NAMES[0])
    if str(initial.GetName() or "") != SHEET_NAMES[0]:
        raise RuntimeError("failed to name the jig's primary sheet")
    for name in SHEET_NAMES[1:]:
        _append_template_sheet(adapter, target, name=name)
    actual = tuple(_early_bound(target, "IDrawingDoc").GetSheetNames() or ())
    if actual != SHEET_NAMES:
        raise RuntimeError(f"jig sheet order mismatch: {actual!r}")


def _place_package(adapter: Any) -> Callable[[], None]:
    _create_package_sheets(adapter)
    for sheet_name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, sheet_name)
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(f"failed to set jig sheet scale: {sheet_name}")
    _place_assembled_sheet(adapter)
    exploded_settled = _place_exploded_sheet(adapter)
    _place_steps_sheet(adapter)
    return exploded_settled


@_telemetry.traced("drawing.ch_rocker_arm_tl_oblique_jig_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open jig drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    properties = read_required_properties(
        source_model,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    if properties["Number"] != spec.DRAWING_NUMBER:
        raise RuntimeError(
            f"jig source Number {properties['Number']!r} != {spec.DRAWING_NUMBER!r}"
        )
    _validate_source(source_model)

    settled = _place_package(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Rocker Oblique Trammel Jig Assembly Drawing Package",
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts=SHEET_LAYOUTS,
        sheet_scales=SHEET_SCALES,
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
