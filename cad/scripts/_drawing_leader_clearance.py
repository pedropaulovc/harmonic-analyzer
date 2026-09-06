"""Measured native leader clearance shared by production and copied controls.

Pure sheet-metre geometry only. Candidate offsets are hypotheses; only actual
native route readback and a fresh complete final annotation witness accept them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
import json
from typing import Any

from _drawing_annotation_bounds import Segment, LeaderGeometry
from _drawing_view_packing import Rect


def intersects_cell(segment: Segment, cell: Rect) -> bool:
    """Closed segment/rectangle clipping; include touching as a conservative hit."""
    points = (*segment.start, *segment.end)
    if not all(math.isfinite(value) for value in points):
        raise ValueError("native leader coordinates must be finite")
    if not math.isfinite(segment.width_m) or segment.width_m < 0:
        raise ValueError("native leader width must be finite/nonnegative")
    radius = segment.width_m / 2
    lower, upper = 0.0, 1.0
    for start, finish, minimum, maximum in (
        (segment.start[0], segment.end[0], cell.xmin - radius, cell.xmax + radius),
        (segment.start[1], segment.end[1], cell.ymin - radius, cell.ymax + radius),
    ):
        delta = finish - start
        if delta == 0:
            if start < minimum or start > maximum:
                return False
            continue
        enter, leave = sorted(((minimum - start) / delta, (maximum - start) / delta))
        lower, upper = max(lower, enter), min(upper, leave)
        if lower > upper:
            return False
    return True


def _clear(first: Rect, second: Rect, gap: float) -> bool:
    return (
        first.xmax + gap <= second.xmin + 1e-9
        or second.xmax + gap <= first.xmin + 1e-9
        or first.ymax + gap <= second.ymin + 1e-9
        or second.ymax + gap <= first.ymin + 1e-9
    )


def stationary_ink_obstacles(bounds):
    """Keep moved frames clear of an existing annotation's body AND open ink.

    These rectangles conservatively bound already-measured displayed strokes;
    they are planning obstacles, not a new native measurement or inferred route.
    In particular, dimension extension lines are not part of a text-only body.
    """
    obstacles = [bounds.body, *bounds.leader_decorations]
    for stroke in bounds.leader_segments:
        if not all(math.isfinite(value) for value in (*stroke.start, *stroke.end)):
            raise ValueError("stationary annotation stroke must be finite")
        if not math.isfinite(stroke.width_m) or stroke.width_m < 0:
            raise ValueError("stationary annotation width must be finite/nonnegative")
        radius = stroke.width_m / 2
        # Rect requires positive area. Enclose even a zero-width horizontal or
        # vertical native stroke by the adjacent representable floats; this
        # does not invent a physical print width. The planner adds its gap.
        obstacles.append(
            Rect(
                math.nextafter(min(stroke.start[0], stroke.end[0]) - radius, -math.inf),
                math.nextafter(min(stroke.start[1], stroke.end[1]) - radius, -math.inf),
                math.nextafter(max(stroke.start[0], stroke.end[0]) + radius, math.inf),
                math.nextafter(max(stroke.start[1], stroke.end[1]) + radius, math.inf),
            )
        )
    return tuple(obstacles)


def crossing_records(leader_banks, measurements, decorations):
    if leader_banks.keys() != decorations.keys():
        raise ValueError("every native leader bank needs explicit decoration inventory")
    result = []
    for name, segments in leader_banks.items():
        for target, bounds in measurements.items():
            if target == name:
                continue  # own native leader/frame join is intentional
            # Native note text uses INote.GetExtent rather than font cells.
            # Its measured body is the conservative multiline/rich-text cell.
            cells = (bounds.body,) if bounds.kind == 6 else bounds.text_boxes
            for index, cell in enumerate(cells):
                hits = [
                    i
                    for i, segment in enumerate(segments)
                    if intersects_cell(segment, cell)
                ]
                adornments = [
                    i
                    for i, box in enumerate(decorations[name])
                    if box.xmin <= cell.xmax
                    and cell.xmin <= box.xmax
                    and box.ymin <= cell.ymax
                    and cell.ymin <= box.ymax
                ]
                if hits or adornments:
                    result.append(
                        {
                            "leader_annotation": name,
                            "target_annotation": target,
                            "target_kind": bounds.kind,
                            "text_cell_index": index,
                            "text_cell": cell.bounds,
                            "segments": hits,
                            "decorations": adornments,
                            "target_text": [run.value for run in bounds.text_runs],
                        }
                    )
    return result


def displayed_leader_coverage(native, displayed):
    """Conservative complete-segment containment map; no dropped display ink."""
    epsilon = 1e-8  # Same native duplicate-vertex precision as bounds extraction.
    if any(
        not math.isfinite(line.width_m) or line.width_m < 0
        for line in (*native.segments, *displayed)
    ):
        raise ValueError("leader coverage requires finite/nonnegative stroke widths")

    def on_segment(point, segment):
        length = math.dist(segment.start, segment.end)
        if length <= epsilon:
            return math.dist(point, segment.start) <= epsilon
        dx, dy = segment.end[0] - segment.start[0], segment.end[1] - segment.start[1]
        px, py = point[0] - segment.start[0], point[1] - segment.start[1]
        station = (px * dx + py * dy) / length
        return (
            abs(px * dy - py * dx) / length <= epsilon
            and -epsilon <= station <= length + epsilon
        )

    matches = []
    for index, line in enumerate(displayed):
        native_indices = [
            i
            for i, segment in enumerate(native.segments)
            if line.width_m <= segment.width_m
            and on_segment(line.start, segment)
            and on_segment(line.end, segment)
        ]
        decoration_indices = [
            i
            for i, box in enumerate(native.decorations)
            if all(
                box.xmin - epsilon <= point[0] - line.width_m / 2
                and point[0] + line.width_m / 2 <= box.xmax + epsilon
                and box.ymin - epsilon <= point[1] - line.width_m / 2
                and point[1] + line.width_m / 2 <= box.ymax + epsilon
                for point in (line.start, line.end)
            )
        ]
        matches.append(
            {
                "display_index": index,
                "native_container_indices": native_indices,
                "decoration_container_indices": decoration_indices,
            }
        )
    return {
        "native_segments": [asdict(row) for row in native.segments],
        "display_segments": [asdict(row) for row in displayed],
        "native_decorations": [box.bounds for box in native.decorations],
        "coverage": matches,
        "uncovered_display_indices": [
            row["display_index"]
            for row in matches
            if not row["native_container_indices"]
            and not row["decoration_container_indices"]
        ],
    }


class VerticalDirection(Enum):
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class VerticalCandidate:
    direction: VerticalDirection
    dy_m: float


@dataclass(frozen=True)
class _TextCells:
    kind: int
    text_boxes: tuple[Rect, ...]
    text_runs: tuple[Any, ...]
    body: Rect | None = None


def vertical_candidates(crossings, leaders, decorations, *, clearance_m=0.001):
    """Two finite native-column hypotheses, never a computed leader route."""
    if not math.isfinite(clearance_m) or clearance_m < 0:
        raise ValueError("vertical candidate clearance must be finite/nonnegative")
    if not crossings:
        return ()
    up, down = [], []
    for crossing in crossings:
        name = crossing["leader_annotation"]
        cell = Rect(*crossing["text_cell"])
        if crossing["segments"]:
            chain = leaders[name]
            if len(chain) != 2 or math.dist(chain[0].end, chain[1].start) > 1e-8:
                raise ValueError(
                    "vertical control requires one native three-point bent leader"
                )
            elbow_y = chain[0].end[1]
            up.append(max(0.0, cell.ymax + clearance_m - elbow_y))
            down.append(min(0.0, cell.ymin - clearance_m - elbow_y))
        for index in crossing["decorations"]:
            primitive = decorations[name][index]
            up.append(max(0.0, cell.ymax + clearance_m - primitive.ymin))
            down.append(min(0.0, cell.ymin - clearance_m - primitive.ymax))
    if not up:
        raise ValueError(
            "crossing inventory has no actual obstructing native primitives"
        )
    return (
        VerticalCandidate(VerticalDirection.UP, max(up)),
        VerticalCandidate(VerticalDirection.DOWN, min(down)),
    )


def _candidate_text_cells(measured, right_seed, predicted):
    """Moving GTol bodies include symbol/frame ink; other text cells stay fixed."""
    result = {}
    for name, bounds in measured.items():
        result[name] = _TextCells(
            bounds.kind,
            (predicted[name].body,)
            if name in right_seed
            else tuple(bounds.text_boxes),
            tuple(bounds.text_runs),
            bounds.body if bounds.kind == 6 else None,
        )
    return result


def validate_gtol_leader_clearance(measurements_by_view):
    """Validate fresh FINAL packing measurements, including unchanged layouts.

    The caller supplies every visible, non-template annotation in each native
    view AFTER attachment/content/packing checks. This pure callback performs no
    COM or font work, and never substitutes cached trial cells for final bounds.
    Declared view-owned notes are included here even though trials defer them.
    Clearance is bidirectional: another annotation's displayed extension/leader
    strokes and decorations must also avoid every GTol body, including symbols
    and frame borders outside the font cells.
    """
    report = {}
    for view, measurements in measurements_by_view.items():
        geometry = {
            name: LeaderGeometry(
                tuple(row.native_leader_segments), tuple(row.leader_decorations)
            )
            for name, row in measurements.items()
            if row.kind == 5
        }
        coverage = {
            name: displayed_leader_coverage(native, measurements[name].leader_segments)
            for name, native in geometry.items()
        }
        if any(row["uncovered_display_indices"] for row in coverage.values()):
            raise RuntimeError(
                f"{view}: final GTol geometry does not cover displayed leader ink: {json.dumps(coverage)}"
            )
        crossings = crossing_records(
            {name: row.segments for name, row in geometry.items()},
            measurements,
            {name: row.decorations for name, row in geometry.items()},
        )
        if crossings:
            raise RuntimeError(
                f"{view}: final measured GTol leader/text-cell crossings: {json.dumps({'crossings': crossings, 'native_geometry': {name: asdict(row) for name, row in geometry.items()}})}"
            )
        reverse_crossings = crossing_records(
            {
                name: (*row.native_strokes, *row.native_leader_segments)
                for name, row in measurements.items()
            },
            {
                name: _TextCells(row.kind, (row.body,), row.text_runs)
                for name, row in measurements.items()
                if row.kind == 5
            },
            {name: row.leader_decorations for name, row in measurements.items()},
        )
        if reverse_crossings:
            raise RuntimeError(
                f"{view}: final annotation stroke/GTol-body crossings: "
                f"{json.dumps(reverse_crossings)}"
            )
        report[view] = {
            "gtol_count": len(geometry),
            "displayed_stroke_count": sum(
                len(row["display_segments"]) for row in coverage.values()
            ),
            "crossings": crossings,
            "reverse_crossings": reverse_crossings,
        }
    return report
