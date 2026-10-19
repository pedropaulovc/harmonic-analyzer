r"""Create the curated machinist drawing for MHA-DT-035, the crank handle butt cup.

A plain steel cup (user rulings 2026-09-29 and 2026-09-30, ch11 p.14/p.15 and
ch30 eight-views-4).  The end view
carries only its centre mark and the cutting plane; the longitudinal section
A-A is the cup's length view (drawing-guidelines.md rule 9 (show internal shape in solid lines)) and takes every dimension, so
the pocket and the floor hole read on cut edges rather than hidden lines (the
MHA-DT-035 machinist review).  The body diameter and the pocket depth are the
bands; the pocket is bored to suit the MHA-DT-032 head (a reference size whose
callout states the fit), and the floor hole carries its drill callout.  Every
band names its mate at the callout (MHA-DT-035 machinist ENFORCE, r1).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_butt_cup.py dt-crank-handle-butt-cup
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
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
)
from dt_crank_handle_butt_cup_spec import (
    BODY_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OVERALL_LENGTH,
    REFERENCE_DIMENSIONS,
)


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

# Ø8.2 x 8.1 at 5:1 reads 41 x 41 on the sheet.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
ISO_SCALE = (4, 1)
END_CENTER = (0.074, 0.165)
# 10 mm right of the r1 sheet: the body-fit callout needs the room between the
# floor-hole dimension and the section.
SECTION_CENTER = (0.225, 0.165)
ISO_CENTER = (0.368, 0.215)
# Below the floor end, clear of the floor-hole callout and the notes.
CAPTION_XY = (0.160, 0.114)
MANUFACTURING_NOTES_POS = (0.022, 0.085)
ISO_NOTE_POS = (0.335, 0.170)

_S = VIEW_SCALE[0] / 1000.0
BODY_R = BODY_DIA * _S / 2.0  # 0.0205
HALF_LENGTH = OVERALL_LENGTH * _S / 2.0  # 0.02025
# The section lays the part's +X to the right (the draw_crank_pinion
# convention), so the face is the right edge and the floor the left.
FACE_X = SECTION_CENTER[0] + HALF_LENGTH

# The pocket, which opens at the face, stands right of the section; the body
# and the floor hole left of it; the axial sizes stack above (the overall) and
# below (the pocket depth), both from the face.
#
# Offline layout math (r1 layout audit: 3.5 mm text, a 5.55 mm line pitch,
# ~2.75 mm a character; a multi-line block centres on its keep point, and a
# horizontal dimension's line runs under its LAST line):
# - PocketDia, five lines ~69 mm wide, centres between its extension lines
#   (31.5 mm apart) with ~2.9 mm each side, 4 mm right of the face.
# - BodyDia, two lines ~63 mm wide, sits between the floor-hole extension
#   lines (21 mm apart) with ~6 mm each side, ~6.7 mm left of the floor end.
# - PocketDepth, four lines ~58 mm wide, cannot fit between its extension
#   lines (27.5 mm), so it stands outside them right of the face, its top
#   ~3.6 mm under the pocket-diameter extension line.
# - BodyChamfer (the profile sketch is the section's upper half, so the
#   chamfer is the floor end's top corner, 2 mm on paper), four lines ~50 mm
#   wide, stands outside its extension lines left of the floor end: line at
#   y ~0.1905 (part top 0.1855, overall's line 0.1947 right of x 0.2047),
#   block x ~0.150-0.200 and y ~0.190-0.211, 15 mm over the floor-hole
#   extension line (0.1755) and 4 mm left of the floor end.
SECTION_KEEP = {
    "PocketDia": (FACE_X + 0.039, SECTION_CENTER[1] + 0.001),
    "BodyDia": (SECTION_CENTER[0] - HALF_LENGTH - 0.038, SECTION_CENTER[1] + 0.001),
    # The DRILL THRU block stands left of the body callout and below the
    # hole's lower extension line, clear of its arrows (MHA-DT-035 re-reviews).
    "FloorHoleDia": (
        SECTION_CENTER[0] - HALF_LENGTH - 0.076,
        SECTION_CENTER[1] - 0.024,
    ),
    "OverallLength": (SECTION_CENTER[0], SECTION_CENTER[1] + BODY_R + 0.012),
    "PocketDepth": (FACE_X + 0.033, SECTION_CENTER[1] - BODY_R - 0.008),
    "BodyChamfer": (
        SECTION_CENTER[0] - HALF_LENGTH - 0.0295,
        SECTION_CENTER[1] + BODY_R + 0.0161,
    ),
}
DIMENSION_CALLOUTS = {
    "BodyChamfer": BODY_CHAMFER_CALLOUT,
    "BodyDia": BODY_FIT_CALLOUT,
    "FloorHoleDia": FLOOR_HOLE_CALLOUT,
    "PocketDepth": POCKET_DEPTH_CALLOUT,
    "PocketDia": POCKET_FIT_CALLOUT,
}
CUT_START = (END_CENTER[0], END_CENTER[1] - BODY_R - 0.006)
CUT_END = (END_CENTER[0], END_CENTER[1] + BODY_R + 0.006)


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
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
            adapter, by_name[name], label=f"MHA-DT-035 {name}", diameter=True
        )
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the cup end view")
    create_section_axis_centerline(
        adapter, section, length_mm=OVERALL_LENGTH, label="butt cup axis"
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS)
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
