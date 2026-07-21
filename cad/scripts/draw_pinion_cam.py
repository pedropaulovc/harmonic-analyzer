r"""Create the curated machinist drawing for the pinion lift cam.

An eccentric steel collar: the Ø6.35 bore is offset 1.0 mm from the Ø9.2 OD
axis (so the collar and bore are NOT concentric -- the drawing dimensions that
offset explicitly, per the cam-note precedent).  The collar/bore sketches live
on the Front plane (front view carries OD/bore/eccentricity); the boss and the
collar length live on the Top plane (top view carries the boss and length).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_cam.py pinion-cam
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
from pinion_cam_spec import BORE, BOSS_DIA, BOSS_Z, CAM_LEN, CAM_OD, ECC
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_cam"]
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

SHEET_SCALE = (3.0, 1.0)

# Front view (XY): the collar circle is centred ECC BELOW the origin, the bore
# is ON the origin, and the boss stub points down.  bbox spans the boss tip.
FRONT_BBOX_CY = ((CAM_OD / 2.0 - ECC) + (-(ECC + CAM_OD / 2.0 + 0.5))) / 2.0
FRONT_CENTER = (0.085, 0.150)
TOP_CENTER = (0.085, 0.232)
ISO_CENTER = (0.215, 0.185)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


BORE_R_SHEET = BORE * SHEET_SCALE[0] / 2000.0
CAM_R_SHEET = CAM_OD * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    "BoreDia": (0.050, 0.150),
    "CollarOd": (0.030, 0.120),
    "CollarCy": (0.140, 0.150),
}
TOP_KEEP = {
    "Depth": (0.085, 0.205),
    "BossDia": (0.150, 0.232),
    "BossCz": (0.150, 0.208),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "NOMINAL REF ONLY\nFINAL REAM LIMITS\n6.375 MAX / 6.360 MIN THRU\nRa 1.6",
    "CollarOd": "+/-0.05",
    "CollarCy": "ECCENTRICITY +/-0.05",
    "Depth": "+/-0.05",
    "BossDia": "INTEGRAL BOSS\n+/-0.05; PROJECTION 0.50+/-0.05",
    "BossCz": "+/-0.05 FROM FRONT FACE",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-cam source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Lift Cam Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion lift cam; eccentric collar; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *top_annotations], DIMENSION_CALLOUTS
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    bore_center = (FRONT_CENTER[0], _front_y(0.0))
    bore_top = (bore_center[0], bore_center[1] + BORE_R_SHEET)
    front_face_x = TOP_CENTER[0] - CAM_LEN * SHEET_SCALE[0] / 2000.0
    front_face = (front_face_x, TOP_CENTER[1])
    boss_center_x = front_face_x + BOSS_Z * SHEET_SCALE[0] / 1000.0
    boss_top = (
        boss_center_x,
        TOP_CENTER[1] + BOSS_DIA * SHEET_SCALE[0] / 2000.0,
    )
    od_center = (FRONT_CENTER[0], _front_y(-ECC))
    od_right = (od_center[0] + CAM_R_SHEET, od_center[1])
    add_datum_feature(
        adapter,
        top,
        edge_xy=front_face,
        symbol_xy=(front_face_x - 0.018, TOP_CENTER[1] + 0.018),
        datum="A",
        label="cam front end face",
        entity_type="SILHOUETTE",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(bore_center[0], bore_center[1] + 0.038),
        datum="B",
        label="cam final bore axis",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=od_right,
        frame_xy=(0.160, 0.118),
        characteristic="parallelism",
        tolerance="0.03",
        datums=("B",),
        diameter=True,
        label="cam OD axis parallelism",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=boss_top,
        frame_xy=(0.190, 0.255),
        characteristic="position",
        tolerance="0.05",
        datums=("A", "B"),
        diameter=True,
        label="cam boss axis position",
        entity_type="SILHOUETTE",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.205, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Lift Cam Manufacturing Drawing",
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
