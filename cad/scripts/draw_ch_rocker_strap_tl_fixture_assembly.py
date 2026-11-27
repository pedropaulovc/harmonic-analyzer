r"""Create the fitting sheets for the rocker-strap sub-plate fixture (MHA-CH-13-TL-00).

Shop fixture (owner ask 2026-11-17; ``ch_rocker_strap_tl_fixture_spec``).
Sheet 1: the plan view (looking down on the plate top, the fence at the
back) in the outline setup, its parts ballooned against the parts list, the
strap blank (not in the fixture) in phantom where it lies; the shaded
isometric; the parts list; the fitting steps (vise, fence indicated along X,
work zero, clamps). Sheet 2: the exploded front view (rule 22) at 1:1, one
view per item family (draw_dt_cone_tip_gear_tl_cutter_assembly's
``_item_view``): the plug, the washer and the hub screw drawn up out of the
counterbore in fitting order, the four clamps up out of their pockets, item
2 ballooned (the washer hides it in the plan view), every loose item
labelled with its facing; the screw schedule (thread and torque) and each
blank's steps. Poses, items and the sheet words come from the spec; this recipe
only lays the sheets out and never edits the source assembly.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
import ch_rocker_strap_tl_fixture_spec as spec
from _check import check
from _com import _early_bound
from _drawing_balloons import (
    BalloonAnchor,
    BalloonLanding,
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_tables import bom_row_identities, insert_bom_table
from _drawing_types import DrawingLayout
from _drawing_view_configuration import (
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from _transgear_zone_line import require_placed, sketch_lines
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["ch_rocker_strap_tl_fixture_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the strap-fixture sheets must remain landscape")

DRAWING_NUMBER = spec.DRAWING_NUMBER
# Sheet 1 at 1:2, so the 13 in plate and its isometric fit the left half;
# sheet 2's exploded front view at 1:1, so the .140 pockets, the plug and
# the clamps read, the 13 in plate end to end across the sheet.
SHEET_NAMES = ("ASSEMBLY", "EXPLODED VIEW")
SHEET_SCALE = (1.0, 2.0)
EXPLODED_SCALE = (1.0, 1.0)
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALES = {SHEET_NAMES[0]: SHEET_SCALE, SHEET_NAMES[1]: EXPLODED_SCALE}
PLAN_SCALE = (1, 2)
ISO_SCALE = (1, 2)
_S1 = PLAN_SCALE[0] / PLAN_SCALE[1] / 1000.0

BOM_COMPONENTS = spec.BOM_ORDER
BOM_ITEMS = spec.BOM_ITEMS
PLATE, PLUG, WASHER, CLAMP, SCREW = BOM_COMPONENTS

# --- Sheet 1 (sheet metres) -----------------------------------------------------
# The plan view's model origin (X0 end-stop face, Y0 fence face) top left,
# the plate running 317.5 mm right of it (159 mm at 1:2) and 63.5 mm toward
# the viewer's bottom (32 mm), far enough right that the balloon ring's left
# end stays inside the border; the isometric under it; the fitting steps
# top right, right of the plan view's outline (x 0.228); the parts list
# (220 mm wide, so it starts no further right than 0.198) under the steps,
# above the title block (y > 0.066). Every view is at 1:2, so the title
# block's SCALE carries it and no view note does. The screw schedule is on
# sheet 2, under the exploded view, left of the title block (x < 0.216 m).
PLAN_ORIGIN = (0.064, 0.232)
ISO_CENTER = (0.105, 0.135)
ISO_POINT_MM = (spec.plate.HUB_X, spec.plate.HUB_Y, 0.0)
STEPS_XY = (0.240, 0.264)
BOM_ANCHOR = (0.198, 0.144)
BOM_HEIGHT = 0.0665  # r6's native parts list: 195.7..262.0 mm
TABLE_XY = (0.017, 0.080)  # the schedule title's top left; the table under it
TABLE_CHAR_WIDTH = 0.0028
TABLE_CELL_PAD = 0.003
TABLE_ROW_HEIGHT = 0.0055
TABLE_TITLE_GAP = 0.0015
SHEET_CLEARANCE = 0.003  # visible air at the border and the title block
SHEET_INNER_LEFT = 0.0127
SHEET_INNER_BOTTOM = 0.0127
TITLE_BLOCK_LEFT = 0.216
TITLE_BLOCK_TOP = 0.066
BALLOON_MARGIN = 0.012
CHAR_WIDTH = 0.00255  # default-format note text, per character
LINE_PITCH = 0.0046

SCREW_TABLE_ROWS: tuple[tuple[str, ...], ...] = spec.SCREW_TABLE_ROWS


def table_column_widths(
    header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]
) -> tuple[float, ...]:
    """Each general-table column cut to its longest cell (metres)."""
    return tuple(
        max(len(text) for text in column) * TABLE_CHAR_WIDTH + TABLE_CELL_PAD
        for column in zip(header, *rows, strict=True)
    )


def screw_table_box() -> tuple[float, float, float, float]:
    """The screw schedule's planned box (x0, y0, x1, y1) under its title."""
    x, top = TABLE_XY
    top -= len(spec.SCREW_TABLE_TITLE.splitlines()) * LINE_PITCH + TABLE_TITLE_GAP
    widths = table_column_widths(spec.SCREW_TABLE_HEADER, SCREW_TABLE_ROWS)
    height = (len(SCREW_TABLE_ROWS) + 1) * TABLE_ROW_HEIGHT
    return (x, top - height, x + sum(widths), top)


