"""One-shot PR1849 native diagnostic; never merge this module into production.

Runs only on the isolated diagnostic branch. The supervised FR drawing leaf
captures B-B evidence, then intentionally fails before normal publication.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import math
from typing import Any, Callable, NoReturn
from pathlib import Path

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_projection import model_point_in_view
from _drawing_scan import _HIT_ZOOM_HALF, _zoomed_on
import _seat_forensics
import _telemetry


_VARIANTS = ("screen_control", "view_component", "view_safe")


def _observe(row: dict[str, Any], key: str, operation: Callable[[], Any]) -> Any:
    """Record each diagnostic rejection without skipping the other variants."""
    try:
        result = operation()
    except Exception as exc:  # noqa: BLE001 - evidence only; terminal failure is unconditional
        row[key] = {"error": f"{type(exc).__name__}: {exc}"}
        return None
    if result is None or isinstance(result, (str, int, float, bool)):
        row[key] = result
    elif isinstance(result, (tuple, list)) and all(
        item is None or isinstance(item, (str, int, float, bool)) for item in result
    ):
        row[key] = list(result)
    else:
        row[key] = {"python_type": f"{type(result).__module__}.{type(result).__name__}"}
    return result


def _same(adapter: Any, left: Any, right: Any) -> int | None:
    if left is None or right is None:
        return None
    return int(adapter.swApp.IsSame(left, right))


def _entity_state(adapter: Any, view: Any, entity: Any, sources: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    row: dict[str, Any] = {"is_null": entity is None}
    reverses: dict[str, Any] = {}
    if entity is None:
        return row, reverses
    row["python_type"] = f"{type(entity).__module__}.{type(entity).__name__}"
    _observe(row, "com_type_name", lambda: entity._oleobj_.GetTypeInfo().GetDocumentation(-1)[0])
    _observe(row, "com_type_guid", lambda: str(entity._oleobj_.GetTypeInfo().GetTypeAttr()[0]))
    bound = _early_bound(entity, "IEntity")
    _observe(row, "entity_type", lambda: int(bound.GetType()))
    _observe(row, "is_safe", lambda: bool(bound.IsSafe))
    component = _observe(row, "get_component", bound.GetComponent)
    row["component_is_null"] = component is None
    if component is not None:
        component = _early_bound(component, "IComponent2")
        _observe(row, "component_name", lambda: str(component.Name2))
        _observe(row, "component_path", lambda: str(component.GetPathName()))
        _observe(row, "component_configuration", lambda: str(component.ReferencedConfiguration))
    for name, source in sources.items():
        reverse = None
        if source is not None:
            reverse = _observe(
                row, f"{name}_reverse",
                lambda source=source: _early_bound(source.Extension, "IModelDocExtension").GetCorrespondingEntity2(entity),
            )
        row[f"{name}_reverse_is_null"] = reverse is None
        reverses[name] = reverse
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    selection: dict[str, Any] = {}
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = manager.CreateSelectData()
    data.View = view
    selected = _observe(selection, "selected", lambda: bool(bound.Select4(False, data)))
    if selected:
        count = _observe(selection, "count", lambda: int(manager.GetSelectedObjectCount2(-1)))
        if count:
            actual = _observe(selection, "entity", lambda: manager.GetSelectedObject6(count, -1))
            actual_view = _observe(selection, "view", lambda: manager.GetSelectedObjectsDrawingView2(count, -1))
            _observe(selection, "entity_type", lambda: int(manager.GetSelectedObjectType3(count, -1)))
            _observe(selection, "same_entity", lambda: _same(adapter, actual, entity))
            _observe(selection, "same_view", lambda: _same(adapter, actual_view, view))
            if actual_view is not None:
                _observe(selection, "view_name", lambda: view_name(adapter, actual_view))
    draw.ClearSelection2(True)
    row["selection"] = selection
    return row, reverses


def _screen_control(adapter: Any, view: Any, xy: tuple[float, ...], recipe: Any, row: dict[str, Any]) -> Any:
    """One original-main zoomed pick at z25; no station search or retry."""
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("diagnostic cannot activate B-B for its screen control")
    draw.ClearSelection2(True)
    with _zoomed_on(adapter, (xy[0], xy[1]), _HIT_ZOOM_HALF):
        selected = draw.Extension.SelectByID2(
            "", "EDGE", xy[0], xy[1], 0.0, False, 0, null_callout(), 0,
        )
    row["selected"] = bool(selected)
    if not selected:
        return None
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    count = int(manager.GetSelectedObjectCount2(-1))
    actual_view = manager.GetSelectedObjectsDrawingView2(count, -1)
    row["same_view"] = _same(adapter, actual_view, view)
    edge, owner, xs = recipe._read_selected_inset_edge(adapter)
    row.update(owner=owner, machine_x_mm=xs)
    return edge


def _target_snapshot(
    adapter: Any, view: Any, recipe: Any, leaves: Any, target: tuple[str, str, float],
    *, retained_safe: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    label, stem, x_mm = target
    row: dict[str, Any] = {"label": label, "target_x_mm": x_mm}
    stages: dict[str, Any] = {}
    ray_hits: dict[int, tuple[Any, Any, Any]] = {}
    answer = _observe(row, "ray_call", lambda: recipe._inset_edge_rays(
        adapter, view, leaves=leaves, stem=stem, target_mm=x_mm,
        stations_m=(recipe.NAMEPLATE_INSET_PICK_Z_M[0],), diagnostic_hits=ray_hits,
    ))
    if answer is not None:
        row["expected_instance"] = answer[0]
        if answer[1] and answer[1][0] is not None:
            row["ray_y_mm"] = answer[1][0][1] * 1000.0
    raw, component_edge, explicit_component = ray_hits.get(0, (None, None, None))
    stages.update(ray_raw=raw, component=component_edge)
    row["explicit_component_is_null"] = explicit_component is None
    part = None
    if explicit_component is not None:
        explicit_component = _early_bound(explicit_component, "IComponent2")
        _observe(row, "explicit_component_name", lambda: str(explicit_component.Name2))
        _observe(row, "explicit_component_configuration", lambda: str(explicit_component.ReferencedConfiguration))
        part = _observe(row, "explicit_component_model", explicit_component.GetModelDoc2)
        if part is not None:
            part = _early_bound(part, "IModelDoc2")
            _observe(row, "source_path", lambda: str(part.GetPathName()))
            _observe(row, "source_active_configuration", lambda: str(_early_bound(
                _early_bound(part.ConfigurationManager, "IConfigurationManager").ActiveConfiguration,
                "IConfiguration",
            ).Name))
    stages["safe"] = None if component_edge is None else _observe(
        row, "get_safe_entity", lambda: _early_bound(component_edge, "IEntity").GetSafeEntity(),
    )
    bound_view = _early_bound(view, "IView")
    for name, entity in (("view_component", component_edge), ("view_safe", stages["safe"])):
        stages[name] = None if entity is None else _observe(
            row, name, lambda entity=entity: bound_view.GetCorrespondingEntity(entity),
        )
    xy = model_point_in_view(
        adapter, view,
        (x_mm / 1000.0, recipe.NAMEPLATE_MOUNT_POS[1] / 1000.0, recipe.NAMEPLATE_INSET_PICK_Z_M[0]),
        label=f"diagnostic {label} screen-control station",
    )
    control_row: dict[str, Any] = {"sheet_xy": xy[:2]}
    stages["screen_control"] = _observe(control_row, "pick", lambda: _screen_control(
        adapter, view, xy, recipe, control_row,
    ))
    row["screen_control"] = control_row
    stages["screen_safe"] = None if stages["screen_control"] is None else _observe(
        row, "screen_get_safe_entity", lambda: _early_bound(stages["screen_control"], "IEntity").GetSafeEntity(),
    )
    if retained_safe is not None:
        stages["retained_safe"] = retained_safe
        stages["view_retained_safe"] = _observe(
            row, "view_retained_safe", lambda: bound_view.GetCorrespondingEntity(retained_safe),
        )
    assembly = _early_bound(bound_view.ReferencedDocument, "IModelDoc2")
    sources = {"part": part, "assembly": assembly}
    details, reverse_entities = {}, {}
    for name, entity in stages.items():
        snapshot = _observe(
            row, f"snapshot_{name}",
            lambda entity=entity: _entity_state(adapter, view, entity, sources),
        )
        if snapshot is None:
            details[name], reverse_entities[name] = {"snapshot_error": row[f"snapshot_{name}"]}, {}
        else:
            details[name], reverse_entities[name] = snapshot
    row["entities"] = details
    comparisons: dict[str, Any] = {}
    pairs = (
        ("component", "safe"), ("ray_raw", "component"),
        ("screen_control", "view_component"), ("screen_control", "view_safe"),
        ("screen_control", "screen_safe"), ("safe", "retained_safe"),
        ("view_safe", "view_retained_safe"),
    )
    for left, right in pairs:
        if left not in stages or right not in stages:
            continue
        _observe(comparisons, f"{left}|{right}", lambda left=left, right=right: _same(adapter, stages[left], stages[right]))
        for source in sources:
            _observe(
                comparisons, f"{source}:{left}|{right}",
                lambda left=left, right=right, source=source: _same(
                    adapter, reverse_entities[left].get(source), reverse_entities[right].get(source),
                ),
            )
    row["identities"] = comparisons
    _telemetry.event(
        "drawing.inset_diagnostic_target", label=label,
        component_before_safe_null=details["component"].get("component_is_null", True),
        component_after_safe_null=details["safe"].get("component_is_null", True),
        explicit_component_null=explicit_component is None, source_part_null=part is None,
        view_component_null=stages["view_component"] is None, view_safe_null=stages["view_safe"] is None,
        screen_control_null=stages["screen_control"] is None,
        details=json.dumps(row, default=str),
    )
    return row, stages


def _dimension_state(adapter: Any, view: Any, display: Any, expected: tuple[Any, ...], label: str, expected_mm: float) -> dict[str, Any]:
    row: dict[str, Any] = {"display_is_null": display is None}
    if display is None:
        return row
    display = _early_bound(display, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    _observe(row, "dangling", lambda: bool(annotation.IsDangling()))
    _observe(row, "attached_types", lambda: tuple(int(t) for t in (annotation.GetAttachedEntityTypes() or ())))
    attached = _observe(row, "attached_entities", lambda: tuple(annotation.GetAttachedEntities3() or ()))
    row["attached_count"] = 0 if attached is None else len(attached)
    _observe(row, "dimension_type", lambda: int(display.Type2))
    native = _observe(row, "native_dimension", lambda: display.GetDimension2(0))
    if native is not None:
        _observe(row, "measured_mm", lambda: abs(float(_early_bound(native, "IDimension").SystemValue)) * 1000.0)
    inventory = tuple(_early_bound(view, "IView").GetDisplayDimensions() or ())
    _observe(row, "section_inventory_matches", lambda: sum(_same(adapter, item, display) == 1 for item in inventory))
    if len(expected) == 2 and all(entity is not None for entity in expected):
        _observe(row, "named_attachment_value_proof", lambda: assert_dimension_measures(
            adapter, display, expected_mm=expected_mm, label=label, entities=expected,
        ))
    else:
        row["named_attachment_value_proof"] = {"error": "one or more expected references are null"}
    row["passes"] = (
        row.get("dangling") is False and row.get("attached_types") == [1, 1]
        and row.get("dimension_type") in (2, 11, 12)
        and row.get("section_inventory_matches") == 1
        and isinstance(row.get("named_attachment_value_proof"), (int, float))
        and math.isfinite(row["named_attachment_value_proof"])
        and abs(row["named_attachment_value_proof"] - expected_mm) <= 1e-5
    )
    return row


@_telemetry.traced("drawing.inset_safe_context_diagnostic")
def diagnose_inset(adapter: Any, view: Any, *, recipe: Any) -> NoReturn:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = _seat_forensics.OUT_FAILURES / "fr-inset-safe-context-diagnostic" / stamp
    report: dict[str, Any] = {
        "diagnostic_only": True, "base": "61a6fb0b53dc962955351559f8820de1f4662f01",
        "status": "running", "variants": {name: {"status": "not_attempted"} for name in _VARIANTS},
    }
    retained: dict[str, Any] = {}
    try:
        targets = (
            ("nameplate lower edge", "fr-nameplate", recipe.NAMEPLATE_MOUNT_POS[0]),
            ("deck end", "fr-harmonic-base", recipe.DECK_HALF_X),
        )
        leaves = recipe._view_component_leaves(adapter, view, label="inset diagnostic before rebuild")
        before = [_target_snapshot(adapter, view, recipe, leaves, target) for target in targets]
        report["before_entities"] = [row for row, _stages in before]
        stage_rows = [stages for _row, stages in before]
        plate, deck = recipe.model_points_in_view(
            adapter, view,
            [(target[2] / 1000.0, recipe.NAMEPLATE_MOUNT_POS[1] / 1000.0, recipe.NAMEPLATE_INSET_TEXT_Z_M) for target in targets],
            label="diagnostic dimension lanes", names=[target[0] for target in targets],
        )
        gap = math.dist(plate[:2], deck[:2])
        text = tuple(deck[i] + (deck[i] - plate[i]) / gap * recipe.NAMEPLATE_INSET_TEXT_OFFSET_M for i in range(2))
        displays = {}
        for index, name in enumerate(_VARIANTS):
            variant = report["variants"][name]
            edges = tuple(stages.get(name) for stages in stage_rows)
            if any(edge is None for edge in edges):
                variant.update(status="creation_rejected", error="one or more native edge references are null")
                displays[name] = None
                continue
            displays[name] = _observe(variant, "creation", lambda edges=edges, index=index, name=name: recipe._add_inset_dimension(
                adapter, view, edges, text_xy=(text[0], text[1] - index * 0.012), label=f"DIAGNOSTIC {name}",
            ))
            variant["status"] = "created" if displays[name] is not None else "creation_rejected"
            if displays[name] is not None:
                _observe(variant, "precision", lambda name=name: _early_bound(displays[name], "IDisplayDimension").SetPrecision3(1, -1, -1, -1))
            variant["before_rebuild"] = _observe(variant, "before_proof", lambda name=name, edges=edges: _dimension_state(
                adapter, view, displays[name], edges, f"diagnostic {name} before rebuild", recipe.NAMEPLATE_END_INSET,
            ))
        adapter.currentModel.ClearSelection2(True)
        report["rebuild_result"] = bool(adapter.currentModel.EditRebuild3())
        _early_bound(view, "IView").UpdateViewDisplayGeometry()
        adapter.currentModel.GraphicsRedraw2()
        leaves = recipe._view_component_leaves(adapter, view, label="inset diagnostic after rebuild")
        after = [_target_snapshot(
            adapter, view, recipe, leaves, target, retained_safe=stage_rows[index].get("safe"),
        ) for index, target in enumerate(targets)]
        report["after_entities"] = [row for row, _stages in after]
        for name in _VARIANTS:
            expected_key = "view_retained_safe" if name == "view_safe" else name
            edges = tuple(stages.get(expected_key) for _row, stages in after)
            variant = report["variants"][name]
            variant["after_rebuild"] = _observe(variant, "after_proof", lambda name=name, edges=edges: _dimension_state(
                adapter, view, displays.get(name), edges, f"diagnostic {name} after rebuild", recipe.NAMEPLATE_END_INSET,
            ))
            _telemetry.event("drawing.inset_diagnostic_dimension", variant=name, details=json.dumps(variant, default=str))
        control = report["variants"]["screen_control"]
        report["positive_control_verified"] = all(
            isinstance(control.get(phase), dict) and control[phase].get("passes") is True
            for phase in ("before_rebuild", "after_rebuild")
        )
        report["status"] = "diagnostic_complete"
    except Exception as exc:  # noqa: BLE001 - preserve incomplete diagnostic evidence, never publish
        report.update(status="diagnostic_error", error=f"{type(exc).__name__}: {exc}")
    finally:
        _observe(report, "clear_final_selection", lambda: adapter.currentModel.ClearSelection2(True))
        for name, options in (("slddrw", {}), ("pdf", {"sheet_pdf": True})):
            result = _observe(report, f"export_{name}", lambda options=options: _seat_forensics._save_failure_document(
                adapter, out_dir, "fr-inset-context-diagnostic", **options,
            ))
            if result:
                report[f"export_{name}_receipt"] = result
                path = result.get("document_copy" if name == "slddrw" else "sheet_pdf")
                if path:
                    retained[name] = Path(path)
        out_dir.mkdir(parents=True, exist_ok=True)
        receipt = out_dir / "diagnostic.json"
        receipt.write_text(json.dumps(report, indent=2, default=str, sort_keys=True), encoding="utf-8")
        _telemetry.event("drawing.inset_diagnostic_complete", receipt=str(receipt), details=json.dumps(report, default=str))
        _seat_forensics.capture_com_failure(
            adapter, "fr-inset-safe-context-diagnostic",
            "Intentional diagnostic stop: B-B context evidence captured; no approved drawing published",
            api="IEntity.GetSafeEntity/GetComponent + IView.GetCorrespondingEntity",
            retained_artifacts=retained, diagnostic_receipt=str(receipt), diagnostic=json.dumps(report, default=str),
        )
