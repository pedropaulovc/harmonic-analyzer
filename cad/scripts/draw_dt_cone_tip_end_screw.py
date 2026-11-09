r"""Create the machinist drawing for MHA-DT-39, the cone tip end screw.

A stock McMaster 91794A558 slotted fillister screw with one shop operation:
the pivot hole reamed concentric in its threaded end (owner decision C1
keyed, 2026-11-09).  The MHA-DT-34 ferrule's layout: the end view, looking at
the threaded end, carries the hole's centre mark and the cutting plane; the
longitudinal section A-A shows the hole on cut edges (drawing-guidelines.md
rule 9) and takes its two model dimensions: the reamed diameter, whose
callout names the process, the fit, the mate and the wall to the thread root
(rules 4, 12, 20), and the full-diameter depth.  Note 1 names the stock;
everything else is the supplier's (reference).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_tip_end_screw.py dt-cone-tip-end-screw
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
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
from dt_cone_tip_end_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    END_HOLE_CALLOUT,
    END_HOLE_DEPTH,
    END_HOLE_DEPTH_CALLOUT,
    HEAD_RADIUS,
    ISOMETRIC_VIEW_SCALE,
    OVERALL_LENGTH,
    SHANK_DIA,
    STOCK_NOTE,
    UNIT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_tip_end_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

# 21.9 long over a Ø10.5 head at 4:1 reads 88 x 42 on the sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
END_CENTER = (0.075, 0.165)
SECTION_CENTER = (0.215, 0.165)
ISO_CENTER = (0.365, 0.215)
CAPTION_XY = (0.200, 0.110)
ISO_NOTE_POS = (0.335, 0.160)
NOTES_XY = (0.030, 0.085)

_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # model mm -> sheet m
HEAD_R = HEAD_RADIUS * _S
THREAD_R = SHANK_DIA / 2.0 * _S
# The section lays the axis horizontal, centred on the screw's length: as for
# the ferrule's A-A (its arrows point right), the end toward the end view's
# viewer, the threaded end, is the section's right edge.
TIP_X = SECTION_CENTER[0] + (OVERALL_LENGTH / 2.0) * _S
HOLE_FLOOR_X = TIP_X - END_HOLE_DEPTH * _S
if not SECTION_CENTER[0] < HOLE_FLOOR_X < TIP_X:
    raise AssertionError("MHA-DT-39 hole lies outside its section's right half")

# The reamed diameter's four-row block stands right of the threaded end,
# above the axis; the depth under the thread, between its extension lines.
SECTION_KEEP = {
    "EndHoleDia": (TIP_X + 0.060, SECTION_CENTER[1] + 0.018),
    "EndHoleDepth": (
        (TIP_X + HOLE_FLOOR_X) / 2.0,
        SECTION_CENTER[1] - THREAD_R - 0.012,
    ),
}
DIMENSION_CALLOUTS = {
    "EndHoleDia": END_HOLE_CALLOUT,
    "EndHoleDepth": END_HOLE_DEPTH_CALLOUT,
}
# The end view looks at the threaded end along model +Y: its vertical runs
# along model Z, so a vertical cut through the centre is the Right plane.
CUT_START = (END_CENTER[0], END_CENTER[1] - HEAD_R - 0.006)
CUT_END = (END_CENTER[0], END_CENTER[1] + HEAD_R + 0.006)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-end-screw source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Tip End Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip end screw; McMaster 91794A558 with a reamed pivot hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        end,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="end screw longitudinal section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="end screw")
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
    # Places and the reamed band are authored on the part; the sheet only
    # proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="below")
    rebuild_drawing(adapter, label="MHA-DT-39 dimensions")
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the end screw end view")
    create_section_axis_centerline(
        adapter, section, length_mm=OVERALL_LENGTH, label="end screw axis"
    )

    if add_note(adapter, STOCK_NOTE, *NOTES_XY) is None:
        raise RuntimeError("failed to add the end screw's stock note")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)
    rebuild_drawing(adapter, label="cone-tip-end-screw layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip End Screw Manufacturing Drawing",
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
