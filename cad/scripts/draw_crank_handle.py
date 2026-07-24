r"""Create the curated machinist drawing for the crank handle.

A turned stained-oak pear grip (book ch. 11): an integral collar profile at the crank end,
a waisted neck, a smooth twin-arc swell to the Ø22 max, and a blunt domed butt
with a flat cap.  The pear silhouette is two internally-tangent arcs, so the
swell/neck/butt diameters derive from the profile and cannot be marked without
over-defining; the print dimensions the clean AXIAL stations (overall length,
collar length, peak station) in the front profile view and gives the diameters
as a turning-schedule note.  The profile sketches on the Front plane, so every
marked dimension imports into the front view (handle axis horizontal).

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_handle.py crank-handle
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
    add_view_centerline,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_view_properties,
    set_basic_dimension,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import fit_limits
from crank_handle_spec import (
    COLLAR_DIA,
    HANDLE_LENGTH,
    HANDLE_MAX_DIA,
    PEAK_X,
    PIVOT_BORE_BAND,
    PIVOT_BORE_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_handle"]
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

SHEET_SCALE = (2.0, 1.0)

# Front view (XY): the pear lies horizontal, axis along +X, collar at the left
# (x=0) and butt at the right (x=HANDLE_LENGTH).  Centre on the axial midspan.
FRONT_BBOX_CX = HANDLE_LENGTH / 2.0
FRONT_CENTER = (0.150, 0.178)
RIGHT_CENTER = (0.285, 0.205)
ISO_CENTER = (0.350, 0.150)

COLLAR_R = COLLAR_DIA / 2.0


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + model_y_mm * SHEET_SCALE[0] / 1000.0


COLLAR_R_SHEET = COLLAR_R * SHEET_SCALE[0] / 1000.0

FRONT_KEEP = {
    "HandleLength": (0.150, 0.128),
    "CollarLength": (0.070, 0.222),
    "PeakStation": (0.150, 0.242),
}
RIGHT_KEEP = {
    "PivotBoreDia": (0.360, 0.220),
}
DIMENSION_CALLOUTS = {
    "HandleLength": "+0.00/-0.25 OVERALL",
    "PivotBoreDia": (
        "NOMINAL REF ONLY\n"
        f"FINAL LIMITS {fit_limits(PIVOT_BORE_DIA, PIVOT_BORE_BAND, decimals=2)} THRU"
    ),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    drawing_model, sheet = new_project_drawing(
        adapter,
        category=SPEC.category,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Handle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle; turned oak pear grip; integral collar profile",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    read_required_view_properties(
        adapter,
        front,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)
    front.SetDisplayTangentEdges2(0)
    if int(front.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError("failed to hide crank-handle tangent edges")
    front.UpdateViewDisplayGeometry()

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *right_annotations], DIMENSION_CALLOUTS
    )
    front_by_name = {dimension_name(adapter, a): a for a in front_annotations}
    for station in ("CollarLength", "PeakStation"):
        annotation = front_by_name[station]
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"{station} has no display dimension to box")
        set_basic_dimension(adapter, display, label=f"{station} profile station")
    add_view_centerline(
        adapter,
        front,
        face_xy=(_front_x(35.0), _front_y(0.0)),
        label="crank handle turning axis",
    )
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to crank-handle end view")

    collar_od_top = (RIGHT_CENTER[0], RIGHT_CENTER[1] + COLLAR_R_SHEET)
    bore_top = (
        RIGHT_CENTER[0],
        RIGHT_CENTER[1] + PIVOT_BORE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    collar_face = (_front_x(0.0), _front_y(COLLAR_R * 0.55))
    profile_peak = (
        _front_x(PEAK_X),
        _front_y(HANDLE_MAX_DIA / 2.0),
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=collar_od_top,
        symbol_xy=(RIGHT_CENTER[0], 0.245),
        # Native readback is session-sensitive at this on-axis attachment: one
        # established session normalized Y down by 9.371 um, while a freshly
        # restarted session retained the requested point within 0.02 um.  Both
        # are the same legal placement, so gate the bounded normalization rather
        # than one session's exact floating-point result.
        expected_position_xy=(RIGHT_CENTER[0], 0.245),
        position_tolerance_m=0.001,
        datum="A",
        label="collar OD datum axis",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=collar_face,
        symbol_xy=(0.040, 0.198),
        datum="B",
        label="flat collar face",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=collar_face,
        frame_xy=(0.020, 0.155),
        characteristic="perpendicularity",
        tolerance="0.10",
        datums=("A",),
        quantity="DATUM B FACE",
        label="flat collar end perpendicularity",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=bore_top,
        frame_xy=(0.350, 0.263),
        characteristic="total_runout",
        tolerance="0.10",
        datums=("A",),
        quantity="FULL BORE LENGTH",
        label="full-length bore total runout",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=profile_peak,
        frame_xy=(0.180, 0.263),
        characteristic="profile_surface",
        tolerance="0.50",
        datums=("A", "B"),
        quantity="TURNED GRIP PROFILE - SEE NOTE",
        label="turned handle profile",
        entity_type="SILHOUETTE",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.080)
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.116)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
