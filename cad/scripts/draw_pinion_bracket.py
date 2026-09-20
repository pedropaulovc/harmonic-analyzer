r"""Create the curated machinist drawing for the pinion swing bracket.

The SLDPRT remains authoritative.  This recipe supplies only the strap's
views and its dimension/callout placement; every shared sheet/template,
import, curation and export behaviour lives in ``_drawing_common``, and every
nominal, decimal place and tolerance band is imported from the model.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
bracket carries no datums and no feature-control frames, and it carries no
manufacturing-note block either -- the outline, the four hole/scallop
callouts, two roughness symbols and the title block say everything.  Three
bands survive, one per fitted bore, each from a named fit class.

Two orthographic views at the 2:1 sheet scale, plus the isometric:

* FRONT -- the strap face: both bores, both end radii, the two cam-relief
  scallops, the follower-seat height and the seat's blind depth.  This is
  the only view carrying hidden lines, and the blind seat is the only
  feature that needs them: both bores and both scallops go clean through.
* LEFT -- the seat flank, where the blind O4 seat mouth is a SOLID circle:
  its size, its station through the bar and the bar thickness.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_bracket.py pinion-bracket
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_surface_finish,
    assert_imported_precision,
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
from _surface_finish import surface_finish_by_key
from pinion_bracket_spec import (
    ARBOR_BORE,
    C2C,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIVOT_BORE,
    R_END,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_bracket"]
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

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  The strap runs UP the sheet: the front view's model
# bbox is +/-7.5 in X and -7.5..35.5 in Y, so at 2:1 it is 30 x 86 mm and the
# left flank view beside it is 16 x 86.  The face view keeps the clear column
# to its LEFT for everything measured off the pivot axis and the column to its
# RIGHT for the leadered sizes, so no two dimension lanes cross.  Each end
# radius is labelled almost straight below/above its own arc while that bore's
# roughness symbol leads away to the side: the two leaders leave the same
# crowded corner on diverging paths and never cross.
FRONT_BBOX_CY = (C2C + 2.0 * R_END) / 2.0 - R_END
FRONT_CENTER = (0.100, 0.150)
LEFT_CENTER = (0.180, 0.150)
ISO_CENTER = (0.345, 0.195)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The face features and their locations stay on the front view; the
# scallop pair is dimensioned on the open (left) side it is cut from, the two
# bore diameters and the end radii on the closed right side.
FRONT_KEEP = {
    "PivotBoreDia": (0.156, 0.110),
    "ArborBoreDia": (0.156, 0.194),
    "ArborBoreCz": (0.130, 0.151),
    "BottomCapRadius": (0.126, 0.062),
    "TopCapRadius": (0.126, 0.238),
    "PinSeatCy": (0.058, 0.134),
    "PinSeatDepth": (0.052, 0.156),
    "CamReliefParkR": (0.022, 0.130),
    "CamReliefParkY": (0.044, 0.112),
    "CamReliefParkX": (0.082, 0.070),
    "CamReliefEngagedR": (0.022, 0.104),
    "CamReliefEngagedY": (0.032, 0.096),
    "CamReliefEngagedX": (0.082, 0.058),
}
# The seat's own plane: its mouth circle is solid here, so its size and its
# station through the bar are dimensioned on real geometry.
LEFT_KEEP = {
    "Depth": (0.180, 0.212),
    "PinSeatCz": (0.180, 0.090),
    "PinSeatDia": (0.230, 0.140),
}
# Each bore's end-radius label leads out to the LEFT of its arc and that same
# bore's roughness symbol to the RIGHT, so the two leaders leaving the same
# crowded corner diverge instead of crossing.
PIVOT_FINISH_EDGE = (_front_x(0.0), _front_y(-PIVOT_BORE / 2.0))
PIVOT_FINISH_XY = (0.126, 0.092)
ARBOR_FINISH_EDGE = (_front_x(0.0), _front_y(C2C + ARBOR_BORE / 2.0))
ARBOR_FINISH_XY = (0.126, 0.208)
# A callout says only what a dimension cannot: how the feature is made, where
# it stops, and -- for the one dimension held finer than the general grade --
# why it is held there.
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "REAM THRU",
    "ArborBoreDia": "REAM THRU",
    "PinSeatDia": "REAM; FLAT-BOTTOM BLIND",
    "PinSeatDepth": "DEPTH FROM ENTRY FACE",
    "PinSeatCy": "CAM ENGAGE CLEARANCE - HOLD FINE GRADE",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-bracket source", await adapter.open_model(str(SOURCE)))
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
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Swing Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion swing bracket; manufacturing drawing; pivot strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    # Only ONE feature on this strap is invisible in outline -- the blind
    # follower seat -- and only the face view sees it, so only the face view
    # carries hidden lines.  Both bores and both scallops go clean through,
    # so nothing else turns dashed and the flank view stays clean.
    set_hidden_lines_visible(adapter, front)
    for view in (left, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="strap face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The seat profile is authored on a Right-parallel plane, so its size and
    # its station through the bar are native to this flank view; the face
    # import above rejects the two it does not place, which returns them to
    # the import pool.
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="seat flank",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *left_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Decimal places are the tolerance statement and the part owns them; this
    # sheet only proves the import kept them (policy rule 2).
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    for view, label in ((front, "strap face"), (left, "seat flank")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Both bores run: the torque shaft in the lower one, the pinion arbor in
    # the upper one.  Nothing else on the strap slides, seats or locates.
    add_surface_finish(
        adapter,
        front,
        edge_xy=PIVOT_FINISH_EDGE,
        symbol_xy=PIVOT_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=ARBOR_FINISH_EDGE,
        symbol_xy=ARBOR_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Swing Bracket Manufacturing Drawing",
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
