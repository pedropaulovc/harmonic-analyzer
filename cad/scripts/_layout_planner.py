"""Read-back candidate search: where a view, its caption and a hole callout
can sit clear of a drawing sheet's ink.

Opt-in: imported only by the drawings that need a placement they cannot state
as a literal (draw_cone_pivot_post; draw_cone_swing_platform next), so adding
it re-keys no other drawing.

It owns NO box reader and NO clearance rule.  Every box comes from the reader
the layout audit gates on (``diagnostics.drawing_layout_audit.collect_document``
-> ``SheetGeometry``); every leader rule is the audit's own
(``_drawing_layout_check.find_leader_crossings`` /
``find_leader_leader_crossings``, same inset and touch tolerances), text-to-ink
depth is ``_layout_geometry.segment_box_overlap_length`` and the crowding
clearance is ``find_view_crowding``'s (one text height of the smaller box).  So
a placement it accepts is judged by the rules the gate applies afterwards.

Convergence note: ``_drawing_annotation_extent`` (dt-torque-shaft-pin,
9709b8757) solves a neighbouring problem -- moving one callout clear of lanes
and frames -- on its own box helpers.  When the #917 line meets that one, the
two must converge on ``collect_document`` as their single reader.
"""

from __future__ import annotations

import math
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
from _layout_geometry import (
    DEFAULT_TEXT_TOUCH_TOL_M,
    Box,
    Segment,
    SheetGeometry,
    segment_box_overlap_length,
)

# The clearance every placed box keeps from the border, views, text and ink.
GAP_M = 0.002
# The candidate grid: every shift and every callout spot is a multiple of it.
STEP_M = 0.002
# The most callout text spots one plan may judge.  Each costs at most ~0.14 ms
# (box rule + leader rule on the 917-s1-9eb0 sheet), so a search that finds
# nothing still fails in seconds: it runs while the build holds the COM seat.
CALLOUT_BUDGET = 40_000


@dataclass(frozen=True)
class SheetObstacles:
    """Everything already on a sheet that a new block must keep clear of."""

    region: DrawableRegion
    keep_outs: tuple[tuple[str, Box], ...] = ()
    views: tuple[tuple[str, Box, bool], ...] = ()  # name, outline, pictorial
    texts: tuple[tuple[str, Box], ...] = ()  # one row per rendered text line
    ink: tuple[tuple[str, Segment], ...] = ()
    leaders: tuple[LeaderSegment, ...] = ()
    # label, owning view, union of its text rows: find_view_crowding's unit.
    owned: tuple[tuple[str, str, Box], ...] = ()

    def text_extent(self, name: str) -> Box:
        """The union of every text row of ``name`` -- the whole annotation."""
        rows = [box for label, box in self.texts if label == name]
        return Box(
            min(box.xmin for box in rows),
            min(box.ymin for box in rows),
            max(box.xmax for box in rows),
            max(box.ymax for box in rows),
        )

    def plus(
        self,
        *,
        views: Iterable[tuple[str, Box]] = (),
        texts: Iterable[tuple[str, Box]] = (),
    ) -> SheetObstacles:
        """These obstacles and the boxes just planned (never pictorial)."""
        return SheetObstacles(
            region=self.region,
            keep_outs=self.keep_outs,
            views=self.views + tuple((name, box, False) for name, box in views),
            texts=self.texts + tuple(texts),
            ink=self.ink,
            leaders=self.leaders,
            owned=self.owned,
        )

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
        rows += [
            f"text {name} {self.text_extent(name).format_mm()}"
            for name in dict.fromkeys(name for name, _ in self.texts)
        ]
        return "; ".join(rows)


def _union(boxes: Iterable[Box]) -> Box | None:
    boxes = list(boxes)
    if not boxes:
        return None
    return Box(
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
    )


def sheet_obstacles(
    sheet: SheetGeometry,
    *,
    skip_views: Iterable[str] = (),
    skip_labels: Iterable[str] = (),
) -> SheetObstacles:
    """The obstacles on ``sheet``, less the views and annotations being placed."""
    skip_views, skip_labels = set(skip_views), set(skip_labels)
    annotations = [a for a in sheet.annotations if a.label not in skip_labels]
    owned = []
    for a in annotations:
        box = _union(a.text_boxes)
        if box is not None and a.owner not in ("", "sheet"):
            owned.append((a.label, a.owner, box))
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
        owned=tuple(owned),
    )


