r"""Create the curated manufacturing drawing for the crank-drive gear (64T).

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The sheet is three
views of a plain helical toothed disc and three native model dimensions --
outside diameter, face width, reamed bore -- plus the gear-data block rule 6
keeps for the tooth system a cut-gear print cannot dimension (including the
helix angle, its hand, and the tooth thinning that opens the crossed mesh).

No datums, no feature control frames: a gear slipped onto a shaft land is not
on the GD&T allowlist (rules 3-4), and the retired end-face perpendicularity
and tooth-tip runout frames said nothing a hobby shop could hold that the bore
and blank limits do not already imply. The one roughness symbol is rule 5's
running-surface case: the bore is a size-toleranced fit and a fit lives on the
peaks too. The decimal places are the PART's
(``crank_drive_gear_spec.DRAWING_PRECISION``, applied natively by
``build_crank_drive_gear``); this script only reads them back off the sheet.

Drawn 3:2 -- at 1:1 a 65 mm disc left two thirds of a B sheet empty, and the
face view's 64 teeth need the size to read as teeth.
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
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from crank_drive_gear_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    OUTSIDE_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_drive_gear"]
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

SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
FRONT_CENTER = (0.135, 0.145)
RIGHT_CENTER = (0.255, 0.145)
ISO_CENTER = (0.350, 0.150)
GEAR_DATA_POS = (0.016, 0.262)
MANUFACTURING_NOTES_POS = (0.016, 0.030)

# Half the printed tooth-tip circle, in sheet metres: the face view's silhouette
# radius and the side view's half-height, which every dimension is placed clear
# of.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / (VIEW_SCALE[1] * 2000.0)  # 0.0489
# Half the printed face width: the side view's half-WIDTH, so the three views
# can be proven not to overlap offline.
FACE_WIDTH_HALF = FACE_WIDTH * VIEW_SCALE[0] / (VIEW_SCALE[1] * 2000.0)  # 0.006

# Face view: the tip circle above, the bore below-left, both leadered clear of
# the silhouette and of the gear-data block's column on the far left.
FRONT_KEEP = {
    "OutsideDia": (FRONT_CENTER[0], FRONT_CENTER[1] + HALF_OD + 0.016),
    "BoreDia": (FRONT_CENTER[0] - 0.078, FRONT_CENTER[1] - 0.062),
}
# Side view: the face width, above the view -- below it would land in the
# title block's corner of the B sheet.
RIGHT_KEEP = {
    "FaceWidth": (RIGHT_CENTER[0], RIGHT_CENTER[1] + HALF_OD + 0.014),
}

DIMENSION_CALLOUTS = {
    # The bore's own limits are the fit; the callout only has to say how far it
    # goes and how it is finished (policy rule 7).
    "BoreDia": "REAM THRU",
}


def _hide_tangent_edges(view: Any, label: str) -> None:
    """Drop a view's tangent edges, and prove they went.

    On a 64-tooth TRUE helix every flank-to-tip and flank-to-root transition
    projects as its own curve, so the side view arrives as a stripe field of
    128 helical lines across a 12 mm face -- ink that carries no fact the gear
    data does not state, and that no dimension can be placed on top of. The
    isometric keeps its tangent edges: there the helix is the thing being
    shown.
    """
    view.SetDisplayTangentEdges2(0)
    if int(view.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError(f"failed to hide {label}-view tangent edges")
    view.UpdateViewDisplayGeometry()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-drive-gear source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank-Drive Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank-drive gear; steel; 64T helical",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # Hidden lines OFF in every view: the only internal feature is a straight
    # reamed bore whose callout already says THRU, so hidden edges in the side
    # view would add ink without adding a fact.
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    _hide_tangent_edges(front, "front")
    _hide_tangent_edges(right, "side")

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(
        adapter, front_annotations + right_annotations, DRAWING_PRECISION_BY_NAME
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to gear bore")
    # The bore is the part's one fit surface, and a fit is a function of the
    # peaks as well as the size: REAM names the operation, not the finish it
    # leaves. The roughness is the project's general machined grade, authored
    # on the PART and read back here (policy rule 5's running-surface case).
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.020, FRONT_CENTER[1] - 0.062),
        control=surface_finish_by_key(SURFACE_FINISHES, "crank_drive_gear_bore"),
        label="crank-drive gear bore finish",
        entity=visible_circle_edge(adapter, front, BORE_DIA),
        leader_attach_xy=(
            FRONT_CENTER[0],
            FRONT_CENTER[1] - BORE_DIA * VIEW_SCALE[0] / (VIEW_SCALE[1] * 2000.0),
        ),
    )

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS, char_height=0.0025
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank-Drive Gear Manufacturing Drawing",
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
