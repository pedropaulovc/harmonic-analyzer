"""Native datum-target symbols on drawing views.

Separate module so edits affect only recipes that use this scope.

A casting is set up on points of its as-cast surface before any face is cut:
each datum target is the native ``IDatumTargetSym`` annotation, its leader
landing on the model entity the target stands on, read back after the rebuild.
"""

from __future__ import annotations

import math
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_selection import _select_annotation_entity
import _telemetry

# IModelDocExtension::InsertDatumTargetSymbol3's AreaStyle: 0 = point (the X).
_INSERT_POINT = 0
# swDatumTargetAreaShape_e.swDatumTargetAreaPoint, what GetTargetShape reads
# for it.
_SHAPE_POINT = 1
# InsertDatumTargetSymbol3's LeaderLineStyle: 0 = solid, the target on the
# side the view shows; 1 draws the leader dashed, which Y14.5 reads as a
# target on the far side (farm run 20261111T023438415Z printed all six
# dashed).  The symbol's leader runs straight (LeaderBent False).
_LEADER_SOLID = 0
# swSelectType_e.swSelSKETCHPOINTS: the target's own point.  Farm run
# 20261111T002327093Z read (11,) for a target on a planar face picked by
# entity, its leader ending on the requested point to the float.
_ATTACHED_TARGET_POINT = 11
# How far the leader's end may read from the requested target point.
_TARGET_LANDING_TOLERANCE_M = 0.001


def datum_target_readback(symbol: Any) -> dict[str, Any]:
    """What one native datum-target symbol states, read off the annotation."""
    symbol = _sw_type_info.early_bound_or_flag(
        symbol,
        "IDatumTargetSym",
        "GetDatumReferenceLabel",
        "GetTargetShape",
        "GetDisplaySymbol",
        "GetDisplayTargetArea",
        "GetAnnotation",
        "GetTextCount",
        "GetTextAtIndex",
    )
    annotation = _sw_type_info.early_bound_or_flag(
        symbol.GetAnnotation(),
        "IAnnotation",
        "GetPosition",
        "GetLeaderCount",
        "GetLeaderPointsAtIndex",
        "GetAttachedEntityCount3",
        "GetAttachedEntityTypes",
        "IsDangling",
        "GetDashedLeader",
    )
    leaders = int(annotation.GetLeaderCount())
    return {
        "label": str(symbol.GetDatumReferenceLabel(0) or ""),
        "shape": int(symbol.GetTargetShape()),
        "symbol_shown": bool(symbol.GetDisplaySymbol()),
        "area_shown": bool(symbol.GetDisplayTargetArea()),
        "texts": [
            str(symbol.GetTextAtIndex(i) or "")
            for i in range(int(symbol.GetTextCount() or 0))
        ],
        "position": tuple(float(v) for v in (annotation.GetPosition() or ())[:2]),
        "leaders": leaders,
        "leader_points": [
            tuple(float(v) for v in (annotation.GetLeaderPointsAtIndex(i) or ()))
            for i in range(leaders)
        ],
        "attached": int(annotation.GetAttachedEntityCount3()),
        "attached_types": tuple(
            int(t) for t in (annotation.GetAttachedEntityTypes() or ())
        ),
        "dangling": bool(annotation.IsDangling()),
        "dashed": bool(annotation.GetDashedLeader()),
    }


@_telemetry.traced("drawing.datum_target", label_param="label")
def add_datum_target(
    adapter: Any,
    view: Any,
    *,
    target: str,
    target_xy: tuple[float, float],
    symbol_xy: tuple[float, float],
    entity: Any,
    entity_type: str,
    label: str,
) -> Any:
    """Put the native datum-target point ``target`` (``"E1"``) on ``entity``.

    ``target_xy`` is the target point on that entity and ``symbol_xy`` the
    symbol's centre, both sheet metres.  The target point becomes the
    entity's selection point before insertion, the way a surface-finish
    leader lands (``_drawing_finish.add_surface_finish``); nothing moves the
    leader afterwards.  SolidWorks stands the target on its own point on the
    picked entity and attaches the symbol to that point, so after the rebuild
    the symbol must read its label as a displayed point target, hold exactly
    that one point by one live leader and end the leader on ``target_xy``.
    """
    draw = adapter.currentModel
    _select_annotation_entity(
        adapter,
        view,
        edge_xy=None,
        edge_entity=None,
        entity=entity,
        entity_type=entity_type,
        label=label,
    )
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    if manager.SetSelectionPoint2(1, -1, target_xy[0], target_xy[1], 0.0) is not True:
        raise RuntimeError(f"failed to set datum target {target}'s point ({label})")
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    symbol = extension.InsertDatumTargetSymbol3(
        target,  # Datum1: the lower half's reference
        "",
        "",
        _INSERT_POINT,
        False,  # AreaOutside
        0.0,
        0.0,  # Value1, Value2: a point has no area size
        "",
        "",
        True,  # ArrowsSmart
        0,  # ArrowStyle (smart arrows choose it)
        _LEADER_SOLID,
        False,  # LeaderBent
        True,  # ShowArea: the point's X
        True,  # ShowSymbol
        0,  # MoveableDatumStyle; SetDatumTargetNotMoveable below states it
    )
    if symbol is None:
        raise RuntimeError(f"failed to insert datum target {target} ({label})")
    symbol = _sw_type_info.early_bound_or_flag(
        symbol,
        "IDatumTargetSym",
        "GetAnnotation",
        "SetDatumTargetNotMoveable",
        "GetDatumReferenceLabel",
    )
    if symbol.SetDatumTargetNotMoveable() is not True:
        raise RuntimeError(f"datum target {target} did not take a fixed target ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        symbol.GetAnnotation(), "IAnnotation", "SetPosition2"
    )
    if not annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position datum target {target} ({label})")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="add_datum_target")
    read = datum_target_readback(symbol)
    _telemetry.info(f"datum target {target} ({label}): {read!r}")
    if (
        read["label"] != target
        or read["shape"] != _SHAPE_POINT
        or not read["symbol_shown"]
        or not read["area_shown"]
    ):
        raise RuntimeError(f"datum target {target} did not persist ({label}): {read!r}")
    if len(read["position"]) != 2 or math.dist(read["position"], symbol_xy) > 0.003:
        raise RuntimeError(
            f"datum target {target} stands at {read['position']}, not {symbol_xy} ({label})"
        )
    if (
        read["attached"] != 1
        or read["attached_types"] != (_ATTACHED_TARGET_POINT,)
        or read["dangling"]
        or read["leaders"] != 1
    ):
        raise RuntimeError(f"datum target {target} lost its point ({label}): {read!r}")
    if read["dashed"]:
        raise RuntimeError(
            f"datum target {target}'s leader is dashed, a far-side target ({label}):"
            f" {read!r}"
        )
    points = read["leader_points"][0]
    if len(points) < 6 or math.dist(points[-3:-1], target_xy) > _TARGET_LANDING_TOLERANCE_M:
        raise RuntimeError(
            f"datum target {target}'s leader does not end on {target_xy} ({label}):"
            f" {points!r}"
        )
    return symbol
