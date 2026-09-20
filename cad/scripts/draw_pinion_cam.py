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
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _named_views import octant_view_name
from _surface_finish import surface_finish_by_key
from pinion_cam_spec import (
    BORE,
    BOSS_PROUD,
    CAM_OD,
    ECC,
    LIFT_ROD_NUMBER,
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
# Third angle: the length view sits directly above the circular view, so the
# body and bore axes project vertically between them (machinist round 2).
TOP_CENTER = (0.105, 0.232)
ISO_CENTER = (0.350, 0.185)
BOTTOM_CENTER = (0.270, 0.195)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


BORE_R_SHEET = BORE * SHEET_SCALE[0] / 2000.0
_SQRT_HALF = 0.5**0.5

# Diameters go on the view that shows them as a SOLID edge: the OD as the
# length view's width, the boss on the boss end view, the bore on the circular
# view where it is the only diagonal (its and the OD's diagonals both pass
# through nearly the same centre, so the two cannot share a view without
# crossing -- machinist round 2).
FRONT_KEEP = {
    "BoreDia": (0.055, 0.186),
    "CollarCy": (0.172, 0.172),
    "BossProjection": (0.180, 0.122),
}
TOP_KEEP = {
    "Depth": (0.062, 0.232),
    "CollarOd": (0.105, 0.205),
    "BossCz": (0.165, 0.226),
}
BOTTOM_KEEP = {"BossDia": (0.312, 0.228)}
DIMENSION_CALLOUTS = {
    "BoreDia": f"FINAL REAM THRU\nRUNNING FIT ON LIFT ROD {LIFT_ROD_NUMBER}",
    "CollarCy": "BORE TO OD, BOTH END FACES",
    "BossProjection": f"BEYOND DIA {CAM_OD:.2f} OD",
    "BossCz": "FRONT FACE TO BOSS AXIS",
}
# Only the two critical features -- the reamed running bore and the cam OD it
# lifts through -- print more than the general grade; everything else takes one
# place under the title block's .X row (cad/docs/tolerance-policy.md).
DIMENSION_PRECISION = {"Depth": 1, "BossDia": 1, "BossProjection": 1}


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    # The built-in isometric looks from +Y, which hides the set-screw boss --
    # the part's one additional feature -- behind the collar, because the boss
    # points at -Y.  The FRONT-BOTTOM-RIGHT octant the PART names shows the
    # boss and its tapped opening (machinist round 2).
    iso = place_view(
        adapter, str(SOURCE), octant_view_name(1, -1, 1), *ISO_CENTER, scale=(2, 1)
    )
    set_hidden_lines_removed(adapter, iso)
    for view in (front, top, bottom):
        set_hidden_lines_visible(adapter, view)

    # The boss end view is curated FIRST so the boss diameter settles on the
    # view where the boss is a SOLID circle; imported into the length view it
    # can only attach to a hidden edge (machinist round 2).
    bottom_annotations = curate_view_dimensions(
        adapter, bottom, keep=BOTTOM_KEEP, view_label="boss end"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    annotations = [*bottom_annotations, *front_annotations, *top_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to boss end view")

    # Bore roughness: picked on the bore's upper-right rim and carried up-right
    # -- the one quadrant of the circular view no other annotation uses, now
    # that the OD is dimensioned on the length view and the bore diameter's
    # diagonal runs up-left.
    bore_center = (FRONT_CENTER[0], _front_y(0.0))
    bore_finish_edge = (
        bore_center[0] + BORE_R_SHEET * _SQRT_HALF,
        bore_center[1] + BORE_R_SHEET * _SQRT_HALF,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_finish_edge,
        symbol_xy=(0.150, 0.190),
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
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
