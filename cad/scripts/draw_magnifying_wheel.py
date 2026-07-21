r"""Create the curated machinist drawing for the magnifying wheel.

A Ø100 spoked cast wheel with a Ø20 grooved hub drum (the 5x ratio) on six
straight spokes and a Ø5 axle bore.  The wheel axis is local +Z, so the FRONT
view is the face (rim / hub / spokes / bore, all real circular edges) and the
RIGHT view is the edge section carrying the rim + hub axial widths.  The face
diameters ride the auto-imported profile marks; the axial widths are added
across the section, the spoke section + count are noted.

Run with SolidWorks open::

    uv run python cad\scripts\draw_magnifying_wheel.py magnifying-wheel
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
    add_edge_dimension,
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
from magnifying_wheel_spec import (
    HUB_AXIAL,
    HUB_DIA,
    RIM_AXIAL,
    RIM_OUTER_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["magnifying_wheel"]
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
FRONT_CENTER = (0.125, 0.150)
RIGHT_CENTER = (0.255, 0.150)
ISO_CENTER = (0.350, 0.150)

_RIM_R = RIM_OUTER_DIA * SHEET_SCALE[0] / 2000.0
_HUB_R = HUB_DIA * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    "RimOuterDiaDim": (FRONT_CENTER[0] - _RIM_R - 0.028, FRONT_CENTER[1] + _RIM_R + 0.006),
    "HubDiaDim": (FRONT_CENTER[0] + _HUB_R + 0.030, FRONT_CENTER[1] - 0.006),
    "BoreDiaDim": (FRONT_CENTER[0] - _HUB_R - 0.030, FRONT_CENTER[1] + 0.004),
    "SpokeWidthDim": (FRONT_CENTER[0] + 0.030, FRONT_CENTER[1] + _HUB_R + 0.020),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "BoreDiaDim": "THRU - REAM",
    "SpokeWidthDim": "6X SPOKE",
}

RIGHT_HALF_HUB = HUB_AXIAL * SHEET_SCALE[0] / 2000.0
RIGHT_HALF_RIM = RIM_AXIAL * SHEET_SCALE[0] / 2000.0


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-wheel source", await adapter.open_model(str(SOURCE)))
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
            "Section View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Section View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Wheel Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying wheel; cast pulley; six spokes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (iso,):
        set_hidden_lines_removed(adapter, view)
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to wheel bore")

    # Axial widths across the right-view section: hub drum length (10) at the
    # centre, rim width (8) up at the rim.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_HUB, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_HUB, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.016),
        label="hub-drum axial length",
    )
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_RIM, RIGHT_CENTER[1] + _RIM_R),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_RIM, RIGHT_CENTER[1] + _RIM_R),
        text_xy=(RIGHT_CENTER[0] + 0.028, RIGHT_CENTER[1] + _RIM_R),
        label="rim axial width",
    )

    # Datum A = the axle bore (front); Ra 1.6 on the bore, position of the bore.
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + _HUB_R),
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + _HUB_R + 0.010),
        datum="A",
        label="axle bore axis",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + RIGHT_HALF_RIM, RIGHT_CENTER[1] + _RIM_R),
        frame_xy=(RIGHT_CENTER[0] + 0.024, RIGHT_CENTER[1] + _RIM_R + 0.020),
        characteristic="circular_runout",
        tolerance="0.10",
        datums=("A",),
        label="rim runout to the bore",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + HUB_DIA * SHEET_SCALE[0] / 2000.0, FRONT_CENTER[1]),
        symbol_xy=(FRONT_CENTER[0] + _HUB_R + 0.006, FRONT_CENTER[1] - 0.028),
        roughness_ra="1.6",
        label="hub drum finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Section View Note", RIGHT_CENTER[0] - 0.022, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.320, 0.085)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Wheel Manufacturing Drawing",
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
