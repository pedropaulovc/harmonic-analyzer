r"""Create the curated machinist drawing for MHA-DT-34, the crank handle ferrule.

A plain brass ring (user ruling 2026-09-29, ch11 p.14/p.15): OD, bore and
length, both bore mouths at the title block's edge break (owner ruling
2026-10-24, #1900, supersedes ruling A's seat-mouth chamfer).  The end view
carries only its centre mark and the cutting plane; the longitudinal section
A-A is the ring's length view (drawing-guidelines.md rule 9 (show internal
shape in solid lines)) and takes every dimension, so the bore reads on cut
edges rather than hidden lines (the MHA-DT-34 machinist review).  Every size
but the bore is routine (.X): the oak tenon is turned to suit this bore.
Note 1, flagged from the OD, carries the OD's skim with MHA-DT-08 and the
walls it leaves; the bore's matched fit is its own callout (rule 7: a callout
is short, a longer requirement is a numbered flag note).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_ferrule.py dt-crank-handle-ferrule
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
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
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _printed_limits import limits
from _supplier_dimensions import supplier_reference_dimension
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _telemetry
from dt_crank_handle_ferrule_notes import (
    BORE_FIT_CALLOUT,
    HANDLE_NUMBER,
    OUTER_DIA_CALLOUT,
    SHEET_NOTES,
)
from dt_crank_handle_ferrule_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OUTER_DIA,
    STOCK_DIA_MIN,
    STOCK_FRACTION_DENOMINATOR,
    TENON_GLUE_LINE,
    UNIT,
    WALL_WORST,
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
# chamfer's dimension line, keeps clear of it; 10 more for the bore's
# matched-fit route row.
ISO_NOTE_POS = (0.355, 0.160)
# Note 1 stands under the views, left of the title block.
NOTES_XY = (0.030, 0.085)

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

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (build_dt_crank_handle_ferrule: one revolve about model +X; the arm-bearing
# face at x = 0, the datum end the length runs from; the seat face at x =
# LENGTH). The O.D. is the 9/16 rod as supplied (a REF, skimmed at
# MHA-DT-08, note 1); the hole is drilled at the title block's .XXX row, no
# drill named against .303 (fit audit question 15), and names its bonded
# tenon; the length the .XX row. Each ``span`` is a diameter's model-X
# extent. The declarations
# print nothing.
_P = DRAWING_PRECISION_BY_NAME
_NOTES = "dt_crank_handle_ferrule_notes"
_SELF = "draw_dt_crank_handle_ferrule"
part_metadata(
    model_sources=("LENGTH", "OUTER_DIA", "BORE_DIA"),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "x", "value": 0.0}, ("LENGTH",)),
        "outward": ([-1.0, 0.0, 0.0], ("LENGTH",)),
    },
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), LENGTH),),
    requirements=("length",),
    fields={
        "plane": ({"frame": "model", "axis": "x", "value": LENGTH}, ("LENGTH",)),
        "outward": ([1.0, 0.0, 0.0], ("LENGTH",)),
        "length": (
            limits(LENGTH, _P["Length"], unit=UNIT),
            ("LENGTH", "UNIT", (_SELF, "SECTION_KEEP")),
        ),
        "length_nominal": (LENGTH, ("LENGTH",)),
        "length_from": ("datum_end", ((_SELF, "SECTION_KEEP"),)),
    },
    precision={"length": _P["Length"]},
)
requirement(
    "outer",
    kind="diameter",
    faces=(CylinderFace(OUTER_DIA),),
    requirements=("stock",),
    fields={
        "axis": ([1.0, 0.0, 0.0], ("OUTER_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("OUTER_DIA",)),
        "span": ([0.0, LENGTH], ("LENGTH",)),
        "dia_ref": (
            OUTER_DIA,
            ("OUTER_DIA", "REFERENCE_DIMENSIONS", "STOCK_FRACTION_DENOMINATOR"),
        ),
        "stock_dia_min": (STOCK_DIA_MIN, ("STOCK_DIA_MIN",)),
        "stock": (OUTER_DIA_CALLOUT, ((_NOTES, "OUTER_DIA_CALLOUT"),)),
        "callout": (OUTER_DIA_CALLOUT, ((_NOTES, "OUTER_DIA_CALLOUT"),)),
    },
    precision={"dia_ref": _P["OuterDia"]},
)
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(BORE_DIA),),
    requirements=("dia", "thru"),
    fields={
        "axis": ([1.0, 0.0, 0.0], ("BORE_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("BORE_DIA",)),
        "span": ([0.0, LENGTH], ("LENGTH",)),
        "dia": (
            limits(BORE_DIA, _P["BoreDia"], unit=UNIT),
            ("BORE_DIA", "BORE_DIA_TOL", "UNIT", (_SELF, "SECTION_KEEP")),
        ),
        "nominal_dia": (BORE_DIA, ("BORE_DIA",)),
        "thru": (True, ((_NOTES, "BORE_FIT_CALLOUT"),)),
        "process": ("drill", ((_NOTES, "BORE_FIT_CALLOUT"),)),
        "diametral_clearance_ref": (
            list(TENON_GLUE_LINE),
            ("TENON_GLUE_LINE", (_NOTES, "BORE_FIT_CALLOUT")),
        ),
        "mate": (
            f"{HANDLE_NUMBER} TENON",
            ((_NOTES, "HANDLE_NUMBER"), (_NOTES, "BORE_FIT_CALLOUT")),
        ),
        "wall_min": (WALL_WORST, ("WALL_WORST",)),
        "callout": (BORE_FIT_CALLOUT, ((_NOTES, "BORE_FIT_CALLOUT"),)),
    },
    precision={"dia": _P["BoreDia"]},
)


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-ferrule source", adapter.open_model(str(SOURCE)))
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

    if add_note(adapter, SHEET_NOTES, *NOTES_XY) is None:
        raise RuntimeError("failed to add the ferrule's numbered sheet note")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)
    return finalize_drawing(
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
