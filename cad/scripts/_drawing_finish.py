"""Drawing surface-finish placement and controlled-face validation.

Surface-finish drawings validate controlled faces and place marks here without
re-keying sheets that have no finish requirements.
"""

from __future__ import annotations

import os
from typing import Any, Sequence

from solidworks_mcp.adapters import sw_type_info as _sw_type_info

from _com import _early_bound
from _drawing_attachment import (
    _LEADER_BENT,
    _LEADER_SIDE_SMART,
    _assert_attached_to,
    _assert_leader_lands,
)
from _drawing_common import rebuild_drawing
from _drawing_selection import _select_annotation_entity
from _surface_finish import SurfaceFinishControl
import _telemetry


def _surface_finish_entity_faces(
    selected_entity: Any, *, entity_type: str, label: str
) -> tuple[Any, ...]:
    """Return the model face(s) qualified by one drawing annotation entity."""
    entity_type = entity_type.upper()
    if entity_type == "FACE":
        return (selected_entity,)
    if entity_type == "SILHOUETTE":
        silhouette = _early_bound(selected_entity, "ISilhouetteEdge")
        face = silhouette.GetFace()
        return () if face is None else (face,)
    if entity_type == "EDGE":
        edge = _early_bound(selected_entity, "IEdge")
        return tuple(
            face for face in (edge.GetTwoAdjacentFaces2() or ()) if face is not None
        )
    raise ValueError(
        f"{label}: cannot validate a surface finish on entity type {entity_type!r}; "
        "expected EDGE, SILHOUETTE, or FACE"
    )


def _surface_finish_face_signatures(faces: Sequence[Any]) -> tuple[dict[str, Any], ...]:
    """Read candidate face geometry once for validation and optional diagnostics."""
    from _gtol_face_read import face_geometry

    signatures: list[dict[str, Any]] = []
    for face in faces:
        geometry = face_geometry(face)
        if geometry is None:
            continue
        signatures.append(
            {
                "geometry": geometry,
                "identity": geometry.identity,
                "parameters": tuple(round(value, 9) for value in geometry.parameters),
                "normal": geometry.outward_normal,
                "box": tuple(round(value, 9) for value in geometry.box),
            }
        )
    return tuple(signatures)


def _validate_surface_finish_control_face(
    selected_entity: Any,
    *,
    entity_type: str,
    control: SurfaceFinishControl,
    label: str,
) -> tuple[dict[str, Any], ...]:
    """Fail unless a selected drawing entity belongs to the controlled face."""
    faces = _surface_finish_entity_faces(
        selected_entity, entity_type=entity_type, label=label
    )
    signatures = _surface_finish_face_signatures(faces)
    if any(control.face.matches(item["geometry"]) for item in signatures):
        return signatures
    diagnostic = tuple(
        {key: value for key, value in item.items() if key != "geometry"}
        for item in signatures
    )
    raise RuntimeError(
        f"{label}: selected {entity_type.lower()} does not touch controlled "
        f"surface-finish face {control.face!r}; candidates={diagnostic!r}"
    )


