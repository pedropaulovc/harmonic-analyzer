"""Drawing BOM balloon anchors, placement and landing verification.

Assembly BOM drawings plan component anchors and prove balloon landings here
without re-keying ordinary part annotations.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
import math
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks import drawing as _sw_drawing
from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _bind, _com_invoke, _early_bound
from _drawing_attachment import _assert_leader_lands
from _drawing_balloon_display import rendered_balloon_circle
from _drawing_common import rebuild_drawing
from _drawing_projection import model_points_in_view
from _drawing_scan import _HIT_ZOOM_HALF, _span_scan_attrs, _zoomed_on
from _drawing_selection import _activate_and_select_view, _select_view_entity
import _seat_forensics
import _telemetry


# Ink gap left between two balloon circles pushed apart on the ring. Their radius
# is measured from its rendered full-circle arc (4.72 mm on pen-assembly), so
# this is only the clearance between them, not a stand-in for the circle itself.
_BALLOON_CLEARANCE_M = 0.0015


# A BOM balloon's leader lands on an edge the hit test proved drawn at the
# requested point, but the edges beside it can be closer than 1 mm: at 1:8 a
# #4-40 screw head is 0.35 mm across on the sheet, and on run
# 20260928T194845954Z-44f5de00de924735961d14f4aad40337 a 0.46 mm drift left
# the frame's screw balloon ending in the nameplate engraving.
_BALLOON_LANDING_TOLERANCE_M = 0.0002


def _min_angular_gap(
    ring_radius: float, balloon_radius: float, *, clearance: float
) -> float:
    """Smallest angle between two balloon centres that keeps their circles apart.

    Separation is set against the SQUARE the audit boxes a balloon with, not the
    circle the sheet draws: :func:`_note_element` boxes the circle's circumscribed
    square, and two such squares whose centres lie on a ring DIAGONAL still
    intersect after their circles have parted -- ``dx = dy = d/sqrt(2)``, so they
    only clear once ``d >= 2*sqrt(2)*balloon_radius``. Separating to ``2*r`` (the
    circles just touching) measured 9 overlaps on pen-assembly: correct about the
    ink, wrong about the checker. Placement must satisfy the model that grades it.

    Measured against ARC length rather than the true chord, which is conservative
    (arc >= chord) and avoids a domain error as the required separation
    approaches the ring's diameter.

    ``ring_radius`` must be the ring ellipse's SMALLER semi-axis: a point's local
    speed along the ellipse is ``sqrt(Rx^2 sin^2 t + Ry^2 cos^2 t)``, whose
    minimum is ``min(Rx, Ry)`` -- so using it can only over-separate, never leave
    two circles touching.
    """
    if ring_radius <= 0.0:
        raise ValueError("balloon spread: ring radius must be positive")
    return (2.0 * math.sqrt(2.0) * balloon_radius + clearance) / ring_radius


def _wrap_angle(angle: float) -> float:
    """Fold ``angle`` back into ``(-pi, pi]`` -- the range ``atan2`` returns."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def _push_apart_on_ring(
    angles: list[float], *, min_gap: float, iterations: int = 400
) -> list[float]:
    """Separate ``angles`` to at least ``min_gap`` apart, preserving their order.

    ``angles`` must be sorted. Order preservation is the whole point, not a
    nicety: balloons placed about a shared centre in their attachments' angular
    ORDER cannot have crossing leaders, so a separation pass that never reorders
    cannot reintroduce one. That argument only holds if the solver actually
    preserves order, so this does it BY CONSTRUCTION rather than by assertion.

    Substituting ``z_i = x_i - i*min_gap`` turns the spacing constraint
    ``x_{i+1} - x_i >= min_gap`` into plain monotonicity ``z_{i+1} >= z_i``, so
    the minimum-movement placement is the isotonic regression of ``z`` -- solved
    exactly by pool-adjacent-violators, in one pass, with no convergence
    question.

    (History: this WAS an iterative pairwise relaxation, and it silently BROKE
    the order it was written to preserve. It measured each gap as
    ``(x[j] - x[i]) % 2pi``, so an inverted pair read as a ~6 rad gap -- huge,
    apparently fine -- and was never repaired; in-place sequential updates then
    kept inverting more. Probed on pen-assembly, it returned
    ``[..., -1.553, -1.817, ...]`` from sorted input while its own docstring
    claimed "it cannot swap them". Do not reintroduce a relaxation here.)

    Falls back to EVEN spacing when the balloons cannot all fit at ``min_gap``
    (``n * min_gap > 2*pi``); packing them tighter than their own circles would
    trade this function's crossings for overlaps, which is the trade the pure-
    radial experiment already lost.

    **Seam-safe.** Angles are a circular quantity, so the isotonic solver must
    run on a LINEAR run that never crosses the +-pi seam. The occupied
    attachments always leave one largest angular gap; unwrapping the run to
    START just after that gap places the seam inside empty space, where a linear
    chain is exact. Without this, a cluster straddling +-pi (attachments on the
    LEFT of the view) reads as two far-apart sub-runs, the solver under-separates
    them, and the wrap-around re-centre below -- an ORDINARY average of the two
    endpoints -- lands on the OPPOSITE side of the view, hauling every leader
    across the model (Codex #3605056589: ``[-3.10, 3.10]`` -> ``[-0.4, 0.0]``).
    """
    count = len(angles)
    if count < 2:
        return list(angles)
    two_pi = 2.0 * math.pi
    span_needed = count * min_gap
    if span_needed > two_pi:
        _telemetry.warn(
            f"balloon spread: {count} balloons need {span_needed:.2f} rad of "
            f"ring but only {two_pi:.2f} is available -- falling back to "
            "even spacing (leaders may run long)"
        )
        start = angles[0]
        return [start + two_pi * i / count for i in range(count)]

    # Unwrap around the LARGEST gap: sort by angle, find the widest gap between
    # cyclically-adjacent attachments, and read the run off as a single strictly
    # increasing sequence starting just after it. The seam then falls in that
    # empty gap, so nothing below straddles +-pi.
    order = sorted(range(count), key=lambda i: angles[i])
    ordered = [angles[i] for i in order]
    gaps = [(ordered[(j + 1) % count] - ordered[j]) % two_pi for j in range(count)]
    cut = max(range(count), key=lambda j: gaps[j])
    run_index = [order[(cut + 1 + step) % count] for step in range(count)]
    base = angles[run_index[0]]
    run = []
    for i in run_index:
        value = angles[i]
        while value < base - 1e-12:
            value += two_pi
        run.append(value)

    # Blocks of (weighted mean, weight) merged while the previous block outranks
    # the next -- the pool-adjacent-violators algorithm.
    blocks: list[list[float]] = []
    for index, angle in enumerate(run):
        blocks.append([angle - index * min_gap, 1.0])
        while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0] - 1e-15:
            value_b, weight_b = blocks.pop()
            value_a, weight_a = blocks.pop()
            weight = weight_a + weight_b
            blocks.append([(value_a * weight_a + value_b * weight_b) / weight, weight])
    fitted: list[float] = []
    for value, weight in blocks:
        fitted.extend([value] * int(weight))
    spread = [value + i * min_gap for i, value in enumerate(fitted)]

    # The wrap-around pair (last -> first) is the one constraint the linear chain
    # cannot see. Unwrapping put the widest gap at the seam, so there is room by
    # construction unless the run fills nearly the whole ring; then centre it in
    # the slack. The endpoints share one linear frame now, so their average is
    # the true midpoint -- no seam to jump.
    if (spread[0] + two_pi) - spread[-1] < min_gap:
        centre = (spread[0] + spread[-1]) / 2.0
        start = centre - span_needed / 2.0
        spread = [start + i * min_gap for i in range(count)]

    result = [0.0] * count
    for step, i in enumerate(run_index):
        result[i] = _wrap_angle(spread[step])
    return result


def _balloon_item_key(adapter: Any, note: Any) -> tuple[int, str]:
    """A balloon's BOM item number, as a sort key that never ties on order.

    The last resort in :func:`_spread_balloons`' ring sort. Every field ahead of
    it is geometric and can therefore tie exactly -- two overlapping or coaxial
    components project to one attachment point -- at which point a stable sort
    silently falls back to ``AutoBalloon5``'s arrival order, which is the very
    nondeterminism the sort exists to remove.

    The item number is the only identity here that comes from the component's
    BOM ROW rather than from when its balloon happened to be created, so it is
    the one that actually terminates the chain. ``IAnnotation::GetName`` would
    NOT do: names like ``DetailItem347`` are handed out at creation time, in
    arrival order, so keying on one re-encodes the instability it is meant to
    break.

    Read through ``GetBomBalloonText(True)`` -- the balloon-specific API for the
    displayed UPPER item, the same one :func:`_balloon_item_number` uses -- and
    NOT through ``INote::GetText``. GetText returns the note's generic text,
    which for a BOM balloon is not guaranteed to be the item number and can come
    back empty; every key would then collapse to ``(sys.maxsize, "")``, the sort
    would tie on all four fields, and this tie-break would silently be a no-op
    that still LOOKS like a fix.

    Returns ``(number, text)`` so "2" sorts before "10" rather than after it,
    with the raw text carrying non-numeric balloons (``A``, ``12A``) and ties
    among them. An unreadable balloon sorts last under its own text rather than
    failing the drawing: this is a tie-break, and losing it degrades placement
    determinism, not correctness. (:func:`_balloon_item_number` raises on the
    same read because there the item IS the product; here it is a sort key.)
    """
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetBomBalloonText")
    text = adapter._attempt(lambda n=note: n.GetBomBalloonText(True), default="") or ""
    text = str(text).strip()
    leading = ""
    for char in text:
        if not char.isdigit():
            break
        leading += char
    return (int(leading) if leading else sys.maxsize, text)


