r"""Create the curated machinist drawing for the rocker pivot bracket (MHA-CH-008).

One sheet, third-angle: the elevation (the ear face, the reamed cross-bore and
the arch) with the plan above it (the foot, the hold-down hole and the apex
set-screw tap), a 2:1 right view for the foot-to-ear corner's MAX radius, and
a shaded isometric. Every value is a native model dimension the part build
marks, places and bands (``ch_pivot_bracket_drawing_spec``); the sheet only
places them.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

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
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import model_points_in_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from ch_pivot_bracket_drawing_spec import (
    CORNER_R_MAX,
    CORNER_R_TOL_TYPE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    SURFACE_FINISHES,
)
from ch_pivot_bracket_sides import FOOT_Z1, HOLE_Z
from ch_pivot_bracket_spec import (
    BORE_DIA,
    BORE_H,
    EAR_ARCH_R,
    EAR_T,
    EAR_TOP_Y,
    FOOT_H,
    FOOT_W,
    FOOT_Z0,
    SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT,
    SET_SCREW_HOLE_SPEC,
)


SPEC = DRAWINGS_BY_NAME["ch_pivot_bracket"]
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
PIVOT_SHAFT_NUMBER = str(_config.parts("ch-pivot-shaft")["number"])
SUPPORT_NUMBER = str(_config.parts("fr-rocker-arm-support")["number"])
THRUST_WASHER_NUMBER = str(_config.parts("ch-rocker-thrust-washer")["number"])

SHEET_SCALE = (3.0, 1.0)  # 33.2 mm tall: 3:1 keeps the bore and the tap legible
_S = SHEET_SCALE[0] / 1000.0  # sheet metres per model mm

# The elevation spans model y 0 (seat) to EAR_TOP_Y (arch apex) and is centred
# on that box; the plan above it spans the foot, z FOOT_Z0 (the ear's inboard
# face, the plan's TOP edge: a *Top view projects +Z downward) to FOOT_Z1 (the
# free end, its bottom edge). Sheet bands, bottom up: bore-lateral lane 0.030,
# elevation 0.040..0.140, foot-width lane 0.153, hole-lateral lane 0.164,
# plan 0.172..0.222, apex tap callout ~0.232..0.248 under the zone frame. The
# views stand right of the sheet's left edge so the plan's left lane and the
# elevation's height lanes have room; the plan's right lanes run out to the
# isometric.
_PART_MID_Y = EAR_TOP_Y / 2.0
_FOOT_MID_Z = (FOOT_Z0 + FOOT_Z1) / 2.0
FRONT_CENTER = (0.160, 0.090)
TOP_CENTER = (FRONT_CENTER[0], 0.197)
ISO_CENTER = (0.365, 0.170)
_WEST_X = FRONT_CENTER[0] - FOOT_W / 2.0 * _S
_EAST_X = FRONT_CENTER[0] + FOOT_W / 2.0 * _S
# The right view (*Right: +Z runs LEFT, +Y up) shows the foot-to-ear inside
# corner in profile, the one view where its radius is an arc. At 2:1 it is
# 33.9 x 66.4 mm and stands right of the bore callout, x 0.275..0.309, y
# 0.089..0.154: over the title block (top 0.066) with its caption under it,
# 17 mm under the foot length's extension line (0.172) and 20 mm left of the
# isometric (0.329). Its caption names it and its scale, as the fleet labels
# a view off the sheet scale.
RIGHT_SCALE = (2, 1)
_SR = RIGHT_SCALE[0] / RIGHT_SCALE[1] / 1000.0  # sheet metres per model mm
RIGHT_CENTER = (0.292, 0.122)
RIGHT_CAPTION = f"RIGHT VIEW\nSCALE {RIGHT_SCALE[0]}:{RIGHT_SCALE[1]}"


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the elevation (seat at model y = 0)."""
    return FRONT_CENTER[1] + (model_y - _PART_MID_Y) * _S


