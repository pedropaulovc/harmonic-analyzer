r"""Create the machinist drawing for MHA-DT-39, the cone tip end screw.

A stock McMaster 91794A558 slotted fillister screw with one shop operation:
the pivot hole reamed concentric in its threaded end (owner decision C1
keyed, 2026-11-09).  The MHA-DT-34 ferrule's layout: the end view, looking at
the threaded end, carries the hole's centre mark, the cutting plane and the
hole's native callout on its rim (size and band, REAM, depth from the cut;
drawing-guidelines.md rules 12 and 26), with the fit and its mate and the wall
to the thread root below it (rules 4, 7, 20); the longitudinal section A-A
shows the hole on cut edges (rule 9).  Note 1 names the stock; everything
else is the supplier's (reference).

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
from _drawing_blind_ream_callout import add_blind_ream_callout
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_layout_collect import check_drawing_layout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _fit_deviations import deviations
from _gear_drawing_entities import visible_circle_edge
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _telemetry
from dt_cone_tip_end_screw_spec import (
    END_HOLE_BAND,
    END_HOLE_CALLOUT_BELOW,
    END_HOLE_DEPTH,
    END_HOLE_DEPTH_TEXT,
    END_HOLE_DIA,
    END_HOLE_PROCESS,
    HEAD_RADIUS,
    ISOMETRIC_VIEW_SCALE,
    OVERALL_LENGTH,
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
# The end view stands far enough right that the hole's callout fits on its
# left, at mid height (below).
END_CENTER = (0.110, 0.165)
SECTION_CENTER = (0.215, 0.165)
ISO_CENTER = (0.365, 0.215)
CAPTION_XY = (0.200, 0.110)
# The isometric's label directly under the pictorial (machinist review of farm
# run 20261110T001845485Z: the hole callout had pushed between them).
ISO_NOTE_POS = (0.340, 0.176)
NOTES_XY = (0.030, 0.085)

_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # model mm -> sheet m
HEAD_R = HEAD_RADIUS * _S
# The section lays the axis horizontal, centred on the screw's length: as for
# the ferrule's A-A (its arrows point right), the end toward the end view's
# viewer, the threaded end, is the section's right edge.
TIP_X = SECTION_CENTER[0] + (OVERALL_LENGTH / 2.0) * _S
HOLE_FLOOR_X = TIP_X - END_HOLE_DEPTH * _S
if not SECTION_CENTER[0] < HOLE_FLOOR_X < TIP_X:
    raise AssertionError("MHA-DT-39 hole lies outside its section's right half")

# The hole's callout (PR 2 r7 machinist review, clarity: the depth belongs in
# the callout, rule 26) stands left of the end view at mid height, its leader
# running right to the rim's upper left: the cutting line's arrows and
# letters stand above and below the view, right of the line, so the leader
# crosses neither, and it lands above the hole's horizontal centre mark.
# Its text centres on CALLOUT_XY (_drawing_blind_ream_callout).  The size
# row is the widest, ~61 mm (the shaft socket's twin "Ø.0625 +.0005/.0000
# REAM ↧ .20", PR 2 r5: 33.9 mm size plus 27.2 mm process and depth); the
# word rows run ~2.48 mm a character (r7's 30-character fit row, 74.4 mm),
# so 24 characters stay under it.  The block spans about 0.0165..0.0775, 4 mm
# inside the frame (0.0124) and 11 mm short of the head's outline
# (END_CENTER - HEAD_R, 0.089).  The section carries no dimension: both the
# hole's are the callout's.
CALLOUT_XY = (0.047, 0.172)
CALLOUT_HALF_WIDTH = 0.0305
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

    _add_hole_callout(adapter, end)
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


def _add_hole_callout(adapter: Any, end: Any) -> Any:
    """The reamed hole's native callout on its rim in the end view
    (_drawing_blind_ream_callout): the cut's diameter, band and depth stay
    SolidWorks' own; REAM joins before the depth and the fit and wall rows go
    below."""
    return add_blind_ream_callout(
        adapter,
        end,
        edge=visible_circle_edge(adapter, end, END_HOLE_DIA),
        callout_xy=CALLOUT_XY,
        label="end screw pivot hole",
        dia_mm=END_HOLE_DIA,
        deviations_mm=deviations(END_HOLE_BAND),
        depth_text=END_HOLE_DEPTH_TEXT,
        process=END_HOLE_PROCESS,
        below=END_HOLE_CALLOUT_BELOW,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
