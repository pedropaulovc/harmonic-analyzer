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

Three views at the 2:1 sheet scale plus a 4:1 section:

* FRONT -- the strap face: both bores, both end radii, the two cam-relief
  scallops and the follower-seat height.
* LEFT -- the seat flank, where the blind O4 seat mouth is a SOLID circle:
  its size, its station through the bar and the bar thickness.
* SECTION A-A -- cut on the seat axis, the only place the seat's blind depth
  and flat bottom are solid lines.  Hidden lines are removed everywhere, so
  no dimension attaches to a dashed edge.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_bracket.py pinion-bracket
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_bracket_spec import (
    ARBOR_BORE,
    C2C,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    OVERALL_LENGTH,
    PIN_DROP,
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
SECTION_SCALE = (4, 1)

# Sheet layout (meters).  The strap runs UP the sheet: the front view's model
# bbox is +/-7.5 in X and -7.5..35.5 in Y, so at 2:1 it is 30 x 86 mm and the
# left flank view beside it is 16 x 86.  The section is a 15 x 8 slice, too
# small to read at the sheet scale, so it runs at 4:1 in its own lane.
FRONT_BBOX_CY = (OVERALL_LENGTH / 2.0) - R_END
FRONT_CENTER = (0.100, 0.150)
LEFT_CENTER = (0.180, 0.150)
SECTION_CENTER = (0.250, 0.090)
ISO_CENTER = (0.345, 0.195)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


PIVOT_R_SHEET = PIVOT_BORE * SHEET_SCALE[0] / 2000.0
ARBOR_R_SHEET = ARBOR_BORE * SHEET_SCALE[0] / 2000.0

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The face features and their locations stay on the front view; the
# scallop pair is dimensioned on the open (left) side it is cut from, the two
# bore diameters and the end radii on the closed right side.
FRONT_KEEP = {
    "PivotBoreDia": (0.152, 0.112),
    "ArborBoreDia": (0.152, 0.192),
    "ArborBoreCz": (0.124, 0.152),
    "BottomCapRadius": (0.126, 0.092),
    "TopCapRadius": (0.126, 0.212),
    "PinSeatCy": (0.076, 0.146),
    "CamReliefParkR": (0.036, 0.178),
    "CamReliefParkY": (0.064, 0.133),
    "CamReliefParkX": (0.087, 0.101),
    "CamReliefEngagedR": (0.036, 0.074),
    "CamReliefEngagedY": (0.048, 0.110),
    "CamReliefEngagedX": (0.087, 0.089),
}
# The seat's own plane: its mouth circle is solid here, so its size and its
# station through the bar are dimensioned on real geometry.
LEFT_KEEP = {
    "Depth": (0.180, 0.206),
    "PinSeatCz": (0.180, 0.100),
    "PinSeatDia": (0.216, 0.140),
}
SECTION_KEEP = {"PinSeatDepth": (0.250, 0.118)}
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "REAM THRU",
    "ArborBoreDia": "REAM THRU",
    "PinSeatDia": "REAM",
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
    # Nothing on this part is communicated by a dashed edge: both bores and
    # both scallops are open profiles on the face, the seat mouth is a solid
    # circle on the flank, and the seat's depth is a section.
    for view in (front, left, iso):
        set_hidden_lines_removed(adapter, view)

    # A-A is taken ON the follower-seat axis, so the seat's blind bottom and
    # its 4 mm depth are cut geometry rather than a hidden outline.  The line
    # runs past both flanks so the whole 15 mm width is sectioned.
    seat_y = -PIN_DROP
    cut_left = model_point_in_view(
        adapter, front, (-12.0, seat_y, 0.0), label="section A-A start"
    )
    cut_right = model_point_in_view(
        adapter, front, (12.0, seat_y, 0.0), label="section A-A end"
    )
    section = create_section_view(
        adapter,
        front,
        line_start=cut_left,
        line_end=cut_right,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="follower-seat axial section",
    )
    set_hidden_lines_removed(adapter, section)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="strap face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The seat profile is authored on a Right-parallel plane, so its three
    # dimensions are native to this flank view; the face import above rejects
    # the two it does not place, which returns them to the import pool.
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="seat flank",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="seat section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *left_annotations, *section_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Decimal places are the tolerance statement and the part owns them; this
    # sheet only proves the import kept them (policy rule 2).
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    for view, label in ((front, "strap face"), (left, "seat flank")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # The overall: a read-only sum of the bore centre distance and the two end
    # radii, so nobody saws the bar short.  Picked on the cap arcs' outer
    # extremes so the tangent-arc condition measures end to end.
    overall = add_edge_dimension(
        adapter,
        front,
        p0=(_front_x(0.0), _front_y(-R_END)),
        p1=(_front_x(0.0), _front_y(C2C + R_END)),
        text_xy=(0.140, 0.152),
        label="overall length reference",
        orientation="vertical",
    )
    set_arc_endpoints_to_max(adapter, overall, label="overall length reference")
    # add_edge_dimension hands back the IDisplayDimension late-bound; bind it
    # before reading the IAnnotation the reference helper wants.
    overall_display = _early_bound(overall, "IDisplayDimension")
    set_reference_dimension(
        adapter,
        overall_display.GetAnnotation(),
        label="overall length reference",
    )
    overall_display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(overall_display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("overall length reference precision did not persist")

    # Both bores run: the torque shaft in the lower one, the pinion arbor in
    # the upper one.  Nothing else on the strap slides, seats or locates.
    add_surface_finish(
        adapter,
        front,
        edge_xy=(_front_x(0.0), _front_y(0.0) - PIVOT_R_SHEET),
        symbol_xy=(0.152, 0.094),
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(_front_x(0.0), _front_y(C2C) + ARBOR_R_SHEET),
        symbol_xy=(0.152, 0.210),
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