def _grown(box: Box, by: float) -> Box:
    return Box(box.xmin - by, box.ymin - by, box.xmax + by, box.ymax + by)


def box_conflict(
    box: Box,
    obstacles: SheetObstacles,
    *,
    gap: float = GAP_M,
    owner: str | None = None,
) -> str | None:
    """Why ``box`` is not a clear spot, or None when it is.

    Clear means: inside the border less ``gap``, and ``gap`` from every
    keep-out, every view outline, every text box and every line of annotation
    ink.  A PICTORIAL outline blocks too: its empty corners excuse a leader
    clipping it (the audit's rule), not a block of text or a whole view laid
    over the picture.  Given the ``owner`` view of the text being placed, it
    also keeps one text height (the smaller box's) from every other view's
    annotation text -- the audit's view-crowding clearance."""
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
        if box.gap(other) < gap:
            kind = "pictorial view" if pictorial else "view"
            return f"{kind} {name} {other.format_mm()}"
    for name, other in obstacles.texts:
        if box.gap(other) < gap:
            return f"text {name} {obstacles.text_extent(name).format_mm()}"
    grown = _grown(box, gap)
    for name, segment in obstacles.ink:
        if segment_box_overlap_length(segment, grown) > 0.0:
            return (
                f"ink of {name} ({segment.x0 * 1000:.1f},{segment.y0 * 1000:.1f})->"
                f"({segment.x1 * 1000:.1f},{segment.y1 * 1000:.1f})mm"
            )
    if owner is None:
        return None
    for name, other_owner, other in obstacles.owned:
        if other_owner == owner:
            continue
        clearance = min(box.height, other.height)
        if 0.0 < box.gap(other) < clearance:
            return (
                f"crowding {name} of {other_owner} {other.format_mm()} "
                f"(under {clearance * 1000:.1f} mm)"
            )
    return None


def _leader_findings(
    segments: list[LeaderSegment], obstacles: SheetObstacles
) -> Iterator[str]:
    """The audit findings of the new leader ``segments``, lazily, cheapest
    check first: a run across a foreign (non-pictorial) view, a run through
    any text, a crossing between the new segments, a crossing with a leader
    already on the sheet.

    Only obstacles whose box meets the new segments' bounding box are handed
    to the audit's checks -- nothing outside it can be crossed -- so a
    candidate costs its neighbourhood, not the sheet: the callout search
    runs this per candidate while the build holds the COM seat."""
    if not segments:
        return
    reach = Box(
        min(min(s.x0, s.x1) for s in segments),
        min(min(s.y0, s.y1) for s in segments),
        max(max(s.x0, s.x1) for s in segments),
        max(max(s.y0, s.y1) for s in segments),
    )
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
        if reach.gap(box) == 0.0
    ]
    for crossing in find_leader_crossings(segments, views):
        yield crossing.describe()
    for segment in segments:
        run = Segment(segment.x0, segment.y0, segment.x1, segment.y1)
        for name, box in obstacles.texts:
            if reach.gap(box) > 0.0:
                continue
            if segment_box_overlap_length(run, box) > DEFAULT_TEXT_TOUCH_TOL_M:
                yield (
                    f"{segment.label}'s leader {run.format_mm()} runs through "
                    f"the text of {name} {box.format_mm()}"
                )
    # Pairs among the new segments, then each new segment against each nearby
    # leader: never the sheet's own pairs, which are not ours to judge.
    for crossing in find_leader_leader_crossings(segments):
        yield crossing.describe()
    for leader in obstacles.leaders:
        if (
            max(leader.x0, leader.x1) < reach.xmin
            or min(leader.x0, leader.x1) > reach.xmax
            or max(leader.y0, leader.y1) < reach.ymin
            or min(leader.y0, leader.y1) > reach.ymax
        ):
            continue
        for crossing in find_leader_leader_crossings([*segments, leader]):
            yield crossing.describe()


def leader_conflicts(
    segments: Iterable[LeaderSegment], obstacles: SheetObstacles
) -> list[str]:
    """Every audit finding the new leader ``segments`` would raise: a run
    across a foreign (non-pictorial) view, a crossing with any leader already
    on the sheet (or with each other), or a run through any text."""
    return list(_leader_findings(list(segments), obstacles))


def leader_conflict(
    segments: Iterable[LeaderSegment], obstacles: SheetObstacles
) -> str | None:
    """The first of :func:`leader_conflicts`, or None -- all a search needs."""
    return next(_leader_findings(list(segments), obstacles), None)


