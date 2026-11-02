r"""Create the curated machinist drawing for MHA-DT-34, the crank handle ferrule.

A plain brass ring (user ruling 2026-09-29, ch11 p.14/p.15): OD, bore and
length, both bore mouths at the title block's edge break (owner ruling
2026-10-24, #1900, supersedes ruling A's seat-mouth chamfer).  The end view
carries only its centre mark and the cutting plane; the longitudinal section
A-A is the ring's length view (drawing-guidelines.md rule 9 (show internal
shape in solid lines)) and takes every dimension, so the bore reads on cut
edges rather than hidden lines (the MHA-DT-34 machinist review).  Every size
but the bore is routine (.X): the oak tenon is turned to suit this bore.
There is no general note (MHA-DT-34 machinist ENFORCE, r1-r3): the bore's
matched fit and the OD's skim with MHA-DT-08, with the wall it leaves, are
callouts on their own dimensions (rule 7: flag it where it applies).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_ferrule.py dt-crank-handle-ferrule
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
)
from _drawing_layout_collect import check_drawing_layout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _supplier_dimensions import supplier_reference_dimension
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _telemetry
from dt_crank_handle_ferrule_notes import (
    BORE_FIT_CALLOUT,
    OUTER_DIA_CALLOUT,
)
from dt_crank_handle_ferrule_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OUTER_DIA,
    STOCK_FRACTION_DENOMINATOR,
    UNIT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_handle_ferrule"]
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

# Ø15 x 7 at 4:1 reads 60 x 28 on the sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = (2, 1)
# 20 left of iteration 1, so the OD's seven-row block (both stated walls)
# clears the end view's centre-mark tails (~10 past its edge).
END_CENTER = (0.065, 0.165)
SECTION_CENTER = (0.215, 0.165)
ISO_CENTER = (0.365, 0.205)
CAPTION_XY = (0.195, 0.113)
# Moved 10 right of iteration 1 so the bore's block, set right of the
# chamfer's dimension line, keeps clear of it.
ISO_NOTE_POS = (0.345, 0.160)

OUTER_R = OUTER_DIA * VIEW_SCALE[0] / 2000.0  # 0.030
HALF_LENGTH = LENGTH * VIEW_SCALE[0] / 2000.0  # 0.014
# A-A's arrows point right, so the section looks along model -Z: local +X
# runs right and the seat face (x=LENGTH) is the section's right edge.
SEAT_FACE_X = SECTION_CENTER[0] + HALF_LENGTH  # 0.229
BORE_TOP_Y = SECTION_CENTER[1] + BORE_DIA * VIEW_SCALE[0] / 2000.0  # 0.1804

# The OD stands left of the section and the bore right of it; the length
# above.  The cutting line runs vertically through the end view's centre.
# Each block is its value plus callout rows at 5.55 pitch, ~2.75 per
# character, centred on its keep point.
SECTION_KEEP = {
    # "(Ø14.29)" over seven rows, the widest 27 chars: 74.3 x 38.9, so x
    # 0.1209-0.1951 and y 0.1456-0.1844.  It clears the section's left edge
    # (x 0.201) by 5.9, the OD's extension lines (y 0.136, 0.194) by 9, and
    # the end view's centre-mark tail (~x 0.104) by 17.
    "OuterDia": (0.158, SECTION_CENTER[1]),
    # "Ø7.70 ±0.1" over three rows, the widest 25 chars: 68.8 x 22.2, so x
    # 0.2626-0.3314 and y 0.1539-0.1761, between the bore's extension lines
    # (y 0.1496, 0.1804); the isometric note (x 0.345) stands 13.6 clear.
    "BoreDia": (SEAT_FACE_X + 0.068, SECTION_CENTER[1]),
    "Length": (SECTION_CENTER[0], SECTION_CENTER[1] + OUTER_R + 0.012),
}
CUT_START = (END_CENTER[0], END_CENTER[1] - OUTER_R - 0.006)
CUT_END = (END_CENTER[0], END_CENTER[1] + OUTER_R + 0.006)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-ferrule source", await adapter.open_model(str(SOURCE)))
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
        unit=UNIT,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Handle Ferrule Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle ferrule; turned brass ring",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # The ring revolves about local +X: *Right is the end view, and a vertical
    # cut through it is the longitudinal section on the profile's Front plane.
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        end,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="ferrule longitudinal section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="ferrule")
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
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The band carries its mate and reason at the callout.
    set_dimension_callouts(
        adapter, annotations, {"BoreDia": BORE_FIT_CALLOUT}, location="below"
    )
    # The OD is the 9/16-in rod as supplied, skimmed at assembly: a reference
    # printed as the rod's fraction, its skim and walls on the callout.
    by_name = {dimension_name(adapter, a): a for a in annotations}
    supplier_reference_dimension(
        adapter,
        _early_bound(by_name["OuterDia"], "IAnnotation").GetSpecificAnnotation(),
        label="MHA-DT-34 OuterDia",
        units="in",
        precision=DRAWING_PRECISION_BY_NAME["OuterDia"],
        expected_mm=OUTER_DIA,
        presentation="diameter",
        fraction_denominator=STOCK_FRACTION_DENOMINATOR,
        callout=OUTER_DIA_CALLOUT,
    )
    rebuild_drawing(adapter, label="MHA-DT-34 stock reference")
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the ferrule end view")
    create_section_axis_centerline(
        adapter, section, length_mm=LENGTH, label="ferrule axis"
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)
    rebuild_drawing(adapter, label="crank-handle-ferrule layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Ferrule Manufacturing Drawing",
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
