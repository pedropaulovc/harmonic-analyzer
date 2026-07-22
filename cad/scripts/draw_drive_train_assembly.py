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
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    iter_views,
    place_view,
    view_name,
)


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

# Four sheets let the ~300 mm-wide mechanism use a readable 1:3 scale without
# forcing its 32-row BOM, exterior balloons, concealed-item identification, and
# functional setup notes into one field.  All views use the sheet scale so the
# title block remains truthful without per-view scale exceptions.
SHEET_SCALE = (1.0, 3.0)
VIEW_SCALE = (1, 3)
SHEET_NAMES = (
    "GENERAL ASSEMBLY",
    "PARTS LIST",
    "EXTERIOR ITEM IDENTIFICATION",
    "CONCEALED ITEM IDENTIFICATION",
)

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
CONCEALED_BALLOON_ITEMS = {
    stem: str(index)
    for index, stem in enumerate(BOM_COMPONENTS, start=1)
    if stem in BOTTOM_VISIBILITY_STEMS
}
MANUAL_EXTERIOR_BALLOON_ITEMS = {
    "cone-tip-adjuster": "7",
    "cone-tip-pinch-screw": "8",
    "swing-stop-screw": "11",
    "alignment-pinion": "12",
    "crank-pinion": "30",
}
MANUAL_EXTERIOR_VIEW_ORDER = {
    "cone-tip-adjuster": (2, 1, 0),
    "cone-tip-pinch-screw": (0, 2, 1),
    "swing-stop-screw": (1, 2, 0),
    "alignment-pinion": (2, 1, 0),
    "crank-pinion": (1, 2, 0),
}
FRONT_DEFERRED_BALLOON_STEMS = frozenset(
    {
        "swing-stop-screw",
        "pinion-pivot-shaft",
        "pinion-lever",
        "foot-screw",
        "crankshaft",
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
        "3. ADJUST CONE-TIP SCREW TO REMOVE AXIAL PLAY WITHOUT BINDING;",
        "   VERIFY FREE SHAFT ROTATION, THEN TIGHTEN PINCH SCREW.",
        "4. PINION DISENGAGED: 2.00 MM TIP GAP; ENGAGED C-C: 41.30 MM.",
        "5. SET STRAPS 12.38 DEG WEST OF VERTICAL AT PARK; 0.25 MM AXIAL",
        "   CLEARANCE EACH SIDE OF PINION DRUM.",
        "6. PHASE BOTH CAMS IDENTICALLY, ECCENTRIC AND SET-PIN BOSS DOWN AT",
        "   PARK; FOLLOWER PLANE 7.00 MM FROM CAM FRONT; AIR 0.10-0.25 MM.",
        "7. CAMS DOWN: SET ENGAGE LEVER 40 DEG EAST OF VERTICAL.",
        "8. INSTALL LEAF SPRING AT BACK STRAP ONLY; FRONT REMAINS SPRING-FREE.",
        "   PRELOAD FOR POSITIVE RETURN TO THE 2.00 MM DISENGAGED TIP GAP.",
        "9. ROTATE CAM SHAFT ONE FULL TURN; FOLLOWERS SHALL NOT BIND OR LIFT OFF.",
    )
)

# Sheet 1: uncluttered assembly views and setup/inspection notes.
GENERAL_FRONT_CENTER = (0.060, 0.165)
GENERAL_RIGHT_CENTER = (0.190, 0.165)
GENERAL_ISO_CENTER = (0.335, 0.165)
GENERAL_NOTES_ORIGIN = (0.018, 0.085)

# Sheet 2: one continuous 32-row parts list plus a small orientation view.
BOM_ANCHOR = (0.018, 0.262)
BOM_ISO_CENTER = (0.310, 0.165)

# Sheet 3: large exterior views and exterior-only item balloons.
EXTERIOR_FRONT_CENTER = (0.075, 0.155)
EXTERIOR_RIGHT_CENTER = (0.220, 0.155)
EXTERIOR_ISO_CENTER = (0.345, 0.155)

