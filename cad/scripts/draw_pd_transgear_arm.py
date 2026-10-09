r"""Create the manufacturing drawing for the transgear arm (MHA-PD-018).

The principal view is ``*Front``, looking at the REAR face: the outline (the
pivot radius, the tip station and the end-face width), the pivot bore, the
MHA-PD-023 pin's reamed press bore, the plate-tap callout with its qualifier
lines, and the hole stations from the pivot (the blanked
``StationReference`` sketch, shown in this view only). The plate-tap stations
follow the reducer's knob bore through ``pd_transgear_arm_geometry``; neither
their imported dimensions nor the annotation picks fix a previous centre.
Section A-A cuts it on the centreline -- through the pivot, every hole and the
latch-pin hole -- so the rear spot face's diameter, its floor from the FRONT
face (the pivot head's end play) and the latch-pin hole's depth print on
solid cut edges.  The end view (``*Right``, the square end) carries the
thickness (the ground stock's, printed as a reference to it) and the
latch-pin hole's reamed size, its height and the press of the pin to the
hole floor.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
import transgear_hanger_joints as joints
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    PmiDrawingPlacement,
    assert_imported_precision,
    create_section_view,
    finalize_drawing,
    new_project_drawing,
    model_point_in_view,
    model_points_in_view,
    project_part_pmi,
    read_required_properties,
    rebuild_drawing,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    set_reference_dimensions,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _native_projected_zone import require_saved_projected_gtols
from _hole_spec import blind_cut_dia_mm
from pd_transgear_arm_geometry import (
    LOCATOR_SITES_MM,
    LOCATOR_HOLE_DIA_MM,
    PIN_HOLE_DEPTH,
    PIN_HOLE_Z,
    PIN_STATION,
    PIVOT_END_R,
    PLATE_TAP_SPEC,
    PLATE_TAP_STATIONS,
    THICKNESS,
    TIP_STATION,
)
from pd_transgear_arm_spec import (
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FLOOR_DEPTH_CALLOUT,
    ISO_VIEW_SCALE,
    OVERALL_LENGTH,
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
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pd_transgear_arm"]
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
ISO_CENTER = (0.370, 0.115)
ISO_NOTE_XY = (0.335, 0.080)
PIVOT_FIT_NOTE_XY = (0.014, 0.067)
REDUCER_POSITION_NOTE_XY = (0.014, 0.048)
NORMAL_INSPECTION_NOTE_XY = (0.215, 0.124)
CLAMP_AXIS_INSPECTION_NOTE_XY = (0.215, 0.138)
LOCATOR_SECTION_CENTER = (0.370, 0.155)
REAR_CENTER = (0.290, 0.265)
REAR_VIEW_SCALE = (1, 1)
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
# the callouts stand above it.
_UNDER_FRONT = _front_y(-PIVOT_END_R)
STATION_PITCH = 0.010
FRONT_KEEP = {
    "PivotEndR": (_front_x(-PIVOT_END_R) - 0.005, _front_y(PIVOT_END_R) + 0.012),
    "PivotBoreDia": (_front_x(0.0) - 0.002, _front_y(PIVOT_END_R) + 0.026),
    # The pin bore's Ø and its three callout lines stand above the arm, right
    # of the plate-tap callout and left of the end view; lower than the pivot
    # bore's, so its stacked +0.008 band keeps inside the upper border.
    "PinBoreDia": (_front_x(PIN_STATION) + 0.036, _front_y(PIVOT_END_R) + 0.018),
    "EndWidth": (_front_x(TIP_STATION) + 0.012, FRONT_CENTER[1]),
    "PlateTapStation1": (
        _front_x(PLATE_TAP_STATIONS[0] / 2.0),
        _UNDER_FRONT - STATION_PITCH,
    ),
    "PlateTapStation2": (
        _front_x(PLATE_TAP_STATIONS[1] / 2.0),
        _UNDER_FRONT - 2 * STATION_PITCH,
    ),
    "PinStation": (_front_x(PIN_STATION / 2.0), _UNDER_FRONT - 3 * STATION_PITCH),
    "TipStation": (_front_x(TIP_STATION / 2.0), _UNDER_FRONT - 4 * STATION_PITCH),
    "ReducerDeltaX": (_front_x((PIN_STATION + LOCATOR_SITES_MM[0][0]) / 2.0), _UNDER_FRONT - 0.005),
    "ReducerDeltaY": (0.018, FRONT_CENTER[1] - 0.025),
}
# The true overall (review of 19e33c6c2: the 128.90 from the bore axis read
# as one), a reference under the stations: picked on the pivot round's upper
# flank and re-anchored to its far extreme, and on the square end.
OVERALL_TEXT_XY = (FRONT_CENTER[0], _UNDER_FRONT - 5 * STATION_PITCH)
_FLANK = PIVOT_END_R * math.sqrt(0.5)
OVERALL_PICKS = (
    (_front_x(-_FLANK), _front_y(_FLANK)),
    (_front_x(TIP_STATION), _front_y(3.0)),
)
# The floor depth's text stands BELOW the section's pivot end, outside its
# witness lines, where it hangs LEFT of the dimension line (away from the
# part, right edge on the line): the line runs 2 mm off the pivot end.
SECTION_KEEP = {
    "SpotFaceDia": (_front_x(0.0), SECTION_CENTER[1] + 0.022),
    "FloorDepth": (_front_x(-PIVOT_END_R) - 0.002, SECTION_CENTER[1] - 0.020),
    "PinHoleDepth": (
        _front_x(TIP_STATION - PIN_HOLE_DEPTH / 2.0),
        SECTION_CENTER[1] - 0.020,
    ),
}
LOCATOR_SECTION_KEEP = {
    "LocatorDepth": (0.375, 0.128),
}
# The blind sockets open in the rear face (z = THICKNESS), which *Front looks
# at; *Back looks at z = 0 and hides them (farm run 20261009T214031408Z: no
# locator rim in the view). These are model XYZ millimetres, not curate's
# sheet XY metres; project through the actual locating view first.
REAR_TEXT_MODEL_MM = {
    "LocatorX1": (LOCATOR_SITES_MM[0][0] / 2.0, -22.0, THICKNESS),
    "LocatorY1": (LOCATOR_SITES_MM[0][0] - 15.0, LOCATOR_SITES_MM[0][1] / 2.0, THICKNESS),
    "LocatorY2": (LOCATOR_SITES_MM[1][0] - 15.0, LOCATOR_SITES_MM[1][1] / 2.0, THICKNESS),
    "LocatorDia1": (LOCATOR_SITES_MM[0][0] + 20.0, -18.0, THICKNESS),
}
END_KEEP = {
    "Depth": (END_CENTER[0], _end_y(PIVOT_END_R) + 0.010),
    "PinHoleZ": (_end_x(PIN_HOLE_Z / 2.0), _end_y(-PIVOT_END_R) - 0.010),
    # Absolute x: the callout's right edge sits 2 mm inside the right border.
    "PinHoleDia": (0.385, _end_y(0.0) + 0.018),
}


def _rear_dimension_positions(adapter: Any, rear: Any) -> dict[str, tuple[float, float]]:
    """Project the rear text anchors to curate's canonical sheet-XY pairs."""
    names = tuple(REAR_TEXT_MODEL_MM)
    positions = model_points_in_view(
        adapter,
        rear,
        [tuple(value / 1000.0 for value in xyz) for xyz in REAR_TEXT_MODEL_MM.values()],
        names=names,
        label="arm rear locating dimension text",
    )
    return dict(zip(names, positions, strict=True))


