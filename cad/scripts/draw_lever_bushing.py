r"""Create the curated machinist drawing for the lever-bank spacer bushing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
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
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from lever_bushing_spec import BORE_DIA, LENGTH, OUTER_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["lever_bushing"]
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

SHEET_SCALE = (4.0, 1.0)
FRONT_CENTER = (0.080, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + (OUTER_DIA + LENGTH) * SHEET_SCALE[0] / 1000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.315, 0.205)

FRONT_KEEP = {
    "OuterDia": (
        FRONT_CENTER[0] - 0.035,
        FRONT_CENTER[1] + 0.010,
    ),
    "BoreDia": (
        FRONT_CENTER[0] + OUTER_DIA * SHEET_SCALE[0] / 1000.0 + 0.005,
        FRONT_CENTER[1] - 0.010,
    ),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.040),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "THRU - REAM\n+0.03/-0.00",
    "Depth": "+/-0.03",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open lever-bushing source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Lever Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "lever bushing; turned spacer; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, right)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    outer_radius = OUTER_DIA * SHEET_SCALE[0] / 2000.0
    # 45 deg on the OD, NOT its 3 o'clock (the old `outer_edge`, which is where
    # `bore_edge` and the Ra's own anchor also sit at centre height).  The Ra
    # symbol is at x=0.120 -- OUTSIDE the OD, which ends at 0.104 -- so its
    # leader runs from (0.120, 0.212) back to bore_edge (0.093, 0.205) and
    # passes through (0.1041, 0.2079), measured INSIDE this frame's arrowhead
    # (ink bbox x 0.1038..0.1045, y 0.2061..0.2088).  The two merged into a
    # single ink blob -- confirmed twice: analytically from the leader's
    # straight path, and by an ink map at 0.08 mm/cell showing the OD circle,
    # this leader and the Ra leader collapsing into one run at (0.1041, 0.2088).
    #
    # The FRAME's terminus is what has to move, not the Ra: any Ra leader from
    # x>0.104 to the bore at 0.093 must cross the 3 o'clock ray, so no Ra
    # placement on this side can avoid a 3-o'clock anchor.  At 45 deg this
    # leader spans y 0.222..0.252 while the Ra's spans y 0.205..0.212 --
    # DISJOINT in y, so they cannot cross at any x (a stronger guarantee than
    # any clearance number).  The arc there is empty: an ink map of the OD's
    # upper-right quadrant finds only the circle itself at (0.0970, 0.2220) --
    # datum A's leader is 17 mm left at x=0.080, and the Ø12.00 diametral line
    # stays below y=0.213.
    outer_runout = (
        FRONT_CENTER[0] + outer_radius * math.cos(math.radians(45.0)),
        FRONT_CENTER[1] + outer_radius * math.sin(math.radians(45.0)),
    )
    bore_edge = (
        FRONT_CENTER[0] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
        FRONT_CENTER[1],
    )
    bore_top = (
        FRONT_CENTER[0],
        FRONT_CENTER[1] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    half_depth = LENGTH * SHEET_SCALE[0] / 2000.0
    left_end = (RIGHT_CENTER[0] - half_depth, RIGHT_CENTER[1])
    right_end = (RIGHT_CENTER[0] + half_depth, RIGHT_CENTER[1])
    # Attach at the bore's TOP, not its 3 o'clock: the symbol is asked for
    # straight above the bore, and a datum tag on a CIRCULAR edge slides its
    # attachment to the circle point nearest the symbol. Picking the 3 o'clock
    # while asking for a 12 o'clock symbol made SolidWorks re-attach at the top
    # and clamp the box down beside it -- it landed at y~0.222, inside the view,
    # straddling the annulus and the vertical centerline. Pick and symbol now
    # agree (the draw_pivot_bushing spelling), so the +0.037 is honored and the
    # box clears the view's 0.229 top.
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.037),
        datum="A",
        label="bushing bore axis",
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=left_end,
        symbol_xy=(left_end[0] - 0.018, RIGHT_CENTER[1]),
        datum="B",
        label="bushing reference end",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=outer_runout,
        frame_xy=(0.115, 0.255),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("A",),
        label="bushing OD runout",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=right_end,
        frame_xy=(right_end[0] + 0.014, 0.180),
        characteristic="parallelism",
        tolerance="0.03",
        datums=("B",),
        label="bushing end-face parallelism",
    )
    # Sits just right of the front view, level with the bore. From (0.160, 0.225)
    # the leader ran ~70 mm diagonally back across the whole ring to reach the
    # bore, tangling with the Ø12.00 and Ø6.50 dimension lines that already meet
    # at the centre. The symbol draws UP and RIGHT of its anchor (roughly
    # x+0.039, y+0.019) and the leader leaves the anchor itself, so anchoring
    # just above/right of the bore keeps the leader short and the body in the
    # empty band between the views: clear of the Ø6.50 callout below (it ends at
    # y=0.205), the runout frame above (y=0.251) and the OD-runout leader, which
    # now drops down x~0.097..0.112 (it was x~0.104..0.115 while that frame
    # picked the OD's 3 o'clock -- see `outer_runout` above).
    #
    # NOTE this reasoning bounds the symbol BODY only.  What actually collided
    # was this Ra's own LEADER, which the body's clearances say nothing about:
    # it runs (0.120, 0.212) -> bore_edge and crossed the runout frame's
    # arrowhead at (0.1041, 0.2079).  Fixed on the frame's side; if this symbol
    # moves, re-check the LEADER's path, not just where the body lands.
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_edge,
        symbol_xy=(0.120, 0.212),
        roughness_ra="1.6",
        label="bushing bore finish",
    )

    # x=0.020: the anchor is the text's left edge, so the ink starts here. The
    # sheet's 0.0127 zone margin and the re-centred border rule (~0.0126) now
    # agree, so 0.020 clears the rule and the audit enforces the same bound.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Lever Bushing Manufacturing Drawing",
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
