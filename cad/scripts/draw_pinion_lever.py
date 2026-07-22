r"""Create the curated machinist drawing for the pinion engage lever.

A clamp hub (Ø13 OD, Ø6.3675 bore) with a tapered grip rod (Ø4 at the hub to Ø6
at the tip) rising 86 mm out of it.  The rod-revolve and hub sketches both live
on the Front plane, so every marked dimension imports into the FRONT view; the
longitudinal section controls the blind bore, end wall, and spherical crown.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_lever.py pinion-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_lever_spec import (
    BORE,
    CAP_RADIUS,
    CAP_SAG,
    HUB_LEN,
    HUB_OD,
    ROD_LEN,
    ROD_ROOT_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_lever"]
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

SHEET_SCALE = (1.0, 1.0)

# Front view (XY): the hub is a Ø13 circle at the origin with the tapered rod
# rising +Y to the tip (model y=ROD_LEN).  bbox y runs -HUB_OD/2..ROD_LEN.
FRONT_BBOX_CY = (ROD_LEN - HUB_OD / 2.0) / 2.0
# At 1:1 the full 86 mm rod leaves enough room for the hub callouts and GD&T
# without crowding the orthographic views.
FRONT_CENTER = (0.078, 0.170)
SECTION_CENTER = (0.190, 0.150)
ISO_CENTER = (0.330, 0.205)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


HUB_R_SHEET = HUB_OD * SHEET_SCALE[0] / 2000.0
BORE_R_SHEET = BORE * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    "HubOd": (0.025, 0.102),
    "HubBore": (0.115, 0.090),
    "RodTipY": (0.044, 0.170),
}
RIGHT_KEEP = {
    "BoreDepth": (0.205, 0.116),
    "EndWall": (0.225, 0.132),
}
DIMENSION_CALLOUTS = {
    "HubBore": "SIZE LIMITS: 6.360 MIN / 6.375 MAX",
    "BoreDepth": "+0.10/-0.00 FULL-DIA DEPTH FROM B; FLAT BOTTOM",
    "EndWall": "+/-0.05 END WALL TO CROWN ROOT PLANE",
    "RodTipY": "+/-0.25 FROM HUB AXIS",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-lever source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Engage Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion engage lever; clamp hub; tapered grip rod",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    set_hidden_lines_visible(adapter, front)
    hub_center = (FRONT_CENTER[0], _front_y(0.0))
    section = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], hub_center[1] - 0.011),
        line_end=(FRONT_CENTER[0], hub_center[1] + 0.018),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="lever longitudinal hub section",
    )
    set_hidden_lines_removed(adapter, section)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, section, keep=RIGHT_KEEP, view_label="section"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *right_annotations], DIMENSION_CALLOUTS
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    bore_top = (hub_center[0], hub_center[1] + BORE_R_SHEET)
    hub_right = (hub_center[0] + HUB_R_SHEET, hub_center[1])
    z_max = HUB_LEN / 2.0
    flat_face_radius = (BORE + HUB_OD) / 4.0
    flat_face = model_point_in_view(
        adapter,
        section,
        (0.0, flat_face_radius / 1000.0, z_max / 1000.0),
        label="lever flat end face",
    )
    grip_edge = (_front_x(ROD_ROOT_DIA / 2.0), _front_y(12.0))
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(hub_center[0] + 0.025, hub_center[1] + 0.030),
        datum="A",
        label="lever final bore axis",
    )
    add_datum_feature(
        adapter,
        section,
        edge_xy=flat_face,
        symbol_xy=(flat_face[0] - 0.025, flat_face[1] - 0.018),
        datum="B",
        label="lever flat end face",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=hub_right,
        frame_xy=(0.145, 0.090),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("A",),
        label="lever hub OD runout",
    )
    add_feature_control_frame(
        adapter,
        section,
        edge_xy=flat_face,
        frame_xy=(0.245, 0.098),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="lever flat-face perpendicularity",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=grip_edge,
        frame_xy=(0.125, 0.245),
        characteristic="profile_surface",
        tolerance="0.10",
        datums=("A", "B"),
        quantity="GRIP PROFILE; BASIC AXIS 5.00 FROM B, 90 DEG TO A, INTERSECTS A",
        label="lever grip profile",
        entity_type="SILHOUETTE",
    )
    add_view_centerline(
        adapter,
        front,
        face_xy=grip_edge,
        label="lever tapered grip axis",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(0.116, 0.070),
        roughness_ra="1.6",
        label="lever finished bore",
    )
    add_attached_note(
        adapter,
        front,
        text=(
            "STRAIGHT CONICAL GRIP PROFILE\n"
            "<MOD-DIAM>4.00+/-0.05 AT BASIC 3.50 FROM HUB AXIS\n"
            "<MOD-DIAM>6.00+/-0.05 AT TIP"
        ),
        entity_xy=grip_edge,
        note_xy=(0.120, 0.235),
        label="lever conical grip size",
        entity_type="SILHOUETTE",
    )
    crown_edge = model_point_in_view(
        adapter,
        section,
        (0.0, 0.0, -(HUB_LEN / 2.0 + CAP_SAG) / 1000.0),
        label="lever spherical crown apex",
    )
    add_attached_note(
        adapter,
        section,
        text=(
            f"SPHERICAL CROWN SR{CAP_RADIUS:.2f}+/-0.10\n"
            "10.00+/-0.10 B TO CROWN ROOT PLANE\n"
            "11.50 REF B TO APEX"
        ),
        entity_xy=crown_edge,
        note_xy=(0.245, 0.155),
        label="lever spherical crown definition",
        entity_type="SILHOUETTE",
    )
    add_feature_control_frame(
        adapter,
        section,
        edge_xy=crown_edge,
        frame_xy=(0.245, 0.180),
        characteristic="profile_surface",
        tolerance="0.10",
        datums=("A", "B"),
        quantity="CROWN",
        label="lever crown profile",
        entity_type="SILHOUETTE",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.045)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.158)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Engage Lever Manufacturing Drawing",
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
