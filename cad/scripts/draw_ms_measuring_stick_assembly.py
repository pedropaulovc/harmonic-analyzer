r"""Create the three-sheet measuring-stick fitter package (MHA-MS-000).

Sheet 1 shows the stick clamped at its stop mark (front and top at full size)
with the overall and stop-position REFERENCE dimensions, a section through
the thumbscrew axis, and the clamp and finish notes; sheet 2 the
builder-owned ``MS_EXPLODED`` presentation with the BOM (numbers, material,
vendor SKU, quantity) and a balloon on every component, both plate screws
included; sheet 3 the finished isometric beside the assembly order and
checks. Every text, pose and reference value comes from
``ms_measuring_stick_assembly_spec`` or the part registry; this recipe only
lays the sheets out. It never edits the source assembly or its explodes.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable

import _config
import _telemetry
import ms_measuring_stick_assembly_spec as spec
from _common import _early_bound, check, run_build
from _drawing_common import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    BalloonAnchor,
    DrawingOutputs,
    ViewRole,
    add_component_bom_balloons,
    add_edge_dimension,
    apply_view_configuration,
    assert_balloon_landings,
    assert_full_detail_view,
    create_blank_drawing_sheets,
    create_section_view,
    finalize_drawing,
    insert_bom_table,
    model_point_in_view,
    model_points_in_view,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_high_quality_shaded_with_edges,
    set_reference_dimension,
    set_view_exploded_state,
)
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _drawing_simplified import simplified_name
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["ms_measuring_stick_assembly"]
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
    "ASSEMBLED + CLAMPED SETUP",
    "EXPLODED VIEW + BOM",
    "ASSEMBLY STEPS",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the measuring-stick package is drawn on landscape sheets")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALE = (1.0, 1.0)
SHEET_SCALES = {name: SHEET_SCALE for name in SHEET_NAMES}

# Sheet geometry, metres: the template's inner border and the title block in
# its lower-right corner. Every view outline and balloon ring stays inside the
# border and out of the title block (drawing-simplicity rule 8).
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
SHEET_INNER_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (
    _TEMPLATE.title_block_left_m,
    0.0,
    _TEMPLATE.width_m,
    _TEMPLATE.title_block_top_m,
)

# Sheet 1: the 200-long stick at full size, top view above the front
# (third-angle), and the clamp section beside them, magnified so the window,
# roof and thumbscrew tip read. The two reference dimensions run in the gap
# between front and top, the clamp and finish notes below the front.
FRONT_CENTER = (0.135, 0.190)
TOP_CENTER = (0.135, 0.248)
CLAMP_SECTION_CENTER = (0.340, 0.165)
CLAMP_SECTION_SCALE = (4.0, 1.0)
CLAMP_SECTION_LABEL = "A"
STOP_POSITION_TEXT_Y = 0.214
OVERALL_LENGTH_TEXT_Y = 0.227
SETUP_NOTE_XY = (0.030, 0.160)
FINISH_NOTE_XY = (0.030, 0.118)
SETUP_NOTE_WIDTH = 52  # characters; default-format note text

# Sheet 2: the BOM across the top-left; the exploded isometric below-right
# of it. Balloons ring the view at BALLOON_MARGIN; the second plate screw's
# balloon rides an outer ring so both screw instances carry one.
EXPLODED_ISO_CENTER = (0.300, 0.145)
BALLOON_MARGIN = 0.012
SECOND_SCREW_BALLOON_MARGIN = 0.024
BOM_ANCHOR = (0.018, 0.258)
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.026,
    "description": 0.080,
    "material": 0.058,
    "sku": 0.024,
    "quantity": 0.012,
}
BOM_MATERIAL_TITLE = "MATERIAL"
BOM_SKU_TITLE = "VENDOR SKU"
MADE_PART_SKU = "-"
BOM_ROW_HEIGHT = 0.006
EXPLODED_CAPTION = "EXPLODED - ASSEMBLE IN REVERSE ORDER, SEE SHEET 3"
EXPLODED_CAPTION_XY = (0.018, 0.205)

# Sheet 3: the order and checks down the left; the finished isometric right.
ASSEMBLY_ISO_CENTER = (0.315, 0.170)
STEPS_XY = (0.018, 0.258)
CHECKS_XY = (0.018, 0.140)
STEPS_LINE_WIDTH = 58  # characters; default-format note text

BOM_QUANTITIES = {stem: spec.QUANTITIES[stem] for stem in spec.BOM_ORDER}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "ms-stick": _config.parts("ms-stick"),
    "ms-stop-block": _config.parts("ms-stop-block"),
    "ms-stop-plate": _config.parts("ms-stop-plate"),
    "vn-ms-stop-plate-screw": _config.parts("vn-ms-stop-plate-screw"),
    "vn-thumb-screw": _config.parts("vn-thumb-screw"),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the assembly families")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
# The registry owns material and vendor SKU; the BOM prints them verbatim.
BOM_MATERIALS = {stem: str(row["material"]).upper() for stem, row in PART_ROWS.items()}
BOM_SKUS = {
    stem: " / ".join(str(sku) for sku in row.get("supplier_skus") or ()) or MADE_PART_SKU
    for stem, row in PART_ROWS.items()
}
BOM_DESCRIPTIONS = dict(spec.BOM_DESCRIPTIONS)
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}
# Each balloon walks its own part's body for a visible edge on the exploded
# view: every family is a single, separated body there. The plate screws are
# two instances, so each is pinned: the first rides the family ring, the
# second its own outer pass (one balloon per component on the sheet).
PLATE_SCREW_INSTANCES = tuple(
    f"{spec.PLATE_SCREW}-{index}"
    for index in range(1, spec.QUANTITIES[spec.PLATE_SCREW] + 1)
)
if len(PLATE_SCREW_INSTANCES) != 2:
    raise AssertionError("the cover plate takes exactly two screws")
BALLOON_ANCHORS = {
    stem: BalloonAnchor(instance=PLATE_SCREW_INSTANCES[0])
    if stem == spec.PLATE_SCREW
    else BalloonAnchor()
    for stem in BOM_COMPONENTS
}
SECOND_SCREW_BALLOON_ANCHORS = {
    spec.PLATE_SCREW: BalloonAnchor(instance=PLATE_SCREW_INSTANCES[1])
}

# Finish, from the registry rows: the pair is finished together after it is
# match-drilled (step 1), so a fitter never mixes covers between stops.
_BLOCK_FINISH = str(PART_ROWS[spec.BLOCK]["finish"]).upper()
if str(PART_ROWS[spec.PLATE]["finish"]).upper() != _BLOCK_FINISH:
    raise AssertionError("the stop block and its cover plate share one finish")
FINISH_NOTE_TEXT = (
    f"FINISH - {spec.BOM_DESCRIPTIONS[spec.BLOCK]} AND "
    f"{spec.BOM_DESCRIPTIONS[spec.PLATE]}: {_BLOCK_FINISH}, FINISHED TOGETHER "
    f"AS ONE PAIR AFTER STEP 1. {spec.BOM_DESCRIPTIONS[spec.STICK]}: "
    f"{str(PART_ROWS[spec.STICK]['finish']).upper()}. SCREWS: AS PURCHASED."
)

# Reference dimensions on the front view: (label, expected mm, callout below).
REFERENCE_DIMENSIONS = (
    ("overall length", spec.REFERENCE_OVERALL_LENGTH, ""),
    ("stop position", spec.REFERENCE_STOP_FACE, spec.STOP_POSITION_CALLOUT),
)

EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: spec.EXPLODED_VIEW_NAME,
    SIMPLIFIED_VIEW_CONFIGURATION: simplified_name(spec.EXPLODED_VIEW_NAME),
}
if spec.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the measuring-stick explode is authored in Default")


def _wrapped(lines: tuple[str, ...], *, width: int, heading: str | None = None) -> str:
    """Wrap each numbered line under its own number; one note per block."""
    out = [heading] if heading else []
    for line in lines:
        number, sep, rest = line.partition(". ")
        if sep and number.isdigit():
            out += textwrap.wrap(
                rest,
                width=width,
                initial_indent=f"{number}. ",
                subsequent_indent=" " * (len(number) + 2),
            )
        else:
            out += textwrap.wrap(line, width=width, subsequent_indent="   ")
    return "\n".join(out)


SETUP_NOTE = _wrapped((spec.CLAMPED_SETUP_NOTE,), width=SETUP_NOTE_WIDTH)
FINISH_NOTE = _wrapped((FINISH_NOTE_TEXT,), width=SETUP_NOTE_WIDTH)
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
        raise RuntimeError(f"failed to place the measuring-stick {label}")
    note = _early_bound(note, "INote")
    printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if printed != text:
        raise RuntimeError(f"measuring-stick {label} printed as {printed!r}")
    return note


def _view_outline(view: Any, *, label: str) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"{label}: invalid view outline {outline!r}")
    return outline[0], outline[1], outline[2], outline[3]


def _assert_view_on_sheet(view: Any, *, margin: float = 0.0, label: str) -> None:
    """The view's outline, grown by ``margin`` (a balloon ring), stays inside
    the inner border and clear of the title block."""
    x0, y0, x1, y1 = _view_outline(view, label=label)
    x0, y0, x1, y1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
    left, bottom, right, top = SHEET_INNER_BORDER
    findings = []
    if x0 < left or y0 < bottom or x1 > right or y1 > top:
        findings.append(f"leaves the inner border {SHEET_INNER_BORDER}")
    tx0, ty0, tx1, ty1 = TITLE_BLOCK
    if x1 > tx0 and x0 < tx1 and y0 < ty1 and y1 > ty0:
        findings.append(f"enters the title block {TITLE_BLOCK}")
    if findings:
        raise RuntimeError(
            f"{label}: outline {(x0, y0, x1, y1)!r} " + "; ".join(findings)
        )


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
        raise RuntimeError("measuring-stick source must open in its Default configuration")
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(
                f"measuring-stick {owner} exploded views {names!r} != {(wanted,)!r}"
            )
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
                f"measuring-stick source must open collapsed: {component.Name2!r} "
                "is displaced"
            )
    if counts != BOM_QUANTITIES:
        raise RuntimeError(
            f"measuring-stick families {counts!r} != contract {BOM_QUANTITIES!r}"
        )


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
        raise RuntimeError(f"measuring-stick BOM has no unique {label} column: {header!r}")
    return matches[0]


def _validate_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    """Rewrite part numbers, prove identities/descriptions/quantities, add the
    registry's MATERIAL and VENDOR SKU columns after DESCRIPTION; return
    (stem, item number) in BOM order."""
    table = _early_bound(table, "ITableAnnotation")
    contents = _bom_cells(table)
    rows = len(contents)
    columns = len(contents[0]) if contents else 0
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"measuring-stick BOM is {rows}x{columns}; expected "
            f"{len(BOM_COMPONENTS) + 1} rows and at least four columns"
        )
    header = contents[0]
    for title in (BOM_MATERIAL_TITLE, BOM_SKU_TITLE):
        if title in (cell.upper() for cell in header):
            raise RuntimeError(f"measuring-stick BOM template already has {title!r}")
    item_column = _bom_column(header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
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
            raise RuntimeError(f"measuring-stick BOM repeats component family {stem!r}")
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"measuring-stick BOM identities {sorted(actual)!r} != "
            f"{sorted(BOM_COMPONENTS)!r}"
        )
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(BOM_COMPONENTS) + 1)}:
        raise RuntimeError(
            f"measuring-stick BOM item numbers {sorted(items)!r} are not contiguous"
        )
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(
                    f"measuring-stick BOM part-number cell for {stem!r} is locked"
                )
            table.SetText2(row_index, part_column, False, number)
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"measuring-stick BOM description mismatch for {stem!r}")
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"measuring-stick BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )

    # User-defined columns, written row by row from the registry: the parts
    # carry no SKU property, and the made parts print MADE_PART_SKU.
    for offset, (title, values) in enumerate(
        ((BOM_MATERIAL_TITLE, BOM_MATERIALS), (BOM_SKU_TITLE, BOM_SKUS))
    ):
        after = description_column + offset
        if not table.InsertColumn2(
            _INSERT_COLUMN_AFTER, after, title, _INSERT_COLUMN_DEFAULT_WIDTH
        ):
            raise RuntimeError(f"measuring-stick BOM refused the {title} column")
        column = after + 1
        if not table.SetColumnTitle2(column, title, False):
            raise RuntimeError(f"measuring-stick BOM {title} column title did not set")
        for stem, (row_index, *_rest) in actual.items():
            if not table.IsCellTextEditable(row_index, column):
                raise RuntimeError(
                    f"measuring-stick BOM {title} cell for {stem!r} is locked"
                )
            table.SetText2(row_index, column, False, values[stem])

    header = _bom_cells(table)[0]
    widths = {
        "item": _bom_column(header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."),
        "part": _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER"),
        "description": _bom_column(
            header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
        ),
        "material": _bom_column(
            header, lambda cell: cell == BOM_MATERIAL_TITLE, BOM_MATERIAL_TITLE
        ),
        "sku": _bom_column(header, lambda cell: cell == BOM_SKU_TITLE, BOM_SKU_TITLE),
        "quantity": _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY."),
    }
    if len(header) != len(BOM_COLUMN_WIDTHS) or set(widths) != set(BOM_COLUMN_WIDTHS):
        raise RuntimeError(f"measuring-stick BOM columns {header!r} are not the contract")
    for key, column in widths.items():
        width = BOM_COLUMN_WIDTHS[key]
        if abs(float(table.SetColumnWidth(column, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"measuring-stick BOM {key} column width did not persist")
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("measuring-stick BOM rebuild failed")
    settled = _bom_cells(table)
    for stem, (row_index, *_rest) in actual.items():
        expected = {
            "part": BOM_PART_NUMBERS[stem],
            "material": BOM_MATERIALS[stem],
            "sku": BOM_SKUS[stem],
        }
        for key, text in expected.items():
            applied = settled[row_index][widths[key]]
            if applied != text:
                raise RuntimeError(
                    f"measuring-stick BOM {key} for {stem!r} reads {applied!r}, "
                    f"expected {text!r}"
                )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _assert_dimension_ink_on_sheet(display: Any, *, label: str) -> None:
    """A dimension's native line ink (witness, dimension line, arrows) stays
    inside the inner border and out of the title block: an outside dimension
    can land its text on either side of the requested anchor."""
    display = _early_bound(display, "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    points = []
    for index in range(int(data.GetLineCount())):
        line = tuple(float(value) for value in data.GetLineAtIndex2(index))
        if len(line) < 10:
            raise RuntimeError(f"{label}: incomplete native dimension line")
        points.extend(((line[4], line[5]), (line[7], line[8])))
    if not points or int(data.GetTextCount()) < 1:
        raise RuntimeError(f"{label}: missing native dimension display data")
    x0 = min(point[0] for point in points)
    y0 = min(point[1] for point in points)
    x1 = max(point[0] for point in points)
    y1 = max(point[1] for point in points)
    left, bottom, right, top = SHEET_INNER_BORDER
    tx0, ty0, tx1, ty1 = TITLE_BLOCK
    if (
        x0 < left
        or y0 < bottom
        or x1 > right
        or y1 > top
        or (x1 > tx0 and x0 < tx1 and y0 < ty1 and y1 > ty0)
    ):
        raise RuntimeError(
            f"{label}: dimension ink {(x0, y0, x1, y1)!r} leaves the drawable sheet"
        )


def _add_reference_dimensions(adapter: Any, front: Any) -> None:
    """Overall length and the stop position as parenthesized REFERENCE
    dimensions across the front view's edges: both stick ends, and the
    stop's near (X=0) face. Each measured value is proved against the spec
    before it is bracketed; the places come from the spec too."""
    # Mid-height on each stick end; below the window floor on the block's
    # near end edge, clear of the stick. Front views drop Z.
    stick_mid_y = (spec.STICK_TOP_Y + spec.STICK_BOTTOM_Y) / 2.0
    names = ("stick scale-start end", "stick far end", "stop near face")
    stick_start, stick_end, stop_face = model_points_in_view(
        adapter,
        front,
        [
            (spec.STICK_X_MIN / 1000.0, stick_mid_y / 1000.0, 0.0),
            (spec.STICK_X_MAX / 1000.0, stick_mid_y / 1000.0, 0.0),
            (spec.BLOCK_ORIGIN[0] / 1000.0, spec.STICK_BOTTOM_Y / 2.0 / 1000.0, 0.0),
        ],
        label="measuring-stick reference-dimension picks",
        names=names,
    )
    picks = {
        "overall length": (
            stick_start,
            stick_end,
            ((stick_start[0] + stick_end[0]) / 2.0, OVERALL_LENGTH_TEXT_Y),
        ),
        "stop position": (
            stick_start,
            stop_face,
            ((stick_start[0] + stop_face[0]) / 2.0, STOP_POSITION_TEXT_Y),
        ),
    }
    for label, expected_mm, callout in REFERENCE_DIMENSIONS:
        p0, p1, text_xy = picks[label]
        display = _early_bound(
            add_edge_dimension(
                adapter,
                front,
                p0=p0,
                p1=p1,
                text_xy=text_xy,
                label=f"measuring-stick {label} reference",
                orientation="horizontal",
            ),
            "IDisplayDimension",
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        measured_mm = abs(float(dimension.SystemValue) * 1000.0)
        if abs(measured_mm - expected_mm) > 1e-4:
            raise RuntimeError(
                f"measuring-stick {label} measured {measured_mm:g}, "
                f"expected {expected_mm:g} mm"
            )
        display = _early_bound(
            set_reference_dimension(
                adapter, display.GetAnnotation(), label=f"measuring-stick {label}"
            ),
            "IDisplayDimension",
        )
        display.SetPrecision3(spec.DRAWING_REFERENCE_PRECISION, -1, -1, -1)
        if int(display.GetPrimaryPrecision2()) != spec.DRAWING_REFERENCE_PRECISION:
            raise RuntimeError(f"measuring-stick {label} precision did not persist")
        if callout:
            display.SetText(4, callout)  # swDimensionTextCalloutBelow
            if str(display.GetText(4) or "") != callout:
                raise RuntimeError(f"measuring-stick {label} callout did not persist")
        _assert_dimension_ink_on_sheet(display, label=f"measuring-stick {label}")


def _place_clamped_sheet(adapter: Any) -> None:
    """Front and top at full size with the overall and stop-position
    references, section A-A through the thumbscrew axis (the stick against
    the roof, the tip on its underside), and the clamp and finish notes."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    for view, label in ((front, "clamped front"), (top, "clamped top")):
        set_hidden_lines_removed(adapter, view)
        apply_view_configuration(adapter, view, label=label)
        _assert_view_on_sheet(view, label=label)

    _left, y0, _right, y1 = _view_outline(front, label="clamped front")
    station_x = model_point_in_view(
        adapter,
        front,
        (spec.THUMB_ORIGIN[0] / 1000.0, 0.0, 0.0),
        label="thumbscrew-axis cutting-plane station",
    )[0]
    section = create_section_view(
        adapter,
        front,
        line_start=(station_x, y1 + 0.004),
        line_end=(station_x, y0 - 0.004),
        view_xy=CLAMP_SECTION_CENTER,
        section_label=CLAMP_SECTION_LABEL,
        scale=CLAMP_SECTION_SCALE,
        label="thumbscrew clamp section",
    )
    set_hidden_lines_removed(adapter, section)
    apply_view_configuration(adapter, section, label="thumbscrew clamp section")
    _assert_view_on_sheet(section, label="thumbscrew clamp section")
    _add_reference_dimensions(adapter, front)
    _add_note_block(
        adapter, SHEET_NAMES[0], SETUP_NOTE, SETUP_NOTE_XY, label="clamped-setup note"
    )
    _add_note_block(
        adapter, SHEET_NAMES[0], FINISH_NOTE, FINISH_NOTE_XY, label="finish note"
    )


