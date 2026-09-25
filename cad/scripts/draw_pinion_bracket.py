r"""Create the curated machinist drawing for the pinion swing bracket.

The SLDPRT remains authoritative.  This recipe supplies only the strap's
views and its dimension/callout placement; every shared sheet/template,
import, curation and export behaviour lives in ``_drawing_common``, and every
nominal, decimal place and tolerance band is imported from the model.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
bracket carries no datums and no feature-control frames, and it carries no
manufacturing-note block either -- the outline, three bore callouts, two
roughness symbols and the title block say everything.  Three bands survive,
one per fitted bore, each from a named fit class.

Two orthographic views at the 2:1 sheet scale, a follower-seat section, plus
the isometric:

* FRONT -- the strap face: both bores, both end radii and follower-seat height.
* LEFT -- the seat flank, where the blind O4 seat mouth is a SOLID circle:
  its size, its station through the bar and the bar thickness; plus the
  (43.0) overall as a reference, so nobody saws the bar short of the two
  end radii the 28.00 centre distance does not include.  The option E-a
  set-pin cross hole's mouth is a solid circle here too, located by its
  station from broad face A and its height from the pivot-bore wall (the
  part's hidden CrossHoleAxisReference sketch, shown in this view only).
* SECTION B-B -- a cut through the follower-seat axis showing its legitimate
  blind depth and solid flat bottom.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_bracket.py pinion-bracket
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
    add_edge_dimension,
    add_surface_finish,
    assert_imported_precision,
    create_blank_drawing_sheets,
    create_section_view,
    check_drawing_layout,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import (
    curate_view_dimensions as curate_hidden_owner_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_bracket_spec import (
    ARBOR_BORE,
    C2C,
    CROSS_HOLE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DROP,
    DRAWING_REFERENCE_PRECISION,
    OVERALL_LENGTH,
    PIVOT_BORE,
    R_END,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    add_note,
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
SHEET_NAMES = ("MAIN",)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters). The third-angle left view belongs to the LEFT of the
# front view. That leaves the lane between them for the follower-seat location,
# while the bore sizes and radii remain outside the front silhouette.
FRONT_BBOX_CY = (C2C + 2.0 * R_END) / 2.0 - R_END
FRONT_CENTER = (0.210, 0.150)
LEFT_CENTER = (0.080, 0.150)
ISO_CENTER = (0.350, 0.215)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


def _flank_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the left view (same bbox as the front)."""
    return LEFT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0




# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position. The front view carries the upper bore and end radii. The side view
# owns every follower-seat dimension so that its axis is located from visible
# geometry; the relief detail owns the lower pivot bore, and the seat section
# owns depth.
FRONT_KEEP = {
    "ArborBoreDia": (0.256, 0.214),
    "ArborBoreCz": (0.240, 0.151),
    # r6 eye-pass: at (0.250, 0.080) it overprinted the pivot bore's REAM
    # THRU; the lower-left field is clear of the pivot Ra and the title block.
    "BottomCapRadius": (0.170, 0.072),
    "TopCapRadius": (0.188, 0.245),
    "PivotBoreDia": (0.256, 0.086),
}
# The seat's own plane: its mouth circle is solid here, so its size and its
# station through the bar are dimensioned on real geometry.
LEFT_KEEP = {
    "Depth": (0.080, 0.212),
    "PinSeatCy": (0.130, 0.125),
    # r6 eye-pass: beside the view its widest callout line ran across the
    # flank.  Converged-r7: above the view the leader crossed the 9.0 thickness
    # dimension, so the callout sits below-right and its leader rises past the
    # text's left end to the seat, crossing only the bottom outline.
    "PinSeatDia": (0.125, 0.082),
    # Option E-a: the cross-hole mouth sits on the flank at the pivot-bore
    # axis height, below the seat.  pc-ea eye pass: left of the view its
    # 32-character line ran off the sheet's left border, so the callout sits
    # in the clear field under the view, left of the follower-seat callout's
    # underline, and its leader rises to the mouth.
    "CrossHoleDia": (0.053, 0.045),
    # Codex #858 P2, user ruling (a): both through-thickness stations run from
    # broad face A (the view's left edge) -- the cross hole's under the view,
    # left of both callout leaders, the seat's above it, under the 9.0 -- and
    # the cross hole's height from the pivot-bore wall sits in the clear field
    # left of the view.
    "CrossHoleCz": (0.0754, 0.099),
    "PinSeatCz": (0.0754, 0.2025),
    "CrossHoleFromBoreWall": (0.058, 0.119),
}
SECTION_CENTER = (0.350, 0.115)
# Right of the seat's witness lines (x <= 0.3394), callout below the value:
# the above-lane callout never rendered and left a bare 66 mm dimension line.
SECTION_KEEP = {"PinSeatDepth": (0.361, 0.160)}
# The flank's top and bottom edges are the strap's two extreme lines. Put the
# overall on its clear right, between the third-angle left and front views.
OVERALL_XY = (0.112, 0.168)
# The arbor symbol has a short leader to the bore's unobstructed left edge.
ARBOR_FINISH_EDGE = (_front_x(-ARBOR_BORE / 2.0), _front_y(C2C))
ARBOR_FINISH_XY = (0.155, 0.205)
PIVOT_FINISH_EDGE = (_front_x(-PIVOT_BORE / 2.0), _front_y(0.0))
# Low and far left, with the leader to the bore's lower-left quadrant: a
# shallow rise keeps it under the symbol's own Ra text and the B label.
PIVOT_FINISH_XY = (0.136, 0.106)
PIVOT_FINISH_LEADER = (
    _front_x(-PIVOT_BORE / 2.0 * math.cos(math.radians(45.0))),
    _front_y(-PIVOT_BORE / 2.0 * math.sin(math.radians(45.0))),
)
# A callout says only what a dimension cannot: how the feature is made, where
# it stops, and -- for the one dimension held finer than the general grade --
# why it is held there.  Naming both follower-seat annotations ties the native
# diameter and native depth together without copying either model value into
# note text; the depth then reads explicitly from the depicted entry face.
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "REAM THRU",
    "ArborBoreDia": "REAM THRU",
    "PinSeatDia": "FOLLOWER SEAT FOR MHA-116\nBLIND FLAT-BOTTOM\nREAM",
    "CrossHoleDia": CROSS_HOLE_CALLOUT,
}
PIN_SEAT_DEPTH_CALLOUT = "FOLLOWER SEAT\nREAM DEPTH FROM\nENTRY FACE"



