"""Let native commands space GTols, then move each measured column outboard.

The runnable control is ``diagnostics/probe_gtol_commands.py``: commands 317
and 307 move real view-owned GTol banks and preserve saved entity/text identity.
Their success does NOT certify collision clearance. This helper keeps their
top-down order, moves only later members downward by the measured missing gap,
then tests at most six whole-bank outboard/vertical positions against actual
native leaders and measured text. It never creates annotations, picks geometry,
changes text, or edits leader segments. The caller subsequently packs decorated
views onto the sheet and verifies the save.

Coordinates are sheet metres. Footprints must include quantity/below-frame text
and exclude open leaders. Outboard means outside the actual IView.GetOutline;
same-view datum, dimension and surface-finish bodies are also kept clear. This
includes their measured open strokes and leader decorations, so a dimension
extension cannot pass through an otherwise clear GTol symbol/frame. This local
operation requires text-cell clearance and complete displayed-stroke
coverage, but does not certify final sheet fit or exact glyph-ink distances.

Full native XML/text/attachment/body witnesses are read before and after each
view's complete bank operation. Intermediate bodies are explicitly derived from
observed position translations, not remeasured ink. Final native measurement
must match that prediction and every initial semantic/identity witness; a native
command changing body shape or content can never establish a new accepted base.
"""

from __future__ import annotations

from contextlib import nullcontext

from dataclasses import asdict, dataclass, replace
from enum import Enum
from itertools import combinations
import json
import math
from typing import Any, Callable, Mapping, Sequence
from xml.etree import ElementTree

from _common import _early_bound
from _drawing_view_packing import Rect
from _drawing_annotation_bounds import LeaderGeometry, annotation_leader_geometry
from _drawing_leader_clearance import (
    crossing_records,
    displayed_leader_coverage,
    intersects_cell,
    stationary_ink_obstacles,
    VerticalCandidate,
    VerticalDirection,
    _candidate_text_cells,
)
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


class ColumnSide(Enum):
    LEFT = "left"
    RIGHT = "right"


class _Clearance(Enum):
    CLEAR = "clear"
    BLOCKED = "blocked"


def column_outboard_candidates(
    column: Rect,
    outline: Rect,
    obstacles: Sequence[Rect] = (),
    *,
    gap_m: float = 0.002,
) -> tuple[tuple[ColumnSide, float], ...]:
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
    sides = []
    for side, values in (
        (ColumnSide.LEFT, [dx for dx in feasible if dx <= left + _BODY_EPSILON_M]),
        (ColumnSide.RIGHT, [dx for dx in feasible if dx >= right - _BODY_EPSILON_M]),
    ):
        if values:
            sides.append((side, min(values, key=lambda value: (abs(value), value))))
    return tuple(sorted(sides, key=lambda row: (abs(row[1]), row[1])))


def column_outboard_translation(column, outline, obstacles=(), *, gap_m=0.002):
    return column_outboard_candidates(column, outline, obstacles, gap_m=gap_m)[0][
        1
    ], 0.0


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