_planned = screw_table_box()
if _planned[2] > TITLE_BLOCK_LEFT - SHEET_CLEARANCE:
    raise AssertionError("the screw schedule runs into the title block")
if _planned[1] < SHEET_INNER_BOTTOM + SHEET_CLEARANCE:
    raise AssertionError("the screw schedule runs past the bottom border")
_steps_bottom = STEPS_XY[1] - len(spec.ASSEMBLY_STEPS.splitlines()) * LINE_PITCH
if _steps_bottom < BOM_ANCHOR[1] + 2.0 * SHEET_CLEARANCE:
    raise AssertionError("the fitting steps run into the parts list")
if BOM_ANCHOR[1] - BOM_HEIGHT < TITLE_BLOCK_TOP + SHEET_CLEARANCE:
    raise AssertionError("the parts list runs into the title block")
_plan_right = PLAN_ORIGIN[0] + spec.plate.RIGHT_END_X * _S1
if STEPS_XY[0] < _plan_right + 0.010:
    raise AssertionError("the fitting steps crowd the plan view")

# --- The strap blank in phantom (spec.BLANK_*) ----------------------------------
# Drawn in the plan view's own sketch as the arbor kit draws its blank (thin
# phantom, swLineStyles_e 2 / swLineWeights_e 0): its outline on the plate
# top, its back edge on the fence face, its left end on the end-stop face.
# Its label's tip on its outline's front edge, between clamps 2 and 3.
PHANTOM_STYLE, PHANTOM_WIDTH = 2, 0
Point3 = tuple[float, float, float]
_BZ = spec.BLANK_TOP_Z
BLANK_OUTLINE: dict[str, tuple[Point3, Point3]] = {
    "back": ((0.0, 0.0, _BZ), (spec.BLANK_LENGTH, 0.0, _BZ)),
    "front": (
        (0.0, -spec.BLANK_WIDTH, _BZ),
        (spec.BLANK_LENGTH, -spec.BLANK_WIDTH, _BZ),
    ),
    "left": ((0.0, 0.0, _BZ), (0.0, -spec.BLANK_WIDTH, _BZ)),
    "right": (
        (spec.BLANK_LENGTH, 0.0, _BZ),
        (spec.BLANK_LENGTH, -spec.BLANK_WIDTH, _BZ),
    ),
}
BLANK_TIP_MM: Point3 = (
    (spec.CLAMP_POSITIONS[1][0] + spec.plate.HUB_X) / 2.0,
    -spec.BLANK_WIDTH,
    _BZ,
)
# The label straight under its tip, below the plate, its leader leaving the
# label's left end upward: clear of its own text and of the plate's balloon
# (down right of the hub).
BLANK_LABEL_OFFSET = (0.0, -0.045)

