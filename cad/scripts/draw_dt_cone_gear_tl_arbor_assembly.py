r"""Create the fitting sheets for the keyed cutting arbor kit (MHA-DT-03-TL-05).

Shop fixture (issue #2465; ``dt_cone_gear_tl_arbor_assembly_spec``).
Sheet 1: the kit's side view in its working pose, the 64T setup (item 1 with
item 5 bonded in its keyseat, item 2 and item 6 seated on its pilot), its
parts ballooned against the parts list, the 64T blank (not in the kit) in
phantom where it seats; the shaded isometric in the same pose; the parts
list; the setup table (each blank's collar and first index). Sheet 2: the
exploded side view (rule 22), one view per item
(draw_dt_cone_tip_gear_tl_cutter_assembly's ``_item_view``): items 1 and 5
seated together, the blank's phantom, item 2 and item 6 drawn off the thread
end in fitting order on the arbor's axis, items 3 and 4 under item 2, whose
place either takes; the fitting steps. The spare collars stand off the
arbor's end in the model, so every sheet-1 view shows only the working
pose's parts. Poses, items and the sheet words come from the spec; this
recipe only lays the sheets out and never edits the source assembly.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
import dt_cone_gear_tl_arbor_assembly_spec as spec
import dt_cone_gear_tl_arbor_collar_spec as collar
import dt_cone_gear_tl_arbor_key_spec as key
import dt_cone_gear_tl_keyed_arbor_spec as arbor
import dt_cone_gear_tl_vn_arbor_nut_spec as nut
from _assembly_contract import assembly_contract
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
SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_arbor_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the arbor-kit sheets must remain landscape")

CONTRACT = assembly_contract("dt-cone-gear-tl-arbor")
DRAWING_NUMBER = CONTRACT.number
# Sheet 1 at 2:1, so the 1/16 key reads; sheet 2's exploded row at 1:1, so
# the arbor, the collar and the nut fit the left half end to end with room
# for the labels.
SHEET_NAMES = ("ASSEMBLY", "EXPLODED VIEW")
SHEET_SCALE = (2.0, 1.0)
EXPLODED_SCALE = (1.0, 1.0)
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALES = {SHEET_NAMES[0]: SHEET_SCALE, SHEET_NAMES[1]: EXPLODED_SCALE}
SIDE_SCALE = (2.0, 1.0)
ISO_SCALE = (1.0, 1.0)

# Every BOM row; the working pose's parts, the only ones sheet 1 shows.
BOM_COMPONENTS = spec.BOM_ORDER
KIT_COLLAR = spec.member(spec.KIT_COLLAR)
SPARES = tuple(
    spec.member(name) for name in collar.CONFIGURATIONS if name != spec.KIT_COLLAR
)
WORKING = (spec.ARBOR, KIT_COLLAR, spec.KEY, spec.NUT)
if set(WORKING) | set(SPARES) != set(BOM_COMPONENTS):
    raise AssertionError("every kit part is in the working pose or a spare collar")

# --- Sheet 1 (sheet metres) ----------------------------------------------------
# The side view's model origin (the grip's end-face centre) top left, the
# 2.58 arbor running 131 mm left of it, the Ø1.75 collar 89 mm tall and the
# 64T blank's phantom 142 mm; the isometric under it; the parts list and the
# setup table in the right half, above the title block (x >= 0.216 m,
# y <= 0.066 m). The parts list's template columns print 196.6 mm wide, so
# from x 0.219 it ends inside the right border
# (draw_dt_cone_gear_tl_indexing_assembly); its six rows end by about y 0.189
# (farm 20261113T071241685Z). Under it the setup table: its two-line title,
# then a native general table (draw_ch_rocker_arm_tl_oblique_jig_assembly's
# setting tables: each column cut to its longest cell, the BOM's 5.5 mm
# rows), its 18 rows ending over the title block.
SIDE_ORIGIN = (0.180, 0.190)
ISO_CENTER = (0.105, 0.085)
ISO_POINT_MM = (0.0, 0.0, arbor.ARBOR_END_Z / 2.0)
ISO_NOTE_XY = (0.060, 0.045)
BOM_ANCHOR = (0.219, 0.262)
TABLE_XY = (0.219, 0.183)  # the title's top left; the table under it
TABLE_CHAR_WIDTH = 0.0028
TABLE_CELL_PAD = 0.003
TABLE_ROW_HEIGHT = 0.0055
TABLE_TITLE_GAP = 0.0015
SHEET_CLEARANCE = 0.003  # visible air at the border and the title block
SHEET_INNER_RIGHT = 0.4191
TITLE_BLOCK_TOP = 0.066
BALLOON_MARGIN = 0.012
ISO_NOTE = f"ISOMETRIC VIEW SCALE {ISO_SCALE[0]:g}:{ISO_SCALE[1]:g}"
CHAR_WIDTH = 0.00255  # default-format note text, per character
LINE_PITCH = 0.0046


def table_column_widths(
    header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]
) -> tuple[float, ...]:
    """Each general-table column cut to its longest cell (metres)."""
    return tuple(
        max(len(text) for text in column) * TABLE_CHAR_WIDTH + TABLE_CELL_PAD
        for column in zip(header, *rows, strict=True)
    )


def setup_table_box() -> tuple[float, float, float, float]:
    """The setup table's planned box (x0, y0, x1, y1) under its title."""
    x, top = TABLE_XY
    top -= len(spec.SETUP_TABLE_TITLE.splitlines()) * LINE_PITCH + TABLE_TITLE_GAP
    widths = table_column_widths(spec.SETUP_TABLE_HEADER, spec.SETUP_TABLE_ROWS)
    height = (len(spec.SETUP_TABLE_ROWS) + 1) * TABLE_ROW_HEIGHT
    return (x, top - height, x + sum(widths), top)


