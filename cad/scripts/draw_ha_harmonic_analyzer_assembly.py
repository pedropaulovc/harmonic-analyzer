r"""Create the five-sheet complete-machine fitter package (MHA-HA-00).

Sheet 1 shows the assembled machine (front and crank-side views at 1:5) with
the two settings only the complete machine makes, imported as the builder's
driving dimensions; sheet 2 the finished machine in full detail; sheet 3 the
builder-owned ``HA_EXPLODED`` presentation with the top-level BOM (one row per
subassembly) and a balloon on every row; sheet 4 the integration sequence;
sheet 5 the checks before running. Every pose and setting comes from
``ha_harmonic_analyzer_assembly_spec``, every printed text from
``ha_harmonic_analyzer_assembly_sheet``; this recipe only lays the sheets out.
It never edits the source assembly or its explodes.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable

import _telemetry
import ha_harmonic_analyzer_assembly_sheet as notes
import ha_harmonic_analyzer_assembly_spec as spec
from _assembly_contract import assembly_contract
from _check import check
from _com import _early_bound
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_high_quality_shaded_with_edges,
)
from _drawing_balloons import (
    BalloonAnchor,
    _explode_offset,
    _view_explode_offsets,
    add_component_bom_balloons,
    assert_balloon_landings,
)
from _drawing_centerline import add_view_centerline
from _drawing_dimension_import import curate_view_dimensions
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view, model_points_in_view
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
from _machinist_review_mode import MachinistReviewMode
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _drawing_hidden_sketches import _show_base_view_sketches
from _simplified_names import SIMPLIFIED_SUFFIX, simplified_name
from fr_frame_attachment_spec import TOP_SCREW_Y
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["ha_harmonic_analyzer_assembly"]
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
    "ASSEMBLED",
    "FINISHED MACHINE",
    "EXPLODED VIEW + BOM",
    "INTEGRATION STEPS",
    "CHECKS BEFORE RUNNING",
)
if SPEC.layout is not DrawingLayout.PORTRAIT:
    raise AssertionError("the complete-machine primary sheet must stay portrait")
SHEET_LAYOUTS = dict(
    zip(
        SHEET_NAMES,
        (
            DrawingLayout.PORTRAIT,
            DrawingLayout.PORTRAIT,
            DrawingLayout.PORTRAIT,
            DrawingLayout.LANDSCAPE,
            DrawingLayout.LANDSCAPE,
        ),
    )
)
# The machine is 1360 tall: 1:5 holds it on a portrait sheet at a scale the
# fitter can read. The explode's isometric outline (SolidWorks' projected
# model box, about twice the ink) is 2.41 x 2.94 m (r5 audit: 161 x 196 mm at
# 1:15, the ink only ~82 x 125 mm, leaving most of the sheet empty). 1:12
# keeps that outline (201 x 245 mm) inside the border and between the BOM and
# the title block, the ink ~1.25x larger. The steps and checks sheets'
# orientation view is a thumbnail beside the text.
ASSEMBLED_SCALE = (1.0, 5.0)
EXPLODED_SCALE = (1.0, 12.0)
STEPS_VIEW_SCALE = (1.0, 20.0)
SHEET_SCALES = dict(
    zip(
        SHEET_NAMES,
        (
            ASSEMBLED_SCALE,
            ASSEMBLED_SCALE,
            EXPLODED_SCALE,
            STEPS_VIEW_SCALE,
            STEPS_VIEW_SCALE,
        ),
    )
)

_LINEAR_DIMENSION = 2  # swLinearDimension
_VERTICAL_LINEAR_DIMENSION = 12  # swVerLinearDimension
_CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

# Sheet geometry, metres (drawing-guidelines.md rule 13: views and their
# balloon rings stay inside the inner border and out of the title block).
_BORDER = 0.0127
_PORTRAIT = DRAWING_TEMPLATES[DrawingLayout.PORTRAIT]
_LANDSCAPE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
_PORTRAIT_USABLE_Y = (_PORTRAIT.title_block_top_m, _PORTRAIT.height_m - _BORDER)

# Sheet 1: front (paper side) and the crank-side view to its right, one row,
# the front's left edge set in far enough for the bar-height dimension and its
# callout, which stand wholly west of the front view's ink (r3: at 0.040 the
# callout crossed the left border by 9 mm and ran into the west column; the
# outline carries ~7 mm of padding west of the ink). The crank-side outline
# then ends ~7 mm inside the right border. The note sits under the views,
# above the title block.
ASSEMBLED_ROW_Y = 0.252
FRONT_LEFT_X = 0.052
VIEW_GAP_X = 0.015
BAR_DIMENSION_TEXT_DX = -0.016  # left of the front view's outline
# The stud-drop text stands outside the east column (viewer's right), in the
# strip between the front view's ink and the crank-side view, the extension
# lines carried across the column to it (r3: beside the rod it sat across the
# rod and the wheel rim; r4: inside the frame, pressed against the pen
# hanger). Model x of the text centre: the east column's outer face is at
# x = -(197 + 12.7) (fr_top_frame_spec.COLUMN_X, fr_tube_frame_spec.OUTER_DIA;
# pinned by the test); the 7-character callout is ~80 mm of model wide at 1:5,
# so its west end clears the column by ~15 mm of model (3 mm of sheet) and its
# east end stays ~10 mm of sheet short of the crank-side view's crank handle.
STUD_DIMENSION_TEXT_MODEL_X_MM = -265.0
# The bar-height setting's construction line lies on the west front column's
# axis (ha_harmonic_analyzer_assembly_spec.BAR_HEIGHT_X), shown in the front
# view for its dimension to import (_drawing_hidden_sketches, r21). The
# column's own centreline makes that chain read as the axis it lies on (the
# mg-magnifier precedent, 1d6de0958). Picked on the axis halfway between the
# bar top and the top-frame screw: clear of the bar clamp, the top frame and
# the chain itself, which stops at the bar top. Metres; the front view
# projects along z, so z is immaterial.
BAR_COLUMN_PICK_M = (
    spec.BAR_HEIGHT_X / 1000.0,
    (spec.WHEEL_BAR_TOP_Y + TOP_SCREW_Y) / 2000.0,
    0.0,
)
ASSEMBLED_NOTE_XY = (0.020, 0.100)
ASSEMBLED_NOTE_WIDTH = 84  # characters; default-format note text

# Sheet 2: the finished machine, full detail, centred in the usable area.
FINISHED_CENTER = (_PORTRAIT.width_m / 2.0, sum(_PORTRAIT_USABLE_Y) / 2.0)

# Sheet 3: BOM over the exploded isometric, both centred.
BALLOON_MARGIN = 0.012
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.032,
    "description": 0.125,
    "quantity": 0.012,
}
# ~2.7 mm per BOM character (r3: 0.100 wrapped five of the eight rows)
BOM_DESCRIPTION_MAX_CHARS = 46
BOM_ROW_HEIGHT = 0.006
BOM_ANCHOR = ((_PORTRAIT.width_m - sum(BOM_COLUMN_WIDTHS.values())) / 2.0, 0.405)
EXPLODED_CAPTION_XY = (BOM_ANCHOR[0], 0.415)
_BOM_BOTTOM_Y = BOM_ANCHOR[1] - (len(spec.BOM_ORDER) + 1) * BOM_ROW_HEIGHT
EXPLODED_CENTER = (
    _PORTRAIT.width_m / 2.0,
    (_PORTRAIT.title_block_top_m + _BOM_BOTTOM_Y) / 2.0,
)
# The spare sprocket's label (notes.SPARE_SPROCKET_LABEL): its top-left
# corner this far from the leader tip, sheet metres. The spare lies ~4 mm
# west of item 7's leader (5bca52e13 sheet 3), so the three short lines stand
# below-left of it, in the open sheet between the item 6 and item 7 balloons
# and clear of that leader.
SPARE_LABEL_OFFSET = (-0.058, -0.004)
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
# The paper drive's authored explode (model metres): the spare rides it.
PAPER_DRIVE_EXPLODE_M = tuple(
    sum(
        step.distance_mm / 1000.0
        for step in spec.EXPLODE_STEPS
        if notes.PAPER_DRIVE in step.stems and _AXIS_INDEX[step.axis] == axis
    )
    for axis in range(3)
)

# Sheets 4 and 5 (landscape): text columns over the title block's height,
# the finished-machine thumbnail at the right. A blank line separates the
# numbered steps, so the sequence fills both sheet-4 columns and the checks
# move to sheet 5, level with its thumbnail rather than bunched in the top
# corner (machinist review rule 15 on 29a080cd4).
NOTE_LINE_PITCH = 0.00455  # measured default-format note line pitch
STEPS_LINE_WIDTH = 60  # characters; ~2.7 mm each
STEPS_TOP_Y = 0.262
STEPS_LEFT_X = 0.018
STEPS_RIGHT_X = 0.195
STEPS_SPLIT = 7  # steps 1..7 in the left column
STEPS_VIEW_CENTER = (0.390, 0.170)

BOM_COMPONENTS = spec.BOM_ORDER
BOM_PART_NUMBERS = {stem: assembly_contract(stem).number for stem in BOM_COMPONENTS}
BOM_DESCRIPTIONS = dict(notes.BOM_DESCRIPTIONS)
if max(len(text) for text in BOM_DESCRIPTIONS.values()) > BOM_DESCRIPTION_MAX_CHARS:
    raise AssertionError("a BOM description outgrows its column")
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}
BALLOON_ANCHORS = {part: BalloonAnchor() for part in notes.BALLOON_PARTS.values()}

EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: spec.EXPLODED_VIEW_NAME,
    SIMPLIFIED_VIEW_CONFIGURATION: simplified_name(spec.EXPLODED_VIEW_NAME),
}
if spec.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the complete-machine explode is authored in Default")


def _wrapped(lines: tuple[str, ...], *, width: int, heading: str | None = None) -> str:
    """Wrap each numbered line under its own number, a blank line between
    numbered lines; one note per block."""
    out = [heading] if heading else []
    numbered = False
    for line in lines:
        number, sep, rest = line.partition(". ")
        if sep and number.isdigit():
            if numbered:
                out.append("")
            numbered = True
            out += textwrap.wrap(
                rest,
                width=width,
                initial_indent=f"{number}. ",
                subsequent_indent=" " * (len(number) + 2),
            )
        else:
            out += textwrap.wrap(line, width=width, subsequent_indent="   ")
    return "\n".join(out)


ASSEMBLED_NOTE = _wrapped(
    (
        notes.ORIENTATION_NOTE,
        notes.NIB_PARKED_NOTE,
        f"INTEGRATION STEPS ON SHEET {SHEET_NAMES.index('INTEGRATION STEPS') + 1}.",
    ),
    width=ASSEMBLED_NOTE_WIDTH,
)
STEPS_LEFT = _wrapped(
    notes.ASSEMBLY_STEPS[:STEPS_SPLIT],
    width=STEPS_LINE_WIDTH,
    heading="INTEGRATION SEQUENCE",
)
STEPS_RIGHT = _wrapped(notes.ASSEMBLY_STEPS[STEPS_SPLIT:], width=STEPS_LINE_WIDTH)
ASSEMBLY_CHECKS = _wrapped(
    notes.ASSEMBLY_CHECKS, width=STEPS_LINE_WIDTH, heading="CHECKS BEFORE RUNNING"
)
_CHECKS_HEIGHT = (ASSEMBLY_CHECKS.count("\n") + 1) * NOTE_LINE_PITCH
CHECKS_XY = (STEPS_LEFT_X, STEPS_VIEW_CENTER[1] + _CHECKS_HEIGHT / 2.0)
STEPS_COLUMN_BOTTOM_Y = min(
    STEPS_TOP_Y
    - NOTE_LINE_PITCH
    * max(block.count("\n") + 1 for block in (STEPS_LEFT, STEPS_RIGHT)),
    CHECKS_XY[1] - _CHECKS_HEIGHT,
)
if STEPS_COLUMN_BOTTOM_Y <= _LANDSCAPE.title_block_top_m or CHECKS_XY[1] > STEPS_TOP_Y:
    raise AssertionError("the steps sheets' text leaves its field")


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
        raise RuntimeError(f"failed to place the complete-machine {label}")
    note = _early_bound(note, "INote")
    printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if printed != text:
        raise RuntimeError(f"complete-machine {label} printed as {printed!r}")
    return note


def _view_outline(view: Any, *, label: str) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"{label}: invalid view outline {outline!r}")
    return outline[0], outline[1], outline[2], outline[3]


def _assert_view_on_sheet(
    view: Any, *, layout: DrawingLayout, label: str, margin: float = 0.0
) -> None:
    """The view's outline, grown by ``margin`` (a balloon ring), stays inside
    the inner border and clear of the title block."""
    x0, y0, x1, y1 = _view_outline(view, label=label)
    x0, y0, x1, y1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
    template = DRAWING_TEMPLATES[layout]
    border = (_BORDER, _BORDER, template.width_m - _BORDER, template.height_m - _BORDER)
    title = (
        template.title_block_left_m,
        0.0,
        template.width_m,
        template.title_block_top_m,
    )
    left, bottom, right, top = border
    findings = []
    if x0 < left or y0 < bottom or x1 > right or y1 > top:
        findings.append(f"leaves the inner border {border}")
    tx0, ty0, tx1, ty1 = title
    if x1 > tx0 and x0 < tx1 and y0 < ty1 and y1 > ty0:
        findings.append(f"enters the title block {title}")
    if findings:
        raise RuntimeError(
            f"{label}: outline {(x0, y0, x1, y1)!r} " + "; ".join(findings)
        )


def _move_view_outline(
    adapter: Any,
    view: Any,
    *,
    label: str,
    center_x: float | None = None,
    left_x: float | None = None,
    center_y: float,
) -> None:
    """Translate a view so its measured outline sits where asked: centred on
    ``center_y`` and either centred on ``center_x`` or starting at ``left_x``."""
    if (center_x is None) == (left_x is None):
        raise ValueError(f"{label}: give exactly one of center_x and left_x")
    view = _early_bound(view, "IView")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    dx = (center_x - (x0 + x1) / 2.0) if center_x is not None else (left_x - x0)
    dy = center_y - (y0 + y1) / 2.0
    before = tuple(float(value) for value in view.Position)
    target = (before[0] + dx, before[1] + dy)
    if not view.SetViewPosition(double_array(list(target)), False):
        raise RuntimeError(f"{label}: SetViewPosition refused {target!r}")
    adapter.currentModel.EditRebuild3()
    after = tuple(float(value) for value in view.Position)
    if len(after) != 2 or any(abs(a - b) > 1e-6 for a, b in zip(after, target)):
        raise RuntimeError(f"{label}: view moved to {after!r}, expected {target!r}")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    placed_x = (x0 + x1) / 2.0 if center_x is not None else x0
    wanted_x = center_x if center_x is not None else left_x
    if abs(placed_x - wanted_x) > 1e-6 or abs((y0 + y1) / 2.0 - center_y) > 1e-6:
        raise RuntimeError(f"{label}: measured outline did not land as asked")


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _spare_sprocket_tip(adapter: Any, view: Any) -> tuple[float, float]:
    """The sheet point on the paper drive's spare sprocket, exploded, that its
    label's leader ends on (notes.SPARE_SPROCKET_TIP_MM on its upper face).

    The spare is found in the view's referenced configuration's own tree as
    the one paper-drive removable in the spare configuration (its derived
    ``Simplified`` one in ``Default Simplified``), never by an
    allocator-numbered instance name; its collapsed pose comes from its
    native transform and its explode from the view's explode steps, which
    must equal the paper drive's authored one.
    """
    label = "spare sprocket label"
    bound = _early_bound(view, "IView")
    model = _early_bound(bound.ReferencedDocument, "IModelDoc2")
    configuration_name = str(bound.ReferencedConfiguration)
    configuration = model.GetConfigurationByName(configuration_name)
    if configuration is None:
        raise RuntimeError(f"{label}: no configuration {configuration_name!r}")
    root = _early_bound(configuration, "IConfiguration").GetRootComponent3(True)
    spares = []
    pending = list(root.GetChildren() or ()) if root is not None else []
    while pending:
        component = _early_bound(pending.pop(), "IComponent2")
        pending.extend(component.GetChildren() or ())
        # A pattern member or virtual part may carry no file path, so the
        # stem is read without _component_stem's refusal.
        if (
            Path(str(component.GetPathName() or "")).stem.casefold()
            == notes.SPARE_SPROCKET_STEM
            and str(component.ReferencedConfiguration or "").removesuffix(
                SIMPLIFIED_SUFFIX
            )
            == notes.SPARE_SPROCKET_CONFIG
        ):
            spares.append(component)
    if len(spares) != 1:
        raise RuntimeError(
            f"{label}: {len(spares)} {notes.SPARE_SPROCKET_STEM} "
            f"{notes.SPARE_SPROCKET_CONFIG} instances in {configuration_name!r}, "
            "expected one"
        )
    spare = spares[0]
    parent = spare.GetParent()
    if parent is None or _component_stem(parent) != notes.PAPER_DRIVE:
        raise RuntimeError(f"{label}: {spare.Name2!r} is not the paper drive's")
    path = str(spare.Name2 or "").replace("\\", "/")
    values = [
        float(value)
        for value in _early_bound(spare.Transform2, "IMathTransform").ArrayData
    ]
    rotation, origin = values[0:9], values[9:12]
    local = [value / 1000.0 for value in notes.SPARE_SPROCKET_TIP_MM]
    collapsed = [
        sum(local[i] * rotation[i * 3 + k] for i in range(3)) + origin[k]
        for k in range(3)
    ]
    shift = _explode_offset(_view_explode_offsets(adapter, view, label=label), path)
    if any(
        abs(actual - wanted) > 1e-9
        for actual, wanted in zip(shift, PAPER_DRIVE_EXPLODE_M, strict=True)
    ):
        raise RuntimeError(
            f"{label}: {path} explodes by {shift}, not the paper drive's "
            f"{PAPER_DRIVE_EXPLODE_M}"
        )
    point = (
        collapsed[0] + shift[0],
        collapsed[1] + shift[1],
        collapsed[2] + shift[2],
    )
    _telemetry.event("drawing.spare_sprocket_tip", instance=path, model_m=list(point))
    return model_point_in_view(adapter, view, point, label=label)


def _validate_source(source_model: Any) -> None:
    """The builder-owned explodes exist, and the source opens collapsed with
    exactly the contracted subassemblies at the top level."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != ASSEMBLY_VIEW_CONFIGURATION:
        raise RuntimeError(
            "complete-machine source must open in its Default configuration"
        )
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(
                f"complete-machine {owner} exploded views {names!r} != {(wanted,)!r}"
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
                f"complete-machine source must open collapsed: {component.Name2!r} "
                "is displaced"
            )
    if counts != dict.fromkeys(BOM_COMPONENTS, 1):
        raise RuntimeError(
            f"complete-machine top level {counts!r} != one of each {BOM_COMPONENTS!r}"
        )


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
        raise RuntimeError(
            f"complete-machine BOM has no unique {label} column: {header!r}"
        )
    return matches[0]