@_telemetry.traced("drawing.surface_finish", label_param="label")
def add_surface_finish(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float] | None = None,
    edge_entity: Any | None = None,
    symbol_xy: tuple[float, float],
    roughness_ra: str | None = None,
    control: SurfaceFinishControl | None = None,
    label: str,
    entity_type: str = "EDGE",
    entity: Any | None = None,
    leader_attach_xy: tuple[float, float] | None = None,
    production_method: str = "",
    char_height: float | None = None,
) -> Any:
    """Attach a native machining-required surface-finish symbol to an edge.

    ``entity_type`` widens a coordinate pick for entities that are not model
    edges — a revolve's flank lines are ``"SILHOUETTE"`` edges.  Pass a model
    ``edge_entity`` obtained from ``IView.GetVisibleEntities2`` when a small or
    overlapping projection makes coordinate selection ambiguous.

    ``leader_attach_xy`` is where the leader lands on that entity (sheet
    metres).  It becomes the selection point of the selected entity before
    insertion (``ISelectionMgr.SetSelectionPoint2``), so SolidWorks attaches
    the leader there.  Do not move the leader afterwards: on #1105's
    sfprobe farm leaves, ``SetLeaderAttachmentPointAtIndex`` dropped every
    symbol's attached entity (count 1 before the call, 0 after) while
    ``ISFSymbol.IsAttached`` still read True.  After the rebuild the symbol
    must be attached to exactly the selected entity, and a moved leader must
    end within 5 mm of ``leader_attach_xy``.
    """
    if control is not None:
        if roughness_ra is not None or production_method:
            raise ValueError(
                f"{label}: pass a part-owned control or drawing-owned values, not both"
            )
        roughness_ra = control.roughness_ra
        production_method = control.production_method
    if roughness_ra is None:
        raise ValueError(f"{label}: surface finish requires a part-owned control")
    selected_entity = _select_annotation_entity(
        adapter,
        view,
        edge_xy=edge_xy,
        edge_entity=edge_entity,
        entity=entity,
        entity_type=entity_type,
        label=label,
    )
    signatures: tuple[dict[str, Any], ...] = ()
    if control is not None:
        signatures = _validate_surface_finish_control_face(
            selected_entity,
            entity_type=entity_type,
            control=control,
            label=label,
        )
    elif os.getenv("HARMONIC_SURFACE_AUDIT") == "1":
        faces = _surface_finish_entity_faces(
            selected_entity, entity_type=entity_type, label=label
        )
        signatures = _surface_finish_face_signatures(faces)
    if os.getenv("HARMONIC_SURFACE_AUDIT") == "1":
        diagnostic = tuple(
            {key: value for key, value in item.items() if key != "geometry"}
            for item in signatures
        )
        _telemetry.info(
            f"SURFACE_AUDIT {label}: entity_type={entity_type}, faces={diagnostic!r}"
        )
    draw = adapter.currentModel
    if leader_attach_xy is not None:
        # Coordinates are sheet metres with z 0: the probe landed every
        # leader within 0.01 mm of the requested point this way.
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        if (
            selection_manager.SetSelectionPoint2(
                1, -1, leader_attach_xy[0], leader_attach_xy[1], 0.0
            )
            is not True
        ):
            raise RuntimeError(
                f"failed to set the surface-finish landing {leader_attach_xy} ({label})"
            )
    symbol = draw.Extension.InsertSurfaceFinishSymbol3(
        1,  # installed R2026x swSFSymType_e.swSFMachining_Req
        _LEADER_BENT,  # swLeaderStyle_e.swBENT -- see _LEADER_BENT
        symbol_xy[0],
        symbol_xy[1],
        0.0,
        0,  # swSFLaySym_e.swSFNone
        10,  # swArrowStyle_e.swNO_ARROWHEAD
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    )
    if symbol is None:
        raise RuntimeError(f"failed to insert Ra {roughness_ra} symbol ({label})")
    symbol = _sw_type_info.early_bound_or_flag(
        symbol, "ISFSymbol", "SetText", "GetSymbol", "GetText", "GetAnnotation"
    )
    if not symbol.SetText(8, f"Ra {roughness_ra}"):  # current-profile roughness value
        raise RuntimeError(f"failed to set Ra {roughness_ra} ({label})")
    if production_method and not symbol.SetText(2, production_method):
        raise RuntimeError(
            f"failed to set surface target {production_method!r} ({label})"
        )
    if int(symbol.GetSymbol()) != 1:
        raise RuntimeError(f"surface-finish symbol type did not persist ({label})")
    if str(symbol.GetText(8) or "").strip() != f"Ra {roughness_ra}":
        raise RuntimeError(f"surface-finish roughness did not persist ({label})")
    if production_method and str(symbol.GetText(2) or "").strip() != production_method:
        raise RuntimeError(f"surface target did not persist ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        symbol.GetAnnotation(),
        "IAnnotation",
        "SetPosition2",
        "SetLeader3",
        "GetTextFormat",
        "SetTextFormat",
        "GetAttachedEntityCount3",
        "GetAttachedEntities3",
        "GetAttachedEntityTypes",
        "GetLeaderCount",
        "IsDangling",
        "GetLeaderPointsAtIndex",
    )
    leader_status = int(
        annotation.SetLeader3(
            _LEADER_BENT,
            _LEADER_SIDE_SMART,
            True,  # smart arrowhead
            False,  # perpendicular (GTol-only)
            False,  # all-around
            False,  # dashed
        )
    )
    if leader_status != 0:
        raise RuntimeError(
            f"failed to set a bent leader on the Ra {roughness_ra} symbol "
            f"({label}): SetLeader3 status {leader_status}"
        )
    if not annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position surface-finish symbol ({label})")
    if char_height is not None:
        # The symbol scales with its text: a smaller Ra reads as the routine
        # callout it is instead of a headline (default document height is
        # the dimension height; ~0.7 of it matches the sheet's note text).
        text_format = annotation.GetTextFormat(0)
        if text_format is None:
            raise RuntimeError(f"surface-finish symbol has no text format ({label})")
        text_format.CharHeight = float(char_height)
        if not annotation.SetTextFormat(0, False, text_format):
            raise RuntimeError(f"failed to set surface-finish text height ({label})")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="add_surface_finish")
    _assert_attached_to(
        adapter,
        annotation,
        selected_entity,
        entity_type=entity_type,
        what="surface-finish symbol",
        label=label,
    )
    if leader_attach_xy is not None:
        _assert_leader_lands(
            annotation, leader_attach_xy, what="surface-finish symbol", label=label
        )
    return symbol
