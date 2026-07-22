r"""Create the curated cone-platform pivot shoulder-screw drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_surface_finish,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_drawing import FastenerSheet, build_fastener_sheet


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
    "HeadHt": (0.190, 0.222),
    "ShoulderLg": (0.165, 0.138),
    "ThreadLg": (0.238, 0.132),
}
SIDE_DIMENSION_CALLOUTS = {
    "ThreadLg": "1/4-20 UNC-2A",
}
DIMENSION_CALLOUTS: dict[str, str] = {}


def _decorate(adapter: Any, side: Any, end: Any, _iso: Any) -> None:
    """Add the native GD&T and finish controls required by the shoulder joint."""
    # The innermost circle in the tail-end view is the thread-tail feature. Its
    # native datum-feature tag establishes the derived pitch-diameter axis A.
    add_datum_feature(
        adapter,
        end,
        edge_xy=(0.0853, 0.150),
        symbol_xy=(0.108, 0.150),
        datum="A",
        label="thread pitch-diameter datum feature",
    )
    for edge_xy, frame_xy, label in (
        ((0.070, 0.16905), (0.108, 0.182), "shoulder total runout"),
        ((0.070, 0.17850), (0.108, 0.204), "head total runout"),
    ):
        add_feature_control_frame(
            adapter,
            end,
            edge_xy=edge_xy,
            frame_xy=frame_xy,
            characteristic="total_runout",
            tolerance="0.05",
            datums=("A",),
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
        label="head bearing face perpendicularity",
    )
    add_feature_control_frame(
        adapter,
        end,
        edge_xy=(0.070, 0.13095),
        frame_xy=(0.108, 0.118),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="shoulder end perpendicularity",
    )
    add_surface_finish(
        adapter,
        end,
        edge_xy=(0.08347, 0.13653),
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
    iso_center=(0.310, 0.170),
    end_keep=END_KEEP,
    dimension_callouts=DIMENSION_CALLOUTS,
    side_keep=SIDE_KEEP,
    side_dimension_callouts=SIDE_DIMENSION_CALLOUTS,
    note_xy=(0.020, 0.105),
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