def _top_y(model_z: float) -> float:
    """Sheet Y of a model-Z station in the plan: +Z runs DOWN the sheet, and
    the view centres on the foot's mid-length, not on model z = 0."""
    return TOP_CENTER[1] - (model_z - _FOOT_MID_Z) * _S


def _right_x(model_z: float) -> float:
    """Sheet X of a model-Z station in the right view (+Z runs LEFT), the
    view centred on the foot's mid-length like the plan."""
    return RIGHT_CENTER[0] - (model_z - _FOOT_MID_Z) * _SR


def _right_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the right view (seat at model y = 0)."""
    return RIGHT_CENTER[1] + (model_y - _PART_MID_Y) * _SR


# The caption's top-left anchor, under the right view's seat line.
RIGHT_CAPTION_XY = (RIGHT_CENTER[0] - 0.013, _right_y(0.0) - 0.004)
# The inside corner (the foot top meets the ear's outboard face) and where the
# R MAX text stands off it, in sheet metres along the view's +Z and +Y: up
# into the open corner and out past the foot end, so the radial leader runs
# diagonally down to the arc over nothing but the corner's own air. Placed
# off the corner the build PROJECTS, so the view's real frame governs.
CORNER_MODEL_MM = (0.0, FOOT_H, EAR_T / 2.0)
CORNER_TEXT_OFFSET = (0.022, 0.020)
_CORNER_FRAME_TOL_M = 2.5e-4

# The elevation carries the heights off the seat -- the one face a machinist
# clamps to -- in nested left lanes (foot, bore axis, overall reference), the
# bore's lateral location off the west side face below the seat, and the arch
# radius up and right of the arch.
FRONT_KEEP = {
    "FootHt": (_WEST_X - 0.012, _front_y(FOOT_H / 2.0)),
    "BoreCz": (_WEST_X - 0.028, _front_y(BORE_H / 2.0)),
    # Right of the elevation's right edge by a clear 7 mm: the callout's
    # widest line, its mate's part number, ~58 mm long, centres on the text.
    "ShaftBoreDia": (FRONT_CENTER[0] + 0.060, _front_y(BORE_H) - 0.016),
    "ArchRadius": (FRONT_CENTER[0] + 0.043, _front_y(EAR_TOP_Y) + 0.006),
    "BoreLateral": (FRONT_CENTER[0] - FOOT_W / 4.0 * _S, _front_y(0.0) - 0.010),
}
# Every plan length along the foot runs from the ear's INBOARD face (the plan's
# top edge): the face fit-up sets and the fixtures hold Z0 on. Only the hole
# station stands on the left; the tap station, the ear thickness and the foot
# length step out on the right, each text in its own column (the foot length's
# extension lines leave the EAST corners, so on the left they would run the
# whole top edge the tap's leader must cross). The tap station's text sits
# just above its short span. Both laterals start on the west side face, below
# the plan, where the foot width nests outside them. Above the plan's left
# half only the apex tap callout stands.
TOP_KEEP = {
    "HoleStation": (_WEST_X - 0.031, _top_y(FOOT_Z0) - 0.0105),
    "SetScrewLocation": (_EAST_X + 0.021, _top_y(FOOT_Z0) + 0.009),
    "EarThick": (_EAST_X + 0.061, _top_y(0.0)),
    "FootLen": (_EAST_X + 0.116, _top_y(FOOT_Z1) + 0.012),
    "HoleDia": (FRONT_CENTER[0] + 0.045, _top_y(HOLE_Z)),
    "HoleLateral": (FRONT_CENTER[0] - FOOT_W / 4.0 * _S, _top_y(FOOT_Z1) - 0.008),
    "FootW": (FRONT_CENTER[0], _top_y(FOOT_Z1) - 0.019),
}
# REAM marks a fit bore, so the callout names its mate (drawing-guidelines.md
# rule 4); the drilled hold-down hole says drill and through. The three
# lengths that carry their own band say what the band holds: the hold-down
# hole lands on the support's tapped seat, the ear's faces bear on the bank's
# thrust washers and, with the tap's station, place the apex screw's cup on
# the pivot shaft's flat (ch_pivot_bracket_spec, rocker_bank_layout). The
# foot length rides the title block.
DIMENSION_CALLOUTS = {
    "ShaftBoreDia": f"REAM THRU\nSLIP FIT ON\nPIVOT SHAFT {PIVOT_SHAFT_NUMBER}",
    "HoleDia": "DRILL THRU",
    "HoleStation": f"ON {SUPPORT_NUMBER} SEAT",
    "EarThick": f"THRUST FACES ON {THRUST_WASHER_NUMBER}\nSET SCREW TO SHAFT FLAT",
    "SetScrewLocation": "ON SHAFT FLAT",
}
# The right view prints the one dimension it exists for.
RIGHT_KEEP_NAMES = ("CornerRadius",)
# The apex tap runs down into the bore and stops there. Both native extents
# ("<hw-thru>", the drill's and the thread's) say so in words; the thread
# class is the title block's; the thread's full-thread shortfall (a plain
# fact, rule 20) closes the callout of the hole it describes.
# Pending exception ruling: MHA-CH-008 set-screw engagement (#1371).
SET_SCREW_PROCESS = "TAP"
SET_SCREW_EXTENT = "TO BORE"
SET_SCREW_QUALIFIER = SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT
# Centre of the native tap callout's text, above the plan's left half: its
# leader drops from the block's right end through the plan's top edge to the
# tap's east rim, east of the hole station's extension line (which ends at
# the plan's centre) and west of the right lanes' (which start at its east
# edge).
SET_SCREW_CALLOUT_XY = (FRONT_CENTER[0] - 0.030, _top_y(FOOT_Z0) + 0.021)
# The overall height's lane, outside the bore-height lane.
OVERALL_HEIGHT_XY = (_WEST_X - 0.046, FRONT_CENTER[1])
_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
_LEADER_LINE_NONE = 3  # swLeaderLineVisibility_e.swLeaderLineNone
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)


def set_screw_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Rewrite the native tap callout's definition parts (5..8).

    Both ``<hw-thru>`` extents become TO BORE, the thread class goes (the
    title block states it), and the engagement fact closes the thread's own
    part, which prints last. Every Hole Wizard size variable stays.
    """
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    if "\n".join(definitions.values()).count("<hw-thru>") != 2:
        raise RuntimeError(f"tap callout lacks its two native extents: {definitions!r}")
    updated = {
        part: text.replace("<hw-thru>", SET_SCREW_EXTENT)
        for part, text in definitions.items()
    }
    thread_parts = [
        part for part, text in updated.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(f"tap thread line is not in one callout part: {updated!r}")
    part = thread_parts[0]
    without_class = re.sub(r" {2,}", " ", _THREAD_CLASS.sub(" ", updated[part]))
    updated[part] = f"{without_class.rstrip()}\n{SET_SCREW_QUALIFIER}"
    return updated


@_telemetry.traced("drawing.pivot_bracket.tap_callout_text")
def _set_tap_callout_text(display: Any) -> None:
    """Write the rewritten definitions and prove they persisted."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = set_screw_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(native.GetText(part) or "") for part in (1, 2, 3, 4)}
    joined = "\n".join(resolved.values())
    if (
        persisted != updated
        or joined.count(SET_SCREW_EXTENT) != 2
        or "2B" in joined
        or not any(
            text.rstrip().endswith(SET_SCREW_QUALIFIER) for text in resolved.values()
        )
    ):
        raise RuntimeError(
            "apex tap callout text did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"apex tap callout: {resolved!r}")


def _set_reference_precision(display: Any, label: str) -> None:
    """Give the SHEET-derived overall height its spec-owned decimal places.

    Every imported dimension's places are the part's and are read back by
    ``assert_imported_precision``; the parenthesised overall height is a
    band-free restatement with no model dimension behind it, so its places
    come from the spec's ``DRAWING_REFERENCE_PRECISION``, never a literal.
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: do-not-change for the dual and both tolerance places.
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{label}: sheet dimension prints {applied} decimal places, not {places}"
        )


