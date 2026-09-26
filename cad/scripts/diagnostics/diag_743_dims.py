"""#743 canary diagnosis (throwaway, never merged): why two drawings lost a dim.

r743-canary (de9db7ec3) failed two drawing leaves in dimension curation:

* drawing:cylinder_gear_shaft -- the profile view's targeted import of
  ``DomeReference`` (a blanked construction sketch) brought no ``DomeHeight``.
* drawing:rocker_arm_support -- the front view's entire-model import brought
  every dimension it used to except ``RimChamferSize``.

The patched draw scripts on this branch call in here right before the curation
that failed. Everything is a seat READ or an import into the unsaved drawing:
nothing is saved, and :func:`finish` raises so the leaf never stores an
artefact. Each variant changes ONE thing against the as-built repro, and every
result is one ``DIAG743`` log line (rg the leaf's task.log for it).
"""

from __future__ import annotations

from typing import Any, Sequence

import _telemetry
from _common import _early_bound, _read_member
from _drawing_common import _model_item_paths, _select_model_feature
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, view_name
from solidworks_mcp.adapters import sw_type_info as _sw_type_info

SW_HIDDEN = 2  # swDisplayMode_e: hidden lines removed
SW_HIDDEN_GREYED = 1  # hidden lines visible
FROM_SELECTED_FEATURE = 1  # swImportModelItemsFromSelectedFeature
FROM_ENTIRE_MODEL = 0
DIMS_MARKED = 0x8000  # swInsertDimensionsMarkedForDrawing
DIMS_ALL = 0x8 | 0x8000 | 0x80000  # plain + marked + not-marked
VIEW_EDGE = 1  # swViewEntityType_Edge
VIEW_FACE = 3
VIEW_SILHOUETTE = 4
SEL_EDGES, SEL_FACES, SEL_VERTICES = 1, 2, 3

_results: list[str] = []


def _log(message: str) -> None:
    line = f"DIAG743 {message}"
    _results.append(line)
    _telemetry.info(line)


def _round(values: Sequence[float]) -> tuple[float, ...]:
    return tuple(round(float(v) * 1000.0, 3) for v in values)


def _edge_key(edge: Any) -> tuple:
    """Endpoints (mm) of an edge, order-free, so model and view edges compare."""
    edge = _early_bound(edge, "IEdge")
    start, end = edge.GetStartVertex(), edge.GetEndVertex()
    if start is None or end is None:
        params = edge.GetCurveParams3()
        return ("closed", _round(params.StartPoint[:3]))
    a = _round(_early_bound(start, "IVertex").GetPoint())
    b = _round(_early_bound(end, "IVertex").GetPoint())
    return tuple(sorted((a, b)))


def _visible_edge_keys(view: Any) -> set:
    v = _early_bound(view, "IView")
    keys: set = set()
    for kind in (VIEW_EDGE, VIEW_SILHOUETTE):
        for edge in v.GetVisibleEntities2(None, kind) or ():
            try:
                keys.add(_edge_key(edge))
            except Exception as exc:  # noqa: BLE001 -- a diag records, never dies
                _log(f"visible-edge key failed kind={kind}: {exc!r}")
    return keys


def log_view_mode(view: Any, *, tag: str) -> None:
    v = _early_bound(view, "IView")
    try:
        _log(f"{tag} view {v.GetName2()} display mode {v.GetDisplayMode2()}")
    except Exception as exc:  # noqa: BLE001 -- a diag records, never dies
        _log(f"{tag} display mode read failed: {exc!r}")


def log_feature_dims(adapter: Any, view: Any, feature: str, *, tag: str) -> None:
    try:
        _log_feature_dims(adapter, view, feature, tag=tag)
    except Exception as exc:  # noqa: BLE001
        _log(f"{tag} feature-dims read failed: {exc!r}")