def _shift(box: Box, dx: float, dy: float) -> Box:
    return Box(box.xmin + dx, box.ymin + dy, box.xmax + dx, box.ymax + dy)


def shift_candidates(
    box: Box, region: DrawableRegion, *, step: float = STEP_M
) -> Iterator[tuple[float, float]]:
    """Every grid shift that keeps ``box`` on the sheet, nearest first: the
    current spot is always the first candidate, so a clear drawing never
    moves."""
    lo_x = math.ceil((region.xmin - box.xmin) / step)
    hi_x = math.floor((region.xmax - box.xmax) / step)
    lo_y = math.ceil((region.ymin - box.ymin) / step)
    hi_y = math.floor((region.ymax - box.ymax) / step)
    grid = sorted(
        (
            (i, j)
            for i in range(min(lo_x, 0), max(hi_x, 0) + 1)
            for j in range(min(lo_y, 0), max(hi_y, 0) + 1)
        ),
        key=lambda ij: (ij[0] * ij[0] + ij[1] * ij[1], abs(ij[1]), ij),
    )
    for i, j in grid:
        yield round(i * step, 9), round(j * step, 9)


def caption_boxes(
    view: Box, size: tuple[float, float], *, gap: float = GAP_M
) -> tuple[tuple[str, Box], ...]:
    """The caption's places around ``view``, in the drawing's reading order:
    over it (left-aligned), then beside it top-aligned, left then right."""
    width, height = size
    return (
        (
            "caption over the view",
            Box(
                view.xmin, view.ymax + gap, view.xmin + width, view.ymax + gap + height
            ),
        ),
        (
            "caption beside the view, left",
            Box(
                view.xmin - gap - width, view.ymax - height, view.xmin - gap, view.ymax
            ),
        ),
        (
            "caption beside the view, right",
            Box(
                view.xmax + gap, view.ymax - height, view.xmax + gap + width, view.ymax
            ),
        ),
    )


@dataclass(frozen=True)
class HoleCallout:
    """A native hole callout already on the sheet, read back: where its text
    is, its shelf (the horizontal leader run under the text), and the rim it
    points at (centre + radius, at the view's CURRENT position).  SolidWorks
    redraws the leader from the rim to the nearer shelf end wherever the text
    goes, so the planner draws it the same way."""

    label: str
    owner: str
    text: Box
    shelf: Segment
    rim: tuple[float, float, float]  # x, y, radius
    reach: float = 0.12

    def leader(
        self, dx: float, dy: float, view_shift: tuple[float, float]
    ) -> tuple[LeaderSegment, ...]:
        """The leader + shelf with the text moved by (dx, dy) and the view
        (so the rim) by ``view_shift``."""
        cx, cy, radius = self.rim
        cx, cy = cx + view_shift[0], cy + view_shift[1]
        x0, x1 = sorted((self.shelf.x0 + dx, self.shelf.x1 + dx))
        y = self.shelf.y0 + dy
        end_x = min((x0, x1), key=lambda x: math.hypot(x - cx, y - cy))
        angle = math.atan2(y - cy, end_x - cx)
        tip = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        return (
            LeaderSegment(self.label, "dim", tip[0], tip[1], end_x, y, self.owner),
            LeaderSegment(self.label, "dim", x0, y, x1, y, self.owner),
        )


@dataclass(frozen=True)
class GroupPlan:
    """Where a view, its caption and (optionally) its callout go."""

    how: str
    view_dx: float
    view_dy: float
    view: Box
    caption: Box
    callout_dx: float = 0.0
    callout_dy: float = 0.0
    callout_text: Box | None = None
    callout_leader: tuple[LeaderSegment, ...] = ()


def _callout_offsets(callout: HoleCallout, step: float) -> list[tuple[int, int]]:
    reach = int(callout.reach / step)
    return sorted(
        ((i, j) for i in range(-reach, reach + 1) for j in range(-reach, reach + 1)),
        key=lambda ij: (ij[0] * ij[0] + ij[1] * ij[1], ij),
    )


