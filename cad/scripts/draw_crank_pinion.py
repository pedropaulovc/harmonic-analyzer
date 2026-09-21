r"""Create the curated manufacturing drawing for the crank pinion (16T).

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The sheet is three
views of a toothed disc with a hub boss and seven native model dimensions --
outside diameter, reamed bore and boss diameter on the face view; face width,
pin station and overall length stacked from the toothed face, plus the boss
end break, on the side view -- the retention pin's match-drill hole callout,
and the gear-data block rule 6 keeps for the tooth system a cut-gear print
cannot dimension.

No datums, no feature control frames, one roughness symbol (the bore): a
removable stock pinion pinned to its crankshaft is not on the GD&T allowlist
(rules 3-5), and its bore's own limits already say what the fit is. The
decimal places are the PART's (``crank_pinion_spec.DRAWING_PRECISION``,
applied natively by ``build_crank_pinion``); this script only reads them back
off the sheet.

Drawn 4:1 -- the boss makes the part 17.28 long, and at the disc's 5:1 the
isometric ran off the B sheet's right border.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
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
    FACE_WIDTH,
    OUTSIDE_DIA,
    OVERALL_LENGTH,
    PIN_DIA,
    PIN_HOLE_PROCESS,
    PIN_STATION,
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

SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FRONT_CENTER = (0.110, 0.150)
RIGHT_CENTER = (0.215, 0.150)
ISO_CENTER = (0.345, 0.150)

# Half the printed tooth-tip circle, in sheet metres: the face view's silhouette
# radius and the side view's half-height, which every dimension is placed clear
# of.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0  # 0.0356


def _side_x(z_mm: float) -> float:
    """Sheet x of a model-z station in the side view.

    SolidWorks centres a view on its geometry (the crankshaft sheet's
    ``_SIDE_BOTTOM`` idiom), and a *Right view lays model +Z to the LEFT (the
    boss end sits nearest the face view), so the toothed south face (z = 0) is
    the view's right edge and the boss end its left.
    """
    return RIGHT_CENTER[0] + (OVERALL_LENGTH / 2.0 - z_mm) * VIEW_SCALE[0] / 1000.0


# Face view: the three turned diameters, leadered out into the free field
# around the face -- tip circle upper-left, bore lower-left (its roughness
# symbol hangs below), boss upper-right, so no leader crosses another or the
# data block.
FRONT_KEEP = {
    "OutsideDia": (FRONT_CENTER[0] - 0.062, FRONT_CENTER[1] + 0.048),
    "BoreDia": (FRONT_CENTER[0] - 0.070, FRONT_CENTER[1] - 0.035),
    "BossDia": (FRONT_CENTER[0] + 0.050, FRONT_CENTER[1] + 0.053),
}
# Side view: the three lengths stacked below the view, every one from the
# toothed south face (rule 7: one origin per view, baseline not chained) --
# shortest nearest the part, the overall length outermost and clear of the
# title block's top edge. The boss end break sits off the boss end's lower
# corner, left of the overall length's extension line.
_SIDE_BOTTOM = RIGHT_CENTER[1] - HALF_OD
RIGHT_KEEP = {
    "FaceWidth": ((_side_x(0.0) + _side_x(FACE_WIDTH)) / 2.0, _SIDE_BOTTOM - 0.014),
    "PinStation": ((_side_x(0.0) + _side_x(PIN_STATION)) / 2.0, _SIDE_BOTTOM - 0.026),
    "OverallLength": (RIGHT_CENTER[0], _SIDE_BOTTOM - 0.038),
    "BossChamfer": (_side_x(OVERALL_LENGTH) - 0.020, _SIDE_BOTTOM - 0.008),
}

DIMENSION_CALLOUTS = {
    # The bore's own limits are the fit; the callout only has to say how far it
    # goes and how it is finished (policy rule 7).
    "BoreDia": "REAM THRU",
    # The chamfer feature imports its one distance; the angle is the caption.
    "BossChamfer": "X 45 DEG",
}

# The retention-pin cross-hole: its exit circle on the boss wall nearest the
# viewer, at the pin station on the axis. The native callout hangs above the
# side view with the match-drill statement as its prefix.
PIN_HOLE_EDGE = (
    _side_x(PIN_STATION),
    RIGHT_CENTER[1] + PIN_DIA * VIEW_SCALE[0] / 2000.0,
)
PIN_HOLE_CALLOUT = (_side_x(PIN_STATION) + 0.022, RIGHT_CENTER[1] + HALF_OD + 0.036)


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
    # Hidden lines OFF in every view (rule 7): the reamed bore's callout says
    # THRU, and the pin cross-hole is a standard drill whose callout defines
    # it -- its exit circle is solid on the side view where its station is
    # dimensioned, so dashed edges would add ink without adding a fact.
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
    set_dimension_callouts(
        adapter, [*front_annotations, *right_annotations], DIMENSION_CALLOUTS
    )
    assert_imported_precision(
        adapter, front_annotations + right_annotations, DRAWING_PRECISION_BY_NAME
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pinion bore")
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin cross-hole")
    # The side view is a turned part's length view: its axis centerline says
    # which pair of edges is the faced ends (rule 7, turned parts), picked on
    # the boss's cylindrical face between the tooth face and the pin hole's
    # rim, a hair above the axis so the pick cannot land in the hole.
    add_view_centerline(
        adapter,
        right,
        face_xy=(
            (_side_x(FACE_WIDTH) + _side_x(PIN_STATION - PIN_DIA / 2.0)) / 2.0,
            RIGHT_CENTER[1] + 0.004,
        ),
        label="crank pinion axis centerline",
    )
    # The retention pin's hole: native size and THRU from the Hole Wizard,
    # the match-drill statement (mate by number) as its prefix -- rule 6 puts
    # a matched-fit requirement on the feature callout, not in a note.
    add_native_hole_callout(
        adapter,
        right,
        edge_xy=PIN_HOLE_EDGE,
        callout_xy=PIN_HOLE_CALLOUT,
        label="retention-pin cross-hole",
        process=PIN_HOLE_PROCESS,
    )
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
