"""Drawing hole tables, BOM tables and hole-group tags.

Hole-table and BOM recipes share native schedules and datum tags here, while
drawings without tables stay independent.
"""

from __future__ import annotations

import json
from math import isfinite
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

# Global row index, native file/member occurrence counts, released Number, QTY.
BomSnapshot = tuple[tuple[int, tuple[tuple[str, str, int], ...], str, str], ...]


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
    observed: dict[tuple[int, str, str], int] = {}
    row_count_after = -1
    try:
        for row in range(1, row_count):
            components = tuple(annotation.GetComponents2(row, configuration) or ())
            if not components:
                raise RuntimeError(f"BOM row {row} has no native component association")
            row_keys: set[str] = set()
            for component in components:
                stem, member = component_identity(component)
                native_key = (row, stem, member)
                if native_key in observed or len(observed) < 64:
                    observed[native_key] = observed.get(native_key, 0) + 1
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
        row_count_after = int(table.RowCount)
        if row_count_after != row_count:
            raise RuntimeError(
                f"BOM row count changed while reading native associations: "
                f"{row_count} -> {row_count_after}"
            )
        missing = sorted(set(component_identities) - result.keys())
        if missing:
            raise RuntimeError(
                f"BOM native associations are missing members {missing!r}"
            )
    finally:
        _telemetry.annotate(
            configuration=configuration,
            rows_before=row_count,
            rows_after=row_count_after,
            expected_members=len(component_identities),
            observed_members=tuple(
                f"{row}:{stem[:96]}@{member[:96]}={count}"
                for (row, stem, member), count in observed.items()
            ),
        )
    return result


def _bom_visibility_offset(
    table: Any, kinds: Sequence[Any], declared: int, *, label: str
) -> tuple[int, int]:
    """Locate the latent Quantity columns of deselected BOM configurations.

    A top-level BOM keeps one Quantity column per available configuration
    (``IBomFeature.GetConfigurations`` remarks), in that configuration order.
    Only the selected configuration's column is in the typed/title/text
    ``IncludeHidden`` index domain; each deselected one stays latent, yet
    ``TotalColumnCount`` and the 0-based ``ColumnHidden``/``SetColumnHidden``
    domain still count it. Native paper-drive evidence with configurations
    ``('Default', 'Default Simplified')``: selecting Default Simplified put
    visibility index 4 on typed Qty3 and 5 on the trailing native201[4];
    selecting Default put index 4 on native201[4], while writing index 5
    materialized the latent Default Simplified Qty as a hidden column.

    Returns the typed index of the selected Quantity column and the number of
    latent columns that precede it (and every later typed column).
    """
    annotation = _sw_type_info.early_bound_or_flag(
        table, "IBomTableAnnotation", "BomFeature"
    )
    feature = annotation.BomFeature
    if feature is None:
        raise RuntimeError(f"{label} BOM table has no BOM feature")
    feature = _sw_type_info.early_bound_or_flag(
        feature, "IBomFeature", "GetConfigurations"
    )
    names, visibility = feature.GetConfigurations(False, None)
    names = tuple(names or ())
    visibility = tuple(visibility or ())
    if (
        not names
        or any(type(name) is not str or not name for name in names)
        or len(set(names)) != len(names)
        or len(visibility) != len(names)
        or any(type(visible) is not bool for visible in visibility)
        or sum(visibility) != 1
    ):
        raise RuntimeError(
            f"{label} BOM column visibility needs exactly one selected "
            f"configuration: names={repr(names)[:256]}, "
            f"visibility={repr(visibility)[:128]}"
        )
    quantities = [index for index, kind in enumerate(kinds) if kind == 203]
    latent = declared - len(kinds)
    if len(quantities) != 1 or latent != len(names) - 1:
        raise RuntimeError(
            f"{label} BOM Quantity columns do not match its configurations: "
            f"typed Quantity indices {quantities}, {latent} latent columns, "
            f"{len(names)} configurations"
        )
    return quantities[0], visibility.index(True)


def _bom_visibility_index(table: Any, physical_column: int, *, label: str) -> int:
    """Translate a typed physical column into the native visibility domain."""
    if type(physical_column) is not int or physical_column < 0:
        raise ValueError(f"{label} BOM physical column must be a nonnegative integer")
    declared = int(table.TotalColumnCount)
    kinds: list[Any] = []
    for index in range(declared):
        kind = table.GetColumnType3(index, True)[0]
        if type(kind) is int and kind == -1:
            break
        kinds.append(kind)
    quantity, latent_before = _bom_visibility_offset(
        table, kinds, declared, label=label
    )
    return physical_column + (latent_before if physical_column >= quantity else 0)


