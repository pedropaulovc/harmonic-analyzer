r"""Create the manufacturing drawing for the transgear arm (MHA-PD-18).

The principal view is ``*Front``, looking at the REAR face: the outline (the
pivot radius, the tip station and the end-face width), the pivot bore, the
MHA-PD-23 pin's reamed press bore, the plate-tap callout with its qualifier
lines, and the hole stations from the pivot (the blanked
``StationReference`` sketch, shown in this view only). The plate-tap stations
follow the reducer's knob bore through ``pd_transgear_arm_geometry``; neither
their imported dimensions nor the annotation picks fix a previous centre.
Section A-A cuts it on the centreline -- through the pivot, every hole and the
latch-pin hole -- so the rear spot face's diameter, its floor from the FRONT
face (the pivot spring's room under the head) and the latch-pin hole's depth print on
solid cut edges.  The end view (``*Right``, the square end) carries the
thickness (the ground stock's, printed as a reference to it) and the
latch-pin hole's reamed size, its height and the press of the pin to the
hole floor.  The matched locating sockets open in the rear face the front
view looks at, so their stations, size and position frames print there;
section B-B cuts them for their depth.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any, Callable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

import _config
from _check import check
from _com import _early_bound
from _drawing_annotation_extent import require_clear, require_inside, sheet_region
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
    set_reference_dimensions,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import visible_view_entities
from _drawing_gdt import PmiDrawingPlacement, project_part_pmi
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_leader_notes import add_attached_note
from _drawing_leaders import section_line_segments
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _native_projected_zone import require_saved_projected_gtols
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pd_paper_drive_assembly_steps import matched_locator_notes
from pd_transgear_arm_geometry import (
    LOCATOR_SITES_MM,
    LOCATOR_HOLE_DIA_MM,
    PIN_HOLE_DEPTH,
    PIN_BORE_DIA,
    PIN_STATION,
    PIVOT_END_R,
    PLATE_TAP_SPEC,
    PLATE_TAP_STATIONS,
    THICKNESS,
    TIP_STATION,
)
from pd_transgear_arm_plate_geometry import BORE_DIA as KNOB_BORE_DIA
from pd_transgear_arm_plate_spec import BORE_PLACES as KNOB_BORE_PLACES
from pd_transgear_arm_spec import (
    GEOMETRIC_CONTROLS,
    PLATE_PROJECTED_ZONE_CALLOUT,
    PIN_PROJECTED_ZONE_CALLOUT,
    LOCATOR_DEPTH_CALLOUT,
    PART_DATUMS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FLOOR_DEPTH_CALLOUT,
    ISO_VIEW_SCALE,
    OVERALL_LENGTH,
    PIN_BORE_DIA_PLACES,
    PIN_BORE_CALLOUT,
    LOCATOR_CALLOUT,
    PIN_HOLE_CALLOUT,
    PIVOT_BORE_CALLOUT,
    PLATE_TAP_EDGE_BREAK_CALLOUT,
    SPOT_FACE_CALLOUT,
    STOCK_TEXT_PREFIX,
    STOCK_TEXT_SUFFIX,
    engagement_line,
)
import transgear_hanger_joints as joints


SPEC = DRAWINGS_BY_NAME["pd_transgear_arm"]
SHEET_NAMES = ("Geometry", "Projected zones")
# Full attached-note extents must clear each other and the title block.
# Separate rows preserve both true tap attachments without shortened wording.
PROJECTED_TAP_NOTE_POSITIONS = ((0.200, 0.200), (0.200, 0.180))
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

# The arm is 141 mm long: 2:1 spans 0.283 m of the landscape sheet, with the
# section A-A under it and the end view and isometric to its right, clear of
# the title block (x > 0.216 below y 0.066).  The front view's box centres
# at x 0.189 so the section's floor-depth text, hanging left of its
# dimension line under the pivot end, keeps inside the left border
# (machinist reviews of 19e33c6c2 and 8b5e1f354: at 0.178 it reached x 1.5
# mm).  The end view moves 2 mm with it, so the 14.0 keeps clear of it.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.189, 0.205)
# Low enough that the counterbore callout above the section clears the
# overall-length reference under the station stack.
SECTION_CENTER = (FRONT_CENTER[0], 0.094)
END_CENTER = (0.357, FRONT_CENTER[1])
# Bottom left between the notes and the title block, under section A-A's
# label: the right column holds the end view, its pin callout and section
# B-B (run 20261010T001620278Z: B-B's label printed on the isometric).
ISO_CENTER = (0.184, 0.037)
ISO_NOTE_XY = (0.080, 0.022)
# This is a locator-feature callout, not a general note block. The shared
# emitter retains the original S-K setting, acceptance and numbered step refs.
# K is the actual knob bore on the plate, not a tap/locator station or the
# arm's longitudinal X projection of the true centre distance.
LOCATOR_MATCH_XY = (0.014, 0.202)
LOCATOR_MATCH_TEXT = "\n".join((
    f"S-K: ACTUAL Ø{KNOB_BORE_DIA:.{KNOB_BORE_PLACES}f} KNOB-BORE K TO "
    f"Ø{PIN_BORE_DIA:.{PIN_BORE_DIA_PLACES}f} PIN-BORE S;",
    "NOT TAP / LOCATOR STATION OR ALONG-ARM X.",
    matched_locator_notes(
        _config.parts("pd-transgear-arm")["number"],
        "TRANSGEAR ARM PLATE " + _config.parts("pd-transgear-arm-plate")["number"],
        on_arm=True,
        width=62,
    ),
))
# Under the end view's pin callout and on its axis; its label clears the
# title block and section A-A's 8.50.  The socket mouths face right, and the
# column right of them holds the sockets' position frames inside the border.
LOCATOR_SECTION_CENTER = (END_CENTER[0], 0.120)
# The front view centres on the outline's bounding box (x -R .. tip).
_BBOX_CENTER_X = (TIP_STATION - PIVOT_END_R) / 2.0


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X station in the front view and section A-A."""
    return FRONT_CENTER[0] + (model_x_mm - _BBOX_CENTER_X) * _S / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y offset in the front view."""
    return FRONT_CENTER[1] + model_y_mm * _S / 1000.0


def _end_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z height in the end view (*Right: sheet right = -Z)."""
    return END_CENTER[0] - (model_z_mm - THICKNESS / 2.0) * _S / 1000.0