DIMENSION_CALLOUTS = {
    "PivotBoreDia": PIVOT_BORE_CALLOUT,
    "PinBoreDia": PIN_BORE_CALLOUT,
    "SpotFaceDia": SPOT_FACE_CALLOUT,
    "FloorDepth": FLOOR_DEPTH_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "LocatorDia1": LOCATOR_CALLOUT,
}

# Native tap callout: arrow on the rear entry break's own edge, text above
# the view with its top inside the upper border. It carries the ordinary
# entry/exit edge-break limit and the mating cut screw's worst-case full-
# thread engagement. The joint source pays entry loss and the overlapping
# exit/cut-end loss separately; screws do not locate or centre this joint.
_PLATE_DRILL_R = blind_cut_dia_mm(PLATE_TAP_SPEC) / 2.0
_CALLOUT_Y = _front_y(PIVOT_END_R) + 0.022
PLATE_CALLOUT_XY = (_front_x(PLATE_TAP_STATIONS[0]) + 0.016, _CALLOUT_Y)
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
    bearing_deg: float, label: str,
) -> tuple[float, float]:
    """Sheet point on a centreline bore's rear rim at a model bearing."""
    angle = math.radians(bearing_deg)
    return model_point_in_view(
        adapter, view,
        (
            (station_mm + radius_mm * math.cos(angle)) / 1000.0,
            radius_mm * math.sin(angle) / 1000.0,
            THICKNESS / 1000.0,
        ),
        label=label,
    )


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
            "Pivot Fit Inspection",
            "Reducer Position Inspection",
            "Arm Plate Normal Inspection",
            "Clamp Axis Inspection",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Pivot Fit Inspection",
            "Reducer Position Inspection",
            "Arm Plate Normal Inspection",
            "Clamp Axis Inspection",
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
    rear = place_view(adapter, str(SOURCE), "*Front", *REAR_CENTER, scale=REAR_VIEW_SCALE)
    if add_note(
        adapter, f"REAR LOCATING VIEW ({REAR_VIEW_SCALE[0]}:{REAR_VIEW_SCALE[1]})",
        0.215, 0.279,
    ) is None:
        raise RuntimeError("failed to label the actual rear locating inspection view scale")
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    for view in (front, section, locator_section, rear, end, iso):
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
            adapter, rear, keep=_rear_dimension_positions(adapter, rear),
            view_label="rear locating inspection",
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
    # Model-owned circular zones and actual feature datums. BASIC stations
    # are imported from the part; no drawing-only coordinate tolerances.
    bore_dia = {
        datum.letter: datum.face.diameter_mm
        for datum in PART_DATUMS if datum.letter != "A"
    }
    pin_rim = _rear_rim(
        front, radius_mm=bore_dia["C"] / 2.0, station_mm=PIN_STATION,
        label="datum C pin bore",
    )
    placements = {
        "datum:A": PmiDrawingPlacement(
            section, (_front_x(35.0), SECTION_CENTER[1] + 0.035),
            attachment_xy=model_point_in_view(
                adapter, section, (0.035, 0.0, 0.0), label="arm front datum",
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
        "feed_stud_position": PmiDrawingPlacement(
            front, (_front_x(PIN_STATION) + 0.018, FRONT_CENTER[1] + 0.020),
            edge_entity=pin_rim,
        ),
        **{
            f"plate_tap_{index}_position": PmiDrawingPlacement(
                front, (_front_x(station) - 0.040, FRONT_CENTER[1] + 0.010 * index),
                edge_entity=_rear_rim(
                    front, radius_mm=_PLATE_DRILL_R, station_mm=station,
                    label=f"plate tap {index} position",
                ),
            )
            for index, station in enumerate(PLATE_TAP_STATIONS, 1)
        },
        "feed_stud_projected_axis": PmiDrawingPlacement(
            front, (_front_x(PIN_STATION) + 0.045, FRONT_CENTER[1] - 0.025),
            edge_entity=pin_rim,
        ),
        "arm_rear_parallel": PmiDrawingPlacement(
            section, (0.245, SECTION_CENTER[1] - 0.025),
            attachment_xy=model_point_in_view(
                adapter, section, (0.040, 0.0, THICKNESS / 1000.0),
                label="actual rear mounting face parallelism",
            ),
        ),
        **{
            f"arm_locator_{index}_position": PmiDrawingPlacement(
                rear, model_point_in_view(
                    adapter, rear, ((x - 27.0) / 1000.0, (y + math.copysign(7.0, y)) / 1000.0, THICKNESS / 1000.0),
                    label=f"rear locator {index} position frame",
                ),
                edge_entity=_rear_rim(
                    rear, radius_mm=LOCATOR_HOLE_DIA_MM / 2.0,
                    station_mm=x, offset_mm=y, label=f"arm locator {index}",
                ),
            ) for index, (x, y) in enumerate(LOCATOR_SITES_MM, 1)
        },
    }
    project_part_pmi(
        adapter, placements=placements, datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS, label="transgear arm locating frame",
    )
    _overall_reference(adapter, front)
    for view, label in ((front, "front"), (rear, "rear"), (end, "end")):
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
    add_property_linked_note(adapter, "Pivot Fit Inspection", *PIVOT_FIT_NOTE_XY)
    add_property_linked_note(
        adapter, "Reducer Position Inspection", *REDUCER_POSITION_NOTE_XY,
    )
    add_property_linked_note(
        adapter, "Arm Plate Normal Inspection", *NORMAL_INSPECTION_NOTE_XY,
    )
    add_property_linked_note(
        adapter, "Clamp Axis Inspection", *CLAMP_AXIS_INSPECTION_NOTE_XY,
    )

    artefacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Arm Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
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
