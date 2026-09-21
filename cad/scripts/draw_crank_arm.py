r"""Create the curated machinist drawing for the crank arm.

The SLDPRT remains authoritative.  This recipe supplies only the crank-arm
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the arm is 93 mm end to end); the isometric carries an
explicit 1:1 override so it stays clear of the title block.

The principal view is the model's *Front* face, where the fiducial dimple and
keeper-ring anchor are authored on ``HandleSeat`` at local z=8 mm. Third-angle
projection therefore uses the unrotated *Top* and *Right* views; model +X runs
to paper-right in the principal and top views.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): the
arm is a pinned hand-crank lever, so it carries no datums, no feature-control
frames, no roughness symbols and no basic dimensions -- the title block's
general tolerances govern everything.  Every printed value is a model
dimension imported with the part's own decimal places (rule 2); the hole
stations the Hole Wizard cannot measure from a feature come from the part's
hidden ``StationReference`` / ``PinStationReference`` sketches.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_arm.py crank-arm
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Any

import _telemetry
from _config import parts, title_block
from _hole_spec import blind_cut_dia_mm, drill_process
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hole_callout_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_arc_endpoints_to_max,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from crank_arm_spec import (
    ANCHOR_HOLE_SPEC,
    ANCHOR_SCREW_X,
    ANCHOR_SCREW_Y,
    ARM_C2C,
    ARM_END_X,
    DIMPLE_X,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    HALF_WIDTH,
    HANDLE_PIVOT_HOLE_SPEC,
    SHAFT_BORE_DIA,
    PIN_HOLE_SPEC,
)
from crankshaft_spec import SHAFT_DIA as CRANKSHAFT_DIA
from crankshaft_spec import SHAFT_DIA_BAND as CRANKSHAFT_DIA_BAND
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_arm"]
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
_HANDLE_PIVOT_HOLE_DIA = blind_cut_dia_mm(HANDLE_PIVOT_HOLE_SPEC)
_PIN_HOLE_DIA = blind_cut_dia_mm(PIN_HOLE_SPEC)
_CRANKSHAFT_NUMBER = str(parts("crankshaft")["number"])
_HOLE_TOLERANCE = title_block("drilled_hole")
_SHAFT_CLEARANCE_MIN = (
    SHAFT_BORE_DIA + float(_HOLE_TOLERANCE["minus_mm"])
) - (CRANKSHAFT_DIA + CRANKSHAFT_DIA_BAND[0])
_SHAFT_CLEARANCE_MAX = (
    SHAFT_BORE_DIA + float(_HOLE_TOLERANCE["plus_mm"])
) - (CRANKSHAFT_DIA + CRANKSHAFT_DIA_BAND[1])
if _SHAFT_CLEARANCE_MIN < 0.0:
    raise AssertionError("title-block crank-arm bore range interferes with shaft")
PIN_HOLE_CALLOUT_PREFIX = f"{drill_process(PIN_HOLE_SPEC)}\nON SHAFT-BORE CL"
# The top view is cropped around the shaft boss: it retains the HLV evidence
# that the #14 cross-hole meets the shaft bore without repeating the remote
# tap, dimple and handle-pivot profiles.


SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  The principal (front) view's model bbox runs
# boss..arm-end in sheet X (93 mm overall, model +X to the right) and +/-8 in
# Y; at 2:1 the principal view is 186 x 32 mm. The cropped edge-on view sits
# above it and carries only the shaft-boss cross-hole evidence; the side view
# (16 x 8 stock section) is to its right.
FRONT_CENTER = (0.145, 0.135)
TOP_CENTER = (0.145, 0.205)
RIGHT_CENTER = (0.300, 0.135)
ISO_CENTER = (0.360, 0.230)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the principal/top views (2:1, bbox-centred)."""
    bbox_center = (ARM_END_X - HALF_WIDTH) / 2.0
    return FRONT_CENTER[0] + (model_x_mm - bbox_center) * SHEET_SCALE[0] / 1000.0


