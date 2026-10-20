"""Drawing hole tables, BOM tables and hole-group tags.

Hole-table and BOM recipes share native schedules and datum tags here, while
drawings without tables stay independent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Sequence

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import bool_array, bstr_array, dispatch_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_selection import _activate_and_select_view, _select_edge
import _telemetry


def add_hole_group_tags(
    adapter: Any,
    view: Any,
    tag: str,
    *,
    edge_points: Sequence[tuple[float, float]],
    note_positions: Sequence[tuple[float, float]],
) -> list[Any]:
    """Put the same short arrowed group tag on every hole in a group.

    ``IAnnotation.SetAttachedEntities`` throws for multiple edges on a note in
    SolidWorks 2026.  One leadered note per hole is both supported and clearer:
    the nearby schedule owns the full specification while every individual hole
    visibly carries its group letter.
    """
    if not edge_points:
        raise ValueError("hole group tags require at least one edge")
    if len(edge_points) != len(note_positions):
        raise ValueError("hole edge and tag-position counts differ")
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    notes: list[Any] = []
    for edge_point, note_position in zip(edge_points, note_positions, strict=True):
        draw.ClearSelection2(True)
        edge = _select_edge(adapter, *edge_point, append=False)
        note = draw.InsertNote(tag)
        if note is None:
            raise RuntimeError(f"failed to insert hole group tag {tag!r}")
        note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
        annotation = note.GetAnnotation()
        if annotation is None:
            raise RuntimeError(f"hole group tag has no annotation: {tag!r}")
        annotation = _sw_type_info.early_bound_or_flag(
            annotation,
            "IAnnotation",
            "GetAttachedEntityCount3",
            "SetAttachedEntities",
            "SetLeader3",
            "SetPosition2",
            "GetLeaderCount",
        )
        if int(annotation.GetAttachedEntityCount3()) != 1:
            if not annotation.SetAttachedEntities(dispatch_array([edge])):
                raise RuntimeError(f"failed to attach hole group tag {tag!r}")
        leader_status = annotation.SetLeader3(1, 0, True, False, False, False)
        if leader_status != 0:
            raise RuntimeError(
                f"failed to create hole-group tag leader: status={leader_status}"
            )
        if not annotation.SetPosition2(*note_position, 0.0):
            raise RuntimeError(f"failed to position hole group tag {tag!r}")
        rebuild_drawing(adapter, label="add_hole_group_tags")
        if (
            int(annotation.GetAttachedEntityCount3()) != 1
            or int(annotation.GetLeaderCount()) != 1
        ):
            raise RuntimeError(f"hole group tag {tag!r} lacks one attached arrow")
        notes.append(note)
    draw.ClearSelection2(True)
    return notes


def hole_table_template(adapter: Any) -> Path:
    executable = adapter._attempt(
        lambda: adapter.swApp.GetExecutablePath(), default=None
    )
    if not executable:
        raise RuntimeError("SolidWorks executable path is unavailable")
    install_root = Path(str(executable)).parent
    relative = Path("lang") / "english" / "standard hole table--letters.sldholtbt"
    candidates = (install_root / relative, install_root / "SOLIDWORKS" / relative)
    for template in candidates:
        if template.is_file():
            return template
    raise FileNotFoundError(
        "native hole-table template is missing; checked "
        + ", ".join(str(path) for path in candidates)
    )


@_telemetry.traced("drawing.theoretical_datum", label_param="label")
def create_view_theoretical_datum(
    adapter: Any,
    view: Any,
    *,
    point_xy: tuple[float, float],
    label: str,
) -> Any:
    """Create a view-owned datum point at a broken theoretical corner.

    ``point_xy`` is in view-local model metres.  A drawing view has no model
    vertex at a filleted or chamfered theoretical sharp, so this creates a
    retained user ``ISketchPoint`` in the view's drawing sketch.  Native tables
    can use that point as their origin while callers derive its coordinates
    from authoritative model dimensions.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not drawing.ActivateView(name):
        raise RuntimeError(f"failed to activate theoretical-datum view {name!r}")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    previous_display = bool(sketch_manager.DisplayWhenAdded)
    sketch_manager.AddToDB = True
    sketch_manager.DisplayWhenAdded = True
    try:
        point = sketch_manager.CreatePoint(point_xy[0], point_xy[1], 0.0)
    finally:
        sketch_manager.AddToDB = previous_add_to_db
        sketch_manager.DisplayWhenAdded = previous_display
    if point is None:
        raise RuntimeError(f"failed to create {label} theoretical datum point")
    point = _early_bound(point, "ISketchPoint")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="create_view_theoretical_datum")
    return point