def _validate_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    """Rewrite part numbers to the subassembly drawing numbers, prove
    identities/descriptions/quantities, size the columns; return (stem, item
    number) in BOM order."""
    table = _early_bound(table, "ITableAnnotation")
    contents = _bom_cells(table)
    rows = len(contents)
    if rows != len(BOM_COMPONENTS) + 1:
        raise RuntimeError(
            f"complete-machine BOM has {rows} rows; expected {len(BOM_COMPONENTS) + 1}"
        )
    header = contents[0]
    columns = {
        "item": _bom_column(
            header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
        ),
        "part": _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER"),
        "description": _bom_column(
            header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
        ),
        "quantity": _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY."),
    }
    if len(header) != len(BOM_COLUMN_WIDTHS):
        raise RuntimeError(
            f"complete-machine BOM columns {header!r} are not the contract"
        )

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        text = row[columns["part"]].casefold()
        stem = BOM_NORMALIZED_ALIASES.get(text, text)
        if stem in actual:
            raise RuntimeError(f"complete-machine BOM repeats subassembly {stem!r}")
        actual[stem] = (
            row_index,
            row[columns["item"]],
            row[columns["description"]],
            row[columns["quantity"]],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"complete-machine BOM identities {sorted(actual)!r} != "
            f"{sorted(BOM_COMPONENTS)!r}"
        )
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(BOM_COMPONENTS) + 1)}:
        raise RuntimeError(
            f"complete-machine BOM item numbers {sorted(items)!r} are not contiguous"
        )
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][columns["part"]] != number:
            if not table.IsCellTextEditable(row_index, columns["part"]):
                raise RuntimeError(
                    f"complete-machine BOM part-number cell for {stem!r} is locked"
                )
            table.SetText2(row_index, columns["part"], False, number)
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(
                f"complete-machine BOM description mismatch for {stem!r}"
            )
        if quantity != "1":
            raise RuntimeError(
                f"complete-machine BOM quantity for {stem!r} is {quantity!r}, expected 1"
            )

    for key, column in columns.items():
        width = BOM_COLUMN_WIDTHS[key]
        if abs(float(table.SetColumnWidth(column, width, 0)) - width) > 1e-6:
            raise RuntimeError(
                f"complete-machine BOM {key} column width did not persist"
            )
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("complete-machine BOM rebuild failed")
    settled = _bom_cells(table)
    for stem, (row_index, *_rest) in actual.items():
        applied = settled[row_index][columns["part"]]
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(
                f"complete-machine BOM part number for {stem!r} reads {applied!r}"
            )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _add_setting_dimensions(adapter: Any, front: Any) -> Callable[[], None]:
    """Import the builder's two driving setting dimensions onto the front
    view: the bar height outside the view's west edge, the stud drop outside
    the east column."""
    x0, _y0, _x1, _y1 = _view_outline(front, label="assembled front")
    lines = {line.dimension: line for line in spec.SETTING_LINES}
    bar = lines[spec.BAR_HEIGHT_DIMENSION]
    stud = lines[spec.STUD_DROP_DIMENSION]
    bar_mid, stud_text = model_points_in_view(
        adapter,
        front,
        [
            (bar.x / 1000.0, (bar.y_low + bar.y_high) / 2000.0, 0.0),
            (
                STUD_DIMENSION_TEXT_MODEL_X_MM / 1000.0,
                (stud.y_low + stud.y_high) / 2000.0,
                0.0,
            ),
        ],
        label="complete-machine setting dimension text",
        names=("bar height text", "stud drop text"),
    )
    keep = {
        spec.BAR_HEIGHT_DIMENSION: (x0 + BAR_DIMENSION_TEXT_DX, bar_mid[1]),
        spec.STUD_DROP_DIMENSION: stud_text,
    }
    _show_base_view_sketches(
        adapter, front, (spec.SETTING_FEATURE,), label="integration settings"
    )
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=keep,
        view_label="integration settings",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    if len(annotations) != len(keep):
        raise RuntimeError("integration settings must import exactly two dimensions")
    expected = {line.dimension: line.length for line in spec.SETTING_LINES}
    authored = []
    for annotation in annotations:
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        name = str(dimension.Name or "")
        if name not in expected:
            raise RuntimeError(f"integration settings imported {name!r}")
        if int(display.Type2) not in (_LINEAR_DIMENSION, _VERTICAL_LINEAR_DIMENSION):
            raise RuntimeError(
                f"{name}: expected a linear dimension, got {display.Type2}"
            )
        if int(display.GetPrimaryPrecision2()) != spec.SETTING_PRECISION:
            raise RuntimeError(f"{name}: precision did not persist")
        callout = notes.SETTING_CALLOUTS[name]
        display.SetText(_CALLOUT_BELOW, callout)
        if str(display.GetText(_CALLOUT_BELOW) or "") != callout:
            raise RuntimeError(f"{name}: callout did not persist")
        authored.append((name, display))

    def settled() -> None:
        for name, display in authored:
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            measured = abs(float(dimension.SystemValue) * 1000.0)
            if abs(measured - expected[name]) > 1e-4:
                raise RuntimeError(f"{name}: settled value {measured:g} mm changed")
            if (
                str(display.GetText(_CALLOUT_BELOW) or "")
                != notes.SETTING_CALLOUTS[name]
            ):
                raise RuntimeError(f"{name}: settled callout changed")

    settled()
    return settled


