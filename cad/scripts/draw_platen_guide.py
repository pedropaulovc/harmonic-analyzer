r"""Create the curated machinist drawing for the platen guide.

The SLDPRT remains authoritative.  This recipe supplies only the platen-guide
views, dimensions, hole groups, and manufacturing notes; shared sheet/template,
leader, reopen, and artifact behavior lives in ``_drawing_common``.

Run with SolidWorks open::

    uv run python cad\scripts\draw_platen_guide.py platen-guide
"""

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
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    insert_hole_table,
    new_project_drawing,
    read_required_view_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_platen_guide import HOLE_X as THROUGH_X
from build_platen_guide import SCREW_STATION_X as BLIND_X
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
)


SPEC = DRAWINGS_BY_NAME["platen_guide"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# The 1:1 front view is 300 mm long and centred at sheet X=0.190 m, so its
# left end is X=0.040 m.  The circular-edge pick Y was measured and then
# read-validated against every expected attached entity in live SolidWorks.
FRONT_LEFT_X_M = 0.040
FRONT_VIEW_Y_M = 0.110
FRONT_HOLE_Y_M = 0.1111
FRONT_BOTTOM_Y_M = FRONT_HOLE_Y_M - 0.0025
HOLE_TABLE_X_M = 0.014
HOLE_TABLE_Y_M = 0.258
THREAD_DESIGNATION = "#4-40 UNC-2B"
THREAD_MAJOR_DIA_MM = 2.845
THREAD_PITCH_MM = 25.4 / 40.0
THREAD_TAP_DRILL_MM = 2.261


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    drawing_model, sheet = new_project_drawing(adapter, property_view=PART_STEM)
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Platen Guide Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen guide; manufacturing drawing; #4-40 UNC",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(
        adapter, str(SOURCE), "*Front", 0.190, FRONT_VIEW_Y_M, scale=(1, 1)
    )
    read_required_view_properties(
        adapter,
        front,
        (
            "Number", "Revision", "Title", "Material Specification", "Finish",
            "Quantity", "Manufacturing Notes",
        ),
        required=(
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes",
        ),
    )
    right = place_view(adapter, str(SOURCE), "*Right", 0.370, 0.110, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", 0.285, 0.210, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    thread_seeds, thread_instances = import_cosmetic_threads(adapter, front)
    expected_thread_instances = len(BLIND_X)
    if thread_instances != expected_thread_instances:
        raise RuntimeError(
            f"front view has {thread_seeds} cosmetic-thread seed(s) / "
            f"{thread_instances} instance(s); expected {expected_thread_instances}"
        )
    removed_thread_notes = remove_notes_matching(adapter, "#4-40")
    _telemetry.info(
        f"front view imported {thread_seeds} cosmetic-thread seed(s) as "
        f"{thread_instances} instance(s); removed {removed_thread_notes} "
        "automatic callout note(s)"
    )

    # Keep only overall length; hole coordinates live in the native hole table.
    curate_view_dimensions(
        adapter, front, keep={"Length": (0.190, 0.135)}, view_label="front"
    )
    curate_view_dimensions(
        adapter,
        right,
        keep={"Depth": (0.370, 0.095), "Height": (0.385, 0.110)},
        view_label="right",
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    stations = tuple(sorted((*THROUGH_X, *BLIND_X)))
    insert_hole_table(
        adapter,
        front,
        datum_xy=(FRONT_LEFT_X_M, FRONT_BOTTOM_Y_M),
        hole_points=tuple(
            (FRONT_LEFT_X_M + station / 1000.0, FRONT_HOLE_Y_M)
            for station in stations
        ),
        anchor_xy=(HOLE_TABLE_X_M, HOLE_TABLE_Y_M),
        label="platen-guide",
    )

    # Native datum reference frame and feature controls replace former notes 5-7.
    # Right view shows the 10 mm depth: left edge is the blind-hole entry face A.
    datum_a_edge = (0.365, 0.110)
    datum_b_edge = (0.190, FRONT_BOTTOM_Y_M)
    datum_c_edge = (FRONT_LEFT_X_M, FRONT_HOLE_Y_M)
    add_datum_feature(
        adapter,
        right,
        edge_xy=datum_a_edge,
        symbol_xy=(0.350, 0.132),
        datum="A",
        label="platen-mating face",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=datum_b_edge,
        symbol_xy=(0.190, 0.098),
        datum="B",
        label="guide bottom edge",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=datum_c_edge,
        symbol_xy=(0.028, FRONT_HOLE_Y_M),
        datum="C",
        label="guide end edge",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=datum_a_edge,
        frame_xy=(0.325, 0.145),
        characteristic="flatness",
        tolerance="0.10",
        label="platen-mating face flatness",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(0.375, 0.110),
        frame_xy=(0.382, 0.145),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("A",),
        label="guide opposite-face parallelism",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_LEFT_X_M + BLIND_X[0] / 1000.0, FRONT_HOLE_Y_M),
        frame_xy=(0.105, 0.155),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="9X",
        label="guide hole-pattern position",
    )
    add_surface_finish(
        adapter,
        right,
        edge_xy=datum_a_edge,
        symbol_xy=(0.335, 0.170),
        roughness_ra="3.2",
        label="platen-mating face finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.075)

    return await finalize_drawing(
        adapter, OUTPUTS, pdf_title="Platen Guide Manufacturing Drawing"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
