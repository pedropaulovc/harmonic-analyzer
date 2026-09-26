r"""Create the manufacturing drawing for the rocker-bank south thrust washer (MHA-148)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from rocker_thrust_washer_drawing_spec import SURFACE_FINISHES
from rocker_thrust_washer_spec import OD, THICKNESS
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_thrust_washer"]
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

# A O10 x 1.5 washer: 4:1 keeps both diameters and the thickness legible
# without crowding the landscape sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FRONT_CENTER = (0.110, 0.180)
RIGHT_CENTER = (0.200, 0.180)
ISO_CENTER = (0.320, 0.180)

FRONT_KEEP = {
    "DiscDia": (0.060, 0.240),
    "BoreDia": (0.150, 0.240),
}
RIGHT_KEEP = {
    "DiscThick": (0.235, 0.225),
}

# Both running faces carry their finish on the edge-on right view, where each
# face is one line: the *Right view looks along -X, so part +Z (the hub face)
# draws LEFT of centre and -Z (the ear face) right. Key -> (symbol, leader
# tip) in sheet metres; the symbols stand off left-high and right-low, clear
# of the front view and of the thickness dimension above right.
_HALF_THICK = THICKNESS * VIEW_SCALE[0] / VIEW_SCALE[1] / 2000.0
FINISH_PLACEMENT = {
    "hub_face": (
        (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] + 0.025),
        (RIGHT_CENTER[0] - _HALF_THICK, RIGHT_CENTER[1] + 0.010),
    ),
    "ear_face": (
        (RIGHT_CENTER[0] + 0.028, RIGHT_CENTER[1] - 0.030),
        (RIGHT_CENTER[0] + _HALF_THICK, RIGHT_CENTER[1] - 0.010),
    ),
}


def _face_rim_edge(view: Any, z_mm: float, *, label: str) -> Any:
    """The OD rim circle of the face at part z ``z_mm``: in the edge-on view it
    IS that face's line, and its faces include the face the control names
    (add_surface_finish validates that)."""
    matches = []
    for raw in visible_view_entities(view, 1, label=label):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        centre_x, centre_y, centre_z, *_axis, radius = (
            float(value) for value in curve.CircleParams
        )
        if abs(radius - OD / 2000.0) > 1e-7 or abs(centre_z - z_mm / 1000.0) > 1e-7:
            continue
        matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"expected one {label} rim edge, found {len(matches)}")
    return matches[0]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-thrust-washer source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Bank Thrust Washer Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker bank south thrust washer; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the washer face view")
    for key, (symbol_xy, attach_xy) in FINISH_PLACEMENT.items():
        control = surface_finish_by_key(SURFACE_FINISHES, key)
        # A +/-Z PlanarFace sits at z = its offset along its normal.
        z_mm = control.face.offset_mm * control.face.normal[2]
        add_surface_finish(
            adapter,
            right,
            edge_entity=_face_rim_edge(right, z_mm, label=f"washer {key}"),
            symbol_xy=symbol_xy,
            control=control,
            label=f"washer {key} finish",
            char_height=0.0025,
            leader_attach_xy=attach_xy,
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Bank Thrust Washer Manufacturing Drawing",
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
