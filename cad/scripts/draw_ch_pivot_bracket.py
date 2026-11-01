r"""Create the curated machinist drawing for the rocker pivot bracket (MHA-CH-08).

One sheet at 2:1, third-angle: the elevation (the ear face, the reamed
cross-bore and the arch) with the plan above it (the foot, the hold-down hole
and the apex set-screw tap) and the right view beside it for the foot-to-ear
corner's MAX radius, all three projected and aligned, and a shaded
isometric. Every value is a native model dimension the part build marks,
places and bands (``ch_pivot_bracket_drawing_spec``); the sheet only places
them, and adds one native REFERENCE between model edges: the bore axis to the
arch apex, which the overall and bore heights already fix.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
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
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import model_points_in_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from ch_pivot_bracket_drawing_spec import (
    CORNER_R_MAX,
    CORNER_R_TOL_TYPE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SURFACE_FINISHES,
)
from ch_pivot_bracket_sides import FOOT_Z1, HOLE_STATION, HOLE_Z
from ch_pivot_bracket_spec import (
    APEX_ABOVE_BORE,
    ARCH_LIFT,
    BORE_DIA,
    BORE_H,
    EAR_ARCH_R,
    EAR_T,
    EAR_TOP_Y,
    FOOT_H,
    FOOT_W,
    FOOT_Z0,
    SET_SCREW_HOLE_SPEC,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

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
THRUST_WASHER_NUMBER = str(_config.parts("ch-vn-rocker-thrust-washer")["number"])
HOLD_DOWN_SCREW_NUMBER = str(_config.parts("ch-vn-bracket-hold-down-screw")["number"])

# 35 mm tall: 2:1 keeps the bore and the tap legible and lets the right view
# stand at the sheet scale, level with the elevation, clear of the title block
# (#1371 machinist review: a 2:1 right view under a 3:1 sheet broke the
# projection).
SHEET_SCALE = (2.0, 1.0)
_VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / 1000.0  # sheet metres per model mm

# The elevation spans model y 0 (seat) to EAR_TOP_Y (arch apex) and is centred
# on that box; the plan above it spans the foot, z FOOT_Z0 (the ear's inboard
# face, the plan's TOP edge: a *Top view projects +Z downward) to FOOT_Z1 (the
# free end, its bottom edge). Sheet bands, bottom up: bore-lateral lane 0.070,
# elevation 0.080..0.149, foot-width lane 0.161, hole-lateral lane 0.172,
# plan 0.180..0.216, apex tap callout ~0.236..0.248 under the zone frame. The
# views stand right of the sheet's left edge so the elevation's height lanes
# have room; the plan's right lanes run out toward the isometric.
_PART_MID_Y = EAR_TOP_Y / 2.0
_FOOT_MID_Z = (FOOT_Z0 + FOOT_Z1) / 2.0
_SEAT_SHEET_Y = 0.080
_PLAN_BOTTOM_SHEET_Y = 0.180
FRONT_CENTER = (0.115, _SEAT_SHEET_Y + _PART_MID_Y * _S)
TOP_CENTER = (
    FRONT_CENTER[0],
    _PLAN_BOTTOM_SHEET_Y + (FOOT_Z1 - FOOT_Z0) / 2.0 * _S,
)
ISO_CENTER = (0.355, 0.160)
_WEST_X = FRONT_CENTER[0] - FOOT_W / 2.0 * _S
_EAST_X = FRONT_CENTER[0] + FOOT_W / 2.0 * _S
# The right view (*Right: +Z runs LEFT, +Y up) shows the foot-to-ear inside
# corner in profile, the one view where its radius is an arc. Projected off
# the elevation at the sheet scale, it stands level with it (the same seat
# and apex lines), right of the bore callout, x 0.244..0.280: over the title
# block (top 0.066), under the foot length's extension line (0.180) and left
# of the isometric. Being aligned at the sheet scale it needs no caption.
RIGHT_CENTER = (0.262, FRONT_CENTER[1])


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
    return RIGHT_CENTER[0] - (model_z - _FOOT_MID_Z) * _S


def _right_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the right view: the elevation's."""
    return RIGHT_CENTER[1] + (model_y - _PART_MID_Y) * _S


