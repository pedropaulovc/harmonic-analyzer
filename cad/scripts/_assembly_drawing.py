"""Shared multi-sheet assembly-package recipe."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import _telemetry
from _common import _early_bound, check
from _drawing_common import (
    DrawingOutputs,
    add_auto_balloons_across_views,
    add_note,
    create_blank_drawing_sheets,
    check_drawing_layout,
    finalize_drawing,
    insert_bom_table,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SHEET_NAMES = ("ASSEMBLED VIEWS", "EXPLODED AND BOM", "ASSEMBLY PROCEDURE")
_BORDER_LEFT = 0.012
_BORDER_RIGHT = 0.394
_BORDER_BOTTOM = 0.012
_BORDER_TOP = 0.267
_TITLE_BLOCK_LEFT = 0.200
_TITLE_BLOCK_TOP = 0.068


@dataclass(frozen=True)
class AssemblyDrawingLayout:
    """View and table geometry for one three-sheet assembly package."""

    working_scale: tuple[float, float]
    exploded_scale: tuple[float, float]
    procedure_scale: tuple[float, float]
    reference_scale: tuple[float, float]
    working_front_center: tuple[float, float] = (0.100, 0.165)
    working_right_center: tuple[float, float] = (0.285, 0.165)
    exploded_center: tuple[float, float] = (0.130, 0.178)
    reference_front_center: tuple[float, float] = (0.055, 0.052)
    reference_right_center: tuple[float, float] = (0.145, 0.052)
    procedure_center: tuple[float, float] = (0.305, 0.170)
    bom_anchor: tuple[float, float] = (0.222, 0.257)
    bom_row_height: float = 0.0045
    bom_column_widths: tuple[float, ...] = (0.025, 0.050, 0.080, 0.015)
    balloon_margin: float = 0.008
    working_display_mode: Literal[
        "hidden-lines-removed", "shaded-with-edges"
    ] = "hidden-lines-removed"

    def __post_init__(self) -> None:
        for name in (
            "working_scale",
            "exploded_scale",
            "procedure_scale",
            "reference_scale",
        ):
            scale = getattr(self, name)
            if len(scale) != 2 or min(scale) <= 0.0:
                raise ValueError(f"{name} must contain two positive values")
        for name in (
            "working_front_center",
            "working_right_center",
            "exploded_center",
            "reference_front_center",
            "reference_right_center",
            "procedure_center",
        ):
            x, y = getattr(self, name)
            if not (_BORDER_LEFT < x < _BORDER_RIGHT):
                raise ValueError(f"{name} x-coordinate lies outside the sheet border")
            if not (_BORDER_BOTTOM < y < _BORDER_TOP):
                raise ValueError(f"{name} y-coordinate lies outside the sheet border")
        for name in (
            "working_front_center",
            "working_right_center",
            "exploded_center",
            "procedure_center",
        ):
            if getattr(self, name)[1] <= _TITLE_BLOCK_TOP:
                raise ValueError(f"{name} must stay above the title-block band")
        for name in ("reference_front_center", "reference_right_center"):
            if getattr(self, name)[0] >= _TITLE_BLOCK_LEFT:
                raise ValueError("sheet-2 reference views must stay left of the title block")
        if not (
            _TITLE_BLOCK_LEFT < self.bom_anchor[0] < _BORDER_RIGHT
            and _TITLE_BLOCK_TOP < self.bom_anchor[1] <= _BORDER_TOP
        ):
            raise ValueError("BOM anchor must lie above the sheet-2 title block")
        if (
            self.bom_row_height <= 0.0
            or not self.bom_column_widths
            or min(self.bom_column_widths) <= 0.0
        ):
            raise ValueError("BOM row height and column widths must be positive")
        if self.bom_anchor[0] + sum(self.bom_column_widths) > _BORDER_RIGHT:
            raise ValueError("BOM columns extend through the right sheet border")
        if self.balloon_margin <= 0.0:
            raise ValueError("balloon margin must be positive")
        if self.working_display_mode not in (
            "hidden-lines-removed",
            "shaded-with-edges",
        ):
            raise ValueError(
                f"unsupported working-view display mode {self.working_display_mode!r}"
            )


@dataclass(frozen=True)
class _BomMetadata:
    components: tuple[str, ...]
    descriptions: dict[str, str]
    description_fallbacks: dict[str, str]
    quantities: dict[str, int]
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


def _component_property(
    adapter: Any, model: Any, configuration: str, name: str
) -> str:
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
    description_fallbacks: dict[str, str] = {}
    native_descriptions: set[str] = set()
    quantities: dict[str, int] = {}
    aliases: dict[str, str] = {}
    for raw_component in components:
        component = _early_bound(raw_component, "IComponent2")
        if bool(adapter._attempt(lambda: component.IsSuppressed(), default=False)):
            continue
        stem = _component_stem(adapter, component)
        model = adapter._attempt(lambda: component.GetModelDoc2(), default=None)
        referenced_configuration = str(
            adapter._attempt(lambda: component.ReferencedConfiguration, default="")
            or ""
        )
        native_description = ""
        native_number = ""
        if model is not None:
            model = _early_bound(model, "IModelDoc2")
            raw_configuration = adapter._attempt(
                lambda: getattr(model, "GetConfigurationByName", lambda _name: None)(
                    referenced_configuration
                ),
                default=None,
            )
            if raw_configuration is not None:
                part_configuration = _early_bound(raw_configuration, "IConfiguration")
                if bool(
                    adapter._attempt(
                        lambda: part_configuration.UseDescriptionInBOM, default=False
                    )
                ):
                    native_description = str(
                        adapter._attempt(
                            lambda: part_configuration.Description, default=""
                        )
                        or ""
                    ).strip()
                    if not native_description:
                        raise RuntimeError(
                            f"component {stem!r} configuration "
                            f"{referenced_configuration!r} uses a blank BOM description"
                        )
                if bool(
                    adapter._attempt(
                        lambda: part_configuration.UseAlternateNameInBOM, default=False
                    )
                ):
                    native_number = str(
                        adapter._attempt(
                            lambda: part_configuration.AlternateName, default=""
                        )
                        or ""
                    ).strip()
                    if not native_number:
                        raise RuntimeError(
                            f"component {stem!r} configuration "
                            f"{referenced_configuration!r} uses a blank BOM part number"
                        )
            native_description = native_description or _component_property(
                adapter, model, referenced_configuration, "Description"
            )
            title = _component_property(
                adapter, model, referenced_configuration, "Title"
            )
            number = _component_property(
                adapter, model, referenced_configuration, "Number"
            )
        else:
            title = ""
            number = ""
        description = (
            native_description
            or title
            or stem.replace("-", " ").replace("_", " ").title()
        )
        previous = descriptions.setdefault(stem, description)
        if previous != description:
            raise RuntimeError(
                f"component {stem!r} has conflicting BOM descriptions "
                f"{previous!r} and {description!r}"
            )
        if native_description:
            native_descriptions.add(stem)
            description_fallbacks.pop(stem, None)
        elif stem not in native_descriptions:
            description_fallbacks[stem] = description
        quantities[stem] = quantities.get(stem, 0) + 1
        for candidate_number in (number, native_number):
            if not candidate_number:
                continue
            normalized = candidate_number.casefold()
            prior = aliases.setdefault(normalized, stem)
            if prior != stem:
                raise RuntimeError(
                    f"BOM part number {candidate_number!r} identifies both "
                    f"{prior!r} and {stem!r}"
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
        description_fallbacks=description_fallbacks,
        quantities=quantities,
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


def _validate_assembly_bom_columns(
    adapter: Any, table: Any, metadata: _BomMetadata, *, label: str
) -> None:
    """Validate the native BOM's required cells, identities, descriptions, and counts."""
    table = _early_bound(table, "ITableAnnotation")
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    contents = [
        [
            str(
                adapter._attempt(
                    lambda row=row, column=column: table.DisplayedText(row, column),
                    default="",
                )
                or ""
            ).strip()
            for column in range(columns)
        ]
        for row in range(rows)
    ]
    headers = [cell.upper().rstrip(".") for cell in (contents[0] if contents else ())]
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
        if not contents[row][column]
    ]
    if blank_cells:
        raise RuntimeError(f"{label}: BOM has blank required cells: {blank_cells!r}")

    part_column = headers.index("PART NUMBER")
    description_column = headers.index("DESCRIPTION")
    identities = {component.casefold(): component for component in metadata.components}
    identities.update(
        {alias.casefold(): component for alias, component in metadata.aliases.items()}
    )
    observed: set[str] = set()
    for row in range(1, rows):
        displayed_identity = contents[row][part_column]
        component = identities.get(displayed_identity.casefold())
        if component is None:
            raise RuntimeError(
                f"{label}: BOM row {row} has incorrect part identity "
                f"{displayed_identity!r}"
            )
        if component in observed:
            raise RuntimeError(
                f"{label}: BOM has duplicate row identity {displayed_identity!r}"
            )
        observed.add(component)
        expected_description = metadata.descriptions[component]
        displayed_description = contents[row][description_column]
        if displayed_description != expected_description:
            raise RuntimeError(
                f"{label}: BOM description for {displayed_identity!r} is "
                f"{displayed_description!r}, expected {expected_description!r}"
            )
        displayed_quantity = contents[row][quantity_column]
        try:
            quantity = int(displayed_quantity)
        except ValueError as exc:
            raise RuntimeError(
                f"{label}: BOM quantity for {displayed_identity!r} is not an integer: "
                f"{displayed_quantity!r}"
            ) from exc
        expected_quantity = metadata.quantities[component]
        if quantity != expected_quantity:
            raise RuntimeError(
                f"{label}: BOM quantity for {displayed_identity!r} is {quantity}, "
                f"expected {expected_quantity}"
            )
    missing_components = sorted(set(metadata.components) - observed)
    if missing_components:
        raise RuntimeError(
            f"{label}: BOM is missing component rows {missing_components!r}"
        )