_planned = setup_table_box()
if _planned[2] > SHEET_INNER_RIGHT - SHEET_CLEARANCE:
    raise AssertionError("the setup table runs past the right border")
if _planned[1] < TITLE_BLOCK_TOP + SHEET_CLEARANCE:
    raise AssertionError("the setup table runs into the title block")

# --- The 64T blank in phantom (spec.SHOWN_BLANK) ----------------------------------
# Drawn in the views' own sketches as MHA-DT-03-TL-00's sheets draw the
# dividing head (thin phantom, swLineStyles_e 2 / swLineWeights_e 0): its
# edge-view outline, faces and rim, where it seats (sheet 1) and where it
# stands exploded (sheet 2). Its label names it and its facing; the label's
# tip on the face nearer the grip, BLANK_TIP_SHARE of its radius out, clear
# of item 2's and item 1's own ink.
PHANTOM_STYLE, PHANTOM_WIDTH = 2, 0
_BLANK_R = spec.SHOWN_BLANK_OD / 2.0
BLANK_TIP_SHARE = {"sheet 1": 0.85, "sheet 2": -0.6}
Point3 = tuple[float, float, float]


def blank_outline(near_z: float) -> dict[str, tuple[Point3, Point3]]:
    """The blank's edge-view outline, its near face (toward the grip) at
    ``near_z``, assembly mm."""
    far_z = near_z + spec.SHOWN_BLANK_FACE
    r = _BLANK_R
    return {
        "near face": ((0.0, -r, near_z), (0.0, r, near_z)),
        "far face": ((0.0, -r, far_z), (0.0, r, far_z)),
        "top": ((0.0, r, near_z), (0.0, r, far_z)),
        "bottom": ((0.0, -r, near_z), (0.0, -r, far_z)),
    }


def blank_tip_mm(sheet: str, near_z: float) -> Point3:
    """The blank label's tip on its near face, assembly mm."""
    return (0.0, BLANK_TIP_SHARE[sheet] * _BLANK_R, near_z)


# The label beside its tip (side, top over the tip, sheet m): over the blank
# on sheet 1, under the arbor on sheet 2.
BLANK_LABEL_PLACES = {"sheet 1": (1.0, 0.0128), "sheet 2": (1.0, -0.016)}

BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in BOM_COMPONENTS}
# The side view sees every turned edge edge-on, one line across the axis. A
# leader asked on such a line near its end lands ON the end: farm
# 20261113T042822797Z walked the arbor to its thread end's rim at part
# (1.133, 2.966, 65.532), 0.42 mm (sheet) in from the line's end, and the
# leader read back on the end (_assert_leader_lands, limit 0.2 mm); the
# collars' walks that stood far from their ends were not snapped. The oblique
# jig's form (draw_ch_rocker_arm_tl_oblique_jig_assembly: KP08_RIM_DEG,
# STUD_RIM_DEG): a rim point RIM_DEG round from the viewer's +X toward +Y, so
# it stands mid-line, on the viewer's half of a real circular edge. The
# arbor's is the grip step's outer rim (Ø.62 at the grip step, clear of every
# kit part), 7.9 mm (sheet) from either end of its line and 4.8 from the
# standoff's silhouette; the Ø1.00 collar's walk stood 1.7 mm from its line's
# end, so its rim is frozen the same way, on the face its walk found drawn.
RIM_DEG = 30.0


def rim_point(radius: float, z: float) -> tuple[float, float, float]:
    """Part millimetres of the rim of ``radius`` at ``z``, RIM_DEG round."""
    angle = math.radians(RIM_DEG)
    return (radius * math.cos(angle), radius * math.sin(angle), z)


BALLOON_ANCHORS[spec.ARBOR] = BalloonAnchor(
    point_mm=rim_point(arbor.GRIP_DIA / 2.0, arbor.GRIP_LENGTH)
)
_C100 = spec.member(collar.CONFIGURATIONS[1])
BALLOON_ANCHORS[_C100] = BalloonAnchor(
    point_mm=rim_point(
        collar.OD_BY_CONFIGURATION[collar.CONFIGURATIONS[1]] / 2.0, collar.LENGTH
    )
)

# --- Sheet 2: the exploded side view (rule 22) ---------------------------------
# One side view per item at 1:1, each isolated to its item, placed where its
# explode offset lands in item 1's view (the side view prints model z to the
# left, y up). Item 5 stays seated in item 1 (bonded first, steps 1-6). The
# 64T blank's phantom (item 1's view) stands off the thread end by
# EXPLODE_GAP, item 2 the same beyond it, item 6 beyond item 2: the order
# they go on. Items 3 and 4, which take item 2's place per the setup table,
# stand under item 2, item 3 centred under it, item 4 SPARE_SPREAD toward the
# thread end, each SPARE_DROP clear. Assembly mm.
EXPLODED_ORIGIN = (0.193, 0.200)  # item 1's grip end-face centre, sheet m
EXPLODE_GAP = 20.0
SPARE_DROP = 30.0
SPARE_SPREAD = 42.0
EXPLODED_BLANK_Z = arbor.ARBOR_END_Z + EXPLODE_GAP  # its near face
_EXPLODED_ITEM2_Z = EXPLODED_BLANK_Z + spec.SHOWN_BLANK_FACE + EXPLODE_GAP
_ITEM2_MID_Z = _EXPLODED_ITEM2_Z + collar.LENGTH / 2.0
_EXPLODED_NUT_Z = _EXPLODED_ITEM2_Z + collar.LENGTH + EXPLODE_GAP
_R = {
    spec.member(name): collar.OD_BY_CONFIGURATION[name] / 2.0
    for name in collar.CONFIGURATIONS
}
_SPARE_Y = -(_R[KIT_COLLAR] + SPARE_DROP + max(_R[s] for s in SPARES))


def _collar_offset(stem: str, mid_z: float, y: float) -> tuple[float, float, float]:
    """The offset that puts collar ``stem``'s mid-length at ``mid_z``, ``y``."""
    return (0.0, y, mid_z - (spec.POSITIONS[stem][2] + collar.LENGTH / 2.0))


