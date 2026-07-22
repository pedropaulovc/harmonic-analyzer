r"""Create the curated cone-platform pivot shoulder-screw drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_surface_finish,
    curate_view_dimensions,
    import_cosmetic_threads,
    set_hidden_lines_removed,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from cone_pivot_screw_spec import (
    SHOULDER_DIA,
    SHOULDER_LEN,
    THREAD,
    THREAD_DESIGNATION,
    THREAD_SOLID_DIA,
    UNDERHEAD_LEN,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view, remove_notes_matching


SPEC = DRAWINGS_BY_NAME["cone_pivot_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

SHEET_SCALE = (6.0, 1.0)
END_KEEP = {
    "HeadDiaDim": (0.028, 0.176),
    "ShoulderDiaDim": (0.028, 0.124),
}
SIDE_KEEP = {
    "HeadHt": (0.190, 0.240),
    "ShoulderLg": (0.165, 0.185),
    "ThreadLg": (0.238, 0.132),
}
SLOT_KEEP = {
    "SlotWDim": (0.285, 0.242),
    "SlotDepth": (0.325, 0.215),
}
SIDE_DIMENSION_CALLOUTS = {
    "ThreadLg": THREAD_DESIGNATION,
}
DIMENSION_CALLOUTS: dict[str, str] = {}


def _circular_edge(
    adapter: Any,
    view: Any,
    *,
    center_y_mm: float,
    radius_mm: float,
    label: str,
) -> Any:
    """Return the unique visible circular edge matching model-space geometry."""
    view = _early_bound(view, "IView")
    components = adapter._attempt(lambda: view.GetVisibleComponents()) or (None,)
    matches: list[Any] = []
    seen: list[tuple[float, float]] = []
    edge_count = 0
    for component in components:
        edges = (
            adapter._attempt(lambda c=component: view.GetVisibleEntities2(c, 1)) or ()
        )
        edge_count += len(edges)
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = curve.CircleParams or ()
            if len(params) != 7:
                continue
            center_y = float(params[1]) * 1000.0
            radius = float(params[6]) * 1000.0
            seen.append((center_y, radius))
            if abs(center_y - center_y_mm) <= 0.02 and abs(radius - radius_mm) <= 0.02:
                matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one visible circular edge at y={center_y_mm:g} "
            f"r={radius_mm:g} mm, found {len(matches)}; "
            f"components={len(components)} edges={edge_count} circles={seen}"
        )
    return matches[0]


def _decorate(adapter: Any, side: Any, end: Any, _iso: Any) -> None:
    """Add the native GD&T and finish controls required by the shoulder joint."""
    right = place_view(adapter, str(SOURCE), "*Right", 0.285, 0.170, scale=SHEET_SCALE)
    set_hidden_lines_removed(adapter, right)
    curate_view_dimensions(adapter, right, keep=SLOT_KEEP, view_label="slot profile")

    thread_seeds, thread_instances = import_cosmetic_threads(adapter, side)
    if thread_instances != 1:
        raise RuntimeError(
            f"side view has {thread_seeds} cosmetic-thread seed(s) / "
            f"{thread_instances} instance(s); expected 1"
        )
    removed_thread_notes = remove_notes_matching(adapter, THREAD)
    _telemetry.info(
        f"side view imported {thread_seeds} cosmetic-thread seed(s) as "
        f"{thread_instances} instance(s); removed {removed_thread_notes} "
        "automatic callout note(s)"
    )

    thread_end = _circular_edge(
        adapter,
        side,
        center_y_mm=-UNDERHEAD_LEN,
        radius_mm=THREAD_SOLID_DIA / 2.0,
        label="thread datum edge",
    )
    add_datum_feature(
        adapter,
        side,
        edge_entity=thread_end,
        symbol_xy=(0.115, 0.130),
        datum="A",
        label="thread pitch-diameter datum feature",
        callout_below=f"{THREAD} THREAD",
    )
    for edge_xy, frame_xy, below_text, label in (
        ((0.070, 0.16980), (0.108, 0.182), "SHOULDER OD", "shoulder total runout"),
        ((0.070, 0.17850), (0.108, 0.204), "HEAD OD", "head total runout"),
    ):
        add_feature_control_frame(
            adapter,
            end,
            edge_xy=edge_xy,
            frame_xy=frame_xy,
            characteristic="total_runout",
            tolerance="0.05",
            datums=("A",),
            quantity=below_text,
            label=label,
        )
    add_feature_control_frame(
        adapter,
        side,
        edge_xy=(0.215, 0.20465),
        frame_xy=(0.240, 0.212),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        quantity="HEAD BEARING FACE",
        label="head bearing face perpendicularity",
    )
    add_feature_control_frame(
        adapter,
        side,
        edge_entity=_circular_edge(
            adapter,
            side,
            center_y_mm=-SHOULDER_LEN,
            radius_mm=SHOULDER_DIA / 2.0,
            label="shoulder end edge",
        ),
        frame_xy=(0.125, 0.170),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        quantity="SHOULDER END FACE",
        label="shoulder end perpendicularity",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(0.2898, 0.219),
        frame_xy=(0.325, 0.245),
        characteristic="position",
        tolerance="0.10",
        datums=("A",),
        quantity="SLOT MEDIAN PLANE",
        label="slot median-plane position",
    )
    add_surface_finish(
        adapter,
        end,
        edge_xy=(0.08400, 0.13600),
        symbol_xy=(0.125, 0.136),
        roughness_ra="0.8",
        label="ground shoulder finish",
    )
RECIPE = FastenerSheet(
    title="Cone Pivot Screw Manufacturing Drawing",
    keywords="cone pivot screw; slotted shoulder screw; made fastener",
    scale=SHEET_SCALE,
    side_view="*Front",
    # Look from the threaded tail so the controlled ground shoulder is visible
    # inside the larger head outline; the head-end view occludes that shoulder.
    end_view="*Bottom",
    side_center=(0.190, 0.170),
    end_center=(0.070, 0.150),
    iso_center=(0.370, 0.170),
    end_keep=END_KEEP,
    dimension_callouts=DIMENSION_CALLOUTS,
    side_keep=SIDE_KEEP,
    side_dimension_callouts=SIDE_DIMENSION_CALLOUTS,
    note_xy=(0.020, 0.105),
    end_note_xy=(0.020, 0.245),
    side_centerline_face_xy=(0.190, 0.145),
    decorate=_decorate,
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_fastener_sheet(
        adapter, source=SOURCE, property_view=PART_STEM, outputs=OUTPUTS, recipe=RECIPE
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
