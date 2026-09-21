r"""Create the curated manufacturing drawing for the crank pinion (16T).

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The sheet is three
views of a toothed disc with a hub boss and seven native model dimensions.
Every turned diameter sits beside its axial extent on the side view: tooth-tip
blank, reamed bore and boss, with face width, pin station, overall length and
the boss end break. The retention pin's match-drill hole callout and the
gear-data block carry the process facts that geometry cannot.

No datums, no feature control frames, one roughness symbol (the bore): a
removable stock pinion pinned to its crankshaft is not on the GD&T allowlist
(rules 3-5). The bore's native limits and feature callout jointly identify its
mating crankshaft and required diametral clearance. The decimal places are the
PART's (``crank_pinion_spec.DRAWING_PRECISION``, applied natively by
``build_crank_pinion``); this script only reads them back off the sheet.

Drawn 4:1 -- the boss makes the part 17.28 long, and at the disc's 5:1 the
isometric ran off the B sheet's right border.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_leader_note,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    check_drawing_layout,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from crank_pinion_spec import (
    BORE_DIA,
    BORE_FIT_CALLOUT,
    BORE_PROCESS_CALLOUT,
    BOSS_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    OUTSIDE_DIA,
    OVERALL_LENGTH,
    PIN_DIA,
    PIN_HOLE_PROCESS,
    PIN_STATION,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_pinion"]
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

SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FRONT_CENTER = (0.110, 0.150)
RIGHT_CENTER = (0.215, 0.150)
ISO_CENTER = (0.345, 0.150)

# Half the printed tooth-tip circle, in sheet metres: the face view's silhouette
# radius and the side view's half-height, which every dimension is placed clear
# of; and half the printed boss, the side view's height past the teeth.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0  # 0.0356
HALF_BOSS = BOSS_DIA * VIEW_SCALE[0] / 2000.0  # 0.0270


def _side_x(z_mm: float) -> float:
    """Sheet x of a model-z station in the side view.

    SolidWorks centres a view on its geometry (the crankshaft sheet's
    ``_SIDE_BOTTOM`` idiom), and a *Right view lays model +Z to the LEFT (the
    boss end sits nearest the face view), so the toothed south face (z = 0) is
    the view's right edge and the boss end its left.
    """
    return RIGHT_CENTER[0] + (OVERALL_LENGTH / 2.0 - z_mm) * VIEW_SCALE[0] / 1000.0


def _simplify_side_gear_edges(adapter: Any, view: Any) -> None:
    """Hide repeated axial tooth edges while retaining the two OD silhouettes."""
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    transform = _early_bound(view.ModelToViewTransform, "IMathTransform")
    candidates: list[tuple[float, Any]] = []
    components = tuple(view.GetVisibleComponents() or ())
    for component in components:
        for raw_edge in tuple(view.GetVisibleEntities2(component, 1) or ()):
            edge = _early_bound(raw_edge, "IEdge")
            curve = edge.GetCurve()
            if curve is None:
                continue
            curve = _early_bound(curve, "ICurve")
            if not curve.IsLine():
                continue
            raw_vertices = (edge.GetStartVertex(), edge.GetEndVertex())
            if any(vertex is None for vertex in raw_vertices):
                continue
            start, end = (
                tuple(
                    float(value)
                    for value in _early_bound(vertex, "IVertex").GetPoint()
                )
                for vertex in raw_vertices
            )
            face_end = FACE_WIDTH / 1000.0
            if not (
                (abs(start[2]) <= 2e-6 and abs(end[2] - face_end) <= 2e-6)
                or (abs(end[2]) <= 2e-6 and abs(start[2] - face_end) <= 2e-6)
            ):
                continue
            midpoint = tuple(
                (a + b) / 2.0 for a, b in zip(start, end, strict=True)
            )
            point = _early_bound(
                math_utility.CreatePoint(double_array(midpoint)),
                "IMathPoint",
            )
            mapped = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
            candidates.append((float(mapped.ArrayData[1]), edge))
    if len(candidates) < 6:
        raise RuntimeError(
            f"side view exposed only {len(candidates)} axial gear edges; "
            "cannot apply conventional gear representation"
        )
    min_y = min(y for y, _edge in candidates)
    max_y = max(y for y, _edge in candidates)
    to_hide = [
        edge
        for y, edge in candidates
        if y > min_y + 1e-5 and y < max_y - 1e-5
    ]
    if len(to_hide) < 4:
        raise RuntimeError(
            f"side view identified only {len(to_hide)} repeated tooth edges to hide"
        )
    bound_view = _early_bound(view, "IView")
    hidden_before = len(tuple(bound_view.HiddenEdges or ()))
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    for edge in to_hide:
        entity = _early_bound(edge, "IEntity")
        if not entity.Select4(True, None):
            raise RuntimeError("failed to select a repeated side-view tooth edge")
    drawing = _early_bound(draw, "IDrawingDoc")
    drawing.HideEdge()
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="simplify crank pinion side-view gear")
    hidden_after = len(tuple(bound_view.HiddenEdges or ()))
    if hidden_after < hidden_before + len(to_hide):
        raise RuntimeError(
            "side-view tooth edges did not remain hidden: "
            f"{hidden_after - hidden_before} of {len(to_hide)}"
        )


# The end view is pictorial and carries only its center mark. Every turned
# diameter belongs beside the matching axial extent on the side view (rule 7);
# ``BossProfile`` supplies the tooth-tip and bore as construction-only native
# model dimensions so they import without hidden lines or sheet-authored
# numbers.
FRONT_KEEP: dict[str, tuple[float, float]] = {}
# Side view: the two solid-profile diameters sit above their own axial spans;
# the bore diameter sits just right of the silhouette, still clear of the
# isometric. The three lengths stay baseline-stacked below the view, every one
# from the toothed south face (rule 7: one origin per view, baseline not
# chained). The boss diameter and end break sit in the clear gap immediately
# left of the boss, rather than running through the cross-hole or down to the
# sheet's bottom dimension stack.
_SIDE_BOTTOM = RIGHT_CENTER[1] - HALF_OD
RIGHT_KEEP = {
    "OutsideDia": (
        (_side_x(0.0) + _side_x(FACE_WIDTH)) / 2.0,
        RIGHT_CENTER[1] + HALF_OD + 0.012,
    ),
    "BossDia": (
        _side_x(OVERALL_LENGTH) - 0.016,
        RIGHT_CENTER[1] + HALF_BOSS + 0.012,
    ),
    "BoreDia": (_side_x(0.0) + 0.020, RIGHT_CENTER[1]),
    "FaceWidth": ((_side_x(0.0) + _side_x(FACE_WIDTH)) / 2.0, _SIDE_BOTTOM - 0.014),
    "PinStation": ((_side_x(0.0) + _side_x(PIN_STATION)) / 2.0, _SIDE_BOTTOM - 0.026),
    "OverallLength": (RIGHT_CENTER[0], _SIDE_BOTTOM - 0.038),
    "BossChamfer": (
        _side_x(OVERALL_LENGTH) - 0.016,
        RIGHT_CENTER[1] + HALF_BOSS + 0.002,
    ),
}

DIMENSION_CALLOUTS = {
    # The native value/limits define the bore; this short feature callout adds
    # the process and extent without tangling its native diameter leaders.
    "BoreDia": BORE_PROCESS_CALLOUT,
    # The chamfer feature imports its one distance; the angle is the caption.
    "BossChamfer": "X 45 DEG",
}

# The retention-pin cross-hole: its exit circle on the boss wall nearest the
# viewer, at the pin station on the axis. The native callout hangs above the
# side view with the match-drill statement as its prefix.
PIN_HOLE_EDGE = (
    _side_x(PIN_STATION),
    RIGHT_CENTER[1] + PIN_DIA * VIEW_SCALE[0] / 2000.0,
)
PIN_HOLE_CALLOUT = (_side_x(PIN_STATION) + 0.022, RIGHT_CENTER[1] + HALF_OD + 0.036)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-pinion source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Pinion Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank pinion; steel; 16T spur",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # The side view alone shows hidden lines because it communicates the axial
    # bore there, as rule 7 requires for a turned part. Repeated axial tooth
    # edges are hidden separately so the bore and diameter leaders stay legible.
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, right)
    _simplify_side_gear_edges(adapter, right)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Whole-model import for the side view (the crankshaft's JournalStart
    # idiom): the targeted path selects a dimension's owner as a SKETCH or a
    # BODYFEATURE, and PinStation's owner is a reference PLANE, which it cannot
    # address (farm leaf 2026-09-21T13:51Z). The keep set still prunes the rest.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *right_annotations], DIMENSION_CALLOUTS
    )
    set_reference_dimensions(adapter, right_annotations, ("PinStation",))
    assert_imported_precision(
        adapter, front_annotations + right_annotations, DRAWING_PRECISION_BY_NAME
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pinion bore")
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin cross-hole")
    # The side view is a turned part's length view: its axis centerline says
    # which pair of edges is the faced ends (rule 7, turned parts), picked on
    # the boss's cylindrical face between the tooth face and the pin hole's
    # rim, a hair above the axis so the pick cannot land in the hole.
    add_view_centerline(
        adapter,
        right,
        face_xy=(
            (_side_x(FACE_WIDTH) + _side_x(PIN_STATION - PIN_DIA / 2.0)) / 2.0,
            RIGHT_CENTER[1] + 0.004,
        ),
        label="crank pinion axis centerline",
    )
    # The retention pin's hole: native size and THRU from the Hole Wizard,
    # the match-drill statement (mate by number) as its prefix -- rule 6 puts
    # a matched-fit requirement on the feature callout, not in a note.
    add_native_hole_callout(
        adapter,
        right,
        edge_xy=PIN_HOLE_EDGE,
        callout_xy=PIN_HOLE_CALLOUT,
        label="retention-pin cross-hole",
        process=PIN_HOLE_PROCESS,
    )
    # Keep the fit acceptance beside the visible bore rather than stacking it
    # under the side-view diameter. The view-owned pointer names the bore while
    # the native side-view dimension keeps its normal, connected leader.
    add_leader_note(
        adapter,
        BORE_FIT_CALLOUT,
        text_xy=(0.074, 0.220),
        attach_xy=(
            FRONT_CENTER[0] + BORE_DIA * VIEW_SCALE[0] / 2000.0,
            FRONT_CENTER[1],
        ),
        label="crank pinion bore fit",
        view=front,
        height=0.0025,
    )
    # The fit note and finish symbol use different bore quadrants, so their
    # leaders cannot be mistaken for one another.
    # The bore is the part's one fit surface, and a fit is a function of the
    # peaks as well as the size: REAM names the operation, not the finish it
    # leaves. The roughness is the project's general machined grade, authored
    # on the PART and read back here (policy rule 5's "a surface that has to
    # work" case). A surface symbol's native anchor is its lower-left corner,
    # and its text grows rightward; place it below the face view, clear of the
    # boss-chamfer witness.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + HALF_OD - 0.006, FRONT_CENTER[1] - 0.055),
        control=surface_finish_by_key(SURFACE_FINISHES, "crank_pinion_bore"),
        label="crank pinion bore finish",
        entity=visible_circle_edge(adapter, front, BORE_DIA),
        leader_attach_xy=(
            FRONT_CENTER[0],
            FRONT_CENTER[1] - BORE_DIA * VIEW_SCALE[0] / 2000.0,
        ),
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Gear Data", 0.016, 0.258, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.082, char_height=0.0025
    )
    rebuild_drawing(adapter, label="crank pinion layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Pinion Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
