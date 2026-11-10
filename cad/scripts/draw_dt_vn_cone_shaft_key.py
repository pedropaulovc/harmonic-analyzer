r"""Create the curated manufacturing drawing for MHA-DT-VN-71.

The key is McMaster-Carr 98830A511 key stock cut to length (owner decision C1
keyed, 2026-11-09, PR #1992).  Its section prints as the supplier's fraction
reference on the end view, its cut length at the title block's .XX on the
side view; the cut ends take the title block's edge break.  MHA-DT-00 seats
the key; the keyseat and keyways are their own parts' callouts.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

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
from _drawing_dimensions import assert_imported_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _supplier_dimensions import supplier_reference_dimension
import _telemetry
from dt_vn_cone_shaft_key_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    SIZE,
    STOCK_FRACTION_DENOMINATOR,
    STOCK_FRACTION_DIMENSIONS,
)


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_vn_cone_shaft_key"]
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

# Every view at the sheet's 2:1: the side view's 4.52 key spans 230 mm of the
# B sheet's field, the end view sits left of it in line, the isometric under
# it, clear of the title block (x >= 216 mm, y <= 66 mm).
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
FRONT_CENTER = (0.040, 0.200)
RIGHT_CENTER = (0.200, 0.200)
ISO_CENTER = (0.200, 0.125)
HALF_SIZE = SIZE * VIEW_SCALE[0] / 2000.0
HALF_LENGTH = LENGTH * VIEW_SCALE[0] / 2000.0
# The end view's height (model X, horizontal) above it, its width (model Y,
# vertical) right of it; the side view's length under it.  The square's 3.2 mm
# at 2:1 is shorter than the stacked (1/16") is tall, so the width's text
# stands BELOW the square, outside its extension lines, and its dimension
# line stops at the value: centred between them, both extension lines and
# the dimension line struck the fraction (machinist review of PR #2331 head
# 7f1dedc, r1-r3; draw_dt_pinion_lift_rod's PinHoleZ precedent).  Its line
# stands RIGHT of the square, toward the side view's 44 mm of open field:
# left of it, the value's ~12 mm shelf ran out through the inner border
# (rule 13; review of 5994f29, r1-r3, render at x 11.3-24.0 mm).
WIDTH_TEXT_DROP = 0.012
WIDTH_LINE_OFFSET = 0.014
FRONT_KEEP = {
    "KeyHeight": (FRONT_CENTER[0], FRONT_CENTER[1] + HALF_SIZE + 0.012),
    "KeyWidth": (
        FRONT_CENTER[0] + HALF_SIZE + WIDTH_LINE_OFFSET,
        FRONT_CENTER[1] - HALF_SIZE - WIDTH_TEXT_DROP,
    ),
}
RIGHT_KEEP = {
    "CutLength": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_SIZE - 0.012),
}
NOTES_XY = (0.016, 0.165)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-shaft-key source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
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
            0: "Cone Shaft Key Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear shaft key; square key stock; cut to length; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    section = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    length = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*section, *length]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name, value_mm in STOCK_FRACTION_DIMENSIONS.items():
        matches = [a for a in section if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one MHA-DT-VN-71 {name}, got {len(matches)}")
        supplier_reference_dimension(
            adapter,
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            label=f"MHA-DT-VN-71 supplied {name}",
            units="in",
            precision=0,
            expected_mm=value_mm,
            presentation="length",
            fraction_denominator=STOCK_FRACTION_DENOMINATOR,
        )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Shaft Key Manufacturing Drawing",
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
