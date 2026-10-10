r"""Manufacturing drawing of the open-rebate brass stop block.

The cover-side view and end view show the rebate in solid lines. Standard
native Hole Wizard callouts define the orthogonal taps, including blind full
thread and drill depths. Every controlling dimension is imported unchanged.
Hole-mouth points convert the shared millimetre frame to COM metres before
projection; the cover-side *Back view reverses X, not the coordinate units.
The *Bottom view is turned 180 degrees to preserve that X direction and
show the true third-angle underside; its current transform locates the tap.
Native callout positions centre their text; reserve the full two-line tap
instruction inside the print border and keep the thumb callout off the title.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _config
import _telemetry
import ms_stop_spec as part
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs, add_native_hole_callout, add_property_linked_callout,
    add_property_linked_note,
    finalize_drawing, model_point_in_view,
    new_project_drawing, read_required_properties, rebuild_drawing, set_dimension_callouts,
    set_hidden_lines_removed, stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _ms_drawing_contract import assert_manufacturing_dimensions
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["ms_stop_block"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (4.0, 1.0)
FRONT_CENTER = (0.155, 0.185)
RIGHT_CENTER = (0.315, FRONT_CENTER[1])
BOTTOM_CENTER = (FRONT_CENTER[0], 0.080)
# Native 2:1 outline is 56.4 x 60.3 mm; fit above the title and below the end view.
ISO_CENTER = (0.360, 0.119)
FRONT_KEEP = {
    "BlockLength": (0.155, 0.235), "BlockHeight": (0.085, 0.185),
    "RoofChamferSize": (0.227, 0.240), "RoofChamferAngle": (0.207, 0.220),
    "PlateLeftFromEnd": (0.155, 0.140),
    "PlateRightFromEnd": (0.155, 0.122),
    "PlateFromHeadFace": (0.100, 0.163),
}
RIGHT_KEEP = {
    "BlockDepth": (0.315, 0.235), "WindowWidth": (0.315, 0.130),
    "WindowHeight": (0.365, 0.198), "RoofThickness": (0.350, 0.215),
}
BOTTOM_KEEP = {
    "ThumbFromEnd": (0.175, 0.038), "ThumbFromPlate": (0.090, 0.080),
}
# Native horizontal size witnesses end at this corner rather than spanning
# the view; the shorter angle arc stays below the overall length dimension.
DIMENSION_CALLOUTS = {"RoofChamferSize": "2 CORNERS", "WindowWidth": "OPEN REBATE"}
# The title block owns the general internal thread class. Keep Hole Wizard's
# variable definitions, not the resolved text that would freeze drill/depths.
FINAL_SHEET_REMOVED_NOTES = ("Tapped Hole",)
COVER_HOLE_PROCESS = (
    "2X MATCH-DRILL WITH MS-STOP-PLATE\n"
    f"{_config.parts('ms-stop-plate')['number']} CLAMPED\n"
)


def _remove_general_thread_class(display: Any) -> None:
    """Suppress only the native class token; leave thread/drill variables live."""
    native = _early_bound(display, "IDisplayDimension")
    if not native.IsHoleCallout():
        raise RuntimeError("general thread class removal requires a native hole callout")
    definition = str(native.GetText(5) or "")  # swDimensionTextPrefixDefinition
    token = "<hw-threadclass>"
    if definition.count(token) != 1:
        raise RuntimeError(f"native tap callout lacks one thread-class variable: {definition!r}")
    before, _token, after = definition.partition(token)
    before = before.rstrip(" \t")
    if before.endswith("-"):
        before = before[:-1].rstrip(" \t")
    revised = before + after
    native.SetText(1, revised)  # swDimensionTextPrefix; void return
    if str(native.GetText(5) or "") != revised:
        raise RuntimeError("native tap class-token removal did not persist")


def _orient_bottom_view(adapter: Any, view: Any) -> None:
    """Make *Bottom the third-angle underside of the displayed *Back face."""
    native = _early_bound(view, "IView")
    native.Angle = math.pi
    rebuild_drawing(adapter, label="stop block underside orientation")
    applied = float(native.Angle)
    if not math.isfinite(applied) or abs(math.remainder(applied - math.pi, math.tau)) > 1e-9:
        raise RuntimeError(
            f"stop block underside rotation did not take: {applied!r} rad, expected pi"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source stop block missing: {SOURCE}")
    check("open stop block", await adapter.open_model(str(SOURCE)))
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity")
    read_required_properties(adapter.currentModel, properties,
                             required=("Number", "Material Specification", "Finish", "Quantity"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM,
                                        scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing, {
        0: "Measuring Stick Stop Block Manufacturing Drawing",
        1: "Harmonic Analyzer hobby-machinist book drawing",
        2: "Harmonic Analyzer Project", 3: "brass stop block; open rebate; native taps",
        4: "Generated from the project-owned ASME B drawing standard",
    })
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Left", *RIGHT_CENTER, scale=SHEET_SCALE)
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=SHEET_SCALE)
    _orient_bottom_view(adapter, bottom)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2.0, 1.0))
    annotations = []
    for view, keep, label in ((front, FRONT_KEEP, "cover face"),
                              (right, RIGHT_KEEP, "open rebate end"),
                              (bottom, BOTTOM_KEEP, "thumbscrew face")):
        set_hidden_lines_removed(adapter, view)
        annotations += curate_view_dimensions(adapter, view, keep=keep, view_label=label,
                                               dimensions_by_feature=part.BLOCK_DRAWING_DIMENSIONS)
    set_hidden_lines_removed(adapter, iso)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    plate_edge = model_point_in_view(
        adapter, front, (
            (part.PLATE_HOLE_XS[1] + part.PLATE_TAP_DRILL_DIA / 2.0) / 1000.0,
            part.PLATE_HOLE_Y / 1000.0, part.PLATE_Z_MAX / 1000.0,
        ), label="plate tap mouth")
    plate_callout = add_native_hole_callout(
        adapter, front, edge_xy=plate_edge, callout_xy=(0.065, 0.138),
        label="two cover blind taps",
        process=COVER_HOLE_PROCESS,
    )
    _remove_general_thread_class(plate_callout)
    thumb_edge = model_point_in_view(
        adapter, bottom, (
            (part.THUMB_AXIS_X + part.THUMB_TAP_DRILL / 2.0) / 1000.0,
            0.0, part.THUMB_AXIS_Z / 1000.0,
        ), label="thumb tap mouth")
    thumb_callout = add_native_hole_callout(
        adapter, bottom, edge_xy=thumb_edge, callout_xy=(0.060, 0.063),
        label="thumbscrew tap through floor",
    )
    _remove_general_thread_class(thumb_callout)
    mating_edge = model_point_in_view(
        adapter, right, (
            part.BLOCK_LENGTH / 2000.0,
            (part.WINDOW_Y_MAX + (part.ROOF_THICKNESS - part.ROOF_END_CHAMFER) / 2.0) / 1000.0,
            part.PLATE_Z_MAX / 1000.0,
        ), label="cover mating face",
    )
    add_property_linked_callout(
        adapter, right, property_name="Mating Face Note",
        edge_xy=mating_edge, note_xy=(0.220, 0.210),
    )
    for view in (front, bottom):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError("stop tap centre marks failed")
    assert_manufacturing_dimensions(
        adapter, annotations, part.BLOCK_DRAWING_VALUES_BY_NAME,
        part.BLOCK_DRAWING_PRECISION_BY_NAME,
        bands={
            **{name: part.WINDOW_SIZE_TOLERANCE_MM for name in ("WindowWidth", "WindowHeight")},
            **{name: (-part.PLATE_HOLE_POSITION_TOLERANCE_MM, part.PLATE_HOLE_POSITION_TOLERANCE_MM)
               for name in part.PLATE_LOCATION_DIMENSIONS},
        },
        angular=frozenset({"RoofChamferAngle"}),
    )
    for view in (front, right, bottom):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Isometric View Note", ISO_CENTER[0] - 0.030, 0.085)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.024, 0.036)
    return await finalize_drawing(adapter, OUTPUTS,
                                  pdf_title="Measuring Stick Stop Block Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout,
                                  redundant_note_substrings=FINAL_SHEET_REMOVED_NOTES,
                                  expected_redundant_notes=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