def _spread_balloons(
    adapter: Any,
    view: Any,
    balloons: list[Any],
    *,
    margin: float = 0.014,
    clearance: float = _BALLOON_CLEARANCE_M,
) -> None:
    """Re-ring auto-balloons evenly around ``view`` (the layout audit fails loud).

    ``AutoBalloon5`` stacks balloons whose attachment points cluster, and on a
    pictorial view its square layout can even drop balloons INSIDE the outline
    box. Deterministic fix: place every balloon's rendered CIRCLE centre on an
    ellipse ``margin`` outside the view outline, evenly spaced, and assign the
    ring slots in the angular order of the balloons' ATTACHMENT POINTS. Leaders
    stay attached; only the balloon anchor moves (``IAnnotation.SetPosition``),
    carrying the anchor's constant offset from the circle centre (#866).

    **Sort on the ATTACHMENT, not on where the balloon landed.** For straight
    leaders from points on a convex ring to points inside it, the non-crossing
    condition is that the ring order matches the ATTACHMENTS' angular order --
    ring slot k must serve the k-th attachment going round. Sorting on the
    balloon's own landed angle (the ``GetPosition`` this used to read) merely
    preserves AutoBalloon5's ordering, which was never non-crossing to begin
    with, so the ring was re-spacing the balloons while faithfully reproducing
    the crossings.

    This docstring used to CLAIM "each assigned the ring slot nearest its landed
    angle so leaders do not cross". That claim was never true and never tested;
    the shipped pen-assembly sheet crossed B4xB6 at (0.2285, 0.1161) under it.
    ``find_leader_leader_crossings`` is now the repro, so the claim is a gate
    rather than a comment.

    Attachment = the LAST point of ``GetLeaderPointsAtIndex(0)``; the first is
    the balloon end. Measured on pen-assembly's 8 balloons: the first points
    spread over 61 mm of x (the ring) while the last cluster within 13 mm (the
    tall, skinny pen sub they point at).
    """
    outline = adapter._attempt(lambda: view.GetOutline())
    if not outline:
        raise RuntimeError("balloon spread: view has no outline")
    vxmin, vymin, vxmax, vymax = (float(v) for v in list(outline)[:4])
    center_x, center_y = (vxmin + vxmax) / 2.0, (vymin + vymax) / 2.0
    radius_x = (vxmax - vxmin) / 2.0 + margin
    radius_y = (vymax - vymin) / 2.0 + margin
    items = []
    radii: list[float] = []
    for note in balloons:
        note = _sw_type_info.early_bound_or_flag(
            note, "INote", "GetAnnotation", "GetBomBalloonText"
        )
        circle_x, circle_y, radius = rendered_balloon_circle(
            note, label="balloon spread"
        )
        radii.append(radius)
        annotation = adapter._attempt(lambda n=note: n.GetAnnotation())
        if annotation is None:
            raise RuntimeError("balloon spread: balloon without an annotation")
        annotation = _sw_type_info.early_bound_or_flag(
            annotation,
            "IAnnotation",
            "GetPosition",
            "SetPosition",
            "GetLeaderPointsAtIndex",
        )
        # SetPosition moves the ANCHOR, which is not the circle centre: it sits
        # a constant ~(+4.0, -1.7) mm off it (#866, 40 balloons on MHA-DT-00).
        # Carry that offset so the CIRCLE lands on its ring slot.
        anchor = annotation.GetPosition()
        if anchor is None or len(anchor) < 2:
            raise RuntimeError("balloon spread: balloon without a position")
        offset = (float(anchor[0]) - circle_x, float(anchor[1]) - circle_y)
        # Never GetExtent: a balloon note's extent box includes its LEADER, so it
        # spans to the pointed-at component and is useless for placing the
        # balloon circle itself.
        raw = adapter._attempt(lambda a=annotation: a.GetLeaderPointsAtIndex(0))
        if not raw or len(raw) < 6:
            raise RuntimeError(
                "balloon spread: balloon without a readable leader -- the ring "
                "order is derived from the ATTACHMENT point, so a balloon whose "
                "leader cannot be read cannot be placed without crossing"
            )
        # Flat x,y,z stream; the LAST triple is the attachment on the component.
        attach_x, attach_y = float(raw[-3]), float(raw[-2])
        theta = math.atan2(attach_y - center_y, attach_x - center_x)
        items.append(
            (
                theta,
                attach_x,
                attach_y,
                _balloon_item_key(adapter, note),
                (annotation, offset),
            )
        )
    # Sort on (theta, attach x, attach y, BOM item), never on theta alone. Two
    # balloons attached at the same angle from the view centre -- coaxial parts
    # in a pictorial view do this routinely -- would otherwise keep whatever
    # relative order the balloons arrived in, which is AutoBalloon5's, which is
    # not stable. Ring order decides whether leaders cross, so an unstable
    # tie-break is an unstable drawing.
    #
    # The BOM item number is the LAST key because the three geometric ones can
    # ALL tie: overlapping or coaxial components can attach at exactly the same
    # projected point, and then the stable sort just re-emits AutoBalloon5's
    # arrival order -- the same nondeterminism, one level down. The item number
    # is the only field here tied to the component's BOM row rather than to when
    # the balloon happened to be created, so it is the one that ends the chain.
    order = sorted(range(len(items)), key=lambda i: items[i][:4])
    items = [items[i] for i in order]
    radii = [radii[i] for i in order]
    _telemetry.event(
        "drawing.balloon_ring",
        count=len(items),
        attachments=[f"{x:.6f},{y:.6f}" for _t, x, y, _i, _a in items],
        items=[str(item) for _t, _x, _y, item, _a in items],
    )

    # Place each balloon at its OWN attachment's angle, then separate only the
    # circles that actually collide. Two earlier placements both failed, each in
    # the way the other avoided, and this is the synthesis of what they proved:
    #
    #   EVEN SPACING (was here) preserved the attachments' ORDER but not their
    #   DIRECTIONS. The pen sub is tall and skinny, so its 8 attachments cluster
    #   in a narrow angular band while evenly-spaced slots span 360 deg. Measured
    #   on the shipped sheet: balloon DetailItem347 sat at y=0.1908 serving an
    #   attachment at y=0.1035 -- an 87 mm near-vertical leader hauled across the
    #   model, and it alone caused BOTH remaining crossings.
    #
    #   PURE RADIAL placement fixed that (crossings 2 -> 0: radial segments about
    #   a shared centre cannot intersect) but piled the clustered balloons on top
    #   of each other -- overlaps 0 -> 9, the very defect AutoBalloon5 has and
    #   this function exists to undo. It failed for ONE reason: nothing separated
    #   the colliding circles.
    #
    # So: keep the radial direction, enforce a minimum angular separation. The
    # separation is derived from the rendered full-circle radius, not a guess.
    # A monotone push-apart cannot reorder balloons; placement about a shared centre
    # is what rules crossings out, so this keeps radial's proof while paying
    # radial's price only where circles genuinely touch.
    gap = _min_angular_gap(min(radius_x, radius_y), max(radii), clearance=clearance)
    angles = _push_apart_on_ring(
        [theta for theta, _x, _y, _i, _a in items], min_gap=gap
    )
    for angle, (_theta, _x, _y, _item, (annotation, offset)) in zip(angles, items):
        target_x = center_x + radius_x * math.cos(angle) + offset[0]
        target_y = center_y + radius_y * math.sin(angle) + offset[1]
        if not annotation.SetPosition(target_x, target_y, 0.0):
            raise RuntimeError("failed to re-ring a BOM balloon")


@_telemetry.traced("drawing.auto_balloons", label_param="label")
def _create_auto_balloons(
    adapter: Any,
    view: Any,
    *,
    label: str,
    allow_empty: bool = False,
    layout: int = 1,
    attachment: Literal["face", "edge"] = "face",
) -> list[Any]:
    """Create item-number balloons for one selected view without repositioning."""
    if layout not in range(1, 7):
        raise ValueError(f"{label}: invalid auto-balloon layout {layout}")
    if attachment not in ("face", "edge"):
        raise ValueError(f"{label}: invalid auto-balloon attachment {attachment!r}")
    _activate_and_select_view(adapter, view, label=label)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    options = ddoc.CreateAutoBalloonOptions()
    if options is None:
        raise RuntimeError(f"failed to create auto-balloon options ({label})")
    options = _sw_type_info.early_bound_or_flag(options, "IAutoBalloonOptions")
    options.Layout = layout
    options.ReverseDirection = False
    options.IgnoreMultiple = True
    options.InsertMagneticLine = False
    options.LeaderAttachmentToFaces = attachment == "face"
    options.Style = 1
    options.Size = 2
    options.UpperTextContent = 1
    options.ItemNumberStart = 1
    options.ItemNumberIncrement = 1
    options.ItemOrder = 1
    notes = ddoc.AutoBalloon5(options)
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_create_auto_balloons")
    if not notes or isinstance(notes, str):
        if allow_empty:
            return []
        raise RuntimeError(f"AutoBalloon5 produced no balloons ({label})")
    balloons = list(notes)
    identities: list[str] = []
    for note in balloons:
        item = _balloon_item_number(adapter, note, label=label)
        note = _sw_type_info.early_bound_or_flag(note, "INote", "GetName")
        identities.append(f"{note.GetName()}=item {item}")
    _telemetry.info(f"{label}: AutoBalloon5 identities {identities}")
    return balloons