def _add_bar_column_axis(adapter: Any, front: Any) -> None:
    """The west front column's centreline on the front view: the bar-height
    chain lies on that axis and reads as it (machinist review r2/r3 on
    b4df34ad9 read the chain, beside the column, as an unlabelled line)."""
    xy = model_point_in_view(
        adapter, front, BAR_COLUMN_PICK_M, label="west front column axis pick"
    )
    add_view_centerline(
        adapter, front, face_xy=(xy[0], xy[1]), label="front view west column axis"
    )


def _place_assembled_sheet(adapter: Any) -> Callable[[], None]:
    """Front and crank-side views at 1:5, the settings and the note."""
    name = SHEET_NAMES[0]
    layout = SHEET_LAYOUTS[name]
    _activate_sheet(adapter, name)
    front = place_view(
        adapter, str(SOURCE), "*Front", 0.090, ASSEMBLED_ROW_Y, scale=ASSEMBLED_SCALE
    )
    right = place_view(
        adapter, str(SOURCE), "*Right", 0.200, ASSEMBLED_ROW_Y, scale=ASSEMBLED_SCALE
    )
    for view, label in ((front, "assembled front"), (right, "assembled crank side")):
        set_hidden_lines_removed(adapter, view)
        apply_view_configuration(adapter, view, label=label)
    _move_view_outline(
        adapter,
        front,
        label="assembled front",
        left_x=FRONT_LEFT_X,
        center_y=ASSEMBLED_ROW_Y,
    )
    _x0, _y0, front_right, _y1 = _view_outline(front, label="assembled front")
    _move_view_outline(
        adapter,
        right,
        label="assembled crank side",
        left_x=front_right + VIEW_GAP_X,
        center_y=ASSEMBLED_ROW_Y,
    )
    for view, label in ((front, "assembled front"), (right, "assembled crank side")):
        _assert_view_on_sheet(view, layout=layout, label=label)
    settled = _add_setting_dimensions(adapter, front)
    _add_bar_column_axis(adapter, front)
    _add_note_block(
        adapter, name, ASSEMBLED_NOTE, ASSEMBLED_NOTE_XY, label="assembled note"
    )
    return settled


