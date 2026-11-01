r"""Create the manufacturing drawing for the rocker strap (MHA-CH-13).

Under ``cad/docs/drawing-guidelines.md``, in decimal inch (the part's
``drawing_unit: in``): the flat strap of the built-up rocker arm MHA-CH-06
(``ch_rocker_strap_spec``), every size a native model dimension of its one
profile sketch, located from the Ø.4000 hub hole's centre (rule 10): the top
edge's height over the hole with the MHA-CH-06 band and mate, the R31.5 top
edge (its centre, ~32 in off the sheet, stated on it as above the hole), the
bottom edge's depth under the hole, both tip corners' and both taper feet's
offsets, and the 2X radial tip land; the parenthesised overall length across
the tip corners ties the two offsets together (rule 10: the overall size is
conspicuous). The hole's press band names the MHA-CH-12 hub and the fit
(rule 4) and keeps both its edges sharp (the title block's break would groove
the pressed root); the thickness,
on the end view, names the rod fork it runs in. One property-linked note names
the joint the finish field's "after joining" refers to. No datums, no frames,
no roughness symbol (rule 6: a pressed bore carries none). The decimal places
and bands are the PART's (``ch_rocker_strap_notes.DRAWING_PRECISION``); this
script only reads them back off the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_strap.py ch-rocker-strap
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from ch_rocker_strap_notes import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
)
from ch_rocker_strap_spec import (
    ARM_THICKNESS,
    BOT_END_X,
    DRAWING_REFERENCE_PRECISION,
    PIVOT_MID_Y,
    ROD_TIP_X,
    ROD_TIP_Y,
    TOP_END_Y,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_strap"]
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

# The 292.5 mm strap at full size across the sheet's upper band, its 2.5 mm
# end view to the right; the isometric at 1:2 (captioned, it differs from the
# sheet scale) and the note sit left of the title block below. At 1:4 the
# 2.5 mm plate rendered stair-stepped (r1 and r4 machinist reviews), so the
# view is doubled: its diagonal runs ~(0.083, 0.115) to ~(0.187, 0.049),
# under the foot offsets' line (y 0.125) and left of the title block (x
# 0.215), the caption in the empty corner below its upper-left end.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
FRONT_CENTER = (0.185, 0.185)
RIGHT_CENTER = (0.385, FRONT_CENTER[1])  # projected: same row as the front
ISO_CENTER = (0.135, 0.082)
ISO_CAPTION_XY = (0.105, 0.052)  # centred under the pictorial's low end
NOTES_XY = (0.020, 0.040)


def _front(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a model (x, y) on the 1:1 front view, whose box is
    centred on FRONT_CENTER: x spans +-ROD_TIP_X, y 0..TOP_END_Y."""
    return (
        FRONT_CENTER[0] + x_mm / 1000.0,
        FRONT_CENTER[1] + (y_mm - TOP_END_Y / 2.0) / 1000.0,
    )


_HOLE = _front(0.0, PIVOT_MID_Y)
# The tip corners' offsets on one dimension line above the strap, the taper
# feet's on one below it, each pair meeting on the hole centre's extension
# line. Between the strap and the lower line: the R800's text (far left,
# below both arcs, so its leader stays outside its circle --
# draw_ch_rocker_arm _dress_arc_radii), the bottom edge's depth under the
# hole and the hole's callout (right, its leader short). The top edge's
# height reads left of the hole, under the upper line. A vertical dimension's
# text stands LEFT of its dimension line, ending at the requested x (r3: the
# depth's ~55 mm rows ran x 0.093..0.147 over the R800 at x 0.100), so the
# depth's line sits 12 mm left of the hole (rows ~0.118..0.173) and the R800
# block (centred on its x, ~47 mm wide with its CENTRE ABOVE HOLE row) moves
# to x 0.090, right of the left foot's extension line at x 0.052, raised so
# its leader up to the top arc clears those rows (top ~0.171).
TIP_LINE_Y = 0.232
FOOT_LINE_Y = 0.125
# The overall length (ENFORCE r3: only the two 146.25 offsets gave it) on its
# own row above the offsets' line, the longest outermost, under the border
# (~0.267).
OVERALL_LINE_Y = 0.249
FRONT_KEEP = {
    "TailTipX": (FRONT_CENTER[0] - ROD_TIP_X / 2000.0, TIP_LINE_Y),
    "RodTipX": (FRONT_CENTER[0] + ROD_TIP_X / 2000.0, TIP_LINE_Y),
    "BottomTailX": (FRONT_CENTER[0] - BOT_END_X / 2000.0, FOOT_LINE_Y),
    "BottomRodX": (FRONT_CENTER[0] + BOT_END_X / 2000.0, FOOT_LINE_Y),
    "TopRadius": (FRONT_CENTER[0] - 0.095, 0.166),
    "BottomBelowPivot": (_HOLE[0] - 0.012, 0.160),
    # The callout's rows stack UP from the requested y: with its sharp-edge
    # row at 0.160 (strap-sharp-r1) the +0.018 limit sat on the strap's bottom
    # edge. Dropped one row for that row (0.153, r2: clear), then 4 mm more
    # for its reason row (r3), whose last row still clears the foot line.
    "HoleDia": (_HOLE[0] + 0.060, 0.149),
    "TopAbovePivot": (_HOLE[0] - 0.035, 0.207),
    # The land's two extension lines run ~5.6 mm apart, rising ~10 deg to the
    # right (perpendicular to the radial land); the upper one passes y ~0.206
    # at x 0.365. Between them (r1, r2) a line struck the text, so it stands
    # above both, the dimension line carried up to it, high enough (r3 -> r4)
    # that its RADIAL row below the value clears that line too.
    "RodTipLen": (_front(ROD_TIP_X, 0.0)[0] + 0.031, 0.226),
}
# The 2.5 mm end view is narrower than its four-row callout: centred over it
# (r1) both extension lines ran through the text, so the text stands below
# the view, left of its left extension line, the dimension line carried out.
RIGHT_KEEP = {"StrapThickness": (RIGHT_CENTER[0] - 0.027, 0.150)}
ARC_RADIUS_NAMES = ("TopRadius",)