def balloon_item_resolved(text: str) -> bool:
    """Whether a BOM balloon's displayed item is a real one: SolidWorks prints
    ``?`` when the balloon's component no longer resolves to a BOM row (the
    feature-suppression preview's balloons did), and nothing when unattached."""
    item = text.strip()
    return bool(item) and "?" not in item


def _balloon_item_number(adapter: Any, note: Any, *, label: str) -> str:
    """Read one BOM balloon's displayed upper item number; refuse an unresolved one."""
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetBomBalloonText")
    item = str(adapter._attempt(lambda: note.GetBomBalloonText(True)) or "").strip()
    if not balloon_item_resolved(item):
        raise RuntimeError(f"{label}: BOM balloon shows unresolved item {item!r}")
    return item


@_telemetry.traced("drawing.validated_auto_balloons", label_param="label")
def add_auto_balloons(
    adapter: Any,
    view: Any,
    *,
    items: Sequence[tuple[str, str]],
    label: str,
) -> list[BalloonLanding]:
    """Insert one native EDGE/Square balloon per requested ``(stem, BOM item)``.

    Keep AutoBalloon5's positions, with no sheet-coordinate picks or spreading.
    Every returned item must occur exactly once and attach to one real edge of
    a shown full component path belonging to that row's family. Return native
    landings for the drawing's existing final-rebuild attachment check.
    The span covers component resolution, creation, rebuild and validation,
    not just the AutoBalloon5 call.
    """
    if not items:
        raise ValueError(f"{label}: component balloon list must not be empty")
    stems = [stem for stem, _item in items]
    numbers = [item for _stem, item in items]
    if len(stems) != len(set(stems)) or len(numbers) != len(set(numbers)):
        raise ValueError(f"{label}: duplicate component or item number")
    leaves = _view_component_leaves(adapter, view, label=label)
    expected = {
        item: (
            stem,
            {
                leaf.path.casefold()
                for leaf in _shown_instances(leaves, stem, BalloonAnchor(), label=label)
            },
        )
        for stem, item in items
    }
    _telemetry.annotate(expected=len(expected), attachment="EDGE", layout=1)
    balloons = _create_auto_balloons(
        adapter, view, label=label, attachment="edge", layout=1
    )
    seen: set[str] = set()
    landings: list[BalloonLanding] = []
    for raw_note in balloons:
        note = _early_bound(raw_note, "INote")
        item = _balloon_item_number(adapter, note, label=label)
        if item not in expected:
            raise RuntimeError(f"{label}: unexpected native BOM item {item}")
        if item in seen:
            raise RuntimeError(f"{label}: duplicate native BOM item {item}")
        seen.add(item)
        stem, allowed = expected[item]
        annotation = note.GetAnnotation()
        if annotation is None:
            raise RuntimeError(f"{label}: {stem} item {item} has no native annotation")
        annotation = _early_bound(annotation, "IAnnotation")
        entities = tuple(annotation.GetAttachedEntities3() or ())
        kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
        if len(entities) != 1 or kinds != (_SEL_EDGES,) or entities[0] is None:
            raise RuntimeError(
                f"{label}: {stem} item {item} must attach to one native EDGE; "
                f"entities={len(entities)}, types={list(kinds)}"
            )
        owner = _entity_owner(adapter, entities[0])
        _telemetry.event(
            "drawing.auto_balloon_owner", stem=stem, item=item, instance=owner
        )
        if not owner or owner.casefold() not in allowed:
            raise RuntimeError(
                f"{label}: {stem} item {item} native EDGE owner {owner!r} "
                f"is not a shown instance of its BOM row; expected={sorted(allowed)}"
            )
        landings.append(
            BalloonLanding(
                stem=stem, instance=owner, note=note, sheet_xy=None, label=label
            )
        )
    missing = sorted(expected.keys() - seen)
    if missing:
        raise RuntimeError(f"{label}: missing native BOM items {missing}")
    _telemetry.success(f"{label}: validated {len(landings)} native BOM balloons")
    return landings


def _drawing_component_children(drawing_component: Any) -> tuple[Any, ...]:
    """Return children across callable and materialized pywin32 shapes."""
    member = drawing_component.GetChildren
    children = member() if callable(member) else member
    return tuple(children or ())


@dataclass(frozen=True)
class BalloonAnchor:
    """Where one BOM family's balloon attaches: a point on one of its edges.

    ``point_mm`` is in the part's own millimetres, so view scale, placement
    and explode distance do not move it. ``instance`` pins the instance it is
    on by its full component path (``IComponent2.Name2``: ``dt-cone-gear-2``, or
    ``sub-1/dt-cone-gear-2`` inside a sub-assembly); ``None`` means the
    lowest-named instance the view shows (:func:`_shown_instances`).

    ``point_mm=None`` walks the part's own body instead
    (:func:`_select_balloon_anchor`), for a family no single point claims,
    on the pinned instance or else the lowest-named shown one, never another.
    """

    point_mm: tuple[float, float, float] | None = None
    instance: str | None = None


@dataclass(frozen=True)
class _ComponentLeaf:
    """One leaf drawing component and the file identities it answers to.

    ``visible`` is the leaf's own drawing-view flag AND every ancestor's: a
    part under a hidden sub-assembly is not drawn, whatever its own flag says.
    ``path`` is the model component's full instance path
    (:func:`_component_path`), the identity every ownership check compares:
    two sub-assemblies may each hold a ``dt-cone-gear-1``, so the last path
    segment names no instance on its own.
    """

    name: str
    component: Any
    identities: frozenset[str]
    visible: bool = True
    path: str = ""


def _instance_name(name: str) -> str:
    """``dt-drive-train-8/dt-cone-gear-2@Drawing View1`` -> ``dt-cone-gear-2``.

    For file-stem matching only: it drops the sub-assembly path, so it never
    decides which instance an entity belongs to (:func:`_component_path`).
    """
    return name.split("@", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]


def _component_path(adapter: Any, component: Any) -> str:
    """A model component's full instance path, ``IComponent2.Name2``.

    A drawing component's ``Name`` carries the view's root prefix
    (``fr-frame-4/fr-vn-tube-frame-cap-1``) while an edge's owning component reads
    ``fr-tube-frame-3`` (farm probe on the frame drawing): ``Name2`` of the
    model component is the one string both sides share, and it keeps every
    sub-assembly segment (``sub-1/dt-cone-gear-1``).
    """
    if component is None:
        return ""
    name = adapter._attempt(
        lambda: _early_bound(component, "IComponent2").Name2, default=""
    )
    return str(name or "").replace("\\", "/")


def _component_leaf(
    adapter: Any, drawing_component: Any, *, visible: bool = True
) -> _ComponentLeaf:
    """Read one leaf drawing component's model component and identities."""
    component = adapter._attempt(
        lambda dc=drawing_component: dc.Component, default=None
    )
    path = ""
    if component is not None:
        path = adapter._attempt(lambda c=component: c.GetPathName(), default="") or ""
    name = str(drawing_component.Name or "")
    identities = frozenset(
        {
            Path(str(path)).stem.casefold(),
            _instance_name(name).casefold(),
        }
    )
    return _ComponentLeaf(
        name=name, component=component, identities=identities, visible=visible
    )


def _stems_matching(identities: frozenset[str], stems: frozenset[str]) -> set[str]:
    """Return the requested file stems ``identities`` represent."""
    return {
        stem
        for stem in stems
        if any(
            identity == stem
            or (
                identity.startswith(f"{stem}-")
                and identity.removeprefix(f"{stem}-").isdigit()
            )
            for identity in identities
        )
    }


def _drawing_component_stems(
    adapter: Any, drawing_component: Any, stems: frozenset[str]
) -> set[str]:
    """Return requested file stems represented by one leaf drawing component."""
    return _stems_matching(
        _component_leaf(adapter, drawing_component).identities, stems
    )


@_telemetry.traced("drawing.component_leaves", label_param="label")
def _view_component_leaves(
    adapter: Any, view: Any, *, label: str
) -> tuple[_ComponentLeaf, ...]:
    """Every leaf drawing component of ``view``, in depth-first walk order,
    each marked shown or hidden in this view.

    Balloon anchoring used to repeat this walk once PER BALLOON -- ~3 s of
    fixed cost on every ``drawing.pick_balloon_anchor`` span across the farm
    (fit intercept 3.08 s, n=1302). Inserting balloons changes no component
    visibility, so one walk serves a whole balloon set.
    """
    root = adapter._attempt(lambda: view.RootDrawingComponent2(False), default=None)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    leaves: list[_ComponentLeaf] = []
    pending = [(child, True) for child in _drawing_component_children(root)]
    while pending:
        drawing_component, shown = pending.pop()
        shown = shown and bool(
            adapter._attempt(lambda dc=drawing_component: dc.Visible, default=True)
        )
        children = _drawing_component_children(drawing_component)
        pending.extend((child, shown) for child in children)
        if children:
            continue
        leaf = _component_leaf(adapter, drawing_component, visible=shown)
        leaves.append(replace(leaf, path=_component_path(adapter, leaf.component)))
    _span_scan_attrs(leaves=len(leaves))
    return tuple(leaves)