# Sheet 4: two isolated views keep the coaxial concealed items readable.  The
# bushing and shaft share the underside view; the crank gear gets a separate
# front view because its projected attachment lies on top of the shaft callout.
CONCEALED_BOTTOM_CENTER = (0.115, 0.135)
CONCEALED_FRONT_CENTER = (0.285, 0.155)
CONCEALED_BOTTOM_STEMS = frozenset({"cone-tip-bushing", "cone-gear-shaft"})
CONCEALED_FRONT_STEMS = frozenset({"crank-drive-gear"})
CONCEALED_BOTTOM_BALLOON_RING_MARGIN = 0.015
CONCEALED_FRONT_BALLOON_RING_MARGIN = 0.025
CONCEALED_BALLOON_CLEARANCE = 0.006
BOM_COLUMN_WIDTHS = {
    "ITEM NO.": 0.014,
    "PART NUMBER": 0.025,
    "DESCRIPTION": 0.074,
    "QTY.": 0.012,
}
EXTERIOR_BALLOON_RING_MARGINS = (0.014, 0.014, 0.014)


@_telemetry.traced("drawing.format_drive_train_bom")
def _format_drive_train_bom(adapter: Any, table: Any) -> None:
    """Fit the 32-item BOM as one readable table on its dedicated sheet."""
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

    adapter.currentModel.EditRebuild3()
    _telemetry.success(
        f"drive-train BOM formatted as one {len(BOM_COMPONENTS)}-item table"
    )


@_telemetry.traced("drawing.drive_train_balloons")
def _add_drive_train_balloons(
    adapter: Any,
    views: tuple[Any, ...],
    *,
    expected_items: frozenset[str],
    manual_items: dict[str, str],
    label: str,
) -> list[Any]:
    """Balloon the exterior item set across the three large exterior views."""
    if len(views) != len(EXTERIOR_BALLOON_RING_MARGINS):
        raise ValueError("drive-train view and balloon-margin counts differ")
    all_balloons: list[Any] = []
    item_numbers: set[str] = set()
    view_balloons: list[list[Any]] = []
    for index, (view, margin) in enumerate(
        zip(views, EXTERIOR_BALLOON_RING_MARGINS, strict=True), start=1
    ):
        view_label = f"{label} view {index}"
        balloons = _create_auto_balloons(
            adapter, view, label=view_label, allow_empty=True
        )
        if index == 1:
            balloons = _defer_front_balloons(adapter, balloons)
        balloons, _removed = _delete_balloon_items(
            adapter,
            balloons,
            frozenset(CONCEALED_BALLOON_ITEMS.values())
            | frozenset(manual_items.values()),
            label=f"{view_label} dedicated-sheet deferral",
        )
        view_balloons.append(balloons)
        if not balloons:
            continue
        _spread_balloons(adapter, view, balloons, margin=margin)
        for note in balloons:
            item_numbers.add(_balloon_item_number(adapter, note, label=view_label))
        all_balloons.extend(balloons)

    for stem, item in manual_items.items():
        view_order = MANUAL_EXTERIOR_VIEW_ORDER[stem]
        preferred_views = tuple(views[index] for index in view_order)
        note, owner_view = _create_component_balloon(
            adapter, preferred_views, stem=stem, expected_item=item
        )
        owner_index = next(
            index for index, candidate in enumerate(views) if candidate is owner_view
        )
        view_balloons[owner_index].append(note)
        _spread_balloons(
            adapter,
            owner_view,
            view_balloons[owner_index],
            margin=EXTERIOR_BALLOON_RING_MARGINS[owner_index],
        )
        item_numbers.add(item)
        all_balloons.append(note)

    missing = sorted(expected_items - item_numbers, key=int)
    unexpected = sorted(item_numbers - expected_items, key=int)
    if missing or unexpected:
        raise RuntimeError(
            f"{label}: balloon item coverage mismatch; missing={missing}, "
            f"unexpected={unexpected}, seen={sorted(item_numbers)}"
        )
    adapter.currentModel.EditRebuild3()
    _telemetry.success(
        f"{label}: {len(all_balloons)} balloons cover "
        f"{len(expected_items)} exterior BOM items"
    )
    return all_balloons