def _overall_reference(adapter: Any, left: Any) -> None:
    """The (43.0) overall between the flank's top and bottom runs.

    Both end caps are half-cylinders whose axes run through the bar, so the
    flank shows each as a SILHOUETTE line, not a model edge (the cap's own
    edges are the two arcs on the faces): an EDGE pick there finds nothing
    (farm iter9).
    """
    display = add_edge_dimension(
        adapter,
        left,
        p0=(LEFT_CENTER[0], _flank_y(C2C + R_END)),
        p1=(LEFT_CENTER[0], _flank_y(-R_END)),
        text_xy=OVERALL_XY,
        label="overall length reference",
        orientation="vertical",
        entity_type="SILHOUETTE",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL_LENGTH) > 1e-5:
        raise RuntimeError(
            f"overall length reference measured {measured_mm:g}, "
            f"expected {OVERALL_LENGTH:g} mm"
        )
    set_reference_dimension(
        adapter, display.GetAnnotation(), label="overall length reference"
    )
    # A derived reference has no part-side precision to import; the spec owns
    # the digit (policy rule 2).
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("overall length reference precision did not persist")

def _seat_depth_dimension(adapter: Any, section: Any) -> Any:
    """Import the part's marked seat depth into Section B-B.

    The section plane runs through the seat axis, so the blind cut's own depth
    dimension lies in the view plane and imports as a native model dimension
    with the part-authored places (policy rule 2) -- the sheet never writes a
    precision for a controlling dimension.
    """
    (annotation,) = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="follower seat section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        [annotation],
        {"PinSeatDepth": PIN_SEAT_DEPTH_CALLOUT},
    )
    return annotation


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
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="pinion bracket drawing package"
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
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate pinion bracket main sheet")
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    seat_axis_y = FRONT_CENTER[1] + (-PIN_DROP - FRONT_BBOX_CY) * 2.0 / 1000.0
    seat_section = create_section_view(
        adapter,
        front,
        line_start=(0.180, seat_axis_y),
        line_end=(0.240, seat_axis_y),
        view_xy=SECTION_CENTER,
        section_label="B",
        scale=(3.0, 1.0),
        label="follower seat depth section",
    )
    # Policy rule 7: every view is hidden-lines-removed.  The two reamed
    # through-bores are fully defined by their callouts and the blind seat by
    # its callout plus Section B-B, so no dashed line carries information here
    # (converged-r7 Fable delta, reviewfirst).
    for view in (front, left, iso, seat_section):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="strap face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The part saves CrossHoleAxisReference hidden, so the side view imports
    # through the hidden-owner form, which shows that sketch here only.
    left_annotations = curate_hidden_owner_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="seat flank",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _overall_reference(adapter, left)
    for view, label in ((front, "strap face"), (left, "seat flank")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
    add_surface_finish(
        adapter,
        front,
        edge_xy=ARBOR_FINISH_EDGE,
        symbol_xy=ARBOR_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
        char_height=0.0025,  # the pivot-block size; the default read oversized
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=PIVOT_FINISH_EDGE,
        symbol_xy=PIVOT_FINISH_XY,
        leader_attach_xy=PIVOT_FINISH_LEADER,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
        char_height=0.0025,
    )
    seat_depth = _seat_depth_dimension(adapter, seat_section)


    annotations = [*front_annotations, *left_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(
        adapter, [*annotations, seat_depth], DRAWING_PRECISION_BY_NAME
    )

    for index, sheet_name in enumerate(SHEET_NAMES, start=1):
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to activate sheet {sheet_name!r} for audit")
        if add_note(adapter, f"SHEET {index} OF {len(SHEET_NAMES)}", 0.380, 0.260) is None:
            raise RuntimeError(f"failed to stamp sheet count on {sheet_name!r}")
        rebuild_drawing(adapter, label=f"pinion bracket {sheet_name} layout")
        check_drawing_layout(adapter, layout=SPEC.layout, stem=sheet_name)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Swing Bracket Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