def _bom_column_hidden_at(
    table: Any, visibility_index: int, physical_column: int, *, label: str
) -> bool:
    hidden = table.ColumnHidden(visibility_index)
    if type(hidden) is not bool:
        raise RuntimeError(
            f"{label} BOM column visibility is not BOOL at physical index "
            f"{physical_column}"
        )
    return hidden


def _bom_column_hidden(table: Any, physical_column: int, *, label: str) -> bool:
    """Read the native visibility of a typed physical column."""
    index = _bom_visibility_index(table, physical_column, label=label)
    return _bom_column_hidden_at(table, index, physical_column, label=label)


def _set_bom_column_hidden(
    table: Any, physical_column: int, hidden: bool, *, label: str
) -> None:
    """Set visibility without changing physical typed/text or width indexing."""
    if type(physical_column) is not int or physical_column < 0:
        raise ValueError(f"{label} BOM physical column must be a nonnegative integer")
    if type(hidden) is not bool:
        raise ValueError(f"{label} BOM column hidden state must be BOOL")
    index = _bom_visibility_index(table, physical_column, label=label)
    table.SetColumnHidden(index, hidden)  # VT_VOID, not success.


def _bom_physical_columns(table: Any, *, label: str) -> tuple[tuple[int, bool], ...]:
    """Read the complete typed prefix, proving any advertised empty tail."""
    annotation = _sw_type_info.early_bound_or_flag(
        table, "IBomTableAnnotation", "GetColumnCustomProperty"
    )

    def unsupported(index: int, physical_type: Any) -> tuple[Any, ...]:
        visible_type = table.GetColumnType3(index, False)
        titles = (
            table.GetColumnTitle2(index, True),
            table.GetColumnTitle2(index, False),
        )
        headers = (
            table.DisplayedText2(0, index, True),
            table.DisplayedText2(0, index, False),
        )
        width = table.GetColumnWidth(index)
        hidden = _bom_column_hidden_at(table, visibility(index), index, label=label)
        binding = annotation.GetColumnCustomProperty(index)
        for kind, property_data, status in (physical_type, visible_type):
            if (
                type(kind) is not int
                or kind != -1
                or property_data is not None
                or type(status) is not int
                or status not in (0, 1)  # Observed Success / documented InvalidIndex.
            ):
                raise RuntimeError(
                    f"{label} BOM unsupported column type at physical index {index}"
                )
        if (
            titles != ("", "")
            or headers != ("", "")
            or type(width) is not float
            or width != 0.0
            or hidden is not False
            or binding != ""
        ):
            raise RuntimeError(
                f"{label} BOM nonempty unsupported column at physical index {index}"
            )
        return (physical_type, visible_type, titles, headers, width, hidden, binding)

    try:
        visible = int(table.ColumnCount)
        declared = int(table.TotalColumnCount)
        if not 1 <= visible <= declared <= 16:
            raise RuntimeError(
                f"{label} BOM physical column census bounds are {visible}/{declared}"
            )
        # Discover the whole typed prefix before reading visibility: latent
        # Quantity columns shift the visibility domain, not the typed one.
        typed_prefix: list[Any] = []
        typed_tail: list[tuple[int, Any]] = []
        in_tail = False
        for index in range(declared):
            physical_type = table.GetColumnType3(index, True)
            kind, _property_data, status = physical_type
            if type(kind) is int and kind == -1:
                typed_tail.append((index, physical_type))
                in_tail = True
                continue
            if (
                in_tail
                or type(kind) is not int
                or not (kind == 0 or 201 <= kind <= 211)
                or type(status) is not int
                or status != 0
            ):
                raise RuntimeError(
                    f"{label} BOM invalid typed column prefix at physical index {index}"
                )
            typed_prefix.append(physical_type)

        quantity, latent_before = _bom_visibility_offset(
            table, [physical_type[0] for physical_type in typed_prefix], declared,
            label=label,
        )

        def visibility(index: int) -> int:
            return index + (latent_before if index >= quantity else 0)

        physical: list[tuple[int, bool]] = []
        metadata: list[tuple[Any, Any, Any]] = []
        visible_index = 0
        for index, physical_type in enumerate(typed_prefix):
            kind, _property_data, _status = physical_type
            hidden = _bom_column_hidden_at(table, visibility(index), index, label=label)
            # The unversioned width accessor uses visible positions, not the
            # visibility domain. Hidden reads only prove a finite nonnegative
            # accessor result; they do not measure hidden width.
            width = table.GetColumnWidth(index if hidden else visible_index)
            if not hidden:
                visible_index += 1
            if (
                type(width) is not float
                or not isfinite(width)
                or width < 0.0
                or (not hidden and width == 0.0)
            ):
                raise RuntimeError(
                    f"{label} BOM invalid column visibility/width at physical index {index}"
                )
            physical.append((kind, hidden))
            metadata.append(
                (
                    physical_type,
                    table.GetColumnTitle2(index, True),
                    table.DisplayedText2(0, index, True),
                )
            )
        if not physical or sum(not hidden for _kind, hidden in physical) != visible:
            raise RuntimeError(
                f"{label} BOM typed column visibility count does not match {visible}"
            )
        # Advertised empty slots must match two independent beyond-count
        # controls in every accessor domain, including mapped visibility.
        control = unsupported(declared, table.GetColumnType3(declared, True))
        if control != unsupported(
            declared + 1, table.GetColumnType3(declared + 1, True)
        ):
            raise RuntimeError(f"{label} BOM unsupported column controls disagree")
        for index, physical_type in typed_tail:
            if unsupported(index, physical_type) != control:
                raise RuntimeError(
                    f"{label} BOM unsupported column tail disagrees at {index}"
                )
        visible_indices = [
            index for index, (_kind, hidden) in enumerate(physical) if not hidden
        ]
        for visible_index, physical_index in enumerate(visible_indices):
            visible_type = table.GetColumnType3(visible_index, False)
            kind, _property_data, status = visible_type
            projected = (
                visible_type,
                table.GetColumnTitle2(visible_index, False),
                table.DisplayedText2(0, visible_index, False),
            )
            if (
                type(kind) is not int
                or type(status) is not int
                or status != 0
                or projected != metadata[physical_index]
            ):
                observations = ""
                try:
                    columns = tuple(
                        (
                            index, visibility(index), kind, hidden,
                            repr(metadata[index][0])[:192],
                            str(metadata[index][1])[:96],
                            str(metadata[index][2])[:96],
                        )
                        for index, (kind, hidden) in enumerate(physical)
                    )
                    observations = (
                        f"; ColumnCount={visible}, TotalColumnCount={declared}; "
                        f"columns(physical,visibility_index,kind,hidden,type,title,header)"
                        f"={columns!r}; visible_read={repr(projected)[:512]}"
                    )
                except Exception:
                    pass  # Failure evidence must not replace the strict refusal.
                raise RuntimeError(
                    f"{label} BOM visible column projection disagrees at "
                    f"{visible_index} (physical {physical_index}){observations}"
                )
        return tuple(physical)
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(f"{label} BOM physical column census read failed") from error


