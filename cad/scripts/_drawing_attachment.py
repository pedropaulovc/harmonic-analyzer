"""Drawing attachment identity, leader styles and landing assertions.

Datum, finish and callout authors share attachment proofs and leader styles
here, independently of drawing-session and export policy.
"""

from __future__ import annotations

import math
from typing import Any

from _com import _early_bound


_SEL_EDGE = 1  # swSelectType_e.swSelEDGES


_SEL_SILHOUETTE = 46  # swSelectType_e.swSelSILHOUETTES


_SEL_FACE = 2  # swSelectType_e.swSelFACES


# swLeaderStyle_e.swBENT / swLeaderSide_e.swLS_SMART. Every leadered annotation
# is bent: a straight leader runs at whatever angle its anchor-to-text vector
# happens to take, which is what drove the old Ra symbol's leader diagonally
# across two views. A bent leader lands its elbow horizontally at the text.
_LEADER_BENT = 2


_LEADER_SIDE_SMART = 0


# How far a leader may land from its requested attachment point.  Measured on
# the #1105 idprobe farm leaves (20260928T084216466Z, 14 surface finishes and
# feature-control frames landed by selection point): every leader but one read
# back within 4e-8 m of its request; the pinion-bracket pivot-bore finish,
# whose request sits on the bore circle at 45 deg, re-solved 0.61 mm along the
# edge.  1 mm admits that re-solve and rejects a landing on the neighbouring
# edge, which the earlier 5 mm bound could not.
_LEADER_LANDING_TOLERANCE_M = 0.001


def _assert_leader_lands(
    annotation: Any,
    leader_attach_xy: tuple[float, float],
    *,
    what: str,
    label: str,
    tolerance: float = _LEADER_LANDING_TOLERANCE_M,
) -> None:
    """Fail unless ``annotation`` keeps one live leader ending within
    ``tolerance`` of ``leader_attach_xy``.  A returned True from a leader or
    selection-point setter proves nothing, so the landing is read back."""
    leaders = int(annotation.GetLeaderCount())
    dangling = bool(annotation.IsDangling())
    if dangling or leaders != 1:
        raise RuntimeError(
            f"{what} leader did not survive ({label}): dangling={dangling}, "
            f"leaders={leaders}"
        )
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6:
        raise RuntimeError(f"{what} leader is unreadable ({label})")
    actual = (float(points[-3]), float(points[-2]))
    error = math.dist(actual, leader_attach_xy)
    if error > tolerance:
        raise RuntimeError(
            f"{what} leader attachment moved ({label}): actual={actual}, "
            f"requested={leader_attach_xy}, error={error:.6g} m, "
            f"limit={tolerance:g} m"
        )


_ATTACHMENT_SELECT_TYPES = {
    "EDGE": _SEL_EDGE,
    "FACE": _SEL_FACE,
    "SILHOUETTE": _SEL_SILHOUETTE,
}


def _is_same_attachment(adapter: Any, attached: Any, entity: Any, kind: str) -> bool:
    """Whether ``attached`` is the ``kind`` entity an annotation was inserted on.

    ``ISldWorks::IsSame`` reads 1 for the model edge or face itself, and 0 for
    every silhouette, moved or not (probe 3 and run 20260928T081119688Z).  A
    silhouette is identified by its owning face instead: on the #1105 idprobe2
    leaves (20260928T085009031Z) ``ISilhouetteEdge::GetFace`` of the selected
    and of the attached silhouette passed IsSame on all 16 silhouette finishes
    and frames, and the drawing's ``IsSamePersistentID`` agreed.  A cylinder's
    two flank silhouettes share that face; the leader-landing check tells them
    apart.
    """
    if kind != "SILHOUETTE":
        return int(adapter.swApp.IsSame(attached, entity)) == 1
    selected_face = _early_bound(entity, "ISilhouetteEdge").GetFace()
    attached_face = _early_bound(attached, "ISilhouetteEdge").GetFace()
    if selected_face is None or attached_face is None:
        return False
    return int(adapter.swApp.IsSame(attached_face, selected_face)) == 1


def _assert_attached_to(
    adapter: Any,
    annotation: Any,
    entity: Any,
    *,
    entity_type: str,
    what: str,
    label: str,
    expected_leaders: int = 1,
) -> None:
    """Fail unless ``annotation`` is still attached, by ``expected_leaders``
    live leaders, to exactly ``entity``, an ``entity_type`` (EDGE, FACE or
    SILHOUETTE) entity.

    The count, type and entity readbacks must agree on one entity of that
    type -- ``IGtol.IsAttached`` and ``ISFSymbol.IsAttached`` keep reading
    True on a detached symbol -- and that entity must be ``entity`` by
    :func:`_is_same_attachment`.  A leader move re-solves the attachment:
    ``SetLeaderAttachmentPointAtIndex`` detached a feature-control frame
    (entities=0) on the #1105 platen_guide leaf.  A datum tag's triangle is
    not a leader (``GetLeaderCount`` reads 0 on every datum tag), so it
    passes ``expected_leaders=0``.
    """
    kind = entity_type.upper()
    if kind not in _ATTACHMENT_SELECT_TYPES:
        raise ValueError(f"{what} cannot verify a {kind} attachment ({label})")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    count = int(annotation.GetAttachedEntityCount3())
    types = tuple(int(t) for t in (annotation.GetAttachedEntityTypes() or ()))
    leaders = int(annotation.GetLeaderCount())
    dangling = bool(annotation.IsDangling())
    one = (
        len(attached) == 1
        and count == 1
        and types == (_ATTACHMENT_SELECT_TYPES[kind],)
        and attached[0] is not None
    )
    same = one and _is_same_attachment(adapter, attached[0], entity, kind)
    if not same or dangling or leaders != expected_leaders:
        raise RuntimeError(
            f"{what} lost its {kind.lower()} attachment ({label}): "
            f"entities={len(attached)}, count={count}, types={types}, "
            f"same_entity={same}, dangling={dangling}, leaders={leaders}"
        )


def _expected_pick(
    adapter: Any,
    selected: Any,
    expected: Any | None,
    *,
    entity_type: str,
    what: str,
    label: str,
) -> Any:
    """The entity an annotation must end up on: ``expected`` when the recipe
    named one, else what the pick returned.

    A named entity that was selected directly is ``selected`` itself. One
    named alongside a coordinate hit-test must BE what the hit-test resolved
    to (``_is_same_attachment``): a pick point where two lines meet returns
    whichever SolidWorks tests first, and every later readback then agrees
    on that wrong line, so the only proof is against an independently
    identified entity.
    """
    if expected is None:
        return selected
    if expected is not selected and not _is_same_attachment(
        adapter, selected, expected, entity_type.upper()
    ):
        raise RuntimeError(
            f"{what} pick resolved to a {entity_type.lower()} other than the "
            f"one named ({label}): the hit-test landed on a neighbour"
        )
    return expected
