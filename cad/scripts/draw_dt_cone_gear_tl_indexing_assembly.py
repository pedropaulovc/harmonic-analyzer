r"""Create the cone-gear shop kit's fitter sheets (MHA-DT-03-TL-00).

The kit is the custom index plate (item 1, MHA-DT-03-TL-01) on the owner's
PM BS-0 dividing head, which is shop equipment and is not modelled, and the
tip gears' phasing comb (item 2, MHA-DT-03-TL-02), which MHA-DT-00 step 1
fits, not this sheet. The sheet shows the plate face (countersunk side, the
side that faces out on the head) and the comb under it with their balloons,
the edge view and the shaded isometric, the BOM, the plate's fitting steps
and checks, and the indexing table for the three cone gears the plate exists
for. Hole-circle counts, tooth counts and the worm ratio come from
``dt_cone_gear_tl_index_plate_spec``; this recipe only lays the sheet out
and never edits the source assembly.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any, Callable

import _config
import _telemetry
import dt_cone_gear_tl_index_plate_spec as plate
import dt_cone_gear_tl_phasing_comb_spec as comb
from _assembly_contract import assembly_contract
from _check import check
from _com import _early_bound
from _drawing_balloons import (
    BalloonAnchor,
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
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
from _drawing_tables import insert_bom_table
from _drawing_view_configuration import (
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from _transgear_zone_line import require_placed, sketch_lines
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_indexing_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the indexing-kit sheet must remain landscape")

CONTRACT = assembly_contract("dt-cone-gear-tl-indexing")
DRAWING_NUMBER = CONTRACT.number
SHEET_SCALE = (1.0, 1.0)
ISO_SCALE = (1.0, 2.0)
# Sheet 1 carries the views, BOM, steps, checks and indexing table; sheet 2
# the exploded view (rule 22), with room for its labels.
SHEET_NAMES = ("ASSEMBLY", "EXPLODED VIEW")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALES = {name: SHEET_SCALE for name in SHEET_NAMES}
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
SHEET_INNER_BORDER = (
    0.0127,
    0.0127,
    _TEMPLATE.width_m - 0.0127,
    _TEMPLATE.height_m - 0.0127,
)

# Sheet metres. The plate face and edge sit top-left at full size; the
# isometric sits below them, clear of the title block (x >= 0.216 m,
# y <= 0.066 m); the BOM and the notes fill the right half above it.
FRONT_CENTER = (0.085, 0.190)
RIGHT_CENTER = (0.170, 0.190)
ISO_CENTER = (0.085, 0.072)
ISO_NOTE_XY = (0.050, 0.046)
# The BOM's template columns print 196.6 mm wide (farm r2 layout audit), so
# its left edge sits close enough to the views to end inside the right border.
BOM_ANCHOR = (0.219, 0.262)
# The BOM's two item rows end above the steps; the steps' eleven lines (4.5
# mm a line) above the checks, the checks above the indexing table, and the
# comb's line under the table.
STEPS_XY = (0.219, 0.228)
CHECKS_XY = (0.219, 0.171)
TABLE_XY = (0.219, 0.138)
COMB_NOTE_XY = (0.219, 0.110)
BALLOON_MARGIN = 0.012

PLATE = plate.PART_NAME
COMB = comb.PART_NAME
BOM_COMPONENTS = (PLATE, COMB)
BOM_ITEMS = {PLATE: "1", COMB: "2"}
BOM_DESCRIPTIONS = {
    PLATE: "BS-0 INDEX PLATE, "
    + "/".join(str(count) for count in sorted(plate.RING_COUNTS))
    + " HOLES",
    COMB: "TIP GEAR PHASING COMB, T030-T006",
}
BOM_COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    PLATE: (PLATE, None),
    COMB: (COMB, None),
}
BALLOON_ANCHORS = {PLATE: BalloonAnchor(), COMB: BalloonAnchor()}
# Item 2 has no fitting here: the drive train's bonding step engages it.
COMB_NOTE = "ITEM 2 IS FITTED BY MHA-DT-00 STEP 1, NOT ON THE HEAD."

# Steps 1 and 4 reuse the head's own plate screws without a lock: owner
# ruling RV-01 (the kit's machinist_exceptions) accepts that joint. The head
# and its screws are shop equipment, named as such and not parts-list rows
# (RV-02). A step does one thing (rule 22).
HEAD = "PM BS-0 DIVIDING HEAD (SHOP EQUIPMENT)"
ASSEMBLY_STEPS = "\n".join(
    (
        f"FITTING ON THE {HEAD}",
        "1. REMOVE THE HEAD'S STOCK INDEX PLATE; KEEP ITS THREE #8 FLAT HEAD",
        "   SCREWS.",
        "2. SLIDE ITEM 1 ONTO THE HEAD'S PLATE HUB, COUNTERSUNK FACE OUT",
        "   (SHEET 2).",
        "3. TURN ITEM 1 UNTIL ITS THREE COUNTERSINKS LINE UP WITH THE",
        "   HEAD'S PLATE-SCREW TAPS.",
        "4. FIT THE SCREWS FROM STEP 1 AND TIGHTEN THEM EVENLY.",
        "5. SET THE CRANK PIN ON THE CIRCLE THE INDEXING TABLE NAMES.",
        "6. SET THE SECTOR ARMS TO SPAN THE PIN'S HOLE PLUS THE TABLE'S",
        "   HOLE SPACES PER TOOTH (10 SPACES = 11 HOLES).",
    )
)
ASSEMBLY_CHECKS = "\n".join(
    (
        "CHECKS",
        "1. ITEM 1 SITS FLAT ON THE HEAD; NO SCREW HEAD STANDS PROUD.",
        "2. THE INDEX PIN DROPS INTO EVERY HOLE OF THE CHOSEN CIRCLE.",
        "3. INDEXING EVERY TOOTH OF ONE BLANK TURN BRINGS THE PIN BACK",
        "   TO ITS STARTING HOLE.",
    )
)

# --- sheet 2: the exploded view ----------------------------------------------
# Item 1's edge view at 1:1 with what it fits to, which the kit does not
# supply and the model does not hold: the head's plate face and hub in
# phantom on its back-face side, and the head's own #8 flat head plate
# screws drawn off its countersunk face, each on its tapped-hole axis. Model
# millimetres in the plate's frame (part frame = kit frame): the plate spans
# z 0..THICKNESS, its countersunk face at +Z. The head and screw outlines are
# schematic: no size on them is a requirement.
EXPLODED_CENTER = (0.200, 0.160)
HEAD_GAP = 15.0  # plate back face to the hub's end, as exploded
SCREW_GAP = 15.0  # countersunk face to the screw tips, as exploded
HUB_LENGTH = plate.THICKNESS
HEAD_DEPTH = 25.0
HEAD_FACE_Z = -HEAD_GAP - HUB_LENGTH
HEAD_BACK_Z = HEAD_FACE_Z - HEAD_DEPTH
HEAD_HALF = plate.PLATE_DIA / 2.0
HUB_R = plate.BORE_DIA / 2.0
SCREW_LENGTH = 0.375 * plate.INCH
SCREW_R = plate.MOUNT_SCREW_BODY_DIA / 2.0
SCREW_HEAD_R = plate.MOUNT_HEAD_DIA_MAX / 2.0
SCREW_HEAD_H = (SCREW_HEAD_R - SCREW_R) / math.tan(math.radians(plate.CSK_ANGLE / 2.0))
SCREW_TIP_Z = plate.THICKNESS + SCREW_GAP
SCREW_CONE_Z = SCREW_TIP_Z + SCREW_LENGTH - SCREW_HEAD_H
SCREW_TOP_Z = SCREW_TIP_Z + SCREW_LENGTH
AXIS_OVERRUN = 3.0
TAP_AXIS_DEPTH = 10.0
# Line fonts (swLineStyles_e / swLineWeights_e): the head in thin phantom,
# the screws as visible outlines, their axes as thin centre lines.
PHANTOM_STYLE, PHANTOM_WIDTH = 2, 0
SCREW_STYLE, SCREW_WIDTH = 0, 1
AXIS_STYLE, AXIS_WIDTH = 4, 0


def mount_axis_heights() -> tuple[float, ...]:
    """The distinct heights (model y, mm) of the three mount-hole axes as the
    edge view sees them: 150 and 30 degrees coincide, 270 stands alone."""
    return tuple(
        sorted(
            {
                round(
                    plate.MOUNT_PCD
                    / 2.0
                    * math.sin(
                        math.radians(
                            plate.MOUNT_SEED_DEG + 360.0 * k / plate.MOUNT_COUNT
                        )
                    ),
                    6,
                )
                for k in range(plate.MOUNT_COUNT)
            }
        )
    )


Point3 = tuple[float, float, float]


def _yz(y: float, z: float) -> Point3:
    return (0.0, y, z)


def exploded_lines() -> dict[str, dict[str, tuple[Point3, Point3]]]:
    """Every line the exploded view adds, by font, model mm (x, y, z)."""
    h, f, b = HEAD_HALF, HEAD_FACE_Z, HEAD_BACK_Z
    hub_end = -HEAD_GAP
    phantom = {
        "head face": (_yz(-h, f), _yz(h, f)),
        "head back": (_yz(-h, b), _yz(h, b)),
        "head top": (_yz(h, b), _yz(h, f)),
        "head bottom": (_yz(-h, b), _yz(-h, f)),
        "hub top": (_yz(HUB_R, f), _yz(HUB_R, hub_end)),
        "hub bottom": (_yz(-HUB_R, f), _yz(-HUB_R, hub_end)),
        "hub end": (_yz(-HUB_R, hub_end), _yz(HUB_R, hub_end)),
    }
    screws: dict[str, tuple[Point3, Point3]] = {}
    axes = {
        "spindle axis": (
            _yz(0.0, b - AXIS_OVERRUN),
            _yz(0.0, plate.THICKNESS + AXIS_OVERRUN),
        )
    }
    r, rh, tip, cone, top = (
        SCREW_R,
        SCREW_HEAD_R,
        SCREW_TIP_Z,
        SCREW_CONE_Z,
        SCREW_TOP_Z,
    )
    for index, y in enumerate(mount_axis_heights()):
        name = f"screw {index + 1}"
        screws |= {
            f"{name} shank top": (_yz(y + r, tip), _yz(y + r, cone)),
            f"{name} shank bottom": (_yz(y - r, tip), _yz(y - r, cone)),
            f"{name} tip": (_yz(y - r, tip), _yz(y + r, tip)),
            f"{name} head flank top": (_yz(y + r, cone), _yz(y + rh, top)),
            f"{name} head flank bottom": (_yz(y - r, cone), _yz(y - rh, top)),
            f"{name} head top": (_yz(y - rh, top), _yz(y + rh, top)),
        }
        axes[f"{name} axis"] = (
            _yz(y, f - TAP_AXIS_DEPTH),
            _yz(y, top + AXIS_OVERRUN),
        )
    return {"phantom": phantom, "screw": screws, "axis": axes}


# Labels: what each leader names and the model point its tip lands on.
HEAD_LABEL = "PM BS-0 DIVIDING HEAD\n(SHOP EQUIPMENT)"
HUB_LABEL = "HEAD'S PLATE HUB"
SCREW_LABEL = "3X #8 FLAT HEAD PLATE SCREW\nOF THE HEAD (SHOP EQUIPMENT)"
PLATE_LABEL = "ITEM 1\nCOUNTERSUNK FACE OUT"
EXPLODED_CAPTION = "EXPLODED VIEW - FITTING STEPS 1-4 ON SHEET 1"
LABEL_TIPS: dict[str, Point3] = {
    HEAD_LABEL: _yz(-HEAD_HALF, (HEAD_FACE_Z + HEAD_BACK_Z) / 2.0),
    HUB_LABEL: _yz(HUB_R, (HEAD_FACE_Z - HEAD_GAP) / 2.0),
    SCREW_LABEL: _yz(mount_axis_heights()[0] - SCREW_HEAD_R, SCREW_TOP_Z),
    PLATE_LABEL: _yz(0.4 * HEAD_HALF, plate.THICKNESS),
}
# Sheet metres: labels stand this far above the head's top or below its
# bottom; a label's text runs away from the plate from its leader end.
LABEL_RISE = 0.012
CHAR_WIDTH = 0.00255  # default-format note text, per character
LINE_PITCH = 0.0046
LEADER_END_INSET = 0.003
PLATE_LABEL_SET_BACK = 0.025
CAPTION_GAP = 0.010


def _indexing_rows() -> tuple[str, ...]:
    """One row per cone gear: no full crank turns, ``holes`` on ``count``."""
    rows = []
    for count in sorted(plate.RING_COUNTS):
        teeth = plate.RING_TEETH[count]
        holes, remainder = divmod(plate.WORM_RATIO * count, teeth)
        if remainder or holes >= count:
            raise AssertionError(f"{teeth}T does not index on the {count}-hole circle")
        rows.append(f"{teeth}T: {holes} HOLE SPACES ON THE {count}-HOLE CIRCLE")
    return tuple(rows)


INDEXING_TABLE = "\n".join(
    (
        f"INDEXING TABLE ({plate.WORM_RATIO}:1 WORM, NO FULL CRANK TURNS)",
        *_indexing_rows(),
    )
)
ISO_NOTE = f"ISOMETRIC VIEW SCALE {ISO_SCALE[0]:g}:{ISO_SCALE[1]:g}"


def _add_note(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> None:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the indexing-kit {label}")
    printed = (
        str(_early_bound(note, "INote").GetText() or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if printed != text:
        raise RuntimeError(f"indexing-kit {label} printed as {printed!r}")


def _bom_items(adapter: Any, table: Any) -> dict[str, str]:
    """Each part's ITEM NO. as the BOM prints it, read off its PART NUMBER
    row; the steps cite item 1 and the comb's line item 2."""
    table = _early_bound(table, "ITableAnnotation")

    def cell(row: int, column: int) -> str:
        return str(
            adapter._attempt(lambda: table.DisplayedText2(row, column, True)) or ""
        ).strip()

    header = [cell(0, column).upper() for column in range(int(table.ColumnCount))]
    items = [index for index, text in enumerate(header) if text.startswith("ITEM NO")]
    numbers = [index for index, text in enumerate(header) if text == "PART NUMBER"]
    if (
        int(table.RowCount) != 1 + len(BOM_COMPONENTS)
        or len(items) != 1
        or len(numbers) != 1
    ):
        raise RuntimeError(
            f"indexing-kit BOM is not {len(BOM_COMPONENTS)} item rows: {header!r}"
        )
    stems = {
        str(_config.parts("dt-cone-gear-tl-index-plate")["number"]): PLATE,
        comb.PART_NUMBER: COMB,
    }
    printed = {
        stems.get(cell(row, numbers[0]), cell(row, numbers[0])): cell(row, items[0])
        for row in range(1, int(table.RowCount))
    }
    if printed != BOM_ITEMS:
        raise RuntimeError(
            f"indexing-kit BOM numbers its parts {printed!r}, not {BOM_ITEMS!r}"
        )
    return printed