def _bind_bom_number_property(
    adapter: Any,
    table: Any,
    *,
    configuration: str,
    label: str,
) -> None:
    """Display associative Numbers without replacing the native grouping column."""
    rows = int(table.RowCount)
    if int(table.TotalRowCount) != rows:
        raise RuntimeError(f"{label} BOM has hidden rows before Number binding")
    for row in range(rows):
        if table.RowHidden(row) is not False:
            raise RuntimeError(f"{label} BOM row {row} is not proven visible")
    headers = [
        str(table.DisplayedText2(0, column, True) or "").strip().upper()
        for column in range(int(table.ColumnCount))
    ]
    if "PART NUMBER" not in headers:
        raise RuntimeError(f"{label} BOM has no PART NUMBER column")
    column = headers.index("PART NUMBER")
    visible_columns = int(table.ColumnCount)
    physical = _bom_physical_columns(table, label=label)
    if any(hidden for _kind, hidden in physical):
        raise RuntimeError(f"{label} BOM starts with typed hidden columns")
    if [index for index, (kind, _hidden) in enumerate(physical) if kind == 201] != [
        column
    ]:
        raise RuntimeError(f"{label} BOM has no unique native PART NUMBER column")
    # Keep the native grouping key intact and physically last. Only the new
    # user-defined column is bound to the released Number custom property.
    native_column = len(physical) - 1
    moved = physical[:column] + physical[column + 1 :] + (physical[column],)
    if column != native_column:
        result = table.MoveColumn(
            column,
            3,
            native_column,  # swTableItemInsertPosition_After
        )
        if not result:
            raise RuntimeError(f"{label} BOM native column could not be moved")
        if _bom_physical_columns(table, label=label) != moved:
            raise RuntimeError(f"{label} BOM column sequence changed during move")
    result = table.InsertColumn2(
        2,
        column,
        "PART NUMBER",
        0,  # Before; swInsertColumn_DefaultWidth
    )
    if not result:
        raise RuntimeError(f"{label} BOM Number column could not be inserted")
    inserted = _bom_physical_columns(table, label=label)
    if (
        len(inserted) != len(moved) + 1
        or inserted[column] != (204, False)
        or inserted != moved[:column] + (inserted[column],) + moved[column:]
    ):
        raise RuntimeError(f"{label} BOM column sequence changed during insertion")
    native_column = len(inserted) - 1
    annotation = _sw_type_info.early_bound_or_flag(
        table, "IBomTableAnnotation", "SetColumnCustomProperty"
    )
    # Bind the already-204 column while every real column is still visible.
    result = annotation.SetColumnCustomProperty(column, "Number")
    if result is not True:
        raise RuntimeError(
            f"{label} BOM Number property binding failed: {result!r}"
        )
    if str(annotation.GetColumnCustomProperty(column) or "") != "Number":
        raise RuntimeError(f"{label} BOM Number property binding did not persist")
    if _bom_physical_columns(table, label=label) != inserted:
        raise RuntimeError(f"{label} BOM column sequence changed during Number binding")
    _set_bom_column_hidden(table, native_column, True, label=label)
    retained = inserted[:-1] + ((201, True),)
    if _bom_physical_columns(table, label=label) != retained:
        raise RuntimeError(f"{label} BOM retained native column is not hidden")
    if not table.SetColumnTitle2(column, "PART NUMBER", True):
        raise RuntimeError(f"{label} BOM PART NUMBER header could not be restored")
    rebuild_drawing(adapter, label="bind_bom_number_property")
    if int(table.ColumnCount) != visible_columns:
        raise RuntimeError(f"{label} BOM visible column count changed")
    validate_bom_number_property(table, configuration=configuration, label=label)