@_telemetry.traced("drawing.pivot_bracket.front_entity_scan")
def _front_entities(adapter: Any, view: Any) -> tuple[Any, Any, Any]:
    """Return the seat edge, the cross-bore edge and the arch edge."""
    seat_candidates: list[tuple[float, Any]] = []
    circles: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="pivot bracket front edges"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is not None:
            curve = _early_bound(curve, "ICurve")
            if curve.IsCircle():
                params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
                circles.append((params[6], params[1], edge))
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(v) * 1000.0 for v in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(v) * 1000.0 for v in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1]) <= 0.01 and abs(p1[1]) <= 0.01:
            seat_candidates.append((abs(p1[0] - p0[0]), edge))
    if not seat_candidates:
        raise RuntimeError("front view has no model edge on the seat plane")
    seat_span, seat_edge = max(seat_candidates, key=lambda item: item[0])
    if seat_span < FOOT_W - 0.1:
        raise RuntimeError(f"seat edge span is only {seat_span:.3f} mm")

    def _circle(radius: float, label: str) -> Any:
        if not circles:
            raise RuntimeError("front view has no circular model edges")
        found_r, found_y, edge = min(
            circles, key=lambda item: abs(item[0] - radius) + abs(item[1] - BORE_H)
        )
        if abs(found_r - radius) > 0.01 or abs(found_y - BORE_H) > 0.01:
            raise RuntimeError(f"front view has no {label} edge at {BORE_H:.2f} mm")
        return edge

    return seat_edge, _circle(BORE_DIA / 2.0, "cross-bore"), _circle(EAR_ARCH_R, "arch")


