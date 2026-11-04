r"""Create the curated machinist drawing for MHA-DT-35, the crank handle butt cup.

A plain steel cup (user rulings 2026-09-29 and 2026-09-30, ch11 p.14/p.15 and
ch30 eight-views-4).  The end view
carries only its centre mark and the cutting plane; the longitudinal section
A-A is the cup's length view (drawing-guidelines.md rule 9 (show internal shape in solid lines)) and takes every dimension, so
the pocket and the floor hole read on cut edges rather than hidden lines (the
MHA-DT-35 machinist review).  The body diameter and the pocket depth are the
bands; the pocket is bored to suit the MHA-DT-32 head (a reference size whose
callout states the fit), and the floor hole carries its drill callout.  Every
band names its mate at the callout (MHA-DT-35 machinist ENFORCE, r1).
The local radial MAX callout also names the MHA-DT-32 head and its floor
seating function; it does not change the model's corner or clearance.
Owner ruling B on #1375 restores the pocket-wall floor in the model, so its
former shortfall note and property are not part of the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_butt_cup.py dt-crank-handle-butt-cup
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
from _drawing_layout_collect import check_drawing_layout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _telemetry
from dt_crank_handle_butt_cup_notes import (
    BODY_CHAMFER_CALLOUT,
    BODY_FIT_CALLOUT,
    FLOOR_HOLE_CALLOUT,
    POCKET_DEPTH_CALLOUT,
    POCKET_FIT_CALLOUT,
    POCKET_FLOOR_RADIUS_CALLOUT,
)
from dt_crank_handle_butt_cup_spec import (
    BODY_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OVERALL_LENGTH,
    POCKET_DEPTH,
    POCKET_FLOOR_CORNER_R_BAND,
    POCKET_FLOOR_CORNER_R_MAX,
    POCKET_FLOOR_CORNER_R_TOL_TYPE,
    REFERENCE_DIMENSIONS,
)
from _fit_deviations import deviations


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_handle_butt_cup"]
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

# Ø9.6 x 8.1 at 5:1 reads 48 x 41 on the sheet.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
ISO_SCALE = (4, 1)
# Third angle: the end view left of the section looks at the chamfered
# floor face (*Left), not the counterbore mouth on the opposite end.
END_CENTER = (0.074, 0.165)
# 10 mm right of the r1 sheet: the body-fit callout needs the room between the
# floor-hole dimension and the section.
SECTION_CENTER = (0.225, 0.165)
ISO_CENTER = (0.368, 0.215)
# Below the floor end, clear of the floor-hole callout.
CAPTION_XY = (0.160, 0.114)
ISO_NOTE_POS = (0.335, 0.170)

_S = VIEW_SCALE[0] / 1000.0
BODY_R = BODY_DIA * _S / 2.0  # 0.024
HALF_LENGTH = OVERALL_LENGTH * _S / 2.0  # 0.02025
# The section lays the part's +X to the right (the draw_crank_pinion
# convention), so the face is the right edge and the floor the left.
FACE_X = SECTION_CENTER[0] + HALF_LENGTH

# The pocket opens right; the smaller floor-hole dimension nests closest to
# the floor end, with the body diameter outboard.  Keep the overall below
# the section and the pocket-depth row: its upper witnesses otherwise strike
# the three-row functional radius callout.  The radius owns the open upper
# corridor, above the independent outer-chamfer block, with its native leader
# still pointing to the real quarter arc.  No model dimension or fit changes.
#
# Retained sheet-mm solve from the 22821a1d2 native r2 findings (2026-10-19):
# - PocketDepth's upper row [268.8,140.2]..[286.9,143.8] met PocketDia's
#   outside-arrow tail x284.2, y142.9..149.2.  Lower the whole depth block
#   3.5: its top is y140.3, 2.6 below the tail, including its far endpoint.
# - The 031202 native floor-hole keep (136.75,141) put DRILL THRU on a
#   shoulder at keep_y-5.583, with its main glyph top at keep_y+3.5267.
#   Keep the same below-witness/hung-text regime (keep_y <154.5), but nest
#   its column at x201.75, 3 left of the floor, instead of crossing BodyDia's
#   x166.75 column.  For 2 mm air above BodyDia's y144.5 lower witness and
#   3.57 mm below its r2 y160.4 text-break boundary, the keep-Y range is
#   152.083..153.3033; choose 152.5.  The shoulder is then y146.917 and the
#   main glyph top y156.0267, 4.3733 below BodyDia's lower row.  DRILL THRU's
#   full 24.0285 mm row hangs LEFT of keep X, so all text ends at x201.75,
#   3 mm from the actual floor silhouette x204.75, not on the section.
# Rounded r2 coordinates have 0.05 mm uncertainty; offline contracts retain it.
SECTION_KEEP = {
    "PocketDia": (FACE_X + 0.039, SECTION_CENTER[1] + 0.001),
    "BodyDia": (SECTION_CENTER[0] - HALF_LENGTH - 0.038, SECTION_CENTER[1] + 0.001),
    # Smaller diameter closest to the floor; the complete two-row hung block
    # fits above the body witness without moving into the hole's witness span.
    "FloorHoleDia": (
        SECTION_CENTER[0] - HALF_LENGTH - 0.003,
        SECTION_CENTER[1] - 0.0125,
    ),
    "OverallLength": (SECTION_CENTER[0], SECTION_CENTER[1] - BODY_R - 0.035),
    "PocketDepth": (FACE_X + 0.033, SECTION_CENTER[1] - BODY_R - 0.0115),
    "BodyChamfer": (
        SECTION_CENTER[0] - HALF_LENGTH - 0.0295,
        SECTION_CENTER[1] + BODY_R + 0.0161,
    ),
    "PocketFloorRadius": (
        FACE_X - POCKET_DEPTH * _S,
        SECTION_CENTER[1] + BODY_R + 0.041,
    ),
}
DIMENSION_CALLOUTS = {
    "BodyChamfer": BODY_CHAMFER_CALLOUT,
    "BodyDia": BODY_FIT_CALLOUT,
    "FloorHoleDia": FLOOR_HOLE_CALLOUT,
    "PocketDepth": POCKET_DEPTH_CALLOUT,
    "PocketDia": POCKET_FIT_CALLOUT,
    "PocketFloorRadius": POCKET_FLOOR_RADIUS_CALLOUT,
}
# *Left reverses *Right's horizontal basis.  Reverse the cut as well to
# retain the section's physical viewing direction and +X-right orientation.
CUT_START = (END_CENTER[0], END_CENTER[1] + BODY_R + 0.006)
CUT_END = (END_CENTER[0], END_CENTER[1] - BODY_R - 0.006)


def _dress_pocket_floor_radius(annotation: Any) -> None:
    """Keep the imported model radius controlling, MAX, and on its real arc."""
    label = "MHA-DT-35 PocketFloorRadius"
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric) or int(display.Type2) != 5:  # swRadialDimension
        raise RuntimeError(f"{label}: imported as a non-radial dimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    lower, upper = deviations(POCKET_FLOOR_CORNER_R_BAND)
    if (
        not math.isclose(
            float(dimension.SystemValue),
            POCKET_FLOOR_CORNER_R_MAX / 1000.0,
            abs_tol=1e-9,
        )
        or int(tolerance.Type) != POCKET_FLOOR_CORNER_R_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: imported radius lost its model MAX limit")
    if (
        bool(dimension.IsReference())
        or bool(display.ShowParenthesis)
        or any(
            "(" in str(display.GetText(index) or "")
            or ")" in str(display.GetText(index) or "")
            for index in (1, 2)
        )
    ):
        raise RuntimeError(f"{label}: imported as a reference")
    display.ArcExtensionLineOrOppositeSide = False
    display.ArrowSide = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
    display.SolidLeader = False
    if (
        bool(display.ArcExtensionLineOrOppositeSide)
        or int(display.ArrowSide) != 1
        or bool(display.SolidLeader)
    ):
        raise RuntimeError(f"{label}: radial leader style did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-butt-cup source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Handle Butt Cup Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle butt cup; turned plain steel cup",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    end = place_view(adapter, str(SOURCE), "*Left", *END_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        end,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="butt cup longitudinal section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="butt cup")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, section, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    by_name = {dimension_name(adapter, a): a for a in annotations}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, by_name[name], label=f"MHA-DT-35 {name}", diameter=True
        )
    _dress_pocket_floor_radius(by_name["PocketFloorRadius"])
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the cup end view")
    create_section_axis_centerline(
        adapter, section, length_mm=OVERALL_LENGTH, label="butt cup axis"
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)
    rebuild_drawing(adapter, label="crank-handle-butt-cup layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Butt Cup Manufacturing Drawing",
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
