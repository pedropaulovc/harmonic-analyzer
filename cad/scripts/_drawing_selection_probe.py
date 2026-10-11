"""Native selected-entity descriptions and diagnostic probes.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from typing import Callable
from _com import _early_bound
import json
from solidworks_mcp.adapters.solidworks.drawing import view_name


# swSelectType_e names for the kinds a drawing-view pick can resolve to; an
# unlisted code is reported as its number, never mapped to a guess.
_SELECT_TYPE_NAMES = {
    0: "NOTHING",
    1: "EDGE",
    2: "FACE",
    3: "VERTEX",
    9: "SKETCH",
    10: "SKETCHSEGMENT",
    11: "SKETCHPOINT",
    12: "DRAWINGVIEW",
    13: "GTOL",
    14: "DIMENSION",
    15: "NOTE",
    20: "COMPONENT",
    24: "EXTSKETCHSEGMENT",
    25: "EXTSKETCHPOINT",
    28: "CENTERMARKS",
    35: "SFSYMBOL",
    46: "SILHOUETTE",
    103: "CENTERLINE",
}


def _probe(
    bag: dict[str, Any], key: str, read: Callable[[], Any], *, record: bool = True
) -> Any:
    """Record ONE forensic read in ``bag`` -- its value, or its own failure.

    A description that cannot be read must say so under ``<key>_error`` and
    let the next read run: this executes on the success path of every hole
    callout (the BEFORE snapshot) and on the failure path after a refusal,
    and a diagnostic that raises there either fails a good sheet or masks the
    real failure.
    ``record=False`` keeps only the failure (for wrapper bindings, whose value
    is a COM object no telemetry channel can carry).
    """
    try:
        value = read()
    except Exception as exc:  # noqa: BLE001 - forensics never raise (see above)
        bag[f"{key}_error"] = f"{type(exc).__name__}: {exc}"
        return None
    if record:
        bag[key] = value
    return value


def _feature_identity(face: Any) -> str:
    """``<feature name>(<feature type>)`` of the feature that owns ``face``."""
    feature = _early_bound(face, "IFace2").GetFeature()
    if feature is None:
        return "<no feature>"
    feature = _early_bound(feature, "IFeature")
    return f"{feature.Name}({feature.GetTypeName2()})"


def describe_selected_entity(
    adapter: Any,
    view: Any,
    entity: Any,
    *,
    entity_type: str,
    requested_xy: tuple[float, float] | None,
    label: str,
) -> dict[str, Any]:
    """What a drawing-view pick actually resolved to, as scalar telemetry fields.

    The failure this exists for: ``AddHoleCallout2`` answered ``None`` to a
    coordinate pick that had succeeded (drawing:ch_rocker_arm, worker5,
    2026-09-20) and the leaf log could not say whether the selected EDGE was
    the hole rim, the strap arc 2.3 sheet-mm below it, or the hidden back-face
    rim under it. Recorded: the view (name, scale, position, outline), the
    requested sheet point, the selection set (count and every entry's
    ``swSelectType_e``), and for an edge its curve (circle centre/radius or
    line endpoints, model mm), its vertices and the feature owning each
    adjacent face -- which names the hole feature, or does not.

    Called only at the hole-callout boundary (:func:`add_native_hole_callout`),
    not on every pick: it is ~10 COM reads per call, and a generic pick has
    nothing to compare them against. Every read is guarded (:func:`_probe`);
    a value that could not be read is reported as ``<key>_error`` rather than
    raising. Values are scalars or JSON strings so they ride a span event, a
    log record and ``capture.json`` unchanged.
    """
    bag: dict[str, Any] = {
        "label": label,
        "entity_type": entity_type,
        "pick": "coordinate" if requested_xy is not None else "entity",
    }
    if requested_xy is not None:
        bag["requested_x"] = float(requested_xy[0])
        bag["requested_y"] = float(requested_xy[1])
    _probe(bag, "view_name", lambda: view_name(adapter, view))
    bound_view = _probe(bag, "view", lambda: _early_bound(view, "IView"), record=False)
    if bound_view is not None:
        _probe(bag, "view_scale", lambda: float(bound_view.ScaleDecimal))
        _probe(
            bag,
            "view_position",
            lambda: json.dumps([float(v) for v in bound_view.Position]),
        )
        _probe(
            bag,
            "view_outline",
            lambda: json.dumps([float(v) for v in bound_view.GetOutline()]),
        )
    selection_manager = _probe(
        bag,
        "selection_manager",
        lambda: _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr"),
        record=False,
    )
    count = None
    if selection_manager is not None:
        count = _probe(
            bag,
            "selected_count",
            lambda: int(selection_manager.GetSelectedObjectCount2(-1)),
        )
    if count:
        _probe(
            bag,
            "selected_types",
            lambda: json.dumps(
                [
                    _SELECT_TYPE_NAMES.get(code, code)
                    for code in (
                        int(selection_manager.GetSelectedObjectType3(index, -1))
                        for index in range(1, count + 1)
                    )
                ]
            ),
        )
    kind = entity_type.upper()
    if kind == "SILHOUETTE":
        _probe(
            bag,
            "face_feature",
            lambda: _feature_identity(
                _early_bound(entity, "ISilhouetteEdge").GetFace()
            ),
        )
        return bag
    if kind != "EDGE":
        return bag
    edge = _probe(bag, "edge", lambda: _early_bound(entity, "IEdge"), record=False)
    if edge is None:
        return bag
    curve = _probe(
        bag, "curve", lambda: _early_bound(edge.GetCurve(), "ICurve"), record=False
    )
    if curve is not None:
        if _probe(bag, "is_circle", lambda: bool(curve.IsCircle())):
            # CircleParams = (centre xyz, axis xyz, radius), metres -- ONE
            # property read, then sliced.
            def circle_mm() -> str:
                params = [float(v) for v in curve.CircleParams]
                return json.dumps(
                    [round(v * 1000.0, 4) for v in params[:3]]
                    + [round(params[6] * 1000.0, 4)]
                )

            _probe(bag, "circle_mm", circle_mm)
        elif _probe(bag, "is_line", lambda: bool(curve.IsLine())):
            _probe(
                bag,
                "line_mm",
                lambda: json.dumps(
                    [
                        [
                            round(float(v) * 1000.0, 4)
                            for v in _early_bound(vertex, "IVertex").GetPoint()
                        ]
                        for vertex in (edge.GetStartVertex(), edge.GetEndVertex())
                    ]
                ),
            )
    _probe(
        bag,
        "adjacent_features",
        lambda: json.dumps(
            [
                _feature_identity(face)
                for face in (edge.GetTwoAdjacentFaces2() or ())
                if face is not None
            ]
        ),
    )
    return bag