@_telemetry.traced("drawing.arch_radius")
def _show_arch_radius(adapter: Any, annotations: list[Any]) -> None:
    """Dress the model's arch radius so its leader stops at the arc.

    The arch is a full-circle boss in the model with only its upper half on
    the part; the PART dimensions it as a radius. With the default "extend to
    the opposite side" the leader would run on through the bore and across
    the bore's diameter dimension, so it stops at the arc with the arrow
    outside (build_dt_arbor_pedestal's crown precedent).
    """
    for raw_annotation in annotations:
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if dimension_name(adapter, annotation) != "ArchRadius":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if bool(display.Diametric):
            raise RuntimeError("the imported arch dimension is not radial")
        display.ArcExtensionLineOrOppositeSide = False
        display.ArrowSide = _ARROWS_OUTSIDE
        if bool(display.ArcExtensionLineOrOppositeSide) or (
            int(display.ArrowSide) != _ARROWS_OUTSIDE
        ):
            raise RuntimeError("arch radius display did not persist")
        return
    raise RuntimeError("front view has no imported ArchRadius")


@_telemetry.traced("drawing.diameter_second_arrow", label_param="label")
def _disable_diameter_second_arrow(
    adapter: Any, annotations: list[Any], *, dimension: str, label: str
) -> None:
    """Remove a diameter dimension's optional arrow across the far side."""
    for raw_annotation in annotations:
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if dimension_name(adapter, annotation) != dimension:
            continue
        display = annotation.GetSpecificAnnotation()
        if display is None:
            raise RuntimeError(f"dimension {dimension!r} has no display annotation")
        display = _early_bound(display, "IDisplayDimension")
        display.SetSecondArrow(False, False)
        if bool(display.GetUseDocSecondArrow()) or bool(display.GetSecondArrow()):
            raise RuntimeError(f"failed to disable {label} far-side arrow")
        adapter.currentModel.GraphicsRedraw2()
        return
    raise RuntimeError(f"dimension {dimension!r} not found for {label}")