@_telemetry.traced("drawing.delete_balloon_items")
def _delete_balloon_items(
    adapter: Any,
    balloons: list[Any],
    items: frozenset[str],
    *,
    label: str,
) -> tuple[list[Any], set[str]]:
    """Delete selected item balloons so another view or sheet can own them."""
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    kept: list[Any] = []
    selected_items: set[str] = set()
    for note in balloons:
        item = _balloon_item_number(adapter, note, label=label)
        if item not in items:
            kept.append(note)
            continue
        note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
        annotation = note.GetAnnotation()
        if annotation is None:
            raise RuntimeError(f"{label}: item {item} has no annotation")
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "Select2"
        )
        if not annotation.Select2(bool(selected_items), 0):
            raise RuntimeError(f"{label}: failed to select item {item}")
        selected_items.add(item)

    if selected_items:
        extension = _sw_type_info.early_bound_or_flag(
            draw.Extension, "IModelDocExtension", "DeleteSelection2"
        )
        if not extension.DeleteSelection2(0):
            raise RuntimeError(f"{label}: failed to delete deferred balloons")
        draw.ClearSelection2(True)
        draw.EditRebuild3()
    return kept, selected_items


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
    """Delete crowded front balloons so later views can own those items."""
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


@_telemetry.traced("drawing.component_balloon", label_param="stem")
def _create_component_balloon(
    adapter: Any, views: tuple[Any, ...], *, stem: str, expected_item: str
) -> tuple[Any, Any]:
    """Insert one BOM balloon on a real visible edge of the requested component."""
    selected_view: Any | None = None
    selected_edge: Any | None = None
    enumerated: list[str] = []
    for view in views:
        root = adapter._attempt(
            lambda v=view: v.RootDrawingComponent2(False), default=None
        )
        if root is None:
            continue
        pending = list(_drawing_component_children(root))
        while pending:
            drawing_component = pending.pop()
            children = _drawing_component_children(drawing_component)
            pending.extend(children)
            if children:
                continue
            if not _drawing_component_matches(
                adapter, drawing_component, frozenset({stem})
            ):
                continue
            enumerated.append(str(drawing_component.Name or ""))
            component = adapter._attempt(
                lambda dc=drawing_component: dc.Component, default=None
            )
            edges = adapter._attempt(
                lambda v=view, c=component: v.GetVisibleEntities2(c, 1), default=()
            ) or ()
            if not edges:
                continue
            selected_view = view
            selected_edge = edges[0]
            break
        if selected_edge is not None:
            break
    if selected_view is None or selected_edge is None:
        raise RuntimeError(
            f"drive-train {stem} balloon has no visible edge across drawing views; "
            f"matching components={enumerated}"
        )

    draw = adapter.currentModel
    ddoc = _sw_type_info.early_bound_or_flag(draw, "IDrawingDoc", "ActivateView")
    if not ddoc.ActivateView(view_name(adapter, selected_view)):
        raise RuntimeError(f"failed to activate drive-train {stem} balloon view")
    draw.ClearSelection2(True)
    if not selected_view.SelectEntity(selected_edge, False):
        raise RuntimeError(f"failed to select drive-train {stem} visible edge")
    extension = _sw_type_info.early_bound_or_flag(
        draw.Extension,
        "IModelDocExtension",
        "CreateBalloonOptions",
        "InsertBOMBalloon2",
    )
    options = extension.CreateBalloonOptions()
    if options is None:
        raise RuntimeError(f"failed to create drive-train {stem} balloon options")
    options = _sw_type_info.early_bound_or_flag(options, "IBalloonOptions")
    options.Style = 1
    options.Size = 2
    options.UpperTextContent = 1
    options.ShowQuantity = False
    options.ItemNumberStart = 1
    options.ItemNumberIncrement = 1
    options.ItemOrder = 1
    note = extension.InsertBOMBalloon2(options)
    draw.ClearSelection2(True)
    if note is None:
        raise RuntimeError(f"failed to insert drive-train {stem} BOM balloon")
    item = _balloon_item_number(adapter, note, label=f"drive-train {stem} balloon")
    if item != expected_item:
        raise RuntimeError(
            f"drive-train {stem} balloon resolved item {item}, expected {expected_item}"
        )
    _telemetry.success(f"drive-train {stem} component balloon -> item {item}")
    return note, selected_view


