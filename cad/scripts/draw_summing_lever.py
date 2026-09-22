r"""Create the two-sheet manufacturing drawing for MHA-073.

The SLDPRT owns every nominal, decimal place, tolerance and surface control.
Sheet ``FORM-KNIFE`` defines the lever envelope, boss and knife trunnions at
native 1:2 sheet scale, with a native 2:1 Detail A for the functional knife
end. Sheet ``SPRING-PATTERN`` gives the authoritative 20-hole field an ordinary
first location, controlled total span, equal-spacing reference and both end
offsets.
All orthographic views are HLR; the standard isometric is finalized as
precision Shaded With Edges.

Run with SolidWorks open::

    uv run python cad\scripts\draw_summing_lever.py summing-lever
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from win32com.client.dynamic import Dispatch as dynamic_dispatch

import _telemetry
from _hole_spec import blind_cut_dia_mm
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_note,
    add_surface_finish,
    assert_imported_precision,
    create_blank_drawing_sheets,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    scan_view_edges,
    stamp_drawing_summary,
    set_reference_dimension,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from summing_lever_spec import (
    ANCHOR_R,
    CYL_R,
    COUNTER_HOLE_SPEC,
    DRAWING_REFERENCE_PRECISION,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEX_H,
    HEX_W,
    HEX_Z_OUTER,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_LAST,
    PLATE_W,
    SURFACE_FINISHES,
    TIP_X,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["summing_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
# Tap-drill diameter of the boss's counter-anchor tap; the rim points below
# pick its circular edge, and the native callout prints the thread itself.
COUNTER_R = blind_cut_dia_mm(COUNTER_HOLE_SPEC) / 2.0

SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 2.0)
SHEET_NAMES = ("FORM-KNIFE", "SPRING-PATTERN")

FORM_FRONT_SCALE = SHEET_SCALE
FORM_TOP_SCALE = SHEET_SCALE
ISO_SCALE = SHEET_SCALE
PATTERN_SCALE = SHEET_SCALE

# Front (down -Z) and top (down -Y) share this X envelope.
_BBOX_CX = (TIP_X - ANCHOR_R + PLATE_W) / 2.0

FORM_FRONT_CENTER = (0.150, 0.220)
FORM_TOP_CENTER = (0.150, 0.105)  # same X: true third-angle projection
ISO_CENTER = (0.335, 0.165)
PATTERN_CENTER = (0.165, 0.145)
DETAIL_CENTER = (0.335, 0.095)
DETAIL_SCALE = (2.0, 1.0)
DETAIL_RADIUS_MM = CYL_R + 3.3


def _top_xy(
    mx: float,
    mz: float,
    *,
    center: tuple[float, float],
    scale: tuple[float, float],
) -> tuple[float, float]:
    """Project model X/Z millimetres into one explicit top-view sheet frame."""
    factor = scale[0] / scale[1]
    return (
        center[0] + (mx - _BBOX_CX) * factor / 1000.0,
        center[1] + mz * factor / 1000.0,
    )

def _assert_uses_sheet_scale(view: Any, label: str) -> None:
    """Prove a view follows the native sheet scale printed in the title block."""
    bound = _early_bound(view, "IView")
    if int(bound.UseSheetScale) != 1:
        raise RuntimeError(f"{label} does not use its native sheet scale")


FORM_FRONT_KEEP = {
    "CylDia": (0.155, 0.258),
    "PlateThickness": (0.205, 0.215),
    "WebThickness": (0.218, 0.198),
    "AnchorHeight": (0.112, 0.215),
    "MidRibArcR": (0.225, 0.245),
}
FORM_TOP_KEEP = {
    "PlateWidth": (0.205, 0.145),
    "PlateLength": (0.225, FORM_TOP_CENTER[1]),
    "AnchorOuterDia": (0.112, 0.125),
    "AnchorOuterX": (0.135, 0.045),
    "HexKnifeFrontDepth": (0.158, 0.170),
    "EdgeRibThickness": (0.190, 0.165),
    "MiddleRibThickness": (0.205, 0.085),
    "SummationArcRadius": (0.105, 0.150),
    "BossAxialLocation": (0.095, 0.085),
}
DETAIL_KEEP = {
    "HexWidth": (DETAIL_CENTER[0], 0.128),
    "HexHeight": (0.370, DETAIL_CENTER[1]),
}
PATTERN_KEEP = {
    "HoleSeedX": (0.240, 0.230),
    "HolePitch": (0.230, 0.125),
    "HoleStartOffset": (0.260, 0.090),
    "PatternSpan": (0.275, 0.155),
    "HoleEndOffsetLast": (0.285, 0.205),
}


def _knife_detail(adapter: Any, front: Any) -> Any:
    """Create a native 2:1 crop of the actual hex trunnion end."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not ddoc.ActivateView(view_name(adapter, front)):
        raise RuntimeError("failed to activate knife-detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        front,
        (0.0, 0.0, 0.0),
        label="knife-detail center",
    )
    radius = DETAIL_RADIUS_MM * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if sketch_manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create knife-detail fence")
    detail = ddoc.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        "A",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create native knife-end detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    initial_outline = tuple(float(value) for value in detail.GetOutline())
    initial_position = tuple(float(value) for value in detail.Position)
    if len(initial_outline) != 4 or len(initial_position) != 2:
        raise RuntimeError(
            f"invalid knife-detail bounds: {initial_outline!r}, {initial_position!r}"
        )
    positioned_origin = tuple(
        initial_position[axis]
        + DETAIL_CENTER[axis]
        - (initial_outline[axis] + initial_outline[axis + 2]) / 2.0
        for axis in range(2)
    )
    if not detail.SetViewPosition(double_array(list(positioned_origin)), False):
        raise RuntimeError("failed to position knife-end detail")
    draw.EditRebuild3()
    final_outline = tuple(float(value) for value in detail.GetOutline())
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    outline_center = (
        (final_outline[0] + final_outline[2]) / 2.0,
        (final_outline[1] + final_outline[3]) / 2.0,
    )
    if (
        len(ratio) != 2
        or not math.isclose(ratio[0] / ratio[1], DETAIL_SCALE[0] / DETAIL_SCALE[1])
        or math.dist(outline_center, DETAIL_CENTER) > 0.0001
    ):
        raise RuntimeError(
            f"knife-detail scale/position did not persist: "
            f"ratio={ratio!r}, outline={final_outline!r}"
        )
    return detail