@_telemetry.traced("drawing.diameter_leader_lines", label_param="label")
def _hide_diameter_leader_lines(
    adapter: Any, annotations: list[Any], *, dimension: str, label: str
) -> None:
    """Keep a diameter callout to its arrow, bent leader and shelf.

    The plan's DRILL THRU callout drew, on one seat, a second line from the
    hole's quadrant straight past its text (farm audit 20261015T015928596Z:
    HoleDia's fourth line, 166.9,186.4 -> 216.4,177.6 mm) beside the bent
    leader. That is the dimension's LEADER-LINE pair, which
    ``swLeaderLineNone`` hides while the arrow at the rim survives
    (draw_fr_tube_frame's cross-hole callout, solidworks-drawing-layout-
    tuning.md refusal a).
    """
    for raw_annotation in annotations:
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if dimension_name(adapter, annotation) != dimension:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.LeaderVisibility = _LEADER_LINE_NONE
        if int(display.LeaderVisibility) != _LEADER_LINE_NONE:
            raise RuntimeError(f"{label} callout kept its dimension leader lines")
        adapter.currentModel.GraphicsRedraw2()
        return
    raise RuntimeError(f"dimension {dimension!r} not found for {label}")


@_telemetry.traced("drawing.pivot_bracket.right_keep")
def _right_keep(adapter: Any, view: Any) -> dict[str, tuple[float, float]]:
    """The R MAX text's sheet point, off the corner the view really shows.

    Projects the inside corner and one millimetre along model +Z and +Y, so
    the text stands CORNER_TEXT_OFFSET up into the open corner whichever way
    the view lays the foot; a frame off the planned one is logged.
    """
    x, y, z = (value / 1000.0 for value in CORNER_MODEL_MM)
    corner, along_z, along_y = model_points_in_view(
        adapter,
        view,
        [(x, y, z), (x, y, z + 0.001), (x, y + 0.001, z)],
        label="right-view corner frame",
        names=["corner", "corner +Z", "corner +Y"],
    )
    units = []
    for point in (along_z, along_y):
        length = math.dist(point, corner)
        if length <= 0.0:
            raise RuntimeError("right view does not show the corner in profile")
        units.append(
            tuple((p - c) / length for p, c in zip(point, corner, strict=True))
        )
    planned = (_right_x(CORNER_MODEL_MM[2]), _right_y(CORNER_MODEL_MM[1]))
    if math.dist(corner, planned) > _CORNER_FRAME_TOL_M:
        _telemetry.warn(
            f"right view corner at {corner!r}, planned {planned!r}; placing off "
            "the projected corner"
        )
    text = tuple(
        corner[axis]
        + CORNER_TEXT_OFFSET[0] * units[0][axis]
        + CORNER_TEXT_OFFSET[1] * units[1][axis]
        for axis in range(2)
    )
    _telemetry.info(f"right view corner {corner!r}, R MAX text {text!r}")
    return {"CornerRadius": (text[0], text[1])}