def insert_hole_table(
    adapter: Any,
    view: Any,
    *,
    datum_xy: tuple[float, float],
    hole_points: Sequence[tuple[float, float]],
    datum_entity: Any | None = None,
    datum_point: Any | None = None,
    datum_axes: tuple[Any, Any] | None = None,
    hole_entities: Sequence[Any] | None = None,
    expected_locations_mm: Sequence[tuple[float, float]] | None = None,
    anchor_xy: tuple[float, float],
    basic_locations: bool = True,
    label: str,
    starting_hole_tag: str = "A",
) -> Any:
    """Insert the model-associated TAG/X LOC/Y LOC/SIZE hole table on ``view``.

    ``datum_xy`` picks the origin VERTEX and each ``hole_points`` entry picks a
    hole EDGE, all in sheet meters.  Callers that can identify drawing-context
    entities topologically may additionally supply ``datum_entity`` and
    ``hole_entities``; those are selected directly with the same hole-table
    marks and the coordinates remain the count/diagnostic contract.  A part
    whose plan corners are broken can supply ``datum_axes=(x_axis_edge,
    y_axis_edge)`` for initial insertion.  When ``datum_point`` is also
    supplied, the table's native ``IDatumOrigin`` is then reattached to that
    view-owned theoretical-corner point.  ``starting_hole_tag`` lets multiple
    tables on one sheet use distinct tag families.  The table lands with its
    top-left corner at ``anchor_xy`` and is validated before returning.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate hole-table view {name!r}")
    draw.ClearSelection2(True)
    if hole_entities is not None and len(hole_entities) != len(hole_points):
        raise ValueError(
            f"{label} supplied {len(hole_entities)} hole entities for "
            f"{len(hole_points)} hole points"
        )

    def _select_entity(entity: Any, *, append: bool, mark: int) -> bool:
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        selection_data = _early_bound(
            selection_manager.CreateSelectData(), "ISelectData"
        )
        selection_data.Mark = mark
        selectable = _early_bound(entity, "IEntity")
        return bool(selectable.Select4(append, selection_data))

    if datum_axes is not None and datum_entity is not None:
        raise ValueError(f"{label} supplied multiple initial datum sources")
    if datum_point is not None and datum_axes is None and datum_entity is None:
        raise ValueError(f"{label} datum point requires an initial datum source")
    if datum_axes is not None:
        x_axis, y_axis = datum_axes
        datum = _select_entity(x_axis, append=False, mark=4) and _select_entity(
            y_axis, append=True, mark=8
        )
    elif datum_entity is not None:
        datum = _select_entity(datum_entity, append=False, mark=1)
    else:
        datum = draw.Extension.SelectByID2(
            "", "VERTEX", datum_xy[0], datum_xy[1], 0.0, False, 1, null_callout(), 0
        )
    if not datum:
        raise RuntimeError(f"failed to select {label} hole-table datum origin")
    selections = (
        zip(hole_points, hole_entities, strict=True)
        if hole_entities is not None
        else ((point, None) for point in hole_points)
    )
    for (x, y), entity in selections:
        if entity is not None:
            selected = _select_entity(entity, append=True, mark=2)
        else:
            selected = draw.Extension.SelectByID2(
                "", "EDGE", x, y, 0.0, True, 2, null_callout(), 0
            )
        if not selected:
            raise RuntimeError(
                f"failed to select {label} hole-table edge at sheet ({x:g}, {y:g})"
            )
    table = view.InsertHoleTable3(
        False,
        anchor_xy[0],
        anchor_xy[1],
        1,  # swBOMConfigurationAnchor_TopLeft
        starting_hole_tag,
        str(hole_table_template(adapter)),
        1,  # swHoleTableTagOrder_XY
        1,  # swHoleTable_AlphaNumericTags
        None,
    )
    draw.ClearSelection2(True)
    if table is None:
        raise RuntimeError(f"SolidWorks failed to create the {label} hole table")
    table = _sw_type_info.early_bound_or_flag(table, "IHoleTableAnnotation")
    feature = table.HoleTable
    if feature is None:
        raise RuntimeError("native hole table annotation has no feature")
    feature = _sw_type_info.early_bound_or_flag(feature, "IHoleTable")
    feature.CombineSameSize = False
    feature.CombineTags = False
    if datum_point is not None:
        draw.ClearSelection2(True)
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        selection_data = _early_bound(
            selection_manager.CreateSelectData(), "ISelectData"
        )
        selection_data.View = view
        point = _early_bound(datum_point, "ISketchPoint")
        if not point.Select4(False, selection_data):
            raise RuntimeError(f"failed to select {label} theoretical datum point")
        origin = _early_bound(feature.DatumOrigin, "IDatumOrigin")
        if not origin.Reattach():
            raise RuntimeError(f"failed to reattach {label} hole-table datum")
        draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_select_entity")
    table = _sw_type_info.early_bound(table, "ITableAnnotation")
    # Indexed COM properties such as Text2 are omitted by the late-bound
    # dispatch returned from IHoleTableAnnotation.  Wrap the same dispatch in
    # its generated early-bound interface before using the setter.
    if not _sw_type_info.is_early_bound(table, "ITableAnnotation"):
        raise RuntimeError("ITableAnnotation early-bound wrapper is unavailable")
    if basic_locations:
        for column, heading in ((1, "X LOC (BASIC)"), (2, "Y LOC (BASIC)")):
            if not table.IsCellTextEditable(0, column):
                raise RuntimeError(
                    f"native hole-table header column {column} is not editable"
                )
            table.SetText2(0, column, False, heading)
            applied_heading = str(table.DisplayedText2(0, column, False) or "")
            if applied_heading.upper() != heading:
                raise RuntimeError(
                    f"native hole-table header did not persist: {applied_heading!r}"
                )
        rebuild_drawing(adapter, label="_select_entity")
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    contents = tuple(
        tuple(
            str(
                adapter._attempt(
                    lambda row=row, column=column: table.DisplayedText(row, column)
                )
                or ""
            )
            for column in range(columns)
        )
        for row in range(rows)
    )
    expected_rows = 1 + len(hole_points)
    if (rows, columns) != (expected_rows, 4):
        raise RuntimeError(
            f"native hole table is {rows}x{columns}, "
            f"expected {expected_rows}x4: {contents!r}"
        )
    header = contents[0]
    expected = (
        "TAG",
        "X LOC (BASIC)" if basic_locations else "X LOC",
        "Y LOC (BASIC)" if basic_locations else "Y LOC",
        "SIZE",
    )
    if tuple(value.upper() for value in header) != expected:
        raise RuntimeError(f"native hole-table header is unexpected: {header!r}")
    if expected_locations_mm is not None:
        _check_hole_table_locations(contents, expected_locations_mm, label=label)
    _telemetry.success(f"native hole table inserted: {rows - 1} holes, header={header}")
    return table


def _check_hole_table_locations(
    contents: Sequence[Sequence[str]],
    expected_mm: Sequence[tuple[float, float]],
    *,
    label: str,
    tol_mm: float = 0.02,
) -> None:
    """Match every printed X/Y LOC cell against an expected station, one-to-one.

    SolidWorks computes the LOC cells from the model against the selected
    datum origin, and ``insert_hole_table`` otherwise validates only the
    header and row count -- so a mis-anchored origin (e.g. a fillet-arc
    endpoint picked instead of the theoretical corner) would shift every
    coordinate SILENTLY. Expected stations are matched as a SET (table rows
    are tag-ordered, not selection-ordered) within ``tol_mm`` (cells print
    at 2 decimals, so the honest floor is 0.005 rounding).
    """
    if len(expected_mm) != len(contents) - 1:
        raise RuntimeError(
            f"{label} hole table: {len(expected_mm)} expected locations for "
            f"{len(contents) - 1} rows"
        )
    printed: list[tuple[float, float, str]] = []
    for row in contents[1:]:
        try:
            printed.append((float(row[1]), float(row[2]), row[0]))
        except ValueError as error:
            raise RuntimeError(
                f"{label} hole table: unparseable LOC cells in row {row!r}"
            ) from error
    unmatched = list(range(len(printed)))
    for ex, ey in expected_mm:
        hit = next(
            (
                index
                for index in unmatched
                if abs(printed[index][0] - ex) <= tol_mm
                and abs(printed[index][1] - ey) <= tol_mm
            ),
            None,
        )
        if hit is None:
            table_dump = ", ".join(f"{tag}({x:g}, {y:g})" for x, y, tag in printed)
            raise RuntimeError(
                f"{label} hole table: no printed row matches expected "
                f"({ex:g}, {ey:g}) mm within {tol_mm}; table: {table_dump}"
            )
        unmatched.remove(hit)
    _telemetry.success(
        f"{label} hole table locations verified: {len(expected_mm)} stations "
        f"within {tol_mm} mm"
    )


def bom_table_template(adapter: Any) -> Path:
    """Path to the install's standard BOM table template (``bom-standard.sldbomtbt``)."""
    executable = adapter._attempt(
        lambda: adapter.swApp.GetExecutablePath(), default=None
    )
    if not executable:
        raise RuntimeError("SolidWorks executable path is unavailable")
    install_root = Path(str(executable)).parent
    relative = Path("lang") / "english" / "bom-standard.sldbomtbt"
    candidates = (install_root / relative, install_root / "SOLIDWORKS" / relative)
    for template in candidates:
        if template.is_file():
            return template
    raise FileNotFoundError(
        "native BOM-table template is missing; checked "
        + ", ".join(str(path) for path in candidates)
    )


