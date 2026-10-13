"""Model-to-sheet projection through a freshly created detail view.

``CreateDetailViewAt4`` and the ``SetViewPosition`` that places a detail by
its outline leave the view's ``IView.ModelToViewTransform`` in the frame the
view had before SolidWorks recentred it, while ``GetOutline`` (the ink) and
``Position`` have already moved on. Rebuilds, re-reads and idle time each bring
the transform up to date only some of the time. ``IView.UpdateViewDisplayGeometry``
"accesses new view geometry before Microsoft has repainted the window"
(``types/IView/UpdateViewDisplayGeometry.md``), and behind it the read has
always been current, so every projection here is read behind it.

Evidence (#1336). ``drawing:dt_cone_swing_platform`` read detail B straight
after placement and settled it with rebuilds. The first read was stale in 41
of 41 leaves, and 4 of them were still stale after three rebuilds.
``drawing:dt_cone_gear_shaft`` used the same rebuild loop for its tip detail
until 660229544 put the barrier in front of every read. Over the 35 days of
App Insights to 2026-10-13, 32 of the 35 leaves without the barrier read stale
first, and one never settled. All 15 leaves with the barrier read current
first time. A seat probe (leaf 20261013T052718Z-1-4b76316f) ran 20 throwaway
detail views through the same sequence. All 20 read 102.55 mm stale first,
and all 4 behind the barrier then read current. The same leaf's real detail
B, settled the old way, stayed stale through three rebuilds and failed.
"""

from __future__ import annotations

import time
from typing import Any

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_projection import model_point_in_view
import _telemetry


# The barrier is expected to leave the first read current.  If it does not,
# a rebuild and another barrier are retried until this many seconds have
# passed since the first read; ``reads`` and ``waited_s`` on the span show
# how often that happens.
DETAIL_SETTLE_BUDGET_S = 5.0


@_telemetry.traced("drawing.detail_projection_settle", label_param="label")
def settle_detail_projection(
    adapter: Any,
    detail: Any,
    xyz: tuple[float, float, float],
    *,
    ink_xy: tuple[float, float],
    tolerance_xy: tuple[float, float],
    label: str,
) -> tuple[float, float]:
    """Project ``xyz`` through ``detail`` once its transform agrees with its ink.

    ``ink_xy`` is where the placed detail draws ``xyz`` (its outline centre).
    The read must land within ``tolerance_xy`` of it, per axis. The span records
    one control read taken before the barrier (``unrefreshed_dx_mm`` /
    ``unrefreshed_dy_mm``). It also records how many barriered reads and
    rebuilds the transform needed and the seconds they took.
    """
    view = _early_bound(detail, "IView")

    def offset(projected: tuple[float, float]) -> tuple[float, float]:
        return (projected[0] - ink_xy[0], projected[1] - ink_xy[1])

    def agrees(projected: tuple[float, float]) -> bool:
        dx, dy = offset(projected)
        return abs(dx) <= tolerance_xy[0] and abs(dy) <= tolerance_xy[1]

    started = time.perf_counter()
    unrefreshed = model_point_in_view(
        adapter, detail, xyz, label=f"{label}, unrefreshed"
    )
    reads = rebuilds = 0
    while True:
        view.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, detail, xyz, label=f"{label}, read {reads}"
        )
        reads += 1
        waited = time.perf_counter() - started
        if agrees(projected) or waited >= DETAIL_SETTLE_BUDGET_S:
            break
        rebuild_drawing(adapter, label=f"settle {label}")
        rebuilds += 1
    unrefreshed_dx, unrefreshed_dy = offset(unrefreshed)
    dx, dy = offset(projected)
    _telemetry.annotate(
        reads=reads,
        rebuilds=rebuilds,
        waited_s=round(waited, 3),
        stale_before_refresh=not agrees(unrefreshed),
        unrefreshed_dx_mm=round(unrefreshed_dx * 1000.0, 3),
        unrefreshed_dy_mm=round(unrefreshed_dy * 1000.0, 3),
        dx_mm=round(dx * 1000.0, 3),
        dy_mm=round(dy * 1000.0, 3),
    )
    if not agrees(projected):
        raise RuntimeError(
            f"{label} projects its centre to {projected} while its outline is "
            f"centred on {ink_xy}; after {reads} refreshed reads, {rebuilds} "
            f"rebuilds and {waited:.2f} s it reads outline "
            f"{tuple(float(value) for value in view.GetOutline())}, Position "
            f"{tuple(float(value) for value in view.Position)}"
        )
    return projected
