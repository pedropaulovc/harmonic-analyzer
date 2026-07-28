r"""Create the curated machinist drawing for the pinion lift cam.

An eccentric steel collar: the Ø6.37 bore is offset 1.4 mm from the Ø10.32 OD
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
from _common import CAD_ROOT, _early_bound, check, run_build
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
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import fit_limits
from _surface_finish import MACHINED
from pinion_cam_spec import (
    BORE,
    BORE_BAND,
    BOSS_DIA,
    BOSS_PROUD,
    BOSS_Z,
    CAM_LEN,
    CAM_OD,
    ECC,
    TAP_DRILL_DIA,
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
FRONT_BBOX_CY = (
    (CAM_OD / 2.0 - ECC) + (-(ECC + CAM_OD / 2.0 + BOSS_PROUD))
) / 2.0
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
    "CollarOd": (0.025, 0.120),
    "CollarCy": (0.170, 0.135),
}
TOP_KEEP = {
    "Depth": (0.100, 0.195),
    "BossDia": (0.180, 0.225),
    "BossCz": (0.155, 0.200),
}
DIMENSION_CALLOUTS = {
    "BoreDia": f"FINAL REAM LIMITS\n{fit_limits(BORE, BORE_BAND)} THRU",
    "CollarOd": "+/-0.05",
    "CollarCy": "+/-0.05 BOTH END FACES",
    "Depth": "+/-0.05",
    "BossDia": (
        f"+/-0.05\nPROJECTION {BOSS_PROUD:.2f}+/-0.05\nBEYOND DIA {CAM_OD:.2f} OD"
    ),
    "BossCz": "A TO BOSS / TAP AXIS",
}


@_telemetry.traced("drawing.pinion_cam_front_end_scan")
def _front_end_edge(view: Any) -> Any:
    """Return the collar's real front circular edge at model Z=0."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="pinion-cam top edges"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        candidates.append((params[2], params[6], edge))
    matches = [
        edge
        for center_z, radius, edge in candidates
        if abs(center_z) <= 0.01 and abs(radius - CAM_OD / 2.0) <= 0.01
    ]
    if len(matches) != 1:
        seen = [(round(z, 4), round(r, 4)) for z, r, _edge in candidates]
        raise RuntimeError(
            "pinion-cam top view expected one front OD edge at "
            f"z=0 r={CAM_OD / 2.0:.3f} mm; found {len(matches)} from {seen}"
        )
    return matches[0]


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
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(2, 1)
    )
    place_view(adapter, str(SOURCE), "*Isometric", 0.350, 0.185, scale=(2, 1))

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *top_annotations], DIMENSION_CALLOUTS
    )
    top_by_name = {dimension_name(adapter, a): a for a in top_annotations}
    boss_station = top_by_name["BossCz"]
    boss_station_display = adapter._attempt(
        lambda: boss_station.GetSpecificAnnotation()
    )
    if boss_station_display is None:
        raise RuntimeError("BossCz has no display dimension to box")
    set_basic_dimension(
        adapter, boss_station_display, label="boss/tap axial station"
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to boss end view")

    bore_center = (FRONT_CENTER[0], _front_y(0.0))
    bore_bottom = (bore_center[0], bore_center[1] - BORE_R_SHEET)
    bore_right = (bore_center[0] + BORE_R_SHEET, bore_center[1])
    front_face_x = TOP_CENTER[0] - CAM_LEN * SHEET_SCALE[0] / 2000.0
    front_face = (front_face_x, TOP_CENTER[1])
    bottom_boss_center = (
        BOTTOM_CENTER[0],
        BOTTOM_CENTER[1] + (BOSS_Z - CAM_LEN / 2.0) * 2.0 / 1000.0,
    )
    bottom_boss_right = (
        bottom_boss_center[0] + BOSS_DIA / 1000.0,
        bottom_boss_center[1],
    )
    bottom_boss_left = (
        bottom_boss_center[0] - BOSS_DIA / 1000.0,
        bottom_boss_center[1],
    )
    bottom_tap_right = (
        bottom_boss_center[0] + TAP_DRILL_DIA / 1000.0,
        bottom_boss_center[1],
    )
    od_center = (FRONT_CENTER[0], _front_y(-ECC))
    od_bottom = (od_center[0], od_center[1] - CAM_R_SHEET)
    add_datum_feature(
        adapter,
        top,
        edge_entity=_front_end_edge(top),
        symbol_xy=(front_face_x - 0.018, TOP_CENTER[1] + 0.018),
        datum="A",
        label="cam front end face",
    )
    # SolidWorks restricts this axis-attached tag and live readback normalizes
    # the requested sheet point by 2.846 mm.  Bound that annotation placement
    # behavior without changing any part dimension or geometric tolerance.
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_bottom,
        symbol_xy=(0.085, 0.105),
        datum="B",
        label="cam final bore axis",
        position_tolerance_m=0.003,
    )
    # The OD-axis datum is constrained more strongly: live readback places its
    # tag 18.197 mm from the requested sheet point.  Keep the intended anchor
    # and bound only this annotation-placement normalization.
    add_datum_feature(
        adapter,
        front,
        edge_xy=od_bottom,
        symbol_xy=(0.155, 0.105),
        datum="C",
        label="cam OD datum axis",
        position_tolerance_m=0.019,
    )
    # Datum D attaches on the boss's LEFT flank, opposite the two position
    # frames on the right, so its leader unambiguously lands on the boss OD
    # rather than the tap/axis region (machinist round 1).
    # Live readback normalizes the restricted tag by 4.072 mm; bound only that
    # annotation-placement behavior while retaining the reviewed sheet point.
    add_datum_feature(
        adapter,
        bottom,
        edge_xy=bottom_boss_left,
        symbol_xy=(0.192, 0.170),
        datum="D",
        label="cam boss OD axis",
        position_tolerance_m=0.0041,
    )
    add_feature_control_frame(
        adapter,
        bottom,
        edge_xy=bottom_boss_right,
        frame_xy=(0.285, 0.240),
        characteristic="position",
        tolerance="0.03",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="BOSS OD AXIS",
        label="cam boss axis position",
    )
    add_feature_control_frame(
        adapter,
        bottom,
        edge_xy=bottom_tap_right,
        frame_xy=(0.315, 0.215),
        characteristic="position",
        tolerance="0.03",
        datums=("D",),
        diameter=True,
        quantity="M2.5 TAP PITCH AXIS",
        label="cam tap pitch axis position",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_right,
        symbol_xy=(0.155, 0.175),
        roughness_ra=MACHINED,
        label="cam bore finish",
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
