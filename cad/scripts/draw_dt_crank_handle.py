r"""Create the curated machinist drawing for the crank handle.

A turned, ebonized oak pear grip (book ch. 11).  User ruling 2026-09-29: the
brass ferrule MHA-DT-034 and the steel butt cup MHA-DT-035 are separate parts, so
this sheet prints only the oak -- a tenon for the ferrule at the crank end, a
flared waist, an S-curve swell to the Ø21 max, and a domed butt whose end
round crests on a flat oak end round the cup bonded into its counterbore
(user rulings 2026-09-30, concept v4).

The sheet is plain (user ruling 2026-09-29): no datums, feature-control frames
or basic dimensions, and no general notes (MHA-DT-008 machinist review of
2026-10-18).  The longitudinal section A-A, taken on the end view's vertical
centre line, is the handle's length view (drawing-guidelines.md rule 11
(turned parts read like the lathe)): the profile, the reamed bore and the
counterbore all sketch on the Front plane the section lies in, so every size
prints there.  The stations stack above it in a baseline from the tenon end
face, with the tangency-fixed radii as references beneath them; the diameters
are dimensioned across their own cut, their text on shelves clear of the
section; the fitted tenon and counterbore carry their mates and clearances as
callouts, and the tenon root and the counterbore's floor corner their R0.3 MAX
single limits with the part that seats on each.  The end
view stands on the section's axis and carries the cutting plane.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle.py dt-crank-handle
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
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
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _telemetry
from dt_crank_handle_spec import (
    COUNTERBORE_DEPTH,
    COUNTERBORE_FIT_NOTE,
    COUNTERBORE_FLOOR_CALLOUT,
    COUNTERBORE_FLOOR_X,
    DOME_CENTER,
    DOME_R,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    END_ROUND_CENTER,
    FLARE_CENTER,
    HANDLE_MAX_DIA,
    INFLECTION,
    INSIDE_CORNER_R_MAX,
    INSIDE_CORNER_R_TOL_TYPE,
    OAK_END_X,
    PEAK_X,
    PIVOT_BORE_CALLOUT,
    REFERENCE_DIMENSIONS,
    REFERENCE_RADII,
    S_CONCAVE_CENTER,
    S_CONVEX_CENTER,
    S_CONVEX_R,
    SHOULDER_X,
    TENON_FIT_NOTE,
    TENON_R,
    TENON_ROOT_CALLOUT,
    TENON_X0,
    WAIST_X,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_handle"]
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

# 4:1 gives the five-arc profile room for its stations, diameters and radii:
# the section reads 224 x 84 on the sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / 1000.0

# The section lays the handle axis horizontal, tenon at the left and butt at
# the right (the part's +X to the right, as MHA-DT-035's section shows), centred
# on the oak's extent.  The end view stands on the same axis height.  The axis
# sits low enough that the S-curve's concave centre (26.4 above it) falls
# under the long station rows, so its radius line crosses none of them.
FRONT_BBOX_CX = (TENON_X0 + OAK_END_X) / 2.0
FRONT_CENTER = (0.162, 0.130)
RIGHT_CENTER = (0.362, FRONT_CENTER[1])
ISO_CENTER = (0.380, 0.235)
ISO_NOTE_POS = (0.285, 0.244)
CAPTION_XY = (0.085, 0.052)

END_R = HANDLE_MAX_DIA * _S / 2.0


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model station (x from the arm face) on the section."""
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * _S


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model height (up from the axis) on the section."""
    return FRONT_CENTER[1] + model_y_mm * _S


def _on_radius(
    center: tuple[float, float], distance_mm: float, degrees: float
) -> tuple[float, float]:
    """Sheet point ``distance_mm`` from a model arc centre at ``degrees`` CCW."""
    angle = math.radians(degrees)
    return (
        _front_x(center[0] + distance_mm * math.cos(angle)),
        _front_y(center[1] + distance_mm * math.sin(angle)),
    )


# Rows above the section, the stations in a baseline from the tenon end face,
# shortest nearest: the two that end left of the waist below the S-curve's
# concave centre, the three that run past it above it; the counterbore depth
# from the oak end on the second row.
_ROW = (0.195, 0.205, 0.242, 0.250, 0.258)
# A diameter's text hangs on a shelf off its dimension line, on the side the
# text stands from the point it measures to (a line's END point; r2/r3 sheets):
# each stands right of it, so every shelf runs right.
_SHELF = 0.0015
_BELOW = 0.098
_CALLOUT_ROW = 0.080
FRONT_KEEP = {
    "TenonLength": (_front_x((TENON_X0 + SHOULDER_X) / 2.0), _ROW[0]),
    "WaistStation": (_front_x((TENON_X0 + WAIST_X) / 2.0), _ROW[1]),
    "InflectionStation": (_front_x((TENON_X0 + INFLECTION[0]) / 2.0), _ROW[2]),
    "PeakStation": (_front_x((TENON_X0 + PEAK_X) / 2.0), _ROW[3]),
    "OverallLength": (_front_x(FRONT_BBOX_CX), _ROW[4]),
    "CounterboreDepth": (_front_x(OAK_END_X - COUNTERBORE_DEPTH / 2.0), _ROW[1]),
    # The radii stand between the station extension lines, below the rows:
    # the convex ones outside their arcs (a short leader to the arc), the
    # concave ones between centre and arc.
    "FlareR": _on_radius(FLARE_CENTER, 5.3, 245.0),
    "SConcaveR": _on_radius(S_CONCAVE_CENTER, 15.5, 285.0),
    "SConvexR": _on_radius(S_CONVEX_CENTER, S_CONVEX_R + 5.0, 100.0),
    "DomeR": _on_radius(DOME_CENTER, DOME_R + 5.0, 78.0),
    "EndRoundR": _on_radius(END_ROUND_CENTER, 8.1, 42.5),
    # Diameters across their own cut.  The shoulder and waist shelves sit
    # under the section; the fitted tenon's and the counterbore's callout
    # blocks stand below them, above the title block, and the reamed bore's
    # lower still between them, clear of the swell.  The counterbore's
    # five-line block stands near its floor, clear of the end view.
    "ShoulderDia": (_front_x(SHOULDER_X) + _SHELF, _BELOW),
    "WaistDia": (_front_x(WAIST_X) + _SHELF, _BELOW),
    "TenonDia": (_front_x(TENON_X0) + 4.0 * _SHELF, _CALLOUT_ROW),
    "PivotBoreDia": (0.140, 0.068),
    "CounterboreDia": (
        _front_x(OAK_END_X - COUNTERBORE_DEPTH) + 0.0055,
        _CALLOUT_ROW + 0.0015,
    ),
    # The swell's diameter reads above the section, clear of the bore's
    # callout, beside the 40.0 station's extension line.
    "PeakDia": (_front_x(PEAK_X) + 2.0 * _SHELF, 0.225),
    # Right of the oak end, above the crest, under the R1.5 and clear of the
    # end view and of the counterbore's callout block.
    "CrestDia": (_front_x(OAK_END_X) + 0.0095, 0.165),
    # The inside corners' three-row blocks (R0.3 MAX / mate / SEAT), 8 x 2.75 =
    # 22.0 mm wide and 2 x 5.55 + 3.5 = 14.6 mm tall, centred on the keep (were
    # the rows to hang from the keep instead, each box drops ~7 mm and stays
    # clear):
    #   Tenon root, left of the tenon end: box x 0.024..0.046, y 0.1607..
    #   0.1753 -- 4.0 mm clear of the tenon end's extension line (x 0.050),
    #   11.3 inside the border, 16.9 under the 5.0's outside tail (y 0.1922).
    #   Its leader runs down-right through the air over the tenon to the
    #   corner, crossing that extension line at y ~0.158 (4 mm from the text)
    #   and passing ~9 mm over the tenon diameter's extension line (y 0.1452).
    "TenonRootRadius": (_front_x(TENON_X0) - 0.015, _front_y(TENON_R) + 0.0228),
    #   Counterbore floor, above the section between the swell diameter's
    #   dimension line (x 0.213) and the 8.1's floor extension line (x
    #   0.2416): box x 0.2163..0.2383 (3.3 mm clear of each), y 0.1877..0.2023
    #   -- 15.8 above the silhouette (y <= 0.1719 there), 19.9 under the
    #   swell diameter's text (y 0.2222).  Its leader drops ~23 mm through the
    #   oak to the corner (under the corner's 25.4 approach to the section's
    #   top edge) and crosses the 8.1's floor extension line at y ~0.157,
    #   31 mm from either text.
    "CounterboreFloorRadius": (_front_x(COUNTERBORE_FLOOR_X) - 0.0143, 0.195),
}
# Every band renders from its model dimension; the callouts carry the reamed
# bore's mate, the fitted tenon's and counterbore's mates and clearances, and
# the part seating on each inside corner (drawing-guidelines.md rules 4 and 7).
DIMENSION_CALLOUTS = {
    "PivotBoreDia": PIVOT_BORE_CALLOUT,
    "TenonDia": TENON_FIT_NOTE,
    "CounterboreDia": COUNTERBORE_FIT_NOTE,
    "TenonRootRadius": TENON_ROOT_CALLOUT,
    "CounterboreFloorRadius": COUNTERBORE_FLOOR_CALLOUT,
}
# Each inside corner's text stands up-left of its arc's centre: the tenon
# root's (the arc's lower-right quarter) off the arc's span, the counterbore
# floor's (its upper-left quarter) inside it.
INSIDE_CORNER_ARC_EXTENSION = {
    "TenonRootRadius": True,
    "CounterboreFloorRadius": False,
}
RADII = (*sorted(REFERENCE_RADII), "EndRoundR")
CUT_START = (RIGHT_CENTER[0], RIGHT_CENTER[1] - END_R - 0.006)
CUT_END = (RIGHT_CENTER[0], RIGHT_CENTER[1] + END_R + 0.006)
_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside


def _style_radius(adapter: Any, annotation: Any, *, name: str, reference: bool) -> None:
    """Arrow outside, no solid leader: the convex arcs' leaders run from the
    text to the arc and stop there, since the swell and dome centres lie off
    the sheet (draw_ch_fulcrum_keeper._set_crown_reference).
    A tangency-fixed radius prints as the reference "(R59.5)"; the bare "("
    prefix of set_reference_dimension would replace SolidWorks' own radius
    glyph, so whatever prefix the display carries stays behind it."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError(f"MHA-DT-008 {name} imported as a diameter")
    if reference:
        existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
        prefix = "(" + existing
        display.SetText(1, prefix)
        display.SetText(2, ")")  # swDimensionTextSuffix
        applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        _telemetry.info(f"{name}: radial reference prefix {existing!r} -> {applied[0]!r}")
        if applied != (prefix, ")"):
            raise RuntimeError(f"failed to mark MHA-DT-008 {name} as a reference: {applied}")
    display.ArcExtensionLineOrOppositeSide = False
    display.ArrowSide = _ARROWS_OUTSIDE
    display.SolidLeader = False
    if (
        bool(display.ArcExtensionLineOrOppositeSide)
        or int(display.ArrowSide) != _ARROWS_OUTSIDE
        or bool(display.SolidLeader)
    ):
        raise RuntimeError(f"MHA-DT-008 {name} kept its leader to the arc's centre")


