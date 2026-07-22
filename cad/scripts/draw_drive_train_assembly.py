r"""Create the curated assembly drawing for the drive-train subassembly.

Front / right / bottom / isometric views of ``cad/out/sldasm/drive-train.SLDASM`` plus a
top-level parts BOM and auto-inserted item-number balloons, on the same
hand-made ASME B template every part print uses. The title block resolves from
the custom properties ``build_drive_train_assembly.py`` stamps on the assembly
(Number, Revision, component-drawing material/finish, and the TOL_* cells
``finalize_drawing`` requires).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import _telemetry
from _assembly_drawing_bom import (
    configured_part_numbers,
    insert_identified_bom_table,
)
from _common import check, run_build
from _drawing_common import (
    DrawingOutputs,
    _balloon_item_number,
    _create_auto_balloons,
    _spread_balloons,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["drive_train_assembly"]
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

# The drive-train is the machine's WIDEST subassembly but not its tallest: its
# dominant extent is the Z depth -- the crank outboard end (machine z ~-175, plus
# the hanging arm/handle) to the cone-integrator tip end (cone_station(199) ~z
# +106, north arbor pedestal +97.5) -- a ~300 mm span shown horizontally in the
# RIGHT view. In X it runs the crank axis (-122.8) to the alignment-pinion drum
# (~+1), ~125 mm; in Y only ~50.8 (base top) to ~148 (crankshaft axis + gear
# tips), ~100 mm. So the governing on-sheet dimension is the right view's ~300
# mm depth: 1:5 shrinks it to ~60 mm, and the ~125 mm-wide front view to ~25 mm,
# which clears summing's view centers (a larger 1:3 would render the right view
# ~100 mm and collide the front/right views). 1:5 also keeps the whole assembly-
# drawing batch (summing, frame) on one scale.
SHEET_SCALE = (1.0, 5.0)
VIEW_SCALE = (1, 5)

# One BOM row per UNIQUE top-level component of build_drive_train_assembly.py.
# Stems placed more than once collapse to a single QTY row under the standard
# BOM's IgnoreMultiple: arbor-pedestal (south + north), pinion-bracket (front +
# back strap), pinion-pivot-block / pinion-cam-pin / pinion-cam (front + back),
# foot-screw (spring foot + pedestal flange). The cone-gear and cylinder-gear
# ladders are ONE placed seed each -- their siblings are CopyWithMates2 copies
# (cone-gear-N / cylinder-gear-N), never place_component'd, so they carry no
# extra BOM row. Descriptions fill the template's DESCRIPTION column (the parts
# carry no Description custom property, and a blank column reads as unreleased).
BOM_COMPONENTS = {
    "cylinder-gear-shaft": "CYLINDER DRUM ARBOR",
    "arbor-pedestal": "ARBOR PEDESTAL SUPPORT",
    "cone-swing-platform": "CONE SWING PLATFORM",
    "cone-pivot-post": "CONE BIG-END JOURNAL POST",
    "cone-tip-block": "CONE TIP JOURNAL BLOCK",
    "cone-tip-bushing": "CONE TIP SPACER BUSHING",
    "cone-tip-adjuster": "CONE TIP ENDPLAY ADJUSTER",
    "cone-tip-pinch-screw": "CONE TIP PINCH SCREW",
    "cone-lock-knob": "CONE PLATFORM LOCK KNOB",
    "cone-pivot-screw": "CONE SWING PIVOT SCREW",
    "swing-stop-screw": "SWING TRAVEL STOP SCREW",
    "alignment-pinion": "ALIGNMENT PINION DRUM",
    "pinion-bracket": "PINION ENGAGE STRAP",
    "pinion-pivot-block": "PINION PIVOT BLOCK",
    "pinion-pivot-shaft": "PINION TORQUE SHAFT",
    "pinion-lift-rod": "PINION LIFT ROD",
    "pinion-spring": "PINION DISENGAGE SPRING",
    "pinion-cam-pin": "PINION CAM FOLLOWER PIN",
    "pinion-cam": "PINION ECCENTRIC CAM",
    "pinion-lever": "PINION ENGAGE LEVER",
    "pinion-handle": "PINION TEE HANDLE",
    "pinion-arbor": "PINION DRUM ARBOR",
    "slotted-screw": "SLOTTED HOLD-DOWN SCREW",
    "foot-screw": "FOOT MOUNT SCREW",
    "cone-gear-shaft": "CONE GEAR SHAFT",
    "crank-drive-gear": "64T CRANK DRIVE GEAR",
    "cone-gear": "CONE GEAR, T006-T120 BY 6; 1 EACH",
    "cylinder-gear": "CYLINDER DRUM GEAR",
    "crankshaft": "CRANKSHAFT",
    "crank-pinion": "16T CRANK PINION",
    "crank-arm": "CRANK ARM",
    "crank-handle": "CRANK HANDLE",
}
BOM_PART_NUMBERS = configured_part_numbers(tuple(BOM_COMPONENTS))

BOTTOM_VISIBILITY_STEMS = frozenset(
    {"cone-tip-bushing", "cone-gear-shaft", "crank-drive-gear"}
)
FRONT_DEFERRED_BALLOON_STEMS = frozenset(
    {
        "swing-stop-screw",
        "pinion-pivot-shaft",
        "pinion-lever",
        "foot-screw",
        "crank-pinion",
    }
)
FRONT_DEFERRED_BALLOON_ITEMS = frozenset(
    str(index)
    for index, stem in enumerate(BOM_COMPONENTS, start=1)
    if stem in FRONT_DEFERRED_BALLOON_STEMS
)

ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. INSTALL CONE GEARS T006-T120 IN 6-TOOTH STEPS; T120 AT BIG END.",
        "2. SHOWN: CONE PLATFORM ENGAGED; ALIGNMENT PINION DISENGAGED.",
        "3. ADJUST CONE-TIP END PLAY, THEN LOCK THE PINCH SCREW.",
        "4. VERIFY CRANK, CONE SWING, PINION SWING AND CAM SHAFT MOVE FREELY.",
        "5. BOTTOM BALLOON VIEW: CONE-TIP BUSHING, CONE-GEAR SHAFT AND",
        "   CRANK-DRIVE GEAR ONLY; OUTER COMPONENTS HIDDEN.",
    )
)

# The 32-row BOM is split into three compact sections across the sheet top;
# four views and their balloons occupy the open field below it.
FRONT_CENTER = (0.080, 0.135)
RIGHT_CENTER = (0.200, 0.135)
ISO_CENTER = (0.310, 0.145)
BOTTOM_CENTER = (0.365, 0.105)
BOM_ANCHOR = (0.020, 0.265)
BOM_ROWS_PER_SECTION = 12
BOM_COLUMN_WIDTHS = {
    "ITEM NO.": 0.014,
    "PART NUMBER": 0.025,
    "DESCRIPTION": 0.074,
    "QTY.": 0.012,
}
BALLOON_RING_MARGINS = (0.036, 0.014, 0.014, 0.014)


@_telemetry.traced("drawing.format_drive_train_bom")
def _format_drive_train_bom(adapter: Any, table: Any) -> None:
    """Fit the 32-item BOM as three readable sections across the sheet top."""
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    header = [
        str(table.DisplayedText2(0, column, False) or "").strip().upper()
        for column in range(columns)
    ]
    if set(header) != set(BOM_COLUMN_WIDTHS):
        raise RuntimeError(f"unexpected drive-train BOM columns: {header!r}")

    for column, title in enumerate(header):
        requested = BOM_COLUMN_WIDTHS[title]
        actual = float(table.SetColumnWidth(column, requested, 0))
        if abs(actual - requested) > 0.0005:
            raise RuntimeError(
                f"drive-train BOM column {title!r} width {actual:.4f} m "
                f"does not match requested {requested:.4f} m"
            )

    split_tables = table.HorizontalAutoSplit(
        BOM_ROWS_PER_SECTION,
        0,  # swHorizontalAutoSplitApply_ThisTimeOnly
        0,  # swHorizontalAutoSplitPlacementOfSplitTable_NextToLastSplit
    )
    if not split_tables:
        raise RuntimeError("drive-train BOM did not split into sheet-width sections")
    pieces = tuple(split_tables)
    if len(pieces) not in (2, 3):
        raise RuntimeError(
            f"drive-train BOM returned {len(pieces)} split-table objects, expected 3"
        )
    for index, raw_piece in enumerate((table, *pieces)):
        piece = _sw_type_info.early_bound_or_flag(
            raw_piece, "ITableAnnotation", "GetAnnotation", "GetSplitInformation"
        )
        split_info = adapter._attempt(
            lambda p=piece: p.GetSplitInformation(0, 0, 0, 0)
        )
        annotation = adapter._attempt(lambda p=piece: p.GetAnnotation())
        position = adapter._attempt(
            lambda a=annotation: adapter._get_attr_or_call(a, "GetPosition")
        )
        _telemetry.info(
            f"drive-train BOM split object {index}: "
            f"info={split_info!r}, position={position!r}"
        )
    adapter.currentModel.EditRebuild3()
    _telemetry.success(
        f"drive-train BOM split at {BOM_ROWS_PER_SECTION} rows; "
        f"HorizontalAutoSplit returned {len(pieces)} objects"
    )


@_telemetry.traced("drawing.drive_train_balloons")
def _add_drive_train_balloons(
    adapter: Any, views: tuple[Any, ...], *, expected: int, label: str
) -> list[Any]:
    """Cover the BOM across four views with a larger front-view balloon ring."""
    if len(views) != len(BALLOON_RING_MARGINS):
        raise ValueError("drive-train view and balloon-margin counts differ")
    all_balloons: list[Any] = []
    item_numbers: set[str] = set()
    for index, (view, margin) in enumerate(
        zip(views, BALLOON_RING_MARGINS, strict=True), start=1
    ):
        view_label = f"{label} view {index}"
        balloons = _create_auto_balloons(
            adapter, view, label=view_label, allow_empty=True
        )
        if index == 1:
            balloons = _defer_front_balloons(adapter, balloons)
        if not balloons:
            continue
        _spread_balloons(adapter, view, balloons, margin=margin)
        for note in balloons:
            item_numbers.add(_balloon_item_number(adapter, note, label=view_label))
        all_balloons.extend(balloons)

    expected_numbers = {str(item) for item in range(1, expected + 1)}
    missing = sorted(expected_numbers - item_numbers, key=int)
    unexpected = sorted(item_numbers - expected_numbers)
    if missing or unexpected:
        raise RuntimeError(
            f"{label}: balloon item coverage mismatch; missing={missing}, "
            f"unexpected={unexpected}, seen={sorted(item_numbers)}"
        )
    adapter.currentModel.EditRebuild3()
    _telemetry.success(
        f"{label}: {len(all_balloons)} balloons cover all {expected} BOM items"
    )
    return all_balloons


def _drawing_component_children(drawing_component: Any) -> tuple[Any, ...]:
    """Return children across callable and materialized pywin32 dispatch shapes."""
    member = drawing_component.GetChildren
    children = member() if callable(member) else member
    return tuple(children or ())


def _drawing_component_matches(
    adapter: Any, drawing_component: Any, stems: frozenset[str]
) -> set[str]:
    """Return configured stems represented by one leaf drawing component."""
    name = str(drawing_component.Name or "")
    component = adapter._attempt(
        lambda dc=drawing_component: dc.Component, default=None
    )
    path = ""
    if component is not None:
        path = adapter._attempt(lambda c=component: c.GetPathName(), default="") or ""

    identities = {Path(str(path)).stem.casefold()}
    drawing_name = name.split("@", 1)[0].replace("\\", "/")
    identities.add(drawing_name.rsplit("/", 1)[-1].casefold())
    return {
        stem
        for stem in stems
        if any(
            identity == stem
            or (
                identity.startswith(f"{stem}-")
                and identity.removeprefix(f"{stem}-").isdigit()
            )
            for identity in identities
        )
    }


@_telemetry.traced("drawing.defer_front_balloons")
def _defer_front_balloons(adapter: Any, balloons: list[Any]) -> list[Any]:
    """Delete four crowded front balloons so later views can own those items."""
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    kept: list[Any] = []
    selected_items: set[str] = set()
    for note in balloons:
        item = _balloon_item_number(
            adapter, note, label="drive-train front balloon deferral"
        )
        if item not in FRONT_DEFERRED_BALLOON_ITEMS:
            kept.append(note)
            continue
        note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
        annotation = note.GetAnnotation()
        if annotation is None:
            raise RuntimeError(f"drive-train front balloon item {item} has no annotation")
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "Select2"
        )
        if not annotation.Select2(bool(selected_items), 0):
            raise RuntimeError(f"failed to select front balloon item {item} for deferral")
        selected_items.add(item)

    if selected_items != FRONT_DEFERRED_BALLOON_ITEMS:
        missing = sorted(FRONT_DEFERRED_BALLOON_ITEMS - selected_items, key=int)
        raise RuntimeError(f"drive-train front balloons cannot defer missing items: {missing}")
    extension = _sw_type_info.early_bound_or_flag(
        draw.Extension, "IModelDocExtension", "DeleteSelection2"
    )
    if not extension.DeleteSelection2(0):
        raise RuntimeError("failed to delete deferred drive-train front balloons")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return kept


@_telemetry.traced("drawing.isolate_bottom_balloon_components")
def _isolate_bottom_balloon_components(adapter: Any, view: Any) -> None:
    """Show only the three enclosed BOM families in the auxiliary bottom view."""
    root = adapter._attempt(
        lambda: view.RootDrawingComponent2(False), default=None
    )
    if root is None:
        raise RuntimeError("drive-train bottom view has no root drawing component")

    pending = list(_drawing_component_children(root))
    found: set[str] = set()
    enumerated: list[str] = []
    while pending:
        drawing_component = pending.pop()
        children = _drawing_component_children(drawing_component)
        pending.extend(children)

        enumerated.append(str(drawing_component.Name or ""))
        matched = _drawing_component_matches(
            adapter, drawing_component, BOTTOM_VISIBILITY_STEMS
        )
        if children:
            continue
        drawing_component.Visible = bool(matched)
        if not matched:
            continue
        found.update(matched)
        for stem in matched:
            _telemetry.event("drawing.component_visible", component=stem)

    missing = sorted(BOTTOM_VISIBILITY_STEMS - found)
    if missing:
        raise RuntimeError(
            "drive-train bottom view is missing enclosed components: "
            f"{missing}; enumerated drawing components: {sorted(enumerated)}"
        )
    adapter.currentModel.EditRebuild3()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open drive-train assembly source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(adapter, scale=SHEET_SCALE)
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Drive-Train Assembly Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank; cone integrator; cylinder drum; pinion engage; parts list",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(
        adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE
    )
    right = place_view(
        adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE
    )
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE
    )
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    # The cone-tip bushing and the two coaxial crank/cone-drive items are fully
    # enclosed in every exterior projection.  The auxiliary bottom view shows
    # hidden lines so those physical BOM items have balloonable geometry.
    set_hidden_lines_visible(adapter, bottom)
    _isolate_bottom_balloon_components(adapter, bottom)

    bom_table = insert_identified_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        descriptions=BOM_COMPONENTS,
        part_numbers=BOM_PART_NUMBERS,
        configuration_grouping="same-part",
        label="drive-train assembly",
    )
    _format_drive_train_bom(adapter, bom_table)
    # The lower platform and fastener families are occluded in the front/right
    # pair and behind the gear ladders in the pictorial.  The bottom projection
    # exposes those remaining BOM identities rather than accepting an
    # incomplete balloon set.
    _add_drive_train_balloons(
        adapter, (front, right, iso, bottom), expected=len(BOM_COMPONENTS),
        label="drive-train assembly balloons",
    )
    if add_note(adapter, ASSEMBLY_NOTES, 0.018, 0.052) is None:
        raise RuntimeError("failed to add drive-train assembly notes")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Drive-Train Assembly Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
