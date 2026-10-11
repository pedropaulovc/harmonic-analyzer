"""Manufacturing drawing of the custom collar; its set screw is stock.

Native model dimensions own every made size, its places and its band.
The radial through tap is a native Hole Wizard callout.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
import vn_cone_tip_collar_spec as spec
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs, add_native_hole_callout,
    add_property_linked_note, assert_imported_precision,
    curate_view_dimensions, dimension_name, finalize_drawing,
    model_point_in_view, new_project_drawing,
    read_required_properties, rebuild_drawing,
    set_dimension_callouts, set_hidden_lines_removed,
    stamp_drawing_summary, view_name,
)
import _drawing_hidden_sketches as hidden_sketches
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import format_findings
from diagnostics.drawing_layout_audit import audit_document
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["vn_cone_tip_collar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png
SHEET_SCALE = (4, 1)
END_CENTER = (0.080, 0.170)
SIDE_CENTER = (0.205, 0.170)
# The radial tap view stands over the end view, left of the turning view.
# Over the turning view, at (205, 240) mm, its gauge dimensions crossed the
# top border by 3.2 and 8.8 mm, its note sat on NoseLength's lines, and the
# root gauge and position leaders ran through the hole callout (run 14 at
# 7fda4144f). Offsets below are from TAP_CENTER. The view spans +/-11.5 x
# +/-17.48 mm at 2:1. Run 14 put the tap mouth at (+3.3, +1.8) mm, the callout
# text at [-39, -1] x [-5.6, -2.1] mm from its callout point, and the view
# note's 62 x 4.3 mm box with its left/top corner at the note point.
TAP_CENTER = (0.065, 0.238)
TAP_SCALE = spec.RADIAL_TAP_VIEW_SCALE
ISO_CENTER = (0.345, 0.210)
END_KEEP = {"NoseDia": (0.027, 0.165), "FlatDistance": (0.080, 0.112)}
# CollarDia is a turned-profile sketch dimension, native to the side view.
SIDE_KEEP = {"CollarWidth": (0.205, 0.110), "CollarDia": (0.250, SIDE_CENTER[1]),
             "NoseLength": (0.182, 0.218), "ShoulderRadius": (0.282, 0.205)}
# TapStation reads under the view (above the end view's top, y 204 mm). The
# two-line TAP ROOT gauge reads level with the tap, left of the view; its
# leader runs straight through the circle.
TAP_KEEP = {
    "TapStation": (TAP_CENTER[0] - 0.021, TAP_CENTER[1] - 0.024),
    "TapRootLimit": (TAP_CENTER[0] - 0.030, TAP_CENTER[1]),
}
# Right of the view: the hole callout's text starting past the view's right
# edge. The view note goes over the view, 3.7 mm inside the top border.
TAP_CALLOUT_XY = (TAP_CENTER[0] + 0.0553, TAP_CENTER[1] - 0.0062)
TAP_NOTE_XY = (TAP_CENTER[0] - 0.030, TAP_CENTER[1] + 0.025)
# Between the turning view and the isometric, clear of the title block: at
# (350, 80) mm the 40:1 crop circle (radius 20.6 mm) ran 6.6 mm down into it,
# over the title text (run 16 at b760a440c). BoreDia reads up-right, clear
# of CollarDia's lower extension line (y 136 mm, x <= 251); the note under
# the circle, centred on it.
BORE_CENTER = (0.300, 0.110)
BORE_KEEP = {"BoreDia": (BORE_CENTER[0] + 0.035, BORE_CENTER[1] + 0.032)}
BORE_NOTE_XY = (BORE_CENTER[0] - 0.025, BORE_CENTER[1] - 0.026)


def bore_crop_radius_m() -> float:
    """Sheet radius of the 40:1 bore view's circular crop."""
    return spec.BORE_FINISHED_DIA_LIMITS_MM[1] * spec.BORE_VIEW_SCALE[0] / (
        2000.0 * spec.BORE_VIEW_SCALE[1]
    ) + 0.003


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


def _precision(keep):
    """The part-authored places of only the names this view keeps
    (main's per-view form, draw_ch_connecting_rod)."""
    return {name: spec.DRAWING_PRECISION_BY_NAME[name] for name in keep}


# Native tolerance types the part authors: MAX 6.
TAP_DIMENSION_TYPES = {"TapRootLimit": 6}
SIDE_DIMENSION_TYPES = {"ShoulderRadius": 6}


def _assert_functional_dimension_types(adapter, annotations, expected):
    observed = {}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in expected:
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            observed[name] = int(tolerance.Type)
    if observed != expected:
        raise RuntimeError(f"collar MAX dimensions lost native types: {observed}")


