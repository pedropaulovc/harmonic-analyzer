"""Experiment-only raw witnesses; never use these observations as validation."""
from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path

from _com import _early_bound


def _read(record, key, getter, encode=lambda value: value):
    try:
        value = getter()
        record[key] = encode(value)
        return value
    except Exception as error:
        record.setdefault("errors", {})[key] = repr(error)
        return None


def raw_owner(raw):
    result = {"chain": []}
    component = _read(result, "present", lambda: _early_bound(raw, "IComponent2"), lambda value: value is not None)
    for _ in range(64):
        if component is None:
            return result
        row = {}
        result["chain"].append(row)
        _read(row, "name", lambda: component.Name2)
        _read(row, "path", lambda: component.GetPathName())
        _read(row, "configuration", lambda: component.ReferencedConfiguration)
        _read(row, "visible", lambda: component.Visible)
        component = _read(row, "parent_present", lambda: _early_bound(component.GetParent(), "IComponent2"), lambda value: value is not None)
    result["truncated"] = "parent chain exceeded 64"
    return result


def raw_view_state(view):
    result = {}
    for key, getter in (
        ("name", lambda: view.GetName2()), ("type", lambda: view.Type),
        ("configuration", lambda: view.ReferencedConfiguration),
        ("use_parent_display", lambda: view.GetUseParentDisplayMode()),
        ("display_mode", lambda: view.GetDisplayMode2()),
        ("faceted_hlr", lambda: view.GetFacettedHlrDisplay()),
        ("edges_shaded", lambda: view.GetDisplayEdgesInShadedMode()),
        ("thread_quality", lambda: view.GetCThreadQuality()),
        ("position", lambda: list(view.Position)), ("scale", lambda: view.ScaleDecimal),
    ):
        _read(result, key, getter)
    return result


def _children(component, record):
    def getter():
        member = component.GetChildren
        return member() if callable(member) else member
    values = _read(record, "children_count", getter, lambda value: None if value is None else len(value))
    if values is None:
        return ()
    if not isinstance(values, (tuple, list)):
        record.setdefault("errors", {})["children_type"] = repr(type(values))
        return ()
    return values


