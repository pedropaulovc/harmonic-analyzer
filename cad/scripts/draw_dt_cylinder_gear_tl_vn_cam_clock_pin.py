r"""Create the curated manufacturing drawing for MHA-DT-12-TL-VN-51.

The cam fixture's clock pin is a McMaster-Carr 23065A503 gauge pin cut to
length (draw_dt_vn_crank_hub_pin's pattern). Its diameter prints as the
supplier's reference with the press fit's mate under it, its length at the
title block's .XX.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_projection import model_point_in_view
from _drawing_dimensions import assert_imported_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _supplier_dimensions import supplier_reference_dimension
from dt_cylinder_gear_tl_vn_cam_clock_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DIA,
    PIN_LEN,
    PIN_DIA_CALLOUT,
    STOCK_REFERENCE_DIMENSIONS,
)

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_vn_cam_clock_pin"]
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
# The pin stands on +Y: the front view shows its length vertical, the top
# view its end. Low enough that the end view's centre mark stays inside the
# top border (run 20261112T203156536Z: its arms crossed it by 8 mm).
FRONT_CENTER = (0.150, 0.130)
TOP_CENTER = (0.150, 0.230)
ISO_CENTER = (0.320, 0.170)
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0
# swCenterMarkStyle_e.swCenterMark_Single; swCenterMarkHandle_e Up/Left/Down/Right.
CENTER_MARK_SINGLE = 2
_CENTER_MARK_HANDLES = (0, 1, 2, 3)
# The end mark's arms run this far past the rim (model mm; 2 mm on the sheet).
END_ARM_OVERRUN_MM = 0.2
FRONT_KEEP = {
    "PinDia": (FRONT_CENTER[0] + HALF_DIA + 0.040, FRONT_CENTER[1] + 0.020),
    "PinLen": (FRONT_CENTER[0] - HALF_DIA - 0.020, FRONT_CENTER[1]),
}


@_telemetry.traced("drawing.cam_clock_pin_end_centre_mark")
def _centre_mark_end(adapter: Any, view: Any) -> None:
    """One centre mark on the pin's end circle. The view's auto-insert put
    two on it (both end rims project there) and ran its arms 25 mm."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the end view {name!r}")
    draw.ClearSelection2(True)
    pick = model_point_in_view(
        adapter,
        view,
        (-PIN_DIA / 2000.0, PIN_LEN / 1000.0, 0.0),
        label="clock pin end rim -X point",
    )
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    if not extension.SelectByID2(
        "", "EDGE", pick[0], pick[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("failed to select the clock pin's end rim")
    mark = ddoc.InsertCenterMark3(CENTER_MARK_SINGLE, False, False)
    draw.ClearSelection2(True)
    if mark is None:
        raise RuntimeError("failed to centre-mark the clock pin's end")
    mark = _early_bound(mark, "ICenterMark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = True
    for handle in _CENTER_MARK_HANDLES:
        if not mark.SetExtendedLength(0, handle, END_ARM_OVERRUN_MM / 1000.0):
            raise RuntimeError(f"clock pin end mark arm {handle} did not extend")
    if bool(mark.UseDocDisplaySettings) or not bool(mark.ShowLines):
        raise RuntimeError("clock pin end mark lost its extended lines")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open clock-pin source", await adapter.open_model(str(SOURCE)))
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
            0: "Cylinder Gear Cam Fixture Clock Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cam fixture clock pin; gauge pin; shop tooling; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name, value_mm in STOCK_REFERENCE_DIMENSIONS.items():
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one MHA-DT-12-TL-VN-51 {name}, got {len(matches)}"
            )
        supplier_reference_dimension(
            adapter,
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            label=f"MHA-DT-12-TL-VN-51 supplied {name}",
            units="in",
            precision=DRAWING_PRECISION_BY_NAME[name],
            expected_mm=value_mm,
            presentation="diameter",
            callout=PIN_DIA_CALLOUT,
        )
    _centre_mark_end(adapter, top)
    add_view_centerline(
        adapter,
        front,
        face_xy=(FRONT_CENTER[0] + 0.0005, FRONT_CENTER[1]),
        label="MHA-DT-12-TL-VN-51 axis centerline",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.082)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Cam Fixture Clock Pin Manufacturing Drawing",
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