# The inside corner (the foot top meets the ear's outboard face) and where the
# R MAX text stands off it, in sheet metres along the view's +Z and +Y: up
# into the open corner and out past the foot end, so the radial leader runs
# diagonally down to the arc over nothing but the corner's own air. Placed
# off the corner the build PROJECTS, so the view's real frame governs. The
# text stands high and far enough out that its three callout lines (naming
# the screw head the limit clears) end above the foot top and left of the
# ear, right of the bore callout.
CORNER_MODEL_MM = (0.0, FOOT_H, EAR_T / 2.0)
CORNER_TEXT_OFFSET = (0.030, 0.030)
_CORNER_FRAME_TOL_M = 2.5e-4

# The elevation carries every height off the seat -- the one face a machinist
# clamps to -- in nested left lanes (rule 10, #1371 r1 review): the foot, the
# bore axis, the overall height to the arch apex (both the apex tap's thread
# is counted against); the bore's lateral location off the west side face
# below the seat, and the arch radius up and right of the arch.
FRONT_KEEP = {
    "FootHt": (_WEST_X - 0.012, _front_y(FOOT_H / 2.0)),
    "BoreCz": (_WEST_X - 0.028, _front_y(BORE_H / 2.0)),
    "OverallHeight": (_WEST_X - 0.044, _front_y(EAR_TOP_Y / 2.0)),
    # Right of the elevation's right edge by a clear 7 mm: the callout's
    # widest line, its mate's part number, ~58 mm long, centres on the text.
    "ShaftBoreDia": (FRONT_CENTER[0] + 0.052, _front_y(BORE_H) - 0.016),
    "ArchRadius": (FRONT_CENTER[0] + 0.030, _front_y(EAR_TOP_Y) + 0.004),
    "BoreLateral": (FRONT_CENTER[0] - FOOT_W / 4.0 * _S, _front_y(0.0) - 0.010),
}
# The arch's centre stands ARCH_LIFT over the bore axis, not on it (owner
# ruling Q12, 2026-10-16: the gate review read the R8.00 crown as concentric
# with the bore and counted 8.00 - 3.25 of metal over it). The bore axis to
# the arch apex prints as a REFERENCE chained on the bore height: the overall
# and the bore heights fix it, and it is the metal the apex tap's thread is
# counted in (ch_pivot_bracket_spec.APEX_ABOVE_BORE). A sheet dimension
# between the bore circle (its centre) and the arch arc (its far point), so
# the part and its cache key stay as they are. Its text stands in the foot
# height's lane, halfway up its span, between the bore and overall heights' extension
# lines it shares; it prints at the two heights' places, which the drawing
# document's default must already give (the sheet sets no precision).
APEX_REFERENCE_TEXT_XY = (
    FRONT_KEEP["FootHt"][0],
    _front_y((BORE_H + EAR_TOP_Y) / 2.0),
)
APEX_REFERENCE_PLACES = DRAWING_PRECISION_BY_NAME["OverallHeight"]
_ARC_END_CENTER = 1  # swArcEndCondition_e.swArcEndConditionCenter
_ARC_END_MAX = 3  # swArcEndCondition_e.swArcEndConditionMax (furthest point)
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
FRONT_CENTER_MARKS = 1  # the cross-bore
PLAN_CENTER_MARKS = 2  # the hold-down hole and the apex set-screw tap
# Every plan length along the foot runs from the ear's INBOARD face (the plan's
# top edge): the face fit-up sets and the fixtures hold Z0 on. Only the hole
# station stands on the left; the tap station, the ear thickness and the foot
# length step out on the right, nested shortest first, each in its own column
# (the foot length's extension lines leave the EAST corners, so on the left
# they would run the whole top edge the tap's leader must cross). Each banded
# station's text hangs off its own dimension line, at its own arrows, the two
# staggered (5bca52e machinist review FIX: the 4.00 block stood over the 8.00
# column's top arrow and the 8.00 text sat inside the 4.00 span, beside its
# lower arrow, so neither value read as its own pair's). The tap station's
# text stands ABOVE its short span: the shelf starts on its column 10 mm off
# the plan and the ~55 mm block runs east from it, east of the tap callout.
# The ear thickness's column stands clear east of that block, and its text
# hangs BELOW its span, under the ear's outboard-face line and over the foot
# length's lower extension line, the ~76 mm block running east from its own
# column, east of the hold-down hole's callout. The foot length's column
# stands past that block, its text in the upper half of its span, level with
# neither banded block. Both laterals start on the west side face, below the
# plan, where the foot width nests outside them. Above the plan's left half
# only the apex tap callout stands.
TOP_KEEP = {
    "HoleStation": (_WEST_X - 0.010, _top_y(FOOT_Z0 + HOLE_STATION / 2.0)),
    "SetScrewLocation": (_EAST_X + 0.010, _top_y(FOOT_Z0) + 0.017),
    "EarThick": (_EAST_X + 0.077, _top_y(FOOT_Z0 + EAR_T) - 0.010),
    "FootLen": (_EAST_X + 0.160, TOP_CENTER[1] + 0.008),
    "HoleDia": (FRONT_CENTER[0] + 0.045, _top_y(HOLE_Z) - 0.001),
    "HoleLateral": (FRONT_CENTER[0] - FOOT_W / 4.0 * _S, _top_y(FOOT_Z1) - 0.008),
    "FootW": (FRONT_CENTER[0], _top_y(FOOT_Z1) - 0.019),
}
# REAM marks a fit bore, so the callout names its mate (drawing-guidelines.md
# rule 4); the drilled hold-down hole says drill and through. The two lengths
# that carry their own band say what the band holds, naming the mate: the
# ear's faces bear on the bank's thrust washers, and the tap's station from
# the inboard face puts the apex screw's cup on the pivot shaft's flat
# (ch_pivot_bracket_spec, rocker_bank_layout). The foot length and the
# hold-down station ride the title block. The foot-to-ear corner's R MAX,
# tighter than the title block's inside corners, names what it serves: the
# hold-down screw's head seats on the foot top beside the ear's outboard face
# (ch_pivot_bracket_drawing_spec.CORNER_R_MAX), so a larger round lifts it.
DIMENSION_CALLOUTS = {
    "ShaftBoreDia": f"REAM THRU\nSLIP FIT ON\nPIVOT SHAFT {PIVOT_SHAFT_NUMBER}",
    "HoleDia": "DRILL THRU",
    "EarThick": f"THRUST FACES ON {THRUST_WASHER_NUMBER}",
    "SetScrewLocation": f"SET SCREW ON FLAT OF\nPIVOT SHAFT {PIVOT_SHAFT_NUMBER}",
    "CornerRadius": f"CLEARS HEAD OF\nHOLD-DOWN SCREW\n{HOLD_DOWN_SCREW_NUMBER}",
}
# The right view prints the one dimension it exists for.
RIGHT_KEEP_NAMES = ("CornerRadius",)
# The apex tap runs down into the bore and stops there. Both native extents
# ("<hw-thru>", the drill's and the thread's) say so in words; the thread
# class is the title block's. The arch's lift gives the tap 1.5D of full
# thread (ch_pivot_bracket_spec), so the callout states no shortfall.
SET_SCREW_PROCESS = "TAP"
# Hole Wizard callouts print three places on the inch sheet.
SET_SCREW_CALLOUT_PRECISION = {"hw-tapdrldia": 3}
SET_SCREW_EXTENT = "TO BORE"
# Centre of the native tap callout's text, above the plan's left half: its
# leader drops from the block's right end through the plan's top edge to the
# tap's east rim, east of the hole station's extension line (which ends at
# the plan's centre) and west of the right lanes' (which start at its east
# edge).
SET_SCREW_CALLOUT_XY = (FRONT_CENTER[0] - 0.018, _top_y(FOOT_Z0) + 0.026)
_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
_LEADER_LINE_NONE = 3  # swLeaderLineVisibility_e.swLeaderLineNone
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)