def _place_exploded_sheet(adapter: Any) -> Callable[[], None]:
    """The exploded isometric, its BOM (with material and vendor SKU) and one
    balloon per component -- both plate screws included; returns the check
    that proves every balloon again after the last rebuild."""
    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter, str(SOURCE), "*Isometric", *EXPLODED_ISO_CENTER, scale=SHEET_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, exploded, label="measuring-stick exploded")
    # Configuration, then its own explode, then the BOM and balloons bind.
    configuration = apply_view_configuration(
        adapter, exploded, label="measuring-stick exploded"
    )
    set_view_exploded_state(
        adapter,
        exploded,
        True,
        configuration=configuration,
        label="measuring-stick exploded",
    )
    _assert_view_on_sheet(
        exploded, margin=SECOND_SCREW_BALLOON_MARGIN, label="measuring-stick exploded"
    )
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="measuring-stick",
    )
    items = _validate_bom(adapter, table)
    landings = add_component_bom_balloons(
        adapter,
        exploded,
        items=items,
        anchors=BALLOON_ANCHORS,
        label="measuring-stick exploded-view BOM coverage",
        margin=BALLOON_MARGIN,
    )
    # The helper rings one balloon per family per pass; the second screw
    # instance takes its own pass, a ring further out, so its balloon sits
    # radially beyond the first ring rather than among it.
    screw_item = dict(items)[spec.PLATE_SCREW]
    landings += add_component_bom_balloons(
        adapter,
        exploded,
        items=((spec.PLATE_SCREW, screw_item),),
        anchors=SECOND_SCREW_BALLOON_ANCHORS,
        label="measuring-stick second plate-screw balloon",
        margin=SECOND_SCREW_BALLOON_MARGIN,
    )
    if len(landings) != sum(BOM_QUANTITIES.values()):
        raise RuntimeError(
            f"measuring-stick exploded view carries {len(landings)} balloons, "
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
    finished = place_view(
        adapter, str(SOURCE), "*Isometric", *ASSEMBLY_ISO_CENTER, scale=SHEET_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, finished, label="measuring-stick finished")
    configuration = apply_view_configuration(
        adapter, finished, role=ViewRole.FULL_DETAIL, label="measuring-stick finished"
    )
    set_view_exploded_state(
        adapter,
        finished,
        False,
        configuration=configuration,
        label="measuring-stick finished",
    )
    _assert_view_on_sheet(finished, label="measuring-stick finished")
    assert_full_detail_view(adapter, label="measuring-stick assembly")
    _add_note_block(
        adapter, SHEET_NAMES[2], ASSEMBLY_STEPS, STEPS_XY, label="assembly sequence"
    )
    _add_note_block(
        adapter, SHEET_NAMES[2], ASSEMBLY_CHECKS, CHECKS_XY, label="assembly checks"
    )


def _place_package(adapter: Any) -> Callable[[], None]:
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="measuring-stick package")
    for sheet_name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, sheet_name)
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(f"failed to set measuring-stick sheet scale: {sheet_name}")
    _place_clamped_sheet(adapter)
    settled = _place_exploded_sheet(adapter)
    _place_steps_sheet(adapter)
    return settled


@_telemetry.traced("drawing.ms_measuring_stick_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open measuring-stick drawing source", await adapter.open_model(str(SOURCE)))
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
            f"measuring-stick source Number {properties['Number']!r} != "
            f"{spec.DRAWING_NUMBER!r}"
        )
    _validate_source(source_model)

    new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE)
    settled = _place_package(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Measuring Stick Assembly Drawing Package",
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