def _exterior_radius_leaders(adapter: Any, annotations: list[Any]) -> None:
    """Exterior leader on the top radius (draw_ch_rocker_arm._dress_arc_radii):
    the ~32 in centre is off the sheet, so no centre-directed leader."""
    remaining = set(ARC_RADIUS_NAMES)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = False
        display.ArcExtensionLineOrOppositeSide = False
        display.ArrowSide = 1  # swDimArrowsOutside
        display.SolidLeader = False
        if (
            bool(display.ShortenedRadius)
            or bool(display.ArcExtensionLineOrOppositeSide)
            or int(display.ArrowSide) != 1
            or bool(display.SolidLeader)
        ):
            raise RuntimeError(f"{name} retained its centre-directed radius leader")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"strap radius dimensions missing: {sorted(remaining)}")


@_telemetry.traced("drawing.strap_overall_length")
def _add_overall_length(adapter: Any, front: Any) -> None:
    """Parenthesised overall length across both tip corners (rule 10), a
    native vertex-to-vertex sheet dimension (draw_ch_rocker_arm's overall
    width): a band-free restatement of the two offsets, so no band and no
    second model size."""
    label = "OverallLength"
    # The +Z face's tip corners: the strap is extruded mid-plane in Z.
    tips = (
        (-ROD_TIP_X, ROD_TIP_Y, ARM_THICKNESS / 2.0),
        (ROD_TIP_X, ROD_TIP_Y, ARM_THICKNESS / 2.0),
    )
    edges = scan_view_edges(front, label="strap front outline")
    vertices = tuple(
        edges.exact_vertex_at(point, label=f"strap tip corner {index}")
        for index, point in enumerate(tips)
    )
    # The vertices are selected as entities and the dimension is forced
    # horizontal, so add_edge_dimension never reads p0/p1: the 1:1 view's
    # nominal sheet points stand in, no COM projection needed (codjiflo P3).
    dimension = add_edge_dimension(
        adapter,
        front,
        p0=_front(-ROD_TIP_X, ROD_TIP_Y),
        p1=_front(ROD_TIP_X, ROD_TIP_Y),
        text_xy=(FRONT_CENTER[0], OVERALL_LINE_Y),
        label="strap overall length",
        orientation="horizontal",
        entities=vertices,
        entity_types=("VERTEX", "VERTEX"),
    )
    dimension = _early_bound(dimension, "IDisplayDimension")
    assert_dimension_measures(
        adapter,
        dimension,
        expected_mm=2.0 * ROD_TIP_X,
        label="strap overall length",
        entities=vertices,
        entity_types=("VERTEX", "VERTEX"),
    )
    annotation = _early_bound(dimension.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("strap overall length has no native annotation")
    display = set_reference_dimension(adapter, annotation, label="strap overall length")
    # Its places are the spec's (drawing-simplicity-policy.md: a pure
    # reference dimension); -1 leaves the dual and tolerance places alone.
    display = _early_bound(display, "IDisplayDimension")
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != DRAWING_REFERENCE_PRECISION[label]:
        raise RuntimeError(
            f"strap overall length prints {applied} decimal places, "
            f"not {DRAWING_REFERENCE_PRECISION[label]}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-strap source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-rocker-strap"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Strap Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker strap; 1018 flat; hub hole press fit",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # A flat plate: every edge reads on the face view; hidden lines off
    # everywhere (drawing-guidelines.md rule 9).
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
    annotations = [*front_annotations, *right_annotations]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _exterior_radius_leaders(adapter, front_annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _add_overall_length(adapter, front)
    # The template centre-marks the hub hole as the view is placed
    # (draw_mg_wheel_drum: a second AutoInsertCenterMarks2 printed a duplicate).
    add_property_linked_note(adapter, "Isometric View Note", *ISO_CAPTION_XY)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Strap Manufacturing Drawing",
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