def _place_sheet(adapter: Any) -> Any:
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=SHEET_SCALE)
    for view, name in ((front, "*Front"), (right, "*Right")):
        set_hidden_lines_removed(adapter, view)
        apply_view_configuration(adapter, view, label=f"indexing kit {name}")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_high_quality_shaded_with_edges(adapter, iso, label="indexing kit isometric")
    apply_view_configuration(
        adapter, iso, role=ViewRole.FULL_DETAIL, label="indexing kit *Isometric"
    )
    assert_full_detail_view(adapter, label="indexing kit")

    table = insert_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        component_identities=BOM_COMPONENT_IDENTITIES,
        part_number_property="Number",
        label="indexing kit",
    )
    items = _bom_items(adapter, table)
    landings = add_component_bom_balloons(
        adapter,
        front,
        items=tuple((stem, items[stem]) for stem in BOM_COMPONENTS),
        anchors=BALLOON_ANCHORS,
        label="indexing-kit BOM coverage",
        margin=BALLOON_MARGIN,
        explode_offsets={},
    )
    if len(landings) != len(BOM_COMPONENTS):
        raise RuntimeError(
            f"indexing kit carries {len(landings)} balloons, expected {len(BOM_COMPONENTS)}"
        )
    for text, xy, label in (
        (ASSEMBLY_STEPS, STEPS_XY, "fitting steps"),
        (ASSEMBLY_CHECKS, CHECKS_XY, "checks"),
        (INDEXING_TABLE, TABLE_XY, "indexing table"),
        (COMB_NOTE, COMB_NOTE_XY, "phasing comb note"),
        (ISO_NOTE, ISO_NOTE_XY, "isometric scale note"),
    ):
        _add_note(adapter, text, xy, label=label)
    return lambda: assert_balloon_landings(adapter, landings)


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate indexing-kit sheet {name!r}")
    actual = str(_early_bound(ddoc.GetCurrentSheet(), "ISheet").GetName() or "")
    if actual != name:
        raise RuntimeError(f"indexing-kit sheet is {actual!r}, expected {name!r}")


