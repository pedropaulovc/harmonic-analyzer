"""Attached, leadered and property-linked drawing callouts.

Drawings with attached callouts share leadered-note placement here without
making plain note schedules depend on view-entity selection.
"""

from __future__ import annotations

import math
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import dispatch_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, view_name

from _com import _early_bound
from _drawing_attachment import (
    _LEADER_SIDE_SMART,
    _assert_attached_to,
    _assert_leader_lands,
    _is_same_attachment,
)
from _drawing_common import rebuild_drawing
from _drawing_notes import property_link
from _drawing_selection import _select_edge, _select_view_entity
import _telemetry


@_telemetry.traced("drawing.linked_callout", label_param="property_name")
def add_property_linked_callout(
    adapter: Any,
    view: Any,
    *,
    property_name: str,
    edge_xy: tuple[float, float],
    note_xy: tuple[float, float],
) -> Any:
    """Attach one arrowed callout whose text resolves from the source SLDPRT."""
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate linked-callout view {name!r}")
    draw.ClearSelection2(True)
    edge = _select_edge(adapter, *edge_xy, append=False)
    note = draw.InsertNote(property_link(property_name))
    if note is None:
        raise RuntimeError(f"failed to insert linked callout {property_name!r}")
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"linked callout has no annotation: {property_name!r}")
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
            raise RuntimeError(f"failed to attach linked callout {property_name!r}")
    status = annotation.SetLeader3(1, 0, True, False, False, False)
    if status != 0:
        raise RuntimeError(
            f"failed to create linked-callout leader {property_name!r}: {status}"
        )
    if not annotation.SetPosition2(note_xy[0], note_xy[1], 0.0):
        raise RuntimeError(f"failed to position linked callout {property_name!r}")
    rebuild_drawing(adapter, label="add_property_linked_callout")
    if (
        int(annotation.GetAttachedEntityCount3()) != 1
        or int(annotation.GetLeaderCount()) != 1
    ):
        raise RuntimeError(f"linked callout {property_name!r} lacks one arrow")
    draw.ClearSelection2(True)
    return note


@_telemetry.traced("drawing.attached_note", label_param="label")
def add_attached_note(
    adapter: Any,
    view: Any,
    *,
    text: str,
    entity_xy: tuple[float, float] | None = None,
    note_xy: tuple[float, float],
    label: str,
    entity_type: str = "EDGE",
    entity: Any | None = None,
    attached_to: Any | None = None,
    leader_attach_xy: tuple[float, float] | None = None,
) -> Any:
    """Attach one literal arrowed note to a drawing-view entity.

    Provide EITHER ``entity_xy`` (a sheet-coordinate pick) OR ``entity`` (a
    precise model entity — for an offset/inclined rim whose projected edge has
    no stable sheet coordinate); ``_select_view_entity`` prefers ``entity``.
    ``attached_to`` is the identified model entity a sheet-point pick must
    resolve to: the pick sets where the arrow lands, and the build fails if
    it attached anything else.
    ``leader_attach_xy`` sets a direct entity's selection point BEFORE note
    insertion. Moving an existing attached note's endpoint can detach it;
    this path instead preserves and verifies the selected entity throughout.
    """
    landing = None
    if leader_attach_xy is not None:
        landing = tuple(float(value) for value in leader_attach_xy)
        if (
            entity is None
            or len(landing) != 2
            or not all(math.isfinite(value) for value in landing)
        ):
            raise ValueError(
                f"attached-note landing requires a direct entity and finite XY ({label})"
            )
    target = _select_view_entity(
        adapter, view, entity_type, entity_xy, label=label, entity=entity
    )
    draw = adapter.currentModel
    expected = attached_to if attached_to is not None else entity
    if landing is not None:
        manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        count = int(manager.GetSelectedObjectCount2(-1))
        selected = manager.GetSelectedObject6(1, -1) if count == 1 else None
        if count != 1 or not _is_same_attachment(
            adapter, selected, expected, entity_type.upper()
        ):
            raise RuntimeError(
                f"attached-note selection changed before landing ({label}): count={count}"
            )
        if manager.SetSelectionPoint2(1, -1, landing[0], landing[1], 0.0) is not True:
            raise RuntimeError(f"failed to set attached-note selection point ({label})")
        actual = tuple(
            float(value) for value in manager.GetSelectionPoint2(1, -1) or ()
        )
        requested = (*landing, 0.0)
        if (
            len(actual) != 3
            or not all(math.isfinite(value) for value in actual)
            or math.dist(actual, requested) > 1e-8
        ):
            raise RuntimeError(
                f"attached-note selection point did not persist ({label}): "
                f"actual={actual!r}, requested={requested!r}"
            )
        count = int(manager.GetSelectedObjectCount2(-1))
        selected = manager.GetSelectedObject6(1, -1) if count == 1 else None
        if count != 1 or not _is_same_attachment(
            adapter, selected, expected, entity_type.upper()
        ):
            raise RuntimeError(
                f"attached-note selection changed after landing ({label}): count={count}"
            )
    note = draw.InsertNote(text)
    if note is None:
        raise RuntimeError(f"failed to insert attached note ({label})")
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"attached note has no annotation ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation,
        "IAnnotation",
        "GetAttachedEntityCount3",
        "SetAttachedEntities",
        "SetLeader3",
        "SetPosition2",
        "GetLeaderCount",
        "GetAttachedEntities3",
        "GetAttachedEntityTypes",
        "IsDangling",
    )
    if int(annotation.GetAttachedEntityCount3()) != 1:
        if landing is not None:
            raise RuntimeError(
                f"native attached note lost its initial entity ({label})"
            )
        if not annotation.SetAttachedEntities(dispatch_array([target])):
            raise RuntimeError(f"failed to attach note ({label})")
    status = annotation.SetLeader3(1, 0, True, False, False, False)
    if status != 0:
        raise RuntimeError(f"failed to create attached-note leader ({label}): {status}")
    if not annotation.SetPosition2(note_xy[0], note_xy[1], 0.0):
        raise RuntimeError(f"failed to position attached note ({label})")
    rebuild_drawing(adapter, label="add_attached_note")
    if (
        int(annotation.GetAttachedEntityCount3()) != 1
        or int(annotation.GetLeaderCount()) != 1
    ):
        raise RuntimeError(f"attached note lacks one arrow ({label})")
    attachment = expected if landing is not None else attached_to
    if attachment is not None:
        _assert_attached_to(
            adapter,
            annotation,
            attachment,
            entity_type=entity_type,
            what="attached note",
            label=label,
        )
    if landing is not None:
        points = tuple(
            float(value) for value in annotation.GetLeaderPointsAtIndex(0) or ()
        )
        if (
            len(points) < 6
            or len(points) % 3
            or not all(math.isfinite(value) for value in points)
        ):
            raise RuntimeError(f"attached-note leader is unreadable ({label})")
        _assert_leader_lands(annotation, landing, what="attached note", label=label)
    draw.ClearSelection2(True)
    return note