def raw_view(adapter, view, retained_target):
    result = {"state": raw_view_state(view), "occurrences": [], "hidden_owners": []}
    _read(result, "view_self_same", lambda: adapter.swApp.IsSame(view, view))
    root = _read(result, "root_present", lambda: _early_bound(view.RootDrawingComponent2(False), "IDrawingComponent"), lambda value: value is not None)
    pending = [(raw, None) for raw in _children(root, result)] if root is not None else []
    native_owners = []
    drawing_components = []
    while pending and len(result["occurrences"]) < 4096:
        raw, parent_index = pending.pop()
        index = len(result["occurrences"])
        row = {"index": index, "parent_index": parent_index}
        result["occurrences"].append(row)
        component = _read(row, "present", lambda: _early_bound(raw, "IDrawingComponent"), lambda value: value is not None)
        drawing_components.append(component)
        native = None
        if component is not None:
            _read(row, "drawing_name", lambda: component.Name)
            _read(row, "visible_flag", lambda: component.Visible)
            native = _read(row, "owner_present", lambda: _early_bound(component.Component, "IComponent2"), lambda value: value is not None)
            row["owner"] = raw_owner(native)
            if native is not None:
                _read(row, "owner_self_same", lambda: adapter.swApp.IsSame(native, native))
                if retained_target is not None:
                    _read(row, "same_as_retained_target", lambda: adapter.swApp.IsSame(native, retained_target))
            pending.extend((child, index) for child in _children(component, row))
        native_owners.append(native)
    if pending:
        result["truncated_pending"] = len(pending)
    groups = defaultdict(list)
    for row in result["occurrences"]:
        name = row.get("drawing_name")
        if isinstance(name, str):
            groups[name].append(row["index"])
    result["duplicate_drawing_names"] = []
    for name, indices in groups.items():
        if len(indices) < 2:
            continue
        group = {"drawing_name": name, "indices": indices, "pairs": [], "possible_pairs": len(indices) * (len(indices) - 1) // 2}
        result["duplicate_drawing_names"].append(group)
        for offset, left in enumerate(indices):
            for right in indices[offset + 1:]:
                if len(group["pairs"]) == 64:
                    break
                pair = {"left": left, "right": right}
                group["pairs"].append(pair)
                _read(pair, "owner_same", lambda: adapter.swApp.IsSame(native_owners[left], native_owners[right]))
                _read(pair, "drawing_same", lambda: adapter.swApp.IsSame(drawing_components[left], drawing_components[right]))
        group["pairs_truncated"] = len(group["pairs"]) != group["possible_pairs"]
    hidden = _read(result, "hidden_returned_none", lambda: view.GetHiddenComponents(), lambda value: value is None)
    if hidden is not None:
        if isinstance(hidden, (tuple, list)):
            for raw in hidden:
                row = raw_owner(raw)
                if retained_target is not None:
                    _read(row, "same_as_retained_target", lambda: adapter.swApp.IsSame(_early_bound(raw, "IComponent2"), retained_target))
                result["hidden_owners"].append(row)
        else:
            result.setdefault("errors", {})["hidden_type"] = repr(type(hidden))
    return result


def raw_source(view, retained_target, app):
    result = {"base_chain": [], "owners": [], "file_hashes": {}}
    base = view
    for _ in range(64):
        state = raw_view_state(base)
        result["base_chain"].append(state)
        if state.get("type") != 2:
            break
        base = _read(state, "base_present", lambda: _early_bound(base.GetBaseView(), "IView"), lambda value: value is not None)
        if base is None:
            return result
    else:
        result["truncated"] = "base chain exceeded 64"
        return result
    model = _read(result, "document_present", lambda: _early_bound(base.ReferencedDocument, "IModelDoc2"), lambda value: value is not None)
    if model is None:
        return result
    path = _read(result, "path", lambda: model.GetPathName())
    _read(result, "type", lambda: model.GetType())
    _read(result, "save_flag", lambda: model.GetSaveFlag())
    _read(result, "active_configuration", lambda: _early_bound(_early_bound(model.ConfigurationManager, "IConfigurationManager").ActiveConfiguration, "IConfiguration").Name)
    components = _read(result, "component_count", lambda: _early_bound(model, "IAssemblyDoc").GetComponents(False), lambda value: None if value is None else len(value))
    files = {path} if isinstance(path, str) and path else set()
    if components is not None:
        if isinstance(components, (tuple, list)):
            for raw in components:
                row = raw_owner(raw)
                if retained_target is not None:
                    _read(row, "same_as_retained_target", lambda: app.IsSame(_early_bound(raw, "IComponent2"), retained_target))
                result["owners"].append(row)
                for owner in row["chain"]:
                    owner_path = owner.get("path")
                    if isinstance(owner_path, str) and owner_path:
                        files.add(owner_path)
        else:
            result.setdefault("errors", {})["components_type"] = repr(type(components))
    for path in sorted(files):
        def file_hash():
            with Path(path).open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").hexdigest()
        _read(result["file_hashes"], path, file_hash)
    return result


def raw_snapshot(adapter, view, retained_target):
    result = {"siblings": []}
    _read(result, "target", lambda: raw_view(adapter, view, retained_target))
    _read(result, "source", lambda: raw_source(view, retained_target, adapter.swApp))
    drawing = _read(result, "drawing_present", lambda: _early_bound(adapter.currentModel, "IDrawingDoc"), lambda value: value is not None)
    sheets = _read(result, "sheet_count", lambda: drawing.GetViews(), lambda value: None if value is None else len(value)) if drawing is not None else None
    if sheets is not None:
        for sheet_index, sheet in enumerate(sheets):
            for view_index, raw in enumerate(tuple(sheet)[1:]):
                row = {"sheet_index": sheet_index, "view_index": view_index}
                sibling = _read(row, "present", lambda: _early_bound(raw, "IView"), lambda value: value is not None)
                same = _read(row, "same_as_target_view", lambda: adapter.swApp.IsSame(sibling, view))
                if type(same) is int and same == 1:
                    continue
                result["siblings"].append(row)
                if sibling is not None:
                    _read(row, "view", lambda: raw_view(adapter, sibling, retained_target))
    return result


def observed_call(record, operation, snapshot, checkpoint):
    record["before_raw"] = snapshot()
    checkpoint()
    try:
        result = operation()
        record["operation"] = "returned"
        return result
    except Exception as error:
        record["operation_error"] = repr(error)
        raise
    finally:
        try:
            record["after_raw"] = snapshot()
        except Exception as error:
            record["after_raw_error"] = repr(error)
        checkpoint()