Box = tuple[float, float, float, float]


def _text_size(text: str) -> tuple[float, float]:
    lines = text.splitlines()
    return max(map(len, lines)) * CHAR_WIDTH, len(lines) * LINE_PITCH


def exploded_label_positions(
    tips: dict[str, tuple[float, float]],
    head_top_y: float,
) -> dict[str, tuple[float, float]]:
    """Each label's upper-left corner (sheet metres) from its leader tip on
    the placed view. ``tips`` holds every LABEL_TIPS key; the head side is
    read from them, so the layout follows the view's own projection: the
    head and hub labels run toward the head, the screw and plate labels
    away from it, the head and screw labels under the head's bottom, the
    hub and plate labels over its top."""
    side = math.copysign(1.0, tips[HEAD_LABEL][0] - tips[PLATE_LABEL][0])

    def run(text: str, x: float, toward_head: bool) -> float:
        width = _text_size(text)[0]
        if (side > 0) == toward_head:
            return x - LEADER_END_INSET
        return x + LEADER_END_INSET - width

    below = tips[HEAD_LABEL][1] - LABEL_RISE
    hub_top = head_top_y + LABEL_RISE + _text_size(HUB_LABEL)[1]
    plate_top = head_top_y + LABEL_RISE + _text_size(PLATE_LABEL)[1]
    plate_x = tips[PLATE_LABEL][0] - side * PLATE_LABEL_SET_BACK
    caption_width = _text_size(EXPLODED_CAPTION)[0]
    return {
        HEAD_LABEL: (run(HEAD_LABEL, tips[HEAD_LABEL][0], True), below),
        SCREW_LABEL: (run(SCREW_LABEL, tips[SCREW_LABEL][0], False), below),
        HUB_LABEL: (run(HUB_LABEL, tips[HUB_LABEL][0], True), hub_top),
        PLATE_LABEL: (run(PLATE_LABEL, plate_x, False), plate_top),
        EXPLODED_CAPTION: (
            tips[PLATE_LABEL][0] - caption_width / 2.0,
            below - _text_size(SCREW_LABEL)[1] - CAPTION_GAP,
        ),
    }