# Balloon anchors, each part's own mm on an edge the plan view shows. The
# ring (_drawing_balloons._spread_balloons) puts each balloon at its
# attachment's angle from the view's centre, stretched onto a wide ellipse,
# so an attachment near the centre swings far: each family is aimed at its
# own quarter so no two leaders cross. Clamp 1 (left end) goes left; the
# plate's front top edge between the hub and clamp 3 goes down and right;
# the hub screw's head rim where its side meets the dome (its bearing rim
# lies under the head's own side) goes up and right; the washer's top outer
# rim, outside the screw head, goes straight up (r8: at 135 deg the shallow
# leader clipped its own balloon's text box). The clamp's anchor is its
# screw's head-top circle (inside the chamfer: the head's full radius is no
# edge at the top face). Rim angles run from part +X toward +Y.
CLAMP_RIM_DEG = -45.0
SCREW_RIM_DEG = 45.0
WASHER_RIM_DEG = 90.0


def rim_point(radius: float, z: float, degrees: float) -> Point3:
    """Part millimetres of the rim of ``radius`` at ``z``, ``degrees`` round."""
    angle = math.radians(degrees)
    return (radius * math.cos(angle), radius * math.sin(angle), z)


PLAN_ITEMS = (PLATE, WASHER, CLAMP, SCREW)
BALLOON_ANCHORS: dict[str, BalloonAnchor] = {
    PLATE: BalloonAnchor(
        point_mm=(
            (spec.plate.HUB_X + spec.CLAMP_POSITIONS[2][0]) / 2.0,
            spec.plate.FRONT_EDGE_Y,
            0.0,
        )
    ),
    WASHER: BalloonAnchor(
        point_mm=rim_point(
            spec.washer.OUTER_DIA / 2.0, spec.washer.THICKNESS, WASHER_RIM_DEG
        )
    ),
    CLAMP: BalloonAnchor(
        point_mm=rim_point(
            spec.clamp.SCREW_HEAD_DIA / 2.0 - spec.clamp.SCREW_HEAD_CHAMFER,
            spec.clamp.SCREW_HEAD_TOP_Z,
            CLAMP_RIM_DEG,
        )
    ),
    SCREW: BalloonAnchor(
        point_mm=rim_point(
            spec.HUB_SCREW_HEAD_DIA / 2.0, spec.hub_screw.SIDE_TOP_Y, SCREW_RIM_DEG
        )
    ),
    # Sheet 2's front view looks along +Y: the plug's shoulder rim on its
    # viewer's side, a third of the way round from +X.
    PLUG: BalloonAnchor(
        point_mm=(
            spec.plug.BODY_DIA / 4.0,
            -spec.plug.BODY_DIA / 2.0 * math.sin(math.radians(60.0)),
            spec.plug.BODY_LENGTH,
        )
    ),
}