def _set_reference_precision(adapter: Any, display: Any, label: str) -> None:
    """Give the one SHEET-derived dimension its PART-authored decimal places.

    Every controlling dimension on this print is a model dimension whose
    places the part authored and ``assert_imported_precision`` reads back.
    The parenthesised overall (boss extreme to arm end) is the single
    exception: a read-only sum with no model dimension to import, so its
    places come from the spec's ``DRAWING_REFERENCE_PRECISION`` -- never a
    literal typed here.  ``SetPrecision3`` reports rejection through its
    return status rather than by raising, so the side effect is read back.
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: swDimensionPrecisionSettings_e do-not-change for the dual and both
    # tolerance places.  The subscript is written out again because
    # _drawing_contract only accepts a spec lookup here.
    adapter._attempt(
        lambda: display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    )
    applied = adapter._attempt(display.GetPrimaryPrecision2)
    if applied != places:
        raise RuntimeError(
            f"{label}: sheet dimension prints {applied} decimal places, not {places}"
        )


def _add_arm_centerline(adapter: Any, view: Any) -> None:
    """Draw the arm's longitudinal centreline between its two long edges.

    The shaft bore, the fiducial dimple and the handle-pivot hole all sit on
    the arm's mid-width axis and no cross-width location dimension exists to
    say so; the drawn centreline through their centre marks is the ASME way
    to state it.  Both picks land on the straight edge run between the
    dimple and the pivot, clear of every hole.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the front view for its centreline")
    draw.ClearSelection2(True)
    x = _sheet_x((DIMPLE_X + ARM_C2C) / 2.0)
    for index, side in enumerate((-1.0, 1.0)):
        y = FRONT_CENTER[1] + side * HALF_WIDTH * SHEET_SCALE[0] / 1000.0
        if not draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, index > 0, 0, null_callout(), 0
        ):
            raise RuntimeError("failed to select an arm long edge for its centreline")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError("failed to insert the arm centreline between its edges")
    count = int(_early_bound(view, "IView").GetCenterLineCount())
    if count != 1:
        raise RuntimeError(f"front view carries {count} centrelines, expected 1")