def _log_feature_dims(adapter: Any, view: Any, feature: str, *, tag: str) -> None:
    """The feature's display dims as the PART holds them: name, marked,
    visible, driven state, and each attached entity (edges checked against
    the view's visible edges)."""
    part = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")
    feat = _early_bound(part, "IPartDoc").FeatureByName(feature)
    if feat is None:
        _log(f"{tag} feature {feature!r} not found")
        return
    feat = _early_bound(feat, "IFeature")
    _log(
        f"{tag} feature {feature} type={feat.GetTypeName2()} "
        f"visible={_read_member(feat, 'Visible')} suppressed={feat.IsSuppressed()}"
    )
    visible = _visible_edge_keys(view)
    _log(f"{tag} view {view_name(adapter, view)} visible edges={len(visible)}")
    disp = feat.GetFirstDisplayDimension()
    count = 0
    while disp is not None:
        count += 1
        dd = _early_bound(disp, "IDisplayDimension")
        dim = _early_bound(dd.GetDimension2(0), "IDimension")
        ann = _early_bound(dd.GetAnnotation(), "IAnnotation")
        types = list(ann.GetAttachedEntityTypes() or ())
        entities = list(ann.GetAttachedEntities3() or ())
        described = []
        for kind, entity in zip(types, entities, strict=False):
            if kind == SEL_EDGES:
                try:
                    key = _edge_key(entity)
                    described.append(f"edge{key} in_view={key in visible}")
                except Exception as exc:  # noqa: BLE001
                    described.append(f"edge(? {exc!r})")
            else:
                described.append(f"type{kind}")
        _log(
            f"{tag} dim {dim.FullName} value_m={_read_member(dim, 'SystemValue')} "
            f"marked={dd.MarkedForDrawing} ann_visible={_read_member(ann, 'Visible')} "
            f"driven={dim.DrivenState} readonly={dim.ReadOnly} "
            f"attached={described or 'none'}"
        )
        disp = feat.GetNextDisplayDimension(disp)
    if count == 0:
        _log(f"{tag} feature {feature} has NO display dimensions")


def import_variant(
    adapter: Any,
    view: Any,
    features: Sequence[str],
    *,
    tag: str,
    option: int = FROM_SELECTED_FEATURE,
    types: int = DIMS_MARKED,
) -> list[str]:
    """One InsertModelAnnotations3 call, the production selection recipe with
    ``option``/``types`` as the variables; logs the dimension names it brought."""
    try:
        return _import_variant(adapter, view, features, tag=tag, option=option, types=types)
    except Exception as exc:  # noqa: BLE001
        _log(f"{tag} import failed: {exc!r}")
        return []


def _import_variant(
    adapter: Any, view: Any, features: Sequence[str], *, tag: str, option: int, types: int
) -> list[str]:
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    ddoc.ActivateView(name)
    draw.ClearSelection2(True)
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    draw.Extension.SelectByID2(name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0)
    if option == FROM_SELECTED_FEATURE:
        paths = _model_item_paths(adapter, view)
        for feature in features:
            _select_model_feature(adapter, feature, paths=paths)
    result = ddoc.InsertModelAnnotations3(option, types, False, True, True, False)
    draw.ClearSelection2(True)
    names = []
    for annotation in result or ():
        specific = _sw_type_info.early_bound_or_flag(annotation, "IAnnotation", "GetSpecificAnnotation")
        names.append(dimension_name(adapter, specific) or "<non-dim>")
    _log(
        f"{tag} import view={name} option={option} types={hex(types)} "
        f"features={list(features)} -> {sorted(names)}"
    )
    return names


def set_display_mode(view: Any, mode: int, *, tag: str) -> None:
    v = _early_bound(view, "IView")
    ok = v.SetDisplayMode4(False, mode, False, True, False)
    _log(f"{tag} SetDisplayMode4(mode={mode}) -> {ok}; now {v.GetDisplayMode2()}")


def finish() -> None:
    _log(f"SUMMARY {len(_results)} lines")
    raise RuntimeError("DIAG743 probe complete (deliberate stop; nothing saved)")


# --- rim-chamfer bisect inside de9db7ec3 (Main GO 2026-09-26) ---------------
SW_SUPPRESS, SW_UNSUPPRESS = 0, 1  # swFeatureSuppressionAction_e
SW_ALL_CONFIGURATIONS = 2  # swInConfigurationOpts_e


def _part(view: Any) -> Any:
    return _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")


def log_dim_annotation(view: Any, feature: str, *, tag: str) -> None:
    """Where the part keeps each of the feature's display dims (its annotation
    position and owning view plane), since GetAttachedEntities3 reads none."""
    try:
        feat = _early_bound(_early_bound(_part(view), "IPartDoc").FeatureByName(feature), "IFeature")
        disp = feat.GetFirstDisplayDimension()
        while disp is not None:
            dd = _early_bound(disp, "IDisplayDimension")
            dim = _early_bound(dd.GetDimension2(0), "IDimension")
            ann = _early_bound(dd.GetAnnotation(), "IAnnotation")
            position = ann.GetPosition()
            _log(
                f"{tag} annotation {dim.FullName} position_mm="
                f"{_round(position[:3]) if position else None} "
                f"type={dd.Type2} attached_count={len(ann.GetAttachedEntityTypes() or ())}"
            )
            disp = feat.GetNextDisplayDimension(disp)
    except Exception as exc:  # noqa: BLE001
        _log(f"{tag} annotation read failed: {exc!r}")


def log_feature_state(view: Any, features: Sequence[str], *, tag: str) -> None:
    part = _early_bound(_part(view), "IPartDoc")
    for name in features:
        try:
            feat = _early_bound(part.FeatureByName(name), "IFeature")
            code, warning = feat.GetErrorCode2()
            _log(f"{tag} feature {name} suppressed={feat.IsSuppressed()} error={code} warning={warning}")
        except Exception as exc:  # noqa: BLE001
            _log(f"{tag} feature {name} state read failed: {exc!r}")