def _line_vertical_interval(line, cell, motion, clearance):
    """Closed forbidden DY interval for fixed X and endpoint Y coefficients.

    Clip the parameter t to the rectangle's X slab, as intersects_cell does.
    Rigid Y motion is linear; a fixed/moving endpoint pair has bounds a/t+b,
    whose extrema are at that clipped interval's ends. No diagonal AABB is
    substituted for the line. Motion is relative to the target cell.
    """
    if not math.isfinite(clearance) or clearance < 0:
        raise ValueError("vertical candidate clearance must be finite/nonnegative")
    expanded = Rect(
        cell.xmin - clearance,
        cell.ymin - clearance,
        cell.xmax + clearance,
        cell.ymax + clearance,
    )
    # Reuse the acceptance clipper's finite-coordinate/width validation.
    stationary_hit = intersects_cell(line, expanded)
    if motion not in ((0, 0), (1, 1), (-1, -1), (1, 0), (0, 1), (-1, 0), (0, -1)):
        raise ValueError("unsupported relative vertical endpoint motion")
    if motion == (0, 0):
        return (-math.inf, math.inf) if stationary_hit else None
    start, end = line.start, line.end
    coefficients = motion
    if motion[0] != motion[1] and motion[0] != 0:
        start, end = end, start
        coefficients = motion[::-1]
    radius = line.width_m / 2
    xmin, xmax = expanded.xmin - radius, expanded.xmax + radius
    ymin, ymax = expanded.ymin - radius, expanded.ymax + radius
    lower, upper = 0.0, 1.0
    dx = end[0] - start[0]
    if dx == 0:
        if not xmin <= start[0] <= xmax:
            return None
    else:
        enter, leave = sorted(((xmin - start[0]) / dx, (xmax - start[0]) / dx))
        lower, upper = max(lower, enter), min(upper, leave)
        if lower > upper:
            return None
    dy = end[1] - start[1]
    if coefficients[0] == coefficients[1]:
        values = (start[1] + lower * dy, start[1] + upper * dy)
        interval = ymin - max(values), ymax - min(values)
    elif lower == 0 and ymin <= start[1] <= ymax:
        return -math.inf, math.inf  # fixed endpoint itself intersects the cell
    elif upper == 0:
        return None
    else:
        low_values = [(ymin - start[1]) / upper - dy]
        high_values = [(ymax - start[1]) / upper - dy]
        if lower > 0:
            low_values.append((ymin - start[1]) / lower - dy)
            high_values.append((ymax - start[1]) / lower - dy)
        if lower == 0 and start[1] > ymax:
            low_values.append(-math.inf)
        if lower == 0 and start[1] < ymin:
            high_values.append(math.inf)
        interval = min(low_values), max(high_values)
    return interval if coefficients[1] == 1 else (-interval[1], -interval[0])


def _decoration_motion(box, chain):
    """Associate a measured decoration with moving shoulder OR fixed endpoint."""

    def contains(point):
        return (
            box.xmin - _BODY_EPSILON_M <= point[0] <= box.xmax + _BODY_EPSILON_M
            and box.ymin - _BODY_EPSILON_M <= point[1] <= box.ymax + _BODY_EPSILON_M
        )

    moving = contains(chain[0].start) or contains(chain[0].end)
    fixed = contains(chain[1].end)
    if moving == fixed:
        raise ValueError(
            "whole-bank frontier decoration has ambiguous/unknown vertex association"
        )
    return 1 if moving else 0


def _box_vertical_interval(box, cell, motion, clearance):
    if box.xmax + clearance < cell.xmin or cell.xmax + clearance < box.xmin:
        return None
    low, high = cell.ymin - clearance - box.ymax, cell.ymax + clearance - box.ymin
    if motion == 0:
        return (-math.inf, math.inf) if low <= 0 <= high else None
    if motion == 1:
        return low, high
    if motion == -1:
        return -high, -low
    raise ValueError("unsupported relative vertical rectangle motion")


def _nearest_vertical_candidates(intervals):
    """Walk a finite interval union once per direction, never a grid/retry loop."""
    if any(
        math.isnan(low) or math.isnan(high) or low > high for low, high in intervals
    ):
        raise ValueError("invalid forbidden vertical interval")
    result = []
    for direction, sign in ((VerticalDirection.UP, 1), (VerticalDirection.DOWN, -1)):
        ordered = sorted(
            (low, high) if sign == 1 else (-high, -low) for low, high in intervals
        )
        offset = 0.0
        for low, high in ordered:
            if low > offset:
                break
            if offset <= high:
                # Outward 1 nm exceeds float cancellation at sheet coordinates;
                # it is numerical headroom, not a new physical clearance policy.
                offset = high + _POSITION_EPSILON_M
        if math.isfinite(offset) and offset > 0:
            result.append(VerticalCandidate(direction, sign * offset))
    return tuple(result)