def _bom_number_column(table: Any, *, label: str) -> int:
    """Rediscover physical columns after SKU insertion, splitting or rebuilding."""
    visible = int(table.ColumnCount)
    physical = _bom_physical_columns(table, label=label)
    if len(physical) != visible + 1:
        raise RuntimeError(
            f"{label} BOM retained native column count is {visible}/{len(physical)}"
        )
    native_columns: list[int] = []
    number_columns: list[int] = []
    for index, (kind, hidden) in enumerate(physical):
        if hidden is not (index == visible):
            raise RuntimeError(
                f"{label} BOM visible columns are not a contiguous prefix"
            )
        if int(kind) == 201:  # swBomTableColumnType_PartNumber
            native_columns.append(index)
        if (
            index < visible
            and str(table.DisplayedText2(0, index, True) or "").strip().upper()
            == "PART NUMBER"
        ):
            # The BOM property getter proves the binding, not this raw variant.
            if int(kind) != 204:
                raise RuntimeError(f"{label} BOM Number column type/property changed")
            number_columns.append(index)
    if native_columns != [len(physical) - 1]:
        raise RuntimeError(f"{label} BOM has no unique trailing native column")
    if len(number_columns) != 1:
        raise RuntimeError(f"{label} BOM has no unique PART NUMBER column")
    return number_columns[0]