def _place_finished_sheet(adapter: Any) -> None:
    """The finished machine in full detail: the package's every-tooth view."""
    name = SHEET_NAMES[1]
    _activate_sheet(adapter, name)
    finished = place_view(
        adapter, str(SOURCE), "*Isometric", *FINISHED_CENTER, scale=ASSEMBLED_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, finished, label="finished machine")
    configuration = apply_view_configuration(
        adapter, finished, role=ViewRole.FULL_DETAIL, label="finished machine"
    )
    set_view_exploded_state(
        adapter, finished, False, configuration=configuration, label="finished machine"
    )
    _move_view_outline(
        adapter,
        finished,
        label="finished machine",
        center_x=FINISHED_CENTER[0],
        center_y=FINISHED_CENTER[1],
    )
    _assert_view_on_sheet(
        finished, layout=SHEET_LAYOUTS[name], label="finished machine"
    )
    assert_full_detail_view(adapter, label="complete-machine assembly")


def _place_exploded_sheet(adapter: Any) -> Callable[[], None]:
    """The exploded isometric, the top-level BOM, one balloon per row and the
    spare sprocket's label; returns the check that proves every balloon again
    after the last rebuild."""
    name = SHEET_NAMES[2]
    _activate_sheet(adapter, name)
    exploded = place_view(
        adapter, str(SOURCE), "*Isometric", *EXPLODED_CENTER, scale=EXPLODED_SCALE
    )
    set_high_quality_shaded_with_edges(
        adapter, exploded, label="complete-machine exploded"
    )
    # Configuration, then its own explode, then the BOM and balloons bind.
    configuration = apply_view_configuration(
        adapter, exploded, label="complete-machine exploded"
    )
    set_view_exploded_state(
        adapter,
        exploded,
        True,
        configuration=configuration,
        label="complete-machine exploded",
    )
    _move_view_outline(
        adapter,
        exploded,
        label="complete-machine exploded",
        center_x=EXPLODED_CENTER[0],
        center_y=EXPLODED_CENTER[1],
    )
    _assert_view_on_sheet(
        exploded,
        layout=SHEET_LAYOUTS[name],
        margin=BALLOON_MARGIN,
        label="complete-machine exploded",
    )
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="complete-machine",
    )
    rows = _validate_bom(adapter, table)
    # The paper drive's loose spare sprocket, beside item 7's group: labelled
    # with its number and its row, the step that places it (r1/r2 on 5bca52e13).
    # Its tip is read before the balloons exist, so they bind after any
    # explode read-back this does on the source.
    if dict(rows)[notes.PAPER_DRIVE] != notes.PAPER_DRIVE_ITEM:
        raise RuntimeError(
            f"complete-machine paper drive is item {dict(rows)[notes.PAPER_DRIVE]}, "
            f"the spare label says {notes.PAPER_DRIVE_ITEM}"
        )
    spare_tip = _spare_sprocket_tip(adapter, exploded)
    # A top-level BOM numbers a nested part's balloon with its subassembly's
    # row: each row's balloon lands on one part only that subassembly owns.
    landings = add_component_bom_balloons(
        adapter,
        exploded,
        items=tuple((notes.BALLOON_PARTS[stem], item) for stem, item in rows),
        anchors=BALLOON_ANCHORS,
        label="complete-machine exploded-view BOM coverage",
        margin=BALLOON_MARGIN,
    )
    if len(landings) != len(BOM_COMPONENTS):
        raise RuntimeError(
            f"complete-machine exploded view carries {len(landings)} balloons, "
            f"expected one per BOM row ({len(BOM_COMPONENTS)})"
        )
    add_leader_note(
        adapter,
        notes.SPARE_SPROCKET_LABEL,
        text_xy=(
            spare_tip[0] + SPARE_LABEL_OFFSET[0],
            spare_tip[1] + SPARE_LABEL_OFFSET[1],
        ),
        attach_xy=spare_tip,
        label="spare sprocket label",
        view=exploded,
    )
    _add_note_block(
        adapter,
        name,
        notes.EXPLODED_CAPTION,
        EXPLODED_CAPTION_XY,
        label="exploded caption",
    )
    return lambda: assert_balloon_landings(adapter, landings)