def _bom_identity_map(
    expected_components: Sequence[str], identity_aliases: dict[str, str] | None
) -> dict[str, str]:
    """Map every accepted BOM identity to one normalized component stem."""
    expected = {component.strip().lower() for component in expected_components}
    if len(expected) != len(expected_components):
        raise ValueError("BOM expected-component identities are not unique")
    identities = {component: component for component in expected}
    for alias, component in (identity_aliases or {}).items():
        normalized_alias = alias.strip().lower()
        normalized_component = component.strip().lower()
        if normalized_component not in expected:
            raise ValueError(
                f"BOM identity alias {alias!r} targets unknown component {component!r}"
            )
        existing = identities.get(normalized_alias)
        if existing is not None and existing != normalized_component:
            raise ValueError(
                f"BOM identity alias {alias!r} maps to both "
                f"{existing!r} and {normalized_component!r}"
            )
        identities[normalized_alias] = normalized_component
    return identities


@_telemetry.traced("drawing.bom_row_identities")
def bom_row_identities(
    table: Any,
    *,
    configuration: str,
    component_identities: dict[str, tuple[str, str | None]],
) -> dict[str, int]:
    """Associate logical rows through native components, never displayed Number.

    Different members of a shared purchased file have the same released Number.
    Conversely, interchangeable occurrences of one member must share a row. The
    native row association proves both without depending on a mutable cell value.
    ``None`` permits any configuration of an otherwise unambiguous file family
    (for example, the deliberately grouped transgear wheels).
    """
    from _component_references import component_identity, member_configuration

    if not configuration:
        raise ValueError("a top-level BOM requires its assembly configuration")
    expected: dict[tuple[str, str | None], str] = {}
    for logical, (stem, member) in component_identities.items():
        identity = (
            stem.casefold(),
            member_configuration(member) if member is not None else None,
        )
        if identity in expected:
            raise ValueError(
                f"BOM rows {expected[identity]!r} and {logical!r} share {identity!r}"
            )
        expected[identity] = logical
    annotation = _sw_type_info.early_bound_or_flag(
        table, "IBomTableAnnotation", "GetComponents2"
    )
    row_count = int(table.RowCount)
    result: dict[str, int] = {}
    for row in range(1, row_count):
        components = tuple(annotation.GetComponents2(row, configuration) or ())
        if not components:
            raise RuntimeError(f"BOM row {row} has no native component association")
        row_keys: set[str] = set()
        for component in components:
            stem, member = component_identity(component)
            matches = {
                logical
                for (file_stem, member_name), logical in expected.items()
                if file_stem == stem and member_name in (None, member)
            }
            if len(matches) != 1:
                raise RuntimeError(
                    f"BOM row {row} component {(stem, member)!r} matches "
                    f"{sorted(matches)!r}; expected one logical member"
                )
            row_keys.update(matches)
        if len(row_keys) != 1:
            raise RuntimeError(
                f"BOM row {row} merged distinct members {sorted(row_keys)!r}"
            )
        logical = row_keys.pop()
        if logical in result:
            raise RuntimeError(f"BOM member {logical!r} appears in multiple rows")
        result[logical] = row
    missing = sorted(set(component_identities) - result.keys())
    if missing:
        raise RuntimeError(f"BOM native associations are missing members {missing!r}")
    return result