def validate_bom_number_property(
    table: Any,
    *,
    configuration: str,
    label: str,
    expected_rows: int | None = None,
    row_indices: Sequence[int] | None = None,
    occurrence_quantities: bool = False,
) -> BomSnapshot:
    """Read-prove columns/rows and snapshot membership, Number and quantity.

    Split pieces supply global ``row_indices``, never local renumbering.
    ``occurrence_quantities`` is an explicit count-based assembly contract;
    bulk or length quantities must leave it disabled.
    """
    from _com import _early_bound
    from _component_references import component_identity

    row_count = int(table.RowCount)
    if row_count < 2 or (expected_rows is not None and row_count != expected_rows):
        raise RuntimeError(
            f"{label} BOM Number proof has {row_count} rows; "
            f"expected {expected_rows if expected_rows is not None else 'at least 2'}"
        )
    data_rows = tuple(range(1, row_count) if row_indices is None else row_indices)
    if (
        not data_rows
        or len(set(data_rows)) != len(data_rows)
        or any(type(row) is not int or row < 1 for row in data_rows)
    ):
        raise RuntimeError(f"{label} BOM Number proof has invalid data row indices")
    if row_indices is None and int(table.TotalRowCount) != row_count:
        raise RuntimeError(f"{label} BOM Number proof has hidden rows")
    hidden_rows: list[list[Any]] = []
    try:
        for row in (0, *data_rows):
            try:
                hidden = table.RowHidden(row)
            except Exception as error:
                hidden_rows.append([row, f"{type(error).__name__}: {error}"[:160]])
                raise
            hidden_rows.append([row, hidden])
            if hidden is not False:
                raise RuntimeError(f"{label} BOM row {row} is not proven visible")
    finally:
        if row_indices is not None:
            # The caller has already proved these global rows belong to this
            # split piece. Record native visibility evidence, never infer it
            # from a false result on an unchecked row index.
            try:
                proof = {
                    "configuration": configuration,
                    "rows": row_count,
                    "total_rows": int(table.TotalRowCount),
                    "global_rows": list(data_rows[:64]),
                    "hidden": hidden_rows[:65],
                    "truncated": len(data_rows) > 64,
                }
                payload = json.dumps(proof, separators=(",", ":"))
                _telemetry.annotate(bom_split_row_visibility=payload)
                _telemetry.info("drawing.bom_split_row_visibility " + payload)
            except Exception:
                pass  # Visibility diagnostics cannot replace the strict proof.
    column = _bom_number_column(table, label=label)
    annotation = _sw_type_info.early_bound_or_flag(
        table, "IBomTableAnnotation", "GetColumnCustomProperty", "GetComponents2"
    )
    if str(annotation.GetColumnCustomProperty(column) or "") != "Number":
        raise RuntimeError(f"{label} BOM Number property binding did not persist")
    # Rediscovery above proves the visible physical columns are a contiguous
    # prefix, including after SKU insertion; only then map visible indices.
    visible_physical = tuple(range(int(table.ColumnCount)))
    quantity_columns = [
        index
        for index in visible_physical
        if table.GetColumnType3(index, True)[0] == 203
        and str(table.DisplayedText2(0, index, True) or "")
        .strip()
        .upper()
        .startswith("QTY")
    ]
    if len(quantity_columns) != 1:
        raise RuntimeError(f"{label} BOM has no unique quantity column")
    quantity_column = quantity_columns[0]

    def visible_cell(row: int, physical_column: int, name: str) -> str:
        physical_text = str(
            table.DisplayedText2(row, physical_column, True) or ""
        )
        visible_text = str(
            table.DisplayedText2(
                row, visible_physical.index(physical_column), False
            )
            or ""
        )
        if visible_text != physical_text:
            raise RuntimeError(
                f"{label} BOM row {row}: visible {name} {visible_text!r} "
                f"does not match physical {name} {physical_text!r}"
            )
        return physical_text.strip()

    visible_cell(0, column, "Number header")
    visible_cell(0, quantity_column, "quantity header")
    snapshot: list[tuple[int, tuple[tuple[str, str, int], ...], str, str]] = []
    for row in data_rows:
        components = tuple(annotation.GetComponents2(row, configuration) or ())
        if not components:
            raise RuntimeError(f"{label} BOM row {row} has no native components")
        numbers: set[str] = set()
        identities: dict[tuple[str, str], int] = {}
        for raw_component in components:
            component = _early_bound(raw_component, "IComponent2")
            identity = component_identity(component)
            identities[identity] = identities.get(identity, 0) + 1
            native = component.GetModelDoc2()
            if native is None:
                raise RuntimeError(
                    f"{label} BOM row {row}: component document is not resolved"
                )
            native = _early_bound(native, "IModelDoc2")
            member = str(component.ReferencedConfiguration or "")
            # SOLIDWORKS uses a configuration property before its document
            # property. Read the actual member, including Simplified children.
            number = str(
                native.GetCustomInfoValue(member, "Number")
                or native.GetCustomInfoValue("", "Number")
                or ""
            ).strip()
            if not number:
                raise RuntimeError(
                    f"{label} BOM row {row}: {component.Name2!r} "
                    f"configuration {member!r} has no Number property"
                )
            numbers.add(number)
        displayed = visible_cell(row, column, "Number")
        if len(numbers) != 1 or displayed not in numbers:
            raise RuntimeError(
                f"{label} BOM row {row}: associative Number {displayed!r} "
                f"does not match native component Numbers {sorted(numbers)!r}"
            )
        quantity = visible_cell(row, quantity_column, "quantity")
        if occurrence_quantities:
            # Only the four count-based assembly consumers opt in. Bulk/length
            # quantities must not be inferred from the number of native objects.
            try:
                printed_count = int(quantity)
            except ValueError:
                printed_count = -1
            if printed_count != len(components):
                raise RuntimeError(
                    f"{label} BOM row {row}: native occurrence count "
                    f"{len(components)} does not match printed quantity {quantity!r}"
                )
        snapshot.append(
            (
                row,
                tuple(
                    sorted(
                        (stem, member, count)
                        for (stem, member), count in identities.items()
                    )
                ),
                displayed,
                quantity,
            )
        )
    if int(table.RowCount) != row_count:
        raise RuntimeError(f"{label} BOM rows changed during its Number proof")
    return tuple(snapshot)


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
    part_number_property: Literal["Number"] | None = None,
    configuration_grouping: Literal["separate", "same-part", "same-name"] = "separate",
    configuration: str | None = None,
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
    ``part_number_property="Number"`` makes the PART NUMBER column associative
    to the model custom property without changing the internal BOM grouping key.
    ``configuration`` selects native BOM membership independently of the rendered
    view; ``None`` retains the view-derived configuration. An explicit name must
    be nonempty. Bind it before Number, quantity and layout authoring.
    ``descriptions`` maps a part number to its DESCRIPTION cell text (written
    per cell and read-verified) — the components carry no Description custom
    property, and a blank column reads as an unreleased sheet. A cell write on
    the template's ``$PRP:"Description"`` column writes back to the part's
    active configuration, so under an explicit ``configuration`` that column is
    first replaced by a plain inserted one and every row must be described.
    Returns the table rebound as ``ITableAnnotation``.
    """
    grouping_values = {"separate": 1, "same-part": 2, "same-name": 3}
    if configuration_grouping not in grouping_values:
        raise ValueError(f"unsupported BOM grouping {configuration_grouping!r}")
    if component_identities is not None and set(component_identities) != set(
        expected_components
    ):
        raise ValueError("BOM native identities must cover exactly the expected rows")
    if part_number_property not in (None, "Number"):
        raise ValueError("only the released Number custom property is supported")
    if part_number_property is not None and component_identities is None:
        raise ValueError("an associative Number column requires native row identities")
    if configuration is not None and not configuration.strip():
        raise ValueError("an explicit BOM configuration must be nonempty")
    _activate_and_select_view(adapter, view, label=label)
    draw = adapter.currentModel
    explicit_configuration = configuration is not None
    if configuration is None:
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
    # Top-level membership is selected through IBomFeature, not the insertion
    # Configuration argument. Set every available configuration's visibility
    # explicitly, rather than relying on the drawing-creation selection.
    bom = _sw_type_info.early_bound_or_flag(bom, "IBomTableAnnotation", "BomFeature")
    feature = adapter._get_attr_or_call(bom, "BomFeature")
    if feature is None:
        raise RuntimeError(f"{label} BOM table has no BOM feature")
    feature = _sw_type_info.early_bound_or_flag(
        feature,
        "IBomFeature",
        "SetConfigurations",
        "GetConfigurations",
        "PartConfigurationGrouping",
        "DisplayAsOneItem",
    )
    names, _visibility = feature.GetConfigurations(False, None)
    names = tuple(names or ())
    if (
        not names
        or any(type(name) is not str or not name for name in names)
        or len(set(names)) != len(names)
        or configuration not in names
    ):
        raise RuntimeError(
            f"{label} BOM requested configuration {configuration!r} is not "
            f"uniquely available: {repr(names)[:512]}"
        )
    # Use the complete available-name/visibility contract, including explicit
    # false flags for every other configuration, before authoring any columns.
    if feature.SetConfigurations(
        False,
        bool_array([name == configuration for name in names]),
        bstr_array(names),
    ) is not True:
        raise RuntimeError(
            f"failed to bind {label} BOM table to configuration {configuration!r}"
        )
    settled_names, settled_visibility = feature.GetConfigurations(False, None)
    settled_names = tuple(settled_names or ())
    settled_visibility = tuple(settled_visibility or ())
    if (
        len(settled_names) != len(names)
        or any(type(name) is not str for name in settled_names)
        or set(settled_names) != set(names)
        or len(settled_visibility) != len(settled_names)
        or any(type(visible) is not bool for visible in settled_visibility)
        or any(
            visible is not (name == configuration)
            for name, visible in zip(settled_names, settled_visibility, strict=True)
        )
    ):
        raise RuntimeError(
            f"{label} BOM configuration selection did not persist for "
            f"{configuration!r}: names={repr(settled_names)[:512]}, "
            f"visibility={repr(settled_visibility)[:256]}"
        )
    _telemetry.annotate(
        bom_configuration_names=settled_names,
        bom_configuration_visibility=settled_visibility,
    )
    # swDisplay_ConfigurationWithSameName_AsOneItem=3 groups the internal BOM
    # names, not the displayed released Number custom property. Retain the
    # established setter order and materialize grouped rows before binding it.
    grouping_value = grouping_values[configuration_grouping]
    setattr(feature, "PartConfigurationGrouping", grouping_value)
    setattr(feature, "DisplayAsOneItem", configuration_grouping == "same-part")
    draw.ForceRebuild3(False)
    rebuild_drawing(adapter, label="insert_bom_table")
    table = _sw_type_info.early_bound(bom, "ITableAnnotation")
    if not _sw_type_info.is_early_bound(table, "ITableAnnotation"):
        raise RuntimeError("ITableAnnotation early-bound wrapper is unavailable")
    _telemetry.annotate(
        configuration=configuration,
        rows_before_number_binding=int(table.RowCount),
        expected_rows=1 + len(expected_components),
        grouping_requested=grouping_values[configuration_grouping],
    )
    if part_number_property is not None:
        _bind_bom_number_property(
            adapter,
            table,
            configuration=configuration,
            label=label,
        )
    _telemetry.annotate(rows_after_number_binding=int(table.RowCount))
    actual_grouping = int(
        adapter._get_attr_or_call(feature, "PartConfigurationGrouping") or 0
    )
    actual_one_item = bool(adapter._get_attr_or_call(feature, "DisplayAsOneItem"))
    _telemetry.annotate(
        grouping_after_setup=actual_grouping,
        one_item_after_setup=actual_one_item,
    )
    if actual_grouping != grouping_value or actual_one_item != (
        configuration_grouping == "same-part"
    ):
        raise RuntimeError(
            f"{label} BOM configuration grouping did not persist: "
            f"grouping={actual_grouping}, one_item={actual_one_item}"
        )
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    if int(table.TotalRowCount) != rows:
        raise RuntimeError(f"{label} BOM has hidden rows before cell readback")
    for row in range(rows):
        if table.RowHidden(row) is not False:
            raise RuntimeError(f"{label} BOM row {row} is not proven visible")
    contents = tuple(
        tuple(
            str(
                adapter._attempt(
                    lambda row=row, column=column: table.DisplayedText2(
                        row, column, True
                    )
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
        if explicit_configuration:
            _replace_linked_bom_description_column(
                adapter, table, description_column, label=label
            )
        described = 0
        for row in range(1, rows):
            part = (
                str(
                    adapter._attempt(
                        lambda r=row: table.DisplayedText2(r, part_column, True)
                    )
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
                configuration=configuration,
            )
            described += 1
        if remaining:
            raise RuntimeError(
                f"{label} BOM descriptions not applied (no matching row): "
                f"{sorted(remaining)}"
            )
        if explicit_configuration and described != rows - 1:
            raise RuntimeError(
                f"{label} plain BOM DESCRIPTION column left "
                f"{rows - 1 - described} of {rows - 1} rows blank"
            )
        rebuild_drawing(adapter, label="insert_bom_table")
    final_rows = int(table.RowCount)
    final_columns = int(table.ColumnCount)
    final_grouping = int(
        adapter._get_attr_or_call(feature, "PartConfigurationGrouping") or 0
    )
    final_one_item = bool(adapter._get_attr_or_call(feature, "DisplayAsOneItem"))
    _telemetry.annotate(
        rows_after=final_rows,
        grouping_after=final_grouping,
        one_item_after=final_one_item,
    )
    if (final_rows, final_columns) != (rows, columns):
        raise RuntimeError(
            f"{label} BOM dimensions changed during finalization: "
            f"{rows}x{columns} -> {final_rows}x{final_columns}"
        )
    if final_grouping != grouping_value or final_one_item != (
        configuration_grouping == "same-part"
    ):
        raise RuntimeError(
            f"{label} BOM configuration grouping changed during finalization: "
            f"grouping={final_grouping}, one_item={final_one_item}"
        )
    if descriptions and native_rows is not None:
        final_native_rows = bom_row_identities(
            table,
            configuration=configuration,
            component_identities=component_identities,
        )
        if final_native_rows != native_rows:
            raise RuntimeError(
                f"{label} BOM native associations changed during finalization: "
                f"{native_rows!r} -> {final_native_rows!r}"
            )
    if part_number_property is not None:
        validate_bom_number_property(
            table,
            configuration=configuration,
            label=label,
            expected_rows=expected_rows,
        )
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
    configuration: str | None = None,
) -> None:
    """Write and verify one physical BOM cell."""
    table.SetText2(row, column, True, text)
    applied = str(table.DisplayedText2(row, column, True) or "")
    if applied != text:
        error = RuntimeError(f"{label} did not persist: {applied!r} != {text!r}")
        error.add_note(
            f"row {row} after write: "
            f"{_bom_cell_evidence(table, row, column, configuration)}"
        )
        raise error


def _replace_linked_bom_description_column(
    adapter: Any, table: Any, column: int, *, label: str
) -> None:
    """Stop DESCRIPTION cell writes from writing back into component models.

    Native PD runs 20261023T190254133Z and 20261023T192129678Z: SetText2 on any
    property-bound cell (even one rebound to a nonexistent property) writes the
    text into the part's active configuration. An inserted column has no
    property (as for the Number column above), so its cells hold plain text.
    """
    annotation = _sw_type_info.early_bound_or_flag(
        table, "IBomTableAnnotation", "GetColumnCustomProperty"
    )
    before = _bom_physical_columns(table, label=label)
    rows = int(table.RowCount)
    if before[column] != (204, False) or not str(
        annotation.GetColumnCustomProperty(column) or ""
    ):
        raise RuntimeError(f"{label} BOM DESCRIPTION column is not property-linked")
    if not table.InsertColumn2(
        3,  # swTableItemInsertPosition_After
        column,
        "DESCRIPTION",
        0,  # swInsertColumn_DefaultWidth
    ):
        raise RuntimeError(f"{label} BOM plain DESCRIPTION column could not be inserted")
    if not table.DeleteColumn2(column, True):
        raise RuntimeError(f"{label} BOM linked DESCRIPTION column could not be deleted")
    if _bom_physical_columns(table, label=label) != before or int(table.RowCount) != rows:
        raise RuntimeError(f"{label} BOM structure changed replacing DESCRIPTION")
    bound = str(annotation.GetColumnCustomProperty(column) or "")
    if bound:
        raise RuntimeError(f"{label} BOM DESCRIPTION column still reads property {bound!r}")
    if not table.SetColumnTitle2(column, "DESCRIPTION", True):
        raise RuntimeError(f"{label} BOM DESCRIPTION header could not be set")
    rebuild_drawing(adapter, label="replace_linked_bom_description_column")
    header = str(table.DisplayedText2(0, column, True) or "").strip().upper()
    if header != "DESCRIPTION":
        raise RuntimeError(f"{label} BOM DESCRIPTION header reads {header!r}")


def _bom_cell_evidence(
    table: Any, row: int, column: int, configuration: str | None
) -> str:
    """Bounded read-only evidence for a refused cell write; never replaces it."""
    evidence: dict[str, Any] = {}

    def read(key: str, call: Any) -> Any:
        try:
            evidence[key] = call()
        except Exception as error:  # Evidence only: keep the original refusal.
            evidence[key] = f"{type(error).__name__}: {str(error)[:160]}"
        return evidence[key]

    def collect() -> None:
        read("shown", lambda: table.DisplayedText2(row, column, True))
        read("raw", lambda: table.Text2(row, column, True))
        read("type", lambda: table.GetColumnType3(column, True))
        annotation = _sw_type_info.early_bound_or_flag(
            table, "IBomTableAnnotation", "GetColumnCustomProperty", "GetComponents2"
        )
        read("property", lambda: annotation.GetColumnCustomProperty(column))
        components = read(
            "components",
            lambda: tuple(annotation.GetComponents2(row, configuration or "") or ())[:1],
        )
        for component in components if isinstance(components, tuple) else ():
            component = _early_bound(component, "IComponent2")
            member = read("member", lambda: str(component.ReferencedConfiguration))
            model = read("model", component.GetModelDoc2)
            if model is None or isinstance(model, str):
                continue
            model = _early_bound(model, "IModelDoc2")
            read("path", lambda: str(model.GetPathName())[-48:])
            read("read_only", model.IsOpenedReadOnly)
            read("dirty", model.GetSaveFlag)
            read("prp_file", lambda: model.GetCustomInfoValue("", "Description"))
            names = read(
                "configurations", lambda: tuple(model.GetConfigurationNames() or ())[:6]
            )
            for name in names if isinstance(names, tuple) else ():
                read(
                    f"prp[{name}]",
                    lambda name=name: model.GetCustomInfoValue(name, "Description"),
                )
            native = read("config", lambda: model.GetConfigurationByName(member))
            if native is not None and not isinstance(native, str):
                native = _early_bound(native, "IConfiguration")
                read("bom_description", lambda: str(native.Description))
                read("use_bom_description", lambda: native.UseDescriptionInBOM)

    try:
        collect()
    except Exception as error:  # Evidence only.
        evidence["evidence_error"] = f"{type(error).__name__}: {str(error)[:160]}"
    for key in ("components", "model", "config"):
        evidence.pop(key, None)
    return repr(evidence)[:1200]