@_telemetry.traced("drawing.pivot_bracket.corner_radius")
def _dress_corner_radius(adapter: Any, annotations: list[Any]) -> None:
    """Prove the right view's CornerRadius prints the part's R MAX and stop
    its leader at the arc (draw_pn_pen_rod's shoulder radius).

    Read back: radial, measuring CORNER_R_MAX, the native swTolMAX the part
    set. ``ArcExtensionLineOrOppositeSide`` False keeps the leader from
    running on through the arc centre into the part.
    """
    found = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "CornerRadius"
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one CornerRadius on the right view, found {len(found)}"
        )
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported corner radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != CORNER_R_TOL_TYPE:
        raise RuntimeError(
            f"CornerRadius lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), CORNER_R_MAX / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("CornerRadius does not measure the corner fillet")
    display.ArcExtensionLineOrOppositeSide = False
    if bool(display.ArcExtensionLineOrOppositeSide):
        raise RuntimeError("CornerRadius leader still runs to the opposite side")
    _telemetry.info(f"corner radius: text {display.GetText(1)!r}, MAX type")


@_telemetry.traced("drawing.overall_height")
def _add_overall_height(adapter: Any, view: Any, seat: Any, arch: Any) -> Any:
    """The seat-to-apex height as a sheet reference dimension."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the elevation for the overall height")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, seat), (True, arch)):
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        if not _early_bound(raw_entity, "IEntity").Select4(append, selection_data):
            raise RuntimeError("failed to select an overall-height entity")
    display = draw.AddVerticalDimension2(*OVERALL_HEIGHT_XY, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to create the overall height dimension")
    set_arc_endpoints_to_max(adapter, display, label="overall height")
    set_reference_dimension(
        adapter,
        _early_bound(display, "IDisplayDimension").GetAnnotation(),
        label="overall height",
    )
    _set_reference_precision(display, "overall height")
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-bracket source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=("Number", "Material", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Pivot Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker pivot bracket; steel L bracket; pivot shaft cross-bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(3, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=RIGHT_SCALE)
    # No view needs hidden lines: the elevation shows the bore in true circle,
    # both holes are fully defined by their callouts in the plan, and the
    # right view is there for the corner's outline alone.
    for view in (front, top, iso, right):
        set_hidden_lines_removed(adapter, view)
    if add_note(adapter, RIGHT_CAPTION, *RIGHT_CAPTION_XY) is None:
        raise RuntimeError("failed to caption the right view")

    # The lateral locations and the tap station are owned by reference
    # sketches the part saves blanked; the hidden-owner curate shows each in
    # the one view that dimensions it.
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=_right_keep(adapter, right),
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported_annotations = [*front_annotations, *top_annotations, *right_annotations]
    set_dimension_callouts(adapter, imported_annotations, DIMENSION_CALLOUTS)
    _dress_corner_radius(adapter, right_annotations)
    for view, label in ((front, "front"), (top, "plan")):
        view.SetDisplayTangentEdges2(0)
        if int(view.GetDisplayTangentEdges2()) != 0:
            raise RuntimeError(f"failed to hide {label}-view tangent edges")
        view.UpdateViewDisplayGeometry()
    _disable_diameter_second_arrow(
        adapter, front_annotations, dimension="ShaftBoreDia", label="cross-bore"
    )
    _disable_diameter_second_arrow(
        adapter, top_annotations, dimension="HoleDia", label="hold-down hole"
    )
    _hide_diameter_leader_lines(
        adapter, top_annotations, dimension="HoleDia", label="hold-down hole"
    )
    for view, label in ((front, "front"), (top, "plan")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    seat_entity, _bore_entity, arch_entity = _front_entities(adapter, front)
    # Below and right of the seat, clear of the bore-lateral lane on its left
    # half: the leader lands on the seat's right quarter.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.035, _front_y(0.0) - 0.010),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="foot seat finish",
        char_height=0.0025,
        entity=seat_entity,
        leader_attach_xy=(FRONT_CENTER[0] + FOOT_W * _S / 4.0, _front_y(0.0)),
    )
    _add_overall_height(adapter, front, seat_entity, arch_entity)
    _show_arch_radius(adapter, front_annotations)
    adapter.currentModel.GraphicsRedraw2()

    # Apex set-screw tap: the plan sees it end-on at the arch apex. Picked on
    # its EAST rim so the leader leaves it eastward of the plan's centreline.
    tap_r = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC) / 2.0 * _S
    tap_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + tap_r, _top_y(0.0)),
        callout_xy=SET_SCREW_CALLOUT_XY,
        label="apex set-screw tap",
        process=SET_SCREW_PROCESS,
    )
    _set_tap_callout_text(tap_callout)
    # Re-assert the display mode now the last annotation has landed: an
    # annotation attached after placement can leave a view's edge set
    # unregenerated, and only a real mode change rebuilds it.
    for view in (front, top, iso, right):
        set_hidden_lines_removed(adapter, view)
    # The part authored every imported dimension's decimal places; prove the
    # import kept them instead of falling back to the sheet's default.
    assert_imported_precision(adapter, imported_annotations, DRAWING_PRECISION_BY_NAME)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Pivot Bracket Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#4-40 Tapped Hole" note to the tap; the
        # native callout already says everything it does.
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