def _place_thumbnail(adapter: Any, name: str) -> None:
    """A finished-machine thumbnail for orientation beside a text sheet."""
    label = f"{name.lower()} thumbnail"
    _activate_sheet(adapter, name)
    thumbnail = place_view(
        adapter, str(SOURCE), "*Isometric", *STEPS_VIEW_CENTER, scale=STEPS_VIEW_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, thumbnail, label=label)
    configuration = apply_view_configuration(adapter, thumbnail, label=label)
    set_view_exploded_state(
        adapter, thumbnail, False, configuration=configuration, label=label
    )
    _assert_view_on_sheet(thumbnail, layout=SHEET_LAYOUTS[name], label=label)


def _place_steps_sheet(adapter: Any) -> None:
    """The integration sequence in two columns and a thumbnail."""
    name = SHEET_NAMES[3]
    _place_thumbnail(adapter, name)
    _add_note_block(
        adapter,
        name,
        STEPS_LEFT,
        (STEPS_LEFT_X, STEPS_TOP_Y),
        label=f"steps 1-{STEPS_SPLIT}",
    )
    _add_note_block(
        adapter, name, STEPS_RIGHT, (STEPS_RIGHT_X, STEPS_TOP_Y), label="later steps"
    )


def _place_checks_sheet(adapter: Any) -> None:
    """The checks before running and a thumbnail."""
    name = SHEET_NAMES[4]
    _place_thumbnail(adapter, name)
    _add_note_block(adapter, name, ASSEMBLY_CHECKS, CHECKS_XY, label="checks")


