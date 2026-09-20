r"""Create the curated manufacturing drawing for the crank pinion (16T).

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The sheet is three
views of a plain toothed disc and three native model dimensions -- outside
diameter, face width, reamed bore -- plus the gear-data block rule 6 keeps for
the tooth system a cut-gear print cannot dimension.

No datums, no feature control frames, no roughness symbols: a removable stock
pinion clamped to its crankshaft is not on the GD&T allowlist (rules 3-5), and
its bore's own limits already say what the fit is. The decimal places are the
PART's (``crank_pinion_spec.DRAWING_PRECISION``, applied natively by
``build_crank_pinion``); this script only reads them back off the sheet.

Drawn 5:1 -- the whole part is 17.8 mm across, and at the old 3:1 the three
views huddled in one corner of a B sheet.
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
from crank_pinion_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OUTSIDE_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_pinion"]
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

SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
FRONT_CENTER = (0.130, 0.150)
RIGHT_CENTER = (0.230, 0.150)
ISO_CENTER = (0.345, 0.155)

# Half the printed tooth-tip circle, in sheet metres: the face view's silhouette
# radius and the side view's half-height, which every dimension is placed clear
# of.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0  # 0.0444

# Face view: the two turned diameters, leadered out to opposite sides of the
# free left field so neither leader crosses the other or the data block.
FRONT_KEEP = {
    "OutsideDia": (FRONT_CENTER[0] - 0.070, FRONT_CENTER[1] + 0.055),
    "BoreDia": (FRONT_CENTER[0] - 0.075, FRONT_CENTER[1] - 0.038),
}
# Side view: the face width, below the view and clear of the title block.
RIGHT_KEEP = {
    "FaceWidth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_OD - 0.014),
}

DIMENSION_CALLOUTS = {
    # The bore's own limits are the fit; the callout only has to say how far it
    # goes and how it is finished (policy rule 7).
    "BoreDia": "REAM THRU",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-pinion source", await adapter.open_model(str(SOURCE)))
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
            0: "Crank Pinion Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank pinion; steel; 16T spur",
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
        raise RuntimeError("failed to add ASME center mark to pinion bore")
    # The bore is the part's one fit surface, and a fit is a function of the
    # peaks as well as the size: REAM names the operation, not the finish it
    # leaves. The roughness is the project's general machined grade, authored
    # on the PART and read back here (policy rule 5's "a surface that has to
    # work" case; codex machinist review, 2026-09-20).
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.017, FRONT_CENTER[1] - 0.060),
        control=surface_finish_by_key(SURFACE_FINISHES, "crank_pinion_bore"),
        label="crank pinion bore finish",
        entity=visible_circle_edge(adapter, front, BORE_DIA),
        leader_attach_xy=(
            FRONT_CENTER[0],
            FRONT_CENTER[1] - BORE_DIA * VIEW_SCALE[0] / 2000.0,
        ),
    )

    add_property_linked_note(adapter, "Gear Data", 0.016, 0.258, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.082, char_height=0.0025
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Pinion Manufacturing Drawing",
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