def set_screw_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Rewrite the native tap callout's definition parts (5..8).

    Both ``<hw-thru>`` extents become TO BORE and the thread class goes (the
    title block states it). Every Hole Wizard size variable stays.
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
    updated[part] = re.sub(
        r" {2,}", " ", _THREAD_CLASS.sub(" ", updated[part])
    ).rstrip()
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
    if persisted != updated or joined.count(SET_SCREW_EXTENT) != 2 or "2B" in joined:
        raise RuntimeError(
            "apex tap callout text did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"apex tap callout: {resolved!r}")


@_telemetry.traced("drawing.pivot_bracket.front_entity_scan")
def _seat_edge(view: Any) -> Any:
    """Return the elevation's seat edge, the foot's full width on y = 0."""
    seat_candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="pivot bracket front edges"):
        edge = _early_bound(raw_edge, "IEdge")
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
    return seat_edge


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


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION)
        or ()
    )


@_telemetry.traced("drawing.pivot_bracket.apex_reference_edges")
def _apex_reference_edges(view: Any) -> tuple[Any, Any]:
    """The elevation's bore circle and arch arc, as part edges.

    Matched on the part's own geometry (centre and radius, part millimetres),
    not a sheet pick: the arch's centre lies inside the bore circle, among its
    centre mark's lines. The ear's two faces each carry both curves; the near
    face's (largest z) is taken, the far one projecting onto it.
    """
    wanted = {
        "bore circle": (BORE_H, BORE_DIA / 2.0),
        "arch arc": (BORE_H + ARCH_LIFT, EAR_ARCH_R),
    }
    found: dict[str, list[tuple[float, Any]]] = {label: [] for label in wanted}
    for raw_edge in visible_view_entities(view, 1, label="pivot bracket front arcs"):
        curve = _early_bound(raw_edge, "IEdge").GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) for value in curve.CircleParams)
        cx, cy, cz = (value * 1000.0 for value in params[:3])
        radius = params[6] * 1000.0
        for label, (centre_y, wanted_radius) in wanted.items():
            if (
                abs(cx) <= 1e-3
                and abs(cy - centre_y) <= 1e-3
                and abs(radius - wanted_radius) <= 1e-3
            ):
                found[label].append((cz, raw_edge))
    picks = []
    for label, matches in found.items():
        if not matches:
            raise RuntimeError(f"front view shows no {label} for the apex reference")
        picks.append(max(matches, key=lambda item: item[0])[1])
    return picks[0], picks[1]


