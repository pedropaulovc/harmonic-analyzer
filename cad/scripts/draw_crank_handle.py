r"""Create the curated machinist drawing for the crank handle.

A turned, ebonized oak pear grip (book ch. 11).  User ruling 2026-09-29: the
brass ferrule MHA-150 and the flanged steel butt cup MHA-153 are separate
parts, so this sheet prints only the oak -- a tenon for the ferrule at the
crank end, a waisted neck, a smooth twin-arc swell to the Ø21 max, and a
trimmed butt with a counterbore for the cup.  The pear silhouette is two
internally-tangent arcs, so the swell/neck/butt diameters derive from the
profile and cannot be marked without over-defining; the print dimensions the
tenon, the axial stations from the tenon shoulder (datum B) and the
counterbore in the front profile view, and gives the diameters as a
basic-profile note.  The profile sketches on the Front plane, so every marked
profile dimension imports into the front view (handle axis horizontal).

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_handle.py crank-handle
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from crank_handle_spec import (
    BASIC_DIMENSIONS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GEOMETRIC_TOLERANCES_MM,
    HANDLE_MAX_DIA,
    NECK_R,
    PEAK_X,
    PIVOT_BORE_DIA,
    SHOULDER_X,
    TENON_DIA,
    TENON_X0,
    TRIM_X,
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

# Front view (XY): the pear lies horizontal, axis along +X, tenon at the left
# and butt at the right.  SolidWorks centres the view on the oak's extent.
FRONT_BBOX_CX = (TENON_X0 + TRIM_X) / 2.0
FRONT_CENTER = (0.150, 0.178)
RIGHT_CENTER = (0.285, 0.205)
ISO_CENTER = (0.350, 0.150)

TENON_R = TENON_DIA / 2.0


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + model_y_mm * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    "WoodLength": (0.155, 0.128),
    "TenonLength": (_front_x((TENON_X0 + SHOULDER_X) / 2.0), 0.212),
    "TenonDia": (0.068, 0.178),
    "PeakStation": (0.150, 0.242),
    "CounterboreDepth": (0.202, 0.222),
    "CounterboreDia": (0.232, 0.178),
}
RIGHT_KEEP = {
    "PivotBoreDia": (0.360, 0.220),
}
# Every band renders from its model dimension; the callout retains only
# process intent.
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "THRU - REAM",
}

# Datum B is the tenon shoulder, picked on its lower edge so the upper side
# stays free for the tenon runout frame.
SHOULDER_PICK = (_front_x(SHOULDER_X), _front_y(-(TENON_R + NECK_R) / 2.0))
TENON_PICK = (_front_x((TENON_X0 + SHOULDER_X) / 2.0), _front_y(TENON_R))


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Handle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle; turned oak pear grip; ferrule tenon and cup counterbore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
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
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, imported, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, imported, DRAWING_PRECISION_BY_NAME)
    front_by_name = {dimension_name(adapter, a): a for a in front_annotations}
    for station in sorted(BASIC_DIMENSIONS):
        annotation = front_by_name[station]
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"{station} has no display dimension to box")
        set_basic_dimension(adapter, display, label=f"{station} profile station")
    add_view_centerline(
        adapter,
        front,
        face_xy=(_front_x(PEAK_X - 1.0), _front_y(0.0)),
        label="crank handle turning axis",
    )
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to crank-handle end view")

    bore_top = (
        RIGHT_CENTER[0],
        RIGHT_CENTER[1] + PIVOT_BORE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    profile_peak = (
        _front_x(PEAK_X),
        _front_y(HANDLE_MAX_DIA / 2.0),
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=bore_top,
        symbol_xy=(RIGHT_CENTER[0], 0.245),
        datum="A",
        label="reamed bore datum axis",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=SHOULDER_PICK,
        symbol_xy=(0.050, 0.150),
        datum="B",
        label="tenon shoulder face",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=SHOULDER_PICK,
        frame_xy=(0.020, 0.120),
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_MM["shoulder perpendicularity"],
        datums=("A",),
        quantity="DATUM B FACE",
        label="tenon shoulder perpendicularity",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=TENON_PICK,
        frame_xy=(0.020, 0.250),
        characteristic="total_runout",
        tolerance=GEOMETRIC_TOLERANCES_MM["tenon total runout"],
        datums=("A",),
        quantity="TENON OD",
        label="tenon total runout",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=profile_peak,
        frame_xy=(0.180, 0.263),
        characteristic="profile_surface",
        tolerance=GEOMETRIC_TOLERANCES_MM["turned handle profile"],
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
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
