r"""Create the manufacturing drawing for MHA-DT-03-TL-06, the keyed arbor's key.

Shop tooling (issue #2465): 1/16 square undersized key stock cut to length
(``dt_cone_gear_tl_arbor_key_spec``). Its section prints as the stock's
fraction reference on the end view, its cut length at the title block's .XX
on the side view (MHA-DT-VN-71's sheet); the kit (MHA-DT-03-TL-05) bonds it.
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
from dt_cone_gear_tl_arbor_key_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    SIZE,
    STOCK_FRACTION_DENOMINATOR,
    STOCK_FRACTION_DIMENSIONS,
)


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_arbor_key"]
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

# Every view at the sheet's 8:1: the .0625 section spans 12.7 mm and the .15
# length 30.5 mm; the end view stands left of the side view in line, the
# isometric under the side view, clear of the title block.
SHEET_SCALE = (8.0, 1.0)
VIEW_SCALE = (8, 1)
FRONT_CENTER = (0.080, 0.190)
RIGHT_CENTER = (0.200, 0.190)
ISO_CENTER = (0.200, 0.110)
HALF_SIZE = SIZE * VIEW_SCALE[0] / 2000.0
HALF_LENGTH = LENGTH * VIEW_SCALE[0] / 2000.0
# The end view's height (model X, horizontal) above it, its width (model Y,
# vertical) right of it with its value below the square (MHA-DT-VN-71's sheet,
# machinist review of PR #2331); the side view's length under it.
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
NOTES_XY = (0.030, 0.120)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open arbor key source", await adapter.open_model(str(SOURCE)))
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
            0: "Keyed Cutting Arbor Key Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: "keyed arbor key; square key stock; cut to length; steel",
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
            raise RuntimeError(f"expected one arbor key {name}, got {len(matches)}")
        supplier_reference_dimension(
            adapter,
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            label=f"arbor key supplied {name}",
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
        pdf_title="Keyed Cutting Arbor Key Drawing",
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
