r"""Create the machinist drawing for MHA-DT-38, the cone tip bushing.

A turned brass ring (owner decision C1 keyed, 2026-11-09): OD and length at
the title block's .XXX, the bore reamed for the press on the MHA-DT-37 pivot.
The MHA-DT-34 ferrule's layout: the end view carries only its centre mark and
the cutting plane; the longitudinal section A-A is the ring's length view
(drawing-guidelines.md rule 9) and takes every dimension, so the bore reads on
cut edges.  The bore's callout names the fit, the mate and the interference
REF (rule 4).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_tip_bushing.py dt-cone-tip-bushing
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

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
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
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
from dt_cone_tip_bushing_spec import (
    BORE_CALLOUT,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ISOMETRIC_VIEW_SCALE,
    LENGTH,
    LENGTH_CALLOUT,
    OUTER_DIA,
    OUTER_DIA_CALLOUT,
    UNIT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_tip_bushing"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

# Ø5.8 x 4.1 at 5:1 reads 29 x 20 on the sheet.  Machinist review of farm run
# 20261110T001845485Z: on the 8:1 sheet the section caption printed a
# "SCALE 8 : 1" equal to the sheet's; 5:1 sections on 5:1 sheets print none
# (MHA-DT-35).  The isometric stays 8:1, so its label states a real scale.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
if tuple(ISOMETRIC_VIEW_SCALE) == VIEW_SCALE:
    raise AssertionError("MHA-DT-38 isometric label would repeat the sheet scale")
END_CENTER = (0.070, 0.165)
SECTION_CENTER = (0.200, 0.165)
ISO_CENTER = (0.355, 0.205)
CAPTION_XY = (0.185, 0.118)
ISO_NOTE_POS = (0.335, 0.160)

_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # model mm -> sheet m
OUTER_R = OUTER_DIA * _S / 2.0
BORE_R = BORE_DIA * _S / 2.0
HALF_LENGTH = LENGTH * _S / 2.0
# A-A's arrows point right, so the section looks along model -Z: local +X runs
# right and the north face (x = LENGTH) is the section's right edge.
NORTH_FACE_X = SECTION_CENTER[0] + HALF_LENGTH

# Measured on the farm sheet (layout audit, run 20261110T001845485Z): a block
# placed inside its extension lines centres on the keep point; one placed
# outside them hangs on a shelf that starts at the keep x, and its rows run
# about 30 mm down from the value (three callout rows, 3.5 mm text).
_ROW = 0.0056
_BORE_BLOCK_BELOW_KEEP = 0.0038 - 3.0 * _ROW  # last row's baseline
# The OD's two-row block (value, wall) sits between its extension lines left
# of the section.  The length's stack rows go ABOVE its value, beyond the
# ends of its extension lines.  The bore's block stands above and right of
# the north face, wholly above its upper extension line (the bore edge at
# 5:1 leaves 7.8 mm between them, under the block's ~25 mm), clear of the
# length's rows and short of the isometric.
SECTION_KEEP = {
    "OuterDia": (SECTION_CENTER[0] - HALF_LENGTH - 0.030, SECTION_CENTER[1]),
    "BoreDia": (
        NORTH_FACE_X + 0.015,
        SECTION_CENTER[1] + BORE_R + 0.004 - _BORE_BLOCK_BELOW_KEEP,
    ),
    "Length": (SECTION_CENTER[0], SECTION_CENTER[1] + OUTER_R + 0.016),
}
CALLOUTS_BELOW = {"BoreDia": BORE_CALLOUT, "OuterDia": OUTER_DIA_CALLOUT}
CALLOUTS_ABOVE = {"Length": LENGTH_CALLOUT}
CUT_START = (END_CENTER[0], END_CENTER[1] - OUTER_R - 0.006)
CUT_END = (END_CENTER[0], END_CENTER[1] + OUTER_R + 0.006)
if BORE_DIA >= OUTER_DIA:
    raise AssertionError("MHA-DT-38 bore is not inside its OD")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-bushing source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Tip Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip bushing; turned brass ring",
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
        label="bushing longitudinal section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="bushing")
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISOMETRIC_VIEW_SCALE
    )
    for view in (end, section, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places and the bore's band are authored on the part; the sheet only
    # proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW, location="below")
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    rebuild_drawing(adapter, label="MHA-DT-38 dimensions")
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the bushing end view")
    create_section_axis_centerline(
        adapter, section, length_mm=LENGTH, label="bushing axis"
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)
    rebuild_drawing(adapter, label="cone-tip-bushing layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Bushing Manufacturing Drawing",
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
