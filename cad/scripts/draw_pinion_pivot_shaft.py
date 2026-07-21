r"""Create the curated machinist drawing for the pinion strap torque shaft.

A plain Ø6.35 turned steel shaft with a shallow spherical crown at each end.
Modelled on the fulcrum-shaft slice: a 2:1 end view carries the diameter, the
1:1 side view carries the length, and a 1:2 isometric stays clear of the title
block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_pivot_shaft.py pinion-pivot-shaft
"""

from __future__ import annotations

import argparse
import math
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
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_pivot_shaft_spec import CAP_SAG, SHAFT_DIA as SHAFT_DIA, SHAFT_LEN
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_pivot_shaft"]
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
END_VIEW_SCALE = 4.0
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + SHAFT_LEN * SHEET_SCALE[0] / 2000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.355, 0.205)
# 1:2, like fulcrum-shaft's identical long turned shaft: at 1:1 a 192 mm
# isometric bar runs over the right zone border, so the pictorial is halved and
# a scale callout keeps the title block honest.
ISO_SCALE = (1, 2)

FRONT_KEEP = {
    "ShaftDia": (0.055, 0.167),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.025),
}
DIMENSION_CALLOUTS = {
    "ShaftDia": "NOMINAL REF ONLY\nFINAL LIMITS\n6.350 MAX / 6.330 MIN",
    "Depth": "+/-0.25 CYLINDRICAL BODY\nBETWEEN CROWN ROOT CIRCLES",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-pivot-shaft source", await adapter.open_model(str(SOURCE)))
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
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Torque Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion torque shaft; pivot shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
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
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    end_radius = SHAFT_DIA * END_VIEW_SCALE / 2000.0
    end_circle = (FRONT_CENTER[0] + end_radius, FRONT_CENTER[1])
    end_upper = (
        FRONT_CENTER[0] + end_radius * math.cos(math.radians(50.0)),
        FRONT_CENTER[1] + end_radius * math.sin(math.radians(50.0)),
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=end_upper,
        frame_xy=(0.065, 0.250),
        characteristic="cylindricity",
        tolerance="0.01",
        label="pinion pivot cylindrical body",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=end_circle,
        symbol_xy=(0.035, 0.222),
        datum="A",
        label="pinion pivot cylindrical-body axis",
    )
    right_crown = (
        RIGHT_CENTER[0] + (SHAFT_LEN / 2.0 + CAP_SAG) / 1000.0,
        RIGHT_CENTER[1],
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=right_crown,
        frame_xy=(0.245, 0.250),
        characteristic="profile_surface",
        tolerance="0.05",
        datums=("A",),
        quantity="BOTH CROWNS",
        label="pinion pivot crown profile",
        entity_type="SILHOUETTE",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=end_circle,
        symbol_xy=(0.075, 0.222),
        roughness_ra="1.6",
        label="pinion pivot bearing finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.140)
    add_property_linked_note(adapter, "Iso View Note", 0.325, 0.157)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Torque Shaft Manufacturing Drawing",
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
