r"""Create the curated cone-platform pivot shoulder-screw drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Mapping

from cone_pivot_screw_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, run_build
from _drawing_project_layout import repair_project_drawing_layout
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_surface_finish,
    auto_arrange_view_dimensions,
    curate_view_dimensions,
    import_cosmetic_threads,
    set_hidden_lines_removed,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_entities import CircleEdge, FeatureFace, ModelEntities
from _gtol_spec import CylinderFace, PlanarFace
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from _surface_finish import surface_finish_by_key
from cone_pivot_screw_spec import (
    HEAD_DIA,
    SLOT_W,
    SHOULDER_DIA,
    SHOULDER_LEN,
    SURFACE_FINISHES,
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

# The measured 6:1 decorated views exhausted rigid packing without fitting the
# ASME B border/title block. Keep native text sizes and annotation coverage;
# reduce geometric magnification and require the same fresh packing checks.
SHEET_SCALE = (4.0, 1.0)
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
ENTITY_ROLES = {
    "thread_end": CircleEdge(THREAD_SOLID_DIA / 2.0, (0, -UNDERHEAD_LEN, 0), (0, 1, 0)),
    "head_bearing": CircleEdge(HEAD_DIA / 2.0, (0, 0, 0), (0, 1, 0)),
    "shoulder_end": CircleEdge(SHOULDER_DIA / 2.0, (0, -SHOULDER_LEN, 0), (0, 1, 0)),
    "slot_wall": PlanarFace((0, 0, 1), -SLOT_W / 2.0),
}


def _decorate(adapter: Any, side: Any, end: Any, _iso: Any) -> dict[str, Any]:
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

    source_model = _early_bound(side, "IView").ReferencedDocument
    roles = ModelEntities(source_model).resolve(ENTITY_ROLES)
    add_datum_feature(
        adapter,
        side,
        entity=roles["thread_end"],
        datum="A",
        label="thread pitch-diameter datum feature",
        callout_below=f"{THREAD} THREAD",
    )
    for role, below_text, label in (
        ("shoulder_end", "SHOULDER OD", "shoulder total runout"),
        ("head_bearing", "HEAD OD", "head total runout"),
    ):
        add_feature_control_frame(
            adapter,
            end,
            entity=roles[role],
            characteristic="total_runout",
            tolerance=GEOMETRIC_TOLERANCES_MM[label],
            datums=("A",),
            quantity=below_text,
            label=label,
        )
    add_feature_control_frame(
        adapter,
        side,
        entity=roles["head_bearing"],
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_MM["head bearing face perpendicularity"],
        datums=("A",),
        quantity="HEAD BEARING FACE",
        label="head bearing face perpendicularity",
    )
    add_feature_control_frame(
        adapter,
        side,
        entity=roles["shoulder_end"],
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_MM["shoulder end perpendicularity"],
        datums=("A",),
        quantity="SHOULDER END FACE",
        label="shoulder end perpendicularity",
    )
    add_feature_control_frame(
        adapter,
        right,
        entity=roles["slot_wall"],
        entity_type="FACE",
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["slot median-plane position"],
        datums=("A",),
        quantity="SLOT MEDIAN PLANE",
        label="slot median-plane position",
    )
    add_surface_finish(
        adapter,
        end,
        entity=roles["shoulder_end"],
        control=surface_finish_by_key(SURFACE_FINISHES, "ground_shoulder"),
        label="ground shoulder finish",
    )
    auto_arrange_view_dimensions(adapter, (side, end, right))
    return {"right": right}


def _layout(adapter: Any, views: Mapping[str, Any], notes: Mapping[str, Any]) -> None:
    from _drawing_native_layout import AxisLink, LayoutNote
    from _drawing_view_packing import Axis, AxisOrder

    repair_project_drawing_layout(
        adapter,
        views=views,
        alignments=(AxisLink(Axis.Y, "side", "right"),),
        orderings=(AxisOrder(Axis.X, "side", "right"),),
        notes=(
            LayoutNote("manufacturing", notes["manufacturing"].GetAnnotation()),
            LayoutNote("end-caption", notes["end-caption"].GetAnnotation(), "end"),
        ),
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
    side_centerline_face=FeatureFace("Shoulder", CylinderFace(SHOULDER_DIA)),
    decorate=_decorate,
    layout=_layout,
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