def _activate_package(adapter: Any, target: Any) -> None:
    title = str(target.GetTitle() or "")
    if not title:
        raise RuntimeError("complete-machine package drawing has no title")
    activation = adapter.swApp.ActivateDoc3(title, False, 2, 0)
    if not activation:
        raise RuntimeError("failed to reactivate complete-machine package")
    activated, errors = activation
    if int(errors) != 0:
        raise RuntimeError(f"failed to reactivate complete-machine package: {errors}")
    if activated is None:
        activated = adapter.swApp.ActiveDoc
    if activated is None or int(adapter.swApp.IsSame(activated, target)) != 1:
        raise RuntimeError("reactivated document is not the complete-machine package")
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


def _create_mixed_package_sheets(adapter: Any) -> None:
    """Use native template copies, not a metadata-only layout declaration."""
    target, initial = new_project_drawing(
        adapter,
        layout=SHEET_LAYOUTS[SHEET_NAMES[0]],
        scale=SHEET_SCALES[SHEET_NAMES[0]],
    )
    target = _early_bound(target, "IModelDoc2")
    initial = _early_bound(initial, "ISheet")
    initial.SetName(SHEET_NAMES[0])
    if str(initial.GetName() or "") != SHEET_NAMES[0]:
        raise RuntimeError("failed to name complete-machine primary sheet")
    for name in SHEET_NAMES[1:]:
        _append_template_sheet(adapter, target, name=name)
    actual = tuple(_early_bound(target, "IDrawingDoc").GetSheetNames() or ())
    if actual != SHEET_NAMES:
        raise RuntimeError(f"complete-machine sheet order mismatch: {actual!r}")


def _place_package(adapter: Any) -> Callable[[], None]:
    _create_mixed_package_sheets(adapter)
    for sheet_name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, sheet_name)
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(
                f"failed to set complete-machine sheet scale: {sheet_name}"
            )
    assembled_settled = _place_assembled_sheet(adapter)
    _place_finished_sheet(adapter)
    exploded_settled = _place_exploded_sheet(adapter)
    _place_steps_sheet(adapter)
    _place_checks_sheet(adapter)

    def settled() -> None:
        assembled_settled()
        exploded_settled()

    return settled


@_telemetry.traced("drawing.ha_harmonic_analyzer_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open complete-machine drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    properties = read_required_properties(
        source_model,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != notes.DRAWING_NUMBER:
        raise RuntimeError(
            f"complete-machine source Number {properties['Number']!r} != "
            f"{notes.DRAWING_NUMBER!r}"
        )
    _validate_source(source_model)

    settled = _place_package(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Harmonic Analyzer Assembly Drawing Package",
        scale=ASSEMBLED_SCALE,
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