def _centre_view(adapter, view, model_mm, sheet_xy, *, label):
    """Move ``view`` so the model point ``model_mm`` lands on ``sheet_xy``."""
    view = _early_bound(view, "IView")
    model = tuple(value / 1000.0 for value in model_mm)
    at = model_point_in_view(adapter, view, model, label=label)
    position = tuple(float(value) for value in view.Position)
    if not view.SetViewPosition(double_array([
        position[i] + sheet_xy[i] - at[i] for i in range(2)
    ]), False):
        raise RuntimeError(f"cannot centre {label}")
    rebuild_drawing(adapter, label=f"{label} position")
    at = model_point_in_view(adapter, view, model, label=f"{label} readback")
    if math.dist(at, sheet_xy) > 1e-4:
        raise RuntimeError(f"{label} did not remain centred")


def _bore_view(adapter):
    """Native circular crop, using the existing cone/arbor drawing sequence."""
    view = _early_bound(place_view(
        adapter, str(SOURCE), "*Bottom", *BORE_CENTER, scale=spec.BORE_VIEW_SCALE,
    ), "IView")
    _configuration(adapter, (view,), "Collar")
    if tuple(float(value) for value in view.ScaleRatio) != tuple(spec.BORE_VIEW_SCALE):
        raise RuntimeError("collar bore view lost its source scale")
    _centre_view(adapter, view, (0.0, 0.0, 0.0), BORE_CENTER, label="collar bore axis")
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("cannot activate collar bore crop")
    before = tuple(float(value) for value in view.GetOutline())
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    radius = bore_crop_radius_m()
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
    assert_imported_precision(adapter, marks, _precision(BORE_KEEP))
    set_dimension_callouts(adapter, marks, {"BoreDia": "REAM THRU"})
    add_property_linked_note(adapter, "Bore View Note", *BORE_NOTE_XY)
    return view


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part missing: {SOURCE}")
    check("open custom collar", await adapter.open_model(str(SOURCE)))
    read_required_properties(adapter.currentModel, (
        "Number", "Revision", "Title", "Material Specification", "Finish",
        "Quantity", "Manufacturing Notes", "Isometric View Note",
        "Radial Tap View Note", "Bore View Note", "Installation Notes",
    ), required=("Number", "Material Specification", "Manufacturing Notes",
                 "Radial Tap View Note", "Bore View Note", "Installation Notes"))
    drawing, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
    )
    stamp_drawing_summary(adapter, drawing, {
        0: "Cone Tip Collar Manufacturing Drawing", 1: "Harmonic Analyzer hobby-machinist drawing",
        2: "Harmonic Analyzer Project", 3: "Custom steel collar and stock set screw",
        4: "Project-owned ASME B drawing standard",
    })
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=SHEET_SCALE)
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=SHEET_SCALE)
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
    marks = end_marks + side_marks
    assert_imported_precision(adapter, marks, _precision(END_KEEP | SIDE_KEEP))
    _assert_functional_dimension_types(adapter, side_marks, SIDE_DIMENSION_TYPES)
    # TapRootGauge is a blanked sketch: main's hidden-owner importer shows it
    # in this view for the import (draw_ch_rocker_arm_tl_pivot_screw).
    tap_marks = hidden_sketches.curate_view_dimensions(
        adapter, tap, keep=TAP_KEEP, view_label="collar radial process controls",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, tap_marks, _precision(TAP_KEEP))
    _assert_functional_dimension_types(adapter, tap_marks, TAP_DIMENSION_TYPES)
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
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.080)
    add_property_linked_note(adapter, "Installation Notes", 0.016, 0.048)
    add_property_linked_note(adapter, "Isometric View Note", 0.310, 0.160)
    add_property_linked_note(adapter, "Radial Tap View Note", *TAP_NOTE_XY)
    _bore_view(adapter)
    # In the radial projection the tap mouth is a real circle on the flat.
    add_native_hole_callout(
        adapter, tap,
        edge_xy=tap_rim,
        callout_xy=TAP_CALLOUT_XY, label="custom collar through set screw tap",
    )
    rebuild_drawing(adapter, label="collar layout audit")
    findings = audit_document(adapter)
    if findings:
        raise RuntimeError("collar manufacturing layout:\n" + format_findings(findings))
    return await finalize_drawing(
        adapter, OUTPUTS, pdf_title="Cone Tip Collar Manufacturing Drawing",
        scale=SHEET_SCALE, layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