@_telemetry.traced("drawing.bom_table", label_param="label")
def insert_bom_table(
    adapter: Any,
    view: Any,
    *,
    anchor_xy: tuple[float, float],
    expected_components: Sequence[str],
    descriptions: dict[str, str] | None = None,
    identity_aliases: dict[str, str] | None = None,
    component_identities: dict[str, tuple[str, str | None]] | None = None,
    configuration_grouping: Literal["separate", "same-part", "same-name"] = "separate",
    label: str,
) -> Any:
    """Insert a top-level parts BOM for an ASSEMBLY drawing view and validate it.

    ``IView.InsertBomTable6`` (the current variant; ``InsertBomTable4`` is
    obsolete) with the install's standard ITEM NO./PART NUMBER/DESCRIPTION/QTY
    template, anchored top-left at ``anchor_xy`` (sheet meters). Validated hard:
    one data row per ``expected_components`` entry and every expected part
    number present, so a BOM that silently dropped a component can never ship.
    ``identity_aliases`` maps alternate displayed identities (such as released
    part numbers) back to the expected component stems.
    ``component_identities`` instead binds logical member rows to native
    (file stem, configuration) identities; use it when Numbers repeat across
    configured members. ``same-name`` groups by the model's BOM part-number key,
    retaining distinct member keys while combining the transgear variants.
    ``descriptions`` maps a part number to its DESCRIPTION cell text (written
    per cell and read-verified) — the components carry no Description custom
    property, and a blank column reads as an unreleased sheet. Returns the
    table rebound as ``ITableAnnotation``.
    """
    grouping_values = {"separate": 1, "same-part": 2, "same-name": 3}
    if configuration_grouping not in grouping_values:
        raise ValueError(f"unsupported BOM grouping {configuration_grouping!r}")
    if component_identities is not None and set(component_identities) != set(
        expected_components
    ):
        raise ValueError("BOM native identities must cover exactly the expected rows")
    _activate_and_select_view(adapter, view, label=label)
    draw = adapter.currentModel
    configuration = str(
        adapter._get_attr_or_call(view, "ReferencedConfiguration") or "Default"
    )
    bom = view.InsertBomTable6(
        False,  # UseAnchorPoint=False -> place at the explicit X/Y below
        anchor_xy[0],
        anchor_xy[1],
        1,  # swBomConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft
        2,  # swBomType_e.swBomType_TopLevelOnly
        "",  # Configuration: top-level BOMs bind configs via SetConfigurations
        str(bom_table_template(adapter)),
        False,  # Hidden
        0,  # swNumberingType_e.swNumberingType_None (non-indented BOM)
        False,  # DetailedCutList
        False,  # DissolvePartLevelRows
        configuration_grouping == "same-part",
    )
    draw.ClearSelection2(True)
    if bom is None:
        raise RuntimeError(f"SolidWorks failed to create the {label} BOM table")
    # A COM-inserted top-level BOM starts with NO configuration bound (a
    # header-only table without even its per-configuration QTY column) --
    # IBomFeature::SetConfigurations is the documented binding path for
    # top-level tables, so bind the view's own configuration.
    bom = _sw_type_info.early_bound_or_flag(bom, "IBomTableAnnotation", "BomFeature")
    feature = adapter._get_attr_or_call(bom, "BomFeature")
    if feature is None:
        raise RuntimeError(f"{label} BOM table has no BOM feature")
    feature = _sw_type_info.early_bound_or_flag(
        feature,
        "IBomFeature",
        "SetConfigurations",
        "PartConfigurationGrouping",
        "DisplayAsOneItem",
    )
    if not feature.SetConfigurations(
        True, bool_array([True]), bstr_array([configuration])
    ):
        raise RuntimeError(
            f"failed to bind {label} BOM table to configuration {configuration!r}"
        )
    # swDisplay_ConfigurationWithSameName_AsOneItem=3 groups the internal BOM
    # names, not the displayed released Number custom property.
    grouping_value = grouping_values[configuration_grouping]
    setattr(feature, "PartConfigurationGrouping", grouping_value)
    setattr(feature, "DisplayAsOneItem", configuration_grouping == "same-part")
    actual_grouping = int(
        adapter._get_attr_or_call(feature, "PartConfigurationGrouping") or 0
    )
    actual_one_item = bool(adapter._get_attr_or_call(feature, "DisplayAsOneItem"))
    if actual_grouping != grouping_value or actual_one_item != (
        configuration_grouping == "same-part"
    ):
        raise RuntimeError(
            f"{label} BOM configuration grouping did not persist: "
            f"grouping={actual_grouping}, one_item={actual_one_item}"
        )
    draw.ForceRebuild3(False)
    rebuild_drawing(adapter, label="insert_bom_table")
    table = _sw_type_info.early_bound(bom, "ITableAnnotation")
    if not _sw_type_info.is_early_bound(table, "ITableAnnotation"):
        raise RuntimeError("ITableAnnotation early-bound wrapper is unavailable")
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    contents = tuple(
        tuple(
            str(
                adapter._attempt(
                    lambda row=row, column=column: table.DisplayedText(row, column)
                )
                or ""
            )
            for column in range(columns)
        )
        for row in range(rows)
    )
    expected_rows = 1 + len(expected_components)
    if rows != expected_rows or columns < 3:
        raise RuntimeError(
            f"{label} BOM table is {rows}x{columns}, expected {expected_rows} rows: "
            f"{contents!r}"
        )
    native_rows = (
        bom_row_identities(
            table,
            configuration=configuration,
            component_identities=component_identities,
        )
        if component_identities is not None
        else None
    )
    identities = (
        _bom_identity_map(expected_components, identity_aliases)
        if native_rows is None
        else {}
    )
    row_keys = (
        {row: logical.strip().lower() for logical, row in native_rows.items()}
        if native_rows is not None
        else {}
    )
    header = [cell.strip().upper() for cell in contents[0]]
    part_column = header.index("PART NUMBER") if "PART NUMBER" in header else None
    if native_rows is not None:
        observed = {logical.strip().lower() for logical in native_rows}
    elif part_column is None:
        observed = {cell.strip().lower() for row in contents[1:] for cell in row}
    else:
        observed = {
            identities.get(
                row[part_column].strip().lower(), row[part_column].strip().lower()
            )
            for row in contents[1:]
        }
    missing = sorted(
        component
        for component in expected_components
        if component.strip().lower() not in observed
    )
    if missing:
        raise RuntimeError(
            f"{label} BOM table is missing components {missing}: {contents!r}"
        )
    if descriptions:
        if "DESCRIPTION" not in header or "PART NUMBER" not in header:
            raise RuntimeError(
                f"{label} BOM header carries no DESCRIPTION/PART NUMBER: {header!r}"
            )
        description_column = header.index("DESCRIPTION")
        part_column = header.index("PART NUMBER")
        remaining = {key.strip().lower(): text for key, text in descriptions.items()}
        for row in range(1, rows):
            part = (
                str(
                    adapter._attempt(lambda r=row: table.DisplayedText(r, part_column))
                    or ""
                )
                .strip()
                .lower()
            )
            text = remaining.pop(row_keys.get(row, identities.get(part, part)), None)
            if text is None:
                continue
            if not table.IsCellTextEditable(row, description_column):
                raise RuntimeError(
                    f"{label} BOM description cell {row} is not editable"
                )
            _set_bom_cell_text(
                table,
                row,
                description_column,
                text,
                label=f"{label} BOM description",
            )
        if remaining:
            raise RuntimeError(
                f"{label} BOM descriptions not applied (no matching row): "
                f"{sorted(remaining)}"
            )
        rebuild_drawing(adapter, label="insert_bom_table")
    _telemetry.success(
        f"{label} BOM table inserted: {rows - 1} items, {columns} columns"
    )
    return table


def _set_bom_cell_text(
    table: Any,
    row: int,
    column: int,
    text: str,
    *,
    label: str,
) -> None:
    """Write and verify one visible BOM cell."""
    table.SetText2(row, column, False, text)
    applied = str(table.DisplayedText2(row, column, False) or "")
    if applied != text:
        raise RuntimeError(f"{label} did not persist: {applied!r} != {text!r}")
