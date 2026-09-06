"""Apply measured, translation-only layouts to the active native drawing sheet.

Run native dimension/GTol arrangement before this helper. ``measure_annotation``
is the native ``annotation_box(adapter, annotation)`` callback: it must expose
envelope, name, kind, text_runs and format_signature. Unsupported annotations
must raise; this module never substitutes nominal symbol sizes or drops them.
The unsupported-entity centerline witness additionally requires native_strokes
(each stroke's measured start, end and width_m), without another COM pass.
An optional initial_measure_annotation callback may supply transaction-local
measurements for the first snapshot only. It owns freshness validation and must
raise if its witness changed. Final measurement always calls measure_annotation
afresh, including a no-movement plan; this module has no persistent bounds cache.
Final annotation validation consumes that same fresh snapshot after position,
identity and fit checks. It must not perform another native measurement pass.

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
Optional planning_headroom_m adds clearance and insets the planning rectangle
only. The final readback uses the original drawable and gap_m. The caller chooses
this conservative allowance; it is not a claimed bound on native extent error.

Absolute targets come from the ORIGINAL snapshot. Native parent movement can
propagate to children; parents are applied first, children then receive their
absolute target, not a second relative delta. Every position and scale is read
back after one rebuild, and annotation identity/count/type/context, text/format
signatures, fixed obstacles, and measured fit are rechecked. Failure raises and
leaves the unsaved drawing for the caller to discard; no save or rollback occurs.
Immutable model-geometry identity across save/reopen remains the attachment
probe's independent gate. Conservative font cells are not tight rendered ink.
Null attachment handles fail except the measured, non-dangling view-owned
centerline with one unsupported swSelNOTHING slot. Its native owner, annotation,
specific interface and full stroke translation are checked; underlying entity
identity is explicitly excluded. Zero attachments are also an identity exclusion.
Completed readbacks that fail position or fit validation persist their measured
evidence under cad/out/reports/native-layout. Raw residuals are unrounded sheet
metres, not a second acceptance policy; solver and position tolerances stay intact.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from itertools import combinations
import math
import json
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping, Sequence

from _common import CAD_ROOT, _early_bound
from solidworks_mcp.adapters.com_variant import double_array
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


_FAILURE_REPORT_ROOT = CAD_ROOT / "out" / "reports" / "native-layout"


class NativeLayoutReadbackError(RuntimeError):
    """Rejected measured layout, with JSON evidence even if persistence fails."""

    def __init__(self, reason: str, evidence: dict[str, Any]):
        self.evidence = evidence
        self.report_path: Path | None = None
        try:
            _FAILURE_REPORT_ROOT.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".json",
                prefix="readback-",
                dir=_FAILURE_REPORT_ROOT,
                delete=False,
            ) as report:
                json.dump(evidence, report, indent=2, allow_nan=False)
                self.report_path = Path(report.name)
        except OSError as error:
            # Failure to write diagnostic evidence must not hide the CAD failure.
            reason += f"; evidence persistence failed: {error}"
            _telemetry.error(reason, readback_evidence=json.dumps(evidence))
        if self.report_path is not None:
            reason += f"; readback evidence: {self.report_path}"
        super().__init__(reason)


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
    footprint_exclusions: Mapping[str, str]
    planning_headroom_m: float
    planning_gap_m: float
    validation_gap_m: float
    planning_drawable: Rect | None


@dataclass(frozen=True)
class _CenterlineWitness:
    specific: Any
    strokes: tuple[tuple[tuple[float, ...], tuple[float, ...], float], ...]


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
    annotation_bounds: Mapping[tuple[str, str, int], Rect]
    centerlines: Mapping[tuple[str, str, int], _CenterlineWitness]
    drawable: Rect
    sheet_properties: tuple[float, ...]
    measurements: Mapping[str, Mapping[str, Any]]


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


def _unsupported_centerline(adapter, annotation, key, measured, types, attached):
    # GetAttachedEntities3 documents NULL/swSelNOTHING for either dangling OR
    # unsupported entities. The probe_drawing_primitive_annotations.py control
    # observes this one-slot, non-dangling drawing centerline, never a generic
    # allowance for other kinds/owners or partially missing geometry handles.
    if (
        key[2] != 15
        or int(annotation.OwnerType) != 0
        or types != (0,)
        or len(attached) != 1
        or attached[0] is not None
    ):
        raise RuntimeError(
            f"annotation attachment identity has a null native handle: {key}"
        )
    if annotation.IsDangling():
        raise RuntimeError(f"native centerline is dangling: {key}")
    raw = annotation.GetSpecificAnnotation()
    if raw is None:
        raise RuntimeError(f"native centerline specific interface is missing: {key}")
    specific = _early_bound(raw, "ICenterLine")
    if int(adapter.swApp.IsSame(specific.GetAnnotation(), annotation)) != 1:
        raise RuntimeError(
            f"native centerline specific annotation identity differs: {key}"
        )
    strokes = []
    for stroke in measured.native_strokes:
        start = _values(stroke.start, 2, f"{key} centerline stroke start")
        end = _values(stroke.end, 2, f"{key} centerline stroke end")
        width = float(stroke.width_m)
        if start == end or not math.isfinite(width) or width <= 0:
            raise RuntimeError(f"native centerline stroke geometry is invalid: {key}")
        strokes.append((start, end, width))
    if not strokes:
        raise RuntimeError(f"native centerline has no measured stroke witness: {key}")
    return _CenterlineWitness(specific, tuple(strokes))


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
    annotation_bounds = {}
    measurements = {key: {} for key in views}
    centerlines = {}
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
            annotation_bounds[key] = measured.envelope
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
                centerlines[key] = _unsupported_centerline(
                    adapter, annotation, key, measured, types, attached
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
            if int(annotation.Visible) == 3:  # swAnnotationHidden, not Unknown=0.
                if note is not None:
                    raise ValueError(f"{note.key}: a declared layout note is hidden")
                # The saved-sheet control in probe_gtol_commands.py found an
                # individually hidden SF at the origin. Retain its native object,
                # attachment/text/visibility signatures, but it occupies no ink.
                continue
            # Retain the exact already-read object, including native leader
            # geometry/text cells, for a pure final validator. A sheet-owned
            # caption following a view belongs to that view's collision bank.
            measured_view = (
                note.follows_view
                if note is not None and note.follows_view is not None
                else key[0].removeprefix("view:")
                if key[0].startswith("view:")
                else None
            )
            if measured_view is not None:
                if key[1] in measurements[measured_view]:
                    raise RuntimeError(
                        "final view measurements require unique annotation names"
                    )
                measurements[measured_view][key[1]] = measured
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
        annotation_bounds,
        centerlines,
        drawable,
        properties,
        measurements,
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
    gap_m: float,
    planning_headroom_m: float,
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
            **{
                str(
                    key
                ): "native annotation exposes no attached entities; geometry identity not checked"
                for key, entities in before.attached_entities.items()
                if not entities and key[2] in {2, 4, 5, 7}
            },
            **{
                str(
                    key
                ): "non-dangling native centerline has unsupported swSelNOTHING entity; "
                "annotation/owner/specific identity and native stroke translation checked, "
                "underlying model-entity identity not checked"
                for key in before.centerlines
            },
        },
        footprint_exclusions={
            str(
                key
            ): "individually hidden (swAnnotationHidden=3); identity and visibility retained"
            for key, signature in before.signatures.items()
            if signature[3] == 3
        },
        planning_headroom_m=planning_headroom_m,
        planning_gap_m=gap_m + planning_headroom_m,
        validation_gap_m=gap_m,
        planning_drawable=_inset_drawable(before.drawable, planning_headroom_m),
    )


def _inset_drawable(drawable: Rect, headroom_m: float) -> Rect | None:
    if (
        min(drawable.xmax - drawable.xmin, drawable.ymax - drawable.ymin)
        <= 2 * headroom_m
    ):
        return None
    return Rect(
        drawable.xmin + headroom_m,
        drawable.ymin + headroom_m,
        drawable.xmax - headroom_m,
        drawable.ymax - headroom_m,
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


def _group_bounds(snapshot: _Snapshot) -> dict[str, Rect]:
    return {
        group.name: next(iter(group.rectangles.values())) for group in snapshot.groups
    }


def _raw_residuals(snapshot, title_block, gap_m, alignments, orderings):
    """Expose exact signed gaps; do not round or apply an acceptance tolerance."""
    groups = _group_bounds(snapshot)
    content = {**groups, **{str(k): v for k, v in snapshot.obstacles.items()}}
    overflow = []
    for name, rectangle in content.items():
        excesses = {
            "left": snapshot.drawable.xmin - rectangle.xmin,
            "bottom": snapshot.drawable.ymin - rectangle.ymin,
            "right": rectangle.xmax - snapshot.drawable.xmax,
            "top": rectangle.ymax - snapshot.drawable.ymax,
        }
        overflow.extend(
            {"item": name, "side": side, "excess_m": value}
            for side, value in excesses.items()
            if value > 0
        )
    pairs = []
    for (first, a), (second, b) in combinations(
        {**content, "title-block": title_block}.items(), 2
    ):
        gaps = {
            "first_left_of_second": b.xmin - a.xmax,
            "second_left_of_first": a.xmin - b.xmax,
            "first_below_second": b.ymin - a.ymax,
            "second_below_first": a.ymin - b.ymax,
        }
        deficit = gap_m - max(gaps.values())
        if deficit <= 0:
            continue
        overlap = [
            max(0.0, min(a.xmax, b.xmax) - max(a.xmin, b.xmin)),
            max(0.0, min(a.ymax, b.ymax) - max(a.ymin, b.ymin)),
        ]
        pairs.append(
            {
                "first": first,
                "second": second,
                "kind": "overlap" if min(overlap) > 0 else "clearance",
                "directional_gaps_m": gaps,
                "overlap_m": overlap,
                "clearance_deficit_m": deficit,
            }
        )
    aligned = [
        {
            "axis": link.axis.name,
            "first": link.first_view,
            "second": link.second_view,
            "first_minus_second_m": snapshot.positions[link.first_view][link.axis.value]
            - snapshot.positions[link.second_view][link.axis.value],
        }
        for link in alignments
    ]
    ordered = []
    for order in orderings:
        a, b = groups[f"view:{order.before_group}"], groups[f"view:{order.after_group}"]
        observed_gap = b.bounds[order.axis.value] - a.bounds[order.axis.value + 2]
        ordered.append(
            {
                "axis": order.axis.name,
                "before": order.before_group,
                "after": order.after_group,
                "gap_m": observed_gap,
                "deficit_m": max(0.0, gap_m - observed_gap),
            }
        )
    return {
        "overflow": overflow,
        "pairs": pairs,
        "alignments": aligned,
        "orderings": ordered,
    }


def _readback_evidence(
    reason,
    before,
    after,
    plan,
    validation,
    title_block,
    targets,
    note_targets,
    gap_m,
    position_tolerance_m,
    alignments,
    orderings,
    planning_headroom_m,
):
    def bounds(items):
        return {str(key): list(value.bounds) for key, value in items.items()}

    def packing(result):
        if result is None:
            return None
        return {
            "status": result.status.value,
            "reason": result.reason,
            "explored_nodes": result.explored_nodes,
            "translations": {
                key: list(value) for key, value in result.translations.items()
            },
        }

    def positions(original, requested, observed):
        return {
            key: {
                "before": list(original[key]),
                "requested": list(target),
                "observed": list(observed[key]),
                "observed_minus_requested_m": [
                    a - b for a, b in zip(observed[key], target)
                ],
                "error_m": math.dist(observed[key], target),
            }
            for key, target in requested.items()
        }

    predicted = {
        key: rectangle.translated(plan.translations[key])
        for key, rectangle in _group_bounds(before).items()
    }
    observed = _group_bounds(after)
    planning_drawable = _inset_drawable(before.drawable, planning_headroom_m)
    assert planning_drawable is not None  # Readback follows a successful plan.
    return {
        "schema_version": 1,
        "reason": reason,
        "units": "sheet metres",
        "residual_policy": "raw unrounded measurements; not an acceptance tolerance",
        "gap_m": gap_m,
        "validation_gap_m": gap_m,
        "planning_gap_m": gap_m + planning_headroom_m,
        "planning_headroom_m": planning_headroom_m,
        "planning_drawable": list(planning_drawable.bounds),
        "position_tolerance_m": position_tolerance_m,
        "validation_node_budget": 1,
        "plan": packing(plan),
        "validation": packing(validation),
        "references": {key: list(value) for key, value in before.references.items()},
        "drawable": {
            "before": list(before.drawable.bounds),
            "observed": list(after.drawable.bounds),
        },
        "positions": {
            "views": positions(before.positions, targets, after.positions),
            "notes": positions(
                before.note_positions, note_targets, after.note_positions
            ),
        },
        "footprints": {
            "before": bounds(_group_bounds(before)),
            "predicted": bounds(predicted),
            "observed": bounds(observed),
            "observed_minus_predicted_m": {
                key: [a - b for a, b in zip(rectangle.bounds, predicted[key].bounds)]
                for key, rectangle in observed.items()
                if key in predicted
            },
        },
        "outlines": {
            "before": bounds(before.outlines),
            "predicted": bounds(
                {
                    key: value.translated(plan.translations[f"view:{key}"])
                    for key, value in before.outlines.items()
                }
            ),
            "observed": bounds(after.outlines),
        },
        "annotation_bounds": {
            "before": bounds(before.annotation_bounds),
            "observed": bounds(after.annotation_bounds),
        },
        "fixed_bounds": {
            "title-block": list(title_block.bounds),
            "before": bounds(before.obstacles),
            "observed": bounds(after.obstacles),
        },
        "raw_residuals": _raw_residuals(
            after, title_block, gap_m, alignments, orderings
        ),
    }


@_telemetry.traced("drawing.native_layout.apply")
def _apply_targets(adapter, views, order, targets, notes, note_targets):
    for key in order:
        # Native Position expects doubles, not a Python tuple marshalled as
        # an array of VARIANTs. The method also gives an explicit success
        # result. Keep parent propagation, then apply each child's original
        # absolute target exactly once.
        if not views[key].SetViewPosition(double_array(targets[key]), True):
            raise RuntimeError(
                f"{key}: native view rejected layout target {targets[key]}"
            )
    for note in notes:
        if not note.annotation.SetPosition2(*note_targets[note.key]):
            raise RuntimeError(f"{note.key}: native free-note movement was rejected")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("native layout rebuild failed")


@_telemetry.traced("drawing.native_layout")
def repair_native_layout(
    adapter: Any,
    *,
    views: Mapping[str, Any],
    title_block: Rect,
    measure_annotation: Callable[[Any, Any], Any],
    initial_measure_annotation: Callable[[Any, Any], Any] | None = None,
    parents: Mapping[str, str] | None = None,
    alignments: Sequence[AxisLink] = (),
    orderings: Sequence[AxisOrder] = (),
    notes: Sequence[LayoutNote] = (),
    gap_m: float = 0.002,
    planning_headroom_m: float = 0.0,
    max_search_nodes: int = 10_000,
    position_tolerance_m: float = 1e-8,
    final_annotation_validation: Callable[[Mapping[str, Mapping[str, Any]]], None]
    | None = None,
) -> NativeLayoutReport:
    """Repair one fully declared sheet, or return an explicit no-write packing result."""
    if int(adapter.currentModel.GetType()) != 3:
        raise ValueError("native layout requires an active drawing")
    if not math.isfinite(position_tolerance_m) or position_tolerance_m <= 0:
        raise ValueError("native layout position tolerance must be positive and finite")
    if not math.isfinite(planning_headroom_m) or planning_headroom_m < 0:
        raise ValueError(
            "native layout planning headroom must be nonnegative and finite"
        )
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
        before = _snapshot(
            adapter,
            views,
            notes,
            measure_annotation
            if initial_measure_annotation is None
            else initial_measure_annotation,
        )
    planning_drawable = _inset_drawable(before.drawable, planning_headroom_m)
    if planning_drawable is None:
        reason = "planning headroom leaves no positive drawable area"
        failure = PackingResult(PackingStatus.DOES_NOT_FIT, {}, 0, reason)
        return _report(
            NativeLayoutStatus.NO_FIT,
            failure,
            before,
            None,
            title_block,
            reason,
            gap_m,
            planning_headroom_m,
        )
    fixed_issue = _fixed_content_issue(before, title_block, gap_m)
    if fixed_issue is not None:
        failure = PackingResult(PackingStatus.DOES_NOT_FIT, {}, 0, fixed_issue)
        return _report(
            NativeLayoutStatus.NO_FIT,
            failure,
            before,
            None,
            title_block,
            fixed_issue,
            gap_m,
            planning_headroom_m,
        )
    links, orders = _relations(before, alignments, orderings)
    result = pack_view_groups(
        before.groups,
        planning_drawable,
        (title_block, *before.obstacles.values()),
        gap_m=gap_m + planning_headroom_m,
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
        return _report(
            status,
            result,
            before,
            None,
            title_block,
            result.reason,
            gap_m,
            planning_headroom_m,
        )
    movement_required = any(any(delta) for delta in result.translations.values())
    targets = {
        key: tuple(
            a + b
            for a, b in zip(before.positions[key], result.translations[f"view:{key}"])
        )
        for key in views
    }
    note_targets = {}
    for note in notes:
        group = (
            f"view:{note.follows_view}"
            if note.follows_view is not None
            else f"note:{note.key}"
        )
        dx, dy = result.translations[group]
        x, y, z = before.note_positions[note.key]
        note_targets[note.key] = (x + dx, y + dy, z)
    _telemetry.info(
        "native layout translation plan",
        view_targets=json.dumps(targets),
        view_positions_before=json.dumps(before.positions),
        planning_headroom_m=planning_headroom_m,
        planning_gap_m=gap_m + planning_headroom_m,
        validation_gap_m=gap_m,
        planning_drawable=json.dumps(planning_drawable.bounds),
    )
    if movement_required:
        _apply_targets(adapter, views, order, targets, notes, note_targets)
    with _telemetry.span("drawing.native_layout.readback"):
        after = _snapshot(adapter, views, notes, measure_annotation)

    def readback_failure(reason, validation=None):
        return NativeLayoutReadbackError(
            reason,
            _readback_evidence(
                reason,
                before,
                after,
                result,
                validation,
                title_block,
                targets,
                note_targets,
                gap_m,
                position_tolerance_m,
                alignments,
                orderings,
                planning_headroom_m,
            ),
        )

    for key, target in targets.items():
        if math.dist(target, after.positions[key]) > position_tolerance_m:
            raise readback_failure(
                f"{key}: native view did not reach absolute layout target: "
                f"requested={target}, observed={after.positions[key]}"
            )
    for key, target in note_targets.items():
        if math.dist(target, after.note_positions[key]) > position_tolerance_m:
            raise readback_failure(
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
    if before.centerlines.keys() != after.centerlines.keys():
        raise RuntimeError(
            "native layout changed unsupported centerline entity inventory"
        )
    for key, witness in before.centerlines.items():
        observed = after.centerlines[key]
        if int(adapter.swApp.IsSame(witness.specific, observed.specific)) != 1:
            raise RuntimeError(
                f"native layout replaced centerline specific identity: {key}"
            )
        if len(witness.strokes) != len(observed.strokes):
            raise RuntimeError(f"native layout changed centerline stroke count: {key}")
        view = key[0].removeprefix("view:")
        delta = tuple(
            a - b for a, b in zip(after.positions[view], before.positions[view])
        )
        for original, actual in zip(witness.strokes, observed.strokes, strict=True):
            expected = [
                tuple(a + b for a, b in zip(point, delta)) for point in original[:2]
            ]
            if original[2] != actual[2] or any(
                math.dist(target, point) > position_tolerance_m
                for target, point in zip(expected, actual[:2])
            ):
                raise RuntimeError(
                    f"native layout changed centerline stroke translation/width: {key}"
                )
    for key, annotation in before.annotations.items():
        if int(adapter.swApp.IsSame(annotation, after.annotations[key])) != 1:
            raise RuntimeError(f"native layout replaced annotation identity: {key}")
        for original, observed in zip(
            before.attached_entities[key], after.attached_entities[key], strict=True
        ):
            if key in before.centerlines and original is None and observed is None:
                continue  # Explicit unsupported-entity witness above, not entity identity.
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
        raise readback_failure(
            "remeasured native layout does not fit without further movement: "
            f"{validation.status.value}, explored_nodes={validation.explored_nodes}; "
            f"{validation.reason}",
            validation,
        )
    if final_annotation_validation is not None:
        with _telemetry.span("drawing.native_layout.validate_final_annotations"):
            final_annotation_validation(after.measurements)
    return _report(
        NativeLayoutStatus.APPLIED
        if movement_required
        else NativeLayoutStatus.UNCHANGED,
        result,
        before,
        after,
        title_block,
        "native positions and measured layout verified",
        gap_m,
        planning_headroom_m,
    )
