r"""Create the curated machinist drawing for the pinion swing bracket.

The SLDPRT remains authoritative.  This recipe supplies only the strap's
views and its dimension/callout placement;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.
Every nominal, decimal place and tolerance band is imported from the model.

The print is deliberately plain (cad/docs/drawing-guidelines.md): a
bracket carries no datums and no feature-control frames, and it carries no
manufacturing-note block either -- the outline, the hole callouts (each fitted
bore naming its mate and fit), one roughness symbol and the title block say
everything.  Three bands survive, one per fitted bore, each from a named fit
class, plus the cross hole's pin band.  Decimal-inch sheet (#290).

Two orthographic views at the 2:1 sheet scale, a follower-seat section, plus
the isometric:

* FRONT -- the strap face: both bores, both end radii and follower-seat height.
* LEFT -- the seat flank, where the blind follower seat mouth is a SOLID circle:
  its size, its station through the bar and the bar thickness; plus the
  overall as a reference, so nobody saws the bar short of the two end radii
  the bore centre distance does not include.  The option E-a
  set-pin cross hole's mouth is a solid circle here too, located by its
  station from broad face A, its centre on the pivot-axis line the view draws.
* SECTION B-B -- a cut through the follower-seat axis showing its legitimate
  blind depth and solid flat bottom.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_bracket.py dt-pinion-bracket
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_finish import add_surface_finish
from _drawing_layout_collect import check_drawing_layout
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_pinion_bracket_spec import (
    ARBOR_BORE,
    C2C,
    CROSS_HOLE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    OVERALL_LENGTH,
    PIN_DROP,
    PIN_SEAT_DEPTH_CALLOUT,
    R_END,
    SURFACE_FINISHES,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_pinion_bracket"]
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


_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
FRONT_CENTER_MARKS = 2  # the pivot and arbor bores
LEFT_CENTER_MARKS = 1  # the follower-seat mouth


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position. The front view carries the upper bore and end radii. The side view
# owns every follower-seat dimension so that its axis is located from visible
# geometry; the relief detail owns the lower pivot bore, and the seat section
# owns depth.
FRONT_KEEP = {
    "ArborBoreDia": (0.260, 0.214),
    "ArborBoreCz": (0.240, 0.151),
    # r6 eye-pass: at (0.250, 0.080) it overprinted the pivot bore's REAM
    # THRU; the lower-left field is clear of the title block.
    "BottomCapRadius": (0.170, 0.072),
    "TopCapRadius": (0.188, 0.245),
    # Five rows with its mate and fit: right of the face view's outline, its
    # foot clear of the title block and its head under the B label.
    "PivotBoreDia": (0.260, 0.095),
}
# The seat's own plane: its mouth circle is solid here, so its size and its
# station through the bar are dimensioned on real geometry.
LEFT_KEEP = {
    # Under the 7.000 at the top, inside the 4.50 station (r1: 9.0 at y 0.212
    # had no room for the station's two callout rows beneath it).
    "Depth": (0.080, 0.222),
    # Its function rows hang below the lower witness line: between the two
    # witnesses they would run through the lower one.
    "PinSeatCy": (0.130, 0.108),
    # r6 eye-pass: beside the view its widest callout line ran across the
    # flank.  Converged-r7: above the view the leader crossed the 9.0 thickness
    # dimension.  pc-ra eye pass (Main, nit C): below-right, its leader ran
    # a few pixels from the cross-hole callout's and grazed the cross hole's
    # rim, so the callout sits up-right in the lane between the views, above
    # the 7.000 and under the arbor finish leader, and its leader comes down
    # onto the seat from the upper right.  r1 machinist review (#1007, #1217):
    # that leader crossed the (43.0) dimension line, so the (43.0) moved to
    # the view's left and the callout shifted left, clear of the face view.
    "PinSeatDia": (0.145, 0.170),
    # Option E-a: the cross-hole mouth sits on the flank at the pivot-bore
    # axis height, below the seat.  pc-ea eye pass: left of the view its
    # 32-character line ran off the sheet's left border, so the callout sits
    # in the clear field under the view and its leader rises to the mouth.
    # r2 review (rule 14 polish): from under the view its leader rose almost
    # along the 4.50's hole witness, past that dimension's arrowhead, so it
    # sits down-right, under the 7.000, and its leader climbs at a slant,
    # right of the witness and clear of the 4.50 dimension line.
    "CrossHoleDia": (0.125, 0.078),
    # Codex #858 P2, user ruling (a): both through-thickness stations run from
    # broad face A (the view's left edge) -- the cross hole's under the view,
    # left of both callout leaders, the seat's above it, under the 9.0.
    # pc-ra eye pass: centred between its witnesses the seat's 4.50 was cut
    # by the seat-axis witness, so its text sits left of face A, outside the
    # extension lines.  pc-rc eye pass (nit D): centred, the cross hole's
    # 4.50 threw its right arrow outside the span, where the THRU callout's
    # leader cut through it -- so it sits left of face A too, arrows inside,
    # nothing right of the hole's witness.  The seat's carries two reason
    # rows (r1), so it stands further left and higher, its right end short
    # of face A.
    "CrossHoleCz": (0.058, 0.099),
    "PinSeatCz": (0.043, 0.2055),
}
SECTION_CENTER = (0.350, 0.115)
# The cut's B labels hang under its ends.  Ending at the 28.00's dimension
# line (x 0.240) hung the right B on that dimension's lower arrow (layout
# audit, text-on-line); 0.250 puts it past the arrow and the extension line's
# end.
SECTION_LINE_X = (0.180, 0.250)
# Right of the seat's witness lines (x <= 0.3394), callout below the value:
# the above-lane callout never rendered and left a bare 66 mm dimension line.
# Its widest row (24 characters, ~65 mm) starts right of the entry-face
# witness: centred at 0.361 the floor-corner row sat on that witness (r4).
SECTION_KEEP = {"PinSeatDepth": (0.374, 0.160)}
# The flank's top and bottom edges are the strap's two extreme lines.  The
# overall sits on the view's clear left: on its right the follower-seat
# leader crossed its dimension line (r1 machinist review, rule 14).
OVERALL_XY = (0.040, 0.150)
# The arbor symbol has a short leader to the bore's unobstructed left edge.
ARBOR_FINISH_EDGE = (_front_x(-ARBOR_BORE / 2.0), _front_y(C2C))
ARBOR_FINISH_XY = (0.155, 0.205)
# A callout says only what a dimension cannot: how the feature is made, where
# it stops, what it mates with and the fit it needs (rule 4), and -- for the
# dimensions held finer than the general grade -- why they are held there.
# Naming both follower-seat annotations ties the native diameter and native
# depth together without copying either model value into note text; the
# depth then reads explicitly from the depicted entry face.  The pivot bore
# is a slide fit so the strap goes onto the shaft for fit-up, then pinned
# (option E-a); the arbor runs in its bore; the follower stud slips into its
# seat and is bonded (LOCTITE 638, dt_pinion_cam_pin_spec's bond gap).
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "REAM THRU\nSLIDE FIT ON SHAFT\nMHA-DT-19, PINNED",
    "ArborBoreDia": "REAM THRU\nRUNNING FIT ON\nARBOR MHA-DT-22",
    "PinSeatDia": "FOLLOWER SEAT FOR MHA-DT-25\nBONDED SLIP FIT\nBLIND FLAT-BOTTOM REAM",
    "CrossHoleDia": CROSS_HOLE_CALLOUT,
    # The two held locations name what they serve (rules 3 and 4): the
    # follower's height sets the drum's swing for a given cam lift
    # (DRAWING_PRECISION), and the seat's station keeps it mid-bar
    # (PIN_SEAT_WEB_WORST, user ruling (a)).  SOLIDWORKS starts the follower
    # height's text at its bent dimension line, so that leg touched the leading
    # S of SETS (r3 review, rule 14); the leading spaces stand the rows off it.
    "PinSeatCy": "   SETS FOLLOWER HEIGHT\n   ON MHA-DT-23 CAM",
    "PinSeatCz": "CENTRES MHA-DT-25\nFOLLOWER IN BAR",
}
# The bar thickness is held at .XXX for the axial stack it closes: two straps,
# the drum, its shim and feeler fill the span between the MHA-DT-18 blocks
# (pinion_rig_layout).  Above the value, on one line (a multi-line
# above-callout does not print, draw_dt_pinion_pivot_block): below it the rows
# would run across both thickness witnesses and the seat station's.
CALLOUTS_ABOVE = {"Depth": "AXIAL STACK IN MHA-DT-18 SPAN"}


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
    # the digit (drawing-simplicity-policy.md `How the repository implements the guidelines`).
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("overall length reference precision did not persist")

def _seat_depth_dimension(adapter: Any, section: Any) -> Any:
    """Import the part's marked seat depth into Section B-B.

    The section plane runs through the seat axis, so the blind cut's own depth
    dimension lies in the view plane and imports as a native model dimension
    with the part-authored places (drawing-simplicity-policy.md `How the repository implements the guidelines`) -- the sheet never writes a
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("dt-pinion-bracket"),
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
        line_start=(SECTION_LINE_X[0], seat_axis_y),
        line_end=(SECTION_LINE_X[1], seat_axis_y),
        view_xy=SECTION_CENTER,
        section_label="B",
        scale=(3.0, 1.0),
        label="follower seat depth section",
    )
    # drawing-guidelines.md rule 9 (show internal shape in solid lines): every view is hidden-lines-removed.  The two reamed
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
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="seat flank",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _overall_reference(adapter, left)
    # #913: the template marks the holes as each view is placed, and the
    # explicit AutoInsertCenterMarks2 then printed every mark twice (v43
    # layout audit: DetailItem347/351, 348/352 on the face, 349/353 on the
    # flank).  Add marks only to a bare view, then prove exactly one per hole:
    # both bores on the face, the follower-seat mouth on the flank.
    for view, label, expected in (
        (front, "strap face", FRONT_CENTER_MARKS),
        (left, "seat flank", LEFT_CENTER_MARKS),
    ):
        if _center_mark_count(view) == 0 and not auto_center_marks(
            adapter, view, holes=True, size=0.0025
        ):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
        found = _center_mark_count(view)
        if found != expected:
            raise RuntimeError(
                f"expected {expected} centre marks in the {label} view, found {found}"
            )
    add_surface_finish(
        adapter,
        front,
        edge_xy=ARBOR_FINISH_EDGE,
        symbol_xy=ARBOR_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
        char_height=0.0025,  # the pivot-block size; the default read oversized
    )
    seat_depth = _seat_depth_dimension(adapter, seat_section)


    annotations = [*front_annotations, *left_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, left_annotations, CALLOUTS_ABOVE, location="above")
    assert_imported_precision(
        adapter, [*annotations, seat_depth], DRAWING_PRECISION_BY_NAME
    )

    for sheet_name in SHEET_NAMES:
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to activate sheet {sheet_name!r} for audit")
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