EXPLODE_OFFSETS_MM: dict[str, tuple[float, float, float]] = {
    spec.ARBOR: (0.0, 0.0, 0.0),
    KIT_COLLAR: _collar_offset(KIT_COLLAR, _ITEM2_MID_Z, 0.0),
    spec.NUT: (0.0, 0.0, _EXPLODED_NUT_Z - spec.POSITIONS[spec.NUT][2]),
    SPARES[0]: _collar_offset(SPARES[0], _ITEM2_MID_Z, _SPARE_Y),
    SPARES[1]: _collar_offset(SPARES[1], _ITEM2_MID_Z + SPARE_SPREAD, _SPARE_Y),
}
# The views: item 1's carries item 5; every other item its own.
EXPLODED_VIEWS: dict[str, frozenset[str]] = {
    spec.ARBOR: frozenset({spec.ARBOR, spec.KEY}),
    **{stem: frozenset({stem}) for stem in EXPLODE_OFFSETS_MM if stem != spec.ARBOR},
}
if set().union(*EXPLODED_VIEWS.values()) != set(BOM_COMPONENTS):
    raise AssertionError("the exploded view shows every kit part once")
# Items 3 and 4 carry BOM balloons here, the one view each shows in; the
# stack's items are ballooned on sheet 1 and labelled here by leader.
EXPLODED_BALLOONED = SPARES
EXPLODED_LABELS: dict[str, str] = {
    spec.ARBOR: f"ITEM {spec.BOM_ITEMS[spec.ARBOR]}",
    spec.KEY: (
        f"ITEM {spec.BOM_ITEMS[spec.KEY]}, BONDED IN ITEM {spec.BOM_ITEMS[spec.ARBOR]}"
    ),
    KIT_COLLAR: f"ITEM {spec.BOM_ITEMS[KIT_COLLAR]}",
    spec.NUT: f"ITEM {spec.BOM_ITEMS[spec.NUT]}",
}
# Each leader's tip, seated assembly mm, on a face the view shows.
LABEL_TIPS_MM: dict[str, tuple[float, float, float]] = {
    spec.ARBOR: (0.0, arbor.GRIP_DIA / 4.0, arbor.GRIP_LENGTH / 2.0),
    spec.KEY: (spec.POSITIONS[spec.KEY][0], 0.0, key.END_Z_MM + key.LENGTH / 2.0),
    KIT_COLLAR: (0.0, 0.6 * _R[KIT_COLLAR], spec.BLANK_FACE_Z + collar.LENGTH / 2.0),
    spec.NUT: (0.0, nut.ACROSS_FLATS / 4.0, spec.COLLAR_FAR_Z + nut.THICKNESS / 2.0),
}
# Each label stands wholly to one side of its tip, LABEL_RUN clear, so its
# leader leaves the text's near end and never starts on the text; (side, the
# label's top over its tip, sheet m). All stand above the stack, items 1 and
# 5 toward the head (item 5's over item 1's by more than the layout audit's
# row pitch, farm 20261113T090619426Z: 4.79 mm read as one block), items 2
# and 6 toward the thread, off the blank's phantom. No owned centreline runs
# through the stack: one in item 1's view grew its outline over items 2 and
# 6 and their labels' leaders.
LABEL_RUN = 0.004
TOWARD_HEAD = 1.0
TOWARD_THREAD = -1.0
LABEL_PLACES: dict[str, tuple[float, float]] = {
    spec.ARBOR: (TOWARD_HEAD, 0.022),
    spec.KEY: (TOWARD_HEAD, 0.050),
    KIT_COLLAR: (TOWARD_THREAD, 0.0227),
    spec.NUT: (TOWARD_THREAD, 0.023),
}
EXPLODED_CAPTION = "\n".join(
    (
        f"EXPLODED VIEW, {arbor.crank.TEETH}T SETUP",
        f"ITEM {spec.BOM_ITEMS[SPARES[0]]} OR {spec.BOM_ITEMS[SPARES[1]]} TAKES "
        f"ITEM {spec.BOM_ITEMS[KIT_COLLAR]}'S PLACE PER THE SETUP TABLE (SHEET 1)",
    )
)
CAPTION_XY = (0.020, 0.090)
STEPS_XY = (0.219, 0.262)

Box = tuple[float, float, float, float]


def nominal_sheet_point(point_mm: tuple[float, float, float]) -> tuple[float, float]:
    """Where item 1's exploded view (model z left, y up, 1:1) prints an
    assembly point, sheet m; the build reads the real projection."""
    s = EXPLODED_SCALE[0] / EXPLODED_SCALE[1] / 1000.0
    return (EXPLODED_ORIGIN[0] - point_mm[2] * s, EXPLODED_ORIGIN[1] + point_mm[1] * s)


