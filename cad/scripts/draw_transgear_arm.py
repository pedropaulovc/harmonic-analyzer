r"""Create the manufacturing drawing for the transgear arm (MHA-164).

The principal view is ``*Front``, looking at the REAR face: the outline (the
pivot radius, the tip station and the end-face width), the pivot bore, both
tap callouts with their countersinks, and the tap stations from the pivot
(the blanked ``StationReference`` sketch, shown in this view only).  Section
A-A cuts it on the centreline -- through the pivot, every tap and the
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
import transgear_stud_fit as stud_fit
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    create_section_view,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from transgear_arm_geometry import (
    PIN_HOLE_DEPTH,
    PIN_HOLE_Z,
    PIVOT_END_R,
    PLATE_TAP_SPEC,
    PLATE_TAP_STATIONS,
    STUD_STATION,
    STUD_TAP_SPEC,
    THICKNESS,
    TIP_STATION,
)
from transgear_arm_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FLOOR_DEPTH_CALLOUT,
    ISO_VIEW_SCALE,
    OVERALL_LENGTH,
    PIN_HOLE_CALLOUT,
    PIVOT_BORE_CALLOUT,
    PLATE_TAP_CSK_CALLOUT,
    SPOT_FACE_CALLOUT,
    STOCK_TEXT_PREFIX,
    STOCK_TEXT_SUFFIX,
    STUD_TAP_CSK_CALLOUT,
    engagement_line,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["transgear_arm"]
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
# the title block (x > 0.216 below y 0.066).  The front view stands 10 mm
# right of centre so the section's floor-depth text, under its pivot end,
# keeps clear of the left border (machinist review of 19e33c6c2: centred,
# the counterbore text crossed it).
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.178, 0.205)
# Low enough that the counterbore callout above the section clears the
# overall-length reference under the station stack.
SECTION_CENTER = (FRONT_CENTER[0], 0.094)
END_CENTER = (0.355, FRONT_CENTER[1])
ISO_CENTER = (0.370, 0.115)
ISO_NOTE_XY = (0.335, 0.080)
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
    "EndWidth": (_front_x(TIP_STATION) + 0.012, FRONT_CENTER[1]),
    "PlateTapStation1": (
        _front_x(PLATE_TAP_STATIONS[0] / 2.0),
        _UNDER_FRONT - STATION_PITCH,
    ),
    "PlateTapStation2": (
        _front_x(PLATE_TAP_STATIONS[1] / 2.0),
        _UNDER_FRONT - 2 * STATION_PITCH,
    ),
    "StudStation": (_front_x(STUD_STATION / 2.0), _UNDER_FRONT - 3 * STATION_PITCH),
    "TipStation": (_front_x(TIP_STATION / 2.0), _UNDER_FRONT - 4 * STATION_PITCH),
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
# witness lines: beside the view it crossed the left border.
SECTION_KEEP = {
    "SpotFaceDia": (_front_x(0.0), SECTION_CENTER[1] + 0.022),
    "FloorDepth": (_front_x(-PIVOT_END_R) - 0.005, SECTION_CENTER[1] - 0.020),
    "PinHoleDepth": (
        _front_x(TIP_STATION - PIN_HOLE_DEPTH / 2.0),
        SECTION_CENTER[1] - 0.020,
    ),
}
END_KEEP = {
    "Depth": (END_CENTER[0], _end_y(PIVOT_END_R) + 0.010),
    "PinHoleZ": (_end_x(PIN_HOLE_Z / 2.0), _end_y(-PIVOT_END_R) - 0.010),
    "PinHoleDia": (END_CENTER[0] + 0.030, _end_y(0.0) + 0.018),
}
DIMENSION_CALLOUTS = {
    "PivotBoreDia": PIVOT_BORE_CALLOUT,
    "SpotFaceDia": SPOT_FACE_CALLOUT,
    "FloorDepth": FLOOR_DEPTH_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
}

# Native tap callouts: arrow on the tap-drill rim under the rear countersink
# (the Hole Wizard's own edge; the countersink mouth is the chamfer's), text
# above the view, its top inside the upper border (review of 19e33c6c2: at
# 30 mm over the pivot round it touched the border).  Each carries its
# countersink line and the mating thread's installed full-thread engagement
# at the worst case (the screws are cut flush, the stud's run-out sits in its
# relief, and both taps go through), the hanger joints' and stud fit's
# figures.
_STUD_DRILL_R = blind_cut_dia_mm(STUD_TAP_SPEC) / 2.0
_PLATE_DRILL_R = blind_cut_dia_mm(PLATE_TAP_SPEC) / 2.0
_CALLOUT_Y = _front_y(PIVOT_END_R) + 0.022
STUD_CALLOUT_XY = (_front_x(STUD_STATION) + 0.036, _CALLOUT_Y)
PLATE_CALLOUT_XY = (_front_x(PLATE_TAP_STATIONS[0]) + 0.016, _CALLOUT_Y)
STUD_TAP_QUALIFIER = "\n".join(
    (
        STUD_TAP_CSK_CALLOUT,
        engagement_line(
            stud_fit.REAR_ENGAGEMENT_WORST, stud_fit.REAR_ENGAGEMENT_WORST_D
        ),
    )
)
PLATE_TAP_QUALIFIER = "\n".join(
    (
        PLATE_TAP_CSK_CALLOUT,
        engagement_line(
            joints.PLATE_SCREW_ENGAGEMENT_WORST, joints.PLATE_SCREW_ENGAGEMENT_WORST_D
        ),
    )
)
TAP_CALLOUTS = (
    ("stud tap", STUD_STATION, _STUD_DRILL_R, STUD_CALLOUT_XY, STUD_TAP_QUALIFIER),
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


def _rear_rim(view: Any, *, radius_mm: float, station_mm: float, label: str) -> Any:
    """The tap-drill rim nearest the rear face, by radius and station.

    Looking down a through hole both drill rims project to one circle; the
    rear one (largest z) is the one the viewer sees at the countersink's foot.
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
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        miss = abs(params[6] - radius_mm) + abs(params[0] - station_mm) + abs(params[1])
        nearest_miss = min(nearest_miss, miss)
        if miss <= 0.02:
            rims.append((params[2], edge))
    if not rims:
        raise RuntimeError(
            f"{label}: no drill rim R{radius_mm:.3f} at x {station_mm:.3f}; "
            f"nearest circle misses by {nearest_miss:.3f} mm"
        )
    return max(rims, key=lambda item: item[0])[1]


def tap_callout_definitions(
    definitions: dict[int, str], qualifier: str
) -> dict[int, str]:
    """Drop the title-block thread class from the thread compartment and
    append the countersink line under it; every other compartment and every
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
            f"{label} countersink line did not persist: "
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
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    for view in (front, section, end, iso):
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
    _set_stock_text(adapter, annotations)
    _overall_reference(adapter, front)
    for view, label in ((front, "front"), (end, "end")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME centre marks to the {label} view")

    # Thread and tap drill ride the native callouts; the class is the title
    # block's; the countersink and engagement lines are the qualifier's.
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

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Arm Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "... Tapped Hole" note to the front view
        # once a tap carries a hole callout; the two callouts already state
        # each thread and drill.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=len(TAP_CALLOUTS),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
