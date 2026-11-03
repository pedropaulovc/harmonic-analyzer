r"""Create the one-sheet cone-gear indexing-kit fitter sheet (MHA-DT-03-TL-00).

The kit is the custom index plate (item 1, MHA-DT-03-TL-01) on the owner's
PM BS-0 dividing head, which is not modelled. The sheet shows the plate face
(countersunk side, the side that faces out on the head) with its balloon, the
edge view and the shaded isometric, the one-row BOM, the fitting steps and
checks, and the indexing table for the three cone gears the plate exists for.
Hole-circle counts, tooth counts and the worm ratio come from
``dt_cone_gear_tl_index_plate_spec``; this recipe only lays the sheet out and
never edits the source assembly. Machinist review is OFF while the plate's
sizes are best guesses (#2157).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
import dt_cone_gear_tl_index_plate_spec as plate
from _assembly_contract import assembly_contract
from _check import check
from _com import _early_bound
from _drawing_balloons import (
    BalloonAnchor,
    add_component_bom_balloons,
    assert_balloon_landings,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_high_quality_shaded_with_edges,
)
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _drawing_tables import insert_bom_table
from _drawing_view_configuration import (
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
)
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

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

# Sheet metres. The plate face and edge sit top-left at full size; the
# isometric sits below them, clear of the title block (x >= 0.216 m,
# y <= 0.066 m); the BOM and the notes fill the right half above it.
FRONT_CENTER = (0.085, 0.190)
RIGHT_CENTER = (0.170, 0.190)
ISO_CENTER = (0.085, 0.072)
ISO_NOTE_XY = (0.125, 0.050)
BOM_ANCHOR = (0.225, 0.262)
STEPS_XY = (0.225, 0.235)
CHECKS_XY = (0.225, 0.172)
TABLE_XY = (0.225, 0.122)
BALLOON_MARGIN = 0.012

PLATE = plate.PART_NAME
BOM_COMPONENTS = (PLATE,)
BOM_ITEM = "1"
BOM_DESCRIPTIONS = {
    PLATE: "BS-0 INDEX PLATE, "
    + "/".join(str(count) for count in sorted(plate.RING_COUNTS))
    + " HOLES"
}
BOM_COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {PLATE: (PLATE, None)}
BALLOON_ANCHORS = {PLATE: BalloonAnchor()}

ASSEMBLY_STEPS = "\n".join(
    (
        "FITTING ON THE BS-0 DIVIDING HEAD",
        "1. REMOVE THE STOCK INDEX PLATE; KEEP ITS THREE FLAT HEAD SCREWS.",
        "2. SLIDE ITEM 1 ONTO THE HEAD'S PLATE HUB, COUNTERSUNK FACE OUT.",
        "3. TURN ITEM 1 UNTIL ITS THREE COUNTERSINKS LINE UP WITH THE",
        "   HEAD'S PLATE-SCREW TAPS.",
        "4. FIT THE SCREWS FROM STEP 1 AND TIGHTEN THEM EVENLY.",
        "5. SET THE CRANK PIN ON THE CIRCLE THE INDEXING TABLE NAMES AND",
        "   SPREAD THE SECTOR ARMS OVER ITS HOLES PER TOOTH.",
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


def _indexing_rows() -> tuple[str, ...]:
    """One row per cone gear: no full crank turns, ``holes`` on ``count``."""
    rows = []
    for count in sorted(plate.RING_COUNTS):
        teeth = plate.RING_TEETH[count]
        holes, remainder = divmod(plate.WORM_RATIO * count, teeth)
        if remainder or holes >= count:
            raise AssertionError(f"{teeth}T does not index on the {count}-hole circle")
        rows.append(f"{teeth}T: {holes} HOLES ON THE {count}-HOLE CIRCLE")
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


def _bom_item(adapter: Any, table: Any) -> str:
    """The plate's ITEM NO. as the BOM prints it; the steps cite item 1."""
    table = _early_bound(table, "ITableAnnotation")
    header = [
        str(adapter._attempt(lambda c=column: table.DisplayedText2(0, c, True)) or "")
        .strip()
        .upper()
        for column in range(int(table.ColumnCount))
    ]
    items = [index for index, cell in enumerate(header) if cell.startswith("ITEM NO")]
    if int(table.RowCount) != 2 or len(items) != 1:
        raise RuntimeError(f"indexing-kit BOM is not one item row: {header!r}")
    item = str(
        adapter._attempt(lambda: table.DisplayedText2(1, items[0], True)) or ""
    ).strip()
    if item != BOM_ITEM:
        raise RuntimeError(
            f"indexing-kit BOM numbers the plate {item!r}, not {BOM_ITEM}"
        )
    return item


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
    item = _bom_item(adapter, table)
    landings = add_component_bom_balloons(
        adapter,
        front,
        items=((PLATE, item),),
        anchors=BALLOON_ANCHORS,
        label="indexing-kit BOM coverage",
        margin=BALLOON_MARGIN,
        explode_offsets={},
    )
    if len(landings) != 1:
        raise RuntimeError(f"indexing kit carries {len(landings)} balloons, expected 1")
    for text, xy, label in (
        (ASSEMBLY_STEPS, STEPS_XY, "fitting steps"),
        (ASSEMBLY_CHECKS, CHECKS_XY, "checks"),
        (INDEXING_TABLE, TABLE_XY, "indexing table"),
        (ISO_NOTE, ISO_NOTE_XY, "isometric scale note"),
    ):
        _add_note(adapter, text, xy, label=label)
    return lambda: assert_balloon_landings(adapter, landings)


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
    settled = _place_sheet(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Cone Gear Indexing Kit Assembly Drawing",
        scale=SHEET_SCALE,
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