def _end_y(model_y_mm: float) -> float:
    return END_CENTER[1] + model_y_mm * _S / 1000.0


# Across the front view on the centreline: the cut is the Top plane, the
# plane of the spot-face profile, through every hole.
SECTION_LINE_OVERRUN = 0.005
SECTION_LINE = (
    (_front_x(-PIVOT_END_R) - SECTION_LINE_OVERRUN, FRONT_CENTER[1]),
    (_front_x(TIP_STATION) + SECTION_LINE_OVERRUN, FRONT_CENTER[1]),
)

# Per-view survivors of the marked-dimension import.  The stations stack
# under the front view, nearest first, the overall reference under them;
# the callouts stand above it, the pin bore's below right.
_UNDER_FRONT = _front_y(-PIVOT_END_R)
STATION_PITCH = 0.009


def _station_row(index: int) -> float:
    return _UNDER_FRONT - 0.010 - index * STATION_PITCH


_LOCATOR_X = _front_x(LOCATOR_SITES_MM[0][0])
# Midway between plate tap 1's and the sockets' station witness lines.
_LOCATOR_OFFSET_X = (_front_x(PLATE_TAP_STATIONS[0]) + _LOCATOR_X) / 2.0
FRONT_KEEP = {
    # Lower left of the pivot round, clear of datum B's tag above it.
    "PivotEndR": (0.025, FRONT_CENTER[1] + 0.010),
    "PivotBoreDia": (0.060, _front_y(PIVOT_END_R) + 0.021),
    # The pin bore's Ø and its callout lines stand below right of the arm,
    # right of the station stack; the upper band holds the tap and locator
    # callouts.
    "PinBoreDia": (_front_x(PIN_STATION) + 0.056, _UNDER_FRONT - 0.024),
    "EndWidth": (_front_x(TIP_STATION) + 0.012, FRONT_CENTER[1]),
    "PlateTapStation1": (_front_x(PLATE_TAP_STATIONS[0] / 2.0), _station_row(0)),
    "LocatorX1": (_front_x(LOCATOR_SITES_MM[0][0] / 2.0), _station_row(1)),
    "PlateTapStation2": (_front_x(PLATE_TAP_STATIONS[1] / 2.0), _station_row(2)),
    "PinStation": (_front_x(PIN_STATION / 2.0), _station_row(3)),
    "TipStation": (_front_x(TIP_STATION / 2.0), _station_row(4)),
    # The socket offsets share one dimension line left of section line B,
    # their texts outside the arm: above its top edge, under the tap
    # callout's shelf, and below its bottom edge, between the plate tap's and
    # the socket's station witness lines (machinist review: inside the
    # silhouette they crowded the sockets and line B).
    "LocatorY1": (_LOCATOR_OFFSET_X, _front_y(PIVOT_END_R) + 0.0045),
    "LocatorY2": (_LOCATOR_OFFSET_X, _front_y(-PIVOT_END_R) - 0.0045),
    "LocatorDia1": (0.245, _front_y(PIVOT_END_R) + 0.021),
}
# The true overall (review of 19e33c6c2: the 128.90 from the bore axis read
# as one), a reference under the stations: picked on the pivot round's upper
# flank and re-anchored to its far extreme, and on the square end.
OVERALL_TEXT_XY = (FRONT_CENTER[0], _station_row(5))
_FLANK = PIVOT_END_R * math.sqrt(0.5)
OVERALL_PICKS = (
    (_front_x(-_FLANK), _front_y(_FLANK)),
    (_front_x(TIP_STATION), _front_y(3.0)),
)
# The floor depth's text stands BELOW the section's pivot end, outside its
# witness lines, where it hangs LEFT of the dimension line (away from the
# part, right edge on the line): the line runs 2 mm off the pivot end.
# The spot face's callout stands low enough to clear the overall reference,
# which moved down a row when the locator station joined the stack.
SECTION_KEEP = {
    "SpotFaceDia": (_front_x(0.0), SECTION_CENTER[1] + 0.020),
    "FloorDepth": (_front_x(-PIVOT_END_R) - 0.002, SECTION_CENTER[1] - 0.020),
    "PinHoleDepth": (
        _front_x(TIP_STATION - PIN_HOLE_DEPTH / 2.0),
        SECTION_CENTER[1] - 0.020,
    ),
}
# Each narrow depth's text stands right of its witness lines and outside
# its view (run 20261010T001620278Z: inside them, the witness lines and the
# view edges struck the text).
LOCATOR_SECTION_KEEP = {
    "LocatorDepth": (LOCATOR_SECTION_CENTER[0] + 0.027, 0.0935),
}
END_KEEP = {
    "Depth": (END_CENTER[0], _end_y(PIVOT_END_R) + 0.017),
    # Between the end view and the stock text, right of the front face.
    "PinHoleZ": (_end_x(0.0) + 0.017, _end_y(PIVOT_END_R) + 0.006),
    # Below the end view, above section B-B, right edge inside the border.
    "PinHoleDia": (0.384, 0.162),
}

