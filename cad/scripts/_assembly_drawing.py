"""Shared multi-sheet assembly-package recipe."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import _telemetry
from _common import _early_bound, check
from _drawing_common import (
    DrawingOutputs,
    add_auto_balloons_across_views,
    add_note,
    create_blank_drawing_sheets,
    finalize_drawing,
    insert_bom_table,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SHEET_NAMES = ("ASSEMBLED VIEWS", "EXPLODED AND BOM", "ASSEMBLY PROCEDURE")
_EXPLODED_CENTER = (0.120, 0.170)
_REFERENCE_FRONT_CENTER = (0.050, 0.055)
_REFERENCE_RIGHT_CENTER = (0.210, 0.055)
_BOM_ANCHOR = (0.246, 0.257)


@dataclass(frozen=True)
class _BomMetadata:
    components: tuple[str, ...]
    descriptions: dict[str, str]
    aliases: dict[str, str]
    configuration: str
    exploded_views: int


def _required_lines(
    lines: Sequence[str], *, label: str, minimum: int
) -> tuple[str, ...]:
    cleaned = tuple(str(line).strip() for line in lines)
    if len(cleaned) < minimum or any(not line for line in cleaned):
        raise ValueError(f"{label} requires at least {minimum} nonblank lines")
    too_long = [line for line in cleaned if len(line) > 96]
    if too_long:
        raise ValueError(
            f"{label} lines must fit a normal-size note column: {too_long!r}"
        )
    return cleaned


def _component_property(adapter: Any, component: Any, name: str) -> str:
    model = adapter._attempt(lambda: component.GetModelDoc2(), default=None)
    if model is None:
        return ""
    model = _early_bound(model, "IModelDoc2")
    configuration = str(
        adapter._attempt(lambda: component.ReferencedConfiguration, default="") or ""
    )
    return str(
        adapter._attempt(
            lambda: model.GetCustomInfoValue(configuration, name), default=""
        )
        or adapter._attempt(lambda: model.GetCustomInfoValue("", name), default="")
        or ""
    ).strip()


def _component_stem(adapter: Any, component: Any) -> str:
    path = str(adapter._attempt(lambda: component.GetPathName(), default="") or "")
    if path:
        return Path(path.replace("\\", "/")).stem.casefold()
    name = str(adapter._attempt(lambda: component.Name2, default="") or "")
    leaf = name.replace("\\", "/").rsplit("/", 1)[-1]
    base, separator, suffix = leaf.rpartition("-")
    stem = base if separator and suffix.isdigit() else leaf
    if not stem:
        raise RuntimeError("top-level assembly component has no path or name")
    return stem.casefold()


def _read_bom_metadata(adapter: Any, model: Any) -> _BomMetadata:
    """Read BOM identities from the active source configuration, never a hand list."""
    model_doc = _early_bound(model, "IModelDoc2")
    assembly = _early_bound(model, "IAssemblyDoc")
    manager = _early_bound(model_doc.ConfigurationManager, "IConfigurationManager")
    configuration_object = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    configuration = str(configuration_object.Name or "Default")
    resolve_status = int(assembly.ResolveAllLightWeightComponents(False))
    if resolve_status != 0:  # swComponentResolveStatus_e.swResolveOk
        raise RuntimeError(
            f"failed to resolve source components for BOM metadata: status {resolve_status}"
        )
    components = (
        adapter._attempt(lambda: assembly.GetComponents(True), default=None) or ()
    )

    descriptions: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for raw_component in components:
        component = _early_bound(raw_component, "IComponent2")
        if bool(adapter._attempt(lambda: component.IsSuppressed(), default=False)):
            continue
        stem = _component_stem(adapter, component)
        title = _component_property(adapter, component, "Title")
        description = title or stem.replace("-", " ").replace("_", " ").title()
        previous = descriptions.setdefault(stem, description)
        if previous != description:
            raise RuntimeError(
                f"component {stem!r} has conflicting BOM descriptions "
                f"{previous!r} and {description!r}"
            )
        number = _component_property(adapter, component, "Number")
        if number:
            normalized = number.casefold()
            prior = aliases.setdefault(normalized, stem)
            if prior != stem:
                raise RuntimeError(
                    f"BOM part number {number!r} identifies both {prior!r} and {stem!r}"
                )

    expected = tuple(sorted(descriptions))
    if not expected:
        raise RuntimeError(
            "source assembly has no unsuppressed top-level BOM components"
        )
    exploded_views = int(
        adapter._attempt(
            lambda: assembly.GetExplodedViewCount2(configuration), default=0
        )
        or 0
    )
    return _BomMetadata(
        components=expected,
        descriptions=descriptions,
        aliases=aliases,
        configuration=configuration,
        exploded_views=exploded_views,
    )


def _activate_sheet(adapter: Any, sheet_name: str) -> None:
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(sheet_name):
        raise RuntimeError(f"failed to activate assembly-package sheet {sheet_name!r}")


def _note(adapter: Any, text: str, x: float, y: float, *, label: str) -> None:
    if add_note(adapter, text, x, y) is None:
        raise RuntimeError(f"failed to add {label}")


def _validate_assembly_bom_columns(adapter: Any, table: Any, *, label: str) -> None:
    """Require populated item, part, description, and quantity cells."""
    table = _early_bound(table, "ITableAnnotation")
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    headers = [
        str(
            adapter._attempt(
                lambda column=column: table.DisplayedText(0, column), default=""
            )
            or ""
        )
        .strip()
        .upper()
        .rstrip(".")
        for column in range(columns)
    ]
    required = ("ITEM NO", "PART NUMBER", "DESCRIPTION")
    missing = [name for name in required if name not in headers]
    quantity_column = next(
        (column for column, header in enumerate(headers) if header.startswith("QTY")),
        None,
    )
    if missing or quantity_column is None:
        raise RuntimeError(
            f"{label}: BOM headers do not provide item/part/description/quantity: "
            f"{headers!r}"
        )
    checked_columns = [headers.index(name) for name in required]
    checked_columns.append(quantity_column)
    blank_cells = [
        (row, headers[column])
        for row in range(1, rows)
        for column in checked_columns
        if not str(
            adapter._attempt(
                lambda row=row, column=column: table.DisplayedText(row, column),
                default="",
            )
            or ""
        ).strip()
    ]
    if blank_cells:
        raise RuntimeError(f"{label}: BOM has blank required cells: {blank_cells!r}")


def _place_hlr_view(
    adapter: Any,
    source: Path,
    view_name: str,
    center: tuple[float, float],
    *,
    scale: tuple[float, float],
    configuration: str,
) -> Any:
    view = place_view(adapter, str(source), view_name, *center, scale=scale)
    view = _early_bound(view, "IView")
    view.ReferencedConfiguration = configuration
    adapter.currentModel.EditRebuild3()
    applied = str(adapter._get_attr_or_call(view, "ReferencedConfiguration") or "")
    if applied != configuration:
        raise RuntimeError(
            f"{view_name} view configuration {applied!r} != {configuration!r}"
        )
    set_hidden_lines_removed(adapter, view)
    return view


def _sheet_marker(adapter: Any, number: int) -> None:
    _note(
        adapter,
        f"SHEET {number} OF {len(SHEET_NAMES)}",
        0.382,
        0.266,
        label=f"sheet {number} package marker",
    )


@_telemetry.traced("drawing.assembly_package", label_param="pdf_title")
async def build_assembly_package(
    adapter: Any,
    *,
    source: Path,
    outputs: DrawingOutputs,
    sheet_scale: tuple[float, float],
    reference_scale: tuple[float, float],
    front_center: tuple[float, float],
    right_center: tuple[float, float],
    iso_center: tuple[float, float],
    pdf_title: str,
    assembly_steps: Sequence[str],
    critical_checks: Sequence[str],
    hardware_notes: Sequence[str],
) -> dict[str, str]:
    """Build assembled, exploded/BOM, and procedure sheets for one assembly."""
    if not source.is_file():
        raise FileNotFoundError(f"source assembly is missing: {source}")
    steps = _required_lines(assembly_steps, label="assembly steps", minimum=4)
    checks = _required_lines(critical_checks, label="critical checks", minimum=2)
    hardware = _required_lines(hardware_notes, label="hardware notes", minimum=1)

    check("open assembly drawing source", await adapter.open_model(str(source)))
    source_model = adapter.currentModel
    read_required_properties(
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
    bom = _read_bom_metadata(adapter, source_model)

    new_project_drawing(adapter, scale=sheet_scale)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label=pdf_title)

    _activate_sheet(adapter, SHEET_NAMES[0])
    _place_hlr_view(
        adapter,
        source,
        "*Front",
        front_center,
        scale=sheet_scale,
        configuration=bom.configuration,
    )
    _place_hlr_view(
        adapter,
        source,
        "*Right",
        right_center,
        scale=sheet_scale,
        configuration=bom.configuration,
    )
    _note(
        adapter, "FRONT — WORKING POSITION", front_center[0], 0.252, label="front label"
    )
    _note(
        adapter,
        "RIGHT SIDE — WORKING POSITION",
        right_center[0],
        0.252,
        label="right label",
    )
    _sheet_marker(adapter, 1)

    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = _place_hlr_view(
        adapter,
        source,
        "*Isometric",
        _EXPLODED_CENTER,
        scale=sheet_scale,
        configuration=bom.configuration,
    )
    if not bom.exploded_views:
        raise RuntimeError(
            f"{pdf_title}: configuration {bom.configuration!r} has no exploded view"
        )
    shown = bool(exploded.ShowExploded(True))
    adapter.currentModel.EditRebuild3()
    if not shown or not bool(exploded.IsExploded()):
        raise RuntimeError(
            f"{pdf_title}: configuration {bom.configuration!r} reports "
            f"{bom.exploded_views} exploded view(s), but IView.ShowExploded failed"
        )
    _note(
        adapter,
        "EXPLODED ISOMETRIC — INSTALLATION ORDER",
        _EXPLODED_CENTER[0],
        0.252,
        label="exploded label",
    )
    reference_front = _place_hlr_view(
        adapter,
        source,
        "*Front",
        _REFERENCE_FRONT_CENTER,
        scale=reference_scale,
        configuration=bom.configuration,
    )
    reference_right = _place_hlr_view(
        adapter,
        source,
        "*Right",
        _REFERENCE_RIGHT_CENTER,
        scale=reference_scale,
        configuration=bom.configuration,
    )
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=_BOM_ANCHOR,
        expected_components=bom.components,
        descriptions=bom.descriptions,
        identity_aliases=bom.aliases,
        configuration_grouping="same-part",
        label=pdf_title,
    )
    if table is None:
        raise RuntimeError(f"{pdf_title}: associative BOM insertion returned no table")
    _validate_assembly_bom_columns(adapter, table, label=pdf_title)
    add_auto_balloons_across_views(
        adapter,
        (exploded, reference_front, reference_right),
        expected=len(bom.components),
        label=pdf_title,
        margin=0.012,
        layout=1,
    )
    _note(
        adapter,
        f"FRONT REFERENCE — SCALE {reference_scale[0]:g}:{reference_scale[1]:g}",
        _REFERENCE_FRONT_CENTER[0],
        0.018,
        label="front reference label",
    )
    _note(
        adapter,
        f"RIGHT REFERENCE — SCALE {reference_scale[0]:g}:{reference_scale[1]:g}",
        _REFERENCE_RIGHT_CENTER[0],
        0.018,
        label="right reference label",
    )
    _sheet_marker(adapter, 2)

    _activate_sheet(adapter, SHEET_NAMES[2])
    _place_hlr_view(
        adapter,
        source,
        "*Isometric",
        iso_center,
        scale=sheet_scale,
        configuration=bom.configuration,
    )
    numbered_steps = "\n".join(
        (
            "ORDERED ASSEMBLY",
            *(f"{index}. {line}" for index, line in enumerate(steps, 1)),
        )
    )
    check_text = "\n".join(
        ("ORIENTATION / ADJUSTMENT / ACCEPTANCE", *(f"• {line}" for line in checks))
    )
    hardware_text = "\n".join(
        ("HARDWARE / CONSUMABLES", *(f"• {line}" for line in hardware))
    )
    _note(adapter, numbered_steps, 0.020, 0.226, label="ordered assembly block")
    _note(adapter, hardware_text, 0.020, 0.158, label="hardware block")
    _note(adapter, check_text, 0.020, 0.100, label="critical check block")
    _note(
        adapter,
        "ASSEMBLED ISOMETRIC — WORKING POSITION",
        0.235,
        0.252,
        label="assembled isometric label",
    )
    _sheet_marker(adapter, 3)

    return await finalize_drawing(
        adapter,
        outputs,
        pdf_title=pdf_title,
        scale=sheet_scale,
        expected_sheet_names=SHEET_NAMES,
    )