@_telemetry.traced("drawing.isolate_components", label_param="label")
def isolate_drawing_view_components(
    adapter: Any,
    view: Any,
    *,
    visible_stems: frozenset[str],
    label: str,
) -> None:
    """Show only requested top-level component families in one drawing view."""
    if not visible_stems:
        raise ValueError(f"{label}: visible component set must not be empty")
    root = adapter._attempt(lambda: view.RootDrawingComponent2(False), default=None)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")

    pending = list(_drawing_component_children(root))
    found: set[str] = set()
    enumerated: list[str] = []
    while pending:
        drawing_component = pending.pop()
        children = _drawing_component_children(drawing_component)
        pending.extend(children)
        enumerated.append(str(drawing_component.Name or ""))
        if children:
            continue
        matched = _drawing_component_stems(adapter, drawing_component, visible_stems)
        drawing_component.Visible = bool(matched)
        found.update(matched)

    missing = sorted(visible_stems - found)
    if missing:
        raise RuntimeError(
            f"{label}: component families not found: {missing}; "
            f"enumerated={sorted(enumerated)}"
        )
    rebuild_drawing(adapter, label="isolate_drawing_view_components")
    _telemetry.success(f"{label}: isolated {', '.join(sorted(found))}")


def _natural_sort_key(name: str) -> tuple[tuple[int, int | str], ...]:
    """``dt-cone-gear-2`` before ``dt-cone-gear-10``: digit runs compare as numbers."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", name)
        if part
    )


def _shown_instances(
    leaves: Sequence[_ComponentLeaf],
    stem: str,
    anchor: BalloonAnchor,
    *,
    label: str,
) -> list[_ComponentLeaf]:
    """The instances ``stem``'s balloon may anchor on, first choice first.

    The drawing-component tree lists children in no stable order: over 26
    frame_assembly runs the old first-match walk anchored the cap balloon on
    tube-frame-cap 1, 2, 3 and 4 in turn. The instance path is the one order
    that cannot move, compared as a machinist reads it (2 before 10). A
    hidden instance (drive-train isolates one cluster per view) is never a
    candidate, and a pinned instance is the only one.
    """
    wanted = frozenset({stem})
    matching = sorted(
        (leaf for leaf in leaves if _stems_matching(leaf.identities, wanted)),
        key=lambda leaf: _natural_sort_key(leaf.path or _instance_name(leaf.name)),
    )
    shown = [
        leaf
        for leaf in matching
        if leaf.visible and leaf.component is not None and leaf.path
    ]
    if anchor.instance is not None:
        shown = [
            leaf for leaf in shown if leaf.path.casefold() == anchor.instance.casefold()
        ]
    if not shown:
        pinned = f" {anchor.instance}" if anchor.instance else ""
        raise RuntimeError(
            f"{label}: {stem} has no shown instance{pinned} to anchor its balloon "
            f"on; matching={[(leaf.path or leaf.name, leaf.visible) for leaf in matching]}"
        )
    return shown


def _path_prefixes(path: str) -> list[str]:
    """``sub-1/dt-cone-gear-2`` -> ``["sub-1", "sub-1/dt-cone-gear-2"]``."""
    parts = path.split("/")
    return ["/".join(parts[: count + 1]) for count in range(len(parts))]


@_telemetry.traced("drawing.explode_offsets", label_param="label")
def _view_explode_offsets(
    adapter: Any, view: Any, *, label: str
) -> dict[str, tuple[float, float, float]]:
    """Each exploded component's explode translation, in model metres, keyed
    by its casefolded full instance path (:func:`_component_path`).

    A drawing view shows its model exploded without exploding the model, so
    every component transform (``Transform2``, ``GetSpecificTransform``,
    ``GetTotalTransform``) still reads the collapsed position -- measured on
    the farm: points projected through them landed on the neighbour each
    part had been exploded away from. The explode itself lives in the
    referenced configuration's steps; both explode builders
    (``build_frame_assembly``, ``_drive_train_explode``) author pure
    translations, and a step that rotates is refused rather than summed wrong.

    Each moved component is read as a component (``IExplodeStep::GetComponent``)
    and keyed by the same ``Name2`` the view's leaves carry: the step's own
    name string is an undocumented format, and cutting it to its last segment
    merged two sub-assemblies' ``cone-gear-1``.

    Two reads that fail once a model owns explodes in more than one
    configuration (``Default`` and ``Default Simplified``), measured on both
    frame and drive-train drawings (farm probe, 2026-09-28):

    * the model's ACTIVE configuration reads zero steps until its named
      explode is shown on the model; showing it and collapsing it again makes
      all of them readable and leaves the drawing view exploded;
    * a NON-active configuration reads every step, but ``GetComponent``
      returns None for every member. ``GetComponentName`` then read exactly
      the member's ``Name2``, so the member is resolved by that name against
      the configuration's own component tree. A name that is not one of that
      tree's instance paths still refuses the view.
    """
    bound = _early_bound(view, "IView")
    if not bool(bound.IsExploded()):
        return {}
    model = _early_bound(bound.ReferencedDocument, "IModelDoc2")
    configuration_name = str(bound.ReferencedConfiguration)
    configuration = model.GetConfigurationByName(configuration_name)
    if configuration is None:
        raise RuntimeError(f"{label}: exploded view has no referenced configuration")
    configuration = _early_bound(configuration, "IConfiguration")
    count = int(configuration.GetNumberOfExplodeSteps())
    read = "direct"
    if count == 0:
        count = _shown_explode_step_count(
            model, configuration, configuration_name, label=label
        )
        read = "shown on model"
        if not bool(bound.IsExploded()):
            raise RuntimeError(
                f"{label}: collapsing the model collapsed the drawing view"
            )
    if count == 0:
        raise RuntimeError(
            f"{label}: exploded view's configuration {configuration_name!r} reads no explode steps"
        )
    offsets: dict[str, list[float]] = {}
    instances: dict[str, str] | None = None
    by_name = 0
    for index in range(count):
        step = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
        xform = tuple(float(value) for value in (step.GetComponentXform() or ()))
        if len(xform) < 13 or any(
            abs(xform[k] - (1.0 if k in (0, 4, 8) else 0.0)) > 1e-9 for k in range(9)
        ):
            raise RuntimeError(
                f"{label}: explode step {step.Name!r} is not a pure translation: "
                f"{xform!r}"
            )
        for member in range(int(step.GetNumOfComponents())):
            path = _component_path(adapter, step.GetComponent(member))
            if not path:
                if instances is None:
                    instances = _configuration_instance_paths(adapter, configuration)
                name = str(step.GetComponentName(member) or "").replace("\\", "/")
                path = instances.get(name.casefold(), "")
                if not path:
                    raise RuntimeError(
                        f"{label}: explode step {step.Name!r} moves {name!r}, which reads "
                        f"as no component and names no instance of {configuration_name!r}"
                    )
                by_name += 1
            row = offsets.setdefault(path.casefold(), [0.0, 0.0, 0.0])
            for axis in range(3):
                row[axis] += xform[9 + axis]
    _span_scan_attrs(steps=count, moved=len(offsets), by_name=by_name)
    _telemetry.annotate(explode_read=read)
    return {name: (row[0], row[1], row[2]) for name, row in offsets.items()}


def _shown_explode_step_count(
    model: Any, configuration: Any, configuration_name: str, *, label: str
) -> int:
    """Show the active configuration's one named explode on the model, then
    collapse it again, and return the step count that makes readable."""
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    active = str(_early_bound(manager.ActiveConfiguration, "IConfiguration").Name)
    if active != configuration_name:
        raise RuntimeError(
            f"{label}: {configuration_name!r} reads no explode steps and is not the "
            f"model's active configuration ({active!r})"
        )
    assembly = _early_bound(model, "IAssemblyDoc")
    names = tuple(
        str(name) for name in (assembly.GetExplodedViewNames2(configuration_name) or ())
    )
    if len(names) != 1:
        raise RuntimeError(
            f"{label}: {configuration_name!r} owns explodes {names!r}, not one"
        )
    if not bool(assembly.ShowExploded2(True, names[0])):
        raise RuntimeError(f"{label}: cannot show {names[0]!r} on the model")
    count = int(configuration.GetNumberOfExplodeSteps())
    if not bool(assembly.ShowExploded2(False, names[0])):
        raise RuntimeError(f"{label}: cannot collapse {names[0]!r} on the model")
    return count


def _configuration_instance_paths(adapter: Any, configuration: Any) -> dict[str, str]:
    """Every component instance path of ``configuration``, casefolded -> as read,
    walked from its own root (``GetRootComponent3(True)`` resolves a
    configuration that is not the model's active one)."""
    root = configuration.GetRootComponent3(True)
    paths: dict[str, str] = {}
    pending = list(root.GetChildren() or ()) if root is not None else []
    while pending:
        component = _early_bound(pending.pop(), "IComponent2")
        path = _component_path(adapter, component)
        if path:
            paths[path.casefold()] = path
        pending.extend(component.GetChildren() or ())
    return paths


def _explode_offset(
    offsets: Mapping[str, tuple[float, float, float]], path: str
) -> tuple[float, float, float]:
    """``path``'s own explode plus every enclosing sub-assembly's."""
    total = [0.0, 0.0, 0.0]
    for prefix in _path_prefixes(path):
        for axis, value in enumerate(offsets.get(prefix.casefold(), (0.0, 0.0, 0.0))):
            total[axis] += value
    return (total[0], total[1], total[2])


def _anchor_model_points(
    adapter: Any,
    leaf: _ComponentLeaf,
    points_m: Sequence[Sequence[float]],
    offsets: Mapping[str, tuple[float, float, float]],
    *,
    stem: str,
    label: str,
) -> list[tuple[float, float, float]]:
    """Part-space points (metres) in the view's model space: transform, then explode."""
    transform = adapter._attempt(
        lambda: _early_bound(leaf.component, "IComponent2").Transform2, default=None
    )
    values = (
        ()
        if transform is None
        else tuple(
            float(v)
            for v in (_early_bound(transform, "IMathTransform").ArrayData or ())
        )
    )
    if len(values) < 13:
        raise RuntimeError(f"{label}: {stem} instance {leaf.path} has no transform")
    scale = values[12]
    dx, dy, dz = _explode_offset(offsets, leaf.path)
    return [
        (
            scale * (x * values[0] + y * values[3] + z * values[6]) + values[9] + dx,
            scale * (x * values[1] + y * values[4] + z * values[7]) + values[10] + dy,
            scale * (x * values[2] + y * values[5] + z * values[8]) + values[11] + dz,
        )
        for x, y, z in points_m
    ]


# A walk hit-tests at most this many of its instance's extreme points, each a
# zoomed sheet round trip.
_WALK_POINTS_PER_INSTANCE = 12


# The visible-edge fallback samples every visible edge of the instance, so
# it refuses one with more: pins and screws draw 2-50, the keeper bead chain
# 110 (two rod/bead circles per link; its spheres draw only silhouettes, so it
# can only be claimed here), a gear over 1,000.
_VISIBLE_EDGES_PER_INSTANCE = 128


# Where along a listed edge's parameter range the fallback samples points to
# hit-test: inside the edge, off the vertices it shares with its neighbours.
_EDGE_SAMPLE_FRACTIONS = (0.1, 0.3, 0.5, 0.7, 0.9)


_VIEW_ENTITY_EDGE = 1  # swViewEntityType_Edge


_SEL_EDGES = 1  # swSelEDGES


# The walk's probe directions in part space: every sign of (1, 0.618, 0.382)
# in each cyclic order. No component is zero and no two are equal, so none is
# normal to an axis-aligned face or square to an axis-aligned bore, and a
# body's extreme point along one is a single point, on a plane-and-cylinder
# part usually a vertex or a point of an edge.
_WALK_DIRECTIONS: tuple[tuple[float, float, float], ...] = tuple(
    (sx * a, sy * b, sz * c)
    for a, b, c in ((1.0, 0.618, 0.382), (0.382, 1.0, 0.618), (0.618, 0.382, 1.0))
    for sx, sy, sz in product((1.0, -1.0), repeat=3)
)


AnchorMethod = Literal["frozen", "walk", "visible-edge", "shared-edge", "listed-edge"]


@dataclass(frozen=True)
class _AnchorChoice:
    """The edge one family's balloon attaches to, where, and how it was found.

    ``sheet_xy`` is the sheet point (metres) whose hit test returned ``edge``
    as the instance's: the balloon's leader must end there. Selected by entity
    alone, SolidWorks picks its own point on the edge, which on a washer or a
    gear rim is often behind another part: on run
    20260928T194845954Z-44f5de00de924735961d14f4aad40337 the thrust washer's
    leader landed 10.3 mm from its verified point, in the gear teeth.
    """

    instance: str
    edge: Any
    method: AnchorMethod
    sheet_xy: tuple[float, float]


_PointKey = tuple[int, int, int]


def _point_key(point: Sequence[float]) -> _PointKey:
    """A part-space point in whole micrometres: the ranking's stable key."""
    return (round(point[0] * 1e6), round(point[1] * 1e6), round(point[2] * 1e6))


def _spread_order(keys: Iterable[_PointKey], limit: int) -> list[_PointKey]:
    """Up to ``limit`` keys: the one farthest from the set's box centre, then
    each next the farthest from every one already taken.

    Geometry alone decides, ties falling to the smaller key, so points
    gathered in any order rank the same. Outermost first because a part's
    outer edges are the ones its neighbours hide least; spread because a
    family whose first point is hidden is seldom hidden all round.
    """
    pool = sorted(set(keys))
    if not pool or limit <= 0:
        return []
    doubled = [min(k[i] for k in pool) + max(k[i] for k in pool) for i in range(3)]

    def outward(key: _PointKey) -> int:
        return sum((2 * key[i] - doubled[i]) ** 2 for i in range(3))

    def apart(a: _PointKey, b: _PointKey) -> int:
        return sum((a[i] - b[i]) ** 2 for i in range(3))

    chosen = [min(pool, key=lambda key: (-outward(key), key))]
    gap = {key: apart(key, chosen[0]) for key in pool}
    while len(chosen) < min(limit, len(pool)):
        taken = set(chosen)
        best = min(
            (key for key in pool if key not in taken), key=lambda k: (-gap[k], k)
        )
        chosen.append(best)
        for key in pool:
            gap[key] = min(gap[key], apart(key, best))
    return chosen


def _walk_points(
    adapter: Any, leaf: _ComponentLeaf
) -> tuple[tuple[float, float, float], ...]:
    """``leaf``'s body's extreme points along :data:`_WALK_DIRECTIONS`, ranked.

    ``IBody2::GetExtremePoint`` answers from geometry alone, one point per
    direction even on a tie, so which points exist and the order
    :func:`_spread_order` tries them in owe nothing to a face or edge
    enumeration order (which nothing promises), and no face or edge proxy is
    materialised (a gear's toothed face held ~400). Part metres.
    """
    component = _early_bound(leaf.component, "IComponent2")
    body = adapter._attempt(lambda: component.GetBody(), default=None)
    if body is None:
        return ()
    bound = _early_bound(body, "IBody2")
    found: dict[_PointKey, tuple[float, float, float]] = {}
    for direction in _WALK_DIRECTIONS:
        # The wrapper returns the [out] coordinates after the found flag.
        result = tuple(bound.GetExtremePoint(*direction) or ())
        if len(result) == 4 and result[0]:
            point = (float(result[1]), float(result[2]), float(result[3]))
            found.setdefault(_point_key(point), point)
    return tuple(found[key] for key in _spread_order(found, _WALK_POINTS_PER_INSTANCE))


def _entity_owner(adapter: Any, entity: Any) -> str:
    """The full instance path of the component that owns ``entity``; ``""`` if none."""
    if entity is None:
        return ""
    bound = _early_bound(_bind(entity, "IEntity"), "IEntity")
    component = adapter._attempt(lambda: bound.GetComponent(), default=None)
    return _component_path(adapter, component)


# A frozen anchor's zoomed pick that finds no ink is repeated this many times,
# each after forcing the graphics window to redraw under the zoom. Misses
# returned in 45-172 ms against 300-1264 ms for every hit (21 days, n=20/472),
# as if the pick read a window that had not drawn the zoom; the same key and
# sheet point hit on another seat (#1667). The span's per-pick attributes
# measure whether the redraw heals it.
_FROZEN_REDRAW_RETRIES = 2


def _hit_test_edge(
    adapter: Any,
    sheet_xy: Sequence[float],
    *,
    redraw: bool = False,
    observed: dict[str, Any] | None = None,
    on_miss: Callable[[], None] | None = None,
) -> tuple[Any, str]:
    """Select the edge drawn at ``sheet_xy`` of the active view; return it and its owner.

    The pick runs zoomed onto the point (:data:`_HIT_ZOOM_HALF`), so which
    edge it returns does not depend on the seat's window size. In a drawing
    the view is selected alongside the edge; the edge is last. The selection
    is left in place for the caller to use or clear. ``redraw`` forces the
    window to draw the zoom before the pick; ``observed`` receives the
    zoomed view's ``Scale2`` (``None`` when unreadable). ``on_miss`` runs
    when the pick selects nothing, while the window is still zoomed on it.
    """
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    with _zoomed_on(adapter, sheet_xy, _HIT_ZOOM_HALF):
        if redraw:
            draw.GraphicsRedraw2()
        if observed is not None:
            observed["zoom_scale2"] = _view_scale2(draw)
        selected = draw.Extension.SelectByID2(
            "", "EDGE", sheet_xy[0], sheet_xy[1], 0.0, False, 0, null_callout(), 0
        )
        if not selected and on_miss is not None:
            on_miss()
    if not selected:
        return None, ""
    manager = draw.SelectionManager
    edge = manager.GetSelectedObject6(int(manager.GetSelectedObjectCount2(-1)), -1)
    return edge, _entity_owner(adapter, edge)


def _view_scale2(draw: Any) -> float | None:
    """The active model view's ``Scale2``; ``None`` when it cannot be read."""
    try:
        return float(draw.ActiveView.Scale2)
    except Exception:  # noqa: BLE001 - a telemetry read never fails the pick
        return None


def _visible_edge_points(
    adapter: Any, view: Any, leaf: _ComponentLeaf
) -> tuple[int, tuple[tuple[tuple[float, float, float], Any], ...]]:
    """How many edges of ``leaf`` the view lists as drawn, and points along them.

    ``IView::GetVisibleEntities2`` lists the edges the view's hidden-line pass
    kept: the fallback for a pin in its bore, whose extreme points sit on an
    outline its neighbour's edge also draws. Listed is not drawn everywhere:
    a washer's rim listed as visible ran behind the gear for most of its
    length. So each listed edge gives points (``ICurve::Evaluate2`` at
    :data:`_EDGE_SAMPLE_FRACTIONS` of its range), each with the listed edge
    it lies on, for the same hit test the walk runs, ranked by
    :func:`_spread_order` since the array's order is undocumented. Counted
    first: an instance drawing more than :data:`_VISIBLE_EDGES_PER_INSTANCE`
    edges is not fetched at all. Part metres.
    """
    bound = _early_bound(view, "IView")
    count = int(bound.GetVisibleEntityCount2(leaf.component, _VIEW_ENTITY_EDGE) or 0)
    if count <= 0 or count > _VISIBLE_EDGES_PER_INSTANCE:
        return count, ()
    found: dict[_PointKey, tuple[tuple[float, float, float], Any]] = {}
    raw = _sw_drawing.raw_visible_entities(view, leaf.component, _VIEW_ENTITY_EDGE)
    for edge in raw[:_VISIBLE_EDGES_PER_INSTANCE]:
        curve = _com_invoke(edge, "IEdge", "GetCurve")
        if curve is None:
            continue
        # GetCurveParams2 reads what GetCurve generated, so GetCurve first.
        params = tuple(
            float(v) for v in (_com_invoke(edge, "IEdge", "GetCurveParams2") or ())
        )
        if len(params) < 8:
            continue
        for fraction in _EDGE_SAMPLE_FRACTIONS:
            at = params[6] + fraction * (params[7] - params[6])
            value = tuple(_com_invoke(curve, "ICurve", "Evaluate2", at, 0) or ())
            if len(value) >= 3:
                point = (float(value[0]), float(value[1]), float(value[2]))
                found.setdefault(_point_key(point), (point, edge))
    return count, tuple(
        found[key] for key in _spread_order(found, _WALK_POINTS_PER_INSTANCE)
    )


@dataclass(frozen=True)
class _PointHit:
    """One hit-tested point: its index in the tried list, sheet point, the
    edge the hit test returned and that edge's owner."""

    index: int
    xy: tuple[float, float]
    edge: Any
    owner: str


def _scan_points(
    adapter: Any,
    view: Any,
    leaf: _ComponentLeaf,
    points: Sequence[tuple[float, float, float]],
    offsets: Mapping[str, tuple[float, float, float]],
    tried: list[tuple[float, float]],
    *,
    stem: str,
    what: str,
    label: str,
) -> tuple[_PointHit | None, _PointHit | None]:
    """Hit-test ``points`` (part metres) in order, stopping at the first
    whose hit returns an edge of exactly ``leaf`` (the claimed point).
    Also returns the first point that hit another part's edge on the way:
    ink is drawn there, shared or in front."""
    if not points:
        return None, None
    projected = model_points_in_view(
        adapter,
        view,
        _anchor_model_points(adapter, leaf, points, offsets, stem=stem, label=label),
        label=f"{label} {stem} {what}",
        names=[f"{stem} {what} {index}" for index in range(len(points))],
    )
    shared = None
    for index, xy in enumerate(projected):
        tried.append(xy)
        hit, owner = _hit_test_edge(adapter, xy)
        found = _PointHit(index=index, xy=xy, edge=hit, owner=owner)
        if owner.casefold() == leaf.path.casefold():
            return found, shared
        if hit is not None and shared is None:
            shared = found
    return None, shared


def _mm_text(values: Sequence[float], scale: float = 1.0) -> str:
    return ",".join(f"{value * scale:.3f}" for value in values)


@_telemetry.traced("drawing.pick_balloon_anchor", label_param="stem")
def _select_balloon_anchor(
    adapter: Any,
    view: Any,
    *,
    stem: str,
    anchor: BalloonAnchor,
    candidates: Sequence[_ComponentLeaf],
    offsets: Mapping[str, tuple[float, float, float]],
    sheet_xy: tuple[float, float] | None,
    label: str,
) -> _AnchorChoice:
    """Find the edge ``stem``'s balloon attaches to, and the sheet point on it.

    One hit test per balloon replaces fetching every visible edge of the
    component and keeping ``edges[0]``: that array's order moved between
    runs (harmonic-base's anchor walk took 17 shapes over 24 frame runs),
    and the nameplate's 37,148 edges cost ~524 s a pick, most of it releasing
    their COM proxies (#1079).

    ``frozen``: hit-test at the anchor's projected ``sheet_xy``. An edge of
    another instance in front of the point raises; the balloon never falls
    back to some other edge. No edge at all is retried
    :data:`_FROZEN_REDRAW_RETRIES` times after a forced redraw: a seat's
    zoomed pick can miss ink another seat hits at the same point (#1667). Only
    the instance's own ink passes. Each pick's outcome (``pickN``), time
    (``pickN_ms``) and zoom (``pickN_scale2``) is on the span, and
    ``picks`` lists the outcomes on the event. Every miss, healed or not, is
    screenshotted while still zoomed on the point
    (:func:`_seat_forensics.capture_pick_screens`); the files' paths under
    ``failures/`` ride the span as ``pickN_<kind>``. When every pick misses,
    :func:`_seat_forensics.capture_pick_miss` records them with the window
    and the drawing's pick state, and raises.

    ``walk`` (``anchor.point_mm is None``): hit-test the family's first
    instance's body extreme points (:func:`_walk_points`), the instance
    :func:`_shown_instances` put first (the pinned one when the anchor pins
    it), and take the first point the hit test gives back to that exact
    instance. Never a later instance: whether the first instance's points
    are drawn or covered is a hit result, and a hit result must not choose
    which part carries the item (the lag screw walked to lag-screw-2 after
    lag-screw-1's points all hit other parts; that choice is now a pin). A
    pin in its bore draws its outline on its neighbour's, so no extreme
    point may be claimed: ``visible-edge`` then hit-tests points along the
    edges of the same instance the view's hidden-line pass lists as drawn
    (:func:`_visible_edge_points`) and takes the first it claims. When the
    instance claims none but one of those points hits another part's edge,
    the outline is shared ink: ``shared-edge`` attaches to the listed edge
    that point lies on, landing there. When no point finds ink at all, the
    part shows only where no hit test reaches it (cone-tip-bushing-1 sits
    flush in the tip block's bore: none of 24 points hit any edge on runs
    20260928T202401351Z and 20260928T203306681Z): ``listed-edge`` attaches
    to the listed edge holding the first ranked point and lets SolidWorks
    place the leader on it, the one landing no read-back can prove. No
    listed edge fails the sheet, naming what was tried. Which method ran,
    and where, is in the ``drawing.balloon_anchor`` event (``shared`` names
    the other part).

    Every other method returns the hit-tested sheet point, where the
    balloon's leader is then made to land
    (:func:`_create_component_bom_balloon`).
    """
    first = candidates[0]
    instance = first.path
    tried: list[tuple[float, float]] = []
    scan_attrs: dict[str, Any] = {}
    method: AnchorMethod
    if anchor.point_mm is not None:
        if sheet_xy is None:
            raise RuntimeError(f"{label}: {stem} frozen anchor was never projected")
        where = f"sheet ({sheet_xy[0] * 1000.0:.2f}, {sheet_xy[1] * 1000.0:.2f}) mm"
        picks: list[str] = []
        pick_attrs: dict[str, Any] = {}
        edge, owner = None, ""
        for attempt in range(1, _FROZEN_REDRAW_RETRIES + 2):
            observed: dict[str, Any] = {}
            captured: dict[str, Any] = {}
            started = time.perf_counter()
            edge, owner = _hit_test_edge(
                adapter,
                sheet_xy,
                redraw=attempt > 1,
                observed=observed,
                on_miss=lambda pick=attempt, into=captured: into.update(
                    _seat_forensics.capture_pick_screens(
                        adapter, f"{stem}-frozen-anchor-pick{pick}", sheet_xy=sheet_xy
                    )
                ),
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000.0)
            outcome = (
                "miss"
                if edge is None
                else "hit"
                if owner.casefold() == instance.casefold()
                else "other"
            )
            picks.append(outcome)
            pick_attrs[f"pick{attempt}"] = outcome
            # The pick's own time, without the screenshots taken at its miss.
            pick_attrs[f"pick{attempt}_ms"] = elapsed_ms - int(
                captured.get("capture_ms", 0)
            )
            if observed["zoom_scale2"] is not None:
                pick_attrs[f"pick{attempt}_scale2"] = observed["zoom_scale2"]
            pick_attrs.update(
                {f"pick{attempt}_{kind}": value for kind, value in captured.items()}
            )
            if edge is not None:
                break
        tried.append(sheet_xy)
        pick_attrs.update(_seat_forensics.drawing_pick_state(adapter, view))
        _span_scan_attrs(**pick_attrs)
        if edge is None:
            _seat_forensics.capture_pick_miss(
                adapter,
                f"{label}: {stem} frozen balloon anchor {anchor.point_mm} selects "
                f"no edge at {where} on {instance} in {len(picks)} picks, "
                f"{len(picks) - 1} after a forced redraw",
                view=view_name(adapter, view),
                entity_type="EDGE",
                sheet_xy=sheet_xy,
                state=pick_attrs,
            )
        if owner.casefold() != instance.casefold():
            adapter.currentModel.ClearSelection2(True)
            raise RuntimeError(
                f"{label}: {stem} frozen balloon anchor {anchor.point_mm} at {where} "
                f"selects an edge of {owner or 'no component'}, not {instance}"
            )
        method, point_mm = "frozen", tuple(anchor.point_mm)
        scan_attrs = {"picks": ",".join(picks)}
    else:
        walk_points = _walk_points(adapter, first)
        scan_attrs = {"extremes": len(walk_points)}
        claimed, _ = _scan_points(
            adapter,
            view,
            first,
            walk_points,
            offsets,
            tried,
            stem=stem,
            what="walk",
            label=label,
        )
        if claimed is not None:
            method, point, sheet_xy, edge = (
                "walk",
                walk_points[claimed.index],
                claimed.xy,
                claimed.edge,
            )
        else:
            adapter.currentModel.ClearSelection2(True)
            listed, edge_points = _visible_edge_points(adapter, view, first)
            scan_attrs["visible"] = f"{first.path}={listed}"
            claimed, shared = _scan_points(
                adapter,
                view,
                first,
                [point for point, _edge in edge_points],
                offsets,
                tried,
                stem=stem,
                what="edge",
                label=label,
            )
            if claimed is not None:
                method, edge = "visible-edge", claimed.edge
                point, sheet_xy = edge_points[claimed.index][0], claimed.xy
            elif shared is not None:
                method, (point, edge), sheet_xy = (
                    "shared-edge",
                    edge_points[shared.index],
                    shared.xy,
                )
                scan_attrs["shared"] = shared.owner or "no component"
            elif edge_points:
                method, (point, edge) = "listed-edge", edge_points[0]
                sheet_xy = tried[len(walk_points)]
            else:
                adapter.currentModel.ClearSelection2(True)
                points_text = "; ".join(
                    f"({x * 1000.0:.2f}, {y * 1000.0:.2f})" for x, y in tried
                )
                raise RuntimeError(
                    f"{label}: {stem} has no verifiably visible edge: no hit test "
                    f"found ink of {first.path} at sheet mm [{points_text}]: "
                    f"{len(walk_points)} body extreme points, then "
                    f"{len(edge_points)} points along its {listed} listed visible "
                    f"edges (sampled when 1-{_VISIBLE_EDGES_PER_INSTANCE})"
                )
        point_mm = tuple(value * 1000.0 for value in point)
    # The span carries what profiling queries group by; the event is what a
    # run-to-run anchor diff compares (App Insights traces, this name).
    _span_scan_attrs(instance=instance, method=method, tried=len(tried), **scan_attrs)
    _telemetry.event(
        "drawing.balloon_anchor",
        stem=stem,
        instance=instance,
        method=method,
        point_mm=_mm_text(point_mm),
        sheet_mm=_mm_text(sheet_xy, 1000.0),
        tried=len(tried),
        **scan_attrs,
    )
    adapter.currentModel.ClearSelection2(True)
    return _AnchorChoice(instance=instance, edge=edge, method=method, sheet_xy=sheet_xy)


def _verify_anchor_attachment(
    adapter: Any, note: Any, *, instance: str, stem: str, label: str
) -> None:
    """The inserted balloon must attach to exactly one edge, of the exact
    instance that was selected (full path, not its last segment)."""
    annotation = _early_bound(
        _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
    )
    entities = tuple(annotation.GetAttachedEntities3() or ())
    kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
    owners = [_entity_owner(adapter, entity) for entity in entities]
    if (
        len(entities) != 1
        or kinds != (_SEL_EDGES,)
        or owners[0].casefold() != instance.casefold()
    ):
        raise RuntimeError(
            f"{label}: {stem} balloon must attach to one edge of {instance}; it "
            f"attaches to {len(entities)} entities of types {list(kinds)} owned by "
            f"{owners}"
        )


@dataclass(frozen=True)
class BalloonLanding:
    """One checked component balloon, attached to one edge of ``instance``.

    Its leader ends at ``sheet_xy`` when a manual point was proven; ``None``
    leaves the native or listed-edge attachment position to SolidWorks.
    """

    stem: str
    instance: str
    note: Any
    sheet_xy: tuple[float, float] | None
    label: str


def _prove_landing(adapter: Any, landing: BalloonLanding) -> None:
    """``landing``'s balloon attaches to one edge of its instance and, when
    its landing was proven, its leader still ends there."""
    _verify_anchor_attachment(
        adapter,
        landing.note,
        instance=landing.instance,
        stem=landing.stem,
        label=landing.label,
    )
    if landing.sheet_xy is not None:
        _assert_leader_lands(
            _early_bound(
                _early_bound(landing.note, "INote").GetAnnotation(), "IAnnotation"
            ),
            landing.sheet_xy,
            what=f"{landing.stem} balloon",
            label=landing.label,
            tolerance=_BALLOON_LANDING_TOLERANCE_M,
        )


def assert_balloon_landings(adapter: Any, landings: Sequence[BalloonLanding]) -> None:
    """Prove every balloon's attachment and landing again, all at once.

    The proof at insertion holds only until the next rebuild: each
    ``EditRebuild3`` re-solves every annotation on every sheet, and later
    sheets, notes and the finalizer rebuild after a sheet's balloons are
    checked. Run after the drawing's last rebuild (``finalize_drawing``'s
    ``settled_checks``), this is the state the export prints. Every failing
    balloon is named, not just the first.
    """
    failures = []
    for landing in landings:
        try:
            _prove_landing(adapter, landing)
        except RuntimeError as error:
            failures.append(str(error))
    if failures:
        raise RuntimeError(
            f"{len(failures)} balloon(s) changed after the final rebuild: "
            + "; ".join(failures)
        )


def _create_component_bom_balloon(
    adapter: Any,
    view: Any,
    *,
    stem: str,
    choice: _AnchorChoice,
    expected_item: str,
    label: str,
) -> BalloonLanding:
    """Attach one BOM balloon to ``stem``'s anchor edge and prove where it landed.

    The edge is selected by entity and the hit-tested sheet point made its
    selection point (``ISelectionMgr.SetSelectionPoint2``), the landing
    :func:`add_surface_finish` measured to 0.01 mm; without it SolidWorks
    ends the leader at its own point on the edge (:class:`_AnchorChoice`).
    A ``shared-edge`` or ``listed-edge`` edge is the model edge the view
    listed, not a hit test's pick, so it is selected through the view. The
    leader must then read back there; a ``listed-edge`` leader has no
    proven point to land on, so SolidWorks places it.
    """
    draw = adapter.currentModel
    listed = choice.method in ("shared-edge", "listed-edge")
    if listed:
        draw.ClearSelection2(True)
        if not _early_bound(view, "IView").SelectEntity(choice.edge, False):
            raise RuntimeError(
                f"{label}: failed to select {stem}'s listed visible edge"
            )
    else:
        _select_view_entity(
            adapter,
            view,
            "EDGE",
            None,
            label=f"{label} {stem} anchor",
            entity=choice.edge,
        )
    proven = choice.method != "listed-edge"
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    if (
        proven
        and manager.SetSelectionPoint2(
            1, -1, choice.sheet_xy[0], choice.sheet_xy[1], 0.0
        )
        is not True
    ):
        raise RuntimeError(
            f"{label}: failed to set {stem}'s balloon landing {choice.sheet_xy}"
        )
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    options = extension.CreateBalloonOptions()
    if options is None:
        raise RuntimeError(f"{label}: failed to create {stem} balloon options")
    options = _sw_type_info.early_bound_or_flag(options, "IBalloonOptions")
    options.Style = 1
    options.Size = 2
    options.UpperTextContent = 1
    options.ShowQuantity = False
    options.ItemNumberStart = 1
    options.ItemNumberIncrement = 1
    options.ItemOrder = 1
    note = extension.InsertBOMBalloon2(options)
    draw.ClearSelection2(True)
    if note is None:
        raise RuntimeError(f"{label}: failed to insert {stem} balloon")
    item = _balloon_item_number(adapter, note, label=label)
    if item != expected_item:
        raise RuntimeError(
            f"{label}: {stem} resolved item {item}, expected {expected_item}"
        )
    landing = BalloonLanding(
        stem=stem,
        instance=choice.instance,
        note=note,
        sheet_xy=choice.sheet_xy if proven else None,
        label=label,
    )
    _prove_landing(adapter, landing)
    return landing


@_telemetry.traced("drawing.component_bom_balloons", label_param="label")
def add_component_bom_balloons(
    adapter: Any,
    view: Any,
    *,
    items: Sequence[tuple[str, str]],
    anchors: Mapping[str, BalloonAnchor],
    label: str,
    margin: float = 0.014,
) -> list[BalloonLanding]:
    """Insert and ring one checked balloon per requested component family.

    Each family's balloon attaches at its anchor in ``anchors``
    (:func:`_select_balloon_anchor`). Every family's instance is chosen and
    every frozen anchor projected in one batch before the first balloon
    exists, so a family without an anchor or a shown instance fails the
    sheet naming it, with nothing half-placed. Returns each balloon's
    :class:`BalloonLanding`, for :func:`assert_balloon_landings` to prove
    again after the drawing's last rebuild.
    """
    if not items:
        raise ValueError(f"{label}: component balloon list must not be empty")
    stems = [stem for stem, _item in items]
    numbers = [item for _stem, item in items]
    if len(stems) != len(set(stems)) or len(numbers) != len(set(numbers)):
        raise ValueError(f"{label}: duplicate component or item number")
    if margin <= 0.0:
        raise ValueError(f"{label}: balloon ring margin must be positive")
    missing = [stem for stem in stems if stem not in anchors]
    if missing:
        raise ValueError(f"{label}: no balloon anchor for {missing}")
    leaves = _view_component_leaves(adapter, view, label=label)
    candidates = {
        stem: _shown_instances(leaves, stem, anchors[stem], label=label)
        for stem in stems
    }
    offsets = _view_explode_offsets(adapter, view, label=label)
    frozen = [stem for stem in stems if anchors[stem].point_mm is not None]
    projected = (
        model_points_in_view(
            adapter,
            view,
            [
                _anchor_model_points(
                    adapter,
                    candidates[stem][0],
                    [tuple(value / 1000.0 for value in anchors[stem].point_mm or ())],
                    offsets,
                    stem=stem,
                    label=label,
                )[0]
                for stem in frozen
            ],
            label=f"{label} balloon anchors",
            names=frozen,
        )
        if frozen
        else []
    )
    sheet_points: dict[str, tuple[float, float]] = dict(zip(frozen, projected))
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate the balloon view")
    # A coordinate hit test reads the view's display geometry: make it current once.
    _early_bound(view, "IView").UpdateViewDisplayGeometry()
    # Every anchor is hit-tested before the first balloon exists: a balloon
    # dropped near its own anchor would otherwise sit on the next family's
    # point and swallow its hit test.
    picks = [
        _select_balloon_anchor(
            adapter,
            view,
            stem=stem,
            anchor=anchors[stem],
            candidates=candidates[stem],
            offsets=offsets,
            sheet_xy=sheet_points.get(stem),
            label=label,
        )
        for stem in stems
    ]
    landings = [
        _create_component_bom_balloon(
            adapter,
            view,
            stem=stem,
            choice=choice,
            expected_item=item,
            label=label,
        )
        for (stem, item), choice in zip(items, picks)
    ]
    _spread_balloons(
        adapter, view, [landing.note for landing in landings], margin=margin
    )
    rebuild_drawing(adapter, label="add_component_bom_balloons")
    _telemetry.success(f"{label}: inserted {len(landings)} targeted balloons")
    return landings


@_telemetry.traced("drawing.auto_balloons_across_views", label_param="label")
def add_auto_balloons_across_views(
    adapter: Any,
    views: Sequence[Any],
    *,
    expected: int,
    label: str,
    existing_balloons: Sequence[Any] = (),
    margin: float = 0.014,
    layout: int = 1,
) -> list[Any]:
    """Balloon successive views until every BOM item number is represented.

    Dense assemblies can hide whole component families in one pictorial view.
    AutoBalloon5 only balloons items visible in the selected view, so run it on
    each orthographic and pictorial view, preserve every placed balloon, and
    validate the union of displayed BOM item numbers against the table's full
    contiguous item range. Each view's balloons are spread around that view.
    """
    if margin <= 0.0:
        raise ValueError(f"{label}: balloon ring margin must be positive")
    all_balloons = list(existing_balloons)
    item_numbers = {
        _balloon_item_number(adapter, note, label=f"{label} existing")
        for note in existing_balloons
    }
    for index, view in enumerate(views, start=1):
        view_label = f"{label} view {index}"
        balloons = _create_auto_balloons(
            adapter, view, label=view_label, allow_empty=True, layout=layout
        )
        if not balloons:
            continue
        _spread_balloons(adapter, view, balloons, margin=margin)
        for note in balloons:
            item_numbers.add(_balloon_item_number(adapter, note, label=view_label))
        all_balloons.extend(balloons)
    expected_numbers = {str(item) for item in range(1, expected + 1)}
    missing = sorted(expected_numbers - item_numbers, key=int)
    unexpected = sorted(item_numbers - expected_numbers)
    if missing or unexpected:
        raise RuntimeError(
            f"{label}: balloon item coverage mismatch; missing={missing}, "
            f"unexpected={unexpected}, seen={sorted(item_numbers)}"
        )
    rebuild_drawing(adapter, label="add_auto_balloons_across_views")
    _telemetry.success(
        f"{label}: {len(all_balloons)} balloons cover all {expected} BOM items"
    )
    return all_balloons


def drawing_viewport_pixel_size(adapter: Any) -> tuple[float, float]:
    """Return one current viewport pixel in drawing-sheet X/Y metres."""
    view = _early_bound(adapter.currentModel.ActiveView, "IModelView")
    transform = _early_bound(view.Transform, "IMathTransform")
    data = tuple(float(value) for value in transform.ArrayData)
    if len(data) < 13 or not all(math.isfinite(value) for value in data[:13]):
        raise RuntimeError("drawing viewport has no finite model-to-pixel transform")
    scale = abs(data[12])
    pixels_per_metre = (
        scale * math.hypot(data[0], data[1]),
        scale * math.hypot(data[3], data[4]),
    )
    if any(not math.isfinite(value) or value <= 0.0 for value in pixels_per_metre):
        raise RuntimeError("drawing viewport has a degenerate sheet-to-pixel mapping")
    return (1.0 / pixels_per_metre[0], 1.0 / pixels_per_metre[1])


@_telemetry.traced("drawing.position_bom_balloon", label_param="label")
def position_bom_balloon(
    adapter: Any,
    balloons: Sequence[Any],
    *,
    item_number: str,
    position_xy: tuple[float, float],
    label: str,
    position_tolerance_m: float = 1e-6,
) -> None:
    """Move the anchor strictly; ``position_tolerance_m`` floors one-pixel ink bounds."""
    if position_tolerance_m <= 0.0:
        raise ValueError("balloon position tolerance must be positive")
    matches = [
        note
        for note in balloons
        if _balloon_item_number(adapter, note, label=label) == item_number
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one balloon for item {item_number}, got {len(matches)}"
        )
    note = _sw_type_info.early_bound_or_flag(
        matches[0],
        "INote",
        "GetAnnotation",
        "IsStackedBalloon",
        "IsStackedBalloonMaster",
    )
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label}: item {item_number} has no annotation")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation,
        "IAnnotation",
        "GetPosition",
        "GetSpecificAnnotation",
        "SetPosition",
    )
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = ddoc.GetCurrentSheet()
    magnetic_lines = int(adapter._get_attr_or_call(sheet, "GetMagneticLinesCount") or 0)
    _telemetry.info(
        f"{label}: item {item_number} placement diagnostics "
        f"stacked={bool(note.IsStackedBalloon())}, "
        f"stack_master={bool(note.IsStackedBalloonMaster())}, "
        f"magnetic_lines={magnetic_lines}"
    )
    circle = rendered_balloon_circle(note, label=label)
    anchor = annotation.GetPosition()
    if anchor is None or len(anchor) < 2:
        raise RuntimeError(f"{label}: item {item_number} has no position read-back")
    target_anchor = (
        float(anchor[0]) + position_xy[0] - circle[0],
        float(anchor[1]) + position_xy[1] - circle[1],
    )
    note.LockPosition = False
    if not annotation.SetPosition(target_anchor[0], target_anchor[1], 0.0):
        raise RuntimeError(f"{label}: failed to position item {item_number}")
    note.LockPosition = True
    rebuild_drawing(adapter, label="position_bom_balloon")
    adapter.currentModel.GraphicsRedraw2()
    current_note = annotation.GetSpecificAnnotation()
    if current_note is None:
        raise RuntimeError(
            f"{label}: item {item_number} note vanished after positioning"
        )
    actual_anchor = tuple(float(value) for value in annotation.GetPosition())
    actual_xy = rendered_balloon_circle(current_note, label=label)[:2]
    pixel_bounds = tuple(
        max(position_tolerance_m, value)
        for value in drawing_viewport_pixel_size(adapter)
    )
    residual = tuple(
        actual - expected for actual, expected in zip(actual_xy, position_xy)
    )
    state = {
        "requested_anchor": target_anchor,
        "actual_anchor": actual_anchor,
        "target_circle": position_xy,
        "actual_circle": actual_xy,
        "residual_xy": residual,
        "pixel_bounds_m": pixel_bounds,
    }
    _telemetry.info(f"{label}: item {item_number} pixel-bounded placement {state!r}")
    if (
        len(actual_anchor) < 2
        or not all(math.isfinite(value) for value in actual_anchor[:2])
        or any(
            abs(actual_anchor[index] - target_anchor[index]) > position_tolerance_m
            for index in range(2)
        )
    ):
        raise RuntimeError(
            f"{label}: item {item_number} native anchor did not persist: {state!r}"
        )
    if any(abs(residual[index]) > pixel_bounds[index] for index in range(2)):
        raise RuntimeError(
            f"{label}: item {item_number} rendered circle exceeds viewport resolution: {state!r}"
        )
