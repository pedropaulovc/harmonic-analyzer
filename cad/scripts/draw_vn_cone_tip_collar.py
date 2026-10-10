"""Two-sheet manufacturing package: custom collar and ground stock screw.

Native model dimensions own every reworked size, its places and its band.
The radial blind tap is a native Hole Wizard callout, including drill and
full-thread depths. Stock screw end/hex geometry is supplied, not reworked.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
import vn_cone_tip_collar_spec as spec
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs, PmiDrawingPlacement, add_native_hole_callout, add_property_linked_note,
    assert_imported_precision, create_blank_drawing_sheets,
    curate_view_dimensions, dimension_name, finalize_drawing,
    model_point_in_view, new_project_drawing, project_part_pmi,
    read_required_properties, rebuild_drawing,
    set_dimension_callouts, set_hidden_lines_removed,
    set_hole_callout_precision, stamp_drawing_summary, view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import format_findings
from diagnostics.drawing_layout_audit import audit_document
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["vn_cone_tip_collar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png
SHEET_NAMES = ("Collar", "SetScrew")
SHEET_SCALES = {"Collar": (4, 1), "SetScrew": (20, 1)}
END_CENTER = (0.080, 0.170)
SIDE_CENTER = (0.205, 0.170)
TAP_CENTER = (SIDE_CENTER[0], 0.240)
TAP_SCALE = spec.RADIAL_TAP_VIEW_SCALE
ISO_CENTER = (0.345, 0.210)
END_KEEP = {"CollarDia": (0.030, 0.130), "NoseDia": (0.027, 0.165),
            "FlatDistance": (0.080, 0.112)}
SIDE_KEEP = {"CollarWidth": (0.205, 0.110),
             "NoseLength": (0.182, 0.218), "ShoulderRadius": (0.282, 0.205)}
OD_ON_SIDE = (0.250, SIDE_CENTER[1])
TAP_KEEP = {"TapStation": (0.184, 0.266), "TapRootLimit": (0.250, 0.272)}
BORE_CENTER = (0.350, 0.080)
BORE_KEEP = {"BoreDia": (0.310, 0.110)}
SCREW_CENTER = (0.170, 0.165)
SCREW_KEEP = {"DogDia": (0.075, 0.200), "DogLength": (0.096, 0.116)}


def _configuration(adapter, views, name):
    for view in views:
        native = _early_bound(view, "IView")
        native.ReferencedConfiguration = name
        if str(native.ReferencedConfiguration) != name:
            raise RuntimeError(f"view failed to reference {name}")
    rebuild_drawing(adapter, label=f"collar {name} views")


def _horizontal_axis(adapter, view):
    native = _early_bound(view, "IView")
    native.Angle = -math.pi / 2.0
    if abs(float(native.Angle) + math.pi / 2.0) > 1e-9:
        raise RuntimeError("collar axis is not horizontal on the turning view")
    rebuild_drawing(adapter, label="collar turning orientation")


def _move_od(adapter, annotation, source, target):
    """Move the end-profile circle dimension to the turning side view."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source)):
        raise RuntimeError("cannot activate collar OD donor")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection = str(display.GetNameForSelection() or "")
    draw.ClearSelection2(True)
    if not selection or not draw.Extension.SelectByID2(
        selection, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0,
    ):
        raise RuntimeError("cannot select native collar OD")
    ddoc.DragModelDimension(view_name(adapter, target), 2, *OD_ON_SIDE, 0.0)
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="collar OD transfer")
    matches = [_early_bound(a, "IAnnotation") for a in (_early_bound(target, "IView").GetAnnotations() or ())
               if dimension_name(adapter, _early_bound(a, "IAnnotation")) == "CollarDia"]
    if len(matches) != 1:
        raise RuntimeError("native collar OD did not move to the side view")
    return matches[0]


