"""Let native commands space GTols, then move each measured column outboard.

The runnable control is ``diagnostics/probe_gtol_commands.py``: commands 317
and 307 move real view-owned GTol banks and preserve saved entity/text identity.
Their success does NOT certify collision clearance. This helper keeps their
top-down order, moves only later members downward by the measured missing gap,
then translates the complete bank horizontally. It never creates annotations,
picks geometry, changes text, or searches alternative vertical layouts. The
caller subsequently packs decorated views onto the sheet and verifies the save.

Coordinates are sheet metres. Footprints must include quantity/below-frame text
and exclude open leaders. Outboard means outside the actual IView.GetOutline;
same-view datum, dimension and surface-finish bodies are also kept clear. This
local operation does not certify leader crossings or final sheet fit.

Full native XML/text/attachment/body witnesses are read before and after each
view's complete bank operation. Intermediate bodies are explicitly derived from
observed position translations, not remeasured ink. Final native measurement
must match that prediction and every initial semantic/identity witness; a native
command changing body shape or content can never establish a new accepted base.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
import math
from typing import Any, Callable, Mapping, Sequence
from xml.etree import ElementTree

from _common import _early_bound
from _drawing_view_packing import Rect
import _telemetry


_POSITION_EPSILON_M = 1e-9
_BODY_EPSILON_M = 1e-8
_COMMANDS = (317, 307)  # swCommands_SpaceTightlyDown, AnnotationAlignLeft


def _union(rectangles: Sequence[Rect]) -> Rect:
    if not rectangles:
        raise ValueError("a GTol column must contain measured bodies")
    return Rect(
        min(item.xmin for item in rectangles),
        min(item.ymin for item in rectangles),
        max(item.xmax for item in rectangles),
        max(item.ymax for item in rectangles),
    )


def _separated(first: Rect, second: Rect, gap_m: float = 0.0) -> bool:
    return (
        first.xmax + gap_m <= second.xmin + _BODY_EPSILON_M
        or second.xmax + gap_m <= first.xmin + _BODY_EPSILON_M
        or first.ymax + gap_m <= second.ymin + _BODY_EPSILON_M
        or second.ymax + gap_m <= first.ymin + _BODY_EPSILON_M
    )


def column_outboard_translation(
    column: Rect,
    outline: Rect,
    obstacles: Sequence[Rect] = (),
    *,
    gap_m: float = 0.002,
) -> tuple[float, float]:
    """Return the least absolute horizontal shift among all feasible positions.

    A fixed-height rectangle's horizontal collision constraints are open
    intervals. Their endpoints plus zero contain the closest feasible shift;
    enumeration is bounded by the obstacle count, not a coordinate grid.
    Left wins exact ties. No vertical offsets or sheet boundaries are invented.
    """
    if not math.isfinite(gap_m) or gap_m < 0:
        raise ValueError("GTol clearance must be finite and nonnegative")
    left = outline.xmin - gap_m - column.xmax
    right = outline.xmax + gap_m - column.xmin
    candidates = {0.0, left, right}
    for obstacle in obstacles:
        candidates.add(obstacle.xmin - gap_m - column.xmax)
        candidates.add(obstacle.xmax + gap_m - column.xmin)
    feasible = []
    for dx in candidates:
        if dx > left + _BODY_EPSILON_M and dx < right - _BODY_EPSILON_M:
            continue
        moved = column.translated((dx, 0.0))
        if all(_separated(moved, obstacle, gap_m) for obstacle in obstacles):
            feasible.append(dx)
    if not feasible:
        raise RuntimeError("no finite horizontal outboard translation was found")
    return min(feasible, key=lambda value: (abs(value), value)), 0.0


def column_clearance_translations(
    bodies: Mapping[str, Rect],
    native_order: Sequence[str],
    *,
    gap_m: float = 0.002,
) -> dict[str, tuple[float, float]]:
    """Make one top-down pass; retain native order and every sufficient gap.

    Each later body moves downward only as far as required by the already placed
    predecessor. Native X positions and the first body's position stay intact.
    """
    if not math.isfinite(gap_m) or gap_m < 0:
        raise ValueError("GTol clearance must be finite and nonnegative")
    if len(native_order) != len(bodies) or set(native_order) != set(bodies):
        raise ValueError(
            "native GTol order must contain each measured body exactly once"
        )
    result = {}
    ceiling = math.inf
    for name in native_order:
        body = bodies[name]
        dy = min(0.0, ceiling - body.ymax)
        result[name] = (0.0, dy)
        ceiling = body.ymin + dy - gap_m
    return result


@dataclass(frozen=True)
class _Gtol:
    annotation: Any
    position: tuple[float, float, float]
    body: Rect
    frames: tuple[str, ...]
    text: tuple[str, ...]
    text_format: tuple[Any, ...]
    entities: tuple[Any, ...]
    entity_types: tuple[int, ...]
    owner: Any
    owner_type: int


def _position(annotation: Any) -> tuple[float, float, float]:
    values = tuple(float(value) for value in annotation.GetPosition() or ())
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise RuntimeError("native GTol position must contain three finite values")
    return values


def _read_gtols(adapter: Any, view: Any, measure: Callable) -> dict[str, _Gtol]:
    result = {}
    for raw in view.GetAnnotationsByType(5) or ():  # swGTol
        annotation = _early_bound(raw, "IAnnotation")
        name = str(annotation.GetName())
        if not name or name in result or int(annotation.GetType()) != 5:
            raise RuntimeError("view GTols require unique nonempty native identities")
        if annotation.IsDangling() or int(annotation.Visible) != 1:
            raise RuntimeError(f"{name}: GTol must be visible and attached")
        entities = tuple(annotation.GetAttachedEntities3() or ())
        kinds = tuple(int(value) for value in annotation.GetAttachedEntityTypes() or ())
        if (
            not entities
            or len(entities) != len(kinds)
            or any(item is None for item in entities)
            or any(kind == 0 for kind in kinds)
        ):
            raise RuntimeError(f"{name}: GTol attachment cannot be proven exactly")
        owner_type = int(annotation.OwnerType)
        owner = annotation.Owner
        expected_owner = {0: view, 3: view.ReferencedDocument}.get(owner_type)
        if (
            expected_owner is None
            or int(adapter.swApp.IsSame(owner, expected_owner)) != 1
        ):
            raise RuntimeError(
                f"{name}: annotation owner does not match the drawing view/source"
            )
        gtol = _early_bound(annotation.GetSpecificAnnotation(), "IGtol")
        count = int(gtol.GetFrameCount())
        if count < 1:
            raise RuntimeError(f"{name}: native GTol has no stored frames")
        frames = []
        for index in range(1, count + 1):
            frame = gtol.GetFrame(index)
            if frame is None:
                raise RuntimeError(
                    f"{name}: stored GTol frame {index} has no readable XML object"
                )
            frames.append(
                ElementTree.canonicalize(
                    str(_early_bound(frame, "IGtolFrame").GetSymbolXml())
                )
            )
        bounds = measure(adapter, annotation)
        position = _position(annotation)
        if math.dist(position[:2], bounds.anchor) > _POSITION_EPSILON_M:
            raise RuntimeError(
                f"{name}: measured body and position use different anchors"
            )
        result[name] = _Gtol(
            annotation,
            position,
            bounds.body,
            tuple(frames),
            tuple(
                str(gtol.GetTextAtIndex(index))
                for index in range(int(gtol.GetTextCount()))
            ),
            tuple(bounds.format_signature),
            entities,
            kinds,
            owner,
            owner_type,
        )
    return result


def _unchanged(
    app: Any, before: Mapping[str, _Gtol], after: Mapping[str, _Gtol], stage: str
) -> dict[str, float]:
    if set(before) != set(after):
        raise RuntimeError(f"{stage}: native GTol coverage changed")
    movement = {}
    for name, old in before.items():
        current = after[name]
        if (old.frames, old.text, old.text_format) != (
            current.frames,
            current.text,
            current.text_format,
        ):
            raise RuntimeError(f"{stage}: {name}: frame/text/format changed")
        if old.entity_types != current.entity_types or len(old.entities) != len(
            current.entities
        ):
            raise RuntimeError(f"{stage}: {name}: attachment count/type changed")
        if any(
            int(app.IsSame(first, second)) != 1
            for first, second in zip(old.entities, current.entities)
        ):
            raise RuntimeError(f"{stage}: {name}: exact attachment identity changed")
        if (
            old.owner_type != current.owner_type
            or int(app.IsSame(old.owner, current.owner)) != 1
        ):
            raise RuntimeError(f"{stage}: {name}: annotation owner changed")
        if int(app.IsSame(old.annotation, current.annotation)) != 1:
            raise RuntimeError(f"{stage}: {name}: annotation identity changed")
        movement[name] = math.dist(old.position, current.position)
    return movement


def _native_command(
    adapter: Any, drawing: Any, view: Any, bank: Mapping[str, _Gtol], command: int
) -> None:
    model, app = adapter.currentModel, adapter.swApp
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    model.ClearSelection2(True)
    try:
        if not drawing.ActivateView(str(view.GetName2())):
            raise RuntimeError("failed to activate the GTol bank's owning view")
        for state in bank.values():
            if not state.annotation.Select2(True, 0):
                raise RuntimeError("failed to select a GTol in the native bank")
        if int(selection.GetSelectedObjectCount2(-1)) != len(bank):
            raise RuntimeError("selected GTol bank count is not exact")
        missing_view_context = 0
        for index, state in enumerate(bank.values(), 1):
            if int(selection.GetSelectedObjectType3(index, -1)) != 13:  # swSelGTOLS
                raise RuntimeError("selected bank contains a non-GTol object")
            selected_view = selection.GetSelectedObjectsDrawingView2(index, -1)
            if selected_view is not None and int(app.IsSame(selected_view, view)) != 1:
                raise RuntimeError("selected GTol belongs to a different drawing view")
            selected = _early_bound(selection.GetSelectedObject6(index, -1), "IGtol")
            annotation = _early_bound(selected.GetAnnotation(), "IAnnotation")
            if int(app.IsSame(annotation, state.annotation)) != 1:
                raise RuntimeError(
                    "selected GTol identity differs from the native bank"
                )
            if (
                int(annotation.OwnerType) != state.owner_type
                or int(app.IsSame(annotation.Owner, state.owner)) != 1
            ):
                raise RuntimeError("selected GTol owner differs from the native bank")
            if selected_view is None:
                # The copy-only probe records None for all 24 real Select2 GTol
                # selections, despite exact selected annotation/owning-view IDs.
                # Source-owned imports cannot use this drawing-owner witness.
                if (
                    state.owner_type != 0
                    or int(app.IsSame(annotation.Owner, view)) != 1
                ):
                    raise RuntimeError(
                        "source-owned GTol selection has no exact drawing-view context"
                    )
                missing_view_context += 1
        if missing_view_context:
            _telemetry.info(
                "GTol selection view context supplied by exact annotation owner",
                view=str(view.GetName2()),
                command=command,
                missing_selection_view_count=missing_view_context,
                count=len(bank),
            )
        if not app.IsCommandEnabled(command):
            raise RuntimeError(f"native annotation command {command} is disabled")
        with _telemetry.span(
            "drawing.gtol.native_command", command=command, count=len(bank)
        ):
            if not app.RunCommand(command, ""):
                raise RuntimeError(
                    f"native annotation command {command} rejected the bank"
                )
    finally:
        model.ClearSelection2(True)


def _assert_body_clearance(bank: Mapping[str, _Gtol], gap_m: float) -> None:
    for (first_name, first), (second_name, second) in combinations(bank.items(), 2):
        if not _separated(first.body, second.body, gap_m):
            raise RuntimeError(
                f"native GTol spacing left insufficient measured body clearance: {first_name}, {second_name}"
            )


def _position_translated_bank(bank: Mapping[str, _Gtol]) -> dict[str, _Gtol]:
    """Observe actual native positions; keep bodies as unverified predictions."""
    result = {}
    for name, row in bank.items():
        position = _position(row.annotation)
        delta = (position[0] - row.position[0], position[1] - row.position[1])
        result[name] = replace(row, position=position, body=row.body.translated(delta))
    return result


def _move_bank(
    bank: Mapping[str, _Gtol],
    deltas: Mapping[str, tuple[float, float]],
    stage: str,
) -> dict[str, _Gtol]:
    targets = {
        name: (
            row.position[0] + deltas[name][0],
            row.position[1] + deltas[name][1],
            row.position[2],
        )
        for name, row in bank.items()
    }
    for name, row in bank.items():
        if deltas[name] != (0.0, 0.0) and not row.annotation.SetPosition2(
            *targets[name]
        ):
            raise RuntimeError(f"{stage}: {name}: native GTol translation rejected")
    after = _position_translated_bank(bank)
    for name, row in after.items():
        if math.dist(row.position, targets[name]) > _POSITION_EPSILON_M:
            raise RuntimeError(f"{stage}: {name}: native GTol translation was clamped")
    return after


def _assert_measured_prediction(
    predicted: Mapping[str, _Gtol], measured: Mapping[str, _Gtol]
) -> None:
    """Final native ink must match translated INITIAL bodies, not a new base."""
    for name, row in measured.items():
        expected = predicted[name]
        if math.dist(row.position, expected.position) > _POSITION_EPSILON_M:
            raise RuntimeError(f"{name}: final native GTol position drifted")
        if any(
            abs(a - b) > _BODY_EPSILON_M
            for a, b in zip(row.body.bounds, expected.body.bounds)
        ):
            raise RuntimeError(f"{name}: measured GTol body did not translate rigidly")


def arrange_native_gtol_columns(
    adapter: Any,
    *,
    views: Mapping[str, Any],
    measure_annotation: Callable | None = None,
    gap_m: float = 0.002,
) -> dict[str, dict[str, Any]]:
    """Space exact native banks and translate their measured columns as a whole.

    Called once after annotation/style creation and dimension AutoArrange, before
    view packing. An empty view is a no-op; a singleton skips native multi-select
    commands. Failed commands, semantic drift, clamped targets, body deformation,
    and remaining native GTol overlap all fail loudly. Nothing is saved here.
    """
    if not math.isfinite(gap_m) or gap_m < 0:
        raise ValueError("GTol clearance must be finite and nonnegative")
    if int(adapter.currentModel.GetType()) != 3:
        raise ValueError("native GTol columns require the active drawing document")
    if measure_annotation is None:
        from _drawing_annotation_bounds import annotation_box

        measure_annotation = annotation_box
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    registered = tuple(raw for sheet in drawing.GetViews() or () for raw in sheet[1:])
    names = set()
    for label, view in views.items():
        name = str(view.GetName2())
        if (
            not label
            or not name
            or name in names
            or not any(
                int(adapter.swApp.IsSame(view, actual)) == 1 for actual in registered
            )
        ):
            raise ValueError("GTol views must be unique members of the active drawing")
        names.add(name)
    report = {}
    for label, view in views.items():
        with _telemetry.span("drawing.gtol.initial_witness", view=label):
            before = _read_gtols(adapter, view, measure_annotation)
        if not before:
            report[label] = {"count": 0, "commands": [], "translation_m": (0.0, 0.0)}
            continue
        outline = Rect(*view.GetOutline())
        bank, command_report = before, []
        for command in _COMMANDS if len(bank) > 1 else ():
            _native_command(adapter, drawing, view, bank, command)
            current = _position_translated_bank(bank)
            motion = {
                name: math.dist(row.position, current[name].position)
                for name, row in bank.items()
            }
            command_report.append(
                {
                    "command": command,
                    "movement_m": motion,
                    "body_union": _union([row.body for row in current.values()]).bounds,
                    "body_union_source": "derived_translation",
                }
            )
            bank = current
        native_order = sorted(bank, key=lambda name: -bank[name].position[1])
        clearance_deltas = column_clearance_translations(
            {name: row.body for name, row in bank.items()}, native_order, gap_m=gap_m
        )
        with _telemetry.span(
            "drawing.gtol.minimum_clearance",
            view=label,
            count=len(bank),
            moved_count=sum(delta != (0.0, 0.0) for delta in clearance_deltas.values()),
            bounds_source="derived_translation",
        ):
            bank = _move_bank(
                bank,
                clearance_deltas,
                "minimum clearance",
            )
        _assert_body_clearance(bank, gap_m)
        obstacles = [
            measure_annotation(adapter, _early_bound(raw, "IAnnotation")).body
            for kind in (2, 4, 7)
            for raw in view.GetAnnotationsByType(kind) or ()
        ]
        column = _union([row.body for row in bank.values()])
        delta = column_outboard_translation(column, outline, obstacles, gap_m=gap_m)
        with _telemetry.span(
            "drawing.gtol.translate_column",
            view=label,
            count=len(bank),
            dx=delta[0],
            dy=delta[1],
            bounds_source="derived_translation",
        ):
            predicted = _move_bank(
                bank,
                {name: delta for name in bank},
                "outboard column",
            )
        with _telemetry.span(
            "drawing.gtol.final_witness", view=label, count=len(before)
        ):
            after = _read_gtols(adapter, view, measure_annotation)
            _unchanged(adapter.swApp, before, after, "final native witness")
            _assert_measured_prediction(predicted, after)
        _assert_body_clearance(after, gap_m)
        final_column = _union([row.body for row in after.values()])
        if not _separated(final_column, outline, gap_m) or any(
            not _separated(final_column, item, gap_m) for item in obstacles
        ):
            raise RuntimeError(
                "translated GTol column still collides with its view/annotation bodies"
            )
        report[label] = {
            "count": len(after),
            "commands": command_report,
            "clearance_translations_m": clearance_deltas,
            "translation_m": delta,
            "body_before": column.bounds,
            "body_before_source": "derived_translation",
            "body_after": final_column.bounds,
            "body_after_source": "native_measurement",
            "positions_after": {name: row.position for name, row in after.items()},
            "obstacle_count": len(obstacles),
        }
    return report