def column_vertical_candidates(
    crossings,
    geometry,
    measurements,
    *,
    clearance_m=0.001,
    bodies=(),
    obstacles=(),
    gap_m=0.002,
):
    """Nearest UP/DOWN free interval under the observed three-point route model.

    Every measured cell participates, not just current hits. The shoulder and
    its decoration move with the bank; model endpoints/arrows stay fixed. Other
    GTol bodies move with the bank too. Unsupported routes fail instead of
    guessing. These two predictions ONLY order native attempts: actual route,
    body, semantic and final sheet checks still decide acceptance.
    """
    if any(not math.isfinite(value) or value < 0 for value in (clearance_m, gap_m)):
        raise ValueError("vertical candidate clearance must be finite/nonnegative")
    if not crossings:
        return ()
    intervals = []
    for name, row in geometry.items():
        chain = row.segments
        if not chain and not row.decorations:
            continue
        if (
            len(chain) != 2
            or math.dist(chain[0].end, chain[1].start) > _BODY_EPSILON_M
            or abs(chain[0].end[1] - chain[0].start[1]) > _BODY_EPSILON_M
            or any(
                not all(
                    math.isfinite(value)
                    for value in (*line.start, *line.end, line.width_m)
                )
                or line.width_m < 0
                for line in chain
            )
        ):
            raise ValueError(
                "whole-bank frontier requires finite native three-point bent leaders"
            )
        decorations = tuple(
            (box, _decoration_motion(box, chain)) for box in row.decorations
        )
        for target, measured in measurements.items():
            if target == name:
                continue  # own native leader/frame join is intentional
            target_motion = 1 if target in geometry else 0
            for cell in (measured.body,) if measured.kind == 6 else measured.text_boxes:
                intervals.extend(
                    _line_vertical_interval(line, cell, motion, clearance_m)
                    for line, motion in zip(
                        chain,
                        (
                            (1 - target_motion, 1 - target_motion),
                            (1 - target_motion, -target_motion),
                        ),
                    )
                )
                intervals.extend(
                    _box_vertical_interval(
                        box, cell, motion - target_motion, clearance_m
                    )
                    for box, motion in decorations
                )
    # Match the existing _separated tolerance; a sufficient horizontal body
    # gap must not acquire a false vertical constraint merely at equality.
    intervals.extend(
        _box_vertical_interval(body, obstacle, 1, gap_m - _BODY_EPSILON_M)
        for body in bodies
        for obstacle in obstacles
    )
    return _nearest_vertical_candidates(
        [interval for interval in intervals if interval is not None]
    )


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
    measurement: Any


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
        expected_owner = view if owner_type == 0 else None
        if owner_type == 3:
            expected_owner = view.ReferencedDocument
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
            bounds,
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
        unchanged = (
            deltas[name] == (0.0, 0.0)
            and math.dist(_position(row.annotation), targets[name])
            <= _POSITION_EPSILON_M
        )
        if not unchanged and not row.annotation.SetPosition2(*targets[name]):
            raise RuntimeError(f"{stage}: {name}: native GTol translation rejected")
    after = _position_translated_bank(bank)
    for name, row in after.items():
        if math.dist(row.position, targets[name]) > _POSITION_EPSILON_M:
            raise RuntimeError(f"{stage}: {name}: native GTol translation was clamped")
    return after


def _place_clear_column(
    seed, initial, measurements, outline, obstacles, *, gap_m, read_geometry
):
    """At most six native bank translations; never mutate a leader segment."""
    column = _union([row.body for row in seed.values()])
    sides = column_outboard_candidates(column, outline, obstacles, gap_m=gap_m)
    attempts, horizontal = [], []

    def screen(delta, stage):
        attempt = {"stage": stage, "delta_m": delta, "status": "started"}
        attempts.append(attempt)
        predicted = _move_bank(seed, {name: delta for name in seed}, stage)
        geometry = {
            name: read_geometry(row.annotation) for name, row in predicted.items()
        }
        crossings = crossing_records(
            {name: row.segments for name, row in geometry.items()},
            _candidate_text_cells(measurements, initial, predicted),
            {name: row.decorations for name, row in geometry.items()},
        )
        body_clear = all(
            _separated(row.body, obstacle, gap_m)
            for row in predicted.values()
            for obstacle in (outline, *obstacles)
        )
        attempt.update(
            status="screened",
            crossings=crossings,
            body_clearance="clear" if body_clear else "blocked",
            positions={name: row.position for name, row in predicted.items()},
            geometry={name: asdict(row) for name, row in geometry.items()},
        )
        return (
            predicted,
            geometry,
            crossings,
            _Clearance.CLEAR if body_clear else _Clearance.BLOCKED,
        )

    # Test both horizontal sides first, then each side's nearest free UP/DOWN
    # intervals. Reverse order tries the most recently observed native side
    # first; the successful lever control is RIGHT then UP. Targets ALWAYS use
    # the same immutable seed, even when an earlier native route was rejected.
    for side, dx in sides:
        predicted, geometry, crossings, body_clear = screen((dx, 0.0), side.value)
        if body_clear is _Clearance.CLEAR and not crossings:
            return predicted, geometry, attempts
        horizontal.append((side, dx, predicted, geometry, crossings))
    for side, dx, horizontal_bank, geometry, crossings in reversed(horizontal):
        candidates = column_vertical_candidates(
            crossings,
            geometry,
            _candidate_text_cells(measurements, initial, horizontal_bank),
            bodies=tuple(row.body for row in horizontal_bank.values()),
            obstacles=(outline, *obstacles),
            gap_m=gap_m,
        )
        for candidate in candidates:
            predicted, actual, hits, body_clear = screen(
                (dx, candidate.dy_m), f"{side.value}-{candidate.direction.value}"
            )
            if body_clear is _Clearance.CLEAR and not hits:
                return predicted, actual, attempts
    raise RuntimeError(
        f"no clear native GTol column within six-candidate bound: {json.dumps(attempts)}"
    )