def _require_full_thread_callout(display):
    """Qualify the native thread-depth variable without typing a thread size."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    thread_parts = [part for part, text in definitions.items() if "<hw-threaddepth>" in text]
    if len(thread_parts) != 1 or not any("<hw-tapdrldepth>" in text for text in definitions.values()):
        raise RuntimeError(f"blind collar tap lost its native depth variables: {definitions!r}")
    part = thread_parts[0]
    updated = definitions[part].rstrip() + " FULL THREAD"
    display.SetText(part - 4, updated)
    if str(display.GetText(part) or "") != updated:
        raise RuntimeError("collar tap full-thread qualifier did not persist")


def _assert_functional_dimension_types(adapter, annotations):
    expected = {"TapStation": 1, "TapRootLimit": 6}  # BASIC / MAX
    observed = {}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in expected:
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            observed[name] = int(tolerance.Type)
    if observed != expected:
        raise RuntimeError(f"collar functional location/root limit lost native types: {observed}")


def _bore_view(adapter):
    """Native circular crop, using the existing cone/arbor drawing sequence."""
    view = _early_bound(place_view(
        adapter, str(SOURCE), "*Bottom", *BORE_CENTER, scale=spec.BORE_VIEW_SCALE,
    ), "IView")
    _configuration(adapter, (view,), "Collar")
    if tuple(float(value) for value in view.ScaleRatio) != tuple(spec.BORE_VIEW_SCALE):
        raise RuntimeError("collar bore view lost its source scale")
    axis = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="collar bore axis")
    position = tuple(float(value) for value in view.Position)
    if not view.SetViewPosition(double_array([
        position[i] + BORE_CENTER[i] - axis[i] for i in range(2)
    ]), False):
        raise RuntimeError("cannot centre collar bore view")
    rebuild_drawing(adapter, label="collar bore view position")
    axis = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="collar bore axis readback")
    if math.dist(axis, BORE_CENTER) > 1e-4:
        raise RuntimeError("collar bore axis did not remain centred")
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("cannot activate collar bore crop")
    before = tuple(float(value) for value in view.GetOutline())
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    radius = spec.BORE_FINISHED_DIA_LIMITS_MM[1] * spec.BORE_VIEW_SCALE[0] / (
        2000.0 * spec.BORE_VIEW_SCALE[1]
    ) + 0.003
    points = []
    for x, y in (BORE_CENTER, (BORE_CENTER[0] + radius, BORE_CENTER[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = False
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError("cannot sketch collar bore crop circle")
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="collar bore crop")
    view.UpdateViewDisplayGeometry()
    after = tuple(float(value) for value in view.GetOutline())
    if status != 1 or not view.IsCropped():
        raise RuntimeError(f"collar bore crop failed: {status}")
    if len(before) != 4 or len(after) != 4 or after[2] - after[0] >= before[2] - before[0]:
        raise RuntimeError("collar bore crop did not reduce the native outline")
    if bool(view.CropViewJaggedOutline) or bool(view.CropViewNoOutline):
        raise RuntimeError("collar bore crop lost its plain circle boundary")
    set_hidden_lines_removed(adapter, view)
    marks = curate_view_dimensions(
        adapter, view, keep=BORE_KEEP, view_label="collar enlarged bore",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, marks, spec.DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, marks, {"BoreDia": "REAM THRU"})
    add_property_linked_note(adapter, "Bore View Note", BORE_CENTER[0] - 0.032, 0.044)
    return view


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part missing: {SOURCE}")
    check("open custom collar", await adapter.open_model(str(SOURCE)))
    read_required_properties(adapter.currentModel, (
        "Number", "Revision", "Title", "Material Specification", "Finish",
        "Quantity", "Manufacturing Notes", "Isometric View Note", "Radial Tap View Note",
        "Bore View Note", "Installation Notes",
    ), required=("Number", "Material Specification", "Manufacturing Notes",
                 "Radial Tap View Note", "Bore View Note", "Installation Notes"))
    drawing, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALES["Collar"], layout=SPEC.layout,
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="custom cone collar package")
    stamp_drawing_summary(adapter, drawing, {
        0: "Cone Tip Collar Manufacturing Drawing", 1: "Harmonic Analyzer hobby-machinist drawing",
        2: "Harmonic Analyzer Project", 3: "Custom steel collar and reworked stock set screw",
        4: "Project-owned ASME B drawing standard",
    })
    ddoc = _early_bound(drawing, "IDrawingDoc")
    if not ddoc.ActivateSheet("Collar"):
        raise RuntimeError("cannot activate collar sheet")
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=(4, 1))
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=(4, 1))
    tap = place_view(adapter, str(SOURCE), "*Right", *TAP_CENTER, scale=TAP_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    _configuration(adapter, (end, side, tap, iso), "Collar")
    _horizontal_axis(adapter, side)
    _horizontal_axis(adapter, tap)
    for view in (end, side, tap, iso):
        set_hidden_lines_removed(adapter, view)
    end_marks = curate_view_dimensions(adapter, end, keep=END_KEEP,
                                      view_label="collar end", dimensions_by_feature=spec.DRAWING_DIMENSIONS)
    side_marks = curate_view_dimensions(adapter, side, keep=SIDE_KEEP,
                                       view_label="collar turning view", dimensions_by_feature=spec.DRAWING_DIMENSIONS)
    donors = [a for a in end_marks if dimension_name(adapter, a) == "CollarDia"]
    if len(donors) != 1:
        raise RuntimeError("collar end view has no single OD donor")
    moved = _move_od(adapter, donors[0], end, side)
    marks = [a for a in end_marks if dimension_name(adapter, a) != "CollarDia"] + side_marks + [moved]
    assert_imported_precision(adapter, marks, spec.DRAWING_PRECISION_BY_NAME)
    tap_marks = curate_view_dimensions(
        adapter, tap, keep=TAP_KEEP, view_label="collar radial process controls",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, tap_marks, spec.DRAWING_PRECISION_BY_NAME)
    _assert_functional_dimension_types(adapter, tap_marks)
    set_dimension_callouts(adapter, tap_marks, {"TapRootLimit": "TAP ROOT"})
    # Source geometry is asymmetric and the views are rotated: use the native
    # model-to-sheet transform rather than assuming the view's box centre is
    # the bore origin or that world +Y still projects vertically.
    def point(view, xyz_mm, label):
        return model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in xyz_mm), label=label,
        )

    tap_rim = point(
        tap, (spec.FLAT_DISTANCE, spec.TAP_STATION, spec.TAP_DRILL_DIA / 2.0),
        "collar tap outer mouth",
    )
    project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=end, position=(0.120, 0.210),
                attachment_xy=point(end, (spec.BORE_MODEL_DIA_MM / 2.0, 1.0, 0.0), "collar bore datum"),
            ),
            "datum:B": PmiDrawingPlacement(
                view=side, position=(0.168, 0.162),
                attachment_xy=point(side, (0.0, 0.0, spec.NOSE_DIA / 2.0 - spec.EDGE_BREAK), "collar south datum"),
            ),
            "datum:C": PmiDrawingPlacement(
                view=end, position=(0.126, 0.152),
                attachment_xy=point(end, (spec.FLAT_DISTANCE, spec.TAP_STATION, 0.0), "collar clock datum"),
            ),
            "radial_tap_position": PmiDrawingPlacement(
                view=tap, position=(0.250, 0.221), attachment_xy=tap_rim,
            ),
        },
        datums=spec.COLLAR_DATUMS, controls=spec.COLLAR_CONTROLS,
        label="collar retained dog and wall position",
    )
    # In the radial projection the tap mouth is a real circle on the flat.
    callout = add_native_hole_callout(
        adapter, tap,
        edge_xy=tap_rim,
        callout_xy=(0.250, 0.245), label="custom collar blind set screw tap",
    )
    set_hole_callout_precision(callout, {
        "hw-tapdrldepth": spec.TAP_DEPTH_PRECISION,
        "hw-threaddepth": spec.TAP_DEPTH_PRECISION,
    }, label="collar tap drill and full thread depths")
    _require_full_thread_callout(callout)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.080)
    add_property_linked_note(adapter, "Installation Notes", 0.016, 0.048)
    add_property_linked_note(adapter, "Isometric View Note", 0.310, 0.160)
    add_property_linked_note(adapter, "Radial Tap View Note", 0.169, 0.212)
    _bore_view(adapter)

    if not ddoc.ActivateSheet("SetScrew"):
        raise RuntimeError("cannot activate ground screw sheet")
    screw = place_view(adapter, str(SOURCE), "*Front", *SCREW_CENTER, scale=(20, 1))
    screw_end = place_view(adapter, str(SOURCE), "*Right", 0.305, SCREW_CENTER[1], scale=(20, 1))
    screw_iso = place_view(adapter, str(SOURCE), "*Isometric", 0.345, 0.235, scale=(2, 1))
    _configuration(adapter, (screw, screw_end, screw_iso), "SetScrew")
    for view in (screw, screw_end, screw_iso):
        set_hidden_lines_removed(adapter, view)
    marks = curate_view_dimensions(adapter, screw, keep=SCREW_KEEP,
                                  view_label="ground stock screw", dimensions_by_feature=spec.DRAWING_DIMENSIONS)
    assert_imported_precision(adapter, marks, spec.DRAWING_PRECISION_BY_NAME)
    # Above the value: the freed lane where the old break dimension stood.
    set_dimension_callouts(adapter, marks, {"DogDia": spec.DOG_EDGE_CALLOUT}, location="above")
    project_part_pmi(
        adapter,
        placements={
            "datum:D": PmiDrawingPlacement(
                view=screw, position=(0.203, 0.203),
                attachment_xy=point(
                    screw,
                    (spec.SET_SCREW_SEAT_RADIUS + spec.DOG_LENGTH + 1.0,
                     spec.TAP_STATION + spec.SET_SCREW_MAJOR_DIA / 2.0, 0.0),
                    "retained stock thread datum",
                ),
            ),
            "ground_dog_runout": PmiDrawingPlacement(
                view=screw, position=(0.046, 0.161),
                attachment_xy=point(
                    screw,
                    (spec.SET_SCREW_SEAT_RADIUS + spec.DOG_LENGTH / 2.0,
                     spec.TAP_STATION + spec.DOG_DIA / 2.0, 0.0),
                    "ground dog runout face",
                ),
            ),
        },
        datums=spec.SCREW_DATUMS, controls=spec.SCREW_CONTROLS,
        label="ground dog relative to retained stock thread",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.080)
    add_property_linked_note(adapter, "Isometric View Note", 0.310, 0.210)
    for sheet in SHEET_NAMES:
        if not ddoc.ActivateSheet(sheet):
            raise RuntimeError(f"cannot audit collar package sheet {sheet}")
        rebuild_drawing(adapter, label=f"collar {sheet} layout audit")
        findings = audit_document(adapter)
        if findings:
            raise RuntimeError("collar manufacturing layout:\n" + format_findings(findings))
    return await finalize_drawing(
        adapter, OUTPUTS, pdf_title="Cone Tip Collar Manufacturing Drawing",
        scale=SHEET_SCALES["Collar"], layout=SPEC.layout, sheet_scales=SHEET_SCALES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