def per_view_imports(adapter: Any, views: dict[str, Any], *, tag: str) -> None:
    """Targeted RimChamfer, then entire-model, into each view in turn
    (DuplicateDims is on, so one view's import does not starve the next)."""
    for label, view in views.items():
        import_variant(adapter, view, ["RimChamfer"], tag=f"{tag}-{label}-targeted")
    for label, view in views.items():
        import_variant(adapter, view, [], tag=f"{tag}-{label}-entire", option=FROM_ENTIRE_MODEL)


def log_edge_visibility(adapter: Any, views: dict[str, Any], *, tag: str) -> None:
    """Whether each view shows the rim chamfer's edges: the chamfer faces'
    edges that lie in the web faces (|z| = 3.175 +/- 1.27) against each view's
    visible edges."""
    try:
        body = _early_bound(_early_bound(_part(views["front"]), "IPartDoc").GetBodies2(0, True)[0], "IBody2")
        feat = _early_bound(_early_bound(_part(views["front"]), "IPartDoc").FeatureByName("RimChamfer"), "IFeature")
        faces = list(feat.GetFaces() or ())
        chamfer_edges = set()
        for face in faces:
            for edge in _early_bound(face, "IFace2").GetEdges() or ():
                chamfer_edges.add(_edge_key(edge))
        _log(f"{tag} RimChamfer faces={len(faces)} edges={len(chamfer_edges)} body={body is not None}")
        for label, view in views.items():
            seen = _visible_edge_keys(view)
            _log(f"{tag} view {label} shows {len(chamfer_edges & seen)}/{len(chamfer_edges)} chamfer-face edges")
    except Exception as exc:  # noqa: BLE001
        _log(f"{tag} edge visibility failed: {exc!r}")


def _rebuild(adapter: Any, view: Any, *, tag: str) -> None:
    part = _part(view)
    ok_part = part.ForceRebuild3(False)
    ok_draw = adapter.currentModel.ForceRebuild3(False)
    _log(f"{tag} rebuild part={ok_part} drawing={ok_draw}")


def set_suppressed(adapter: Any, view: Any, feature: str, suppressed: bool, *, tag: str) -> None:
    try:
        feat = _early_bound(_early_bound(_part(view), "IPartDoc").FeatureByName(feature), "IFeature")
        action = SW_SUPPRESS if suppressed else SW_UNSUPPRESS
        ok = feat.SetSuppression2(action, SW_ALL_CONFIGURATIONS, None)
        _log(f"{tag} SetSuppression2({feature}, {action}) -> {ok}")
        _rebuild(adapter, view, tag=tag)
        _log(f"{tag} {feature} now suppressed={feat.IsSuppressed()}")
    except Exception as exc:  # noqa: BLE001
        _log(f"{tag} suppress {feature} failed: {exc!r}")


def set_global(adapter: Any, view: Any, name: str, value: str, *, tag: str) -> None:
    """Rewrite one equation-manager global on the open part (unsaved)."""
    try:
        part = _part(view)
        manager = _sw_type_info.early_bound_or_flag(part.GetEquationMgr(), "IEquationMgr", "SetEquation", "Equation", "Value", "GetCount")
        count = int(_read_member(manager, "GetCount") or 0)
        lhs = f'"{name}"'
        for index in range(count):
            text = str(manager.Equation(index) or "")
            if text.partition("=")[0].strip() == lhs:
                manager.SetEquation(index, f"{lhs} = {value}")
                _log(f"{tag} equation {text!r} -> {manager.Equation(index)!r} value={manager.Value(index)}")
                break
        else:
            _log(f"{tag} global {name} not found in {count} equations")
            return
        _rebuild(adapter, view, tag=tag)
    except Exception as exc:  # noqa: BLE001
        _log(f"{tag} set global {name} failed: {exc!r}")


def log_global(view: Any, name: str, *, tag: str) -> None:
    """The value SolidWorks holds for one global, as read back (globals round
    to the document's decimal places)."""
    try:
        part = _part(view)
        manager = _sw_type_info.early_bound_or_flag(
            part.GetEquationMgr(), "IEquationMgr", "Equation", "Value", "GetCount"
        )
        lhs = f'"{name}"'
        for index in range(int(_read_member(manager, "GetCount") or 0)):
            text = str(manager.Equation(index) or "")
            if text.partition("=")[0].strip() == lhs:
                _log(f"{tag} global {text!r} holds {manager.Value(index)}")
                return
        _log(f"{tag} global {name} not found")
    except Exception as exc:  # noqa: BLE001
        _log(f"{tag} global {name} read failed: {exc!r}")