@_telemetry.traced("drawing.isolate_balloon_components")
def _isolate_balloon_components(
    adapter: Any,
    view: Any,
    *,
    visible_stems: frozenset[str],
    label: str,
) -> None:
    """Show only the requested enclosed BOM families in an auxiliary view."""
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
        matched = _drawing_component_matches(adapter, drawing_component, visible_stems)
        if children:
            continue
        drawing_component.Visible = bool(matched)
        if not matched:
            continue
        found.update(matched)
        for stem in matched:
            _telemetry.event("drawing.component_visible", component=stem)

    missing = sorted(visible_stems - found)
    if missing:
        raise RuntimeError(
            f"drive-train {label} view is missing enclosed components: "
            f"{missing}; enumerated drawing components: {sorted(enumerated)}"
        )
    adapter.currentModel.EditRebuild3()


@_telemetry.traced("drawing.create_drive_train_sheets")
def _create_drive_train_sheets(adapter: Any) -> None:
    """Duplicate the still-blank project sheet into the four-sheet package."""
    draw = adapter.currentModel
    ddoc = _sw_type_info.early_bound_or_flag(
        draw,
        "IDrawingDoc",
        "ActivateSheet",
        "GetCurrentSheet",
        "GetSheetNames",
        "PasteSheet",
    )
    sheet = ddoc.GetCurrentSheet()
    if sheet is None:
        raise RuntimeError("drive-train drawing template has no initial sheet")
    initial_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if len(initial_names) != 1:
        raise RuntimeError(
            f"drive-train drawing template has {len(initial_names)} sheets, expected 1"
        )
    if next(iter_views(adapter), None) is not None:
        raise RuntimeError("drive-train drawing template initial sheet is not blank")
    sheet.SetName(SHEET_NAMES[0])
    renamed = str(adapter._get_attr_or_call(sheet, "GetName") or "")
    if renamed != SHEET_NAMES[0]:
        raise RuntimeError(
            f"failed to rename initial drive-train sheet: {renamed!r}"
        )

    for previous_name, new_name in zip(SHEET_NAMES[:-1], SHEET_NAMES[1:], strict=True):
        pasted_name = ""
        for attempt in range(1, 4):
            if not ddoc.ActivateSheet(previous_name):
                raise RuntimeError(
                    f"failed to activate blank drive-train sheet {previous_name!r}"
                )
            before_names = tuple(
                adapter._get_attr_or_call(ddoc, "GetSheetNames") or ()
            )
            draw.ClearSelection2(True)
            selected = draw.Extension.SelectByID2(
                previous_name,
                "SHEET",
                0.0,
                0.0,
                0.0,
                False,
                0,
                null_callout(),
                0,
            )
            if not selected:
                raise RuntimeError(
                    f"failed to select blank drive-train sheet {previous_name!r}"
                )
            draw.EditCopy()
            # swInsertOption_MoveToEnd=2, swRenameOption_No=2. Copying the
            # blank sheet preserves the project sheet format and title block.
            returned = bool(ddoc.PasteSheet(2, 2))
            after_names = tuple(
                adapter._get_attr_or_call(ddoc, "GetSheetNames") or ()
            )
            added = tuple(name for name in after_names if name not in before_names)
            if len(after_names) == len(before_names) + 1 and len(added) == 1:
                pasted_name = added[0]
                if not returned:
                    _telemetry.warn(
                        "PasteSheet returned false but created "
                        f"{pasted_name!r}; accepting verified side effect"
                    )
                break
            _telemetry.warn(
                f"PasteSheet attempt {attempt}/3 created no sheet "
                f"(returned={returned!r}, before={before_names!r}, "
                f"after={after_names!r})"
            )
        if not pasted_name:
            raise RuntimeError(
                f"failed to duplicate blank drive-train sheet {previous_name!r} "
                "after 3 verified attempts"
            )
        if not ddoc.ActivateSheet(pasted_name):
            raise RuntimeError(f"failed to activate pasted sheet {pasted_name!r}")
        sheet = ddoc.GetCurrentSheet()
        if sheet is None:
            raise RuntimeError("pasted drive-train sheet has no ISheet")
        sheet.SetName(new_name)
        renamed = str(adapter._get_attr_or_call(sheet, "GetName") or "")
        if renamed != new_name:
            raise RuntimeError(
                f"failed to rename pasted drive-train sheet: {renamed!r}"
            )

    actual = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if actual != SHEET_NAMES:
        raise RuntimeError(f"drive-train sheet order mismatch: {actual!r}")
    for name in SHEET_NAMES:
        if not ddoc.ActivateSheet(name):
            raise RuntimeError(f"failed to activate drive-train sheet {name!r}")
        current = ddoc.GetCurrentSheet()
        current_name = str(adapter._get_attr_or_call(current, "GetName") or "")
        if current_name != name:
            raise RuntimeError(
                f"drive-train activated sheet {current_name!r}, expected {name!r}"
            )


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
    _create_drive_train_sheets(adapter)
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

    ddoc = _sw_type_info.early_bound_or_flag(
        drawing_model, "IDrawingDoc", "ActivateSheet"
    )

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate general-assembly sheet")
    general_front = place_view(
        adapter, str(SOURCE), "*Front", *GENERAL_FRONT_CENTER, scale=VIEW_SCALE
    )
    general_right = place_view(
        adapter, str(SOURCE), "*Right", *GENERAL_RIGHT_CENTER, scale=VIEW_SCALE
    )
    general_iso = place_view(
        adapter, str(SOURCE), "*Isometric", *GENERAL_ISO_CENTER, scale=VIEW_SCALE
    )
    for view in (general_front, general_right, general_iso):
        set_hidden_lines_removed(adapter, view)
    if add_note(
        adapter, "SHEET 1 OF 4 — GENERAL ASSEMBLY", 0.018, 0.255
    ) is None:
        raise RuntimeError("failed to add general-assembly heading")
    if add_note(adapter, ASSEMBLY_NOTES, *GENERAL_NOTES_ORIGIN) is None:
        raise RuntimeError("failed to add drive-train assembly notes")

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate drive-train parts-list sheet")
    bom_iso = place_view(
        adapter, str(SOURCE), "*Isometric", *BOM_ISO_CENTER, scale=VIEW_SCALE
    )
    set_hidden_lines_removed(adapter, bom_iso)
    bom_table = insert_identified_bom_table(
        adapter,
        bom_iso,
        anchor_xy=BOM_ANCHOR,
        descriptions=BOM_COMPONENTS,
        part_numbers=BOM_PART_NUMBERS,
        configuration_grouping="same-part",
        label="drive-train assembly",
    )
    _format_drive_train_bom(adapter, bom_table)
    if add_note(
        adapter,
        "SHEET 2 OF 4 — PARTS LIST; ITEM NUMBERS APPLY TO SHEETS 3 AND 4",
        0.170,
        0.255,
    ) is None:
        raise RuntimeError("failed to add drive-train parts-list heading")

    if not ddoc.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("failed to activate exterior-identification sheet")
    exterior_front = place_view(
        adapter, str(SOURCE), "*Front", *EXTERIOR_FRONT_CENTER, scale=VIEW_SCALE
    )
    exterior_right = place_view(
        adapter, str(SOURCE), "*Right", *EXTERIOR_RIGHT_CENTER, scale=VIEW_SCALE
    )
    exterior_iso = place_view(
        adapter, str(SOURCE), "*Isometric", *EXTERIOR_ISO_CENTER, scale=VIEW_SCALE
    )
    exterior_views = (exterior_front, exterior_right, exterior_iso)
    for view in exterior_views:
        set_hidden_lines_removed(adapter, view)
    exterior_items = frozenset(
        str(index)
        for index in range(1, len(BOM_COMPONENTS) + 1)
        if str(index) not in CONCEALED_BALLOON_ITEMS.values()
    )
    _add_drive_train_balloons(
        adapter,
        exterior_views,
        expected_items=exterior_items,
        manual_items=MANUAL_EXTERIOR_BALLOON_ITEMS,
        label="drive-train exterior balloons",
    )
    if add_note(
        adapter,
        "SHEET 3 OF 4 — EXTERIOR ITEM IDENTIFICATION; HIDDEN LINES REMOVED",
        0.018,
        0.255,
    ) is None:
        raise RuntimeError("failed to add exterior-identification heading")

    if not ddoc.ActivateSheet(SHEET_NAMES[3]):
        raise RuntimeError("failed to activate concealed-identification sheet")
    concealed_bottom = place_view(
        adapter,
        str(SOURCE),
        "*Bottom",
        *CONCEALED_BOTTOM_CENTER,
        scale=VIEW_SCALE,
    )
    set_hidden_lines_visible(adapter, concealed_bottom)
    _isolate_balloon_components(
        adapter,
        concealed_bottom,
        visible_stems=CONCEALED_BOTTOM_STEMS,
        label="bottom",
    )
    bottom_balloons: list[Any] = []
    for stem in sorted(CONCEALED_BOTTOM_STEMS):
        item = CONCEALED_BALLOON_ITEMS[stem]
        note, _owner_view = _create_component_balloon(
            adapter, (concealed_bottom,), stem=stem, expected_item=item
        )
        bottom_balloons.append(note)
    _spread_balloons(
        adapter,
        concealed_bottom,
        bottom_balloons,
        margin=CONCEALED_BOTTOM_BALLOON_RING_MARGIN,
        clearance=CONCEALED_BALLOON_CLEARANCE,
    )

    concealed_front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *CONCEALED_FRONT_CENTER,
        scale=VIEW_SCALE,
    )
    set_hidden_lines_visible(adapter, concealed_front)
    _isolate_balloon_components(
        adapter,
        concealed_front,
        visible_stems=CONCEALED_FRONT_STEMS,
        label="front",
    )
    front_balloons: list[Any] = []
    for stem in sorted(CONCEALED_FRONT_STEMS):
        item = CONCEALED_BALLOON_ITEMS[stem]
        note, _owner_view = _create_component_balloon(
            adapter, (concealed_front,), stem=stem, expected_item=item
        )
        front_balloons.append(note)
    _spread_balloons(
        adapter,
        concealed_front,
        front_balloons,
        margin=CONCEALED_FRONT_BALLOON_RING_MARGIN,
        clearance=CONCEALED_BALLOON_CLEARANCE,
    )
    if add_note(
        adapter,
        "SHEET 4 OF 4 — CONCEALED ITEM IDENTIFICATION\n"
        "LEFT: ITEMS 6 AND 25, BOTTOM VIEW; RIGHT: ITEM 26, FRONT VIEW\n"
        "OUTER COMPONENTS HIDDEN; HIDDEN LINES VISIBLE",
        0.018,
        0.255,
    ) is None:
        raise RuntimeError("failed to add concealed-identification heading")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Drive-Train Assembly Drawing",
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
