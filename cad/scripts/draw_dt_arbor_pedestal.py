r"""Create the curated machinist drawing for the cylinder-arbor pedestal."""

from __future__ import annotations

import argparse
import re
import sys
from math import sqrt
from typing import Any, Literal

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

import _config
from _check import check
from _com import _early_bound
from _drawing_annotation_extent import place_callout_clear, require_clear
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_center,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _part_properties import part_drawing_unit
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_arbor_pedestal_spec import (
    BORE_DIA,
    BORE_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FOOT_HEIGHT,
    FOOT_MID_Z,
    FOOT_NEAR_Z,
    FOOT_WIDTH,
    HOLE_CALLOUT_PRECISION,
    SCREW_HOLE_DIA,
    SCREW_Z,
    SET_SCREW_HOLE_SPEC,
    SET_SCREW_Z,
    STRAP_INNER_Z,
    STRAP_ROOT_Z,
    SURFACE_FINISHES,
    TOP_RADIUS,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_arbor_pedestal"]
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

SHEET_SCALE = (2.0, 1.0)  # 2.18 in tall; 2:1 keeps the strap and bore legible
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# The part spans model y 0 (foot seat) to 55.45 (dome top); centre the front
# elevation on that midpoint. Third-angle projection keeps the plan aligned
# above the elevation; the isometric balances the aligned group from the
# right. The elevation sits low so the 1.10-deep plan (2.20 on the sheet) clears
# the crown band and still leaves two dimension lanes above itself under the
# sheet border: lateral-location lane 0.045, elevation 0.055..0.165, crown
# text ~0.173, plan 0.186..0.242, hole lateral lane 0.250, foot-width lane
# 0.259, hold-down hole callout left of the plan at 0.238. The 1.75 common
# cone-axis bore height grew the elevation 9.5 mm on the sheet; it grows
# downward, so the crown-to-plan band the apex tap callout sits in keeps its
# height.
_PART_MID_Y = (
    BORE_HEIGHT + TOP_RADIUS
) / 2.0  # foot 0 .. dome top (bore + dome radius)
FRONT_CENTER = (0.115, 0.110)
TOP_CENTER = (FRONT_CENTER[0], 0.214)
ISO_CENTER = (0.325, 0.155)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot seat at model y=0)."""
    return FRONT_CENTER[1] + (model_y - _PART_MID_Y) * _S


def _top_y(model_z: float) -> float:
    """Sheet Y of a model-Z station in the plan view.

    A ``*Top`` view placed above the elevation projects model +Z downward, so
    the foot's far face (+Z, where the strap is flush) is the plan's BOTTOM
    edge and the exposed hold-down ledge is at the top. The view is centred on
    its bounding box, and the foot runs -20..+8 about the part origin, so the
    sheet centre is the foot's mid-depth, not model z 0.
    """
    return TOP_CENTER[1] - (model_z - FOOT_MID_Z) * _S


# Lanes for the two lateral locations: below the seat in the elevation (the
# bore's centreline extends down through the part, crossing no other
# dimension's extension line), and just above the plan, inside the foot-width
# lane.
BORE_LATERAL_XY = (FRONT_CENTER[0] - FOOT_WIDTH / 4.0 * _S, _front_y(0.0) - 0.010)
HOLE_LATERAL_XY = (TOP_CENTER[0] - FOOT_WIDTH / 4.0 * _S, _top_y(FOOT_NEAR_Z) + 0.008)

# The elevation carries the height chain off the foot seat plus the fitted
# bore; the plan carries the foot rectangle, the strap band and the hold-down
# hole. Nested left lanes work outward from the shorter span (journal axis,
# then overall reference) off the one datum a machinist actually clamps to --
# the seat; the foot height sits east of the elevation, off the same seat.
FRONT_KEEP = {
    # Right of the elevation: the model dimension's upper witness leaves the
    # foot corner at the east taper kink. From a left lane that witness ran
    # across the whole upright face and read as a visible edge (ENFORCE r2).
    "FootHt": (
        FRONT_CENTER[0] + FOOT_WIDTH * _S / 2.0 + 0.016,
        _front_y(FOOT_HEIGHT / 2.0),
    ),
    "BoreHeight": (FRONT_CENTER[0] - 0.046, _front_y(BORE_HEIGHT / 2.0)),
    # Right of the elevation, far enough out that the three-line callout's
    # widest row ("ARBOR MHA-DT-13", ~42 mm) clears the tapered flank.
    "BoreDia": (FRONT_CENTER[0] + 0.050, _front_y(BORE_HEIGHT) - 0.010),
    "BoreLateral": BORE_LATERAL_XY,
    # Crown: the model's radius (_show_crown_radius), up and right of the dome.
    "DomeRadius": (0.178, _front_y(BORE_HEIGHT + TOP_RADIUS) + 0.008),
}
TOP_KEEP = {
    # ABOVE the plan, outside the hole lateral lane. Below it (0.183) the
    # apex tap callout's leader -- which can only leave the plan downward,
    # because the hold-down, set-screw, strap and depth lines all span the tap's
    # station -- crossed this dimension line (2026-10-18 ENFORCE r1, rule 14
    # (keep text off the part)). Up here its witnesses run the plan's full
    # height along the side edges; the hold-down callout's leader crosses the
    # west one, which rule 14 calls conventional.
    "Width": (TOP_CENTER[0], _top_y(FOOT_NEAR_Z) + 0.017),
    # Outer right lane, outboard of the strap band and set-screw station
    # nested inside it. On the left (0.067) its far-face witness was the
    # line the apex tap callout's leader had to cross.
    "Depth": (TOP_CENTER[0] + 0.065, TOP_CENTER[1]),
    # Both plan depths work off the foot's far face -- the one face the strap
    # is flush with, so a shop can set the whole Z chain from a single edge.
    "HoldDownLocation": (
        TOP_CENTER[0] - 0.036,
        _top_y((STRAP_INNER_Z + SCREW_Z) / 2.0),
    ),
    # Right lanes, nested off the same far face: the apex set-screw tap's
    # station (#743) inside, the strap band outside it.
    "SetScrewLocation": (
        TOP_CENTER[0] + 0.032,
        _top_y((STRAP_INNER_Z + SET_SCREW_Z) / 2.0),
    ),
    "StrapDepth": (
        TOP_CENTER[0] + 0.050,
        _top_y((STRAP_INNER_Z + STRAP_ROOT_Z) / 2.0),
    ),
    "HoleLateral": HOLE_LATERAL_XY,
}
# X on this part starts on a FEATURE, never the symmetry axis (drawing-guidelines.md rule 10 (dimension from a real feature)):
# the bore in the elevation and the hold-down hole in the plan are both
# dimensioned from the foot's west side face, so the two views share one
# origin the shop can touch off.

# The arbor (MHA-DT-13) is what the reamed bore fits: the front pedestal's
# apex screw locks it, and the back pedestal slides along it while its strap
# is set off the bank's north spring blade (cylinder_bank_layout), so the bore is a
# sliding fit and the Ra 63 says so (rule 4 (tighten only for function, and
# name the mate); 2026-10-18 ENFORCE r1 blocker).
ARBOR_NUMBER = str(_config.parts("dt-cylinder-gear-shaft")["number"])
DIMENSION_CALLOUTS = {
    "BoreDia": f"REAM THRU\nSLIDING FIT ON\nARBOR {ARBOR_NUMBER}",
}
CROWN_CALLOUT = "SIDES TANGENT FROM FOOT CORNERS"
# The apex tap runs down to the arbor bore and stops there; the MHA-SH-VN-54 cup
# point's spot is drilled into the arbor at fit-up through this hole. Both
# native extents (the tap drill's and the thread's ``<hw-thru>``) say TO BORE,
# so neither can read as a drill carried on past the bore into the strap
# (2026-10-18 ENFORCE r1: "Ø2.26 THRU / TAP TO BORE ... THRU" gave two
# extents), and the thread class goes: the title block states it (rule 2 (the
# title block is the general specification)). Same rewrite as the MHA-CH-05
# pivot bracket's apex tap. Digit-free words (rule 7 (notes: few, flagged,
# never a method)); the plan already shows the hole at the apex, so the words
# do not repeat it: v37's "..., AT CROWN APEX" ran the callout 22.6 mm past
# the zone frame.
SET_SCREW_PROCESS = "TAP"
# Hole Wizard drill sizes print .XXX on the inch sheet, by native variable.
HOLD_DOWN_PRECISION = {"hw-diam": HOLE_CALLOUT_PRECISION}
SET_SCREW_PRECISION = {"hw-tapdrldia": HOLE_CALLOUT_PRECISION}
SET_SCREW_EXTENT = "TO BORE"
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)
# The overall height's lane, left of the elevation.
OVERALL_HEIGHT_XY = (FRONT_CENTER[0] - 0.058, FRONT_CENTER[1])
# Sheet Y of the elevation's crown apex and of the plan's far face: the tap
# callout sits in the band between them, left of the hole, so its leader
# drops left out of the plan under the left lane instead of crossing the
# right-hand strap and set-screw dimensions. Its shoulder (the bottom row,
# ~5.6 mm under the centre) stands above the elevation's padded outline
# (apex + 5.6 mm). Centred mid-band, the shoulder ran inside that outline
# (leader-crosses-view).
_CROWN_APEX_Y = _front_y(BORE_HEIGHT + TOP_RADIUS)
_PLAN_FAR_Y = _top_y(STRAP_INNER_Z)
SET_SCREW_CALLOUT_XY = (TOP_CENTER[0] - 0.055, _CROWN_APEX_Y + 0.0114)
# The hold-down hole's callout: text CENTRE (the row runs ~50 mm) left of
# the plan and above the hold-down station's lane, its leader dropping right
# to the hole's upper-west rim. The leader crosses only the plan's west edge
# (and the foot-width witness on it); it stays above the hole-station
# extension line and west of the strap depth's. Above the plan its leader
# crossed the foot width's dimension line once that lane moved up
# (TOP_KEEP["Width"]).
_HOLD_DOWN_RIM = SCREW_HOLE_DIA / 2.0 * _S * sqrt(0.5)
HOLD_DOWN_EDGE_XY = (TOP_CENTER[0] - _HOLD_DOWN_RIM, _top_y(SCREW_Z) + _HOLD_DOWN_RIM)
HOLD_DOWN_CALLOUT_XY = (TOP_CENTER[0] - 0.055, _top_y(FOOT_NEAR_Z) - 0.004)
# Half the ink of a drawn line: the 0.25 mm line weight.
_LINE_HALF_M = 0.000125


def _line_box(x0: float, y0: float, x1: float, y1: float) -> tuple[float, ...]:
    """A drawn horizontal or vertical line as the box its ink covers."""
    return (
        min(x0, x1) - _LINE_HALF_M,
        min(y0, y1) - _LINE_HALF_M,
        max(x0, x1) + _LINE_HALF_M,
        max(y0, y1) + _LINE_HALF_M,
    )


def set_screw_callout_below() -> dict[str, tuple[float, ...]]:
    """The elevation ink under the apex tap callout's band: its text must
    clear it from above (place_callout_clear's ``below``)."""
    overall_x = OVERALL_HEIGHT_XY[0]
    return {
        "crown apex and its overall-height extension line": _line_box(
            overall_x, _CROWN_APEX_Y, FRONT_CENTER[0], _CROWN_APEX_Y
        ),
        "overall height dimension line": _line_box(
            overall_x, _front_y(0.0), overall_x, _CROWN_APEX_Y
        ),
    }


def set_screw_callout_beside() -> dict[str, tuple[float, ...]]:
    """The plan's left lane over the band: the text clears it from the
    right, and the leader must not cross it (place_callout_clear's
    ``beside``). The far face is split at the plan's west edge: the leader has
    to cross the face itself to reach the hole, but not the extension line
    the hold-down lane draws off it."""
    plan_west = TOP_CENTER[0] - FOOT_WIDTH / 2.0 * _S
    lane_x = TOP_KEEP["HoldDownLocation"][0]
    return {
        "plan far-face extension line": _line_box(
            lane_x, _PLAN_FAR_Y, plan_west, _PLAN_FAR_Y
        ),
        "hold-down location dimension line": _line_box(
            lane_x, _PLAN_FAR_Y, lane_x, _top_y(SCREW_Z)
        ),
    }


def set_screw_callout_above() -> dict[str, tuple[float, ...]]:
    """The plan's far face over the band: the text stays under it."""
    return {
        "plan far face": _line_box(
            TOP_CENTER[0] - FOOT_WIDTH / 2.0 * _S,
            _PLAN_FAR_Y,
            TOP_CENTER[0] + FOOT_WIDTH / 2.0 * _S,
            _PLAN_FAR_Y,
        ),
    }


def _set_reference_precision(display: Any, label: str) -> None:
    """Give a SHEET-derived dimension its PART-authored decimal places.

    drawing-simplicity-policy.md `How the repository implements the guidelines` puts display precision on the model, and every imported
    dimension here is read back by ``assert_imported_precision``. The strap
    band, the hold-down station and both lateral locations are owned by the
    part's hidden reference sketches, and the crown radius is the dome's own
    diameter printed radial (#810 Codex l4afp). What is left is the
    parenthesised overall height, a band-free restatement. Its places are
    still specification, so they come from the spec, never a literal.
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: swDimensionPrecisionSettings_e do-not-change for the dual and both
    # tolerance places -- the part owns those too. The subscript is written
    # out again because _drawing_contract only accepts a spec lookup here.
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{label}: sheet dimension prints {applied} decimal places, not {places}"
        )


@_telemetry.traced("drawing.arbor.front_entity_scan")
def _front_entities(adapter: Any, view: Any) -> tuple[Any, Any, Any]:
    """Return the foot-seat, arbor-bore and crown entities."""
    foot_candidates: list[tuple[float, Any]] = []
    bore_candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="pedestal front edges"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is not None:
            curve = _early_bound(curve, "ICurve")
            if curve.IsCircle():
                params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
                bore_candidates.append((params[6], params[1], edge))
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        start = _early_bound(start, "IVertex")
        end = _early_bound(end, "IVertex")
        p0 = tuple(float(value) * 1000.0 for value in start.GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in end.GetPoint())
        if abs(p0[1]) <= 0.01 and abs(p1[1]) <= 0.01:
            foot_candidates.append((abs(p1[0] - p0[0]), edge))
    if not foot_candidates:
        raise RuntimeError("front view has no model edge on the foot-seat plane")
    foot_span, foot_edge = max(foot_candidates, key=lambda item: item[0])
    if foot_span < FOOT_WIDTH - 0.1:
        raise RuntimeError(f"foot-seat edge span is only {foot_span:.3f} mm")
    if not bore_candidates:
        raise RuntimeError("front view has no circular model edges")
    radius, height, bore_edge = min(
        bore_candidates,
        key=lambda item: abs(item[0] - BORE_DIA / 2.0) + abs(item[1] - BORE_HEIGHT),
    )
    if abs(radius - BORE_DIA / 2.0) > 0.01 or abs(height - BORE_HEIGHT) > 0.01:
        raise RuntimeError(
            f"no circular edge matches arbor bore at {BORE_HEIGHT:.3f} mm"
        )
    dome_radius, dome_height, dome_edge = min(
        bore_candidates,
        key=lambda item: abs(item[0] - TOP_RADIUS) + abs(item[1] - BORE_HEIGHT),
    )
    if abs(dome_radius - TOP_RADIUS) > 0.01 or abs(dome_height - BORE_HEIGHT) > 0.01:
        raise RuntimeError("front view has no circular dome edge")
    return foot_edge, bore_edge, dome_edge


_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside


@_telemetry.traced("drawing.crown_radius")
def _show_crown_radius(adapter: Any, annotations: list[Any]) -> None:
    """Dress the model's crown radius (DomeRadius, part-owned places).

    The dome is a full-circle boss in the model, but only its upper arc
    survives on the part, and a print gives an arc a radius -- so the PART
    dimensions it as one (#810 Codex l4afp, drawing-simplicity-policy.md `How the repository implements the guidelines`). The sheet must not
    flip a model diameter radial instead: that keeps the value and re-reads it
    as a radius, and v37 printed an R22 crown on this R11 part.
    """
    for raw_annotation in annotations:
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if dimension_name(adapter, annotation) != "DomeRadius":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if bool(display.Diametric):
            raise RuntimeError("the imported crown dimension is not radial")
        # The crown is what places the tapered flanks: each side runs from a
        # foot corner up to tangency with this radius, whose centre is
        # the bore's (the shared centre mark says so). The Fable round-2
        # review could not tell where the flanks start, so the words name
        # both ends. Words only -- every digit on this sheet is a dimension.
        display.SetText(4, CROWN_CALLOUT)
        # The leader runs from the text toward the crown centre; with the
        # default "extend to the opposite side" it kept going through the bore
        # and crossed the Ø9.55 dimension at the centre. Stop it at the arc.
        display.ArcExtensionLineOrOppositeSide = False
        # Arrow OUTSIDE the arc (swDimArrowsOutside): the leader runs from the
        # text to the crown and stops there. Inside, the dimension line ran
        # from the arc to the centre, straight through the bore (810-l4afp-1
        # eye pass).
        display.ArrowSide = _ARROWS_OUTSIDE
        if (
            bool(display.Diametric)
            or str(display.GetText(4) or "") != CROWN_CALLOUT
            or bool(display.ArcExtensionLineOrOppositeSide)
            or int(display.ArrowSide) != _ARROWS_OUTSIDE
        ):
            raise RuntimeError("crown radius display did not persist")
        _telemetry.info(f"crown radius: DomeRadius text {display.GetText(1)!r}")
        return
    raise RuntimeError("front view has no imported DomeRadius to show as the crown")


@_telemetry.traced("drawing.set_screw_callout_clear")
def _prove_set_screw_callout_clear(adapter: Any, display: Any) -> None:
    """Place the apex tap callout from its read-back ink and prove it: inside
    the zone frame, its text clear of the crown apex, the overall height, both
    left lanes and the plan, and its leader off every line but the plan face
    it has to cross (v37: 22.6 mm past the frame, over the (61.72) and the
    elevation)."""
    annotation = _early_bound(display, "IDisplayDimension").GetAnnotation()
    ink = place_callout_clear(
        adapter,
        annotation,
        label="apex set-screw tap",
        below=set_screw_callout_below(),
        beside=set_screw_callout_beside(),
    )
    # place_callout_clear only moves up and right; the plan above the band
    # is proven separately so a move can never push the text into it.
    require_clear(ink.label, ink.text, set_screw_callout_above())


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


@_telemetry.traced("drawing.arbor.tap_callout_text")
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


@_telemetry.traced("drawing.diameter_second_arrow", label_param="label")
def _disable_diameter_second_arrow(
    adapter: Any,
    annotations: list[Any],
    *,
    dimension: str,
    label: str,
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


@_telemetry.traced("drawing.entity_dimension", label_param="label")
def _add_entity_dimension(
    adapter: Any,
    view: Any,
    entity0: Any,
    entity1: Any,
    *,
    orientation: str,
    position: tuple[float, float],
    label: str,
    arc_endpoint: Literal["center", "max"] | None = None,
) -> Any:
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, entity0), (True, entity1)):
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        entity = _early_bound(raw_entity, "IEntity")
        if not entity.Select4(append, selection_data):
            raise RuntimeError(f"failed to select {label} entity")
    if orientation == "horizontal":
        display = draw.AddHorizontalDimension2(*position, 0.0)
    elif orientation == "vertical":
        display = draw.AddVerticalDimension2(*position, 0.0)
    else:
        raise ValueError(f"unsupported entity-dimension orientation: {orientation}")
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label} dimension")
    if arc_endpoint == "center":
        set_arc_endpoints_to_center(adapter, display, label=label)
    elif arc_endpoint == "max":
        set_arc_endpoints_to_max(adapter, display, label=label)
    elif arc_endpoint is not None:
        raise ValueError(f"unsupported arc endpoint: {arc_endpoint}")
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open arbor-pedestal source", await adapter.open_model(str(SOURCE)))
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
        required=(
            "Number",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cylinder-Arbor Pedestal Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "arbor pedestal; ferrous stock or casting; arbor clamp bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    # Neither orthographic view needs hidden lines: the elevation shows the
    # arbor bore in true circle and the hold-down hole is a native callout on
    # the plan, so dashed outlines would only add crossings over the strap.
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    # The strap band, hold-down station and lateral locations are owned by
    # reference sketches the part saves blanked (arbor_pedestal_spec
    # REFERENCE_SKETCHES); the hidden-owner curate shows each in the one view
    # that dimensions it.
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
    imported_annotations = [*front_annotations, *top_annotations]
    set_dimension_callouts(adapter, imported_annotations, DIMENSION_CALLOUTS)
    for view, label in ((front, "front"), (top, "plan")):
        view.SetDisplayTangentEdges2(0)
        if int(view.GetDisplayTangentEdges2()) != 0:
            raise RuntimeError(f"failed to hide {label}-view tangent edges")
        view.UpdateViewDisplayGeometry()
    _disable_diameter_second_arrow(
        adapter,
        front_annotations,
        dimension="BoreDia",
        label="arbor bore",
    )
    for view, label in ((front, "front"), (top, "plan")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    foot_entity, bore_entity, dome_entity = _front_entities(adapter, front)
    # Attach on the bore's 3 o'clock point and keep the symbol above that
    # height: left to itself the leader reached into the circle and crossed
    # the diameter dimension's line, which leaves the bore at 315 deg.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.037, _front_y(BORE_HEIGHT) + 0.010),
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
        char_height=0.0025,
        entity=bore_entity,
        leader_attach_xy=(
            FRONT_CENTER[0] + BORE_DIA / 2.0 * _S,
            _front_y(BORE_HEIGHT),
        ),
    )
    # Under the seat's east half, between the bore lateral's witness at the
    # centreline and the foot-height lane east of the elevation: the leader
    # drops from the seat's right quarter and the roughness text hangs right
    # of the vee, short of the foot height's lower arrow.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.017, _front_y(0.0) - 0.011),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="foot seat finish",
        char_height=0.0025,
        entity=foot_entity,
        leader_attach_xy=(FRONT_CENTER[0] + FOOT_WIDTH * _S / 4.0, _front_y(0.0)),
    )
    overall = _add_entity_dimension(
        adapter,
        front,
        foot_entity,
        dome_entity,
        orientation="vertical",
        position=OVERALL_HEIGHT_XY,
        label="overall height",
        arc_endpoint="max",
    )
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall height",
    )
    _set_reference_precision(overall, "overall height")
    _show_crown_radius(adapter, front_annotations)
    adapter.currentModel.GraphicsRedraw2()
    hold_down_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=HOLD_DOWN_EDGE_XY,
        callout_xy=HOLD_DOWN_CALLOUT_XY,
        label="flange hold-down hole",
        process="DRILL",
    )
    set_hole_callout_precision(
        hold_down_callout, HOLD_DOWN_PRECISION, label="flange hold-down hole"
    )
    # Apex set-screw tap (#743): the plan sees it end-on at the crown apex.
    # Its callout sits in the band between the crown apex and the plan
    # (SET_SCREW_CALLOUT_XY); the read-back ink proves it there.
    _tap_r = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC) / 2.0 * _S
    tap_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] - _tap_r, _top_y(SET_SCREW_Z)),
        callout_xy=SET_SCREW_CALLOUT_XY,
        label="apex set-screw tap",
        process=SET_SCREW_PROCESS,
    )
    _set_tap_callout_text(tap_callout)
    set_hole_callout_precision(tap_callout, SET_SCREW_PRECISION, label="apex set-screw tap")
    _prove_set_screw_callout_clear(adapter, tap_callout)
    # Re-assert the display mode now the last annotation has landed: an
    # annotation attached after placement can leave a view's edge set
    # unregenerated, and only a real mode change rebuilds it.
    for view in (front, top):
        set_hidden_lines_removed(adapter, view)
    # The part authored every imported dimension's decimal places; prove the
    # import kept them instead of falling back to the sheet's two-place
    # default (drawing-simplicity-policy.md `How the repository implements the guidelines` -- the sheet may not rewrite them).
    assert_imported_precision(adapter, imported_annotations, DRAWING_PRECISION_BY_NAME)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder-Arbor Pedestal Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#4-40 Tapped Hole" note to the tap; the
        # native callout already says everything it does (v37 printed it
        # over the plan's 24.0). One tap, one note: the v37 sheet carried
        # exactly one.
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
