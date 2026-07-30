r"""Create the curated machinist drawing for the pinion cam-follower pin.

A short Ø4 turned steel stud with a shallow domed outer end.  The sheet runs at
4:1 (the pin is only 15 mm long): an 8:1 end view carries the diameter, the 4:1
side view carries the length, and a 4:1 isometric (matching the sheet scale)
sits clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_cam_pin.py pinion-cam-pin
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from pinion_cam_pin_spec import GEOMETRIC_TOLERANCES_MM

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
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_cam_pin_spec import (
    CAP_RADIUS,
    CAP_SAG,
    PIN_DIA as PIN_DIA,
    PIN_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_cam_pin"]
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

SHEET_SCALE = (4.0, 1.0)
END_VIEW_SCALE = 8.0
FRONT_CENTER = (0.070, 0.200)
RIGHT_CENTER = (
    FRONT_CENTER[0] + PIN_LEN * SHEET_SCALE[0] / 2000.0 + 0.055,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.320, 0.200)

FRONT_KEEP = {
    "PinDia": (0.030, 0.235),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.040),
    "CapR": (RIGHT_CENTER[0] + 0.035, RIGHT_CENTER[1] + 0.040),
}
DIMENSION_CALLOUTS = {
    "PinDia": "FINAL SIZE",
    "Depth": "SEATED FLAT END TO CROWN ROOT",
    "CapR": "OUTER CROWN",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-cam-pin source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Cam-Follower Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion cam-follower pin; turned stud; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(8, 1))
    right = place_view(adapter, str(SOURCE), "*Top", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *right_annotations], DIMENSION_CALLOUTS
    )
    set_dimension_precision(adapter, front_annotations, {"PinDia": 3})
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pin end view")

    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="pinion cam-pin shank axis centerline",
    )
    end_radius = PIN_DIA * END_VIEW_SCALE / 2000.0
    # SolidWorks restricts this axis-attached tag and live readback normalizes
    # the intended sheet point by 6.187 mm.  Bound only annotation placement;
    # part dimensions and GD&T remain unchanged.
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + end_radius, FRONT_CENTER[1]),
        symbol_xy=(0.105, 0.228),
        datum="A",
        label="cam-pin cylindrical-shank datum axis",
        position_tolerance_m=0.0065,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + end_radius, FRONT_CENTER[1]),
        symbol_xy=(0.115, 0.180),
        control=surface_finish_by_key(SURFACE_FINISHES, "finished_shank"),
        label="cam-pin finished shank",
    )
    seated_flat_face = model_point_in_view(
        adapter,
        right,
        (PIN_DIA / 2000.0, 0.0, 0.0),
        label="cam-pin seated flat end",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=seated_flat_face,
        frame_xy=(0.220, 0.210),
        characteristic="flatness",
        tolerance=GEOMETRIC_TOLERANCES_MM["cam-pin seated-end flatness"],
        quantity="SEATED END",
        label="cam-pin seated-end flatness",
        entity_type="SILHOUETTE",
    )
    crown_axial = CAP_SAG / 2.0
    crown_radial = math.sqrt(CAP_RADIUS**2 - (CAP_RADIUS - CAP_SAG + crown_axial) ** 2)
    outer_crown_face = model_point_in_view(
        adapter,
        right,
        (
            crown_radial / 1000.0,
            0.0,
            (PIN_LEN + crown_axial) / 1000.0,
        ),
        label="pinion cam-pin outer crown face",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=outer_crown_face,
        frame_xy=(0.245, 0.235),
        characteristic="profile_surface",
        tolerance=GEOMETRIC_TOLERANCES_MM["pinion cam-pin crown profile"],
        datums=(),
        quantity="OUTER CROWN",
        label="pinion cam-pin crown profile",
        entity_type="SILHOUETTE",
    )
    add_attached_note(
        adapter,
        right,
        text=(
            f"OUTER CROWN\n({CAP_SAG:.2f}) REF AXIAL HEIGHT\nCROWN ROOT PLANE TO APEX"
        ),
        entity_xy=outer_crown_face,
        note_xy=(0.250, 0.175),
        label="cam-pin crown size and height",
        entity_type="SILHOUETTE",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.110)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.168)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Cam-Follower Pin Manufacturing Drawing",
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