# Text shelves are distinct from the unchanged dimension/witness positions.
# FloorDepth's longest functional line hangs left: put its entire box to the
# right of the original dimension line and below the section, inside the border.
DIMENSION_TEXT_POSITIONS = {
    "FloorDepth": (0.115, SECTION_CENTER[1] - 0.024),
    "LocatorY2": (_LOCATOR_OFFSET_X - 0.012, _UNDER_FRONT - 0.005),
    "Depth": (END_CENTER[0] + 0.009, _end_y(PIVOT_END_R) + 0.024),
}


DIMENSION_CALLOUTS = {
    "PivotBoreDia": PIVOT_BORE_CALLOUT,
    "PinBoreDia": PIN_BORE_CALLOUT,
    "SpotFaceDia": SPOT_FACE_CALLOUT,
    "FloorDepth": FLOOR_DEPTH_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "LocatorDia1": LOCATOR_CALLOUT,
    "LocatorDepth": LOCATOR_DEPTH_CALLOUT,
}

# Native tap callout: arrow on the rear entry break's own edge, text above
# the view with its top inside the upper border. It carries the ordinary
# entry/exit edge-break limit and the mating cut screw's worst-case full-
# thread engagement. The joint source pays entry loss and the overlapping
# exit/cut-end loss separately; screws do not locate or centre this joint.
_PLATE_DRILL_R = blind_cut_dia_mm(PLATE_TAP_SPEC) / 2.0
# Reserve one more qualifier line for the source engagement reason without
# letting the complete native callout reach the upper border.
_CALLOUT_Y = _front_y(PIVOT_END_R) + 0.0202
# Between the pivot bore's callout and the locator's, above section label B.
PLATE_CALLOUT_XY = (0.160, _CALLOUT_Y)
PLATE_TAP_QUALIFIER = "\n".join(
    (
        PLATE_TAP_EDGE_BREAK_CALLOUT,
        engagement_line(
            joints.PLATE_SCREW_ENGAGEMENT_WORST, joints.PLATE_SCREW_ENGAGEMENT_WORST_D
        ),
    )
)
TAP_CALLOUTS = (
    (
        "plate taps",
        PLATE_TAP_STATIONS[0],
        _PLATE_DRILL_R,
        PLATE_CALLOUT_XY,
        PLATE_TAP_QUALIFIER,
    ),
)