def _set_view_display_mode(
    adapter: Any,
    view: Any,
    mode: Literal["hidden-lines-removed", "shaded-with-edges"],
) -> None:
    if mode == "hidden-lines-removed":
        set_hidden_lines_removed(adapter, view)
        return
    # R2026x accepts enum 7 but reads it back as HLR (2).  The official API
    # example uses shaded (3) plus Edges=True; validate both independent states.
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(
            False,  # local view setting
            3,  # swDisplayMode_e.swSHADED; Edges carries the with-edges state
            False,  # precision geometry
            True,  # retain edges in shaded mode
            True,  # precision cosmetic threads
        ),
        default=False,
    )
    if not ok:
        raise RuntimeError("failed to set shaded-with-edges drawing view")
    adapter.currentModel.EditRebuild3()
    actual = int(adapter._attempt(lambda: view.GetDisplayMode2(), default=-1))
    if actual != 3:
        raise RuntimeError(
            f"shaded-with-edges drawing view read back display mode {actual}, expected 3"
        )
    edges = bool(
        adapter._attempt(lambda: view.GetDisplayEdgesInShadedMode(), default=False)
    )
    if not edges:
        raise RuntimeError("shaded drawing view did not retain visible edges")


def _place_drawing_view(
    adapter: Any,
    source: Path,
    view_name: str,
    center: tuple[float, float],
    *,
    scale: tuple[float, float],
    configuration: str,
    display_mode: Literal[
        "hidden-lines-removed", "shaded-with-edges"
    ] = "hidden-lines-removed",
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
    _set_view_display_mode(adapter, view, display_mode)
    return view


def _size_bom_table(
    adapter: Any,
    table: Any,
    *,
    anchor: tuple[float, float],
    row_height: float,
    column_widths: tuple[float, ...],
    label: str,
) -> None:
    """Compact the BOM proportionally, preserving rows expanded for wrapped text."""
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    if rows <= 1 or columns != len(column_widths):
        raise RuntimeError(
            f"{label} BOM sizing expects {len(column_widths)} columns and data rows; "
            f"got {rows}x{columns}"
        )
    actual_widths = []
    for column, width in enumerate(column_widths):
        actual = float(table.SetColumnWidth(column, width, 0))
        if actual <= 0.0:
            raise RuntimeError(f"{label} BOM column {column} has no readable width")
        actual_widths.append(actual)
    adapter.currentModel.EditRebuild3()
    original_heights = [
        float(table.GetRowHeight(row))
        for row in range(rows)
    ]
    if not original_heights or min(original_heights) <= 0.0:
        raise RuntimeError(f"{label} BOM has no readable row heights")
    baseline = min(original_heights)
    actual_heights = []
    for row, original in enumerate(original_heights):
        target = row_height * original / baseline
        actual = float(table.SetRowHeight(row, target, 0))
        if actual + 1e-6 < target:
            raise RuntimeError(
                f"{label} BOM row {row} height {actual:g} clipped below {target:g}"
            )
        actual_heights.append(actual)
    adapter.currentModel.EditRebuild3()
    bottom = anchor[1] - sum(actual_heights)
    right = anchor[0] + sum(actual_widths)
    if bottom < _TITLE_BLOCK_TOP or right > _BORDER_RIGHT:
        raise RuntimeError(
            f"{label} BOM crosses reserved sheet geometry: "
            f"bottom={bottom:g}, right={right:g}"
        )


def _sheet_marker(adapter: Any, number: int) -> None:
    _note(
        adapter,
        f"SHEET {number} OF {len(SHEET_NAMES)}",
        0.382,
        0.266,
        label=f"sheet {number} package marker",
    )


def _audit_package_layout(adapter: Any, pdf_title: str) -> None:
    for sheet_name in SHEET_NAMES:
        _activate_sheet(adapter, sheet_name)
        check_drawing_layout(adapter, stem=f"{pdf_title} / {sheet_name}")


@_telemetry.traced("drawing.assembly_package", label_param="pdf_title")
async def build_assembly_package(
    adapter: Any,
    *,
    source: Path,
    outputs: DrawingOutputs,
    sheet_scale: tuple[float, float],
    layout: AssemblyDrawingLayout,
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
    _place_drawing_view(
        adapter,
        source,
        "*Front",
        layout.working_front_center,
        scale=layout.working_scale,
        configuration=bom.configuration,
        display_mode=layout.working_display_mode,
    )
    _place_drawing_view(
        adapter,
        source,
        "*Right",
        layout.working_right_center,
        scale=layout.working_scale,
        configuration=bom.configuration,
        display_mode=layout.working_display_mode,
    )
    _note(
        adapter,
        "FRONT — WORKING POSITION",
        layout.working_front_center[0],
        0.264,
        label="front label",
    )
    _note(
        adapter,
        "RIGHT SIDE — WORKING POSITION",
        layout.working_right_center[0],
        0.264,
        label="right label",
    )
    _sheet_marker(adapter, 1)

    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = _place_drawing_view(
        adapter,
        source,
        "*Isometric",
        layout.exploded_center,
        scale=layout.exploded_scale,
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
        layout.exploded_center[0],
        0.264,
        label="exploded label",
    )
    reference_front = _place_drawing_view(
        adapter,
        source,
        "*Front",
        layout.reference_front_center,
        scale=layout.reference_scale,
        configuration=bom.configuration,
    )
    reference_right = _place_drawing_view(
        adapter,
        source,
        "*Right",
        layout.reference_right_center,
        scale=layout.reference_scale,
        configuration=bom.configuration,
    )
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=layout.bom_anchor,
        expected_components=bom.components,
        descriptions=bom.description_fallbacks,
        identity_aliases=bom.aliases,
        configuration_grouping="same-part",
        label=pdf_title,
    )
    if table is None:
        raise RuntimeError(f"{pdf_title}: associative BOM insertion returned no table")
    _validate_assembly_bom_columns(adapter, table, bom, label=pdf_title)
    _size_bom_table(
        adapter,
        table,
        anchor=layout.bom_anchor,
        row_height=layout.bom_row_height,
        column_widths=layout.bom_column_widths,
        label=pdf_title,
    )
    add_auto_balloons_across_views(
        adapter,
        (exploded, reference_front, reference_right),
        expected=len(bom.components),
        label=pdf_title,
        margin=layout.balloon_margin,
        layout=1,
    )
    _note(
        adapter,
        f"FRONT REFERENCE — SCALE {layout.reference_scale[0]:g}:"
        f"{layout.reference_scale[1]:g}",
        layout.reference_front_center[0],
        0.018,
        label="front reference label",
    )
    _note(
        adapter,
        f"RIGHT REFERENCE — SCALE {layout.reference_scale[0]:g}:"
        f"{layout.reference_scale[1]:g}",
        layout.reference_right_center[0],
        0.018,
        label="right reference label",
    )
    _sheet_marker(adapter, 2)

    _activate_sheet(adapter, SHEET_NAMES[2])
    _place_drawing_view(
        adapter,
        source,
        "*Isometric",
        layout.procedure_center,
        scale=layout.procedure_scale,
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
    _audit_package_layout(adapter, pdf_title)

    return await finalize_drawing(
        adapter,
        outputs,
        pdf_title=pdf_title,
        scale=sheet_scale,
        expected_sheet_names=SHEET_NAMES,
    )