def _crop_top_view_to_shaft(adapter: Any, view: Any) -> None:
    """Crop the HLV top view to the shaft boss and prove remote holes are absent."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native_view = _early_bound(view, "IView")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate top view for shaft-boss crop")
    draw.ClearSelection2(True)

    crop_center = (_sheet_x(0.0), TOP_CENTER[1])
    crop_radius = (HALF_WIDTH + 2.0) * SHEET_SCALE[0] / 1000.0
    sketch = _early_bound(native_view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (
        crop_center,
        (crop_center[0] + crop_radius, crop_center[1]),
    ):
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if sketch_manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create shaft-boss crop fence")

    # IView.Crop2 returns swCropViewErrors_e, where 1 is NoError.
    if int(native_view.Crop2(False, True, 0)) != 1:
        raise RuntimeError("failed to crop top view to shaft boss")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    native_view.UpdateViewDisplayGeometry()
    if not bool(native_view.IsCropped()):
        raise RuntimeError("top view did not retain its shaft-boss crop")
    outline = tuple(float(value) for value in native_view.GetOutline())
    if (
        len(outline) != 4
        or not outline[0] < crop_center[0] < outline[2]
        or outline[2] >= _sheet_x(DIMPLE_X)
    ):
        raise RuntimeError(
            "top-view crop did not isolate the shaft boss: "
            f"outline={outline!r}, dimple_x={_sheet_x(DIMPLE_X)!r}"
        )

_ANCHOR_HOLE_DIA = blind_cut_dia_mm(ANCHOR_HOLE_SPEC)

def _omit_title_block_thread_class(display: Any) -> None:
    """Remove only the redundant Hole Wizard thread-class field."""
    native = _early_bound(display, "IDisplayDimension")
    definition = str(native.GetText(5) or "")
    without_class = re.sub(
        r"\s*-\s*<hw-threadclass>\s*", " ", definition, flags=re.IGNORECASE
    )
    without_class = re.sub(r" {2,}", " ", without_class)
    if without_class == definition:
        raise RuntimeError(
            f"anchor tap callout lacks its thread-class variable: {definition!r}"
        )
    # IDisplayDimension.SetText is void; the definition readback is the
    # authoritative persistence check.
    native.SetText(1, without_class)
    if str(native.GetText(5) or "") != without_class:
        raise RuntimeError("anchor tap callout retained its redundant thread class")




# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Leadered diameters sit above the arm at each feature's station;
# the linear chain stacks below the view from the shaft-bore axis, smallest
# span nearest the geometry (anchor 20, dimple 30, pivot 75, end 85, ref 93).
# The anchor's offset from the top long edge stands just left of the tap,
# above the arm; the stock width stands past the arm end.
FRONT_KEEP = {
    "ArmEndX": (0.190, 0.085),
    "PivotStation": (_sheet_x(ARM_C2C / 2.0), 0.095),
    "DimpleX": (_sheet_x(DIMPLE_X / 2.0), 0.104),
    "AnchorStation": (_sheet_x(ANCHOR_SCREW_X / 2.0), 0.112),
    "AnchorOffset": (0.095, 0.158),
    "AxisOffset": (0.245, FRONT_CENTER[1] + 0.008),
    "Width": (0.274, FRONT_CENTER[1]),
    # Left of the boss so its leader and the bore's (above) never cross.
    "BossRadius": (0.030, FRONT_CENTER[1]),
    "ShaftBoreDia": (0.060, 0.166),
    # Right of the anchor tap so its leader never meets the tap callout's.
    "DimpleDia": (0.178, 0.180),
}
RIGHT_KEEP = {"Depth": (0.300, 0.108)}
# The straight #14 cross-hole's station from the broad face, seen edge-on.
TOP_KEEP = {"PinStation": (0.095, TOP_CENTER[1] + 0.014)}
DIMENSION_CALLOUTS = {
    "ShaftBoreDia": (
        "REAM THRU (3/8 IN)\n"
        f"{_SHAFT_CLEARANCE_MIN:.2f}-{_SHAFT_CLEARANCE_MAX:.2f} DIAMETRAL\n"
        f"CLEARANCE ON {_CRANKSHAFT_NUMBER}"
    ),
    "DimpleDia": "FIDUCIAL FLAT-BOTTOM\n0.3 MIN, 1.0 MAX DEEP",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-arm source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank arm; manufacturing drawing; straight cross-hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    # The cropped top view alone needs HLV: it proves the #14 cross-drill meets
    # the shaft bore.  The front view's blind-feature depths are fully carried
    # by their callouts, so HLR keeps same-face dimple/tap evidence consistent
    # and removes the cross-hole's redundant hidden projection.
    set_hidden_lines_visible(adapter, top)
    _crop_top_view_to_shaft(adapter, top)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Right view: the 16 x 8 stock section.  Thickness is the model Depth dim;
    # the 16 width is the model's Width dim on the principal view, standing
    # past the arm end.
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Top view: cross-drill geometry is visible; its station from the broad
    # face is the model's PinStation dim and its size a native hole callout.
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported_annotations = [*front_annotations, *top_annotations, *right_annotations]
    set_dimension_callouts(adapter, imported_annotations, DIMENSION_CALLOUTS)
    # The part authored every decimal place (policy rule 2): three on the
    # reamed 3/8 in bore alone, one everywhere else.  Read them back; an
    # import that fell back to the sheet default would print a band nobody
    # specified.
    assert_imported_precision(adapter, imported_annotations, DRAWING_PRECISION_BY_NAME)

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
    _add_arm_centerline(adapter, front)

    # Handle-pivot callout attaches at the hole's top rim; the pivot's station
    # from the bore axis is the part's PivotStation dim imported above.
    handle_edge = (
        _sheet_x(ARM_C2C),
        FRONT_CENTER[1] + _HANDLE_PIVOT_HOLE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    # Anchor tap: size and both depths on a native Hole Wizard callout; its
    # station from the bore axis and its offset from the top long edge are the
    # part's StationReference dims imported above.
    anchor_edge = (
        _sheet_x(ANCHOR_SCREW_X),
        FRONT_CENTER[1]
        + (ANCHOR_SCREW_Y + _ANCHOR_HOLE_DIA / 2.0) * SHEET_SCALE[0] / 1000.0,
    )
    anchor_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=anchor_edge,
        callout_xy=(0.150, 0.205),
        label="anchor tap",
    )
    _omit_title_block_thread_class(anchor_callout)
    set_hole_callout_precision(
        anchor_callout,
        {"hw-tapdrldepth": 1, "hw-threaddepth": 1},
        label="anchor tap depths",
    )
    # The true overall (boss extreme to arm end), as a reference below the
    # 85.0 centre-to-end chain so nobody saws the stock 8 mm short
    # (Harvey #25).  Picked at the boss arc's outer extreme so the default
    # tangent arc condition measures the far side, not the centre.
    overall = add_edge_dimension(
        adapter,
        front,
        p0=(_sheet_x(-HALF_WIDTH), FRONT_CENTER[1]),
        p1=(_sheet_x(ARM_END_X), FRONT_CENTER[1] - 0.004),
        text_xy=(_sheet_x(ARM_C2C / 2.0), 0.073),
        label="overall length reference",
        orientation="horizontal",
    )
    set_arc_endpoints_to_max(adapter, overall, label="overall length reference")
    # add_edge_dimension hands back the IDisplayDimension (late-bound); bind
    # it before reading the IAnnotation the reference helper wants.
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length reference",
    )
    _set_reference_precision(adapter, overall, "overall length reference")

    # The straight #14 cross-hole, seen in the cropped top view: the native
    # size callout carries the drill prefix and PinStation locates it from the
    # broad face.
    pin_edge = (
        _sheet_x(0.0),
        TOP_CENTER[1] + _PIN_HOLE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=pin_edge,
        callout_xy=(0.120, 0.230),
        label="crank-arm cross-hole",
        process=PIN_HOLE_CALLOUT_PREFIX,
    )
    # Handle pivot hole: above and just right of the arm, arrow on the hole's
    # top rim. Keeping it on the handle end avoids crossing the full principal
    # view now that model +X runs to paper-right.
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=handle_edge,
        callout_xy=(0.258, 0.172),
        label="handle pivot hole",
        process=drill_process(HANDLE_PIVOT_HOLE_SPEC),
    )

    if add_note(adapter, "PARTIAL TOP VIEW - SHAFT END", 0.047, 0.184) is None:
        raise RuntimeError("failed to label partial crank-arm top view")
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.185)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Arm Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#4-40 Tapped Hole" note to the front view
        # once the tap carries a hole callout; that callout already states
        # the thread, the drill and both depths (iter3 printed both).
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
