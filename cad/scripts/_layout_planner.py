"""Read-back candidate search: where a text block (and its leader) can sit
clear of a drawing sheet's ink.

Opt-in: imported only by the drawings that need a placement they cannot state
as a literal (draw_cone_pivot_post; draw_cone_swing_platform next), so adding
it re-keys no other drawing.

It owns NO box reader and NO clearance rule.  Every box comes from the reader
the layout audit gates on (``diagnostics.drawing_layout_audit.collect_document``
-> ``SheetGeometry``); every leader rule is the audit's own
(``_drawing_layout_check.find_leader_crossings`` /
``find_leader_leader_crossings``, same inset and touch tolerances), and
text-to-ink depth is ``_layout_geometry.segment_box_overlap_length``.  So a
placement it accepts is judged by the rules the gate applies afterwards.

Convergence note: ``_drawing_annotation_extent`` (dt-torque-shaft-pin,
9709b8757) solves a neighbouring problem -- moving one callout clear of lanes
and frames -- on its own box helpers.  When the #917 line meets that one, the
two must converge on ``collect_document`` as their single reader.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from _drawing_layout_check import (
    CollisionScope,
    DrawableRegion,
    LayoutElement,
    LeaderSegment,
    find_leader_crossings,
    find_leader_leader_crossings,
)
from _layout_geometry import Box, Segment, SheetGeometry, segment_box_overlap_length

# The clearance every placed box keeps from the border, views, text and ink.
GAP_M = 0.002


@dataclass(frozen=True)
class SheetObstacles:
    """Everything already on a sheet that a new text block must keep clear of."""

    region: DrawableRegion
    keep_outs: tuple[tuple[str, Box], ...] = ()
    views: tuple[tuple[str, Box, bool], ...] = ()  # name, outline, pictorial
    texts: tuple[tuple[str, Box], ...] = ()
    ink: tuple[tuple[str, Segment], ...] = ()
    leaders: tuple[LeaderSegment, ...] = ()

    def describe(self) -> str:
        rows = [
            f"border [{self.region.xmin * 1000:.1f},{self.region.ymin * 1000:.1f}].."
            f"[{self.region.xmax * 1000:.1f},{self.region.ymax * 1000:.1f}]mm"
        ]
        rows += [f"keep-out {name} {box.format_mm()}" for name, box in self.keep_outs]
        rows += [
            f"view {name} {box.format_mm()}{' (pictorial)' if pictorial else ''}"
            for name, box, pictorial in self.views
        ]
        rows += [f"text {name} {box.format_mm()}" for name, box in self.texts]
        return "; ".join(rows)


def sheet_obstacles(
    sheet: SheetGeometry,
    *,
    skip_views: Iterable[str] = (),
    skip_labels: Iterable[str] = (),
) -> SheetObstacles:
    """The obstacles on ``sheet``, less the views and annotations being placed."""
    skip_views, skip_labels = set(skip_views), set(skip_labels)
    annotations = [a for a in sheet.annotations if a.label not in skip_labels]
    return SheetObstacles(
        region=sheet.region,
        keep_outs=tuple(sheet.keep_outs),
        views=tuple(
            (view.name, view.outline, view.pictorial)
            for view in sheet.views
            if view.outline is not None and view.name not in skip_views
        ),
        texts=tuple((a.label, box) for a in annotations for box in a.text_boxes),
        ink=tuple((a.label, segment) for a in annotations for segment in a.segments),
        leaders=tuple(
            LeaderSegment(a.label, a.kind, s.x0, s.y0, s.x1, s.y1, a.owner)
            for a in annotations
            for s in a.leader_segments()
        ),
    )


def _grown(box: Box, by: float) -> Box:
    return Box(box.xmin - by, box.ymin - by, box.xmax + by, box.ymax + by)


def box_conflict(box: Box, obstacles: SheetObstacles, *, gap: float = GAP_M) -> str | None:
    """Why ``box`` is not a clear spot for text, or None when it is.

    Clear means: inside the border less ``gap``, and ``gap`` from every
    keep-out, every non-pictorial view outline (a pictorial outline is empty
    diagonal space; the audit never collides it), every text box and every
    line of annotation ink."""
    region = obstacles.region
    if (
        box.xmin < region.xmin + gap
        or box.ymin < region.ymin + gap
        or box.xmax > region.xmax - gap
        or box.ymax > region.ymax - gap
    ):
        return f"border ({box.format_mm()} within {gap * 1000:.1f} mm of the border)"
    for name, other in obstacles.keep_outs:
        if box.gap(other) < gap:
            return f"keep-out {name} {other.format_mm()}"
    for name, other, pictorial in obstacles.views:
        if not pictorial and box.gap(other) < gap:
            return f"view {name} {other.format_mm()}"
    for name, other in obstacles.texts:
        if box.gap(other) < gap:
            return f"text {name} {other.format_mm()}"
    grown = _grown(box, gap)
    for name, segment in obstacles.ink:
        if segment_box_overlap_length(segment, grown) > 0.0:
            return (
                f"ink of {name} ({segment.x0 * 1000:.1f},{segment.y0 * 1000:.1f})->"
                f"({segment.x1 * 1000:.1f},{segment.y1 * 1000:.1f})mm"
            )
    return None


def leader_conflicts(
    segments: Iterable[LeaderSegment], obstacles: SheetObstacles
) -> list[str]:
    """Every audit leader finding the new ``segments`` would raise: a run
    across a foreign (non-pictorial) view, or a crossing with any leader
    already on the sheet (or with each other)."""
    segments = list(segments)
    views = [
        LayoutElement(
            name,
            "view",
            box.xmin,
            box.ymin,
            box.xmax,
            box.ymax,
            scope=CollisionScope.NONE if pictorial else CollisionScope.ALL,
        )
        for name, box, pictorial in obstacles.views
    ]
    found = [crossing.describe() for crossing in find_leader_crossings(segments, views)]
    ours = {segment.label for segment in segments}
    for crossing in find_leader_leader_crossings([*segments, *obstacles.leaders]):
        if crossing.a.label in ours or crossing.b.label in ours:
            found.append(crossing.describe())
    return found


@dataclass(frozen=True)
class CaptionPlan:
    """Where a view and its caption go: the view's move and both final boxes."""

    how: str
    view_dx: float
    view_dy: float
    view: Box
    caption: Box