def label_boxes(positions: dict[str, tuple[float, float]]) -> dict[str, Box]:
    """Each label's estimated box (x0, y0, x1, y1) from its upper-left."""
    boxes = {}
    for text, (x, y) in positions.items():
        width, height = _text_size(text)
        boxes[text] = (x, y - height, x + width, y)
    return boxes


def _place_exploded_sheet(adapter: Any) -> Callable[[], None]:
    """Sheet 2: item 1's edge view with the head, its hub and its screws
    drawn in place, exploded, and labelled (rule 22). Item 2 is not fitted
    here, so the view shows item 1 alone."""
    label = "indexing-kit exploded view"
    _activate_sheet(adapter, SHEET_NAMES[1])
    view = place_view(
        adapter, str(SOURCE), "*Right", *EXPLODED_CENTER, scale=SHEET_SCALE
    )
    set_hidden_lines_removed(adapter, view)
    apply_view_configuration(adapter, view, label=label)
    view = isolate_drawing_view_components(
        adapter, view, visible_stems=frozenset({PLATE}), label=label
    )
    groups = exploded_lines()
    fonts = {
        "phantom": (PHANTOM_STYLE, PHANTOM_WIDTH),
        "screw": (SCREW_STYLE, SCREW_WIDTH),
        "axis": (AXIS_STYLE, AXIS_WIDTH),
    }
    sketched = {}
    for group, lines in groups.items():
        keys = list(lines)
        sheet = model_points_in_view(
            adapter,
            view,
            [
                tuple(value / 1000.0 for value in point)
                for key in keys
                for point in lines[key]
            ],
            label=f"{label} {group}",
        )
        style, width = fonts[group]
        sketched[group] = sketch_lines(
            adapter,
            view,
            {key: (sheet[2 * i], sheet[2 * i + 1]) for i, key in enumerate(keys)},
            style=style,
            width=width,
            label=f"{label} {group}",
        )
    rebuild_drawing(adapter, label=label)

    def assert_lines(stage: str) -> None:
        for group, lines in sketched.items():
            style, width = fonts[group]
            require_placed(
                adapter,
                lines,
                style=style,
                width=width,
                label=f"{label} {group}",
                stage=stage,
            )

    assert_lines("drawn")
    texts = list(LABEL_TIPS)
    head_top = _yz(HEAD_HALF, (HEAD_FACE_Z + HEAD_BACK_Z) / 2.0)
    points = model_points_in_view(
        adapter,
        view,
        [
            tuple(value / 1000.0 for value in point)
            for point in (*(LABEL_TIPS[text] for text in texts), head_top)
        ],
        label=f"{label} label tips",
    )
    tips = dict(zip(texts, points[:-1], strict=True))
    positions = exploded_label_positions(tips, points[-1][1])
    boxes = label_boxes(positions)
    for text, box in boxes.items():
        x0, y0, x1, y1 = box
        if (
            x0 < SHEET_INNER_BORDER[0]
            or x1 > SHEET_INNER_BORDER[2]
            or (y0 < SHEET_INNER_BORDER[1] or y1 > SHEET_INNER_BORDER[3])
        ):
            raise RuntimeError(f"{label}: {text!r} would leave the border at {box!r}")
    for text in texts:
        add_leader_note(
            adapter,
            text,
            text_xy=positions[text],
            attach_xy=tips[text],
            label=f"{label}: {text.splitlines()[0]}",
            view=view,
        )
    _activate_sheet(adapter, SHEET_NAMES[1])
    _add_note(adapter, EXPLODED_CAPTION, positions[EXPLODED_CAPTION], label="caption")
    return lambda: assert_lines("settled")


@_telemetry.traced("drawing.dt_cone_gear_tl_indexing_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open indexing-kit drawing source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        _early_bound(adapter.currentModel, "IModelDoc2"),
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != DRAWING_NUMBER:
        raise RuntimeError(
            f"indexing-kit source Number {properties['Number']!r} != {DRAWING_NUMBER!r}"
        )
    new_project_drawing(
        adapter, layout=SPEC.layout, scale=SHEET_SCALE, unit=CONTRACT.drawing_unit
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="indexing kit package")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    for name in SHEET_NAMES:
        _activate_sheet(adapter, name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        if not sheet.SetScale(*SHEET_SCALES[name], False, False):
            raise RuntimeError(f"failed to set indexing-kit sheet scale: {name}")
    _activate_sheet(adapter, SHEET_NAMES[0])
    sheet_settled = _place_sheet(adapter)
    exploded_settled = _place_exploded_sheet(adapter)

    def settled() -> None:
        sheet_settled()
        exploded_settled()

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Cone Gear Indexing Kit Assembly Drawing",
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
