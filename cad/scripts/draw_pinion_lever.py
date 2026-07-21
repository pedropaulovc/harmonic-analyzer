r"""Create the curated machinist drawing for the pinion engage lever.

A clamp hub (Ø13 OD, Ø6.35 bore) with a tapered grip rod (Ø4 at the hub to Ø6
at the tip) rising 86 mm out of it.  The rod-revolve and hub sketches both live
on the Front plane, so every marked dimension imports into the FRONT view; the
right view carries the hub length and domed cap as a reference silhouette.

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
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
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
from pinion_lever_spec import BORE, CAP_SAG, HUB_LEN, HUB_OD, ROD_LEN, ROD_ROOT_DIA
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
RIGHT_CENTER = (0.165, 0.170)
ISO_CENTER = (0.330, 0.205)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


HUB_R_SHEET = HUB_OD * SHEET_SCALE[0] / 2000.0
BORE_R_SHEET = BORE * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    "HubOd": (0.028, 0.112),
    "HubBore": (0.108, 0.105),
    "RodTipY": (0.044, 0.170),
    "RodRootR": (0.145, 0.132),
    "RodTipR": (0.120, 0.232),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "HubBore": "NOMINAL REF ONLY\n8.00+0.10/-0.00 FULL-DIA\nFROM FLAT FACE; FLAT BOTTOM\n6.375 MAX / 6.360 MIN\nRa 1.6",
    "RodRootR": "RESULTING <MOD-DIAM>4.00 AT HUB",
    "RodTipR": "RESULTING <MOD-DIAM>6.00 AT TIP",
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
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Front carries the hub bore as a true circle; the right view shows the hub
    # length and the domed cap in section-like silhouette.  HLV keeps the bore's
    # hidden through-line readable in the right view.
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    hub_center = (FRONT_CENTER[0], _front_y(0.0))
    bore_top = (hub_center[0], hub_center[1] + BORE_R_SHEET)
    hub_right = (hub_center[0] + HUB_R_SHEET, hub_center[1])
    # The south crown makes the right-view bounds asymmetric about z=0.  View
    # placement centres that full -6.5..+5.0 mm silhouette, so locate the flat
    # +Z face from the true bounding-box centre rather than half the hub length.
    z_min = -HUB_LEN / 2.0 - CAP_SAG
    z_max = HUB_LEN / 2.0
    z_center = (z_min + z_max) / 2.0
    flat_face_x = RIGHT_CENTER[0] - (z_max - z_center) * SHEET_SCALE[0] / 1000.0
    flat_face = (flat_face_x, hub_center[1])
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
        right,
        edge_xy=flat_face,
        symbol_xy=(flat_face_x - 0.018, hub_center[1] - 0.018),
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
        right,
        edge_xy=flat_face,
        frame_xy=(0.205, 0.105),
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
        characteristic="position",
        tolerance="0.05",
        datums=("A", "B"),
        diameter=True,
        quantity="GRIP AXIS",
        label="lever grip-axis position",
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