def label_box(text: str, upper_left: tuple[float, float]) -> Box:
    """A note's estimated box (x0, y0, x1, y1) from its upper-left corner."""
    lines = text.splitlines()
    x, y = upper_left
    return (x, y - len(lines) * LINE_PITCH, x + max(map(len, lines)) * CHAR_WIDTH, y)


def beside(
    text: str, tip: tuple[float, float], side: float, rise: float
) -> tuple[float, float]:
    """A label's upper-left corner, sheet m, wholly to ``side`` of its tip,
    LABEL_RUN clear, its top ``rise`` over the tip."""
    x0, _y0, x1, _y1 = label_box(text, (0.0, 0.0))
    x = tip[0] + LABEL_RUN if side > 0 else tip[0] - LABEL_RUN - (x1 - x0)
    return (x, tip[1] + rise)


def label_position(stem: str, tip: tuple[float, float]) -> tuple[float, float]:
    """Label ``stem``'s upper-left corner, sheet m, wholly beside its tip."""
    return beside(EXPLODED_LABELS[stem], tip, *LABEL_PLACES[stem])


def blank_label_position(sheet: str, tip: tuple[float, float]) -> tuple[float, float]:
    """The blank label's upper-left corner on ``sheet``, sheet m."""
    return beside(spec.SHOWN_BLANK_LABEL, tip, *BLANK_LABEL_PLACES[sheet])


def _view_stem(stem: str) -> str:
    """The exploded view that shows ``stem``."""
    (owner,) = (view for view, stems in EXPLODED_VIEWS.items() if stem in stems)
    return owner