def _overall_reference(adapter: Any, front: Any) -> None:
    overall = add_edge_dimension(
        adapter,
        front,
        p0=OVERALL_PICKS[0],
        p1=OVERALL_PICKS[1],
        text_xy=OVERALL_TEXT_XY,
        label="overall length reference",
        orientation="horizontal",
    )
    set_arc_endpoints_to_max(adapter, overall, label="overall length reference")
    display = _early_bound(overall, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL_LENGTH) > 1e-5:
        raise RuntimeError(
            f"overall length reference measured {measured_mm:g}, "
            f"expected {OVERALL_LENGTH:g} mm"
        )
    set_reference_dimension(
        adapter, display.GetAnnotation(), label="overall length reference"
    )
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("overall length reference precision did not persist")


def _rear_rim(view: Any, *, radius_mm: float, station_mm: float, label: str, offset_mm: float = 0.0) -> Any:
    """The tap-drill rim nearest the rear face, by radius and station.

    Looking down a through hole both drill rims project to one circle; the
    rear one (largest z) is the one the viewer sees at the mouth's foot.
    """
    rims: list[tuple[float, Any]] = []
    nearest_miss = float("inf")
    for raw_edge in visible_view_entities(view, 1, label=f"{label} rims"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        raw_params = curve.CircleParams
        if raw_params is None:
            raise RuntimeError(f"{label}: native circle parameters are NULL")
        params = tuple(float(value) * 1000.0 for value in raw_params)
        if len(params) != 7 or not all(map(math.isfinite, params)):
            raise RuntimeError(f"{label}: native circle parameters are not seven finite values")
        miss = abs(params[6] - radius_mm) + abs(params[0] - station_mm) + abs(params[1] - offset_mm)
        nearest_miss = min(nearest_miss, miss)
        if miss <= 0.02:
            rims.append((params[2], edge))
    if not rims:
        raise RuntimeError(
            f"{label}: no drill rim R{radius_mm:.3f} at x {station_mm:.3f}; "
            f"nearest circle misses by {nearest_miss:.3f} mm"
        )
    return max(rims, key=lambda item: item[0])[1]


def _rim_point(
    adapter: Any, view: Any, *, station_mm: float, radius_mm: float,
    bearing_deg: float, label: str, offset_mm: float = 0.0,
) -> tuple[float, float]:
    """Sheet point on a bore's rear rim at a model bearing."""
    angle = math.radians(bearing_deg)
    return model_point_in_view(
        adapter, view,
        (
            (station_mm + radius_mm * math.cos(angle)) / 1000.0,
            (offset_mm + radius_mm * math.sin(angle)) / 1000.0,
            THICKNESS / 1000.0,
        ),
        label=label,
    )


def _wall_point(
    adapter: Any, view: Any, *, x_mm: float, z_mm: float, label: str
) -> tuple[float, float]:
    """Sheet point on a centreline hole's wall in section A-A."""
    return model_point_in_view(
        adapter, view, (x_mm / 1000.0, 0.0, z_mm / 1000.0), label=label
    )


# Position frames on the locating sockets stand in section B-B, which cuts
# both on their axes, right of the socket mouths and each on its socket's side
# of the arm's centre (machinist review: in the front view they sat inside
# the silhouette).  Each leader enters its socket's mouth and lands on the
# wall nearer the centre 1 mm in, as section A-A's tap frames do.
_LOCATOR_MOUTH_X = LOCATOR_SECTION_CENTER[0] + THICKNESS / 2.0 * _S / 1000.0
_LOCATOR_FRAME_GAP = 0.006
_LOCATOR_FRAME_RISE = 0.0025
_FRAME_HALF_HEIGHT = 0.00345


def _locator_frame_xy(offset_mm: float) -> tuple[float, float]:
    """Top-left of a socket's position frame in section B-B."""
    side = math.copysign(1.0, offset_mm)
    centre_y = (
        LOCATOR_SECTION_CENTER[1] + offset_mm * _S / 1000.0 + side * _LOCATOR_FRAME_RISE
    )
    return (_LOCATOR_MOUTH_X + _LOCATOR_FRAME_GAP, centre_y + _FRAME_HALF_HEIGHT)


def tap_callout_definitions(
    definitions: dict[int, str], qualifier: str
) -> dict[int, str]:
    """Drop the title-block thread class from the thread compartment and
    append the qualifier lines under it; every other compartment and every
    associative Hole Wizard variable stays."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(
            f"tap thread line is not in one callout part: {definitions!r}"
        )
    part = thread_parts[0]
    without_class = re.sub(
        r"\s*(?:-\s*)?<hw-threadclass>\s*", " ", definitions[part], flags=re.IGNORECASE
    )
    without_class = re.sub(r" {2,}", " ", without_class).rstrip()
    updated = dict(definitions)
    updated[part] = f"{without_class}\n{qualifier}"
    return updated


def _set_tap_callout_text(display: Any, qualifier: str, *, label: str) -> None:
    native = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = tap_callout_definitions(definitions, qualifier)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(native.GetText(part) or "") for part in (1, 2, 3, 4)}
    if persisted != updated or not any(
        text.rstrip().endswith(qualifier) for text in resolved.values()
    ):
        raise RuntimeError(
            f"{label} qualifier lines did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


def _set_stock_text(adapter: Any, annotations: list[Any]) -> None:
    """Print the thickness as the stock's: "5/16 (7.94) GROUND STOCK".

    The arm is cut from 5/16 ground flat stock with its faces as supplied, so
    the stock's tolerance governs the thickness, not the .XX row.  Prefix and
    suffix, not a whole-text override: the value between them stays the
    model's dimension at its model-owned places, and the parentheses mark it
    as reference (the rocker thrust washer's idiom).
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != "Depth":
            continue
        annotation = _early_bound(annotation, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - THICKNESS / 1000.0) > 1e-9:
            raise RuntimeError(
                f"arm thickness {float(dimension.SystemValue)!r} m "
                f"is not the stock's {THICKNESS} mm"
            )
        display.SetText(1, STOCK_TEXT_PREFIX)  # swDimensionTextPrefix
        display.SetText(2, STOCK_TEXT_SUFFIX)  # swDimensionTextSuffix
        readback = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        if readback != (STOCK_TEXT_PREFIX, STOCK_TEXT_SUFFIX):
            raise RuntimeError(f"arm stock text did not persist: {readback!r}")
        rebuild_drawing(adapter, label="arm stock thickness text")
        return
    raise RuntimeError("arm end view has no Depth dimension to label")


def _projected_axis_graphics(adapter: Any, section: Any) -> None:
    """Draw source-length chains in a view sketch, not in the physical part."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate arm projected-axis section")
    sketch = _early_bound(section.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    zones = [
        (f"plate_tap_{index}_position", station, 1.0)
        for index, station in enumerate(PLATE_TAP_STATIONS, 1)
    ]
    zones.append(("feed_stud_projected_axis", PIN_STATION, -1.0))
    controls = {control.name: control for control in GEOMETRIC_CONTROLS}
    for label, station, direction in zones:
        height = controls[label].projected_zone_height_mm
        if height is None:
            raise RuntimeError(f"arm {label} has no native projected height")
        draw.ClearSelection2(True)
        ends = model_points_in_view(
            adapter, section,
            [(station / 1000.0, 0.0, 0.0),
             (station / 1000.0, 0.0, direction * height / 1000.0)],
            label=f"{label} projected axis", names=("front face A", "zone end"),
        )
        points = []
        for x, y in ends:
            point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
            projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
            points.append(tuple(float(value) for value in projected.ArrayData))
        # Established view-owned centreline pattern: bypass inference snaps,
        # restore AddToDB, then prove both projected endpoints and black ink.
        previous_add_to_db = bool(manager.AddToDB)
        manager.AddToDB = True
        try:
            segment = manager.CreateCenterLine(*points[0], *points[1])
        finally:
            manager.AddToDB = previous_add_to_db
        if segment is None:
            raise RuntimeError(f"failed to create arm {label} projected axis")
        line = _early_bound(segment, "ISketchLine")
        for expected, accessor in zip(points, ("GetStartPoint2", "GetEndPoint2")):
            placed = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
            actual = [float(adapter._get_attr_or_call(placed, axis)) for axis in "XYZ"]
            if max(abs(a - b) for a, b in zip(actual, expected)) > 1e-9:
                raise RuntimeError(f"arm {label} projected-axis endpoint moved")
        segment = _early_bound(segment, "ISketchSegment")
        segment.Color = 0
        if int(segment.Color) != 0:
            raise RuntimeError(f"arm {label} projected-axis color did not persist")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="arm source projected axes")


def _projection_sheet(adapter: Any) -> Callable[[], None]:
    """Separate chains from sheet 1's station stack without shortening zones.

    The supplemental section has no imported dimensions: the native FCFs on
    sheet 1 remain the numerical controls. At 2:1 the complete forward pin
    chain fits between this section and its parent front view.
    """
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate arm projected-zone sheet")
    # Lower the parent front as well as the caption: its top silhouette must
    # not occupy the caption's lane inside the upper zone frame.
    front_center = (FRONT_CENTER[0], 0.230)
    # Leave the complete projected-axis outline below the matched callout,
    # not just its actual chain ink to the right of that callout.
    section_center = (FRONT_CENTER[0], 0.090)
    front = place_view(adapter, str(SOURCE), "*Front", *front_center, scale=VIEW_SCALE)
    section = create_section_view(
        adapter, front,
        line_start=(SECTION_LINE[0][0], front_center[1]),
        line_end=(SECTION_LINE[1][0], front_center[1]),
        view_xy=section_center, section_label="C", scale=VIEW_SCALE,
        label="arm projected axes section",
    )
    for view in (front, section):
        set_hidden_lines_removed(adapter, view)
    _projected_axis_graphics(adapter, section)
    if not drawing.ActivateView(""):
        raise RuntimeError("failed to activate projected-zone sheet caption")
    caption = add_note(adapter, "PROJECTED ZONES — CONTROLS ON SHEET 1", 0.100, 0.263)
    if caption is None:
        raise RuntimeError("failed to add arm projected-zone caption")
    notes: list[tuple[str, Any, bool]] = [("projection caption", caption, False)]
    # Stagger the tap labels to the right of the matched-locator block, in
    # the gap between both view outlines. Arrows still name their own taps.
    for index, station in enumerate(PLATE_TAP_STATIONS, 1):
        note = add_attached_note(
            adapter, section, text=PLATE_PROJECTED_ZONE_CALLOUT,
            entity_xy=_wall_point(
                adapter, section, x_mm=station + _PLATE_DRILL_R,
                z_mm=THICKNESS - 1.0, label=f"tap {index} zone direction wall",
            ),
            note_xy=PROJECTED_TAP_NOTE_POSITIONS[index - 1],
            label=f"tap {index} projected zone direction",
        )
        notes.append((f"tap {index} projected zone direction", note, True))
    pin_r = next(datum.face.diameter_mm / 2.0 for datum in PART_DATUMS if datum.letter == "C")
    note = add_attached_note(
        adapter, section, text=PIN_PROJECTED_ZONE_CALLOUT,
        entity_xy=_wall_point(
            adapter, section, x_mm=PIN_STATION + pin_r, z_mm=1.0,
            label="pin projected zone direction wall",
        ),
        note_xy=(0.300, 0.180),
        label="pin projected zone direction",
    )
    notes.append(("pin projected zone direction", note, True))
    # This actual locator rim is on the uncluttered supplemental front view;
    # its matched acceptance leader no longer crosses section A on sheet 1.
    note = add_attached_note(
        adapter, front, text=LOCATOR_MATCH_TEXT,
        entity=_rear_rim(
            front, radius_mm=LOCATOR_HOLE_DIA_MM / 2.0,
            station_mm=LOCATOR_SITES_MM[0][0], offset_mm=LOCATOR_SITES_MM[0][1],
            label="matched arm plate locator",
        ),
        note_xy=LOCATOR_MATCH_XY,
        label="arm plate matched locator acceptance",
    )
    notes.append(("arm plate matched locator acceptance", note, True))
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to restore arm geometry sheet")

    def require_settled_projection_notes() -> None:
        if not drawing.ActivateSheet(SHEET_NAMES[1]):
            raise RuntimeError("failed to activate arm projection-note extent check")
        try:
            region = sheet_region(adapter)
            view_boxes = {}
            for label, view in (("projection front", front), ("projection section C", section)):
                outline = tuple(float(value) for value in view.GetOutline() or ())
                if (
                    len(outline) != 4
                    or not all(math.isfinite(value) for value in outline)
                    or outline[0] >= outline[2]
                    or outline[1] >= outline[3]
                ):
                    raise RuntimeError(f"arm {label} has invalid native outline: {outline!r}")
                require_inside(f"arm {label}", outline, region)
                require_clear(f"arm {label}", outline, {
                    "title block": (0.216, region.ymin, region.xmax, 0.066),
                })
                require_clear(f"arm {label}", outline, view_boxes)
                view_boxes[label] = outline
            section_boxes = {}
            strokes = section_line_segments(adapter, front)
            if not strokes:
                raise RuntimeError("arm projected section has no native cutting-line strokes")
            for index, (start, end) in enumerate(strokes, 1):
                section_boxes[f"section C cutting stroke {index}"] = (
                    min(start[0], end[0]), min(start[1], end[1]),
                    max(start[0], end[0]), max(start[1], end[1]),
                )
            sections = tuple(front.GetSectionLines() or ())
            if not sections:
                raise RuntimeError("arm projected section has no native cutting-line labels")
            for index, raw_section in enumerate(sections, 1):
                native_section = _early_bound(raw_section, "IDrSection")
                label = str(native_section.GetLabel() or "")
                origins = tuple(float(value) for value in native_section.GetTextInfo() or ())
                text_format = _early_bound(native_section.GetTextFormat(), "ITextFormat")
                # The convenient metres property can be stale when points
                # own this text format. Read the declared authority only.
                height = (
                    float(text_format.CharHeightInPts) * 0.0254 / 72.0
                    if text_format.IsHeightSpecifiedInPts()
                    else float(text_format.CharHeight)
                )
                if (
                    not label or len(origins) != 6
                    or not all(math.isfinite(value) for value in origins)
                    or not math.isfinite(height) or height <= 0.0
                ):
                    raise RuntimeError("arm projected section label has invalid native text data")
                # Native origins and height, conservative one-em-per-letter
                # width. Exact glyph ink remains the vector-PDF layout gate's
                # job: IDrSection has no native glyph-width/bounding-box API.
                width = height * len(label)
                for end in range(2):
                    x, y = origins[end * 3:end * 3 + 2]
                    section_boxes[f"section C {index} label {end + 1}"] = (
                        x, y - height, x + width, y,
                    )
            boxes = {}
            for label, raw_note, attached in notes:
                native_note = _early_bound(raw_note, "INote")
                extent = tuple(float(value) for value in native_note.GetExtent() or ())
                if (
                    len(extent) != 6
                    or not all(math.isfinite(value) for value in extent)
                    or extent[0] >= extent[3]
                    or extent[1] >= extent[4]
                ):
                    raise RuntimeError(f"arm {label} has invalid native extent: {extent!r}")
                box = (extent[0], extent[1], extent[3], extent[4])
                _telemetry.info(f"arm {label} native text extent: {box!r}")
                require_inside(f"arm {label}", box, region)
                require_clear(f"arm {label}", box, {
                    "title block": (0.216, region.ymin, region.xmax, 0.066),
                })
                require_clear(f"arm {label}", box, view_boxes)
                require_clear(f"arm {label}", box, section_boxes)
                require_clear(f"arm {label}", box, boxes)
                boxes[label] = box
                if attached:
                    annotation = _early_bound(native_note.GetAnnotation(), "IAnnotation")
                    if (
                        int(annotation.GetAttachedEntityCount3()) != 1
                        or int(annotation.GetLeaderCount()) != 1
                        or bool(annotation.IsDangling())
                    ):
                        raise RuntimeError(f"arm {label} lost its single attached leader")
        finally:
            if not drawing.ActivateSheet(SHEET_NAMES[0]):
                raise RuntimeError("failed to restore arm geometry sheet after extent check")

    return require_settled_projection_notes


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-arm source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear arm; machined steel bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="transgear arm package"
    )
    drawing = _early_bound(drawing_model, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate arm geometry sheet")

    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="arm centreline section",
    )
    locator_x = _front_x(LOCATOR_SITES_MM[0][0])
    locator_section = create_section_view(
        adapter, front,
        line_start=(locator_x, _front_y(-PIVOT_END_R) - SECTION_LINE_OVERRUN),
        line_end=(locator_x, _front_y(PIVOT_END_R) + SECTION_LINE_OVERRUN),
        view_xy=LOCATOR_SECTION_CENTER, section_label="B", scale=VIEW_SCALE,
        label="matched locating sockets transverse section",
    )
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    for view in (front, section, locator_section, end, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *hidden_sketches.curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *hidden_sketches.curate_view_dimensions(
            adapter, locator_section, keep=LOCATOR_SECTION_KEEP,
            view_label="section B-B locating sockets", dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *hidden_sketches.curate_view_dimensions(
            adapter,
            end,
            keep=END_KEEP,
            view_label="end",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Decimal places and the explicit bands are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_reference_dimensions(adapter, annotations, ("PivotBoreDia",))
    _set_stock_text(adapter, annotations)
    # Offset ONLY the text: model dimension and witness/measurement stations
    # survive. These shelves clear the reported extension/centreline crossings.
    offset_dimension_text(adapter, annotations, DIMENSION_TEXT_POSITIONS)
    # Model-owned circular zones and actual feature datums. BASIC stations
    # are imported from the part; no drawing-only coordinate tolerances.
    bore_dia = {
        datum.letter: datum.face.diameter_mm
        for datum in PART_DATUMS if datum.letter != "A"
    }
    pin_r = bore_dia["C"] / 2.0
    placements = {
        "datum:A": PmiDrawingPlacement(
            section, (_front_x(22.0), SECTION_CENTER[1] + 0.018),
            attachment_xy=model_point_in_view(
                adapter, section, (0.022, 0.0, 0.0), label="arm front datum",
            ),
        ),
        # Datum tags on a bore are picked by a SHEET POINT on the rim
        # (solidworks-drawing-layout-tuning.md section h): an edge-object
        # pick leaves the tag at its default drop beside the bore, and run 5
        # read datum B 35.5 mm from its request.  The point is projected
        # from the rim's model position, on the bearing toward the tag.
        "datum:B": PmiDrawingPlacement(
            front, (_front_x(0.0) - 0.024, FRONT_CENTER[1] + 0.020),
            attachment_xy=_rim_point(
                adapter, front, station_mm=0.0, radius_mm=bore_dia["B"] / 2.0,
                bearing_deg=135.0, label="datum B pivot bore rim",
            ),
        ),
        "datum:C": PmiDrawingPlacement(
            front, (_front_x(PIN_STATION) + 0.018, FRONT_CENTER[1] - 0.009),
            attachment_xy=_rim_point(
                adapter, front, station_mm=PIN_STATION, radius_mm=bore_dia["C"] / 2.0,
                bearing_deg=-27.0, label="datum C pin bore rim",
            ),
        ),
        # Above the arm, landing on the pin bore's upper right rim, clear of
        # datum C's leader below it and of the locator frame left of it.
        "feed_stud_position": PmiDrawingPlacement(
            front, (_front_x(PIN_STATION) + 0.018, FRONT_CENTER[1] + 0.0285),
            attachment_xy=_rim_point(
                adapter, front, station_mm=PIN_STATION, radius_mm=pin_r,
                bearing_deg=50.0, label="feed stud position pin bore rim",
            ),
        ),
        # The projected-zone frames stand in section A-A on the side their
        # zone projects to (the plate taps' rear, the stud's front), each
        # leader entering the hole's mouth and landing on its wall 1 mm in.
        "plate_tap_1_position": PmiDrawingPlacement(
            section, (0.070, SECTION_CENTER[1] - 0.0094),
            attachment_xy=_wall_point(
                adapter, section, x_mm=PLATE_TAP_STATIONS[0] + _PLATE_DRILL_R,
                z_mm=THICKNESS - 1.0, label="plate tap 1 wall",
            ),
        ),
        "plate_tap_2_position": PmiDrawingPlacement(
            section, (0.178, SECTION_CENTER[1] - 0.0094),
            attachment_xy=_wall_point(
                adapter, section, x_mm=PLATE_TAP_STATIONS[1] - _PLATE_DRILL_R,
                z_mm=THICKNESS - 1.0, label="plate tap 2 wall",
            ),
        ),
        "feed_stud_projected_axis": PmiDrawingPlacement(
            section, (0.145, SECTION_CENTER[1] + 0.020),
            attachment_xy=_wall_point(
                adapter, section, x_mm=PIN_STATION + pin_r, z_mm=1.0,
                label="feed stud projected axis pin bore wall",
            ),
        ),
        "arm_rear_parallel": PmiDrawingPlacement(
            section, (0.279, SECTION_CENTER[1] - 0.014),
            attachment_xy=model_point_in_view(
                adapter, section, (0.098, 0.0, THICKNESS / 1000.0),
                label="actual rear mounting face parallelism",
            ),
        ),
        **{
            f"arm_locator_{index}_position": PmiDrawingPlacement(
                locator_section, _locator_frame_xy(y),
                attachment_xy=model_point_in_view(
                    adapter, locator_section,
                    (
                        x / 1000.0,
                        (y - math.copysign(LOCATOR_HOLE_DIA_MM / 2.0, y)) / 1000.0,
                        (THICKNESS - 1.0) / 1000.0,
                    ),
                    label=f"arm locator {index} inner wall",
                ),
            ) for index, (x, y) in enumerate(LOCATOR_SITES_MM, 1)
        },
    }
    project_part_pmi(
        adapter, placements=placements, datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS, label="transgear arm locating frame",
    )
    _overall_reference(adapter, front)
    for view, label in ((front, "front"), (end, "end")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME centre marks to the {label} view")

    # Thread and tap drill ride the native callouts; the class is the title
    # block's; the countersink and engagement lines are the qualifiers'.
    for label, station, radius, callout_xy, qualifier in TAP_CALLOUTS:
        callout = add_native_hole_callout(
            adapter,
            front,
            edge=_rear_rim(front, radius_mm=radius, station_mm=station, label=label),
            callout_xy=callout_xy,
            label=label,
        )
        _set_tap_callout_text(callout, qualifier, label=label)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    projection_note_check = _projection_sheet(adapter)

    artefacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Arm Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        settled_checks=(projection_note_check,),
        # SolidWorks pins its own "... Tapped Hole" note to the front view
        # once a tap carries a hole callout; the plate-tap callout already
        # states the thread and drill.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=len(TAP_CALLOUTS),
    )
    require_saved_projected_gtols(
        adapter, artefacts["drawing"], GEOMETRIC_CONTROLS,
        label="saved transgear arm drawing projected axes",
    )
    return artefacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
