"""Apply measured, translation-only layouts to the active native drawing sheet.

Run native dimension/GTol arrangement before this helper. ``measure_annotation``
is the native ``annotation_box(adapter, annotation)`` callback: it must expose
envelope, name, kind, text_runs and format_signature. Unsupported annotations
must raise; this module never substitutes nominal symbol sizes or drops them.

Pass every drawing view explicitly. Projection alignment/order and free-note
associations are recipe metadata, never inferred from nearby XY coordinates.
For example, with actual IView handles in ``views``::

    repair_native_layout(
        adapter, views=views, parents={"top": "front", "right": "front"},
        alignments=(AxisLink(Axis.X, "front", "top"),
                    AxisLink(Axis.Y, "front", "right")),
        orderings=(AxisOrder(Axis.Y, "front", "top"),
                   AxisOrder(Axis.X, "front", "right")),
        notes=(LayoutNote("manufacturing", manufacturing_annotation),
               LayoutNote("iso-caption", caption_annotation, follows_view="iso")),
        title_block=project_template_title_block,
        measure_annotation=annotation_box,
    )

The caller supplies the title-block rectangle from the existing project template
contract. Sheet zone margins are read natively. Template-owned annotations are
excluded explicitly; their title block is reserved by that contract. Other sheet
notes/tables are measured fixed obstacles unless a free note is explicitly listed.
This first integration accepts drawing-view/sheet ownership only. Source-part or
assembly-owned imported PMI is explicitly unsupported, not reassigned by name.

Each view's packing rectangle is the union envelope of its measured outline and
annotations, including explicitly associated captions. These conservative boxes
can reject a layout which a finer shape solver might fit. NO_FIT and SEARCH_LIMIT
make no changes and never shrink fonts, change view scale, or remove content.
This first version does not repair collisions internal to one decorated view.

Absolute targets come from the ORIGINAL snapshot. Native parent movement can
propagate to children; parents are applied first, children then receive their
absolute target, not a second relative delta. Every position and scale is read
back after one rebuild, and annotation identity/count/type/context, text/format
signatures, fixed obstacles, and measured fit are rechecked. Failure raises and
leaves the unsaved drawing for the caller to discard; no save or rollback occurs.
Immutable model-geometry identity across save/reopen remains the attachment
probe's independent gate. Conservative font cells are not tight rendered ink.
Null attachment handles fail; a native control exposing zero attachments is
reported as a geometry-identity exclusion rather than a successful entity check.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Callable, Mapping, Sequence

from _common import _early_bound
from _drawing_view_packing import (
    Axis,
    AxisAlignment,
    AxisOrder,
    PackingResult,
    PackingStatus,
    Rect,
    RigidViewGroup,
    pack_view_groups,
)
import _telemetry


@dataclass(frozen=True)
class AxisLink:
    axis: Axis
    first_view: str
    second_view: str


@dataclass(frozen=True)
class LayoutNote:
    key: str
    annotation: Any
    follows_view: str | None = None


class NativeLayoutStatus(Enum):
    UNCHANGED = "unchanged"
    APPLIED = "applied"
    NO_FIT = "no_fit"
    SEARCH_LIMIT = "search_limit"


@dataclass(frozen=True)
class NativeLayoutReport:
    status: NativeLayoutStatus
    translations: Mapping[str, tuple[float, float]]
    before_outlines: Mapping[str, Rect]
    after_outlines: Mapping[str, Rect]
    explored_nodes: int
    reason: str
    drawable: Rect
    before_bounds: Mapping[str, Rect]
    after_bounds: Mapping[str, Rect]
    fixed_bounds: Mapping[str, Rect]
    attachment_identity_exclusions: Mapping[str, str]


@dataclass(frozen=True)
class _Snapshot:
    positions: Mapping[str, tuple[float, ...]]
    scales: Mapping[str, tuple[float, ...]]
    references: Mapping[str, tuple[str, str]]
    outlines: Mapping[str, Rect]
    groups: Sequence[RigidViewGroup]
    obstacles: Mapping[tuple[str, str, int], Rect]
    signatures: Mapping[tuple[str, str, int], tuple[Any, ...]]
    annotations: Mapping[tuple[str, str, int], Any]
    attached_entities: Mapping[tuple[str, str, int], tuple[Any, ...]]
    note_positions: Mapping[str, tuple[float, ...]]
    drawable: Rect
    sheet_properties: tuple[float, ...]


def _values(raw: Any, count: int, label: str) -> tuple[float, ...]:
    values = tuple(float(value) for value in raw or ())
    if len(values) != count or not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"{label} requires {count} finite native values: {values}")
    return values


def _union(rectangles: Sequence[Rect]) -> Rect:
    return Rect(
        min(r.xmin for r in rectangles),
        min(r.ymin for r in rectangles),
        max(r.xmax for r in rectangles),
        max(r.ymax for r in rectangles),
    )


def _view_names(views: Mapping[str, Any]) -> dict[str, str]:
    if not views or any(not key.strip() for key in views):
        raise ValueError("native layout requires named views")
    names = {key: str(view.GetName2() or "") for key, view in views.items()}
    if any(not name for name in names.values()) or len(set(names.values())) != len(
        names
    ):
        raise ValueError("native layout view names must be nonempty and unique")
    return names


def _parent_order(
    views: Mapping[str, Any], parents: Mapping[str, str]
) -> tuple[str, ...]:
    names = _view_names(views)
    by_name = {name: key for key, name in names.items()}
    for child, parent in parents.items():
        if child not in views or parent not in views:
            raise ValueError("native layout parent relation refers to an unknown view")
    for key, view in views.items():
        base = view.GetBaseView()
        if base is None:
            continue
        base_name = str(_early_bound(base, "IView").GetName2())
        if base_name not in by_name or parents.get(key) != by_name[base_name]:
            raise ValueError(
                f"{key}: declare its native base view {base_name!r} in parents"
            )
    ordered: list[str] = []
    active: set[str] = set()

    def visit(key: str) -> None:
        if key in ordered:
            return
        if key in active:
            raise ValueError("native layout parent relations contain a cycle")
        active.add(key)
        if key in parents:
            visit(parents[key])
        active.remove(key)
        ordered.append(key)

    for key in sorted(views):
        visit(key)
    return tuple(ordered)


def _annotation_key(
    adapter: Any, annotation: Any, names: Mapping[str, str], views: Mapping[str, Any]
) -> tuple[str, str, int]:
    owner_type = int(annotation.OwnerType)
    owner = "sheet"
    if owner_type == 0:  # swAnnotationOwner_DrawingView
        native_owner = _early_bound(annotation.Owner, "IView")
        owner_name = str(native_owner.GetName2())
        if owner_name not in names:
            raise RuntimeError(
                f"annotation owner {owner_name!r} is not in the view plan"
            )
        if int(adapter.swApp.IsSame(native_owner, views[names[owner_name]])) != 1:
            raise RuntimeError(
                f"annotation owner {owner_name!r} is not the planned native view object"
            )
        owner = f"view:{names[owner_name]}"
    elif owner_type != 1:  # swAnnotationOwner_DrawingSheet
        raise RuntimeError(
            f"unexpected manufacturing annotation owner type {owner_type}"
        )
    name, kind = str(annotation.GetName() or ""), int(annotation.GetType())
    if not name:
        raise RuntimeError("native layout annotation has no identity name")
    return owner, name, kind


def _snapshot(
    adapter: Any,
    views: Mapping[str, Any],
    notes: Sequence[LayoutNote],
    measure_annotation: Callable[[Any, Any], Any],
) -> _Snapshot:
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = _values(sheet.GetProperties2(), 8, "sheet properties")
    width, height = properties[5:7]
    margins = _values(
        [sheet.GetZoneMargin(i) for i in range(4)], 4, "sheet zone margins"
    )
    if width <= 0 or height <= 0 or any(value < 0 for value in margins):
        raise RuntimeError("native sheet size/margins are invalid")
    top, bottom, right, left = margins  # swZoneMargin_e
    drawable = Rect(left, bottom, width - right, height - top)
    names = _view_names(views)
    by_name = {name: key for key, name in names.items()}
    sheet_view = _early_bound(drawing.GetFirstView(), "IView")
    inventory = [sheet_view]
    current = sheet_view.GetNextView()
    found: list[str] = []
    while current is not None:
        current = _early_bound(current, "IView")
        name = str(current.GetName2())
        if name in found:
            raise RuntimeError("native sheet view inventory repeats a view")
        if (
            name in by_name
            and int(adapter.swApp.IsSame(current, views[by_name[name]])) != 1
        ):
            raise RuntimeError(
                f"{name}: planned view is not the active sheet's native view"
            )
        found.append(name)
        inventory.append(current)
        current = current.GetNextView()
    if Counter(found) != Counter(names.values()):
        raise RuntimeError(
            f"native sheet view inventory differs from plan: {found}, {names}"
        )
    positions, scales, references, outlines = {}, {}, {}, {}
    rectangles = {}
    for key, view in views.items():
        positions[key] = _values(view.Position, 2, f"{key} position")
        scales[key] = _values(view.ScaleRatio, 2, f"{key} scale")
        if min(scales[key]) <= 0:
            raise RuntimeError(f"{key} native view scale is invalid")
        reference = (
            str(view.GetReferencedModelName() or ""),
            str(view.ReferencedConfiguration or ""),
        )
        if not all(reference):
            raise RuntimeError(f"{key} native model/configuration reference is missing")
        references[key] = reference
        outlines[key] = Rect(*_values(view.GetOutline(), 4, f"{key} outline"))
        rectangles[f"view:{key}"] = [outlines[key]]
    note_by_annotation = {}
    for note in notes:
        key = _annotation_key(adapter, note.annotation, by_name, views)
        if key[2] != 6 or int(note.annotation.GetAttachedEntityCount3()) != 0:
            raise ValueError(
                f"{note.key}: movable layout notes must be unattached notes"
            )
        if key in note_by_annotation:
            raise ValueError("native layout note is declared more than once")
        note_by_annotation[key] = note
    seen, signatures, entities, obstacles, note_positions = {}, {}, {}, {}, {}
    for native_view in inventory:
        for raw in native_view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.OwnerType) == 2:  # Explicit template baseline exclusion.
                continue
            key = _annotation_key(adapter, annotation, by_name, views)
            if key in seen:
                if int(adapter.swApp.IsSame(seen[key], annotation)) != 1:
                    raise RuntimeError(
                        f"native annotation identity is ambiguous: {key}"
                    )
                continue
            seen[key] = annotation
            measured = measure_annotation(adapter, annotation)
            if (measured.name, measured.kind) != key[1:]:
                raise RuntimeError(f"annotation measurement identity mismatch: {key}")
            count = int(annotation.GetAttachedEntityCount3())
            types = tuple(
                int(value) for value in annotation.GetAttachedEntityTypes() or ()
            )
            attached = tuple(annotation.GetAttachedEntities3() or ())
            if count < 0 or len(types) != count or len(attached) != count:
                raise RuntimeError(
                    f"annotation attachment inventory is incomplete: {key}"
                )
            if any(entity is None for entity in attached):
                raise RuntimeError(
                    f"annotation attachment identity has a null native handle: {key}"
                )
            entities[key] = attached
            text = tuple(
                (
                    run.value,
                    run.height_m,
                    run.font,
                    run.angle_rad,
                    run.reference,
                    run.inverted,
                )
                for run in measured.text_runs
            )
            signatures[key] = (
                count,
                types,
                int(annotation.OwnerType),
                int(annotation.Visible),
                tuple(measured.format_signature),
                text,
            )
            note = note_by_annotation.get(key)
            if note is not None:
                if int(adapter.swApp.IsSame(note.annotation, annotation)) != 1:
                    raise RuntimeError(
                        f"{note.key}: declared note is not the native inventory object"
                    )
                note_positions[note.key] = _values(
                    annotation.GetPosition(), 3, f"{note.key} note position"
                )
                group = (
                    f"view:{note.follows_view}"
                    if note.follows_view is not None
                    else f"note:{note.key}"
                )
                rectangles.setdefault(group, []).append(measured.envelope)
                continue
            if (
                key[0] == "sheet" or key[2] == 14
            ):  # Free sheet content and tables stay fixed.
                obstacles[key] = measured.envelope
                continue
            rectangles[key[0]].append(measured.envelope)
    if set(note_positions) != {note.key for note in notes}:
        raise RuntimeError(
            "declared layout notes are missing from the native sheet inventory"
        )
    groups = tuple(
        RigidViewGroup(key, {key: _union(bounds)})
        for key, bounds in sorted(rectangles.items())
    )
    return _Snapshot(
        positions,
        scales,
        references,
        outlines,
        groups,
        obstacles,
        signatures,
        seen,
        entities,
        note_positions,
        drawable,
        properties,
    )


def _relations(
    snapshot: _Snapshot, links: Sequence[AxisLink], orderings: Sequence[AxisOrder]
):
    alignments = tuple(
        AxisAlignment(
            link.axis,
            f"view:{link.first_view}",
            f"view:{link.second_view}",
            snapshot.positions[link.first_view][link.axis.value],
            snapshot.positions[link.second_view][link.axis.value],
        )
        for link in links
    )
    orders = tuple(
        AxisOrder(order.axis, f"view:{order.before_group}", f"view:{order.after_group}")
        for order in orderings
    )
    return alignments, orders


def _report(
    status: NativeLayoutStatus,
    result: PackingResult,
    before: _Snapshot,
    after: _Snapshot | None,
    title_block: Rect,
    reason: str,
) -> NativeLayoutReport:
    return NativeLayoutReport(
        status=status,
        translations=result.translations,
        before_outlines=before.outlines,
        after_outlines={} if after is None else after.outlines,
        explored_nodes=result.explored_nodes,
        reason=reason,
        drawable=before.drawable,
        before_bounds={
            group.name: next(iter(group.rectangles.values())) for group in before.groups
        },
        after_bounds={}
        if after is None
        else {
            group.name: next(iter(group.rectangles.values())) for group in after.groups
        },
        fixed_bounds={
            "title-block": title_block,
            **{str(key): value for key, value in before.obstacles.items()},
        },
        attachment_identity_exclusions={
            str(
                key
            ): "native annotation exposes no attached entities; geometry identity not checked"
            for key, entities in before.attached_entities.items()
            if not entities and key[2] in {2, 4, 5, 7}
        },
    )


def _fixed_content_issue(
    snapshot: _Snapshot, title_block: Rect, gap_m: float
) -> str | None:
    if not snapshot.obstacles:
        return None
    # A single rigid group detects fixed-vs-fixed overlap as well as overflow.
    # Its placement may not change, so only the initial zero-move result passes.
    fixed = RigidViewGroup(
        "fixed", {str(key): value for key, value in snapshot.obstacles.items()}
    )
    result = pack_view_groups(
        (fixed,), snapshot.drawable, (title_block,), gap_m=gap_m, max_search_nodes=1
    )
    if result.status is PackingStatus.PACKED and result.explored_nodes == 0:
        return None
    return "fixed sheet content does not fit; explicitly declare movable notes or change the sheet plan"


@_telemetry.traced("drawing.native_layout")
def repair_native_layout(
    adapter: Any,
    *,
    views: Mapping[str, Any],
    title_block: Rect,
    measure_annotation: Callable[[Any, Any], Any],
    parents: Mapping[str, str] | None = None,
    alignments: Sequence[AxisLink] = (),
    orderings: Sequence[AxisOrder] = (),
    notes: Sequence[LayoutNote] = (),
    gap_m: float = 0.002,
    max_search_nodes: int = 10_000,
    position_tolerance_m: float = 1e-8,
) -> NativeLayoutReport:
    """Repair one fully declared sheet, or return an explicit no-write packing result."""
    if int(adapter.currentModel.GetType()) != 3:
        raise ValueError("native layout requires an active drawing")
    if not math.isfinite(position_tolerance_m) or position_tolerance_m <= 0:
        raise ValueError("native layout position tolerance must be positive and finite")
    views = {key: _early_bound(view, "IView") for key, view in views.items()}
    notes = tuple(
        LayoutNote(
            note.key, _early_bound(note.annotation, "IAnnotation"), note.follows_view
        )
        for note in notes
    )
    if len({note.key for note in notes}) != len(notes) or any(
        not note.key.strip() for note in notes
    ):
        raise ValueError("native layout notes require unique nonempty keys")
    if any(
        note.follows_view is not None and note.follows_view not in views
        for note in notes
    ):
        raise ValueError("native layout note follows an unknown view")
    for link in alignments:
        if (
            not isinstance(link.axis, Axis)
            or link.first_view not in views
            or link.second_view not in views
        ):
            raise ValueError("native layout alignment refers to an invalid axis/view")
    for order in orderings:
        if (
            not isinstance(order.axis, Axis)
            or order.before_group not in views
            or order.after_group not in views
        ):
            raise ValueError("native layout ordering refers to an invalid axis/view")
    order = _parent_order(views, parents or {})
    with _telemetry.span("drawing.native_layout.measure"):
        before = _snapshot(adapter, views, notes, measure_annotation)
    fixed_issue = _fixed_content_issue(before, title_block, gap_m)
    if fixed_issue is not None:
        failure = PackingResult(PackingStatus.DOES_NOT_FIT, {}, 0, fixed_issue)
        return _report(
            NativeLayoutStatus.NO_FIT, failure, before, None, title_block, fixed_issue
        )
    links, orders = _relations(before, alignments, orderings)
    result = pack_view_groups(
        before.groups,
        before.drawable,
        (title_block, *before.obstacles.values()),
        gap_m=gap_m,
        max_search_nodes=max_search_nodes,
        alignments=links,
        orderings=orders,
    )
    if result.status is not PackingStatus.PACKED:
        status = (
            NativeLayoutStatus.NO_FIT
            if result.status is PackingStatus.DOES_NOT_FIT
            else NativeLayoutStatus.SEARCH_LIMIT
        )
        return _report(status, result, before, None, title_block, result.reason)
    if not any(any(delta) for delta in result.translations.values()):
        return _report(
            NativeLayoutStatus.UNCHANGED,
            result,
            before,
            before,
            title_block,
            "measured sheet already fits",
        )
    targets = {
        key: tuple(
            a + b
            for a, b in zip(before.positions[key], result.translations[f"view:{key}"])
        )
        for key in views
    }
    note_targets = {}
    with _telemetry.span("drawing.native_layout.apply"):
        for key in order:
            # Property assignment follows documented native aligned-child propagation.
            # Even a zero-delta child gets its absolute target after its parent moved.
            views[key].Position = targets[key]
        for note in notes:
            group = (
                f"view:{note.follows_view}"
                if note.follows_view is not None
                else f"note:{note.key}"
            )
            dx, dy = result.translations[group]
            x, y, z = before.note_positions[note.key]
            target = (x + dx, y + dy, z)
            note_targets[note.key] = target
            if not note.annotation.SetPosition2(*target):
                raise RuntimeError(
                    f"{note.key}: native free-note movement was rejected"
                )
        if not adapter.currentModel.EditRebuild3():
            raise RuntimeError("native layout rebuild failed")
    with _telemetry.span("drawing.native_layout.readback"):
        after = _snapshot(adapter, views, notes, measure_annotation)
    for key, target in targets.items():
        if math.dist(target, after.positions[key]) > position_tolerance_m:
            raise RuntimeError(
                f"{key}: native view did not reach absolute layout target"
            )
    for key, target in note_targets.items():
        if math.dist(target, after.note_positions[key]) > position_tolerance_m:
            raise RuntimeError(
                f"{key}: native note did not reach absolute layout target"
            )
    if (
        before.scales != after.scales
        or before.references != after.references
        or before.sheet_properties != after.sheet_properties
    ):
        raise RuntimeError(
            "native layout changed view scale, model/configuration reference or sheet properties"
        )
    if before.signatures != after.signatures:
        raise RuntimeError(
            "native layout changed annotation inventory, attachments, text, or format"
        )
    for key, annotation in before.annotations.items():
        if int(adapter.swApp.IsSame(annotation, after.annotations[key])) != 1:
            raise RuntimeError(f"native layout replaced annotation identity: {key}")
        for original, observed in zip(
            before.attached_entities[key], after.attached_entities[key], strict=True
        ):
            if int(adapter.swApp.IsSame(original, observed)) != 1:
                raise RuntimeError(
                    f"native layout changed exact attachment identity: {key}"
                )
    if before.obstacles != after.obstacles or before.drawable != after.drawable:
        raise RuntimeError("native layout moved fixed sheet content or zone boundaries")
    links, orders = _relations(after, alignments, orderings)
    validation = pack_view_groups(
        after.groups,
        after.drawable,
        (title_block, *after.obstacles.values()),
        gap_m=gap_m,
        max_search_nodes=1,
        alignments=links,
        orderings=orders,
    )
    if validation.status is not PackingStatus.PACKED or validation.explored_nodes != 0:
        raise RuntimeError(
            f"remeasured native layout does not fit: {validation.reason}"
        )
    return _report(
        NativeLayoutStatus.APPLIED,
        result,
        before,
        after,
        title_block,
        "native positions and measured layout verified",
    )