def _omit_default_thread_class(display: Any, expected_class: str, label: str) -> None:
    """Hide only the associative class token already covered by the title block."""
    display = _early_bound(display, "IDisplayDimension")
    class_variables = []
    for raw in display.GetHoleCalloutVariables() or ():
        variable = dynamic_dispatch(raw._oleobj_)
        if str(variable.VariableName) != "hw-threadclass":
            continue
        if int(variable.Type) != 3:
            raise RuntimeError(f"{label}: native thread-class variable is not a string")
        value = str(_early_bound(raw, "ICalloutStringVariable").String or "")
        if value.strip(" -") != expected_class:
            raise RuntimeError(
                f"{label}: native thread class {value!r} != {expected_class!r}"
            )
        class_variables.append(raw)
    if len(class_variables) != 1:
        raise RuntimeError(
            f"{label}: expected one native thread-class variable, "
            f"found {len(class_variables)}"
        )

    definitions = {
        part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)
    }
    matches = [
        part for part, definition in definitions.items()
        if "<hw-threadclass>" in definition
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one associative thread-class token: {definitions!r}"
        )
    definition_part = matches[0]
    updated = definitions[definition_part]
    for fragment in (
        " - <hw-threadclass>",
        "- <hw-threadclass>",
        "-<hw-threadclass>",
        " <hw-threadclass>",
        "<hw-threadclass>",
    ):
        if fragment in updated:
            updated = updated.replace(fragment, "", 1)
            break
    if "<hw-threadclass>" in updated or updated == definitions[definition_part]:
        raise RuntimeError(f"{label}: failed to remove only the thread-class token")
    resolved_part = definition_part - 4
    display.SetText(resolved_part, updated)
    if str(display.GetText(definition_part) or "") != updated:
        raise RuntimeError(f"{label}: associative callout definition did not persist")
    resolved = tuple(str(display.GetText(part) or "") for part in (1, 2, 3, 4))
    if any(expected_class in text for text in resolved):
        raise RuntimeError(f"{label}: default thread class still prints: {resolved!r}")
    if any(
        str(display.GetText(part) or "") != definition
        for part, definition in definitions.items()
        if part != definition_part
    ):
        raise RuntimeError(f"{label}: unrelated native callout definition changed")
    surviving_classes = []
    for raw in display.GetHoleCalloutVariables() or ():
        variable = dynamic_dispatch(raw._oleobj_)
        if str(variable.VariableName) == "hw-threadclass":
            surviving_classes.append(
                str(_early_bound(raw, "ICalloutStringVariable").String or "").strip(" -")
            )
    if surviving_classes != [expected_class]:
        raise RuntimeError(
            f"{label}: native thread-class association changed: "
            f"{surviving_classes!r}"
        )



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="summing-lever manufacturing package"
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; ferrous; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate summing-lever form sheet")
    front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *FORM_FRONT_CENTER,
    )
    top = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *FORM_TOP_CENTER,
    )
    iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *ISO_CENTER,
    )
    for label, view in (("form front", front), ("form top", top), ("iso", iso)):
        _assert_uses_sheet_scale(view, label)
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    front_dimensions = curate_view_dimensions(
        adapter,
        front,
        keep=FORM_FRONT_KEEP,
        view_label="form front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_dimensions = curate_view_dimensions(
        adapter,
        top,
        keep=FORM_TOP_KEEP,
        view_label="form top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail = _knife_detail(adapter, front)
    set_hidden_lines_removed(adapter, detail)
    detail_dimensions = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="knife-end detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    knife_surface_mm = (HEX_W / 4.0, 3.0 * HEX_H / 8.0, HEX_Z_OUTER)
    detail_edges = scan_view_edges(detail, label="knife-end detail finish")
    knife_surface_edge = detail_edges.exact_line_through(
        knife_surface_mm,
        label="upper-right knife face at outboard end",
    ).edge
    knife_surface_xy = model_point_in_view(
        adapter,
        detail,
        tuple(value / 1000.0 for value in knife_surface_mm),
        label="knife-ridge finish attachment",
    )
    add_surface_finish(
        adapter,
        detail,
        edge_entity=knife_surface_edge,
        symbol_xy=(0.382, 0.095),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge"),
        label="knife-edge ridge finish",
        leader_attach_xy=knife_surface_xy,
        char_height=0.0025,
    )
    if add_note(
        adapter,
        "CLOCK KNIFE RIDGE TO BOSS AXIS",
        0.285,
        0.060,
    ) is None:
        raise RuntimeError("failed to label knife-ridge clocking")
    # This is a read-only measurement of the actual knife-ridge endpoints,
    # not a second calculated model dimension.  Resolve the two model vertices
    # from one native visible-edge sweep and select those exact entities; sheet
    # hit-testing near the end edges can otherwise choose a perpendicular edge
    # and silently create an angular dimension.
    top_edges = scan_view_edges(top, label="form top overall reference")
    overall_vertices = tuple(
        top_edges.exact_vertex_at(
            (0.0, HEX_H / 2.0, z),
            label=f"knife-ridge endpoint z={z:g}",
        )
        for z in (-HEX_Z_OUTER, HEX_Z_OUTER)
    )
    overall = _early_bound(
        add_edge_dimension(
            adapter,
            top,
            p0=_top_xy(
                0.0,
                -HEX_Z_OUTER,
                center=FORM_TOP_CENTER,
                scale=FORM_TOP_SCALE,
            ),
            p1=_top_xy(
                0.0,
                HEX_Z_OUTER,
                center=FORM_TOP_CENTER,
                scale=FORM_TOP_SCALE,
            ),
            text_xy=(0.075, FORM_TOP_CENTER[1]),
            label="overall trunnion length reference",
            orientation="vertical",
            entity_types=("VERTEX", "VERTEX"),
            entities=overall_vertices,
        ),
        "IDisplayDimension",
    )
    dimension_type = int(overall.Type2)
    if dimension_type not in (2, 11, 12):
        raise RuntimeError(
            "overall trunnion reference is not linear: "
            f"IDisplayDimension.Type2={dimension_type}"
        )
    overall_annotation = _early_bound(overall.GetAnnotation(), "IAnnotation")
    set_reference_dimension(
        adapter,
        overall_annotation,
        label="overall trunnion length reference",
    )
    overall.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(overall.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("overall trunnion reference precision did not persist")
    overall_dimension = _early_bound(overall.GetDimension2(0), "IDimension")
    measured_overall_mm = abs(float(overall_dimension.SystemValue) * 1000.0)
    expected_overall_mm = 2.0 * HEX_Z_OUTER
    if abs(measured_overall_mm - expected_overall_mm) > 1e-5:
        raise RuntimeError(
            "overall trunnion reference measured "
            f"{measured_overall_mm:g}, expected {expected_overall_mm:g} mm"
        )
    if int(overall_dimension.GetToleranceType()) != 0:  # swTolNONE
        raise RuntimeError("overall trunnion reference unexpectedly carries a tolerance")
    overall_text_xy = (0.070, FORM_TOP_CENTER[1])
    if not overall_annotation.SetPosition2(*overall_text_xy, 0.0):
        raise RuntimeError("failed to position overall trunnion reference text")
    overall_text_position = tuple(
        float(value) for value in overall_annotation.GetPosition()
    )
    if math.dist(overall_text_position[:2], overall_text_xy) > 0.0001:
        raise RuntimeError(
            "overall trunnion reference text position did not persist: "
            f"{overall_text_position[:2]!r}"
        )

    counter_tap_edge = _top_xy(
        TIP_X,
        COUNTER_R,
        center=FORM_TOP_CENTER,
        scale=FORM_TOP_SCALE,
    )
    counter_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=counter_tap_edge,
        callout_xy=(0.070, 0.125),
        label="counter-spring anchor tap",
    )
    _omit_default_thread_class(
        counter_callout,
        COUNTER_HOLE_SPEC.thread_class,
        "counter-spring anchor tap",
    )

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate summing-lever spring-pattern sheet")
    pattern = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *PATTERN_CENTER,
    )
    _assert_uses_sheet_scale(pattern, "spring-pattern plan")
    set_hidden_lines_removed(adapter, pattern)
    pattern_dimensions = curate_view_dimensions(
        adapter,
        pattern,
        keep=PATTERN_KEEP,
        view_label="spring-pattern plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    seed_rim_right = _top_xy(
        HOLE_X + HOLE_DIA / 2.0,
        HOLE_Z_LAST,
        center=PATTERN_CENTER,
        scale=PATTERN_SCALE,
    )
    spring_callout = add_native_hole_callout(
        adapter,
        pattern,
        edge_xy=seed_rim_right,
        callout_xy=(0.275, 0.200),
        label="spring-hole pattern",
    )
    _omit_default_thread_class(
        spring_callout,
        HOLE_SPEC.thread_class,
        "spring-hole pattern",
    )

    for sheet_index, sheet_name in enumerate(SHEET_NAMES, start=1):
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to label drawing sheet {sheet_name}")
        if (
            add_note(
                adapter,
                f"SHEET {sheet_index} OF {len(SHEET_NAMES)}",
                0.350,
                0.263,
            )
            is None
        ):
            raise RuntimeError(f"failed to stamp sheet count on {sheet_name}")

    assert_imported_precision(
        adapter,
        [*front_dimensions, *top_dimensions, *detail_dimensions, *pattern_dimensions],
        DRAWING_PRECISION_BY_NAME,
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # Native readback inventories six view-owned descriptive INotes from
        # the two tap families across this four-view package. The associative
        # IDisplayDimension hole callouts are a separate annotation type.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=6,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales={name: SHEET_SCALE for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