def _callout_spot(
    callout: HoleCallout,
    obstacles: SheetObstacles,
    view_shift: tuple[float, float],
    offsets: list[tuple[int, int]],
    *,
    gap: float,
    step: float,
) -> tuple[float, float, Box, tuple[LeaderSegment, ...]] | str:
    """The clear text spot nearest the (shifted) rim for ``callout``, or the
    nearest rejected spot and its blocker.  Judges ``offsets`` in order (the
    caller trims the list to its remaining budget)."""
    cx, cy, _ = callout.rim
    base_dx = cx + view_shift[0] - (callout.text.xmin + callout.text.xmax) / 2.0
    base_dy = cy + view_shift[1] - (callout.text.ymin + callout.text.ymax) / 2.0
    nearest = None
    for i, j in offsets:
        dx, dy = round(base_dx + i * step, 9), round(base_dy + j * step, 9)
        text = _shift(callout.text, dx, dy)
        reason = box_conflict(text, obstacles, gap=gap, owner=callout.owner)
        if reason is None:
            leader = callout.leader(dx, dy, view_shift)
            reason = leader_conflict(leader, obstacles)
            if reason is None:
                return dx, dy, text, leader
        nearest = nearest or f"text {text.format_mm()}, blocked by {reason}"
    return nearest or "no spot within reach"


def plan_view_group(
    view: Box,
    caption_size: tuple[float, float],
    obstacles: SheetObstacles,
    *,
    label: str,
    view_name: str,
    callout: HoleCallout | None = None,
    gap: float = GAP_M,
    step: float = STEP_M,
    callout_tries: int = 30,
    callout_budget: int = CALLOUT_BUDGET,
) -> GroupPlan:
    """The nearest clear placement of a view, its caption and its callout.

    Shifts are tried nearest first on a ``step`` grid (the current spot
    first, so a clear drawing never moves); at each, the caption over the
    view, then beside it left, then right; then -- for the first
    ``callout_tries`` clear view+caption groups, within ``callout_budget``
    text spots in all -- the callout's text, nearest its rim first, with the
    leader SolidWorks will draw.  Loud when
    nothing clears: the failure names the nearest rejected candidate and its
    blocker, and every box the search read."""
    nearest_group: str | None = None
    nearest_callout: str | None = None
    offsets = _callout_offsets(callout, step) if callout is not None else []
    tried = 0
    spent = 0
    for dx, dy in shift_candidates(view, obstacles.region, step=step):
        where = f"shift ({dx * 1000:+.0f},{dy * 1000:+.0f}) mm"
        moved = _shift(view, dx, dy)
        reason = box_conflict(moved, obstacles, gap=gap)
        if reason is not None:
            nearest_group = (
                nearest_group
                or f"view {moved.format_mm()} at {where}, blocked by {reason}"
            )
            continue
        for how, caption in caption_boxes(moved, caption_size, gap=gap):
            reason = box_conflict(caption, obstacles, gap=gap)
            if reason is not None:
                nearest_group = nearest_group or (
                    f"{how} {caption.format_mm()} at {where}, blocked by {reason}"
                )
                continue
            if callout is None:
                return GroupPlan(how, dx, dy, moved, caption)
            tried += 1
            batch = offsets[: callout_budget - spent]
            spent += len(batch)
            spot = _callout_spot(
                callout,
                obstacles.plus(
                    views=((view_name, moved),), texts=((f"{label} caption", caption),)
                ),
                (dx, dy),
                batch,
                gap=gap,
                step=step,
            )
            if not isinstance(spot, str):
                cdx, cdy, text, leader = spot
                return GroupPlan(how, dx, dy, moved, caption, cdx, cdy, text, leader)
            nearest_callout = (
                nearest_callout or f"{how} at {where}: {callout.label} {spot}"
            )
            if tried >= callout_tries or spent >= callout_budget:
                break
        if tried >= callout_tries or spent >= callout_budget:
            break
    rejected = [f"nearest rejected group: {nearest_group or 'none'}"]
    if callout is not None:
        rejected.append(
            f"{tried} clear view+caption group(s) and {spent} text spot(s) "
            f"(budget {callout_budget}) tried for {callout.label} "
            f"({callout.text.width * 1000:.1f} x {callout.text.height * 1000:.1f} mm), "
            f"nearest: {nearest_callout or 'none'}"
        )
    raise RuntimeError(
        f"{label}: no clear place for view {view.format_mm()} + caption "
        f"({caption_size[0] * 1000:.1f} x {caption_size[1] * 1000:.1f} mm) on a "
        f"{step * 1000:.0f} mm grid; "
        + "; ".join(rejected)
        + f". Sheet: {obstacles.describe()}"
    )
