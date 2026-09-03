r"""Create the curated machinist drawing for the pinion lift cam.

An eccentric steel collar: the Ø6.37 bore is offset 1.4 mm from the Ø10.32 OD
axis (so the collar and bore are NOT concentric -- the drawing dimensions that
offset explicitly, per the cam-note precedent).  The collar/bore sketches live
on the Front plane (front view carries OD/bore/eccentricity); the boss and the
collar length live on the Top plane (top view carries the boss and length).

The cam is on the GD&T allowlist (cad/docs/drawing-simplicity-policy.md rule
3, "cams") and carries the MINIMUM that expresses the eccentricity: the reamed
bore is datum B and one position frame holds the OD axis to it, fed by the
boxed basic offset.  Nothing else on the sheet is geometric: the boss and its
tap are ordinary toleranced dimensions, and the one roughness symbol sits on
the OD the follower stud rides.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_cam.py pinion-cam
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from pinion_cam_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
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
from _surface_finish import surface_finish_by_key
from pinion_cam_spec import (
    BORE,
    BOSS_PROUD,
    CAM_OD,
    ECC,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
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
FRONT_BBOX_CY = ((CAM_OD / 2.0 - ECC) + (-(ECC + CAM_OD / 2.0 + BOSS_PROUD))) / 2.0
FRONT_CENTER = (0.105, 0.150)
TOP_CENTER = (0.100, 0.232)
ISO_CENTER = (0.230, 0.185)
BOTTOM_CENTER = (0.270, 0.195)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


BORE_R_SHEET = BORE * SHEET_SCALE[0] / 2000.0
CAM_R_SHEET = CAM_OD * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    "BoreDia": (0.045, 0.165),
    "BossProjection": (0.190, 0.120),
    "CollarOd": (0.025, 0.120),
    "CollarCy": (0.170, 0.135),
}
TOP_KEEP = {
    "Depth": (0.100, 0.195),
    "BossDia": (0.180, 0.225),
    "BossCz": (0.155, 0.200),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "REAM THRU",
    "BossProjection": f"BEYOND DIA {CAM_OD:.2f} OD",
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
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", 0.350, 0.185, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    for view in (front, top, bottom):
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
    # The eccentricity is the one BASIC dimension: it feeds the OD-axis
    # position frame below (policy rule 4).
    front_by_name = {dimension_name(adapter, a): a for a in front_annotations}
    offset = front_by_name["CollarCy"]
    offset_display = adapter._attempt(lambda: offset.GetSpecificAnnotation())
    if offset_display is None:
        raise RuntimeError("CollarCy has no display dimension to box")
    set_basic_dimension(adapter, offset_display, label="bore-to-OD eccentricity")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to boss end view")

    bore_center = (FRONT_CENTER[0], _front_y(0.0))
    bore_bottom = (bore_center[0], bore_center[1] - BORE_R_SHEET)
    od_center = (FRONT_CENTER[0], _front_y(-ECC))
    od_bottom = (od_center[0], od_center[1] - CAM_R_SHEET)
    od_right = (od_center[0] + CAM_R_SHEET, od_center[1])
    # Datum B: the reamed bore axis.  SolidWorks restricts this axis-attached
    # tag and normalizes the requested point ~2.85 mm ALONG the leader,
    # wherever it is asked to go: (0.085, 0.105) settled 3.07 mm away and
    # (0.0861, 0.1078) settled another 2.9 mm on (2026-09-02 fleet builds), so
    # chasing the settled point never converges.  The allowance bounds that
    # constant offset; a real placement failure is an order of magnitude more.
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_bottom,
        symbol_xy=(0.085, 0.105),
        datum="B",
        label="cam final bore axis",
        position_tolerance_m=0.004,
    )
    # The one frame: the OD axis positioned to the bore axis, at the basic
    # offset boxed above.  Led from the OD's bottom into the clear band below
    # the front view, right of the datum tag.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=od_bottom,
        frame_xy=(0.155, 0.105),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["cam OD axis position"],
        datums=("B",),
        diameter=True,
        quantity="OD AXIS",
        label="cam OD axis position",
    )
    # The OD is the surface the strap's follower stud rides (rule 5); the
    # set-pinned bore does not run on the rod.
    add_surface_finish(
        adapter,
        front,
        edge_xy=od_right,
        symbol_xy=(0.155, 0.175),
        control=surface_finish_by_key(SURFACE_FINISHES, "od"),
        label="cam OD finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    if add_note(adapter, "BOSS END VIEW SCALE 2:1", 0.245, 0.174) is None:
        raise RuntimeError("failed to label cam boss end view")
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.145)

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