# --- Sheet 2: the exploded front view (rule 22) ---------------------------------
# One front view (SolidWorks *Bottom: looking along +Y, model X right, Z
# up) per item family at 1:1, each isolated to its family, placed where its
# explode offset lands in item 1's view. Every loose item goes straight up
# along its own axis, in bands: the four item 4 up out of their pockets,
# each screw's tip over the fence; then, over the clamps, item 2 out of the
# counterbore, item 3 and item 5 above it, in fitting order. A view's
# outline stands VIEW_PAD_MM (r3's native measure) beyond its ink, and the
# layout audit counts any ink inside a view's outline as that view's, so
# each band starts VIEW_PAD_MM + BAND_AIR_MM above the last one's ink.
# Assembly mm.
EXPLODED_ORIGIN = (0.050, 0.112)  # item 1's X0, Z0, sheet m
VIEW_PAD_MM = 5.6
BAND_AIR_MM = 3.0
EXPLODE_GAP = VIEW_PAD_MM + BAND_AIR_MM
_CLAMP_DZ = (
    spec.plate.FENCE_HEIGHT
    + EXPLODE_GAP
    + spec.clamp.SCREW_TIP_DEPTH
    - spec.plate.POCKET_FLOOR_Z
)
_CLAMP_TOP_Z = spec.CLAMP_POSITIONS[0][2] + _CLAMP_DZ + spec.clamp.TOP_Z
_PLUG_DZ = _CLAMP_TOP_Z + EXPLODE_GAP - spec.PLUG_POSITION[2]
_PLUG_TOP_Z = spec.PLUG_POSITION[2] + _PLUG_DZ + spec.plug.OVERALL_LENGTH
_WASHER_DZ = _PLUG_TOP_Z + EXPLODE_GAP - spec.WASHER_POSITION[2]
_WASHER_TOP_Z = spec.WASHER_POSITION[2] + _WASHER_DZ + spec.washer.THICKNESS
_SCREW_DZ = _WASHER_TOP_Z + EXPLODE_GAP + spec.HUB_SCREW_LENGTH - spec.SCREW_POSITION[2]
EXPLODE_OFFSETS_MM: dict[str, Point3] = {
    PLATE: (0.0, 0.0, 0.0),
    PLUG: (0.0, 0.0, _PLUG_DZ),
    WASHER: (0.0, 0.0, _WASHER_DZ),
    CLAMP: (0.0, 0.0, _CLAMP_DZ),
    SCREW: (0.0, 0.0, _SCREW_DZ),
}
EXPLODED_BALLOONED = (PLUG,)
EXPLODED_LABELS: dict[str, str] = {
    PLATE: f"ITEM {BOM_ITEMS[PLATE]}, FENCE AT THE BACK",
    PLUG: f"ITEM {BOM_ITEMS[PLUG]}, PILOT UP",
    WASHER: f"ITEM {BOM_ITEMS[WASHER]}",
    CLAMP: f"ITEM {BOM_ITEMS[CLAMP]}, 4X, CLAMPING EDGE TOWARD THE FENCE",
    SCREW: f"ITEM {BOM_ITEMS[SCREW]}",
}
# Each leader's tip, seated assembly mm, on a face the view shows: item 1's
# front face under clamp 1's pocket's right; item 2's pilot; item 3's front;
# clamp 1's body; item 5's head.
_HUB_X = spec.plate.HUB_X
LABEL_TIPS_MM: dict[str, Point3] = {
    PLATE: (
        spec.CLAMP_POSITIONS[0][0] + 20.0,
        spec.plate.FRONT_EDGE_Y,
        spec.plate.UNDERSIDE_Z / 2.0,
    ),
    PLUG: (
        _HUB_X,
        spec.plate.HUB_Y - spec.plug.PILOT_DIA / 2.0,
        spec.PLUG_POSITION[2] + spec.plug.OVERALL_LENGTH - 1.0,
    ),
    WASHER: (
        _HUB_X - spec.washer.OUTER_DIA / 4.0,
        spec.plate.HUB_Y - spec.washer.OUTER_DIA / 2.0,
        spec.WASHER_POSITION[2] + spec.washer.THICKNESS / 2.0,
    ),
    CLAMP: (
        spec.CLAMP_POSITIONS[0][0],
        spec.CLAMP_POSITIONS[0][1] + spec.clamp.HEEL_Y,
        spec.CLAMP_POSITIONS[0][2] + spec.clamp.HEEL_FACE_MID_Z,
    ),
    SCREW: (
        _HUB_X,
        spec.plate.HUB_Y,
        spec.SCREW_POSITION[2] + spec.HUB_SCREW_HEAD_HEIGHT / 2.0,
    ),
}
# Each label's upper-left corner from its tip, sheet m: wholly to one side
# of its tip, so its leader leaves the text's end, clear of the letters.
# Item 4 above the clamps, left of the hub stack; items 2 and 3 left of the
# stack, item 2's balloon on its right; item 5 right of its head.
LABEL_OFFSETS: dict[str, tuple[float, float]] = {
    PLATE: (0.010, -0.010),
    PLUG: (-0.050, 0.002),
    WASHER: (-0.040, 0.006),
    CLAMP: (-0.010, 0.050),
    SCREW: (0.012, 0.015),
}
EXPLODED_CAPTION = "\n".join(
    (
        "EXPLODED FRONT VIEW",
        "FIXTURE STEPS ON SHEET 1; EACH BLANK'S STEPS AT RIGHT",
    )
)
CAPTION_XY = (0.020, 0.255)
# Each blank's steps top right, right of the hub stack's labels (item 5's
# ends near x 0.230) and over the clamps' band (its outline top 0.141).
BLANK_STEPS_XY = (0.240, 0.262)
_blank_steps_bottom = (
    BLANK_STEPS_XY[1] - len(spec.BLANK_STEPS.splitlines()) * LINE_PITCH
)
_clamp_band_top = (
    EXPLODED_ORIGIN[1] + (_CLAMP_TOP_Z + VIEW_PAD_MM + BAND_AIR_MM) / 1000.0
)
if _blank_steps_bottom < _clamp_band_top:
    raise AssertionError("each blank's steps run into the exploded clamps")