_LEADER_STRAIGHT = 1  # swLeaderStyle_e.swSTRAIGHT


_OWNER_DRAWING_VIEW = 0  # swAnnotationOwner_e.swAnnotationOwner_DrawingView


@_telemetry.traced("drawing.leader_note", label_param="label")
def add_leader_note(
    adapter: Any,
    text: str,
    *,
    text_xy: tuple[float, float],
    attach_xy: tuple[float, float],
    label: str,
    view: Any = None,
    height: float | None = None,
) -> Any:
    """A free note with one straight leader whose tip sits at ``attach_xy``.

    Both points are sheet metres. The leader is a POINTER, not an attachment:
    it names what it touches (a face on a pictorial, a region of a view) and
    is not associated to any entity, which is what a face label wants -- a
    hidden-lines or scale change moves nothing. The tip is read back from
    ``GetLeaderPointsAtIndex`` so a leader SolidWorks quietly re-routed fails
    the build instead of pointing at the wrong face.

    With ``view`` the note is inserted while that view is active, so
    SolidWorks makes the VIEW its owner (``IAnnotation::OwnerType`` reads
    ``swAnnotationOwner_DrawingView``, proved here): it is listed by the
    view's ``GetAnnotations`` and moves with it, and the layout audit exempts
    a leader from the one view it is owned by -- a sheet-owned label whose
    leader ends ON a view reads as crossing it (12 findings on the priming
    sheet before this).

    ``SetLeaderAttachmentPointAtIndex`` is the right call HERE, unlike for
    surface-finish symbols and feature-control frames, which it detaches: a
    pointer note has no attached entity to lose (farm run
    20260928T080412049Z-77daa98fe5514439bd4ce684c6e19ec7 read
    GetAttachedEntityCount3 0 -> 0, one non-dangling leader, on all four
    cone-swing and crank-pinion notes).
    """
    draw = adapter.currentModel
    if view is not None:
        ddoc = _early_bound(draw, "IDrawingDoc")
        name = view_name(adapter, view)
        if not ddoc.ActivateView(name):
            raise RuntimeError(
                f"{label}: failed to activate view {name!r} for the note"
            )
    note = add_note(adapter, text, *text_xy, height=height)
    if note is None:
        raise RuntimeError(f"{label}: failed to insert the note {text!r}")
    annotation = _sw_type_info.early_bound_or_flag(
        note.GetAnnotation(),
        "IAnnotation",
        "SetLeader3",
        "SetLeaderAttachmentPointAtIndex",
        "GetLeaderPointsAtIndex",
        "SetPosition2",
        "OwnerType",
    )
    if view is not None and int(annotation.OwnerType) != _OWNER_DRAWING_VIEW:
        raise RuntimeError(
            f"{label}: note is not owned by its view (OwnerType {int(annotation.OwnerType)})"
        )
    status = int(
        annotation.SetLeader3(
            _LEADER_STRAIGHT, _LEADER_SIDE_SMART, True, False, False, False
        )
    )
    if status != 0:
        raise RuntimeError(
            f"{label}: SetLeader3 refused a straight leader (status {status})"
        )
    if not annotation.SetLeaderAttachmentPointAtIndex(
        0, attach_xy[0], attach_xy[1], 0.0
    ):
        raise RuntimeError(f"{label}: failed to place the leader tip at {attach_xy}")
    if not annotation.SetPosition2(text_xy[0], text_xy[1], 0.0):
        raise RuntimeError(f"{label}: failed to position the note at {text_xy}")
    rebuild_drawing(adapter, label="add_leader_note")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6:
        raise RuntimeError(
            f"{label}: the note's leader is unreadable ({len(points)} values)"
        )
    tip = (float(points[-3]), float(points[-2]))
    if math.dist(tip, attach_xy) > 0.001:
        raise RuntimeError(
            f"{label}: leader tip landed at {tip}, requested {attach_xy}"
        )
    draw.ClearSelection2(True)
    return note