def _add_note(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> None:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the arbor-kit {label}")
    printed = (
        str(_early_bound(note, "INote").GetText() or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if printed != text:
        raise RuntimeError(f"arbor-kit {label} printed as {printed!r}")


def _place_setup_table(adapter: Any) -> None:
    """The setup table's title, then its native general table under it, every
    cell read back; its read-back box must clear the border and the title
    block (draw_ch_rocker_arm_tl_oblique_jig_assembly._place_general_table)."""
    label = "arbor-kit setup table"
    _activate_sheet(adapter, SHEET_NAMES[0])
    _add_note(adapter, spec.SETUP_TABLE_TITLE, TABLE_XY, label=f"{label} title")
    header, rows = spec.SETUP_TABLE_HEADER, spec.SETUP_TABLE_ROWS
    x, _y0, _x1, top = setup_table_box()
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
    if box[2] > SHEET_INNER_RIGHT - SHEET_CLEARANCE:
        raise RuntimeError(f"{label}: runs past the right border at {box!r}")
    if box[1] < TITLE_BLOCK_TOP + SHEET_CLEARANCE:
        raise RuntimeError(f"{label}: runs into the title block at {box!r}")


def _bom_items(table: Any, configuration: str) -> dict[str, str]:
    """Each family's row, read through its native components: the steps and
    the setup table cite the spec's item numbers, so the BOM must number the
    rows in BOM_ORDER."""
    rows = bom_row_identities(
        table,
        configuration=configuration,
        component_identities=dict(spec.COMPONENT_IDENTITIES),
    )
    printed = {stem: str(row) for stem, row in rows.items()}
    if printed != spec.BOM_ITEMS:
        raise RuntimeError(
            f"arbor-kit BOM numbers its rows {printed!r}, not {spec.BOM_ITEMS!r}"
        )
    return printed


def _bom_feature_name(table: Any) -> str:
    """The inserted BOM's feature name, the key a view links to it by
    (draw_ch_rocker_arm_tl_oblique_jig_assembly's)."""
    bom = _early_bound(table, "IBomTableAnnotation")
    feature = _early_bound(bom.BomFeature, "IBomFeature")
    name = str(feature.Name or "")
    if not name:
        raise RuntimeError("arbor-kit BOM feature has no name")
    return name


def _link_view_to_bom(view: Any, bom_name: str, *, label: str) -> None:
    """Number a view's balloons from the BOM another view is the parent of
    (draw_ch_rocker_arm_tl_oblique_jig_assembly's), read back."""
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
    point_mm: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``view`` so the model point lands on ``target`` (sheet m)
    (draw_dt_cone_tip_gear_tl_cutter_assembly's)."""
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
    point_mm: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    point = tuple(value / 1000.0 for value in point_mm)
    (here,) = model_points_in_view(adapter, view, [point], label=label)
    if math.dist(here, target) > 1e-4:
        raise RuntimeError(f"settled {label} sits at {here!r}, not {target!r}")


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate arbor-kit sheet {name!r}")
    actual = str(_early_bound(ddoc.GetCurrentSheet(), "ISheet").GetName() or "")
    if actual != name:
        raise RuntimeError(f"arbor-kit sheet is {actual!r}, expected {name!r}")


def _draw_blank(
    adapter: Any, view: Any, sheet: str, near_z: float
) -> Callable[[], None]:
    """The 64T blank's phantom outline in ``view``'s sketch, its near face at
    ``near_z`` (assembly mm), and its label; returns the settled check."""
    label = f"arbor-kit {sheet} 64T blank"
    lines = blank_outline(near_z)
    keys = list(lines)
    sheet_points = model_points_in_view(
        adapter,
        view,
        [
            tuple(value / 1000.0 for value in point)
            for key in keys
            for point in lines[key]
        ]
        + [tuple(value / 1000.0 for value in blank_tip_mm(sheet, near_z))],
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
        spec.SHOWN_BLANK_LABEL,
        text_xy=blank_label_position(sheet, tip),
        attach_xy=tip,
        label=f"{label} label",
        view=view,
    )
    return lambda: placed("settled")


def _place_sheet(adapter: Any) -> tuple[Callable[[], None], list[BalloonLanding], str]:
    """Sheet 1: the working pose's side view and isometric, the parts list,
    the balloons and the setup table. Returns its settled check, its
    balloons and the BOM's feature name."""
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_ORIGIN, scale=SIDE_SCALE)
    set_hidden_lines_removed(adapter, side)
    configuration = apply_view_configuration(adapter, side, label="arbor kit *Right")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_high_quality_shaded_with_edges(adapter, iso, label="arbor kit isometric")
    apply_view_configuration(
        adapter, iso, role=ViewRole.FULL_DETAIL, label="arbor kit *Isometric"
    )
    # The BOM lists the configuration, every row, whatever a view shows.
    table = insert_bom_table(
        adapter,
        side,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=dict(spec.BOM_DESCRIPTIONS),
        component_identities=dict(spec.COMPONENT_IDENTITIES),
        part_number_property="Number",
        label="arbor kit",
    )
    items = _bom_items(table, configuration)
    working = frozenset(WORKING)
    side = isolate_drawing_view_components(
        adapter, side, visible_stems=working, label="arbor kit working side view"
    )
    _move_model_point(
        adapter, side, (0.0, 0.0, 0.0), SIDE_ORIGIN, label="arbor kit side view"
    )
    iso = isolate_drawing_view_components(
        adapter, iso, visible_stems=working, label="arbor kit working isometric"
    )
    _move_model_point(
        adapter, iso, ISO_POINT_MM, ISO_CENTER, label="arbor kit isometric"
    )
    assert_full_detail_view(adapter, label="arbor kit")
    landings = add_component_bom_balloons(
        adapter,
        side,
        items=tuple((stem, items[stem]) for stem in WORKING),
        anchors=BALLOON_ANCHORS,
        label="arbor-kit working pose balloons",
        margin=BALLOON_MARGIN,
        explode_offsets={},
    )
    if len(landings) != len(WORKING):
        raise RuntimeError(
            f"arbor kit side view carries {len(landings)} balloons, "
            f"expected {len(WORKING)}"
        )
    _place_setup_table(adapter)
    _add_note(adapter, ISO_NOTE, ISO_NOTE_XY, label="isometric scale note")
    blank_settled = _draw_blank(adapter, side, "sheet 1", arbor.SHOULDER_Z)

    def settled() -> None:
        _assert_at(adapter, side, (0.0, 0.0, 0.0), SIDE_ORIGIN, label="side view")
        _assert_at(adapter, iso, ISO_POINT_MM, ISO_CENTER, label="isometric")
        blank_settled()

    return settled, landings, _bom_feature_name(table)


def _item_view(adapter: Any, owner: str, target: tuple[float, float]) -> Any:
    """A side view of ``EXPLODED_VIEWS[owner]`` alone, its assembly origin
    moved onto ``target`` (sheet m)."""
    label = f"arbor-kit exploded {owner}"
    view = place_view(adapter, str(SOURCE), "*Right", *target, scale=EXPLODED_SCALE)
    set_hidden_lines_removed(adapter, view)
    apply_view_configuration(adapter, view, label=label)
    view = isolate_drawing_view_components(
        adapter, view, visible_stems=EXPLODED_VIEWS[owner], label=label
    )
    _move_model_point(adapter, view, (0.0, 0.0, 0.0), target, label=label)
    return view


def _place_exploded_sheet(
    adapter: Any, bom_name: str
) -> tuple[Callable[[], None], list[BalloonLanding]]:
    """Sheet 2: item 1 (with item 5) at EXPLODED_ORIGIN, every other item
    where its explode offset lands in item 1's view; items 3 and 4
    ballooned, the stack labelled; the caption and the steps."""
    label = "arbor-kit exploded view"
    _activate_sheet(adapter, SHEET_NAMES[1])
    targets = {spec.ARBOR: EXPLODED_ORIGIN}
    views = {spec.ARBOR: _item_view(adapter, spec.ARBOR, EXPLODED_ORIGIN)}
    loose = tuple(stem for stem in EXPLODED_VIEWS if stem != spec.ARBOR)
    targets.update(
        zip(
            loose,
            model_points_in_view(
                adapter,
                views[spec.ARBOR],
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
            items=((stem, spec.BOM_ITEMS[stem]),),
            anchors=BALLOON_ANCHORS,
            label=f"{label} {stem} balloon",
            margin=BALLOON_MARGIN,
            explode_offsets={},
        )
    blank_settled = _draw_blank(adapter, views[spec.ARBOR], "sheet 2", EXPLODED_BLANK_Z)
    for stem, text in EXPLODED_LABELS.items():
        owner = _view_stem(stem)
        (tip,) = model_points_in_view(
            adapter,
            views[owner],
            [tuple(value / 1000.0 for value in LABEL_TIPS_MM[stem])],
            label=f"{label} {stem} label tip",
        )
        add_leader_note(
            adapter,
            text,
            text_xy=label_position(stem, tip),
            attach_xy=tip,
            label=f"{label}: {text}",
            view=views[owner],
        )
    _activate_sheet(adapter, SHEET_NAMES[1])
    for text, xy, note_label in (
        (EXPLODED_CAPTION, CAPTION_XY, "exploded view caption"),
        (spec.ASSEMBLY_STEPS, STEPS_XY, "fitting steps"),
    ):
        _add_note(adapter, text, xy, label=note_label)

    def settled() -> None:
        for stem, view in views.items():
            _assert_at(
                adapter, view, (0.0, 0.0, 0.0), targets[stem], label=f"{label} {stem}"
            )
        blank_settled()

    return settled, landings


@_telemetry.traced("drawing.dt_cone_gear_tl_arbor_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open arbor-kit drawing source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        _early_bound(adapter.currentModel, "IModelDoc2"),
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != DRAWING_NUMBER:
        raise RuntimeError(
            f"arbor-kit source Number {properties['Number']!r} != {DRAWING_NUMBER!r}"
        )
    new_project_drawing(
        adapter, layout=SPEC.layout, scale=SHEET_SCALE, unit=CONTRACT.drawing_unit
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="arbor-kit package")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    for name in SHEET_NAMES:
        _activate_sheet(adapter, name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        if not sheet.SetScale(*SHEET_SCALES[name], False, False):
            raise RuntimeError(f"failed to set arbor-kit sheet scale: {name}")
    _activate_sheet(adapter, SHEET_NAMES[0])
    sheet_settled, landings, bom_name = _place_sheet(adapter)
    exploded_settled, exploded_landings = _place_exploded_sheet(adapter, bom_name)

    def settled() -> None:
        assert_balloon_landings(adapter, [*landings, *exploded_landings])
        sheet_settled()
        exploded_settled()

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Keyed Cutting Arbor Kit Assembly Drawing",
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