def _dress_inside_corner(adapter: Any, annotation: Any, *, name: str) -> None:
    """Prove an imported inside-corner radius prints the part's R0.3 MAX with
    its mate callout, and land its leader on the corner
    (draw_mg_magnifying_vertical_rod._dress_relief_roots).

    Read back: radial (not a diameter), measuring INSIDE_CORNER_R_MAX, the
    native swTolMAX the part set, and the callout under the value.
    SolidWorks ends a radial leader at the circle point facing its text, so a
    text standing off the arc's span takes ``ArcExtensionLineOrOppositeSide``
    True to draw the arc's extension out to that point (farm r4 of the
    magnifying rod); one inside the span lands on the arc itself."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError(f"MHA-DT-008 {name} imported as a diameter")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != INSIDE_CORNER_R_TOL_TYPE:
        raise RuntimeError(
            f"MHA-DT-008 {name} lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), INSIDE_CORNER_R_MAX / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError(f"MHA-DT-008 {name} does not measure the inside corner")
    callout = str(display.GetText(4) or "")  # swDimensionTextCalloutBelow
    if callout != DIMENSION_CALLOUTS[name]:
        raise RuntimeError(f"MHA-DT-008 {name} callout did not persist: {callout!r}")
    extension = INSIDE_CORNER_ARC_EXTENSION[name]
    display.ArcExtensionLineOrOppositeSide = extension
    if bool(display.ArcExtensionLineOrOppositeSide) is not extension:
        raise RuntimeError(f"MHA-DT-008 {name} refused its arc extension setting")
    _telemetry.info(
        f"{name}: text {display.GetText(1)!r}, MAX type, callout {callout!r}"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Crank Handle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle; turned oak pear grip; ferrule tenon and cup counterbore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    front = create_section_view(
        adapter,
        right,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=FRONT_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="crank handle longitudinal section",
    )
    position_section_caption(adapter, front, CAPTION_XY, label="crank handle")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    front.SetDisplayTangentEdges2(0)
    if int(front.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError("failed to hide crank-handle tangent edges")
    front.UpdateViewDisplayGeometry()

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, front_annotations, DRAWING_PRECISION_BY_NAME)
    front_by_name = {dimension_name(adapter, a): a for a in front_annotations}
    # The tenon and the counterbore are fitted to the ferrule and cup (their
    # to-suit callouts), so their sizes print as references.
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter,
            front_by_name[name],
            label=f"MHA-DT-008 {name}",
            diameter=name.endswith("Dia"),
        )
    for name in RADII:
        _style_radius(
            adapter, front_by_name[name], name=name, reference=name in REFERENCE_RADII
        )
    for name in sorted(INSIDE_CORNER_ARC_EXTENSION):
        _dress_inside_corner(adapter, front_by_name[name], name=name)
    rebuild_drawing(adapter, label="crank-handle radii")
    create_section_axis_centerline(
        adapter, front, length_mm=OAK_END_X - TENON_X0, label="crank handle axis"
    )
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to crank-handle end view")

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Manufacturing Drawing",
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
