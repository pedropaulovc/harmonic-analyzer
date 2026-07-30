r"""Create the curated manufacturing drawing for the cylinder gear (+ cam).

Sets the batch gear-drawing pattern: two orthographic views (toothed face +
edge profile) dimension the machinable BLANK (bore Ø, face width), while the
GEAR DATA note specifies the involute tooth system (an involute OD is a
scalloped outline with no single circular edge to dimension). The eccentric
cam and alignment notch are carried by the manufacturing notes.
"""

from __future__ import annotations

import argparse
import math
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
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import MACHINED
from cylinder_gear_spec import BORE_DIA, OUTSIDE_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cylinder_gear"]
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

# 1:1 whole sheet: OD 62.2 mm reads roomily and leaves the left column for the
# gear-data and manufacturing-notes blocks. The gear axis is Z, so *Front shows
# the toothed face and *Right the disc thickness (face 3 + cam) edge-on.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.225, 0.175)
RIGHT_CENTER = (0.300, 0.175)
ISO_CENTER = (0.375, 0.205)
GEAR_DATA_POS = (0.040, 0.262)
BORE_R = BORE_DIA * VIEW_SCALE[0] / 2000.0
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0


FRONT_KEEP = {
    "BoreDia": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1] - 0.030),
}
DIMENSION_CALLOUTS = {
    # The 9.525 +0.03/+0.05 reamed bore against the arbor's
    # 9.525 +0.00/-0.02 journal guarantees 0.03..0.07 diametral clearance,
    # inside the project's 0.025..0.075 shaft-in-bushing policy.
    "BoreDia": "THRU - REAM",
}
DIMENSION_PRECISION = {"BoreDia": 3}


def _largest_visible_planar_face(adapter: Any, view: Any) -> Any:
    """Return the largest visible planar face in ``view``."""
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        faces = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 3), default=()
        ) or ()
        for face in faces:
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if surface.IsPlane():
                candidates.append((float(face.GetArea()), face))
    if not candidates:
        raise RuntimeError("front view has no visible planar model face")
    return max(candidates, key=lambda item: item[0])[1]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cylinder-gear source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cylinder Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cylinder gear; integral eccentric cam; brass; 120T",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to gear bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)
    gear_face = _largest_visible_planar_face(adapter, front)

    # Datum A: the bore axis (front view, 12 o'clock pick with the symbol above,
    # the draw_pivot_bushing spelling so the standoff is honoured).
    datum_radial = math.sqrt(0.5)
    bore_top = (
        FRONT_CENTER[0] + BORE_R * datum_radial,
        FRONT_CENTER[1] + BORE_R * datum_radial,
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(
            FRONT_CENTER[0] + (HALF_OD + 0.018) * datum_radial,
            FRONT_CENTER[1] + (HALF_OD + 0.018) * datum_radial,
        ),
        datum="A",
        label="cylinder gear bore axis",
        shoulder=True,
        # This shoulder-constrained tag retains a point 7.186 mm inward on the
        # same radial.  The bounded call-site tolerance admits that native
        # normalization; the layout audit still rejects a collapsed leader.
        position_tolerance_m=0.008,
    )
    # Gear face perpendicular to the bore axis (datum A), attached directly to
    # the largest visible planar gear face instead of a tooth-tip silhouette.
    half_od = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
    add_feature_control_frame(
        adapter,
        front,
        frame_xy=(0.175, RIGHT_CENTER[1] + half_od + 0.010),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="gear face squareness to bore",
        entity_type="FACE",
        entity=gear_face,
    )
    # Bore finish: attaches by model identity (the batch contract) at the
    # circle edge's canonical vertex, which lands at (FRONT_CENTER-0.0038,
    # FRONT_CENTER+... ) -- the bore's lower-left, invariant across runs. Two
    # other invariant leader corridors converge there (the datum's 45-degree
    # run y = x - 0.05 just below the attach, and the face-FCF's vertical run
    # at x 0.201..0.208), so route the SF leader STRAIGHT DOWN from a symbol
    # directly above the attach: x = 0.2212 clears the FCF corridor on the
    # right, and the vertical span stops 0.9 mm above the 45-degree segment.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] - 0.0038, FRONT_CENTER[1] + 0.035),
        roughness_ra=MACHINED,
        label="cylinder gear bore finish",
        entity=bore_edge,
    )

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.018, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Manufacturing Drawing",
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
