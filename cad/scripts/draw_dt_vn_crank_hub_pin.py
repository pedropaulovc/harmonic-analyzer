r"""Create the curated manufacturing drawing for MHA-DT-VN-59.

The pin is a plain straight dowel with an extraction thread tapped through its
axis from the flush outer end. Its two native dimensions define the part;
the end view's associative Hole Wizard callout owns the thread identity.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

from _check import check
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_reference_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_vn_crank_hub_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DIA,
    PULL_THREAD_TAP_DRILL,
    REFERENCE_DIMENSIONS,
)


SPEC = DRAWINGS_BY_NAME["dt_vn_crank_hub_pin"]
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

SHEET_SCALE = (10.0, 1.0)
VIEW_SCALE = (10, 1)
FRONT_CENTER = (0.095, 0.180)
RIGHT_CENTER = (0.225, 0.180)
ISO_CENTER = (0.355, 0.180)
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0
RIGHT_KEEP = {
    "PinDia": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] + HALF_DIA + 0.016),
    "PinLen": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_DIA - 0.016),
}
# Outer-end view (*Front, centre FRONT_CENTER): the native callout lands on
# the tap-drill rim at 45 deg, off the centre-mark arms. Its text sits above
# the Ø40-sheet pin outline (top at y 0.200), left of the right-view diameter.
_TAP_RIM = PULL_THREAD_TAP_DRILL * VIEW_SCALE[0] / 2000.0 / 2.0**0.5
THREAD_PICK = (FRONT_CENTER[0] + _TAP_RIM, FRONT_CENTER[1] + _TAP_RIM)
THREAD_NOTE_XY = (FRONT_CENTER[0] + 0.027, FRONT_CENTER[1] + HALF_DIA + 0.016)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-hub-pin source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Hub Axial Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank hub seam pin; axial key; straight gauge; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-DT-VN-59 end view")
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="MHA-DT-VN-59 axis centerline",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=THREAD_PICK,
        callout_xy=THREAD_NOTE_XY,
        label="MHA-VN-029 pull thread callout",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.082)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Hub Axial Pin Manufacturing Drawing",
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