@_telemetry.traced("drawing.pivot_bracket.apex_reference")
def _add_apex_reference(adapter: Any, view: Any) -> Any:
    """Dimension the bore axis to the arch apex as a REFERENCE (owner Q12).

    Vertical, from the bore circle's centre (endpoint 1, the first pick) to
    the arch arc's furthest point (endpoint 2), each arc condition set and
    read back; its text then put back between the two heights' extension
    lines (SolidWorks keeps the text outside the span the dimension had
    while both ends sat on centres, ARCH_LIFT apart, too short for it -- r1);
    then parenthesized, its value proved against APEX_ABOVE_BORE (a swapped
    endpoint would read the bore's top to the arch centre, 1.45), its text
    position and its places against the heights'.
    """
    bore, arch = _apex_reference_edges(view)
    display = _early_bound(
        add_edge_dimension(
            adapter,
            view,
            p0=(0.0, 0.0),
            p1=(0.0, 0.0),
            text_xy=APEX_REFERENCE_TEXT_XY,
            label="bore axis to arch apex",
            orientation="vertical",
            entities=(bore, arch),
        ),
        "IDisplayDimension",
    )
    model = _early_bound(display.GetDimension(), "IDimension")
    for index, condition in ((1, _ARC_END_CENTER), (2, _ARC_END_MAX)):
        result = int(model.SetArcEndCondition(index, condition))
        if result != 0 or int(model.GetArcEndCondition(index)) != condition:
            raise RuntimeError(
                f"bore axis to arch apex endpoint {index} did not take arc "
                f"condition {condition} (SolidWorks result {result})"
            )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*APEX_REFERENCE_TEXT_XY, 0.0):
        raise RuntimeError("failed to place the bore axis to arch apex text")
    set_reference_dimension(
        adapter, annotation, label="bore axis to arch apex reference"
    )
    position = tuple(float(value) for value in annotation.GetPosition())
    if any(
        abs(actual - wanted) > 5e-4
        for actual, wanted in zip(position[:2], APEX_REFERENCE_TEXT_XY, strict=True)
    ):
        raise RuntimeError(
            f"bore axis to arch apex text sits at {position[:2]}, "
            f"not {APEX_REFERENCE_TEXT_XY}"
        )
    measured = abs(float(model.SystemValue)) * 1000.0
    if abs(measured - APEX_ABOVE_BORE) > 1e-4:
        raise RuntimeError(
            f"bore axis to arch apex measured {measured:.4f} mm, "
            f"expected {APEX_ABOVE_BORE:.4f}"
        )
    primary = int(display.GetPrimaryPrecision2())
    places = primary
    # swDimensionPrecisionSettings_e.swPrecisionFollowsDocumentSetting = -2:
    # read the drawing's linear-dimension default (swconst R2026x:
    # swDetailingLinearDimPrecision = 24, swDetailingLinearDimension = 206).
    if primary == -2:
        extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
        places = int(extension.GetUserPreferenceInteger(24, 206))
    if places != APEX_REFERENCE_PLACES:
        raise RuntimeError(
            f"bore axis to arch apex prints {places} places (primary {primary}), "
            f"the heights {APEX_REFERENCE_PLACES}"
        )
    _telemetry.info(f"apex reference: {display.GetText(1)!r} {measured:.2f}")
    return display


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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-pivot-bracket"),
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

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=_VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=_VIEW_SCALE)
    # The plan shows the crown's tangent seams as grey lines over its outline
    # (machinist review): hide them.
    top_view = _early_bound(top, "IView")
    top_view.SetDisplayTangentEdges2(0)  # swTangentEdgesHidden
    if int(top_view.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError("failed to hide the plan's tangent edges")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=_VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=_VIEW_SCALE)
    # No view needs hidden lines: the elevation shows the bore in true circle,
    # both holes are fully defined by their callouts in the plan, and the
    # right view is there for the corner's outline alone.
    for view in (front, top, iso, right):
        set_hidden_lines_removed(adapter, view)

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
    # The right view's arch-to-block tangent line is no edge the shop cuts.
    for view, label in ((front, "front"), (top, "plan"), (right, "right")):
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
    _add_apex_reference(adapter, front)
    # The template may centre-mark the holes as each view is placed (the Q12
    # r1 and r2 sheets arrived marked, and the explicit AutoInsertCenterMarks2
    # printed every front and plan mark twice: #913's duplicate marks), and
    # earlier sheets arrived unmarked. Add marks only to a bare view, then
    # prove exactly one per hole: the cross-bore; the hold-down hole and the
    # apex tap.
    for view, label, expected in (
        (front, "front", FRONT_CENTER_MARKS),
        (top, "plan", PLAN_CENTER_MARKS),
    ):
        if _center_mark_count(view) == 0 and not auto_center_marks(
            adapter, view, holes=True, size=0.0025
        ):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
        found = _center_mark_count(view)
        if found != expected:
            raise RuntimeError(
                f"expected {expected} centre marks in the {label} view, found {found}"
            )

    seat_entity = _seat_edge(front)
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
    set_hole_callout_precision(
        tap_callout, SET_SCREW_CALLOUT_PRECISION, label="apex set-screw tap"
    )
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