def _final_leader_witness(last_geometry, bank):
    coverage = {}
    for name, row in bank.items():
        full = row.measurement
        actual = LeaderGeometry(
            tuple(full.native_leader_segments), tuple(full.leader_decorations)
        )
        if actual != last_geometry[name]:
            raise RuntimeError(
                f"{name}: final full native leader geometry differs from candidate"
            )
        coverage[name] = displayed_leader_coverage(actual, full.leader_segments)
    if any(row["uncovered_display_indices"] for row in coverage.values()):
        raise RuntimeError(
            f"final native leader does not cover every displayed stroke: {json.dumps(coverage)}"
        )
    return coverage


def _assert_measured_prediction(
    predicted: Mapping[str, _Gtol], measured: Mapping[str, _Gtol]
) -> None:
    """Final native ink must match translated INITIAL bodies, not a new base."""
    for name, row in measured.items():
        expected = predicted[name]
        if math.dist(row.position, expected.position) > _POSITION_EPSILON_M:
            raise RuntimeError(
                f"{name}: final native GTol position drifted: predicted={expected.position}, measured={row.position}"
            )
        if any(
            abs(a - b) > _BODY_EPSILON_M
            for a, b in zip(row.body.bounds, expected.body.bounds)
        ):
            delta = tuple(a - b for a, b in zip(row.body.bounds, expected.body.bounds))
            _telemetry.info(
                "native GTol body translation mismatch",
                annotation=name,
                predicted_body=expected.body.bounds,
                measured_body=row.body.bounds,
                body_delta_m=delta,
                predicted_position=expected.position,
                measured_position=row.position,
            )
            raise RuntimeError(
                f"{name}: measured GTol body did not translate rigidly: "
                f"predicted={expected.body.bounds}, measured={row.body.bounds}, "
                f"delta_m={delta}, position={row.position}"
            )


