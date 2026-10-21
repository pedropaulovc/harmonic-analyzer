"""Temporary paper-drive native BOM binding diagnosis; never save or continue.

Three independent, discarded BOMs distinguish native-column visibility from the
property being bound. This is not a production acceptance path or a repair.
Only the enumerated source properties, dirty flags, active configurations and
disk fingerprints are compared; an already-dirty model's full in-memory state
is not certified. Cached Get6 WasResolved=False remains unresolved evidence.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
import hashlib
import json
from pathlib import Path, PureWindowsPath
from typing import Any, NoReturn

from solidworks_mcp.adapters.com_variant import bool_array, bstr_array

from _com import _early_bound
from _component_references import component_identity, member_configuration
from _drawing_balloons import _view_component_leaves
from _drawing_common import rebuild_drawing
from _drawing_tables import (
    _activate_and_select_view,
    _annotate_bom_quantity_boundary,
    _bom_physical_columns,
    bom_row_identities,
    bom_table_template,
)
import _telemetry


_GEAR = "pd-transgear-removable"
_ARMS = (
    ("hidden_Number", "Number", True),
    ("visible_Number", "Number", False),
    ("hidden_Description", "Description", True),
)
_LIMITATION = (
    "Enumerated properties/dirty flags/active configurations/disk only; "
    "unchanged preexisting dirty=True does not prove the whole in-memory model. "
    "Get6 uses cached=True only; WasResolved=False is explicit uncertainty."
)


def _emit(stage: str, **evidence: Any) -> None:
    payload = json.dumps({"stage": stage, **evidence}, separators=(",", ":"))
    _telemetry.info("drawing.pd_bom_binding_matrix " + payload)
    _telemetry.annotate(**{f"pd_bom_matrix_{stage}": payload})


def _fact(
    call: Callable[[], Any], errors: list[Exception], label: str
) -> dict[str, Any]:
    """Keep independent raw outputs and failures, not false/empty substitutes."""
    try:
        value = call()
        return {"value": value, "raw": repr(value), "type": type(value).__name__}
    except Exception as error:
        error.add_note(f"PD BOM matrix: {label}")
        errors.append(error)
        return {"error": f"{type(error).__name__}: {error}"}


def _fingerprint(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    stat = path.stat()
    return {
        "path": str(path),
        "sha256": digest,
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _members(components: Sequence[Any]) -> tuple[tuple[str, str, int], ...]:
    if len(components) > 256:
        raise RuntimeError("PD BOM native component census exceeds 256 occurrences")
    counts: Counter[tuple[str, str]] = Counter()
    for raw in components:
        component = _early_bound(raw, "IComponent2")
        path = str(component.GetPathName() or "")
        configuration = str(component.ReferencedConfiguration or "")
        if not path or not configuration:
            raise RuntimeError("PD BOM native member has no full file/configuration")
        counts[path, configuration] += 1
    return tuple(
        (path, configuration, count)
        for (path, configuration), count in sorted(counts.items())
    )


def _view_members(adapter: Any, view: Any) -> tuple[Any, ...]:
    # Reuse the drawing-view traversal: source active configuration is NOT
    # evidence of the view's referenced configuration. Never activate a source.
    leaves = _view_component_leaves(adapter, view, label="PD BOM diagnostic source")
    if not leaves or len(leaves) > 256:
        raise RuntimeError("PD BOM reference view has no bounded native members")
    if any(leaf.component is None for leaf in leaves):
        raise RuntimeError("PD BOM reference drawing occurrence has no component")
    return tuple(_early_bound(leaf.component, "IComponent2") for leaf in leaves)


def _logical_members(
    components: Sequence[Any], identities: dict[str, tuple[str, str | None]]
) -> dict[str, tuple[tuple[str, str, int], ...]]:
    by_logical: dict[str, list[Any]] = {}
    for component in components:
        stem, member = component_identity(component)
        matches = [
            logical
            for logical, (file_stem, configuration) in identities.items()
            if file_stem.casefold() == stem
            and (configuration is None or member_configuration(configuration) == member)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"PD BOM source occurrence {(stem, member)!r} "
                f"has ambiguous logical identities {matches!r}"
            )
        by_logical.setdefault(matches[0], []).append(component)
    if set(by_logical) != set(identities):
        raise RuntimeError("PD BOM source/view does not contain all 43 logical members")
    return {logical: _members(by_logical[logical]) for logical in sorted(by_logical)}


def _cached_property(model: Any, configuration: str, name: str) -> dict[str, Any]:
    extension = _early_bound(model.Extension, "IModelDocExtension")
    manager = extension.CustomPropertyManager(configuration)  # Indexed PROPERTYGET.
    if manager is None:
        raise RuntimeError(f"no cached property manager for {configuration!r}")
    raw = _early_bound(manager, "ICustomPropertyManager").Get6(name, True)
    # Generated Get6 returns status followed by its four documented out values.
    # Preserve the entire tuple even if its shape unexpectedly differs.
    result: dict[str, Any] = {
        "raw_return": raw,
        "raw_repr": repr(raw),
        "UseCached": True,
    }
    if isinstance(raw, tuple) and len(raw) == 5:
        result.update(
            zip(
                ("status", "ValOut", "ResolvedValOut", "WasResolved", "LinkToProperty"),
                raw,
                strict=True,
            )
        )
    else:
        result["output_shape_unrecognized"] = True
    return result


def _model_facts(
    model: Any, configuration: str, errors: list[Exception], label: str
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "path": _fact(model.GetPathName, errors, label + ".path"),
        "dirty": _fact(model.GetSaveFlag, errors, label + ".dirty"),
        "active_configuration": _fact(
            lambda: str(
                _early_bound(
                    _early_bound(
                        model.ConfigurationManager, "IConfigurationManager"
                    ).ActiveConfiguration,
                    "IConfiguration",
                ).Name
            ),
            errors,
            label + ".active_configuration",
        ),
        "actual_configuration": configuration,
    }
    try:
        raw = model.GetConfigurationByName(configuration)
        if raw is None:
            raise RuntimeError(f"source configuration {configuration!r} is unavailable")
        native = _early_bound(raw, "IConfiguration")
    except Exception as error:
        error.add_note(f"PD BOM matrix: {label}.configuration_metadata")
        errors.append(error)
        facts["configuration_metadata"] = {"error": f"{type(error).__name__}: {error}"}
    else:
        facts["configuration_metadata"] = {
            name: _fact(
                lambda name=name: getattr(native, name),
                errors,
                label + ".configuration." + name,
            )
            for name in (
                "BOMPartNoSource",
                "AlternateName",
                "UseAlternateNameInBOM",
                "Description",
                "UseDescriptionInBOM",
            )
        }
    properties = {}
    for name in ("Number", "Description"):
        values = {}
        for scope, selected in (("configuration", configuration), ("document", "")):
            values[scope] = {
                "legacy": _fact(
                    lambda selected=selected, name=name: model.GetCustomInfoValue(
                        selected, name
                    ),
                    errors,
                    f"{label}.{scope}.{name}.legacy",
                ),
                "cached_Get6": _fact(
                    lambda selected=selected, name=name: _cached_property(
                        model, selected, name
                    ),
                    errors,
                    f"{label}.{scope}.{name}.cached_Get6",
                ),
            }
        member = values["configuration"]["legacy"]
        document = values["document"]["legacy"]
        if "value" in member and "value" in document:
            values["effective_legacy_fallback"] = (
                member["value"] or document["value"] or ""
            )
        else:
            values["effective_legacy_fallback_unavailable"] = True
        properties[name] = values
    facts["custom_properties"] = properties
    return facts


def _source_facts(
    sources: list[tuple[str, Any, str]],
    gears: Sequence[Any],
    errors: list[Exception],
    stage: str,
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "limitation": _LIMITATION,
        "documents": {},
        "gear_handles": [],
    }
    for label, model, configuration in sources:
        facts["documents"][label] = _model_facts(
            model, configuration, errors, f"{stage}.{label}"
        )
    for index, component in enumerate(gears):
        label = f"{stage}.gear_handle_{index}"
        facts["gear_handles"].append(
            {
                "native_identity": _fact(
                    lambda: component_identity(component), errors, label
                ),
                "full_path": _fact(component.GetPathName, errors, label + ".path"),
                "actual_configuration": _fact(
                    lambda: component.ReferencedConfiguration,
                    errors,
                    label + ".configuration",
                ),
                "name": _fact(lambda: component.Name2, errors, label + ".name"),
                "reference": _fact(
                    lambda: component.ComponentReference, errors, label + ".reference"
                ),
                "suppression": _fact(
                    component.GetSuppression, errors, label + ".suppression"
                ),
                "excluded": _fact(
                    lambda: component.ExcludeFromBOM, errors, label + ".excluded"
                ),
            }
        )
    _emit(stage, **facts)
    return facts


def _prove_drawing(app: Any, drawing: Any, title: str) -> dict[str, Any]:
    if (
        drawing.GetType() != 3
        or drawing.GetPathName() != ""
        or not title
        or drawing.GetTitle() != title
    ):
        raise RuntimeError("PD BOM probe does not own this exact unsaved drawing")
    if app.IsSame(app.ActiveDoc, drawing) != 1:
        raise RuntimeError("PD BOM owned drawing is not the native active document")
    inventory = tuple(app.GetDocuments() or ())
    same = [app.IsSame(raw, drawing) for raw in inventory]
    if any(value not in (0, 1) for value in same) or same.count(1) != 1:
        raise RuntimeError(f"PD BOM owned drawing inventory is ambiguous: {same!r}")
    titles = [str(_early_bound(raw, "IModelDoc2").GetTitle()) for raw in inventory]
    matching = [
        index
        for index, candidate in enumerate(titles)
        if candidate.casefold() == title.casefold()
    ]
    if matching != [same.index(1)]:
        raise RuntimeError(
            "PD BOM unsaved drawing title is ambiguous in native inventory"
        )
    return {
        "title": title,
        "path": "",
        "document_type": 3,
        "native_inventory_identity": same,
        "inventory_titles": titles,
    }


def _close_drawing(app: Any, drawing: Any, title: str, errors: list[Exception]) -> None:
    # No empty name, path/title lookup, CloseAllDocuments, source close or retry.
    safe = _fact(
        lambda: _prove_drawing(app, drawing, title), errors, "before_close.identity"
    )
    if "error" not in safe:
        result = _fact(lambda: app.CloseDoc(title), errors, "owned_drawing.CloseDoc")
        _fact(
            lambda: _emit("drawing_close", title=title, identity=safe, outcome=result),
            errors,
            "owned_drawing.close_log",
        )

    # CloseDoc disconnects its document proxy. Compare only fresh live records
    # against the unique signature whose native identity was proved above.
    def absence() -> dict[str, Any]:
        if "error" in safe:
            raise RuntimeError("owned drawing absence lacks pre-close native proof")
        documents = tuple(app.GetDocuments() or ())
        drawings = []
        for raw in documents:
            live = _early_bound(raw, "IModelDoc2")
            if int(live.GetType()) != 3:
                continue
            signature = {
                "title": str(live.GetTitle()),
                "path": str(live.GetPathName()),
                "document_type": 3,
            }
            if (
                signature["title"].casefold() == title.casefold()
                and not signature["path"]
            ):
                raise RuntimeError(
                    f"owned diagnostic drawing remains live: {signature!r}"
                )
            drawings.append(signature)
        return {
            "preclose_native_identity_verified": True,
            "owned_live_signature_absent": True,
            "remaining_drawings": drawings[:16],
            "remaining_drawings_capped": len(drawings) > 16,
            "remaining_count": len(documents),
        }

    absent = _fact(absence, errors, "after_close.native_inventory")
    _fact(
        lambda: _emit("drawing_absence", outcome=absent),
        errors,
        "after_close.native_inventory_log",
    )


def _configuration_names(raw: Any) -> tuple[str, ...]:
    # IBomFeature.GetConfigurations has a return SAFEARRAY plus an in/out
    # Visible SAFEARRAY. This is the generated wrapper's two-value result.
    if (
        not isinstance(raw, tuple)
        or len(raw) != 2
        or not isinstance(raw[0], (tuple, list))
        or any(not isinstance(name, str) for name in raw[0])
    ):
        raise RuntimeError(f"unrecognized native BOM configuration output: {raw!r}")
    return tuple(raw[0])


def _baseline(
    table: Any,
    annotation: Any,
    feature: Any,
    configuration: str,
    identities: dict[str, tuple[str, str | None]],
    source_members: dict[str, tuple[tuple[str, str, int], ...]],
    arm: str,
    stage: str,
) -> tuple[dict[str, Any], int, dict[str, int]]:
    if int(table.RowCount) != 44 or int(table.TotalRowCount) != 44:
        raise RuntimeError(f"{arm}: baseline is not 44 visible/native rows")
    if any(table.RowHidden(row) is not False for row in range(44)):
        raise RuntimeError(f"{arm}: baseline contains hidden/unreadable rows")
    if feature.PartConfigurationGrouping != 3 or feature.DisplayAsOneItem is not False:
        raise RuntimeError(f"{arm}: native same-name grouping baseline changed")
    available = feature.GetConfigurations(False, None)
    shown = feature.GetConfigurations(True, None)
    if feature.GetConfigurationCount(True) != 1 or _configuration_names(shown) != (
        configuration,
    ):
        raise RuntimeError(f"{arm}: baseline does not show exactly {configuration!r}")
    _configuration_names(available)
    rows = bom_row_identities(
        table, configuration=configuration, component_identities=identities
    )
    physical = _bom_physical_columns(table, label=f"{arm} {stage}")
    quantities = [
        index
        for index, (kind, hidden) in enumerate(physical)
        if kind == 203 and not hidden
    ]
    if len(quantities) != 1:
        raise RuntimeError(f"{arm}: baseline has no unique visible native Qty203")
    quantity = quantities[0]
    membership = {}
    controls: dict[str, int] = {}
    for logical, row in sorted(rows.items()):
        components = tuple(annotation.GetComponents2(row, configuration) or ())
        membership[logical] = _members(components)
        if membership[logical] != source_members[logical]:
            raise RuntimeError(
                f"{arm}: baseline full native file/config/count differs for {logical!r}"
            )
        driving = table.Text2(row, quantity, True)
        displayed = table.DisplayedText2(row, quantity, True)
        if logical != _GEAR and len(components) in (1, 2):
            expected = str(len(components))
            if driving == displayed == expected:
                controls.setdefault(expected, row)
    gear_row = rows[_GEAR]
    gear_members = membership[_GEAR]
    if (
        len(gear_members) != 3
        or any(count != 1 for _path, _cfg, count in gear_members)
        or len({path for path, _cfg, _count in gear_members}) != 1
        or sorted(member_configuration(cfg) for _path, cfg, _count in gear_members)
        != ["T12", "T18", "T24"]
    ):
        raise RuntimeError(f"{arm}: baseline lost the exact three native gear members")
    driving = table.Text2(gear_row, quantity, True)
    displayed = table.DisplayedText2(gear_row, quantity, True)
    if driving != "3" or displayed != "3":
        raise RuntimeError(
            f"{arm}: baseline gear Qty203 is {driving!r}/{displayed!r}, not 3/3"
        )
    if set(controls) != {"1", "2"}:
        raise RuntimeError(f"{arm}: baseline lacks Qty1/Qty2 positive controls")
    original_description = [
        {
            "physical_column": column,
            "type_raw": table.GetColumnType3(column, True),
            "custom_property": annotation.GetColumnCustomProperty(column),
            "driving": table.Text2(gear_row, column, True),
            "displayed": table.DisplayedText2(gear_row, column, True),
        }
        for column, (kind, _hidden) in enumerate(physical)
        if kind == 204 and annotation.GetColumnCustomProperty(column) == "Description"
    ]
    snapshot = {
        "configuration": configuration,
        "available_raw": available,
        "shown_raw": shown,
        "grouping": 3,
        "one_item": False,
        "rows": 44,
        "logical_members": len(rows),
        "members": membership,
        "gear_quantity": [driving, displayed],
    }
    _emit(
        f"{arm}_{stage}",
        baseline=snapshot,
        watched_row=gear_row,
        quantity_column=quantity,
        controls=controls,
        original_description_columns=original_description,
    )
    return snapshot, gear_row, controls


def _checkpoint(
    table: Any,
    annotation: Any,
    feature: Any,
    *,
    configuration: str,
    arm: str,
    stage: str,
    feature_name: str,
    watched: set[tuple[str, str]],
    gear_row: int,
    controls: dict[str, int],
    outcome: dict[str, str],
    errors: list[Exception],
) -> None:
    prefix = f"{arm}_{stage}"
    _annotate_bom_quantity_boundary(
        table,
        configuration=configuration,
        stage=prefix,
        watched=watched,
        outcome=outcome,
    )

    # Each accessor remains independent; a failed native read is never a pass.
    def read(call, label):
        return _fact(call, errors, f"{prefix}.{label}")

    available = read(lambda: feature.GetConfigurations(False, None), "available")
    shown = read(lambda: feature.GetConfigurations(True, None), "shown")
    metadata = {
        "available_raw": available,
        "shown_raw": shown,
        "available_count": read(
            lambda: feature.GetConfigurationCount(False), "available_count"
        ),
        "shown_count": read(lambda: feature.GetConfigurationCount(True), "shown_count"),
        "grouping": read(lambda: feature.PartConfigurationGrouping, "grouping"),
        "one_item": read(lambda: feature.DisplayAsOneItem, "one_item"),
        "ZeroQuantityDisplay": read(
            lambda: feature.ZeroQuantityDisplay, "zero_quantity"
        ),
        "ZeroQuantityDisplay_enum": {"blank": 3, "dash": 1, "zero": 2},
        "configuration_evidence_scope": "row/config attribution, NOT Qty-column mapping",
    }
    columns = []
    declared = read(lambda: int(table.TotalColumnCount), "declared_columns")
    for column in range(min(declared.get("value", 0), 8)):
        columns.append(
            {
                "physical_column": column,
                "type_including_hidden_raw": read(
                    lambda: table.GetColumnType3(column, True), f"column{column}.type"
                ),
                "type_visible_index_raw": read(
                    lambda: table.GetColumnType3(column, False),
                    f"column{column}.visible_type",
                ),
                "title": read(
                    lambda: table.GetColumnTitle2(column, True), f"column{column}.title"
                ),
                "hidden": read(
                    lambda: table.ColumnHidden(column), f"column{column}.hidden"
                ),
                "custom_property": read(
                    lambda: annotation.GetColumnCustomProperty(column),
                    f"column{column}.binding",
                ),
            }
        )
    rows = []
    for label, row in (("gear", gear_row), *sorted(controls.items())):
        rows.append(
            {
                "baseline_role": label,
                "baseline_row": row,
                "native_members": read(
                    lambda: _members(
                        tuple(annotation.GetComponents2(row, configuration) or ())
                    ),
                    f"row{row}.members",
                ),
                "cells": [
                    {
                        "physical_column": column,
                        "driving": read(
                            lambda: table.Text2(row, column, True),
                            f"row{row}.column{column}.driving",
                        ),
                        "displayed": read(
                            lambda: table.DisplayedText2(row, column, True),
                            f"row{row}.column{column}.displayed",
                        ),
                    }
                    for column in range(min(declared.get("value", 0), 8))
                ],
            }
        )
    new_displayed = read(
        lambda: table.DisplayedText2(gear_row, 1, True), "new_custom.gear_displayed"
    )
    new_driving = read(
        lambda: table.Text2(gear_row, 1, True), "new_custom.gear_driving"
    )
    new_state = (
        (
            "empty"
            if new_displayed["value"] == ""
            else "filled"
            if isinstance(new_displayed["value"], str)
            else "uninterpreted"
        )
        if "value" in new_displayed
        else "read_failed"
    )
    per_configuration = []
    if "value" in available:
        names = read(
            lambda: _configuration_names(available["value"]), "available_names"
        )
        for name in names.get("value", ())[:4]:
            per_configuration.append(
                {
                    "configuration": name,
                    "baseline_watched_row": gear_row,
                    "GetComponentsCount2_raw": read(
                        lambda: annotation.GetComponentsCount2(gear_row, name),
                        f"{name}.count_raw",
                    ),
                    "GetComponents2_members": read(
                        lambda: _members(
                            tuple(annotation.GetComponents2(gear_row, name) or ())
                        ),
                        f"{name}.members",
                    ),
                }
            )
    _emit(
        prefix,
        feature_name=feature_name,
        outcome=outcome,
        configuration=configuration,
        row_count=read(lambda: table.RowCount, "rows"),
        total_rows=read(lambda: table.TotalRowCount, "total_rows"),
        visible_columns=read(lambda: table.ColumnCount, "visible_columns"),
        declared_columns=declared,
        metadata=metadata,
        columns=columns,
        rows=rows,
        per_configuration=per_configuration,
        new_custom_gear_cell={
            "driving": new_driving,
            "displayed": new_displayed,
            "display_state": new_state,
            "valid_property_positive_control_claimed": False,
        },
        caps={
            "columns": declared.get("value", 0) > 8,
            "configurations": len(names.get("value", ())) > 4
            if "value" in available
            else False,
        },
        observation_timing="immediate; no title write or post-binding rebuild",
        description_scope="Configuration.Description/UseDescriptionInBOM and CP Description differ; a blank new Description cell is not a validated positive control",
    )


def _delete_feature(
    app: Any,
    drawing: Any,
    drawing_doc: Any,
    feature: Any,
    name: str,
    arm: str,
    errors: list[Exception],
) -> bool:
    before = len(errors)
    try:
        if app.IsSame(app.ActiveDoc, drawing) != 1:
            raise RuntimeError(f"{arm}: cannot delete outside the owned native drawing")
        drawing.ClearSelection2(True)
        selected = feature.Select2(False, 0)
        if selected is not True:
            raise RuntimeError(f"{arm}: owned feature Select2 returned {selected!r}")
        manager = _early_bound(drawing.SelectionManager, "ISelectionMgr")
        count = manager.GetSelectedObjectCount2(-1)
        if count != 1:
            raise RuntimeError(
                f"{arm}: owned feature selection count is {count!r}, not 1"
            )
        selected_type = manager.GetSelectedObjectType3(1, -1)
        raw_selected = manager.GetSelectedObject6(1, -1)
        raw_same = None if raw_selected is None else app.IsSame(raw_selected, feature)
        _fact(
            lambda: _emit(
                f"{arm}_selection_object",
                selected_count=count,
                selected_type=selected_type,
                wrapper_type=type(raw_selected).__name__,
                raw_selected_owned_IsSame=raw_same,
            ),
            errors,
            f"{arm}.cleanup.raw_selection_log",
        )
        if raw_selected is None:
            raise RuntimeError(f"{arm}: selected native object is unavailable")
        if selected_type == 97:  # swSelBOMFEATURES returns IBomFeature.
            selected_bom = _early_bound(raw_selected, "IBomFeature")
        elif selected_type == 98:  # swSelANNOTATIONTABLES requires a BOM subtype.
            selected_table = _early_bound(raw_selected, "ITableAnnotation")
            if int(selected_table.Type) != 2:  # swTableAnnotation_BillOfMaterials
                raise RuntimeError(f"{arm}: selected table is not a native BOM")
            selected_annotation = _early_bound(raw_selected, "IBomTableAnnotation")
            selected_bom = _early_bound(selected_annotation.BomFeature, "IBomFeature")
        else:
            raise RuntimeError(
                f"{arm}: unsupported selected native type {selected_type!r}"
            )
        selected_feature = selected_bom.GetFeature()
        if selected_feature is None:
            raise RuntimeError(f"{arm}: selected BOM has no native feature")
        same = app.IsSame(selected_feature, feature)
        _fact(
            lambda: _emit(
                f"{arm}_selection_feature",
                selected_type=selected_type,
                feature_name=str(_early_bound(selected_feature, "IFeature").Name),
                selected_owned_IsSame=same,
            ),
            errors,
            f"{arm}.cleanup.selected_feature_log",
        )
        if same != 1:
            raise RuntimeError(
                f"{arm}: selected/owned native feature identity is {same!r}"
            )
        deleted = _early_bound(
            drawing.Extension, "IModelDocExtension"
        ).DeleteSelection2(0)
        if deleted is not True:
            raise RuntimeError(
                f"{arm}: exact owned feature deletion returned {deleted!r}"
            )
        if drawing_doc.FeatureByName(name) is not None:
            raise RuntimeError(
                f"{arm}: exact owned feature {name!r} remains after deletion"
            )
        _emit(
            f"{arm}_feature_deleted",
            feature_name=name,
            selected_count=count,
            selected_owned_IsSame=same,
            DeleteSelection2=deleted,
            exact_name_absent=True,
        )
    except Exception as error:
        error.add_note(f"PD BOM matrix: {arm} strict owned-feature cleanup")
        errors.append(error)
    finally:
        cleared = _fact(
            lambda: drawing.ClearSelection2(True),
            errors,
            f"{arm}.cleanup.ClearSelection2",
        )
        _fact(
            lambda: _emit(f"{arm}_selection_cleared", outcome=cleared),
            errors,
            f"{arm}.cleanup.selection_log",
        )
    return len(errors) == before


@_telemetry.traced("drawing.pd_bom_binding_matrix")
def run_bom_binding_matrix(
    adapter: Any,
    view: Any,
    *,
    anchor_xy: tuple[float, float],
    expected_components: Sequence[str],
    component_identities: dict[str, tuple[str, str | None]],
    source: Path,
) -> NoReturn:
    """Discard three fresh native arms and always fail before production/save."""
    errors: list[Exception] = []
    sources: list[tuple[str, Any, str]] = []
    gears: tuple[Any, ...] = ()
    disk_paths = {source}
    disk_before: dict[Path, dict[str, Any]] = {}
    facts_before: dict[str, Any] | None = None
    drawing = app = None
    title = ""
    owned_drawing = False
    complete = False
    # Installed BEFORE any creation, cast, source read or other mutation. A raw
    # InsertBomTable6/cast failure is contained by closing this owned unsaved doc.
    try:
        drawing = _early_bound(adapter.currentModel, "IModelDoc2")
        app = _early_bound(adapter.swApp, "ISldWorks")
        title = str(drawing.GetTitle() or "")
        drawing_identity = _prove_drawing(app, drawing, title)
        owned_drawing = True
        _emit("drawing_identity", **drawing_identity)
        drawing_doc = _early_bound(drawing, "IDrawingDoc")
        view = _early_bound(view, "IView")
        configuration = str(
            adapter._get_attr_or_call(view, "ReferencedConfiguration") or "Default"
        )
        native_source = view.ReferencedDocument
        if native_source is None:
            raise RuntimeError("PD BOM reference view has no native source assembly")
        native_source = _early_bound(native_source, "IModelDoc2")
        sources.append(("assembly", native_source, configuration))
        if (
            native_source.GetType() != 2
            or PureWindowsPath(str(native_source.GetPathName())).as_posix().casefold()
            != PureWindowsPath(str(source)).as_posix().casefold()
        ):
            raise RuntimeError(
                "PD BOM view does not reference the requested native assembly"
            )
        if (
            len(expected_components) != 43
            or len(set(expected_components)) != 43
            or set(component_identities) != set(expected_components)
            or _GEAR not in component_identities
        ):
            raise ValueError(
                "PD BOM probe requires the exact 43-member native identity contract"
            )
        components = _view_members(adapter, view)
        source_members = _logical_members(components, component_identities)
        gears = tuple(
            component
            for component in components
            if component_identity(component)[0] == _GEAR
        )
        if len(gears) != 3:
            raise RuntimeError(
                "PD BOM view does not expose all three native gear handles"
            )
        for index, component in enumerate(gears):
            path = Path(str(component.GetPathName()))
            disk_paths.add(path)
            raw = component.GetModelDoc2()
            if raw is None:
                raise RuntimeError(
                    f"PD BOM gear handle {index} has no resolved native document"
                )
            sources.append(
                (
                    f"gear_handle_{index}",
                    _early_bound(raw, "IModelDoc2"),
                    str(component.ReferencedConfiguration),
                )
            )
        facts_before = _source_facts(sources, gears, errors, "source_before_matrix")
        for path in sorted(disk_paths):
            disk_before[path] = _fact(
                lambda path=path: _fingerprint(path),
                errors,
                f"before_matrix.disk.{path}",
            )
        template = bom_table_template(adapter)
        frozen_template = _fingerprint(template)
        disk_paths.add(template)
        disk_before[template] = {"value": frozen_template}
        _emit("template_frozen", **frozen_template)
        if errors:
            raise RuntimeError(
                "PD BOM source baseline is incomplete; no arm was created"
            )
        master_baseline = None
        watched = {component_identity(component) for component in gears}
        for arm, property_name, hide_before in _ARMS:
            raw_annotation = owned_feature = None
            feature_name = ""
            creation_attempted = False
            cleanup_status = "not_created"
            cleanup_ok = False
            arm_failed = False
            try:
                _prove_drawing(app, drawing, title)
                arm_facts = _source_facts(
                    sources, gears, errors, f"{arm}_source_before"
                )
                if arm_facts != facts_before:
                    raise RuntimeError(
                        f"{arm}: enumerated source facts changed before fresh arm"
                    )
                current_template = _fingerprint(template)
                if current_template != frozen_template:
                    raise RuntimeError(f"{arm}: frozen native BOM template changed")
                _emit(f"{arm}_template", **current_template)
                diagnostic_name = f"PD_BOM_PROBE_{arm}"
                if drawing_doc.FeatureByName(diagnostic_name) is not None:
                    raise RuntimeError(f"{arm}: diagnostic feature name already exists")
                _activate_and_select_view(
                    adapter, view, label=f"paper-drive probe {arm}"
                )
                # Exact public insert_bom_table native arguments and config /
                # grouping / rebuild order, but ownership is captured immediately.
                creation_attempted = True
                raw_annotation = view.InsertBomTable6(
                    False,
                    anchor_xy[0],
                    anchor_xy[1],
                    1,  # swBOMConfigurationAnchor_TopLeft
                    2,  # swBomType_TopLevelOnly
                    "",
                    str(template),
                    False,
                    0,  # swNumberingType_None
                    False,
                    False,
                    False,
                )
                drawing.ClearSelection2(True)
                if raw_annotation is None:
                    raise RuntimeError(f"{arm}: InsertBomTable6 returned no annotation")
                annotation = _early_bound(raw_annotation, "IBomTableAnnotation")
                feature = _early_bound(annotation.BomFeature, "IBomFeature")
                if feature is None:
                    raise RuntimeError(f"{arm}: fresh annotation has no BOM feature")
                raw_feature = feature.GetFeature()
                if raw_feature is None:
                    raise RuntimeError(f"{arm}: fresh BOM has no native feature handle")
                owned_feature = _early_bound(raw_feature, "IFeature")
                original_name = str(owned_feature.Name or "")
                owned_feature.Name = diagnostic_name
                feature_name = str(owned_feature.Name or "")
                if feature_name != diagnostic_name:
                    raise RuntimeError(
                        f"{arm}: diagnostic native feature name did not persist"
                    )
                if (
                    app.IsSame(drawing_doc.FeatureByName(feature_name), owned_feature)
                    != 1
                ):
                    raise RuntimeError(
                        f"{arm}: diagnostic feature lookup identity is unproven"
                    )
                _emit(
                    f"{arm}_feature_owned",
                    feature_name=feature_name,
                    original_name=original_name,
                    native_self_IsSame=app.IsSame(owned_feature, owned_feature),
                )
                if not feature.SetConfigurations(
                    True, bool_array([True]), bstr_array([configuration])
                ):
                    raise RuntimeError(
                        f"{arm}: native view configuration binding failed"
                    )
                feature.PartConfigurationGrouping = 3
                feature.DisplayAsOneItem = False
                drawing.ForceRebuild3(False)
                rebuild_drawing(adapter, label="insert_bom_table")
                table = _early_bound(annotation, "ITableAnnotation")
                baseline, gear_row, controls = _baseline(
                    table,
                    annotation,
                    feature,
                    configuration,
                    component_identities,
                    source_members,
                    arm,
                    "fresh_baseline",
                )
                if master_baseline is None:
                    master_baseline = baseline
                elif baseline != master_baseline:
                    raise RuntimeError(
                        f"{arm}: fresh baseline differs from earlier independent arms"
                    )
                physical = _bom_physical_columns(table, label=arm)
                if any(hidden for _kind, hidden in physical) or [
                    index
                    for index, (kind, _hidden) in enumerate(physical)
                    if kind == 201
                ] != [1]:
                    raise RuntimeError(
                        f"{arm}: initial native201 is not unique visible index1"
                    )
                moved = physical[:1] + physical[2:] + (physical[1],)
                if table.MoveColumn(1, 3, len(physical) - 1) is not True:
                    raise RuntimeError(f"{arm}: native201 move failed")
                if _bom_physical_columns(table, label=arm) != moved:
                    raise RuntimeError(
                        f"{arm}: native column move changed the column sequence"
                    )
                if table.InsertColumn2(2, 1, "PART NUMBER", 0) is not True:
                    raise RuntimeError(f"{arm}: custom204 insertion failed")
                inserted = moved[:1] + ((204, False),) + moved[1:]
                if _bom_physical_columns(table, label=arm) != inserted:
                    raise RuntimeError(
                        f"{arm}: inserted column is not fresh visible custom204 index1"
                    )
                native_column = len(inserted) - 1
                if hide_before:
                    table.SetColumnHidden(
                        native_column, True
                    )  # Generated PROPERTYPUT, VT_VOID.
                    if _bom_physical_columns(table, label=arm) != inserted[:-1] + (
                        (201, True),
                    ):
                        raise RuntimeError(
                            f"{arm}: original native201 hiding did not persist"
                        )
                prepared, gear_row, controls = _baseline(
                    table,
                    annotation,
                    feature,
                    configuration,
                    component_identities,
                    source_members,
                    arm,
                    "prepared_baseline",
                )
                if prepared != master_baseline:
                    raise RuntimeError(
                        f"{arm}: preparation changed the proven native baseline"
                    )

                def checkpoint(stage: str, outcome: dict[str, str]) -> None:
                    _fact(
                        lambda: _checkpoint(
                            table,
                            annotation,
                            feature,
                            configuration=configuration,
                            arm=arm,
                            stage=stage,
                            feature_name=feature_name,
                            watched=watched,
                            gear_row=gear_row,
                            controls=controls,
                            outcome=outcome,
                            errors=errors,
                        ),
                        errors,
                        f"{arm}.{stage}.checkpoint",
                    )

                checkpoint("before_bind", {})
                outcome = {
                    "method": "SetColumnCustomProperty",
                    "property": property_name,
                }
                binding_ok = False
                try:
                    result = annotation.SetColumnCustomProperty(1, property_name)
                    outcome["return"] = repr(result)
                    if result is not True:
                        raise RuntimeError(
                            f"{arm}: sole custom-property bind returned {result!r}"
                        )
                    binding_ok = True
                except Exception as error:
                    error.add_note(
                        f"PD BOM matrix: {arm} sole binding attempt; no retry"
                    )
                    errors.append(error)
                    outcome["error"] = f"{type(error).__name__}: {error}"
                finally:
                    checkpoint("after_bind", outcome)
                if not hide_before and binding_ok:
                    outcome = {
                        "method": "SetColumnHidden",
                        "native201_physical_column": str(native_column),
                    }
                    try:
                        result = table.SetColumnHidden(native_column, True)
                        outcome["return"] = repr(result)
                    except Exception as error:
                        error.add_note(f"PD BOM matrix: {arm} post-bind native201 hide")
                        errors.append(error)
                        outcome["error"] = f"{type(error).__name__}: {error}"
                    finally:
                        checkpoint("after_hide", outcome)
                # Deliberately NO title update, post-binding rebuild, quantity
                # edit, rebind, source write, grouping flip or production proof.
            except Exception as error:
                error.add_note(f"PD BOM matrix: {arm} primary/preparation failure")
                errors.append(error)
                arm_failed = True
            finally:
                if owned_feature is not None and feature_name:
                    deletion = _fact(
                        lambda: _delete_feature(
                            app,
                            drawing,
                            drawing_doc,
                            owned_feature,
                            feature_name,
                            arm,
                            errors,
                        ),
                        errors,
                        f"{arm}.cleanup",
                    )
                    cleanup_ok = deletion.get("value") is True
                    cleanup_status = "deleted" if cleanup_ok else "deletion_unproven"
                elif raw_annotation is not None:
                    cleanup_status = "partial_returned_handle; drawing_close_required"
                    errors.append(
                        RuntimeError(
                            f"{arm}: partial creation has no exact deletable "
                            "owned feature; close the owned unsaved drawing"
                        )
                    )
                elif creation_attempted:
                    cleanup_status = "no_returned_handle; drawing_close_required"
                    errors.append(
                        RuntimeError(
                            f"{arm}: native creation returned no owned handle; "
                            "feature cleanup is unproven until the owned drawing is closed"
                        )
                    )
                else:
                    cleanup_ok = True
                _fact(
                    lambda: _emit(
                        f"{arm}_cleanup",
                        creation_attempted=creation_attempted,
                        raw_annotation_captured=raw_annotation is not None,
                        feature_name=feature_name,
                        cleanup_status=cleanup_status,
                        strict_feature_cleanup=(
                            None
                            if creation_attempted and raw_annotation is None
                            else cleanup_ok
                        ),
                    ),
                    errors,
                    f"{arm}.cleanup.log",
                )
            if not cleanup_ok:
                raise RuntimeError(
                    f"{arm}: ambiguous cleanup; no next arm may be created"
                )
            if arm_failed:
                raise RuntimeError(
                    f"{arm}: failed native baseline/preparation; matrix aborted"
                )
        complete = True
    except Exception as error:
        error.add_note("PD BOM matrix primary/arm failure")
        errors.append(error)
    finally:
        # Source properties, dirty and active-configuration channels are read
        # while native source handles are still open. Every disk is then hashed
        # independently AFTER the drawing-close attempt, on every outcome.
        after = _fact(
            lambda: _source_facts(sources, gears, errors, "source_after_matrix"),
            errors,
            "finally.source_facts",
        )
        if facts_before is not None and "value" in after:
            unchanged = after["value"] == facts_before
            _fact(
                lambda: _emit(
                    "source_open_comparison",
                    unchanged=unchanged,
                    limitation=_LIMITATION,
                ),
                errors,
                "finally.source_comparison_log",
            )
            if not unchanged:
                errors.append(
                    RuntimeError("PD BOM enumerated source facts changed in memory")
                )
        else:
            _fact(
                lambda: _emit(
                    "source_open_comparison",
                    unchanged=None,
                    comparable=False,
                    limitation=_LIMITATION,
                ),
                errors,
                "finally.source_comparison_unavailable",
            )
        if owned_drawing:
            _fact(
                lambda: _close_drawing(app, drawing, title, errors),
                errors,
                "finally.owned_unsaved_drawing_close",
            )
        for path in sorted(disk_paths):
            after_disk = _fact(
                lambda path=path: _fingerprint(path), errors, f"after_close.disk.{path}"
            )
            before_disk = disk_before.get(path)
            comparable = (
                before_disk is not None
                and "value" in before_disk
                and "value" in after_disk
            )
            unchanged = (
                before_disk["value"] == after_disk["value"] if comparable else None
            )
            _fact(
                lambda path=path, before_disk=before_disk, after_disk=after_disk, comparable=comparable, unchanged=unchanged: (
                    _emit(
                        "source_disk_comparison",
                        path=str(path),
                        before=before_disk,
                        after=after_disk,
                        comparable=comparable,
                        unchanged=unchanged,
                    )
                ),
                errors,
                f"finally.disk_log.{path}",
            )
            if comparable and not unchanged:
                errors.append(
                    RuntimeError(
                        f"PD BOM source/template disk fingerprint changed: {path}"
                    )
                )
    if errors:
        raise ExceptionGroup(
            "PD BOM diagnostic failed; all independent failures retained", errors
        )
    if not complete:
        raise RuntimeError(
            "PD BOM diagnostic did not complete; production/save prohibited"
        )
    raise RuntimeError(
        "PD BOM binding diagnostic completed and cleaned up; deliberate stop "
        "before production insertion/save (not a production pass)"
    )
