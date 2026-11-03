r"""Manufacturing drawing of the cone gears' dividing-head index plate (MHA-DT-03-TL-01).

The sheet prints decimal inch (the part's ``drawing_unit: in``). The face
view (*Front, the countersunk face toward the index arm) at 3:2 carries the
plate diameter, the banded bore, the three index circles' bolt-circle
diameters with their counts, the index-hole size once for all 132 holes, and
the mounting holes' size, countersink and bolt circle. Every size is a model
dimension imported from the part; the counts, EQ SP, the countersink and the
mates ride the native callout text. A centre mark with extended lines on the
bore gives the vertical centreline each pattern clocks to. The edge view
(*Right) gives the thickness; the shaded isometric sits top right.

Every size is a best guess pending measurement (#2157); the sheet states the
index circles' web shortfall as a plain fact (rule 20).
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
import dt_cone_gear_tl_index_plate_spec as part
from dt_cone_gear_tl_index_plate_spec import GEOMETRIC_TOLERANCES_IN
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_basic_dimensions,
    set_dimension_callouts,
)
from _drawing_gdt import add_feature_control_frame
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _native_axis_datum import add_native_axis_datum
from _paths import CAD_ROOT
from _session import run_build
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import place_view, view_name

SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_index_plate"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A Ø3.94 plate: 3:2 keeps the .157 holes and their .03 webs legible while the
# face view leaves room for callouts on both sides.
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
ISO_SCALE = (1, 2)
FACE_CENTER = (0.130, 0.150)
# Third-angle right view, level with the face view.
EDGE_CENTER = (0.300, FACE_CENTER[1])
ISO_CENTER = (0.380, 0.195)
ISO_NOTE_XY = (0.345, 0.150)

# Dimension text positions (sheet metres, the text's centre). The plate's
# rim stands 75 mm (sheet) from the centre: the outer index circles' sizes
# and the one hole callout stand right of it, between the face and edge
# views; the plate, bore and mounting sizes stand left and below.
_FX, _FY = FACE_CENTER
FACE_KEEP = {
    "PlateDia": (_FX - 0.080, _FY + 0.093),
    part.PRINTED_HOLE: (_FX + 0.115, _FY + 0.098),
    "Ring57Pcd": (_FX + 0.115, _FY + 0.050),
    "Ring51Pcd": (_FX + 0.115, _FY + 0.008),
    "Ring24Pcd": (_FX + 0.110, _FY - 0.040),
    "MountHoleDia": (_FX - 0.095, _FY + 0.030),
    "BoreDia": (_FX - 0.087, _FY - 0.050),
    "MountPcd": (_FX - 0.020, _FY - 0.100),
}
# Above the edge view's top, clear of its witness lines.
EDGE_KEEP = {"PlateThick": (EDGE_CENTER[0], _FY + 0.090)}

# swCenterMarkStyle_e.swCenterMark_Single; swCenterMarkHandle_e Up/Left/Down/Right.
CENTER_MARK_SINGLE = 2
_CENTER_MARK_HANDLES = (0, 1, 2, 3)
# Each arm runs past the plate's rim (model metres beyond the bore's mark).
CENTRE_LINE_OVERRUN_MM = 3.0

# Owner ruling RV-02 (machinist_exceptions) accepts this control: the BASIC
# hole circles and the 132X position frame to datum A.
# The index holes' position frame: its leader lands on hole 20 of the 57-hole
# circle (lower right, clear of the circle callouts), at a rim point 45° off
# the radial so no centre-mark arm sits under the pick; the frame and its
# count stand below the 24-hole circle's callout, left of the title block.
_POSITION_HOLE_DEG = 90.0 - 20 * 360.0 / 57
POSITION_FRAME_XY = (0.222, 0.088)


@_telemetry.traced("drawing.index_plate_bore_centre_mark")
def _centre_mark_bore(adapter: Any, view: Any) -> None:
    """Centre-mark the bore with lines extended past the rim: the vertical
    centreline that one hole of every pattern sits on (draw_dt_cone_gear's
    bore mark, with its arms shown)."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the face view {name!r}")
    draw.ClearSelection2(True)
    pick = model_point_in_view(
        adapter,
        view,
        (-part.BORE_DIA / 2000.0, 0.0, part.THICKNESS / 1000.0),
        label="bore rim -X point",
    )
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    if not extension.SelectByID2(
        "", "EDGE", pick[0], pick[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("failed to select the bore rim")
    mark = ddoc.InsertCenterMark3(CENTER_MARK_SINGLE, False, False)
    draw.ClearSelection2(True)
    if mark is None:
        raise RuntimeError("failed to centre-mark the bore")
    mark = _early_bound(mark, "ICenterMark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = True
    arm = (part.PLATE_DIA - part.BORE_DIA) / 2000.0 + CENTRE_LINE_OVERRUN_MM / 1000.0
    for handle in _CENTER_MARK_HANDLES:
        if not mark.SetExtendedLength(0, handle, arm):
            raise RuntimeError(f"bore centre mark arm {handle} did not extend")
    if bool(mark.UseDocDisplaySettings) or not bool(mark.ShowLines):
        raise RuntimeError("bore centre mark lost its extended lines")
    _telemetry.success(
        "bore centre mark arms: "
        + ", ".join(
            f"{float(mark.GetExtendedLength(0, h)):.4f}" for h in _CENTER_MARK_HANDLES
        )
    )


@_telemetry.traced("drawing.index_plate_position")
def _position_index_holes(adapter: Any, view: Any) -> None:
    """Datum A on the bore; every index hole's position zone to it."""
    add_native_axis_datum(
        adapter,
        view,
        entity=visible_circle_edge(adapter, view, part.BORE_DIA),
        source_path=SOURCE,
        radius_m=part.BORE_DIA / 2000.0,
        datum=part.BORE_DATUM,
        label="index plate bore axis",
        stability_tolerance_m=0.0001,
    )
    centre = math.radians(_POSITION_HOLE_DEG)
    rim = centre - math.pi / 4.0
    pcd_r = part.RING_PCDS[57] / 2.0
    hole_r = part.INDEX_HOLE_DIA / 2.0
    landing = model_point_in_view(
        adapter,
        view,
        (
            (pcd_r * math.cos(centre) + hole_r * math.cos(rim)) / 1000.0,
            (pcd_r * math.sin(centre) + hole_r * math.sin(rim)) / 1000.0,
            part.THICKNESS / 1000.0,
        ),
        label="57-hole circle hole 20 rim",
    )
    add_feature_control_frame(
        adapter,
        view,
        edge_xy=landing,
        frame_xy=POSITION_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["index-hole position"],
        datums=(part.BORE_DATUM,),
        diameter=True,
        quantity=f"{part.HOLE_COUNT}X",
        label="index-hole position",
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source index plate missing: {SOURCE}")
    check("open index plate", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part.UNIT,
    )
    stamp_drawing_summary(
        adapter,
        drawing,
        {
            0: "Cone Gear Dividing Head Index Plate Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: "BS-0 dividing head index plate; 57, 51 and 24 holes; MHA-DT-03-TL-01",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=VIEW_SCALE)
    edge = place_view(adapter, str(SOURCE), "*Right", *EDGE_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    annotations: list[Any] = []
    for view, keep, label in (
        (face, FACE_KEEP, "face view"),
        (edge, EDGE_KEEP, "edge view"),
    ):
        set_hidden_lines_removed(adapter, view)
        annotations += curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=label,
            dimensions_by_feature=part.DRAWING_DIMENSIONS,
        )
    set_hidden_lines_removed(adapter, iso)
    set_dimension_callouts(adapter, annotations, part.CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, part.CALLOUTS_BELOW)
    assert_imported_precision(adapter, annotations, part.DRAWING_PRECISION_BY_NAME)
    set_basic_dimensions(adapter, annotations, part.BASIC_DIMENSIONS)
    _centre_mark_bore(adapter, face)
    _position_index_holes(adapter, face)
    for view in (face, edge, iso):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Dividing Head Index Plate Drawing",
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