def arrange_native_gtol_columns(
    adapter: Any,
    *,
    views: Mapping[str, Any],
    measure_annotation: Callable | None = None,
    measure_obstacle: Callable | None = None,
    obstacle_read_scope: Callable | None = None,
    record_measurement: Callable | None = None,
    gap_m: float = 0.002,
) -> dict[str, dict[str, Any]]:
    """Space exact native banks and translate their measured columns as a whole.

    Called once after annotation/style creation and dimension AutoArrange, before
    view packing. An empty view is a no-op; a singleton skips native multi-select
    commands. Failed commands, semantic drift, clamped targets, body deformation,
    and remaining native GTol overlap all fail loudly. Nothing is saved here.
    An optional record_measurement(view, annotation, bounds) receives actual
    final GTol output and post-command datum/dimension/SF obstacle output for
    initial packing only; it never replaces either fresh GTol witness or supplies
    derived bounds. Center marks/lines are measured fresh and never registered
    in the XYZ-position handoff: their native annotation position may be null.
    The project wrapper MUST run validate_gtol_leader_clearance on its fresh
    packing-final measurements before acceptance, including unchanged packing;
    trial cells deliberately exclude deferred notes and are not a final proof.
    A separate measure_obstacle callback may consume actual callout-final bounds
    after validating unchanged native context/identity/position. It is NEVER
    used for either GTol semantic/XML witness or final packing measurement.
    """
    if not math.isfinite(gap_m) or gap_m < 0:
        raise ValueError("GTol clearance must be finite and nonnegative")
    if int(adapter.currentModel.GetType()) != 3:
        raise ValueError("native GTol columns require the active drawing document")
    if measure_annotation is None:
        from _drawing_annotation_bounds import annotation_box

        measure_annotation = annotation_box
    if measure_obstacle is None:
        measure_obstacle = measure_annotation
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
        # The copy-only cardinality control proves Space Tightly Down requires
        # three selected GTols; Align Left works with two. Two frames still get
        # the measured minimum-clearance pass after native alignment.
        commands = ()
        if len(bank) >= 2:
            commands = (_COMMANDS[1],)
        if len(bank) >= 3:
            commands = _COMMANDS
        for command in commands:
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
        # One post-command obstacle read supplies trial cells and the initial
        # packing handoff. The packing-final callback checks newly measured
        # final cells after ALL view/note moves; no duplicate final font scan.
        obstacles = []
        measurements = {name: row.measurement for name, row in before.items()}
        # This scope contains reads/recording only. Completion is mandatory
        # before the following native column movement; no mutated view is an
        # acceptable new cache baseline.
        with (
            nullcontext() if obstacle_read_scope is None else obstacle_read_scope(view)
        ):
            for kind in (2, 4, 7, 13, 15):
                reference_ink = kind in (13, 15)  # swCenterMarkSym / swCenterLine
                for raw in view.GetAnnotationsByType(kind) or ():
                    annotation = _early_bound(raw, "IAnnotation")
                    if reference_ink and (
                        int(annotation.OwnerType) == 2 or int(annotation.Visible) == 3
                    ):
                        continue  # Same template/hidden exclusion as final packing.
                    # Their measured body encloses all native center-reference
                    # strokes (including width), not just a text/anchor proxy.
                    # Keep these fixed and out of the position-only handoff;
                    # final packing independently reads them again as before.
                    reader = measure_annotation if reference_ink else measure_obstacle
                    measured = reader(adapter, annotation)
                    name = str(annotation.GetName())
                    if not name or name in measurements:
                        raise RuntimeError(
                            "native obstacle needs unique annotation identity"
                        )
                    measurements[name] = measured
                    obstacles.extend(stationary_ink_obstacles(measured))
                    if record_measurement is not None and not reference_ink:
                        record_measurement(view, annotation, measured)
        column = _union([row.body for row in bank.values()])
        with _telemetry.span(
            "drawing.gtol.translate_column",
            view=label,
            count=len(bank),
            bounds_source="derived_translation",
        ):
            predicted, geometry, attempts = _place_clear_column(
                bank,
                before,
                measurements,
                outline,
                obstacles,
                gap_m=gap_m,
                read_geometry=annotation_leader_geometry,
            )
        delta = attempts[-1]["delta_m"]
        _telemetry.info(
            "native GTol column candidates screened",
            view=label,
            candidates=json.dumps(attempts),
        )
        with _telemetry.span(
            "drawing.gtol.final_witness", view=label, count=len(before)
        ):
            after = _read_gtols(adapter, view, measure_annotation)
            _unchanged(adapter.swApp, before, after, "final native witness")
            _assert_measured_prediction(predicted, after)
            coverage = _final_leader_witness(geometry, after)
        _assert_body_clearance(after, gap_m)
        final_column = _union([row.body for row in after.values()])
        if not _separated(final_column, outline, gap_m) or any(
            not _separated(final_column, item, gap_m) for item in obstacles
        ):
            raise RuntimeError(
                "translated GTol column still collides with its view/annotation bodies"
            )
        # Only the actual fresh FINAL witness can feed initial view packing.
        # Derived intermediate bodies and the initial GTol read never enter it.
        if record_measurement is not None:
            for row in after.values():
                record_measurement(view, row.annotation, row.measurement)
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
            "native_candidates": attempts,
            "final_displayed_leader_coverage": coverage,
        }
        _telemetry.info(
            "native GTol leader clearance witnessed",
            view=label,
            candidate_count=len(attempts),
            layout_report=json.dumps(report[label]),
        )
    return report
