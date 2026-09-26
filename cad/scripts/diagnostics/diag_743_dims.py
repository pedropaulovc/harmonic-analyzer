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
