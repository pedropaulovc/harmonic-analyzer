"""Clear measured datum/SF bodies without selecting features by sheet position.

The copy-only ``probe_drawing_mixed_commands.py --mode leader_position`` proves
native bent SF leaders and datum movement/clamping on the pilot drawings. Four
axis-aligned candidates come from actual view/annotation bodies, not recipe XY.
SolidWorks may clamp a datum: only its observed sheet position is used. Native Z
is recorded, not mistaken for a sheet-coordinate failure.

SF leader style intentionally changes before placement. Its semantic/attachment
witness must survive that change; its freshly measured post-style body supplies
the placement seed. Candidate trials read only positions. Fresh final native
bodies must match the predicted translations and clear all other measured bodies.
Datums have two witnessed native body sides: crossing the attachment flips their
frame above/below its anchor without changing text. Their placement envelope is
the union of those two measured orientations; final ink must equal one of them.
Planning clearance (3 mm) is separate from final clearance (2 mm), not a claimed
measurement error bound. Leader routing/crossings and sheet fit are NOT certified
here; decorated-view packing follows this operation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import json
import math
from typing import Any, Callable, Mapping, Sequence

from _common import _early_bound
from _drawing_view_packing import Rect
import _telemetry


_EPSILON_M = 1e-8
_INTERFACES = {2: "IDatumTag", 7: "ISFSymbol"}


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class GtolPlacement(Enum):
    FIXED = "fixed"
    ARRANGED_NEXT = "arranged_next"


class DimensionSource(Enum):
    DRAWING_REFERENCE = "drawing_reference"
    MODEL = "model"


@dataclass(frozen=True)
class Placement:
    direction: Direction
    delta: tuple[float, float]


def _clear(body: Rect, obstacle: Rect, gap_m: float) -> bool:
    return (
        body.xmax + gap_m <= obstacle.xmin + _EPSILON_M
        or obstacle.xmax + gap_m <= body.xmin + _EPSILON_M
        or body.ymax + gap_m <= obstacle.ymin + _EPSILON_M
        or obstacle.ymax + gap_m <= body.ymin + _EPSILON_M
    )


def _past(body: Rect, obstacle: Rect, direction: Direction, gap: float):
    if direction is Direction.UP:
        return 0.0, max(0.0, obstacle.ymax + gap - body.ymin)
    if direction is Direction.DOWN:
        return 0.0, min(0.0, obstacle.ymin - gap - body.ymax)
    if direction is Direction.LEFT:
        return min(0.0, obstacle.xmin - gap - body.xmax), 0.0
    return max(0.0, obstacle.xmax + gap - body.xmin), 0.0


def placement_candidates(
    body: Rect, view: Rect, obstacles: Sequence[Rect], *, gap_m: float = 0.003
) -> tuple[Placement, ...]:
    """Four bounded rays; push past collisions, not unrelated remote notes."""
    if not math.isfinite(gap_m) or gap_m < 0:
        raise ValueError("callout clearance must be finite and nonnegative")
    result = []
    for direction in Direction:
        delta = _past(body, view, direction, gap_m)
        for _ in range(len(obstacles) + 1):
            shifted = body.translated(delta)
            collision = next(
                (r for r in obstacles if not _clear(shifted, r, gap_m)), None
            )
            if collision is None:
                break
            extra = _past(shifted, collision, direction, gap_m)
            delta = delta[0] + extra[0], delta[1] + extra[1]
        else:
            raise RuntimeError("bounded callout ray did not clear its obstacles")
        result.append(Placement(direction, delta))
    return tuple(sorted(result, key=lambda item: math.hypot(*item.delta)))


@dataclass(frozen=True)
class _Symbol:
    name: str
    kind: int
    annotation: Any
    specific: Any
    owner: Any
    entities: tuple[Any, ...]
    entity_types: tuple[int, ...]
    position: tuple[float, float, float]
    body: Rect
    properties: tuple[Any, ...]
    text: tuple[Any, ...]
    format: tuple[Any, ...]


@dataclass(frozen=True)
class _Obstacle:
    annotation: Any
    kind: int
    owner: Any
    owner_type: int
    body: Rect
    content: tuple[Any, ...]
    entities: tuple[Any, ...]
    entity_types: tuple[int, ...]
    null_specific: Any | None
    native_strokes: tuple[Any, ...]
    dimension: _Dimension | None


@dataclass(frozen=True)
class _Dimension:
    display: Any
    dimensions: tuple[Any, ...]
    source: DimensionSource
    display_type: int
    configuration: str
    parameters: tuple[tuple[str, str, int, float], ...]


@dataclass(frozen=True)
class _Deferred:
    annotation: Any
    kind: int
    visibility: int


def _position(annotation: Any) -> tuple[float, float, float]:
    point = tuple(float(value) for value in annotation.GetPosition() or ())
    if len(point) != 3 or not all(math.isfinite(value) for value in point):
        raise RuntimeError("callout position must contain three finite native values")
    return point


def _ink_content(bounds: Any) -> tuple[Any, ...]:
    return tuple(
        (run.value, run.font, run.height_m, run.angle_rad, run.reference, run.inverted)
        for run in bounds.text_runs
    )


def _properties(kind: int, specific: Any) -> tuple[Any, ...]:
    if kind == 2:
        return (
            str(specific.GetLabel()),
            specific.Shoulder,
            int(specific.GetDisplayStyle()),
        )
    symbol = int(specific.GetSymbol())
    if symbol not in {0, 1, 2, 9}:
        raise RuntimeError(f"unsupported pilot surface-finish symbol type {symbol}")
    orientation = int(specific.Orientation)
    if orientation != 1:
        raise RuntimeError(
            "surface finish must retain the established upright orientation"
        )
    # GetTextCount enumerates displayed runs, NOT these semantic field IDs.
    texts = tuple(str(specific.GetText(index)) for index in range(1, 11))
    all_around = specific.GetSymbolAllAround() if symbol in {0, 2, 9} else None
    return symbol, int(specific.GetDirectionOfLay()), all_around, orientation, texts


def _read_symbol(
    adapter: Any, view: Any, annotation: Any, measure: Callable
) -> _Symbol:
    app = adapter.swApp
    kind, name = int(annotation.GetType()), str(annotation.GetName())
    if kind not in _INTERFACES or not name:
        raise RuntimeError("callout needs a named native datum or surface finish")
    if int(annotation.Visible) != 1 or annotation.IsDangling():
        raise RuntimeError(f"{name}: callout must remain visible and attached")
    owner = annotation.Owner
    if int(annotation.OwnerType) != 0 or int(app.IsSame(owner, view)) != 1:
        raise RuntimeError(f"{name}: callout must belong to the exact drawing view")
    entities = tuple(annotation.GetAttachedEntities3() or ())
    types = tuple(int(value) for value in annotation.GetAttachedEntityTypes() or ())
    native_count = int(annotation.GetAttachedEntityCount3())
    if (
        not entities
        or native_count != len(entities)
        or len(entities) != len(types)
        or any(e is None for e in entities)
        or 0 in types
    ):
        raise RuntimeError(f"{name}: exact callout attachments are not available")
    specific = _early_bound(annotation.GetSpecificAnnotation(), _INTERFACES[kind])
    if specific is None or int(app.IsSame(specific.GetAnnotation(), annotation)) != 1:
        raise RuntimeError(
            f"{name}: specific symbol does not round-trip to its annotation"
        )
    count = int(specific.GetTextCount())
    if count < 1:
        raise RuntimeError(f"{name}: callout has no displayed text")
    properties = _properties(kind, specific)
    text = tuple(str(specific.GetTextAtIndex(index)) for index in range(count))
    measured = measure(adapter, annotation)
    position = _position(annotation)
    if math.dist(position[:2], measured.anchor) > _EPSILON_M:
        raise RuntimeError(
            f"{name}: callout body/position have different sheet anchors"
        )
    return _Symbol(
        name,
        kind,
        annotation,
        specific,
        owner,
        entities,
        types,
        position,
        measured.body,
        properties,
        (text, _ink_content(measured)),
        tuple(measured.format_signature),
    )


def _same_symbol(app: Any, before: _Symbol, after: _Symbol) -> None:
    for field in ("name", "kind", "properties", "text", "format", "entity_types"):
        if getattr(before, field) != getattr(after, field):
            raise RuntimeError(f"{before.name}: native callout {field} changed")
    if len(before.entities) != len(after.entities) or any(
        int(app.IsSame(a, b)) != 1 for a, b in zip(before.entities, after.entities)
    ):
        raise RuntimeError(f"{before.name}: exact controlled entity identity changed")
    for field in ("annotation", "specific", "owner"):
        if int(app.IsSame(getattr(before, field), getattr(after, field))) != 1:
            raise RuntimeError(f"{before.name}: native {field} identity changed")


def _visible_annotations(view: Any) -> dict[str, Any]:
    result = {}
    for raw in view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.OwnerType) == 2:  # drawing template, packed separately
            continue
        visibility = int(annotation.Visible)
        if visibility == 3:  # explicitly hidden, no visible body
            continue
        name = str(annotation.GetName())
        if visibility != 1 or not name or name in result:
            raise RuntimeError("native view annotations need unique visible identities")
        result[name] = annotation
    return result


def _dimension_witness(adapter: Any, view: Any, annotation: Any) -> _Dimension:
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if (
        display is None
        or int(adapter.swApp.IsSame(display.GetAnnotation(), annotation)) != 1
    ):
        raise RuntimeError(
            "obstacle dimension display does not round-trip to its annotation"
        )
    display_type = int(display.Type2)
    source = (
        DimensionSource.DRAWING_REFERENCE
        if display.IsReferenceDim()
        else DimensionSource.MODEL
    )
    configuration = str(view.ReferencedConfiguration)
    if not configuration:
        raise RuntimeError("obstacle dimension view has no referenced configuration")
    dimensions, parameters = [], []
    for index in range(2 if display_type == 10 else 1):  # both chamfer parameters
        raw = display.GetDimension2(index)
        if raw is None:
            raise RuntimeError(f"obstacle display dimension has no parameter {index}")
        dimension = _early_bound(raw, "IDimension")
        name, full_name = str(dimension.Name), str(dimension.FullName)
        if not name or not full_name:
            raise RuntimeError("obstacle dimension has no complete native identity")
        if source is DimensionSource.DRAWING_REFERENCE:
            # The committed probe_drawing_attachments --dimension-values api-capture
            # positively controls this getter for native drawing reference dimensions;
            # GetSystemValue3 returned None on that call shape. No fallback is tried.
            value = dimension.GetSystemValue2("")
        else:
            values = tuple(dimension.GetSystemValue3(3, configuration) or ())
            if len(values) != 1:
                raise RuntimeError(
                    "obstacle model dimension did not return one configured value"
                )
            value = values[0]
        if value is None or not math.isfinite(float(value)):
            raise RuntimeError("obstacle dimension system value is not finite/readable")
        dimensions.append(dimension)
        parameters.append((name, full_name, int(dimension.GetType()), float(value)))
    return _Dimension(
        display,
        tuple(dimensions),
        source,
        display_type,
        configuration,
        tuple(parameters),
    )


def _null_centerline_witness(
    adapter: Any,
    view: Any,
    annotation: Any,
    measured: Any,
    entities: tuple,
    types: tuple,
):
    # Same bounded native positive control as _drawing_native_layout: kind15 has
    # one unsupported swSelNOTHING slot. This is a stroke/owner witness, not an
    # invented entity identity or permission for generic dangling annotations.
    if (
        int(annotation.GetType()) != 15
        or int(annotation.OwnerType) != 0
        or entities != (None,)
        or types != (0,)
        or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
    ):
        raise RuntimeError("obstacle attachment has an unsupported null native handle")
    specific = _early_bound(annotation.GetSpecificAnnotation(), "ICenterLine")
    if (
        specific is None
        or int(adapter.swApp.IsSame(specific.GetAnnotation(), annotation)) != 1
    ):
        raise RuntimeError("obstacle centerline specific identity is unavailable")
    strokes = []
    for stroke in measured.native_strokes:
        start, end, width = (
            tuple(stroke.start),
            tuple(stroke.end),
            float(stroke.width_m),
        )
        if (
            len(start) != 2
            or len(end) != 2
            or start == end
            or not all(math.isfinite(v) for v in (*start, *end, width))
            or width <= 0
        ):
            raise RuntimeError("obstacle centerline has invalid native stroke geometry")
        strokes.append((start, end, width))
    if not strokes:
        raise RuntimeError("obstacle centerline has no measured native stroke witness")
    return specific, tuple(strokes)


def _read_obstacles(
    adapter: Any,
    view: Any,
    annotations: Mapping[str, Any],
    measure: Callable,
    deferred: Mapping[str, _Deferred],
):
    result = {}
    for name, annotation in annotations.items():
        if int(annotation.GetType()) in _INTERFACES or name in deferred:
            continue
        measured = measure(adapter, annotation)  # unsupported kinds fail explicitly
        entities = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(int(value) for value in annotation.GetAttachedEntityTypes() or ())
        if (
            len(entities) != len(types)
            or int(annotation.GetAttachedEntityCount3()) != len(entities)
            or annotation.IsDangling()
        ):
            raise RuntimeError(
                f"{name}: obstacle attachment inventory is incomplete or dangling"
            )
        specific, strokes = None, ()
        if any(entity is None for entity in entities):
            specific, strokes = _null_centerline_witness(
                adapter, view, annotation, measured, entities, types
            )
        elif 0 in types:
            raise RuntimeError(f"{name}: obstacle attachment type is unsupported")
        dimension = (
            _dimension_witness(adapter, view, annotation)
            if int(annotation.GetType()) == 4
            else None
        )
        result[name] = _Obstacle(
            annotation,
            int(annotation.GetType()),
            annotation.Owner,
            int(annotation.OwnerType),
            measured.body,
            (tuple(measured.format_signature), _ink_content(measured)),
            entities,
            types,
            specific,
            strokes,
            dimension,
        )
    return result


def _declared_notes(
    adapter: Any, drawing: Any, views: Mapping[str, Any], notes: Sequence[Any]
) -> dict[str, _Deferred]:
    if not notes:
        return {}
    # Sheet-owned unattached notes are legitimate packing groups, not view-only
    # obstacles. Validate membership in sheet views plus the explicitly planned views.
    owners = tuple(sheet[0] for sheet in drawing.GetViews() or ()) + tuple(
        views.values()
    )
    inventory = tuple(
        raw
        for view in owners
        for raw in _early_bound(view, "IView").GetAnnotations() or ()
    )
    result = {}
    for raw_note in notes:
        note = _early_bound(raw_note, "IAnnotation")
        name = str(note.GetName())
        if (
            not name
            or name in result
            or int(note.GetType()) != 6
            or int(note.Visible) != 1
        ):
            raise ValueError(
                "deferred packing notes need unique visible native note identities"
            )
        if not any(
            int(adapter.swApp.IsSame(note, actual)) == 1 for actual in inventory
        ):
            raise ValueError(
                "deferred note is absent from the planned drawing inventory"
            )
        if (
            int(note.GetAttachedEntityCount3()) != 0
            or tuple(note.GetAttachedEntities3() or ())
            or tuple(note.GetAttachedEntityTypes() or ())
        ):
            raise ValueError(
                "only explicitly declared unattached packing notes may be deferred"
            )
        result[name] = _Deferred(note, 6, int(note.Visible))
    return result


def _deferred_annotations(
    app: Any,
    annotations: Mapping[str, Any],
    gtol_placement: GtolPlacement,
    notes: Mapping[str, _Deferred],
) -> dict[str, _Deferred]:
    result = {}
    for name, annotation in annotations.items():
        kind = int(annotation.GetType())
        if kind == 5 and gtol_placement is GtolPlacement.ARRANGED_NEXT:
            result[name] = _Deferred(annotation, kind, int(annotation.Visible))
            continue
        if any(
            int(app.IsSame(annotation, note.annotation)) == 1 for note in notes.values()
        ):
            result[name] = _Deferred(annotation, kind, int(annotation.Visible))
    return result


def _same_deferred(
    app: Any, before: Mapping[str, _Deferred], after: Mapping[str, _Deferred]
) -> None:
    if before.keys() != after.keys():
        raise RuntimeError("deferred native annotation inventory changed")
    for name, old in before.items():
        actual = after[name]
        if (old.kind, old.visibility) != (actual.kind, actual.visibility) or int(
            app.IsSame(old.annotation, actual.annotation)
        ) != 1:
            raise RuntimeError(
                f"{name}: deferred native annotation identity/type/visibility changed"
            )


def _same_obstacles(app: Any, before: Mapping, after: Mapping) -> None:
    if before.keys() != after.keys():
        raise RuntimeError("native callout operation changed obstacle inventory")
    for name, original in before.items():
        actual = after[name]
        if (original.kind, original.owner_type, original.content) != (
            actual.kind,
            actual.owner_type,
            actual.content,
        ):
            raise RuntimeError(
                f"{name}: native obstacle type/owner/text/format changed"
            )
        if (
            int(app.IsSame(original.annotation, actual.annotation)) != 1
            or int(app.IsSame(original.owner, actual.owner)) != 1
        ):
            raise RuntimeError(f"{name}: native obstacle identity changed")
        if original.entity_types != actual.entity_types or len(
            original.entities
        ) != len(actual.entities):
            raise RuntimeError(f"{name}: obstacle attachment inventory changed")
        for first, second in zip(original.entities, actual.entities):
            if (
                original.null_specific is not None
                and actual.null_specific is not None
                and first is None
                and second is None
            ):
                continue  # exact native centerline/stroke witness checked below
            if int(app.IsSame(first, second)) != 1:
                raise RuntimeError(
                    f"{name}: exact obstacle attachment identity changed"
                )
        if original.null_specific is not None or actual.null_specific is not None:
            if (
                original.null_specific is None
                or actual.null_specific is None
                or int(app.IsSame(original.null_specific, actual.null_specific)) != 1
                or original.native_strokes != actual.native_strokes
            ):
                raise RuntimeError(
                    f"{name}: obstacle native centerline/stroke witness changed"
                )
        old_dim, new_dim = original.dimension, actual.dimension
        if old_dim is None and new_dim is None:
            continue
        if old_dim is None or new_dim is None:
            raise RuntimeError(f"{name}: obstacle dimension witness inventory changed")
        if (
            old_dim.source,
            old_dim.display_type,
            old_dim.configuration,
            old_dim.parameters,
        ) != (
            new_dim.source,
            new_dim.display_type,
            new_dim.configuration,
            new_dim.parameters,
        ):
            raise RuntimeError(
                f"{name}: obstacle dimension identity/type/configuration/system value changed"
            )
        if (
            int(app.IsSame(old_dim.display, new_dim.display)) != 1
            or len(old_dim.dimensions) != len(new_dim.dimensions)
            or any(
                int(app.IsSame(a, b)) != 1
                for a, b in zip(old_dim.dimensions, new_dim.dimensions)
            )
        ):
            raise RuntimeError(f"{name}: obstacle native dimension identity changed")


def _reflected_datum_body(symbol: _Symbol) -> Rect:
    y = symbol.position[1]
    return Rect(
        symbol.body.xmin,
        2 * y - symbol.body.ymax,
        symbol.body.xmax,
        2 * y - symbol.body.ymin,
    )


def _placement_body(symbol: _Symbol) -> Rect:
    if symbol.kind != 2:
        return symbol.body
    reflected = _reflected_datum_body(symbol)
    return Rect(
        symbol.body.xmin,
        min(symbol.body.ymin, reflected.ymin),
        symbol.body.xmax,
        max(symbol.body.ymax, reflected.ymax),
    )


def _place(symbol: _Symbol, outline: Rect, obstacles: Sequence[Rect], gap_m: float):
    attempts = []
    placement_body = _placement_body(symbol)
    for candidate in placement_candidates(
        placement_body, outline, obstacles, gap_m=gap_m
    ):
        target = (
            symbol.position[0] + candidate.delta[0],
            symbol.position[1] + candidate.delta[1],
            symbol.position[2],
        )
        if not symbol.annotation.SetPosition2(*target):
            raise RuntimeError(f"{symbol.name}: native callout position rejected")
        actual = _position(symbol.annotation)
        delta = actual[0] - symbol.position[0], actual[1] - symbol.position[1]
        predicted = replace(symbol, position=actual, body=symbol.body.translated(delta))
        attempts.append(
            {"direction": candidate.direction.value, "target": target, "actual": actual}
        )
        if all(
            _clear(placement_body.translated(delta), item, gap_m)
            for item in (outline, *obstacles)
        ):
            return predicted, attempts
        # Every next target is absolute, from the ORIGINAL measured seed. A
        # clamped trial is never adopted as a body/position base and need not
        # return to an insertion point that the native symbol cannot maintain.
        _telemetry.info(
            "native callout candidate readback rejected",
            annotation=symbol.name,
            seed_position=symbol.position,
            candidate_target=target,
            candidate_actual=actual,
        )
    raise RuntimeError(
        f"{symbol.name}: no permitted native direction clears measured bodies: {attempts}"
    )


def _final_symbol(
    app: Any, initial: _Symbol, predicted: _Symbol, actual: _Symbol
) -> None:
    _same_symbol(app, initial, actual)
    allowed_bodies = (predicted.body,)
    if actual.kind == 2:
        allowed_bodies += (_reflected_datum_body(predicted),)
    body_matches = any(
        all(abs(a - b) <= _EPSILON_M for a, b in zip(body.bounds, actual.body.bounds))
        for body in allowed_bodies
    )
    if (
        math.dist(predicted.position[:2], actual.position[:2]) > _EPSILON_M
        or not body_matches
    ):
        raise RuntimeError(
            f"{initial.name}: final native body did not match its post-style translation"
        )
    if actual.kind == 7 and int(actual.annotation.GetLeaderStyle()) != 2:
        raise RuntimeError(
            f"{initial.name}: native bent surface-finish leader was lost"
        )


def arrange_native_callouts(
    adapter: Any,
    *,
    views: Mapping[str, Any],
    measure_annotation: Callable | None = None,
    planning_gap_m: float = 0.003,
    gap_m: float = 0.002,
    gtol_placement: GtolPlacement = GtolPlacement.FIXED,
    deferred_notes: Sequence[Any] = (),
) -> dict[str, dict[str, Any]]:
    """Clear native datum/SF bodies before GTol columns and decorated-view packing.

    Two full witnesses per datum and obstacle, three per restyled SF; no full
    measurement per trial. Active view membership and final actual clearance
    are strict. Nothing is saved here. Unsupported source-owned callouts or
    annotation footprints fail rather than being omitted from collision checks.
    ARRANGED_NEXT is an explicit caller contract: native GTol columns run next
    and clear these final callout bodies. Exact declared unattached notes move in
    subsequent whole-sheet packing, whose final measurement includes every note.
    Deferred annotations retain inventory/identity/type/visibility witnesses but
    do not contribute temporary obstacle glyph measurements.
    """
    if (
        not all(math.isfinite(v) and v >= 0 for v in (planning_gap_m, gap_m))
        or planning_gap_m < gap_m
    ):
        raise ValueError(
            "planning clearance must be finite and at least final clearance"
        )
    model, app = adapter.currentModel, adapter.swApp
    if not isinstance(gtol_placement, GtolPlacement):
        raise ValueError("GTol placement must use the explicit placement policy enum")
    if int(model.GetType()) != 3:
        raise ValueError("native callout layout requires the active drawing")
    if measure_annotation is None:
        from _drawing_annotation_bounds import annotation_box

        measure_annotation = annotation_box
    drawing = _early_bound(model, "IDrawingDoc")
    registered = tuple(raw for sheet in drawing.GetViews() or () for raw in sheet[1:])
    names = set()
    for label, view in views.items():
        name = str(view.GetName2())
        if (
            not label
            or not name
            or name in names
            or not any(int(app.IsSame(view, item)) == 1 for item in registered)
        ):
            raise ValueError(
                "callout views must be unique members of the active drawing"
            )
        names.add(name)
    declared_notes = _declared_notes(adapter, drawing, views, deferred_notes)
    report = {}
    for label, view in views.items():
        if not any(view.GetAnnotationsByType(kind) for kind in _INTERFACES):
            report[label] = {"count": 0}
            continue
        if not drawing.ActivateView(str(view.GetName2())):
            raise RuntimeError("native callout owning view activation failed")
        model.ClearSelection2(True)
        with _telemetry.span("drawing.callouts.initial_witness", view=label):
            annotations = _visible_annotations(view)
            before = {
                name: _read_symbol(adapter, view, annotation, measure_annotation)
                for name, annotation in annotations.items()
                if int(annotation.GetType()) in _INTERFACES
            }
            deferred = _deferred_annotations(
                app, annotations, gtol_placement, declared_notes
            )
            obstacles = _read_obstacles(
                adapter, view, annotations, measure_annotation, deferred
            )
            outline = Rect(*view.GetOutline())
        bank, attempts = dict(before), {}
        for name in sorted(bank, key=lambda key: (bank[key].kind, key)):
            seed = bank[name]
            if seed.kind == 7:
                with _telemetry.span(
                    "drawing.callouts.surface_finish_leader",
                    view=label,
                    annotation=name,
                ):
                    if (
                        int(seed.annotation.SetLeader3(2, 0, True, False, False, False))
                        != 0
                        or int(seed.annotation.GetLeaderStyle()) != 2
                    ):
                        raise RuntimeError(
                            f"{name}: native bent surface-finish leader rejected"
                        )
                    styled = _read_symbol(
                        adapter, view, seed.annotation, measure_annotation
                    )
                    _same_symbol(app, seed, styled)
                    seed = styled  # measured AFTER intentional representation change
            other_bodies = tuple(row.body for row in obstacles.values()) + tuple(
                _placement_body(row) for key, row in bank.items() if key != name
            )
            with _telemetry.span(
                "drawing.callouts.native_position", view=label, annotation=name
            ):
                bank[name], attempts[name] = _place(
                    seed, outline, other_bodies, planning_gap_m
                )
        with _telemetry.span(
            "drawing.callouts.final_witness", view=label, count=len(before)
        ):
            final_annotations = _visible_annotations(view)
            if annotations.keys() != final_annotations.keys():
                raise RuntimeError(
                    "native callout operation changed visible annotation inventory"
                )
            after = {
                name: _read_symbol(adapter, view, annotation, measure_annotation)
                for name, annotation in final_annotations.items()
                if int(annotation.GetType()) in _INTERFACES
            }
            final_deferred = _deferred_annotations(
                app, final_annotations, gtol_placement, declared_notes
            )
            _same_deferred(app, deferred, final_deferred)
            final_obstacles = _read_obstacles(
                adapter, view, final_annotations, measure_annotation, final_deferred
            )
            _same_obstacles(app, obstacles, final_obstacles)
            final_outline = Rect(*view.GetOutline())
            if before.keys() != after.keys():
                raise RuntimeError("native callout operation changed symbol inventory")
            for name, actual in after.items():
                _final_symbol(app, before[name], bank[name], actual)
                other_bodies = (
                    final_outline,
                    *(row.body for row in final_obstacles.values()),
                    *(row.body for key, row in after.items() if key != name),
                )
                if not all(_clear(actual.body, body, gap_m) for body in other_bodies):
                    raise RuntimeError(
                        f"{name}: final native callout body clearance is insufficient"
                    )
        report[label] = {
            "count": len(after),
            "planning_gap_m": planning_gap_m,
            "final_gap_m": gap_m,
            "attempts": attempts,
            "bodies_after": {name: row.body.bounds for name, row in after.items()},
            "positions_after": {name: row.position for name, row in after.items()},
            "deferred_annotations": {name: row.kind for name, row in deferred.items()},
            "obstacle_attachment_exclusions": {
                name: "non-dangling native centerline: exact specific identity and unchanged native strokes"
                for name, row in final_obstacles.items()
                if row.null_specific is not None
            },
        }
        _telemetry.info(
            "native callout layout witnessed",
            view=label,
            callout_report=json.dumps(report[label]),
        )
    _same_deferred(
        app, declared_notes, _declared_notes(adapter, drawing, views, deferred_notes)
    )
    return report
