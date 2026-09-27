r"""Create the curated machinist drawing for the rocker pivot shaft (MHA-065)."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pivot_shaft_spec import (
    DOME_CALLOUT,
    DOME_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    JOURNAL_LENGTH,
    LENGTH_CALLOUT,
    RELIEF_CALLOUT,
    RELIEF_DIA,
    RELIEF_WIDTH,
    SHAFT_DIA,
    SHOULDER_DIA,
    SHOULDER_LENGTH,
    SHOULDER_SOUTH_Z_MM,
    SURFACE_FINISHES,
)
from rocker_bank_layout import PIVOT_SHAFT_LENGTH
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view, view_name


SPEC = DRAWINGS_BY_NAME["pivot_shaft"]
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

SHEET_SCALE = (1.0, 1.0)
# One orthographic view: the side view carries every turned diameter and
# length (policy rule 7), all authored on the Right-plane half-profile, so
# "*Right" imports them natively with the axis horizontal, as the bar sits in
# the lathe. Model -Z runs to the sheet's right: the shouldered north end
# (the part origin) is on the LEFT, the plain cut-to-fit end on the right.
# An end view would carry nothing, so this sheet has none.
PROFILE_CENTER = (0.150, 0.190)
_MM = SHEET_SCALE[0] / 1000.0
# The view centres on the bar's bounding box, domes included.
_OVERALL = PIVOT_SHAFT_LENGTH + 2.0 * DOME_HEIGHT
NORTH_END_X = PROFILE_CENTER[0] - (_OVERALL / 2.0 - DOME_HEIGHT) * _MM
SOUTH_END_X = NORTH_END_X + PIVOT_SHAFT_LENGTH * _MM
SHOULDER_X = (
    NORTH_END_X + JOURNAL_LENGTH * _MM,
    NORTH_END_X + (JOURNAL_LENGTH + SHOULDER_LENGTH) * _MM,
)
SHAFT_FLANK_Y = PROFILE_CENTER[1] + SHAFT_DIA * _MM / 2.0
SHAFT_UNDER_Y = PROFILE_CENTER[1] - SHAFT_DIA * _MM / 2.0
SHOULDER_TOP_Y = PROFILE_CENTER[1] + SHOULDER_DIA * _MM / 2.0
# The 160 shaft's isometric silhouette is a slender bar taller than the
# drawable band at 1:1, so the pictorial renders at 1:2 and says so.
ISO_CENTER = (0.330, 0.175)
ISO_SCALE = (1, 2)

# A short dimension's callout is far wider than the span it measures, so its
# text stands OUTSIDE the witness pair, clear of both lines, and the dimension
# line runs out under it: centred between them, both witnesses crossed "1.5
# BOTH ENDS" and "2.0 BOTH SHOULDER FACES" (r743-3 eye pass). Callout text
# runs ~2.75 mm a character at the template's dimension height (r743-3 render:
# "BOTH ENDS" 24.5 mm, "BOTH SHOULDER FACES" 52 mm).
CALLOUT_CHAR_WIDTH = 0.00275
CALLOUT_WITNESS_GAP = 0.003


def _left_of_witness(witness_x: float, callout: str) -> float:
    """Text centre x that ends a callout CALLOUT_WITNESS_GAP left of a witness."""
    return witness_x - CALLOUT_WITNESS_GAP - len(callout) * CALLOUT_CHAR_WIDTH / 2.0


PROFILE_KEEP = {
    # Under the bar, centred: the REF span the cut-to-fit callout governs.
    "ShaftLength": (PROFILE_CENTER[0], 0.158),
    # The two diameters stand clear of the ends they measure: the body's
    # past the plain end, the shoulder's before the north end.
    "ShaftDia": (SOUTH_END_X + 0.018, PROFILE_CENTER[1]),
    "ShoulderDia": (NORTH_END_X - 0.022, PROFILE_CENTER[1]),
    # The short axial lengths stack above the north end: journal, then
    # shoulder, each over the feature it spans.
    "JournalLength": ((NORTH_END_X + SHOULDER_X[0]) / 2.0, 0.210),
    "ShoulderLength": ((SHOULDER_X[0] + SHOULDER_X[1]) / 2.0, 0.226),
    # Under the north dome, left of the dome tip's witness: a short .X height
    # the "BOTH ENDS" callout makes a 2X statement. Its top stays under the
    # O10.00 dimension's lower arrow.
    "DomeHeight": (
        _left_of_witness(NORTH_END_X - DOME_HEIGHT * _MM, DOME_CALLOUT),
        0.172,
    ),
}
# Ra on the two running faces: the body the 20 hubs rock on, and the north
# journal in its ear. A revolved flank is a drawing SILHOUETTE, not a model
# edge, so the pick names that entity type; straight leaders keep off the
# geometry. The body's rides its top flank, the journal's its underside
# (the lengths stand over the journal).
# Note text height, as on the other part sheets: at the template default the
# symbols printed ~18 mm tall, the journal's over the profile and DETAIL A's
# over the length dimension (r743-2R render).
FINISH_CHAR_HEIGHT = 0.0025
BEARING_FINISH_EDGE = (PROFILE_CENTER[0] + 0.030, SHAFT_FLANK_Y)
BEARING_FINISH_SYMBOL = (BEARING_FINISH_EDGE[0], 0.206)
JOURNAL_FINISH_EDGE = ((NORTH_END_X + SHOULDER_X[0]) / 2.0, SHAFT_UNDER_Y)
JOURNAL_FINISH_SYMBOL = (JOURNAL_FINISH_EDGE[0] + 0.012, 0.172)

# DETAIL A: the shoulder and its two reliefs (Codex #936 PRRT_kwDOPHDy386mTMXq)
# are 2 x 0.33 features on a 1:1 sheet, so a native 5:1 detail carries their
# dimensions and the shoulder's thrust-face Ra (PRRT_kwDOPHDy386mTMXt). The
# fence centres on the axis mid-shoulder and takes in both grooves and the
# shoulder O.D.; the detail sits in the open field under the profile, left of
# the title block (x 0.218) and right of the notes.
DETAIL_SCALE = (5, 1)
DETAIL_RADIUS_MM = 6.0
DETAIL_CENTER = (0.180, 0.105)
DETAIL_FENCE_Z_MM = -(JOURNAL_LENGTH + SHOULDER_LENGTH / 2.0)
_DETAIL_MM = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
# The label anchors at its top centre, under the fence.
DETAIL_LABEL_XY = (
    DETAIL_CENTER[0],
    DETAIL_CENTER[1] - DETAIL_RADIUS_MM * _DETAIL_MM - 0.004,
)


def _detail_x(z_mm: float) -> float:
    """Sheet x of part station z in the detail: model -Z runs to the right."""
    return DETAIL_CENTER[0] - (z_mm - DETAIL_FENCE_Z_MM) * _DETAIL_MM


DETAIL_KEEP = {
    # Above the fence, left of the north groove's outer witness; the Ra
    # symbol takes the air on the right.
    "ReliefWidth": (
        _left_of_witness(_detail_x(-(JOURNAL_LENGTH - RELIEF_WIDTH)), RELIEF_CALLOUT),
        DETAIL_CENTER[1] + 0.037,
    ),
    # Left of the fence, on the axis: the diameter's line runs through the
    # north groove. At 42 mm out its callout ran across the fence (r743-2R).
    "ReliefDia": (DETAIL_CENTER[0] - 0.061, DETAIL_CENTER[1]),
}
# The thrust face's Ra: the leader lands on the face's upper half, between the
# relief floor and the shoulder O.D., and runs right, through the air over the
# south groove and the body, to a symbol outside the fence. Up-right of the
# face it crossed the ReliefWidth callout and the length dimension (r743-2R).
SHOULDER_FACE_X = _detail_x(SHOULDER_SOUTH_Z_MM)
SHOULDER_FINISH_ATTACH = (
    SHOULDER_FACE_X,
    DETAIL_CENTER[1] + (RELIEF_DIA + SHOULDER_DIA) / 4.0 * _DETAIL_MM,
)
SHOULDER_FINISH_SYMBOL = (
    DETAIL_CENTER[0] + DETAIL_RADIUS_MM * _DETAIL_MM + 0.002,
    SHOULDER_FINISH_ATTACH[1] + 0.003,
)


def _shoulder_detail(adapter: Any, profile: Any) -> Any:
    """A native 5:1 detail of the shoulder and its reliefs."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(profile, "IView")
    if not drawing.ActivateView(view_name(adapter, profile)):
        raise RuntimeError("failed to activate the shoulder detail's parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        profile,
        (0.0, 0.0, DETAIL_FENCE_Z_MM / 1000.0),
        label="shoulder detail centre",
    )
    radius = DETAIL_RADIUS_MM * SHEET_SCALE[0] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create the shoulder detail fence")
    detail = drawing.CreateDetailViewAt4(
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
        raise RuntimeError("failed to create the shoulder detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("the shoulder detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position the shoulder detail")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position the shoulder detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"the shoulder detail label did not persist: {actual}")
    return detail


def _shoulder_rim_edge(view: Any) -> Any:
    """The shoulder's O.D. circle at its south face: edge-on it IS that face's
    line, and its faces include the thrust face the control names."""
    matches = []
    for raw in visible_view_entities(view, 1, label="shoulder south rim"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        _cx, _cy, centre_z, *_axis, radius = (
            float(value) for value in curve.CircleParams
        )
        if abs(radius - SHOULDER_DIA / 2000.0) > 1e-7:
            continue
        if abs(centre_z - SHOULDER_SOUTH_Z_MM / 1000.0) > 1e-7:
            continue
        matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"expected one shoulder south rim edge, found {len(matches)}")
    return matches[0]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-shaft source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
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
            0: "Pivot Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pivot shaft; rocker bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    profile = place_view(adapter, str(SOURCE), "*Right", *PROFILE_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (profile, iso):
        set_hidden_lines_removed(adapter, view)

    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    detail = _shoulder_detail(adapter, profile)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="shoulder detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(
        adapter,
        [*profile_annotations, *detail_annotations],
        DRAWING_PRECISION_BY_NAME,
    )
    set_dimension_callouts(
        adapter,
        detail_annotations,
        {"ReliefWidth": RELIEF_CALLOUT, "ReliefDia": RELIEF_CALLOUT},
    )
    # #743 PR2: the plain end is cut to fit the installed brackets, so the
    # modelled length prints as a REFERENCE value and the callout under it is
    # the requirement. Keyed on the parametric name.
    length_annotations = [
        annotation
        for annotation in profile_annotations
        if dimension_name(adapter, annotation) == "ShaftLength"
    ]
    if len(length_annotations) != 1:
        raise RuntimeError("profile view does not carry exactly one shaft length")
    set_reference_dimension(adapter, length_annotations[0], label="pivot shaft length")
    set_dimension_callouts(adapter, length_annotations, {"ShaftLength": LENGTH_CALLOUT})
    set_dimension_callouts(adapter, profile_annotations, {"DomeHeight": DOME_CALLOUT})

    # The axis says which pairs of lines are diameters and is what the shop
    # indicates the bar on. The face pick sits mid-body, clear of every
    # placed annotation.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0] - 0.030, PROFILE_CENTER[1]),
        label="pivot shaft axis centerline",
    )
    add_surface_finish(
        adapter,
        profile,
        edge_xy=BEARING_FINISH_EDGE,
        entity_type="SILHOUETTE",
        symbol_xy=BEARING_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bearing"),
        label="pivot bearing finish",
        char_height=FINISH_CHAR_HEIGHT,
    )
    add_surface_finish(
        adapter,
        profile,
        edge_xy=JOURNAL_FINISH_EDGE,
        entity_type="SILHOUETTE",
        symbol_xy=JOURNAL_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_journal"),
        label="pivot journal finish",
        char_height=FINISH_CHAR_HEIGHT,
    )
    add_surface_finish(
        adapter,
        detail,
        edge_entity=_shoulder_rim_edge(detail),
        symbol_xy=SHOULDER_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "shoulder_thrust"),
        label="shoulder thrust-face finish",
        leader_attach_xy=SHOULDER_FINISH_ATTACH,
        char_height=FINISH_CHAR_HEIGHT,
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127); 0.020 clears it, and the
    # audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.085)
    add_property_linked_note(adapter, "Isometric View Note", 0.298, 0.118)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pivot Shaft Manufacturing Drawing",
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