def _shift(box: Box, dx: float, dy: float) -> Box:
    return Box(box.xmin + dx, box.ymin + dy, box.xmax + dx, box.ymax + dy)


def caption_candidates(
    view: Box,
    size: tuple[float, float],
    region: DrawableRegion,
    *,
    gap: float = GAP_M,
    step: float = 0.001,
    reach: float = 0.2,
) -> Iterator[CaptionPlan]:
    """Candidates in the drawing's reading order.

    First the usual caption over its view, left-aligned: the view slides
    sideways (nearest first) and drops only as far as the caption needs
    under the border.  Then, with the view where it is, the caption beside
    it, top-aligned: left, then right."""
    width, height = size
    shifts = sorted(
        (round(k * step, 9) for k in range(-int(reach / step), int(reach / step) + 1)),
        key=lambda dx: (abs(dx), dx),
    )
    for dx in shifts:
        dy = min(0.0, (region.ymax - gap) - (view.ymax + gap + height))
        moved = _shift(view, dx, dy)
        caption = Box(
            moved.xmin, moved.ymax + gap, moved.xmin + width, moved.ymax + gap + height
        )
        yield CaptionPlan("caption over the view", dx, dy, moved, caption)
    yield CaptionPlan(
        "caption beside the view, left",
        0.0,
        0.0,
        view,
        Box(view.xmin - gap - width, view.ymax - height, view.xmin - gap, view.ymax),
    )
    yield CaptionPlan(
        "caption beside the view, right",
        0.0,
        0.0,
        view,
        Box(view.xmax + gap, view.ymax - height, view.xmax + gap + width, view.ymax),
    )


def plan_caption(
    view: Box,
    size: tuple[float, float],
    obstacles: SheetObstacles,
    *,
    label: str,
    gap: float = GAP_M,
) -> CaptionPlan:
    """The first candidate whose view and caption are both clear, or a loud
    failure naming every box the search read."""
    rejected: dict[str, str] = {}
    for plan in caption_candidates(view, size, obstacles.region, gap=gap):
        reason = box_conflict(plan.view, obstacles, gap=gap) or box_conflict(
            plan.caption, obstacles, gap=gap
        )
        if reason is None:
            return plan
        if plan.view_dx == 0.0 or plan.how.startswith("caption beside"):
            rejected[plan.how] = reason
    raise RuntimeError(
        f"{label}: no clear place for the caption ({size[0] * 1000:.1f} x "
        f"{size[1] * 1000:.1f} mm) and its view {view.format_mm()}: "
        f"{rejected}; every view shift up to 200 mm either way was blocked too. "
        f"Sheet: {obstacles.describe()}"
    )