Box = tuple[float, float, float, float]


def _add_note(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> None:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the strap-fixture {label}")
    printed = (
        str(_early_bound(note, "INote").GetText() or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if printed != text:
        raise RuntimeError(f"strap-fixture {label} printed as {printed!r}")


def _place_screw_table(adapter: Any) -> None:
    """The screw schedule's title, then its native general table under it,
    every cell read back; its read-back box must clear the border and the
    title block (draw_dt_cone_gear_tl_arbor_assembly._place_setup_table)."""
    label = "strap-fixture screw schedule"
    _activate_sheet(adapter, SHEET_NAMES[1])
    _add_note(adapter, spec.SCREW_TABLE_TITLE, TABLE_XY, label=f"{label} title")
    header, rows = spec.SCREW_TABLE_HEADER, SCREW_TABLE_ROWS
    x, _y0, _x1, top = screw_table_box()
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    # swBOMConfigurationAnchor_TopLeft = 1; no template: a plain general table.
    raw = ddoc.InsertTableAnnotation2(False, x, top, 1, "", len(rows) + 1, len(header))
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
                    f"{label}: cell ({row}, {column}) reads {applied!r}, not {text!r}"
                )
    for row in range(len(rows) + 1):
        table.SetRowHeight(row, TABLE_ROW_HEIGHT, 0)
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    heights = [float(table.GetRowHeight(row)) for row in range(len(rows) + 1)]
    widths = [float(table.GetColumnWidth(column)) for column in range(len(header))]
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
    if box[2] > TITLE_BLOCK_LEFT - SHEET_CLEARANCE:
        raise RuntimeError(f"{label}: runs into the title block at {box!r}")
    if box[1] < SHEET_INNER_BOTTOM + SHEET_CLEARANCE:
        raise RuntimeError(f"{label}: runs past the bottom border at {box!r}")


def _bom_items(table: Any, configuration: str) -> dict[str, str]:
    """Each family's row, read through its native components: the steps and
    the screw schedule cite the spec's item numbers, so the BOM must number
    the rows in BOM_ORDER."""
    rows = bom_row_identities(
        table,
        configuration=configuration,
        component_identities=dict(spec.COMPONENT_IDENTITIES),
    )
    printed = {stem: str(row) for stem, row in rows.items()}
    if printed != BOM_ITEMS:
        raise RuntimeError(
            f"strap-fixture BOM numbers its rows {printed!r}, not {BOM_ITEMS!r}"
        )
    return printed


def _bom_feature_name(table: Any) -> str:
    """The inserted BOM's feature name, the key a view links to it by."""
    bom = _early_bound(table, "IBomTableAnnotation")
    feature = _early_bound(bom.BomFeature, "IBomFeature")
    name = str(feature.Name or "")
    if not name:
        raise RuntimeError("strap-fixture BOM feature has no name")
    return name


def _link_view_to_bom(view: Any, bom_name: str, *, label: str) -> None:
    """Number a view's balloons from the BOM another view is the parent of,
    read back."""
    view = _early_bound(view, "IView")
    if not view.SetKeepLinkedToBOM(True, bom_name):
        raise RuntimeError(f"{label}: SetKeepLinkedToBOM({bom_name!r}) returned false")
    if (
        not bool(view.GetKeepLinkedToBOM())
        or str(view.GetKeepLinkedToBOMName() or "") != bom_name
    ):
        raise RuntimeError(f"{label}: view is not linked to BOM {bom_name!r}")


def _move_model_point(
    adapter: Any,
    view: Any,
    point_mm: Point3,
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``view`` so the model point lands on ``target`` (sheet m)."""
    view = _early_bound(view, "IView")
    point = tuple(value / 1000.0 for value in point_mm)
    here = model_points_in_view(adapter, view, [point], label=label)[0]
    position = tuple(float(value) for value in view.Position)
    moved = [position[i] + target[i] - here[i] for i in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label}")
    rebuild_drawing(adapter, label=f"place {label}")
    here = model_points_in_view(adapter, view, [point], label=label)[0]
    if math.dist(here, target) > 1e-4:
        raise RuntimeError(f"{label}: origin sits at {here!r}, not {target!r}")


def _assert_at(
    adapter: Any,
    view: Any,
    point_mm: Point3,
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    point = tuple(value / 1000.0 for value in point_mm)
    (here,) = model_points_in_view(adapter, view, [point], label=label)
    if math.dist(here, target) > 1e-4:
        raise RuntimeError(f"settled {label} sits at {here!r}, not {target!r}")


def _assert_orientation(
    adapter: Any, view: Any, right: Point3, up: Point3, *, label: str
) -> None:
    """The view prints model ``right`` toward sheet +x and ``up`` toward
    sheet +y: the plan view and the exploded front view are named by these
    directions in the steps."""
    origin, x_end, y_end = model_points_in_view(
        adapter,
        view,
        [
            (0.0, 0.0, 0.0),
            tuple(v / 100.0 for v in right),
            tuple(v / 100.0 for v in up),
        ],
        label=f"{label} orientation",
    )
    dx = (x_end[0] - origin[0], x_end[1] - origin[1])
    dy = (y_end[0] - origin[0], y_end[1] - origin[1])
    if dx[0] <= 0.0 or abs(dx[1]) > 1e-9 or dy[1] <= 0.0 or abs(dy[0]) > 1e-9:
        raise RuntimeError(f"{label}: prints right {dx!r} and up {dy!r}")


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate strap-fixture sheet {name!r}")
    actual = str(_early_bound(ddoc.GetCurrentSheet(), "ISheet").GetName() or "")
    if actual != name:
        raise RuntimeError(f"strap-fixture sheet is {actual!r}, expected {name!r}")


def _draw_blank(adapter: Any, view: Any) -> Callable[[], None]:
    """The strap blank's phantom outline in the plan view's sketch and its
    label; returns the settled check."""
    label = "strap-fixture blank"
    keys = list(BLANK_OUTLINE)
    sheet_points = model_points_in_view(
        adapter,
        view,
        [
            tuple(value / 1000.0 for value in point)
            for key in keys
            for point in BLANK_OUTLINE[key]
        ]
        + [tuple(value / 1000.0 for value in BLANK_TIP_MM)],
        label=f"{label} outline",
    )
    sketched = sketch_lines(
        adapter,
        view,
        {
            key: (sheet_points[2 * i], sheet_points[2 * i + 1])
            for i, key in enumerate(keys)
        },
        style=PHANTOM_STYLE,
        width=PHANTOM_WIDTH,
        label=label,
    )
    rebuild_drawing(adapter, label=label)

    def placed(stage: str) -> None:
        require_placed(
            adapter,
            sketched,
            style=PHANTOM_STYLE,
            width=PHANTOM_WIDTH,
            label=label,
            stage=stage,
        )

    placed("drawn")
    tip = sheet_points[-1]
    add_leader_note(
        adapter,
        spec.BLANK_LABEL,
        text_xy=(tip[0] + BLANK_LABEL_OFFSET[0], tip[1] + BLANK_LABEL_OFFSET[1]),
        attach_xy=tip,
        label=f"{label} label",
        view=view,
    )
    return lambda: placed("settled")


def _place_sheet(adapter: Any) -> tuple[Callable[[], None], list[BalloonLanding], str]:
    """Sheet 1: the plan view and the isometric, the parts list, the
    balloons and the fitting steps (the screw schedule is sheet 2's).
    Returns its settled check, its balloons and the BOM's feature name."""
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_ORIGIN, scale=PLAN_SCALE)
    set_hidden_lines_removed(adapter, plan)
    configuration = apply_view_configuration(adapter, plan, label="strap fixture plan")
    _move_model_point(
        adapter, plan, (0.0, 0.0, 0.0), PLAN_ORIGIN, label="strap-fixture plan view"
    )
    _assert_orientation(
        adapter, plan, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), label="strap-fixture plan"
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_high_quality_shaded_with_edges(adapter, iso, label="strap fixture isometric")
    apply_view_configuration(
        adapter, iso, role=ViewRole.FULL_DETAIL, label="strap fixture *Isometric"
    )
    _move_model_point(
        adapter, iso, ISO_POINT_MM, ISO_CENTER, label="strap-fixture isometric"
    )
    assert_full_detail_view(adapter, label="strap fixture")
    table = insert_bom_table(
        adapter,
        plan,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=dict(spec.BOM_DESCRIPTIONS),
        component_identities=dict(spec.COMPONENT_IDENTITIES),
        part_number_property="Number",
        label="strap fixture",
    )
    items = _bom_items(table, configuration)
    landings = add_component_bom_balloons(
        adapter,
        plan,
        items=tuple((stem, items[stem]) for stem in PLAN_ITEMS),
        anchors=BALLOON_ANCHORS,
        label="strap-fixture plan balloons",
        margin=BALLOON_MARGIN,
        explode_offsets={},
    )
    if len(landings) != len(PLAN_ITEMS):
        raise RuntimeError(
            f"strap-fixture plan view carries {len(landings)} balloons, "
            f"expected {len(PLAN_ITEMS)}"
        )
    _add_note(adapter, spec.ASSEMBLY_STEPS, STEPS_XY, label="fitting steps")
    blank_settled = _draw_blank(adapter, plan)

    def settled() -> None:
        _assert_at(adapter, plan, (0.0, 0.0, 0.0), PLAN_ORIGIN, label="plan view")
        _assert_at(adapter, iso, ISO_POINT_MM, ISO_CENTER, label="isometric")
        blank_settled()

    return settled, landings, _bom_feature_name(table)


def _item_view(adapter: Any, stem: str, target: tuple[float, float]) -> Any:
    """A front view of family ``stem`` alone, hidden lines removed, its
    assembly origin moved onto ``target`` (sheet m)."""
    label = f"strap-fixture exploded {stem}"
    view = place_view(adapter, str(SOURCE), "*Bottom", *target, scale=EXPLODED_SCALE)
    set_hidden_lines_removed(adapter, view)
    apply_view_configuration(adapter, view, label=label)
    view = isolate_drawing_view_components(
        adapter, view, visible_stems=frozenset({stem}), label=label
    )
    _move_model_point(adapter, view, (0.0, 0.0, 0.0), target, label=label)
    return view


def _place_exploded_sheet(
    adapter: Any, bom_name: str
) -> tuple[Callable[[], None], list[BalloonLanding]]:
    """Sheet 2: item 1 at EXPLODED_ORIGIN, every other family where its
    explode offset lands in item 1's view; item 2 ballooned, every family
    labelled; the caption."""
    label = "strap-fixture exploded view"
    _activate_sheet(adapter, SHEET_NAMES[1])
    targets = {PLATE: EXPLODED_ORIGIN}
    views = {PLATE: _item_view(adapter, PLATE, EXPLODED_ORIGIN)}
    _assert_orientation(
        adapter, views[PLATE], (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), label=label
    )
    loose = tuple(stem for stem in BOM_COMPONENTS if stem != PLATE)
    targets.update(
        zip(
            loose,
            model_points_in_view(
                adapter,
                views[PLATE],
                [
                    tuple(value / 1000.0 for value in EXPLODE_OFFSETS_MM[stem])
                    for stem in loose
                ],
                label=f"{label} offsets",
            ),
            strict=True,
        )
    )
    for stem in loose:
        views[stem] = _item_view(adapter, stem, targets[stem])
    landings: list[BalloonLanding] = []
    for stem in EXPLODED_BALLOONED:
        _activate_sheet(adapter, SHEET_NAMES[1])
        _link_view_to_bom(views[stem], bom_name, label=f"{label} {stem}")
        landings += add_component_bom_balloons(
            adapter,
            views[stem],
            items=((stem, BOM_ITEMS[stem]),),
            anchors=BALLOON_ANCHORS,
            label=f"{label} {stem} balloon",
            margin=BALLOON_MARGIN,
            explode_offsets={},
        )
    for stem, text in EXPLODED_LABELS.items():
        (tip,) = model_points_in_view(
            adapter,
            views[stem],
            [tuple(value / 1000.0 for value in LABEL_TIPS_MM[stem])],
            label=f"{label} {stem} label tip",
        )
        add_leader_note(
            adapter,
            text,
            text_xy=(tip[0] + LABEL_OFFSETS[stem][0], tip[1] + LABEL_OFFSETS[stem][1]),
            attach_xy=tip,
            label=f"{label}: {text}",
            view=views[stem],
        )
    _activate_sheet(adapter, SHEET_NAMES[1])
    _add_note(adapter, EXPLODED_CAPTION, CAPTION_XY, label="exploded view caption")
    _add_note(adapter, spec.BLANK_STEPS, BLANK_STEPS_XY, label="each blank's steps")
    _place_screw_table(adapter)

    def settled() -> None:
        for stem, view in views.items():
            _assert_at(
                adapter, view, (0.0, 0.0, 0.0), targets[stem], label=f"{label} {stem}"
            )

    return settled, landings


@_telemetry.traced("drawing.ch_rocker_strap_tl_fixture_assembly")
def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open strap-fixture drawing source", adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        _early_bound(adapter.currentModel, "IModelDoc2"),
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != DRAWING_NUMBER:
        raise RuntimeError(
            f"strap-fixture source Number {properties['Number']!r} != {DRAWING_NUMBER!r}"
        )
    new_project_drawing(
        adapter,
        layout=SPEC.layout,
        scale=SHEET_SCALE,
        unit=spec.CONTRACT.drawing_unit,
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="strap-fixture package")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    for name in SHEET_NAMES:
        _activate_sheet(adapter, name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        if not sheet.SetScale(*SHEET_SCALES[name], False, False):
            raise RuntimeError(f"failed to set strap-fixture sheet scale: {name}")
    _activate_sheet(adapter, SHEET_NAMES[0])
    sheet_settled, landings, bom_name = _place_sheet(adapter)
    exploded_settled, exploded_landings = _place_exploded_sheet(adapter, bom_name)

    def settled() -> None:
        assert_balloon_landings(adapter, [*landings, *exploded_landings])
        sheet_settled()
        exploded_settled()

    return finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Rocker Strap Sub-Plate Fixture Assembly Drawing",
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
