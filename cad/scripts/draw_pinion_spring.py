r"""Create the curated machinist drawing for the pinion return leaf spring.

NOT a coil spring: a bent brass leaf.  A 0.8 x 4.0 half-hard brass strip formed
as a flat screw-down foot (31 long, with a #4 foot-screw clearance hole), an R2
bend up to a blade leaning 12.38 deg off the foot plane, then a subtle R1.5 kink
(~20 deg back) to a short free flat.  The profile sketches on the Front plane so
every marked dimension (foot length, both bend radii, the flat) imports into the
front profile view; the top view shows the 4.0-wide foot and the screw hole.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_spring.py pinion-spring
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
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_spring_spec import WIDTH
from build_pinion_spring import (
    BEND_EXIT,
    FLAT_TIP,
    FOOT_END,
    FOOT_TAN,
    FOOT_Y,
    KINK_START,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_spring"]
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

# Front view (XY): the checkmark profile -- the foot runs along the bottom, the
# blade rises to the upper right.  Centre it on the profile's y midspan.
FRONT_BBOX_CX = (
    FOOT_END[0] + max(BEND_EXIT[0], KINK_START[0], FLAT_TIP[0])
) / 2.0
FRONT_BBOX_CY = (FOOT_Y + FLAT_TIP[1]) / 2.0
FRONT_CENTER = (0.130, 0.150)
# Put the narrow top view in the open right-hand field, above the title block
# and clear of the lower-left manufacturing-note band.
TOP_CENTER = (0.300, 0.100)
ISO_CENTER = (0.320, 0.190)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


_FOOT_MID_X = (FOOT_END[0] + FOOT_TAN[0]) / 2.0
_BLADE_MID = (
    (BEND_EXIT[0] + KINK_START[0]) / 2.0,
    (BEND_EXIT[1] + KINK_START[1]) / 2.0,
)
FRONT_KEEP = {
    "FootLen": (_front_x(_FOOT_MID_X), 0.088),
    "BendR": (0.036, 0.120),
    "KinkR": (0.150, 0.220),
    "FlatLen": (0.205, 0.188),
}
TOP_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS: dict[str, str] = {
    "FootLen": "+/-0.10 TRUE LENGTH\nFREE END TO BEND TANGENCY",
    "BendR": "+/-0.10 INSIDE RADIUS",
    "KinkR": "+/-0.10 INSIDE RADIUS",
    "FlatLen": "+/-0.10 FREE-FLAT TANGENT LENGTH",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-spring source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Return Leaf Spring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion return spring; bent brass leaf; formed strip",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    if TOP_KEEP:
        curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    else:
        curate_view_dimensions(adapter, top, keep={}, view_label="top")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Datum A is the broad foot face visible in the removed top view. Datum B
    # is one designated long edge, giving the formed-profile angles and hole
    # offset a unique, inspectable direction/reference instead of the former
    # prose-only "foot axis" / "either long edge" wording.
    top_face = TOP_CENTER
    top_long_edge = (
        TOP_CENTER[0],
        TOP_CENTER[1] + WIDTH * SHEET_SCALE[0] / 2000.0,
    )
    # The thin-feature centreline is a real projected model edge in the front
    # view.  SOLIDWORKS does not expose the ribbon interior as a selectable
    # drawing FACE, so attach the broad-face controls to this boundary edge and
    # name the controlled surface explicitly in the FCF quantity compartment.
    blade_face_edge = (_front_x(_BLADE_MID[0]), _front_y(_BLADE_MID[1]))
    add_datum_feature(
        adapter,
        top,
        edge_xy=top_face,
        symbol_xy=(0.250, 0.118),
        datum="A",
        label="spring broad foot face",
        entity_type="FACE",
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=top_long_edge,
        symbol_xy=(0.350, 0.118),
        datum="B",
        label="spring designated long edge",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=top_face,
        frame_xy=(0.350, 0.092),
        characteristic="flatness",
        tolerance="0.10",
        label="spring datum-A face flatness",
        entity_type="FACE",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=blade_face_edge,
        frame_xy=(0.260, 0.150),
        characteristic="parallelism",
        tolerance="0.20",
        datums=("A",),
        quantity="FORMED BROAD FACE",
        label="spring formed broad-face coplanarity",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=blade_face_edge,
        symbol_xy=(0.205, 0.123),
        roughness_ra="0.8",
        label="spring concave blade broad face",
    )
    if add_note(adapter, "TOP VIEW (REMOVED) SCALE 2:1", 0.270, 0.078) is None:
        raise RuntimeError("failed to label removed spring top view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.062)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.164)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Return Leaf Spring Manufacturing Drawing",
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
